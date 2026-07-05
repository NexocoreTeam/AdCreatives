"""Exa-powered web research for unfiltered Voice of Customer.

On-site reviews are curated. This module reaches the messier truth:
- Reddit threads about the brand
- Comparison posts ("X vs Y")
- Third-party review aggregators (Trustpilot, SiteJabber)
- Discussion forums

Results are cached per-query under `clients/<slug>/research/exa/raw/` and
failures under `clients/<slug>/research/exa/errors/` so partial runs are
diagnosable and we don't re-pay for the same search. Downstream consumers
(voc_miner, brief_generator) can read the cached JSON.

Query PLANNING (which queries exist, labels, cache filenames) lives in
strategy/exa_queries.py — pure, no SDK import — so the status dashboard can
compare plan vs cache without touching this module.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from exa_py import Exa

from strategy.exa_queries import (
    DEFAULT_NUM_RESULTS,
    ExaQuery,
    cache_stem,
    competitive_queries_for_brand,
    default_queries_for_brand,
)

__all__ = [
    "DEFAULT_NUM_RESULTS",
    "ExaQuery",
    "ExaHit",
    "ExaQueryResult",
    "cache_error",
    "cache_result",
    "cache_stem",
    "competitive_queries_for_brand",
    "default_queries_for_brand",
    "load_cached",
    "run_query",
    "run_research_bundle",
]

CLIENTS_DIR = Path("clients")
DEFAULT_CONTENT_CHARS = 3000  # Per-page content budget


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
    reddit_scoped = "reddit.com" in (query.include_domains or [])
    if livecrawl is None and reddit_scoped:
        livecrawl = "always"
    if livecrawl:
        kwargs["livecrawl"] = livecrawl

    try:
        response = exa.search_and_contents(query.query, **kwargs)
    except Exception as e:
        message = str(e)
        if reddit_scoped and (
            "SOURCE_NOT_AVAILABLE" in message or "domains are not available" in message
        ):
            # Exa dropped reddit.com from its index (Reddit licensing lockdown).
            # Fall back to the official Reddit API — same result shape, same cache.
            from strategy.reddit_research import RedditAuthError, run_reddit_query

            try:
                return run_reddit_query(query, content_chars=content_chars)
            except RedditAuthError as reddit_err:
                raise RuntimeError(
                    "Exa no longer serves reddit.com and the Reddit API fallback "
                    f"is not usable: {reddit_err}"
                ) from e
        raise

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
    stem = cache_stem(result.query.label)
    path = out_dir / f"{stem}.json"
    path.write_text(json.dumps(result.to_json(), indent=2), encoding="utf-8")
    # A successful run supersedes any persisted failure for this query —
    # without this, status keeps reporting failed-query ghosts forever.
    error_path = CLIENTS_DIR / client_slug / "research" / "exa" / "errors" / f"{stem}.json"
    error_path.unlink(missing_ok=True)
    return path


def cache_error(client_slug: str, query: ExaQuery, error: Exception) -> Path:
    """Persist failed query metadata so partial Exa runs are diagnosable."""
    out_dir = CLIENTS_DIR / client_slug / "research" / "exa" / "errors"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{cache_stem(query.label)}.json"
    payload = {
        "query": asdict(query),
        "fetched_at": datetime.utcnow().isoformat() + "Z",
        "error_type": type(error).__name__,
        "error": str(error),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
        cache_path = cache_dir / f"{cache_stem(q.label)}.json"
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
