"""Competitor research orchestrator.

For each competitor in clients/<slug>/competitors.yaml:
1. Scrape their homepage HTML via Firecrawl
2. Detect their review widget vendor (Okendo / Yotpo / Judge.me / Loox / Stamped)
3. Pull reviews via the vendor's public API
4. If the homepage has no widget, walk a few product pages and try again
5. Cache the raw reviews to disk for downstream gap analysis

This is the on-site review layer. It complements the Exa layer (Reddit / Trustpilot
/ news / sentiment from the open web) — between them we have both filtered
(brand-curated, on-site) and unfiltered (open web) competitor sentiment.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from strategy.firecrawl_client import firecrawl_map_urls, firecrawl_scrape_html
from strategy.reviews import Review, VendorSignal, detect_review_vendor, fetch_product_reviews

CLIENTS_DIR = Path("clients")
MAX_PRODUCT_PAGES_TO_TRY = 5
DEFAULT_REVIEW_LIMIT = 200


@dataclass
class Competitor:
    name: str
    slug: str
    url: str
    type: str = "direct"           # direct | adjacent | switch-from
    priority: str = "tier1"        # tier1 | tier2 | tier3
    notes: str = ""
    amazon_urls: list[str] = field(default_factory=list)  # Amazon product URLs for review scraping


@dataclass
class CompetitorReviewBundle:
    """Everything we pulled for one competitor."""
    competitor: Competitor
    vendor: str = "none"           # which review widget they use
    reviews: list[Review] = field(default_factory=list)
    scraped_pages: list[str] = field(default_factory=list)
    fetched_at: str = ""
    notes: str = ""

    def to_json(self) -> dict:
        return {
            "competitor": asdict(self.competitor),
            "vendor": self.vendor,
            "reviews": [asdict(r) for r in self.reviews],
            "scraped_pages": self.scraped_pages,
            "fetched_at": self.fetched_at,
            "notes": self.notes,
        }


def load_competitors(client_slug: str) -> list[Competitor]:
    """Load competitors.yaml for a client. Returns [] if missing."""
    path = CLIENTS_DIR / client_slug / "competitors.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("competitors", [])
    competitors: list[Competitor] = []
    for item in raw:
        competitors.append(Competitor(
            name=item.get("name", ""),
            slug=item.get("slug", ""),
            url=item.get("url", ""),
            type=item.get("type", "direct"),
            priority=item.get("priority", "tier1"),
            notes=item.get("notes", ""),
            amazon_urls=item.get("amazon_urls", []) or [],
        ))
    return competitors


def _extract_product_urls_from_html(html: str, base_url: str) -> list[str]:
    """Best-effort: find /products/<handle> links in raw HTML."""
    if not html:
        return []
    matches = re.findall(r'href=["\'](/products/[^"\'?#]+)["\']', html)
    seen: set[str] = set()
    out: list[str] = []
    for m in matches:
        if m in seen:
            continue
        seen.add(m)
        base = base_url.rstrip("/")
        out.append(f"{base}{m}")
    return out


def pull_competitor_reviews(
    competitor: Competitor,
    review_limit: int = DEFAULT_REVIEW_LIMIT,
) -> CompetitorReviewBundle:
    """Try to pull on-site reviews for one competitor.

    Strategy:
      1. Map the site for /products/* URLs (Firecrawl's sitemap).
      2. Scrape up to N product pages. Reviews almost always live on product
         pages, not the homepage.
      3. Fall back to the homepage only if no product pages were found.
      4. Stop as soon as we get reviews.
    """
    bundle = CompetitorReviewBundle(
        competitor=competitor,
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )

    # 1. Find product pages first (where reviews actually live)
    product_urls: list[str] = []
    try:
        mapped = firecrawl_map_urls(competitor.url, limit=80) or []
        product_urls = [u for u in mapped if "/products/" in u]
    except Exception:
        product_urls = []

    # If no product URLs from sitemap, fall back to homepage + product-link extraction
    if not product_urls:
        homepage_html = firecrawl_scrape_html(competitor.url)
        if homepage_html:
            bundle.scraped_pages.append(competitor.url)
            product_urls = _extract_product_urls_from_html(homepage_html, competitor.url)
            # Try the homepage too in case reviews live there (rare)
            signal = detect_review_vendor(homepage_html)
            if signal.vendor != "none":
                bundle.vendor = signal.vendor
                reviews, _ = fetch_product_reviews(
                    html=homepage_html,
                    product_url=competitor.url,
                    base_url=competitor.url,
                    limit=review_limit,
                )
                if reviews:
                    bundle.reviews = reviews
                    return bundle

    if not product_urls:
        bundle.notes = (
            f"No product pages found for {competitor.url}. "
            f"Site may not be Shopify or sitemap is unavailable."
        )
        return bundle

    # 2. Try product pages, one at a time, until we get reviews
    detected_vendors: list[str] = []
    for product_url in product_urls[:MAX_PRODUCT_PAGES_TO_TRY]:
        product_html = firecrawl_scrape_html(product_url)
        if not product_html:
            continue
        bundle.scraped_pages.append(product_url)

        page_signal = detect_review_vendor(product_html)
        if page_signal.vendor != "none":
            detected_vendors.append(page_signal.vendor)
            bundle.vendor = page_signal.vendor

        reviews, _ = fetch_product_reviews(
            html=product_html,
            product_url=product_url,
            base_url=competitor.url,
            limit=review_limit,
        )
        if reviews:
            bundle.reviews = reviews
            return bundle

    if not bundle.reviews:
        unique_vendors = sorted(set(detected_vendors)) if detected_vendors else ["none"]
        bundle.notes = (
            f"No reviews extracted from {len(bundle.scraped_pages)} page(s). "
            f"Detected vendors: {', '.join(unique_vendors)}. "
            f"Either no supported review widget is present or vendor identifiers "
            f"could not be parsed."
        )
    return bundle


def cache_competitor_bundle(client_slug: str, bundle: CompetitorReviewBundle) -> Path:
    """Persist a competitor's review bundle."""
    out_dir = CLIENTS_DIR / client_slug / "research" / "competitor-reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{bundle.competitor.slug}.json"
    path.write_text(json.dumps(bundle.to_json(), indent=2), encoding="utf-8")
    return path


def load_cached_competitor_bundles(client_slug: str) -> list[CompetitorReviewBundle]:
    """Reload all cached competitor bundles."""
    raw_dir = CLIENTS_DIR / client_slug / "research" / "competitor-reviews"
    if not raw_dir.exists():
        return []
    bundles: list[CompetitorReviewBundle] = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        competitor = Competitor(**data["competitor"])
        reviews = [Review(**r) for r in data.get("reviews", [])]
        bundles.append(CompetitorReviewBundle(
            competitor=competitor,
            vendor=data.get("vendor", "none"),
            reviews=reviews,
            scraped_pages=data.get("scraped_pages", []),
            fetched_at=data.get("fetched_at", ""),
            notes=data.get("notes", ""),
        ))
    return bundles
