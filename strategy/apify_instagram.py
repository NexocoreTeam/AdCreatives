"""Instagram comments scraper via Apify.

Two-actor pipeline matching the TikTok module:
    1. apify/instagram-profile-scraper  — list recent posts from a profile
    2. apify/instagram-comment-scraper  — pull comments for those post URLs

If `instagram_post_urls` are pre-specified on the Competitor we skip step 1.

Cost (approximate, residential proxy tier):
    profile-scraper:  ~$2 per 1000 posts listed
    comment-scraper:  ~$0.30 per 1000 comments

Comment dataset shape from apify/instagram-comment-scraper (observed):
    {
      "id": "...",
      "text": "...",
      "ownerUsername": "...",
      "likesCount": int,
      "repliesCount": int,
      "timestamp": "...",
      "postUrl": "..."
    }
"""

from __future__ import annotations

import os
import re
from datetime import datetime

from apify_client import ApifyClient

from strategy.social_comments import SocialComment, SocialCommentBundle

PROFILE_ACTOR_ID = "apify/instagram-profile-scraper"
COMMENTS_ACTOR_ID = "apify/instagram-comment-scraper"
DEFAULT_POSTS_PER_PROFILE = 8
DEFAULT_COMMENTS_PER_POST = 100
DEFAULT_TIMEOUT_SECS = 600


def _get_client() -> ApifyClient:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise EnvironmentError("APIFY_API_TOKEN not set. See .env.example")
    return ApifyClient(token)


def _normalize_handle(handle: str) -> str:
    """'@brand' / 'brand' / 'https://instagram.com/brand' → 'brand'."""
    if not handle:
        return ""
    handle = handle.strip()
    m = re.search(r"instagram\.com/([\w.\-]+)", handle)
    if m:
        return m.group(1)
    return handle.lstrip("@").rstrip("/")


def _shortcode_from_url(url: str) -> str:
    """Pull the post shortcode from https://instagram.com/p/CXXX or /reel/CXXX."""
    m = re.search(r"/(?:p|reel|tv)/([\w-]+)", url or "")
    return m.group(1) if m else ""


def list_recent_posts_for_profile(
    handle: str,
    max_posts: int = DEFAULT_POSTS_PER_PROFILE,
) -> list[dict]:
    """Step 1: fetch recent post URLs + captions for an IG profile.

    Empty list when the profile has no public posts (or none returned by the
    actor for this run). Auth + actor exceptions propagate so the CLI can
    surface them in the results table instead of showing a false 'ok'.
    """
    client = _get_client()  # raises EnvironmentError if APIFY_API_TOKEN unset
    run_input = {
        "usernames": [_normalize_handle(handle)],
        "resultsLimit": max_posts,
        "addParentData": False,
    }
    # Let ApifyApiError propagate (auth, billing, missing actor access).
    run = client.actor(PROFILE_ACTOR_ID).call(
        run_input=run_input, timeout_secs=DEFAULT_TIMEOUT_SECS,
    )

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        return []

    items = list(client.dataset(dataset_id).iterate_items())

    posts: list[dict] = []
    for it in items:
        # Profile actor returns either a profile-level item with latestPosts, or
        # individual post items depending on actor version. Handle both shapes.
        latest = it.get("latestPosts") or []
        if isinstance(latest, list) and latest:
            sources = latest[:max_posts]
        else:
            sources = [it]
        for p in sources:
            url = p.get("url") or p.get("postUrl") or ""
            if not url:
                continue
            posts.append({
                "url": url,
                "post_id": p.get("shortCode") or _shortcode_from_url(url),
                "caption": str(p.get("caption") or "")[:500],
                "metrics": {
                    "likes": p.get("likesCount") or 0,
                    "comments": p.get("commentsCount") or 0,
                    "video_views": p.get("videoViewCount") or 0,
                },
            })
        if len(posts) >= max_posts:
            break
    return posts[:max_posts]


def scrape_comments_for_post(
    post_url: str,
    competitor_slug: str,
    competitor_name: str,
    *,
    caption: str = "",
    post_metrics: dict | None = None,
    max_comments: int = DEFAULT_COMMENTS_PER_POST,
) -> SocialCommentBundle:
    """Step 2: pull comments for one IG post URL."""
    client = _get_client()
    bundle = SocialCommentBundle(
        platform="instagram",
        competitor_slug=competitor_slug,
        competitor_name=competitor_name,
        post_id=_shortcode_from_url(post_url),
        post_url=post_url,
        post_caption=caption,
        post_metrics=post_metrics or {},
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )

    run_input = {
        "directUrls": [post_url],
        "resultsLimit": max_comments,
    }
    try:
        run = client.actor(COMMENTS_ACTOR_ID).call(
            run_input=run_input, timeout_secs=DEFAULT_TIMEOUT_SECS
        )
    except Exception as e:
        bundle.notes = f"Apify call failed: {type(e).__name__}: {e}"
        return bundle

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        bundle.notes = "Apify run completed but returned no datasetId"
        return bundle

    try:
        items = list(client.dataset(dataset_id).iterate_items())
    except Exception as e:
        bundle.notes = f"Failed to read Apify dataset: {type(e).__name__}: {e}"
        return bundle

    comments: list[SocialComment] = []
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        comments.append(SocialComment(
            platform="instagram",
            text=text[:2000],
            author=str(it.get("ownerUsername") or "")[:120],
            likes=int(it.get("likesCount") or 0),
            reply_count=int(it.get("repliesCount") or 0),
            posted_at=str(it.get("timestamp") or ""),
            comment_id=str(it.get("id") or ""),
            post_id=bundle.post_id,
            post_url=post_url,
            is_reply=bool(it.get("isReply") or False),
        ))
    bundle.comments = comments
    if not comments:
        bundle.notes = f"0 comments extracted from {len(items)} dataset items"
    return bundle


def scrape_instagram_for_competitor(
    competitor,
    *,
    max_posts_per_profile: int = DEFAULT_POSTS_PER_PROFILE,
    max_comments_per_post: int = DEFAULT_COMMENTS_PER_POST,
) -> list[SocialCommentBundle]:
    """Pull IG comments for one competitor.

    Priority: explicit instagram_post_urls > instagram_handle. Returns [] if
    neither is configured.
    """
    if competitor.instagram_post_urls:
        posts_meta = [
            {
                "url": u,
                "post_id": _shortcode_from_url(u),
                "caption": "",
                "metrics": {},
            }
            for u in competitor.instagram_post_urls
        ]
    elif competitor.instagram_handle:
        posts_meta = list_recent_posts_for_profile(
            competitor.instagram_handle, max_posts=max_posts_per_profile,
        )
    else:
        return []

    bundles: list[SocialCommentBundle] = []
    for p in posts_meta:
        bundle = scrape_comments_for_post(
            p["url"],
            competitor_slug=competitor.slug,
            competitor_name=competitor.name,
            caption=p.get("caption", ""),
            post_metrics=p.get("metrics", {}),
            max_comments=max_comments_per_post,
        )
        bundles.append(bundle)
    return bundles
