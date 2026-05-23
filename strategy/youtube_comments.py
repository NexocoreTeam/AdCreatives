"""YouTube comments via the official YouTube Data API v3.

No third-party vendor — just a Google API key. Free quota is 10,000 units/day,
and each commentThreads.list call costs 1 unit (returns up to 100 comments).
That's enough quota to pull ~1M comments/day on the free tier.

Setup:
    1. Create a project at https://console.cloud.google.com
    2. Enable "YouTube Data API v3"
    3. Create an API key (no OAuth needed for public read)
    4. Add YOUTUBE_API_KEY=... to .env

Three endpoints used:
    channels.list?forHandle=@brand    cost: 1 unit, resolves handle → channel ID
    search.list?channelId=X           cost: 100 units (only used when video IDs
                                      not specified — list_recent_videos)
    commentThreads.list?videoId=X     cost: 1 unit per page (100 comments/page)

We default to caller-provided video IDs when possible to avoid the 100-unit
search hit. If only a handle is provided, we resolve channel → search → comments.
"""

from __future__ import annotations

import os
import re
from datetime import datetime

import httpx

from strategy.social_comments import SocialComment, SocialCommentBundle

API_BASE = "https://www.googleapis.com/youtube/v3"
DEFAULT_TIMEOUT = 30.0
DEFAULT_COMMENTS_PER_VIDEO = 100
DEFAULT_VIDEOS_PER_CHANNEL = 8
MAX_RESULTS_PER_PAGE = 100  # API hard cap for commentThreads


class YouTubeAuthError(RuntimeError):
    pass


def _api_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        raise YouTubeAuthError(
            "YOUTUBE_API_KEY not set. Create a key at "
            "https://console.cloud.google.com (enable YouTube Data API v3) and add it to .env."
        )
    return key


def _normalize_handle(handle: str) -> str:
    """'@brand' / 'brand' / 'youtube.com/@brand' → '@brand'."""
    if not handle:
        return ""
    h = handle.strip()
    m = re.search(r"@([\w.\-]+)", h)
    if m:
        return f"@{m.group(1)}"
    return f"@{h.lstrip('@').rstrip('/')}"


