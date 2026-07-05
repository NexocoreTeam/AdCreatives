"""Reddit VOC via the official Reddit API.

Exa can no longer serve reddit.com (403 SOURCE_NOT_AVAILABLE on
include_domains) — Reddit locked its content behind licensing, and the
anonymous .json endpoints are blocked too. This module is the replacement
path: OAuth client-credentials + /search + top comments per thread.

Setup (one-time):
    1. https://www.reddit.com/prefs/apps → create app → type "script"
    2. .env: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET,
       REDDIT_USER_AGENT (e.g. "adcreatives-research/0.1 by u/<you>")

Results are shaped as ExaHit/ExaQueryResult so the exa cache layer and
every downstream consumer (gap_analyzer, voc_miner) work unchanged.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone

import httpx

from strategy.exa_research import ExaHit, ExaQueryResult
from strategy.exa_queries import ExaQuery, reddit_search_terms

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
API_BASE = "https://oauth.reddit.com"
DEFAULT_TIMEOUT = 20.0
COMMENTS_PER_POST = 8
POSTS_WITH_COMMENTS = 5      # fetch comment threads for the top N posts only
REQUEST_GAP_SECONDS = 0.6    # stay well under the 60 req/min OAuth budget

_token_cache: dict = {"token": "", "expires_at": 0.0}


class RedditAuthError(RuntimeError):
    """Reddit API credentials missing or rejected."""


def _user_agent() -> str:
    return os.environ.get(
        "REDDIT_USER_AGENT", "adcreatives-research/0.1 (competitive VOC research)"
    )


def _get_token() -> str:
    if _token_cache["token"] and time.time() < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise RedditAuthError(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set. Create a 'script' "
            "app at https://www.reddit.com/prefs/apps and add them to .env."
        )
    try:
        resp = httpx.post(
            TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            headers={"User-Agent": _user_agent()},
            timeout=DEFAULT_TIMEOUT,
        )
    except httpx.HTTPError as e:
        raise RedditAuthError(f"Reddit token request failed: {e}") from e
    if resp.status_code != 200 or not resp.json().get("access_token"):
        raise RedditAuthError(
            f"Reddit rejected the credentials (HTTP {resp.status_code}). "
            "Rotate REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env."
        )
    payload = resp.json()
    _token_cache["token"] = payload["access_token"]
    _token_cache["expires_at"] = time.time() + float(payload.get("expires_in", 3600))
    return _token_cache["token"]


def _api_get(path: str, params: dict) -> dict:
    resp = httpx.get(
        f"{API_BASE}{path}",
        params=params,
        headers={"Authorization": f"bearer {_get_token()}", "User-Agent": _user_agent()},
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def search_posts(query: str, limit: int = 10) -> list[dict]:
    """Search Reddit posts. Returns the raw post-data dicts."""
    data = _api_get(
        "/search",
        {"q": query, "limit": limit, "sort": "relevance", "t": "all", "type": "link"},
    )
    return [c["data"] for c in data.get("data", {}).get("children", []) if c.get("data")]


def _top_comments(permalink: str, limit: int = COMMENTS_PER_POST) -> list[str]:
    try:
        data = _api_get(f"{permalink.rstrip('/')}.json", {"limit": limit, "sort": "top"})
    except httpx.HTTPError:
        return []
    if not isinstance(data, list) or len(data) < 2:
        return []
    comments: list[str] = []
    for child in data[1].get("data", {}).get("children", []):
        if child.get("kind") != "t1":
            continue
        body = (child.get("data", {}).get("body") or "").strip()
        if body and body not in ("[deleted]", "[removed]"):
            comments.append(body)
        if len(comments) >= limit:
            break
    return comments


def _hit_from_post(post: dict, comments: list[str], content_chars: int) -> ExaHit:
    """Shape one Reddit post + its top comments as an ExaHit."""
    created = post.get("created_utc")
    published = (
        datetime.fromtimestamp(created, tz=timezone.utc).isoformat()
        if isinstance(created, (int, float))
        else None
    )
    parts = [post.get("selftext") or ""]
    if comments:
        parts.append("TOP COMMENTS:\n" + "\n---\n".join(comments))
    text = "\n\n".join(p for p in parts if p).strip()[:content_chars]
    return ExaHit(
        url=f"https://www.reddit.com{post.get('permalink', '')}",
        title=str(post.get("title") or "")[:300],
        published_date=published,
        author=str(post.get("author") or ""),
        score=float(post.get("score") or 0),
        text=text,
        domain="reddit.com",
    )


def run_reddit_query(query: ExaQuery, content_chars: int = 3000) -> ExaQueryResult:
    """Run one reddit-scoped query plan against the Reddit API.

    Drop-in replacement for exa_research.run_query when Exa refuses
    reddit.com — same ExaQueryResult shape, same cache compatibility.
    Searches with the keyword form of the query and drops posts that never
    mention the brand term (Reddit search pads weak matches with junk).
    """
    search, must_contain = reddit_search_terms(query)
    posts = search_posts(search, limit=query.num_results)
    if must_contain:
        needle = must_contain.lower()
        posts = [
            p for p in posts
            if needle in f"{p.get('title', '')} {p.get('selftext', '')}".lower()
        ]

    hits: list[ExaHit] = []
    for i, post in enumerate(posts):
        comments: list[str] = []
        if i < POSTS_WITH_COMMENTS and post.get("permalink"):
            time.sleep(REQUEST_GAP_SECONDS)
            comments = _top_comments(post["permalink"])
        hits.append(_hit_from_post(post, comments, content_chars))

    return ExaQueryResult(
        query=query,
        fetched_at=datetime.utcnow().isoformat() + "Z",
        results=hits,
    )
