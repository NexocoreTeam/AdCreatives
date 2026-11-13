"""Star tiers for Amazon review pulls: call order and the checks on what came back.

Standard library only, so `adc status` can check saved files without loading
the Apify client.
"""

from __future__ import annotations

from collections.abc import Iterable

# Ratings each tier may hold; all_stars may hold any.
TIER_RATINGS: dict[str, frozenset[int]] = {
    "five_star": frozenset({5}),
    "four_star": frozenset({4}),
    "three_star": frozenset({3}),
    "two_star": frozenset({2}),
    "one_star": frozenset({1}),
    "positive": frozenset({4, 5}),
    "critical": frozenset({1, 2, 3}),
}
# A tier counts as unfiltered once this share of its reviews, and at least
# MIN_OFF_TIER of them, carry other ratings.
OFF_TIER_SHARE = 0.1
MIN_OFF_TIER = 2

# research-amazon calls tiers rarest first. An actor that ignores the filter
# answers mostly 5-star, so a 1-star call exposes it at once, while a 5-star
# call could pass the check and be saved under the wrong label.
TIER_CALL_ORDER = ["one_star", "two_star", "three_star", "four_star", "five_star", "all_stars"]

# Notes of a pull that failed. Such a tier must stay retryable, not be kept as
# a real empty tier.
FAILED_PULL_PREFIXES = ("Apify call failed", "Apify run completed", "Failed to read Apify")


def rating_value(value: object) -> int:
    """A review's star rating as an int; 0 when it can't be read."""
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def off_tier_count(star_filter: str, ratings: Iterable[int]) -> int:
    """Ratings outside the tier. Unreadable (0) ratings don't count."""
    allowed = TIER_RATINGS.get(star_filter)
    if not allowed:
        return 0
    return sum(1 for rating in ratings if rating and rating not in allowed)


def tier_looks_unfiltered(star_filter: str, ratings: list[int]) -> bool:
    """True when a tier came back with other ratings, i.e. the actor did not filter."""
    off_tier = off_tier_count(star_filter, ratings)
    return off_tier >= MIN_OFF_TIER and off_tier >= OFF_TIER_SHARE * len(ratings)


def pull_failed(review_count: int, notes: str) -> bool:
    """True for a tier with no reviews because the pull failed, not because there were none."""
    return not review_count and (notes or "").startswith(FAILED_PULL_PREFIXES)


def _saved_ratings(data: dict) -> list[int]:
    reviews = data.get("reviews") or []
    return [rating_value(review.get("rating")) for review in reviews if isinstance(review, dict)]


def saved_tier_unfiltered(data: object) -> bool:
    """True when a saved tier file holds other ratings (saved while the filter was ignored)."""
    if not isinstance(data, dict):
        return False
    return tier_looks_unfiltered(str(data.get("star_filter") or "all_stars"), _saved_ratings(data))


def saved_tier_failed(data: object) -> bool:
    """True when a saved tier file is a failed pull kept from before failures stayed retryable."""
    if not isinstance(data, dict):
        return False
    return pull_failed(len(data.get("reviews") or []), str(data.get("notes") or ""))


def rarest_first(star_filters: list[str]) -> list[str]:
    """A new list of the tiers in call order, rarest ratings first, without repeats.

    Tiers outside TIER_CALL_ORDER keep their order after the known ones.
    """
    known = [tier for tier in TIER_CALL_ORDER if tier in star_filters]
    others = [tier for tier in dict.fromkeys(star_filters) if tier not in TIER_CALL_ORDER]
    return known + others
