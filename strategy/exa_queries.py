"""Pure Exa query planning — what to ask, how to label it, where it caches.

No network calls and no exa_py import. Split from exa_research so consumers
that only need the query plan (status dashboard, tests) don't pull in the
SDK. The cache filename convention lives here too: a query's raw result is
cached at clients/<slug>/research/exa/raw/<cache_stem(label)>.json and its
failure record at clients/<slug>/research/exa/errors/<cache_stem(label)>.json,
so plan and filesystem can always be compared 1:1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_NUM_RESULTS = 10


@dataclass
class ExaQuery:
    """One Exa query plan: what to ask, where to look, how to label it."""
    label: str                            # short slug used in filenames
    query: str
    include_domains: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    num_results: int = DEFAULT_NUM_RESULTS
    category: str = "general"             # general | reddit | comparison | reviews | category-discussion
    # Keyword-engine variant of `query`. Exa's neural phrasing ("X honest
    # review experience worth it") returns junk on keyword engines like
    # Reddit search — set this to a sharp form ('"X" review') for the
    # Reddit API / Apify fallback paths. Empty = fall back to `query`.
    keyword_query: str = ""


def slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60]


def cache_stem(label: str) -> str:
    """Filename stem for a query's cache file (raw/ and errors/)."""
    return slugify(label)


def reddit_search_terms(query: ExaQuery) -> tuple[str, str]:
    """(search string, must-contain filter) for keyword search engines.

    The filter is the first quoted phrase in the keyword query — results
    that never mention it are junk (Reddit search pads weak matches with
    trending content) and callers should drop them. Empty filter = keep all.
    """
    search = query.keyword_query or query.query
    m = re.search(r'"([^"]+)"', search)
    return search, (m.group(1) if m else "")


def default_queries_for_brand(
    brand_name: str,
    competitors: list[str] | None = None,
    category_terms: list[str] | None = None,
) -> list[ExaQuery]:
    """Starter set of queries for any brand. Returns ~7-10 queries.

    Expand with competitor list when you have one — adds N*2 more queries.
    """
    queries: list[ExaQuery] = [
        ExaQuery(
            label=f"reddit-{brand_name}-honest",
            query=f"{brand_name} honest review experience",
            include_domains=["reddit.com"],
            category="reddit",
            keyword_query=f'"{brand_name}" review',
        ),
        ExaQuery(
            label=f"reddit-{brand_name}-worth-it",
            query=f"is {brand_name} worth it",
            include_domains=["reddit.com"],
            category="reddit",
            keyword_query=f'"{brand_name}" worth it',
        ),
        ExaQuery(
            label=f"web-{brand_name}-concerns",
            query=f"{brand_name} problems concerns issues complaints",
            exclude_domains=[],
            category="reviews",
        ),
        ExaQuery(
            label=f"web-{brand_name}-taste-review",
            query=f"{brand_name} taste review what does it taste like",
            category="reviews",
        ),
        ExaQuery(
            label=f"web-{brand_name}-ingredients",
            query=f"{brand_name} ingredients what's in it explained",
            category="reviews",
        ),
    ]

    if competitors:
        for comp in competitors:
            queries.append(ExaQuery(
                label=f"reddit-{brand_name}-vs-{comp}",
                query=f"{brand_name} vs {comp}",
                include_domains=["reddit.com"],
                category="comparison",
                keyword_query=f'"{brand_name}" vs "{comp}"',
            ))
            queries.append(ExaQuery(
                label=f"web-{comp}-honest",
                query=f"{comp} honest review",
                category="reviews",
            ))

    if category_terms:
        for term in category_terms:
            queries.append(ExaQuery(
                label=f"reddit-category-{slugify(term)}",
                query=f"best {term} reddit recommendation",
                include_domains=["reddit.com"],
                category="category-discussion",
            ))

    return queries


def competitive_queries_for_brand(
    own_brand: str,
    competitor_names: list[str],
) -> list[ExaQuery]:
    """Sentiment-stratified query set for competitive gap analysis.

    Per brand (own + each competitor):
      - 'positive' query (surfaces what people love → table stakes)
      - 'mixed' query (surfaces the 3-star equivalent → GAPS)
      - 'negative' query (surfaces 1-star equivalent → dealbreakers)
      - 'reddit honest' query (livecrawl, surfaces the 'why' behind sentiment)
      - 'trustpilot' query (page-level Trustpilot search snippets — NOT parsed
        review objects with star ratings; treat as sentiment, not structured data)
    """
    queries: list[ExaQuery] = []
    all_brands = [own_brand] + competitor_names

    for brand in all_brands:
        b_slug = slugify(brand)
        queries.extend([
            ExaQuery(
                label=f"web-{b_slug}-love",
                query=f"{brand} best love amazing favorite review",
                category="positive",
            ),
            ExaQuery(
                label=f"web-{b_slug}-mixed",
                query=f"{brand} review pros cons mixed feelings okay but wish",
                category="mixed",
            ),
            ExaQuery(
                label=f"web-{b_slug}-complaints",
                query=f"{brand} disappointed problems side effects don't buy bad review",
                category="negative",
            ),
            ExaQuery(
                label=f"reddit-{b_slug}-honest",
                query=f"{brand} honest review experience worth it",
                include_domains=["reddit.com"],
                category="reddit",
                keyword_query=f'"{brand}" review',
            ),
            ExaQuery(
                label=f"trustpilot-{b_slug}",
                query=f"{brand} reviews",
                include_domains=["trustpilot.com"],
                category="trustpilot",
            ),
        ])

    return queries
