"""Reddit VOC via Apify — bridge while official Reddit API access is pending.

Reddit gated new API apps behind its Responsible Builder review, so the
official-API path (strategy/reddit_research.py) is unusable until creds are
approved. This module is tier 2 of the reddit fallback chain in
exa_research.run_query:

    Exa (dead for reddit.com) -> official Reddit API -> THIS -> persisted error

Uses trudax/reddit-scraper-lite (pay-per-result, ~4M runs). The actor emits a
mixed stream of post and comment items; we fold each post's top comments into
one ExaHit so caches and downstream consumers (gap_analyzer, voc_miner) see
the exact same shape the official API path produces.

Observed item shapes (2026-07-05):
    post:    {dataType: "post", title, body, url, username, communityName,
              parsedCommunityName, createdAt, id, parsedId, ...}
    comment: {dataType: "comment", body, url (post permalink), username,
              postId, createdAt, ...}
No vote/score fields in the lite output — ExaHit.score stays None.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from apify_client import ApifyClient

from strategy.exa_queries import ExaQuery, reddit_search_terms
from strategy.exa_research import ExaHit, ExaQueryResult

ACTOR_ID = "trudax/reddit-scraper-lite"
DEFAULT_TIMEOUT_SECS = 600
MAX_ITEMS_PER_QUERY = 30      # total post+comment items the actor may charge for
COMMENTS_PER_POST = 6


class ApifyRedditError(RuntimeError):
    """Apify token missing or the actor run failed."""


def _get_client() -> ApifyClient:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise ApifyRedditError("APIFY_API_TOKEN not set. See .env.example")
    return ApifyClient(token)


def _post_base_url(url: str) -> str:
    """Normalize any post/comment URL to the post's canonical permalink."""
    m = re.match(r"(https://www\.reddit\.com/r/[^/]+/comments/[^/]+/)", url or "")
    return m.group(1) if m else (url or "")


def _hits_from_items(items: list[dict], content_chars: int) -> list[ExaHit]:
    """Group the actor's mixed post/comment stream into one ExaHit per post."""
    posts: dict[str, dict] = {}
    comments: dict[str, list[str]] = {}
    order: list[str] = []

    for item in items:
        base = _post_base_url(item.get("url", ""))
        if not base:
            continue
        if item.get("dataType") == "post":
            if base not in posts:
                posts[base] = item
                order.append(base)
        elif item.get("dataType") == "comment":
            body = (item.get("body") or "").strip()
            if body and body not in ("[deleted]", "[removed]"):
                comments.setdefault(base, []).append(body)
                if base not in posts and base not in order:
                    order.append(base)

    hits: list[ExaHit] = []
    for base in order:
        post = posts.get(base, {})
        parts = [(post.get("body") or "").strip()]
        post_comments = comments.get(base, [])[:COMMENTS_PER_POST]
        if post_comments:
            parts.append("TOP COMMENTS:\n" + "\n---\n".join(post_comments))
        text = "\n\n".join(p for p in parts if p).strip()[:content_chars]
        if not text and not post.get("title"):
            continue
        hits.append(ExaHit(
            url=base,
            title=str(post.get("title") or "")[:300],
            published_date=str(post.get("createdAt") or "") or None,
            author=str(post.get("username") or ""),
            score=None,
            text=text,
            domain="reddit.com",
        ))
    return hits


def run_reddit_query_via_apify(
    query: ExaQuery,
    content_chars: int = 3000,
) -> ExaQueryResult:
    """Run one reddit-scoped query plan through the Apify actor.

    Same ExaQueryResult shape as run_query / run_reddit_query. Zero matches
    is a valid outcome (niche brand) and returns an empty result, not an
    error; actor/auth failures raise ApifyRedditError. Hits that never
    mention the brand term are dropped — the actor scrapes rendered pages,
    and Reddit pads weak searches with trending junk.
    """
    search, must_contain = reddit_search_terms(query)
    client = _get_client()
    run_input = {
        "searches": [search],
        "searchPosts": True,
        "searchComments": False,
        "searchCommunities": False,
        "searchUsers": False,
        "sort": "relevance",
        "maxItems": MAX_ITEMS_PER_QUERY,
        "maxPostCount": query.num_results,
        "maxComments": COMMENTS_PER_POST,
        "proxy": {"useApifyProxy": True},
    }
    try:
        run = client.actor(ACTOR_ID).call(
            run_input=run_input, timeout_secs=DEFAULT_TIMEOUT_SECS,
        )
        dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
        items = (
            list(client.dataset(dataset_id).iterate_items()) if dataset_id else []
        )
    except Exception as e:
        raise ApifyRedditError(
            f"{ACTOR_ID} run failed: {type(e).__name__}: {str(e)[:200]}"
        ) from e

    hits = _hits_from_items(items, content_chars)
    if must_contain:
        needle = must_contain.lower()
        hits = [h for h in hits if needle in f"{h.title} {h.text}".lower()]

    return ExaQueryResult(
        query=query,
        fetched_at=datetime.utcnow().isoformat() + "Z",
        results=hits,
    )
