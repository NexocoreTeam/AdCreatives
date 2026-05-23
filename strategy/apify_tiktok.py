"""TikTok comments scraper via Apify.

Two-actor pipeline:
    1. clockworks/free-tiktok-scraper          — list recent videos from a profile
    2. clockworks/tiktok-comments-scraper      — pull comments for those video URLs

If `tiktok_post_urls` are pre-specified on the Competitor we skip step 1
entirely. Profile-based scraping costs ~$1/1000 results on the videos pull
plus ~$0.30/1000 on the comments pull.

Why two actors instead of one: the all-in-one paid actors are unreliable and
charge per result. The two-step pattern lets us cap each stage independently
and is what every production scraping setup ends up doing anyway.

Comment dataset shape from clockworks/tiktok-comments-scraper (observed):
    {
      "cid": "...",            // comment id
      "text": "...",
      "diggCount": int,        // likes
      "replyCommentTotal": int,
      "uniqueId": "...",       // author handle
      "createTimeISO": "...",
      "videoWebUrl": "...",
      "videoId": "..."
    }
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from apify_client import ApifyClient

from strategy.social_comments import SocialComment, SocialCommentBundle

CLIENTS_DIR = Path("clients")

VIDEO_ACTOR_ID = "clockworks/free-tiktok-scraper"
COMMENTS_ACTOR_ID = "clockworks/tiktok-comments-scraper"
# Search actor — `clockworks/tiktok-scraper` (paid) accepts `searchQueries`
# input mode and returns videos matching those queries. Used for UGC-review
# discovery (e.g. "arrae review", "tried arrae for 30 days"). Costs ~$2 per
# 1000 results — small marginal cost per competitor for 5-8 review URLs.
SEARCH_ACTOR_ID = "clockworks/tiktok-scraper"
DEFAULT_VIDEOS_PER_PROFILE = 8
DEFAULT_VIDEOS_PER_SEARCH_QUERY = 5
DEFAULT_COMMENTS_PER_VIDEO = 100
DEFAULT_TIMEOUT_SECS = 600


def _get_client() -> ApifyClient:
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise EnvironmentError("APIFY_API_TOKEN not set. See .env.example")
    return ApifyClient(token)


def _normalize_handle(handle: str) -> str:
    """'@brand' / 'brand' / 'https://tiktok.com/@brand' → 'brand'."""
    if not handle:
        return ""
    handle = handle.strip()
    m = re.search(r"@([\w.\-]+)", handle)
    if m:
        return m.group(1)
    return handle.lstrip("@")


def _profile_url(handle: str) -> str:
    return f"https://www.tiktok.com/@{_normalize_handle(handle)}"


def _video_id_from_url(url: str) -> str:
    m = re.search(r"/video/(\d+)", url or "")
    return m.group(1) if m else ""


def list_recent_videos_for_profile(
    handle: str,
    max_videos: int = DEFAULT_VIDEOS_PER_PROFILE,
) -> list[dict]:
    """Step 1: fetch recent video URLs + metadata for a TikTok profile.

    Returns a list of {url, video_id, caption, metrics} dicts. Empty list when
    the profile genuinely has no public videos (TikTok login wall, private
    account, brand-new account). Auth failures and other Apify exceptions
    propagate so the CLI's per-row exception handler can surface them in the
    results table instead of misleadingly showing 'ok / 0 results'.
    """
    client = _get_client()  # raises EnvironmentError if APIFY_API_TOKEN unset
    run_input = {
        "profiles": [_normalize_handle(handle)],
        "resultsPerPage": max_videos,
        "shouldDownloadCovers": False,
        "shouldDownloadVideos": False,
        "shouldDownloadSubtitles": False,
    }
    # Don't swallow ApifyApiError — auth issues, billing issues, missing
    # actor permissions should bubble up so the operator sees them.
    run = client.actor(VIDEO_ACTOR_ID).call(
        run_input=run_input, timeout_secs=DEFAULT_TIMEOUT_SECS,
    )

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        return []

    try:
        items = list(client.dataset(dataset_id).iterate_items())
    except Exception:
        return []

    videos: list[dict] = []
    for it in items[:max_videos]:
        url = it.get("webVideoUrl") or it.get("videoUrl") or ""
        if not url:
            continue
        videos.append({
            "url": url,
            "video_id": str(it.get("id") or _video_id_from_url(url)),
            "caption": str(it.get("text") or it.get("desc") or "")[:500],
            "metrics": {
                "plays": it.get("playCount") or 0,
                "diggs": it.get("diggCount") or 0,
                "comments": it.get("commentCount") or 0,
                "shares": it.get("shareCount") or 0,
            },
        })
    return videos


def search_tiktok_videos(
    query: str,
    max_videos: int = DEFAULT_VIDEOS_PER_SEARCH_QUERY,
) -> list[dict]:
    """Search-mode discovery: find UGC review videos matching a query.

    Uses the paid `clockworks/tiktok-scraper` actor's `searchQueries` mode.
    Typical queries for competitive research:
      "arrae review", "tried arrae for 30 days", "arrae honest review",
      "arrae before and after"

    Returns the same {url, video_id, caption, metrics} dict shape as
    list_recent_videos_for_profile so the downstream comment scraper is
    agnostic to discovery mode.
    """
    client = _get_client()
    run_input = {
        "searchQueries": [query],
        "resultsPerPage": max_videos,
        "shouldDownloadCovers": False,
        "shouldDownloadVideos": False,
        "shouldDownloadSubtitles": False,
    }
    run = client.actor(SEARCH_ACTOR_ID).call(
        run_input=run_input, timeout_secs=DEFAULT_TIMEOUT_SECS,
    )

    dataset_id = run.get("defaultDatasetId") if isinstance(run, dict) else None
    if not dataset_id:
        return []

    items = list(client.dataset(dataset_id).iterate_items())
    videos: list[dict] = []
    for it in items[:max_videos]:
        url = it.get("webVideoUrl") or it.get("videoUrl") or ""
        if not url:
            continue
        videos.append({
            "url": url,
            "video_id": str(it.get("id") or _video_id_from_url(url)),
            "caption": str(it.get("text") or it.get("desc") or "")[:500],
            "metrics": {
                "plays": it.get("playCount") or 0,
                "diggs": it.get("diggCount") or 0,
                "comments": it.get("commentCount") or 0,
                "shares": it.get("shareCount") or 0,
            },
            "discovered_via": f"search:{query}",
        })
    return videos


def scrape_comments_for_video(
    video_url: str,
    competitor_slug: str,
    competitor_name: str,
    *,
    caption: str = "",
    post_metrics: dict | None = None,
    max_comments: int = DEFAULT_COMMENTS_PER_VIDEO,
) -> SocialCommentBundle:
    """Step 2: pull comments for one TikTok video URL."""
    client = _get_client()
    bundle = SocialCommentBundle(
        platform="tiktok",
        competitor_slug=competitor_slug,
        competitor_name=competitor_name,
        post_id=_video_id_from_url(video_url),
        post_url=video_url,
        post_caption=caption,
        post_metrics=post_metrics or {},
        fetched_at=datetime.utcnow().isoformat() + "Z",
    )

    run_input = {
        "postURLs": [video_url],
        "commentsPerPost": max_comments,
        "maxRepliesPerComment": 0,  # top-level only; replies rarely add new pain signal
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
            platform="tiktok",
            text=text[:2000],
            author=str(it.get("uniqueId") or it.get("nickName") or "")[:120],
            likes=int(it.get("diggCount") or 0),
            reply_count=int(it.get("replyCommentTotal") or 0),
            posted_at=str(it.get("createTimeISO") or ""),
            comment_id=str(it.get("cid") or ""),
            post_id=bundle.post_id,
            post_url=video_url,
            is_reply=False,
        ))
    bundle.comments = comments
    if not comments:
        bundle.notes = f"0 comments extracted from {len(items)} dataset items"
    return bundle


def scrape_tiktok_for_competitor(
    competitor,
    *,
    max_videos_per_profile: int = DEFAULT_VIDEOS_PER_PROFILE,
    max_comments_per_video: int = DEFAULT_COMMENTS_PER_VIDEO,
    max_videos_per_search_query: int = DEFAULT_VIDEOS_PER_SEARCH_QUERY,
) -> list[SocialCommentBundle]:
    """Pull TikTok comments for one competitor.

    Priority order (first non-empty wins):
      1. tiktok_post_urls           — manual URL list, $0 discovery cost
      2. tiktok_handle              — brand-owned posts via free actor
      3. tiktok_search_queries      — UGC review videos via paid search actor;
                                      higher signal-per-dollar for most categories
      4. None of the above          — return [], skip silently
    """
    if competitor.tiktok_post_urls:
        videos_meta = [
            {
                "url": u,
                "video_id": _video_id_from_url(u),
                "caption": "",
                "metrics": {},
                "discovered_via": "manual",
            }
            for u in competitor.tiktok_post_urls
        ]
    elif competitor.tiktok_search_queries:
        # Run each search query, then dedupe by video_id so two queries that
        # surface the same review video don't get scraped twice. Preserve
        # discovery order (first query first).
        seen_video_ids: set[str] = set()
        videos_meta = []
        for query in competitor.tiktok_search_queries:
            for v in search_tiktok_videos(query, max_videos=max_videos_per_search_query):
                vid = v.get("video_id") or ""
                if vid and vid in seen_video_ids:
                    continue
                if vid:
                    seen_video_ids.add(vid)
                videos_meta.append(v)
    elif competitor.tiktok_handle:
        videos_meta = list_recent_videos_for_profile(
            competitor.tiktok_handle, max_videos=max_videos_per_profile,
        )
    else:
        return []

    bundles: list[SocialCommentBundle] = []
    for v in videos_meta:
        bundle = scrape_comments_for_video(
            v["url"],
            competitor_slug=competitor.slug,
            competitor_name=competitor.name,
            caption=v.get("caption", ""),
            post_metrics=v.get("metrics", {}),
            max_comments=max_comments_per_video,
        )
        bundles.append(bundle)
    return bundles
