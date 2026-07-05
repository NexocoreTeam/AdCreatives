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

import httpx
import yaml

from strategy.firecrawl_client import firecrawl_map_urls, firecrawl_scrape_html
from strategy.researcher import USER_AGENT
from strategy.reviews import Review, fetch_product_reviews

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
    # Foreplay brand identifier (20-char alphanumeric) — drives `adc competitor-ads`.
    # Grab from app.foreplay.co's brand-page URL. Optional; competitors without an
    # id are skipped by competitor-ads but still used by review/research flows.
    foreplay_brand_id: str = ""
    # ─── Tier 3 social handles (optional) ──────────────────────────────────
    # All optional — `adc research-social` skips per-competitor for any handle
    # that's empty. Backwards compatible with existing competitors.yaml files.
    # tiktok_handle:        "@secondkind" or "secondkind"
    # tiktok_post_urls:     specific posts to pull comments from
    # instagram_handle:     "secondkind"
    # instagram_post_urls:  specific posts to pull comments from
    # youtube_channel_id:   canonical UCxxxx channel ID
    # youtube_handle:       "@secondkind" — resolved to channel_id at fetch time
    # youtube_video_ids:    specific videos to pull comments from
    # youtube_search_queries: review/comparison searches ("<brand> review") —
    #                       auto-discovers third-party videos with real VOC
    tiktok_handle: str = ""
    tiktok_post_urls: list[str] = field(default_factory=list)
    # UGC-search queries — when set (and post_urls is empty), the scraper runs
    # an Apify search-actor to auto-discover user-generated review videos
    # matching these queries. Higher signal per dollar than brand-owned posts
    # for most categories.
    tiktok_search_queries: list[str] = field(default_factory=list)
    instagram_handle: str = ""
    instagram_post_urls: list[str] = field(default_factory=list)
    instagram_hashtags: list[str] = field(default_factory=list)
    youtube_channel_id: str = ""
    youtube_handle: str = ""
    youtube_video_ids: list[str] = field(default_factory=list)
    youtube_search_queries: list[str] = field(default_factory=list)


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
            foreplay_brand_id=item.get("foreplay_brand_id", "") or "",
            tiktok_handle=item.get("tiktok_handle", "") or "",
            tiktok_post_urls=item.get("tiktok_post_urls", []) or [],
            tiktok_search_queries=item.get("tiktok_search_queries", []) or [],
            instagram_handle=item.get("instagram_handle", "") or "",
            instagram_post_urls=item.get("instagram_post_urls", []) or [],
            instagram_hashtags=item.get("instagram_hashtags", []) or [],
            youtube_channel_id=item.get("youtube_channel_id", "") or "",
            youtube_handle=item.get("youtube_handle", "") or "",
            youtube_video_ids=item.get("youtube_video_ids", []) or [],
            youtube_search_queries=item.get("youtube_search_queries", []) or [],
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


def _fetch_html(url: str) -> str:
    """Firecrawl when configured, plain httpx otherwise. Empty string on failure.

    The Firecrawl module returns None whenever FIRECRAWL_API_KEY is unset, so
    without this fallback the on-site review layer silently collects nothing.
    Static HTML is enough here: vendor widget signatures and JSON-LD review
    blocks are server-rendered on most storefronts.
    """
    html = firecrawl_scrape_html(url)
    if html:
        return html
    try:
        with httpx.Client(
            timeout=20.0, follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(url)
        if resp.status_code == 200:
            return resp.text
    except httpx.HTTPError:
        pass
    return ""


def _shopify_products_json_urls(base_url: str, limit: int = 25) -> list[str]:
    """PDP discovery via Shopify's public /products.json listing.

    Works without Firecrawl or a sitemap. Returns [] for non-Shopify sites.
    """
    base = base_url.rstrip("/")
    try:
        with httpx.Client(
            timeout=20.0, follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = client.get(f"{base}/products.json", params={"limit": limit})
        if resp.status_code != 200:
            return []
        products = resp.json().get("products", []) or []
    except (httpx.HTTPError, ValueError):
        return []
    return [f"{base}/products/{p['handle']}" for p in products if p.get("handle")]


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

    # 1. Find product pages first (where reviews actually live).
    #    Discovery chain: Firecrawl /map → Shopify /products.json → homepage links.
    product_urls: list[str] = []
    try:
        mapped = firecrawl_map_urls(competitor.url, limit=80) or []
        product_urls = [u for u in mapped if "/products/" in u]
    except Exception:
        product_urls = []

    if not product_urls:
        product_urls = _shopify_products_json_urls(competitor.url)

    if not product_urls:
        homepage_html = _fetch_html(competitor.url)
        if homepage_html:
            bundle.scraped_pages.append(competitor.url)
            product_urls = _extract_product_urls_from_html(homepage_html, competitor.url)
            # Try the homepage too in case reviews live there (rare)
            reviews, signal = fetch_product_reviews(
                html=homepage_html,
                product_url=competitor.url,
                base_url=competitor.url,
                limit=review_limit,
            )
            if signal.vendor != "none":
                bundle.vendor = signal.vendor
            if reviews:
                bundle.reviews = reviews
                return bundle

    if not product_urls:
        bundle.notes = (
            f"No product pages found for {competitor.url}. "
            f"Site may not be Shopify, or sitemap//products.json is unavailable."
        )
        return bundle

    # 2. Try product pages, one at a time, until we get reviews
    detected_vendors: list[str] = []
    for product_url in product_urls[:MAX_PRODUCT_PAGES_TO_TRY]:
        product_html = _fetch_html(product_url)
        if not product_html:
            continue
        bundle.scraped_pages.append(product_url)

        reviews, page_signal = fetch_product_reviews(
            html=product_html,
            product_url=product_url,
            base_url=competitor.url,
            limit=review_limit,
        )
        if page_signal.vendor != "none":
            detected_vendors.append(page_signal.vendor)
            bundle.vendor = page_signal.vendor

        if reviews:
            bundle.reviews = reviews
            return bundle

    if not bundle.reviews:
        unique_vendors = sorted(set(detected_vendors)) if detected_vendors else ["none"]
        bundle.notes = (
            f"No reviews extracted from {len(bundle.scraped_pages)} page(s). "
            f"Detected vendors: {', '.join(unique_vendors)}. "
            f"No supported widget API and no JSON-LD review markup — for this "
            f"competitor, rely on Exa/Reddit/Amazon/social sources instead."
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
