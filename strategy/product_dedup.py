"""Near-duplicate product detection.

Guards against the same physical product entering clients/<slug>/products/
twice under slightly different names — e.g. an operator-typed "Palladino"
next to the site-extracted "Espresso Paladino". Slug equality is not enough:
misspellings and partial names slip through, and a placeholder product file
then confuses downstream product selection and brief generation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from difflib import SequenceMatcher

# "palladino" vs "paladino" scores 0.94; unrelated coffee words score < 0.7.
_TOKEN_MATCH_RATIO = 0.84


def _tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]


def _fuzzy_in(token: str, pool: list[str]) -> bool:
    return any(
        token == other
        or SequenceMatcher(None, token, other).ratio() >= _TOKEN_MATCH_RATIO
        for other in pool
    )


def find_near_duplicate(candidate: str, existing: Iterable[str]) -> str | None:
    """Return the first existing name/slug that looks like the same product.

    Match rule: the smaller token set must fuzzy-map entirely into the larger
    one, so "palladino" matches "espresso-paladino". Products that merely
    share a word ("colombia blend" vs "colombia decaf") don't match because
    the extra token has no counterpart.

    `candidate` and `existing` entries can be display names or slugs — both
    are reduced to token sets. Exact-equal strings are NOT reported as
    duplicates; re-writing the same slug is the caller's idempotent-update
    path.
    """
    cand_tokens = _tokens(candidate)
    if not cand_tokens:
        return None
    for other in existing:
        other_tokens = _tokens(other)
        if not other_tokens or other_tokens == cand_tokens:
            continue
        small, large = sorted([cand_tokens, other_tokens], key=len)
        if all(_fuzzy_in(t, large) for t in small):
            return other
    return None
