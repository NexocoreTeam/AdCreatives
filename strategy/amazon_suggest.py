"""Amazon listing candidates per competitor — suggest, never auto-add.

Full auto-discovery stays off by design (reseller lookalikes poison review
mining), but hunting listings manually is busywork. This runs one Exa query
per competitor and extracts amazon.com product URLs for a human yes/no;
confirmed URLs go into competitors.yaml by hand (the explicit-URL contract
in pipeline-rules rule 6 stands).
"""

from __future__ import annotations

import re

from strategy.exa_queries import ExaQuery, slugify
from strategy.exa_research import ExaHit, run_query

AMAZON_PRODUCT_RE = re.compile(
    r"https?://(?:www\.)?amazon\.com/(?:[^\s\"']*?/)?(?:dp|gp/product)/([A-Z0-9]{10})"
)


def _brand_tokens(brand_name: str) -> list[str]:
    tokens = [t.lower() for t in re.findall(r"[A-Za-z0-9]+", brand_name) if len(t) >= 5]
    if tokens:
        return tokens
    name = brand_name.strip().lower()
    return [name] if name else []


def candidates_from_hits(hits: list[ExaHit], brand_name: str = "") -> list[dict]:
    """Extract deduped Amazon product candidates from search hits.

    Scans both hit URLs and hit text (listing URLs often appear inside
    roundup-article bodies). Canonicalizes to /dp/<ASIN>.

    With brand_name given, candidates whose surrounding context never
    mentions a brand token are dropped — Exa's wide fallback surfaces
    recurring noise (books, watches, generic hardware) that otherwise
    reaches the operator for manual rejection (found live on the
    expand-furniture kickoff: 8 of 12 candidates were noise).
    """
    tokens = _brand_tokens(brand_name)
    seen: set[str] = set()
    candidates: list[dict] = []
    for hit in hits:
        for source in (hit.url or "", hit.text or ""):
            for match in AMAZON_PRODUCT_RE.finditer(source):
                asin = match.group(1)
                if asin in seen:
                    continue
                window = (
                    f"{hit.title or ''} "
                    + source[max(0, match.start() - 150):match.end() + 150]
                ).lower()
                if tokens and not any(t in window for t in tokens):
                    continue
                seen.add(asin)
                candidates.append({
                    "asin": asin,
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "context": (hit.title or hit.url or "")[:80],
                })
    return candidates


def suggest_amazon_candidates(
    competitor_name: str,
    num_results: int = 8,
) -> list[dict]:
    """One Exa query for a competitor's Amazon listings.

    Tries an amazon.com-scoped search first; if Exa refuses the domain
    (as it now does for reddit.com), falls back to an unfiltered query and
    relies on the URL regex to keep only real product pages.
    """
    scoped = ExaQuery(
        label=f"amazon-suggest-{slugify(competitor_name)}",
        query=f'"{competitor_name}"',
        include_domains=["amazon.com"],
        num_results=num_results,
        category="amazon-suggest",
    )
    try:
        result = run_query(scoped)
        candidates = candidates_from_hits(result.results, brand_name=competitor_name)
        if candidates:
            return candidates
    except Exception:
        pass  # domain refused or transient — the unfiltered pass decides

    unfiltered = ExaQuery(
        label=f"amazon-suggest-{slugify(competitor_name)}-wide",
        query=f"{competitor_name} amazon.com product listing",
        num_results=num_results,
        category="amazon-suggest",
    )
    result = run_query(unfiltered)
    return candidates_from_hits(result.results, brand_name=competitor_name)
