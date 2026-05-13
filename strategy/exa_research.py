"""Exa-powered web research for unfiltered Voice of Customer.

On-site reviews are curated. This module reaches the messier truth:
- Reddit threads about the brand
- Comparison posts ("X vs Y")
- Third-party review aggregators (Trustpilot, SiteJabber)
- Discussion forums

Results are cached per-query under `clients/<slug>/research/exa/raw/` so
we don't re-pay for the same search. Downstream consumers (voc_miner,
brief_generator) can read the cached JSON.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from exa_py import Exa

CLIENTS_DIR = Path("clients")
DEFAULT_CONTENT_CHARS = 3000  # Per-page content budget
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


@dataclass
class ExaHit:
    url: str
    title: str
    published_date: str | None
    author: str | None
    score: float | None
    text: str
    domain: str


@dataclass
class ExaQueryResult:
    query: ExaQuery
    fetched_at: str
    results: list[ExaHit]

    def to_json(self) -> dict:
        return {
            "query": asdict(self.query),
            "fetched_at": self.fetched_at,
            "results": [asdict(r) for r in self.results],
        }


def _get_client() -> Exa:
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise EnvironmentError("EXA_API_KEY not set. See .env.example")
    return Exa(api_key=key)


def _slugify(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text[:60]


def _domain_of(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def run_query(
    query: ExaQuery,
    content_chars: int = DEFAULT_CONTENT_CHARS,
    livecrawl: str | None = None,
) -> ExaQueryResult:
    """Run one Exa search-and-contents query.

    livecrawl: 'always' forces a fresh fetch (helps with Reddit/aggressive
    bot-detection sites at a small extra cost). Default behavior is Exa's
    cached crawl.
    """
    exa = _get_client()
    kwargs: dict = {
        "num_results": query.num_results,
        "text": {"max_characters": content_chars},
    }
    if query.include_domains:
        kwargs["include_domains"] = query.include_domains
    if query.exclude_domains:
        kwargs["exclude_domains"] = query.exclude_domains
    # Use livecrawl for Reddit (cache often returns "blocked by network security")
    if livecrawl is None and "reddit.com" in (query.include_domains or []):
        livecrawl = "always"
    if livecrawl:
        kwargs["livecrawl"] = livecrawl

    response = exa.search_and_contents(query.query, **kwargs)

    hits: list[ExaHit] = []
    for r in response.results:
        hits.append(ExaHit(
            url=getattr(r, "url", ""),
            title=getattr(r, "title", "") or "",
            published_date=getattr(r, "published_date", None),
            author=getattr(r, "author", None),
            score=getattr(r, "score", None),
            text=getattr(r, "text", "") or "",
            domain=_domain_of(getattr(r, "url", "")),
        ))

    return ExaQueryResult(
        query=query,
        fetched_at=datetime.utcnow().isoformat() + "Z",
        results=hits,
    )


def cache_result(client_slug: str, result: ExaQueryResult) -> Path:
    """Persist a query result so we never re-pay for the same search."""
    out_dir = CLIENTS_DIR / client_slug / "research" / "exa" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_slugify(result.query.label)}.json"
    path.write_text(json.dumps(result.to_json(), indent=2), encoding="utf-8")
    return path


def load_cached(client_slug: str) -> list[ExaQueryResult]:
    """Reload all cached results for downstream consumers."""
    raw_dir = CLIENTS_DIR / client_slug / "research" / "exa" / "raw"
    if not raw_dir.exists():
        return []
    bundle: list[ExaQueryResult] = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        query = ExaQuery(**data["query"])
        results = [ExaHit(**r) for r in data["results"]]
        bundle.append(ExaQueryResult(
            query=query,
            fetched_at=data["fetched_at"],
            results=results,
        ))
    return bundle


# ─── Default query plans ─────────────────────────────────────────────────────


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
        ),
        ExaQuery(
            label=f"reddit-{brand_name}-worth-it",
            query=f"is {brand_name} worth it",
            include_domains=["reddit.com"],
            category="reddit",
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
            ))
            queries.append(ExaQuery(
                label=f"web-{comp}-honest",
                query=f"{comp} honest review",
                category="reviews",
            ))

    if category_terms:
        for term in category_terms:
            queries.append(ExaQuery(
                label=f"reddit-category-{_slugify(term)}",
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
      - 'trustpilot' query (when available, has explicit star ratings)
    """
    queries: list[ExaQuery] = []
    all_brands = [own_brand] + competitor_names

    for brand in all_brands:
        b_slug = _slugify(brand)
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
            ),
            ExaQuery(
                label=f"trustpilot-{b_slug}",
                query=f"{brand} reviews",
                include_domains=["trustpilot.com"],
                category="trustpilot",
            ),
        ])

    return queries


def run_research_bundle(
    client_slug: str,
    brand_name: str,
    competitors: list[str] | None = None,
    category_terms: list[str] | None = None,
    skip_cached: bool = True,
) -> list[ExaQueryResult]:
    """Run all default queries for a brand and cache each result.

    If skip_cached is True (default), queries whose cache file already exists
    are skipped — re-running is free until the cache is cleared.
    """
    queries = default_queries_for_brand(brand_name, competitors, category_terms)
    cache_dir = CLIENTS_DIR / client_slug / "research" / "exa" / "raw"

    all_results: list[ExaQueryResult] = []
    for q in queries:
        cache_path = cache_dir / f"{_slugify(q.label)}.json"
        if skip_cached and cache_path.exists():
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            query = ExaQuery(**data["query"])
            results = [ExaHit(**r) for r in data["results"]]
            all_results.append(ExaQueryResult(
                query=query,
                fetched_at=data["fetched_at"],
                results=results,
            ))
            continue
        result = run_query(q)
        cache_result(client_slug, result)
        all_results.append(result)

    return all_results
