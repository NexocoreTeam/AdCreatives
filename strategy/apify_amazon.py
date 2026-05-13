"""Apify-powered Amazon Reviews scraper.

Many DTC brands (Poppi, Culture Pop, Spindrift) don't host product reviews
on their own websites — Amazon is the only viable source of star-rated,
unfiltered competitor sentiment.

Uses the `junglee/amazon-reviews-scraper` actor which accepts a list of
Amazon product URLs and returns full review text including:
  - Star rating (1-5)
  - Reviewer name, date, country
  - Title and full review body
  - Verified purchase flag
  - Helpful votes
  - Variant (size, flavor, etc.)

Reviews come pre-stratified by star rating, which matches our 5/3/1 gap
analysis framework directly.

The same Review dataclass shape used elsewhere in the repo is reused so
gap_analyzer doesn't need to know where the reviews came from.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from apify_client import ApifyClient

from strategy.reviews import Review

CLIENTS_DIR = Path("clients")
ACTOR_ID = "junglee/amazon-reviews-scraper"
DEFAULT_MAX_REVIEWS_PER_PRODUCT = 100

# Star filters Amazon's URL parameter accepts. The free Apify tier caps each
# call to ~8 reviews — by running 3 separate calls per product (one for 5-star,
# one for 3-star, one for 1-star) we get explicit stratification matching the
# user's 5/3/1 framework instead of a "recent"-biased mixed sample.
DEFAULT_STAR_FILTERS = ["five_star", "three_star", "one_star"]
ALL_STAR_FILTERS = ["five_star", "four_star", "three_star", "two_star", "one_star"]

STAR_FILTER_SHORT_NAMES = {
    "all_stars": "all",
    "five_star": "5s",
    "four_star": "4s",
    "three_star": "3s",
    "two_star": "2s",
    "one_star": "1s",
    "positive": "pos",
    "critical": "crit",
}


@dataclass
class AmazonReviewBundle:
    """Reviews scraped from one Amazon product page (one star-filter tier)."""
    product_url: str
    competitor_slug: str
    competitor_name: str
    asin: str = ""
    product_title: str = ""
    star_filter: str = "all_stars"   # which star tier this bundle represents
    reviews: list[Review] = field(default_factory=list)
    fetched_at: str = ""
    notes: str = ""

    def to_json(self) -> dict:
        return {
            "product_url": self.product_url,
            "competitor_slug": self.competitor_slug,
            "competitor_name": self.competitor_name,
            "asin": self.asin,
            "product_title": self.product_title,
            "star_filter": self.star_filter,
            "reviews": [asdict(r) for r in self.reviews],
            "fetched_at": self.fetched_at,
            "notes": self.notes,
        }


def _get_client() -> ApifyClient:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise EnvironmentError("APIFY_API_TOKEN not set. See .env.example")
    return ApifyClient(token)


def _extract_asin(url: str) -> str:
    """Pull the ASIN out of an Amazon product URL.

    Amazon URLs look like https://www.amazon.com/Brand-Product/dp/ASIN/...
    """
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return m.group(1) if m else ""


def scrape_amazon_reviews(
    product_url: str,
    competitor_slug: str,
    competitor_name: str,
    max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PRODUCT,
    sort: str = "recent",
    star_filter: str = "all_stars",
) -> AmazonReviewBundle:
    """Scrape reviews for one Amazon product via the junglee actor.

    sort options: 'recent', 'helpful' (default 'recent' for freshest signal).
    star_filter: 'all_stars' | 'five_star' | 'four_star' | 'three_star' |
                 'two_star' | 'one_star' | 'positive' | 'critical'
    """
    client = _get_client()
    asin = _extract_asin(product_url)
    bundle = AmazonReviewBundle(
        product_url=product_url,
        competitor_slug=competitor_slug,
        competitor_name=competitor_name,
        asin=asin,
        star_filter=star_filter,
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )

    run_input = {
        "productUrls": [{"url": product_url}],
        "maxReviews": max_reviews,
        "sortBy": sort,
        "filterByStar": star_filter,
        "scrapeProductDetails": True,
        "useCaptchaSolver": False,
        "proxyConfiguration": {"useApifyProxy": True},
    }

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=600)
    except Exception as e:
        bundle.notes = f"Apify call failed: {type(e).__name__}: {e}"
        return bundle

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        bundle.notes = "Apify run completed but returned no datasetId"
        return bundle

    items: list[dict] = []
    try:
        items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        bundle.notes = f"Failed to read Apify dataset: {type(e).__name__}: {e}"
        return bundle

    # junglee/amazon-reviews-scraper field schema:
    #   reviewTitle, reviewDescription, ratingScore, date, userId,
    #   productAsin, product (nested: {title, brand, stars, reviewsCount, ...}),
    #   isVerified, isAmazonVine, variant
    reviews: list[Review] = []
    for item in items:
        body = (
            item.get("reviewDescription")
            or item.get("reviewText")
            or item.get("reviewBody")
            or item.get("review")
            or ""
        )
        if not body:
            # Skip items without a body (metadata-only rows are rare for this actor,
            # but defensive)
            continue

        rating_raw = item.get("ratingScore") or item.get("rating") or item.get("stars") or 0
        try:
            rating = int(float(rating_raw))
        except (TypeError, ValueError):
            rating = 0

        # Capture product metadata from the nested `product` block (first seen wins)
        product_block = item.get("product") or {}
        if isinstance(product_block, dict):
            if not bundle.product_title and product_block.get("title"):
                bundle.product_title = str(product_block["title"])[:300]

        # Reviewer: actor exposes userId; full name isn't surfaced. Use userId as anonymous handle.
        reviewer = item.get("userId") or item.get("reviewerName") or item.get("author") or ""

        product_name = (
            (product_block.get("title") if isinstance(product_block, dict) else None)
            or item.get("productTitle")
            or bundle.product_title
            or ""
        )

        reviews.append(Review(
            title=str(item.get("reviewTitle") or item.get("title") or "")[:200],
            body=str(body)[:5000],
            rating=rating,
            reviewer=str(reviewer)[:120],
            date=str(item.get("date") or item.get("reviewDate") or ""),
            product_name=str(product_name)[:300],
            product_id=asin,
        ))

    bundle.reviews = reviews
    if not reviews:
        bundle.notes = f"Run completed but yielded 0 reviews from {len(items)} dataset items"
    else:
        # Note the free-tier cap if we hit it
        if len(reviews) <= 8:
            bundle.notes = (
                f"{len(reviews)} reviews extracted. Apify free tier caps each run at "
                f"~8 reviews; upgrade to the Starter plan to access more."
            )
    return bundle


def cache_amazon_bundle(client_slug: str, bundle: AmazonReviewBundle) -> Path:
    """Persist an Amazon review bundle under research/amazon-reviews/.

    Filename pattern: <competitor-slug>-<asin>-<short-star>.json
    e.g. poppi-B09B8CCPCZ-5s.json (5-star tier), poppi-B09B8CCPCZ-1s.json.
    """
    out_dir = CLIENTS_DIR / client_slug / "research" / "amazon-reviews"
    out_dir.mkdir(parents=True, exist_ok=True)
    asin_part = bundle.asin or re.sub(r"[^a-zA-Z0-9]+", "-", bundle.product_url)[:20]
    star_part = STAR_FILTER_SHORT_NAMES.get(bundle.star_filter, bundle.star_filter)
    path = out_dir / f"{bundle.competitor_slug}-{asin_part}-{star_part}.json"
    path.write_text(json.dumps(bundle.to_json(), indent=2), encoding="utf-8")
    return path


def load_cached_amazon_bundles(client_slug: str) -> list[AmazonReviewBundle]:
    """Reload all cached Amazon review bundles for downstream gap analysis.

    Tolerates legacy bundles (pre-star-filter) that lack a star_filter field.
    """
    raw_dir = CLIENTS_DIR / client_slug / "research" / "amazon-reviews"
    if not raw_dir.exists():
        return []
    bundles: list[AmazonReviewBundle] = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        reviews = [Review(**r) for r in data.get("reviews", [])]
        bundles.append(AmazonReviewBundle(
            product_url=data.get("product_url", ""),
            competitor_slug=data.get("competitor_slug", ""),
            competitor_name=data.get("competitor_name", ""),
            asin=data.get("asin", ""),
            product_title=data.get("product_title", ""),
            star_filter=data.get("star_filter", "all_stars"),
            reviews=reviews,
            fetched_at=data.get("fetched_at", ""),
            notes=data.get("notes", ""),
        ))
    return bundles
