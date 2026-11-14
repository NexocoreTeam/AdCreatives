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

from strategy.amazon_tiers import off_tier_count, tier_looks_unfiltered
from strategy.reviews import Review

CLIENTS_DIR = Path("clients")
ACTOR_ID = "junglee/amazon-reviews-scraper"
DEFAULT_MAX_REVIEWS_PER_PRODUCT = 100
ACTOR_MAX_REVIEWS_PER_TIER = 100  # the actor returns no more than this per star tier
PRICE_PER_REVIEW_USD = 0.006  # Apify free-plan price for this actor, Nov 2026

# One actor run per star tier (5-star, 3-star, 1-star by default) gives each
# tier of the 5/3/1 framework up to 100 reviews of its own (the actor's limit
# per tier); an unfiltered run stops at 100 across all ratings.
DEFAULT_STAR_FILTERS = ["five_star", "three_star", "one_star"]
ALL_STAR_FILTERS = ["five_star", "four_star", "three_star", "two_star", "one_star"]

# Our tier names -> the actor's `filterByRatings` values. The actor ignores
# input fields it does not know, so a wrong field name silently returns an
# unfiltered run (it did for months under `filterByStar`).
ACTOR_RATING_FILTERS = {
    "all_stars": "allStars",
    "five_star": "fiveStar",
    "four_star": "fourStar",
    "three_star": "threeStar",
    "two_star": "twoStar",
    "one_star": "oneStar",
    "positive": "positive",
    "critical": "critical",
}
SORT_OPTIONS = ("helpful", "recent")
RUN_SUCCEEDED = "SUCCEEDED"
FILTER_IGNORED_NOTE = "STAR FILTER IGNORED"

# On Apify's free plan the actor returns at most 10 reviews per run, from one
# URL. Its status message then asks for an upgrade, also when fewer came back:
# "... upgrade to the Starter plan" when done, "as a free user ... consider
# upgrading your plan" while running (Nov 2026).
PLAN_LIMIT_PHRASES = ("upgrade", "upgrading", "free user")
PLAN_LIMIT_NOTE = "Apify free plan: 10 reviews per run max"

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


def _plan_limited(run: dict) -> bool:
    """True when the run's status message says the Apify plan limits it."""
    message = run.get("statusMessage")
    if not isinstance(message, str):
        return False
    return any(phrase in message.lower() for phrase in PLAN_LIMIT_PHRASES)


def scrape_amazon_reviews(
    product_url: str,
    competitor_slug: str,
    competitor_name: str,
    max_reviews: int = DEFAULT_MAX_REVIEWS_PER_PRODUCT,
    sort: str = "helpful",
    star_filter: str = "all_stars",
) -> AmazonReviewBundle:
    """Scrape reviews for one Amazon product via the junglee actor.

    sort options: 'helpful' (Amazon's "Top reviews", the actor's default and
    what every run got while the sort field was misnamed) or 'recent'.
    star_filter: 'all_stars' | 'five_star' | 'four_star' | 'three_star' |
                 'two_star' | 'one_star' | 'positive' | 'critical'
    """
    if star_filter not in ACTOR_RATING_FILTERS:
        raise ValueError(f"Unknown star filter {star_filter!r}")
    if sort not in SORT_OPTIONS:
        raise ValueError(f"Unknown sort {sort!r}; use one of {', '.join(SORT_OPTIONS)}")
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

    # No proxy setting: the actor's input schema has no proxy field, and the
    # actor calls `proxyConfiguration` deprecated (Nov 2026).
    run_input = {
        "productUrls": [{"url": product_url}],
        "maxReviews": max_reviews,
        "sort": sort,
        "filterByRatings": [ACTOR_RATING_FILTERS[star_filter]],
        "scrapeProductDetails": True,
        "useCaptchaSolver": False,
    }

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input, timeout_secs=600)
    except Exception as e:
        bundle.notes = f"Apify call failed: {type(e).__name__}: {e}"
        return bundle

    status = run.get("status") if isinstance(run, dict) else None
    if status != RUN_SUCCEEDED:
        # call() returns a FAILED, TIMED-OUT or ABORTED run without raising. Its
        # dataset is not a real "no reviews in this tier" and must not be cached.
        ended = f"run ended {status}" if status else "no run record"
        bundle.notes = f"Apify call failed: {ended} ({ACTOR_ID})"
        return bundle

    dataset_id = run.get("defaultDatasetId")
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
    elif star_filter_ignored(bundle):
        short = STAR_FILTER_SHORT_NAMES.get(star_filter, star_filter)
        off_tier = off_tier_count(star_filter, [review.rating for review in reviews])
        bundle.notes = (
            f"{FILTER_IGNORED_NOTE}: {off_tier} of {len(reviews)} "
            f"reviews are outside the {short} tier"
        )
    elif _plan_limited(run):
        bundle.notes = PLAN_LIMIT_NOTE
    return bundle


def star_filter_ignored(bundle: AmazonReviewBundle) -> bool:
    """True when the actor answered a tier with other ratings, i.e. it did not filter."""
    return tier_looks_unfiltered(bundle.star_filter, [review.rating for review in bundle.reviews])


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
