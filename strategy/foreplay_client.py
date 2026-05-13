"""Foreplay ad library client.

Wraps Foreplay's APIs (public + internal) to fetch ads from boards and
the discovery database. The public API key (FOREPLAY_API_KEY) works against
both hosts:

  - api.foreplay.co             (internal endpoints — what the app uses)
  - public.api.foreplay.co      (documented public endpoints)

Internal endpoint `/ads/expert/<user_id>?orBoardId[]=<board_id>` is the
one that returns ads from public 'Discovery Expert' boards — required for
syncing curated swipe files like Sarah Levinger's psychology library. The
documented public `/api/board/ads` endpoint only returns ads from boards
in YOUR own account.

Generate an API key at https://app.foreplay.co/api-overview.
Pricing: 1 credit per ad. 10K free credits/month on base plans.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import httpx


PUBLIC_API = "https://public.api.foreplay.co"
INTERNAL_API = "https://api.foreplay.co"
USER_AGENT = "AdCreatives-Foreplay/0.1 (+https://github.com/NexocoreTeam/AdCreatives)"
DEFAULT_TIMEOUT = 30.0
DEFAULT_DOWNLOAD_TIMEOUT = 60.0


class ForeplayAuthError(RuntimeError):
    pass


def _load_dotenv_lazy() -> None:
    """Populate os.environ from .env in CWD if keys are missing. No-op if .env absent."""
    env_path = Path(".env")
    if not env_path.exists():
        return
    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def _api_key() -> str:
    key = os.environ.get("FOREPLAY_API_KEY")
    if not key:
        _load_dotenv_lazy()
        key = os.environ.get("FOREPLAY_API_KEY")
    if not key:
        raise ForeplayAuthError(
            "FOREPLAY_API_KEY not set. Add it to your .env file. "
            "Generate one at https://app.foreplay.co/api-overview"
        )
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "User-Agent": USER_AGENT,
    }


@dataclass
class ForeplayAd:
    """Typed view of a Foreplay ad record."""

    ad_id: str = ""              # numeric (facebook) ad id, as string
    foreplay_id: str = ""        # Foreplay's internal doc id (top-level 'id')
    name: str = ""               # brand display name
    brand_id: str = ""
    headline: str = ""
    description: str = ""
    cta_title: str = ""
    cta_type: str = ""
    display_format: str = ""     # 'image' | 'video' | 'carousel' | ...
    type: str = ""               # similar to display_format
    live: bool = False
    started_running: int = 0     # unix ms
    publisher_platform: list[str] = field(default_factory=list)
    niches: list[str] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    market_target: str = ""
    product_category: str = ""
    creative_targeting: str = ""
    link_url: str = ""
    persona: dict = field(default_factory=dict)
    emotional_drivers: dict = field(default_factory=dict)   # {emotion: 1-9}
    content_filter: dict = field(default_factory=dict)      # {ad_type: probability}
    keywords: list[str] = field(default_factory=list)
    ai_keywords: list[str] = field(default_factory=list)
    video_duration: str = ""
    transcription: list[dict] = field(default_factory=list)
    image_url: str = ""          # primary asset for image ads
    video_url: str = ""          # primary asset for video ads
    thumbnail_url: str = ""      # always present for video ads
    cards: list[dict] = field(default_factory=list)        # carousel slides
    mobile_screenshot: str = ""  # full carousel rendered (fallback)
    desktop_screenshot: str = ""
    board_ids: list[str] = field(default_factory=list)
    expert_user_id: str = ""     # 'created_by' for expert ads

    @classmethod
    def from_api(cls, raw: dict) -> "ForeplayAd":
        return cls(
            ad_id=str(raw.get("ad_id") or ""),
            foreplay_id=raw.get("id") or "",
            name=raw.get("name") or "",
            brand_id=raw.get("brandId") or raw.get("brand_id") or "",
            headline=raw.get("headline") or "",
            description=raw.get("description") or "",
            cta_title=raw.get("cta_title") or "",
            cta_type=raw.get("cta_type") or "",
            display_format=raw.get("display_format") or "",
            type=raw.get("type") or "",
            live=bool(raw.get("live")),
            started_running=int(raw.get("startedRunning") or raw.get("started_running") or 0),
            publisher_platform=raw.get("publisher_platform") or [],
            niches=raw.get("niches") or [],
            languages=raw.get("languages") or [],
            market_target=raw.get("marketTarget") or raw.get("market_target") or "",
            product_category=raw.get("productCategory") or "",
            creative_targeting=raw.get("creativeTargeting") or "",
            link_url=raw.get("link_url") or "",
            persona=raw.get("persona") or {},
            emotional_drivers=raw.get("emotionalDrivers") or {},
            content_filter=raw.get("contentFilter") or {},
            keywords=raw.get("keywords") or [],
            ai_keywords=raw.get("aiKeywords") or [],
            video_duration=str(raw.get("video_duration") or ""),
            transcription=raw.get("timestampedTranscription") or [],
            image_url=raw.get("image") or raw.get("backupUrl") or "",
            video_url=raw.get("video") or raw.get("backupVideoUrl") or "",
            thumbnail_url=raw.get("thumbnail") or "",
            cards=raw.get("cards") or [],
            mobile_screenshot=raw.get("mobileScreenshot") or "",
            desktop_screenshot=raw.get("desktopScreenshot") or "",
            board_ids=raw.get("board_ids") or [],
            expert_user_id=raw.get("created_by") or "",
        )

    @property
    def is_video(self) -> bool:
        return self.display_format == "video" or self.type == "video"

    @property
    def is_carousel(self) -> bool:
        return self.display_format == "carousel" or self.type == "carousel"

    @property
    def card_image_urls(self) -> list[str]:
        """All slide image URLs for a carousel ad (empty for non-carousels)."""
        return [c.get("image") for c in self.cards if isinstance(c, dict) and c.get("image")]

    @property
    def primary_image_url(self) -> str:
        """Best single image URL for this ad.

        Priority:
          videos    → thumbnail → image → mobileScreenshot
          carousels → first card image → mobileScreenshot → thumbnail
          images    → image → thumbnail → mobileScreenshot
        """
        if self.is_video:
            return self.thumbnail_url or self.image_url or self.mobile_screenshot
        if self.is_carousel:
            cards = self.card_image_urls
            if cards:
                return cards[0]
            return self.mobile_screenshot or self.thumbnail_url or self.image_url
        return self.image_url or self.thumbnail_url or self.mobile_screenshot


def fetch_expert_board(
    expert_user_id: str,
    board_id: str,
    cursor: str | None = None,
) -> tuple[list[ForeplayAd], str | None]:
    """Fetch one page of ads from a public 'Discovery Expert' board.

    Returns: (ads, next_cursor). next_cursor is None when exhausted.
    """
    url = f"{INTERNAL_API}/ads/expert/{expert_user_id}"
    params: list[tuple[str, str]] = [
        ("sort", "desc"),
        ("orBoardId[]", board_id),
    ]
    if cursor:
        params.append(("next", cursor))

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.get(url, headers=_headers(), params=params)

    if r.status_code in (401, 403):
        raise ForeplayAuthError(
            f"Auth failed ({r.status_code}). Check FOREPLAY_API_KEY validity. "
            f"Body: {r.text[:200]}"
        )
    r.raise_for_status()

    data = r.json()
    results = data.get("results") or []
    ads = [ForeplayAd.from_api(raw) for raw in results]
    # Defense-in-depth: only keep ads that actually list the requested board.
    ads = [a for a in ads if board_id in a.board_ids]

    next_raw = data.get("nextPage")
    if isinstance(next_raw, list) and next_raw:
        next_cursor: str | None = str(next_raw[0])
    elif isinstance(next_raw, str) and next_raw:
        next_cursor = next_raw
    else:
        next_cursor = None
    return ads, next_cursor


def iter_expert_board(
    expert_user_id: str,
    board_id: str,
    max_ads: int = 50,
) -> Iterator[ForeplayAd]:
    """Paginate ads from an expert board, stopping at max_ads."""
    cursor: str | None = None
    yielded = 0
    while yielded < max_ads:
        batch, cursor = fetch_expert_board(expert_user_id, board_id, cursor=cursor)
        if not batch:
            return
        for ad in batch:
            if yielded >= max_ads:
                return
            yield ad
            yielded += 1
        if not cursor:
            return


def fetch_discovery_ads(
    *,
    niches: list[str] | None = None,
    display_format: list[str] | None = None,
    publisher_platform: list[str] | None = None,
    market_target: str | None = None,
    live: bool | None = None,
    order: str = "longest_running",
    running_duration_min_days: int | None = None,
    running_duration_max_days: int | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[ForeplayAd], str | None]:
    """Search the full 100M-ad discovery database.

    Each returned ad costs 1 credit. Most filters accept multiple values
    (passed as repeated query params). Returns (ads, next_cursor).
    """
    url = f"{PUBLIC_API}/api/discovery/ads"
    params: list[tuple[str, str]] = [("order", order), ("limit", str(limit))]

    for n in niches or []:
        params.append(("niches", n))
    for fmt in display_format or []:
        params.append(("display_format", fmt))
    for p in publisher_platform or []:
        params.append(("publisher_platform", p))
    if market_target:
        params.append(("market_target", market_target))
    if live is not None:
        params.append(("live", "true" if live else "false"))
    if running_duration_min_days is not None:
        params.append(("running_duration_min_days", str(running_duration_min_days)))
    if running_duration_max_days is not None:
        params.append(("running_duration_max_days", str(running_duration_max_days)))
    if cursor:
        params.append(("cursor", cursor))

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.get(url, headers=_headers(), params=params)

    if r.status_code in (401, 403):
        raise ForeplayAuthError(
            f"Auth failed ({r.status_code}). Body: {r.text[:200]}"
        )
    r.raise_for_status()
    payload = r.json()

    # Public API uses snake_case-ish keys (content_filter) and lowercases enums;
    # internal API uses camelCase (contentFilter). Normalize.
    raw_ads = payload.get("data") or []
    ads: list[ForeplayAd] = []
    for raw in raw_ads:
        # Snake-case → camelCase aliases for fields our from_api expects.
        if "content_filter" in raw and "contentFilter" not in raw:
            raw["contentFilter"] = raw["content_filter"]
        if "emotional_drivers" in raw and "emotionalDrivers" not in raw:
            raw["emotionalDrivers"] = raw["emotional_drivers"]
        if "ai_keywords" in raw and "aiKeywords" not in raw:
            raw["aiKeywords"] = raw["ai_keywords"]
        if "started_running" in raw and "startedRunning" not in raw:
            raw["startedRunning"] = raw["started_running"]
        # display_format from discovery comes uppercase ("IMAGE") — lowercase it
        if isinstance(raw.get("display_format"), str):
            raw["display_format"] = raw["display_format"].lower()
        if isinstance(raw.get("type"), str):
            raw["type"] = raw["type"].lower()
        ads.append(ForeplayAd.from_api(raw))

    meta = payload.get("metadata") or {}
    next_cursor = meta.get("cursor")
    if isinstance(next_cursor, list) and next_cursor:
        next_cursor = str(next_cursor[0])
    elif not next_cursor:
        next_cursor = None
    return ads, next_cursor


def fetch_ad_by_id(ad_id: str) -> ForeplayAd | None:
    """Fetch a single ad's full metadata by ad_id. Costs 1 credit."""
    url = f"{PUBLIC_API}/api/ad/{ad_id}"
    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.get(url, headers=_headers())
    if r.status_code in (401, 403):
        raise ForeplayAuthError(f"Auth failed ({r.status_code}). Body: {r.text[:200]}")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    payload = r.json()
    raw = payload.get("data")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if not raw:
        return None
    # Normalize keys (same as fetch_brand_ads)
    if "content_filter" in raw and "contentFilter" not in raw:
        raw["contentFilter"] = raw["content_filter"]
    if "emotional_drivers" in raw and "emotionalDrivers" not in raw:
        raw["emotionalDrivers"] = raw["emotional_drivers"]
    if "ai_keywords" in raw and "aiKeywords" not in raw:
        raw["aiKeywords"] = raw["ai_keywords"]
    if "started_running" in raw and "startedRunning" not in raw:
        raw["startedRunning"] = raw["started_running"]
    if isinstance(raw.get("display_format"), str):
        raw["display_format"] = raw["display_format"].lower()
    if isinstance(raw.get("type"), str):
        raw["type"] = raw["type"].lower()
    return ForeplayAd.from_api(raw)