def resolve_handle_to_channel_id(handle: str) -> str:
    """Resolve a @handle to a UCxxxx channel ID. Empty string on failure."""
    if not handle:
        return ""
    params = {
        "part": "id",
        "forHandle": _normalize_handle(handle),
        "key": _api_key(),
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            r = client.get(f"{API_BASE}/channels", params=params)
        r.raise_for_status()
    except httpx.HTTPError:
        return ""
    items = r.json().get("items") or []
    return items[0]["id"] if items and "id" in items[0] else ""


def list_recent_videos(
    channel_id: str,
    max_videos: int = DEFAULT_VIDEOS_PER_CHANNEL,
) -> list[dict]:
    """List recent video IDs + titles for a channel via search.list.

    Costs 100 quota units per call. Returns up to `max_videos` items.
    """
    if not channel_id:
        return []
    params = {
        "part": "snippet",
        "channelId": channel_id,
        "order": "date",
        "type": "video",
        "maxResults": min(max_videos, 50),
        "key": _api_key(),
    }
    try:
        with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
            r = client.get(f"{API_BASE}/search", params=params)
        r.raise_for_status()
    except httpx.HTTPError:
        return []

    items = r.json().get("items") or []
    videos: list[dict] = []
    for it in items[:max_videos]:
        video_id = (it.get("id") or {}).get("videoId")
        snippet = it.get("snippet") or {}
        if not video_id:
            continue
        videos.append({
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": str(snippet.get("title") or "")[:300],
            "published_at": str(snippet.get("publishedAt") or ""),
        })
    return videos


def fetch_comments_for_video(
    video_id: str,
    competitor_slug: str,
    competitor_name: str,
    *,
    video_title: str = "",
    max_comments: int = DEFAULT_COMMENTS_PER_VIDEO,
) -> SocialCommentBundle:
    """Pull top-level comments for one video via commentThreads.list.

    Sorted by `relevance` (YouTube's relevance score, not chronological) so
    the highest-engagement comments lead. Paginates until max_comments or the
    video runs out.
    """
    bundle = SocialCommentBundle(
        platform="youtube",
        competitor_slug=competitor_slug,
        competitor_name=competitor_name,
        post_id=video_id,
        post_url=f"https://www.youtube.com/watch?v={video_id}",
        post_caption=video_title,
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )

    comments: list[SocialComment] = []
    page_token: str | None = None
    remaining = max_comments

    while remaining > 0:
        params = {
            "part": "snippet",
            "videoId": video_id,
            "order": "relevance",
            "textFormat": "plainText",
            "maxResults": min(remaining, MAX_RESULTS_PER_PAGE),
            "key": _api_key(),
        }
        if page_token:
            params["pageToken"] = page_token
        try:
            with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
                r = client.get(f"{API_BASE}/commentThreads", params=params)
        except httpx.HTTPError as e:
            bundle.notes = f"HTTP error: {type(e).__name__}: {e}"
            break

        if r.status_code == 403:
            # Comments disabled on the video (or quota exhausted) — note and stop.
            bundle.notes = f"403 from YouTube API (comments disabled or quota): {r.text[:200]}"
            break
        if r.status_code != 200:
            bundle.notes = f"YouTube API {r.status_code}: {r.text[:200]}"
            break

        payload = r.json()
        items = payload.get("items") or []
        if not items:
            break

        for it in items:
            snippet = ((it.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
            text = (snippet.get("textDisplay") or "").strip()
            if not text:
                continue
            comments.append(SocialComment(
                platform="youtube",
                text=text[:2000],
                author=str(snippet.get("authorDisplayName") or "")[:120],
                likes=int(snippet.get("likeCount") or 0),
                reply_count=int((it.get("snippet") or {}).get("totalReplyCount") or 0),
                posted_at=str(snippet.get("publishedAt") or ""),
                comment_id=str(it.get("id") or ""),
                post_id=video_id,
                post_url=bundle.post_url,
                is_reply=False,
            ))
            if len(comments) >= max_comments:
                break

        remaining = max_comments - len(comments)
        page_token = payload.get("nextPageToken")
        if not page_token:
            break

    bundle.comments = comments
    if not comments and not bundle.notes:
        bundle.notes = "0 comments extracted (video may have comments disabled)"
    return bundle


def fetch_youtube_for_competitor(
    competitor,
    *,
    max_videos_per_channel: int = DEFAULT_VIDEOS_PER_CHANNEL,
    max_comments_per_video: int = DEFAULT_COMMENTS_PER_VIDEO,
) -> list[SocialCommentBundle]:
    """Pull YouTube comments for one competitor.

    Priority order:
      1. Specific `youtube_video_ids` → comment-only fetch, cheapest path.
      2. `youtube_channel_id` → list recent videos + comments.
      3. `youtube_handle` → resolve → channel_id → list videos + comments.
    """
    video_metas: list[dict] = []

    if competitor.youtube_video_ids:
        video_metas = [
            {"video_id": vid, "title": "", "url": f"https://www.youtube.com/watch?v={vid}"}
            for vid in competitor.youtube_video_ids
        ]
    else:
        channel_id = competitor.youtube_channel_id
        if not channel_id and competitor.youtube_handle:
            channel_id = resolve_handle_to_channel_id(competitor.youtube_handle)
        if not channel_id:
            return []
        video_metas = list_recent_videos(channel_id, max_videos=max_videos_per_channel)

    bundles: list[SocialCommentBundle] = []
    for v in video_metas:
        bundle = fetch_comments_for_video(
            v["video_id"],
            competitor_slug=competitor.slug,
            competitor_name=competitor.name,
            video_title=v.get("title", ""),
            max_comments=max_comments_per_video,
        )
        bundles.append(bundle)
    return bundles