def fetch_brand_ads(
    brand_id: str,
    *,
    display_format: list[str] | None = None,
    live: bool | None = None,
    market_target: str | None = None,
    order: str = "longest_running",
    running_duration_min_days: int | None = None,
    running_duration_max_days: int | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[ForeplayAd], str | None]:
    """Fetch ads for a single brand via /api/brand/getAdsByBrandId.

    Each ad returned costs 1 credit. Returns (ads, next_cursor).
    """
    url = f"{PUBLIC_API}/api/brand/getAdsByBrandId"
    params: list[tuple[str, str]] = [
        ("brand_ids", brand_id),
        ("order", order),
        ("limit", str(limit)),
    ]
    for fmt in display_format or []:
        params.append(("display_format", fmt))
    if live is not None:
        params.append(("live", "true" if live else "false"))
    if market_target:
        params.append(("market_target", market_target))
    if running_duration_min_days is not None:
        params.append(("running_duration_min_days", str(running_duration_min_days)))
    if running_duration_max_days is not None:
        params.append(("running_duration_max_days", str(running_duration_max_days)))
    if cursor:
        params.append(("cursor", cursor))

    with httpx.Client(timeout=DEFAULT_TIMEOUT) as client:
        r = client.get(url, headers=_headers(), params=params)
    if r.status_code in (401, 403):
        raise ForeplayAuthError(f"Auth failed ({r.status_code}). Body: {r.text[:200]}")
    r.raise_for_status()
    payload = r.json()

    raw_ads = payload.get("data") or []
    ads: list[ForeplayAd] = []
    for raw in raw_ads:
        # Snake-case → camelCase aliases (same normalization as discovery)
        if "content_filter" in raw and "contentFilter" not in raw:
            raw["contentFilter"] = raw["content_filter"]
        if "emotional_drivers" in raw and "emotionalDrivers" not in raw:
            raw["emotionalDrivers"] = raw["emotional_drivers"]
        if "ai_keywords" in raw and "aiKeywords" not in raw:
            raw["aiKeywords"] = raw["ai_keywords"]
        if "started_running" in raw and "startedRunning" not in raw:
            raw["startedRunning"] = raw["started_running"]
        if isinstance(raw.get("display_format"), str):
            raw["display_format"] = raw["display_format"].lower()
        if isinstance(raw.get("type"), str):
            raw["type"] = raw["type"].lower()
        ads.append(ForeplayAd.from_api(raw))

    meta = payload.get("metadata") or {}
    next_cursor = meta.get("cursor")
    if isinstance(next_cursor, list) and next_cursor:
        next_cursor = str(next_cursor[0])
    elif not next_cursor:
        next_cursor = None
    return ads, next_cursor


def download_asset(url: str, dest_path: Path, *, timeout: float = DEFAULT_DOWNLOAD_TIMEOUT) -> Path:
    """Download a public asset URL (image/video/thumbnail) to dest_path.

    Creates parent directories as needed. Returns dest_path on success.
    Raises httpx.HTTPError on failure.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
        r.raise_for_status()
        with dest_path.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    return dest_path
