"""Per-client competitor ad pulls from Foreplay's Ad Library mirror.

Walks `clients/<slug>/competitors.yaml`, and for each competitor that has a
`foreplay_brand_id` set, pulls currently-live image ads via Foreplay's
`/api/brand/getAdsByBrandId` in two buckets:

- **proven**  — Foreplay reports the ad has been continuously running 14+
  days (`running_duration_min_days=14`). These are the winners: survived
  test-and-kill, still scaling. Limit 20 per brand per run.
- **fresh**   — current uninterrupted run <14 days
  (`running_duration_max_days=14`). Recently launched, relaunched, or
  refreshed — could be a fresh test OR a paused-and-restarted older winner.
  The ad's `days_running` (= days since FIRST launch) may be much higher.
  Limit 10 per brand per run.

Output layout (per client):

    clients/<client>/research/competitor-ads/<competitor>/
        <ad_id>.png    # the static creative
        <ad_id>.yaml   # rich sidecar (brand, days_running, headline, CTA,
                       #   persona, emotional_drivers, ai_keywords, …)
        _index.md      # markdown table ranked by days_running, with image
                       #   thumbnails for visual scanning

Dedup is by Foreplay's stable `ad_id` (= the Facebook Ad Library ID): any ad
whose sidecar already exists on disk is skipped — only net-new ads are
downloaded each run, so a weekly cron is idempotent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from strategy.competitor_research import Competitor, load_competitors
from strategy.foreplay_client import ForeplayAd, download_asset, fetch_brand_ads

CLIENTS_DIR = Path("clients")

# Default filters per bucket. Both use order=longest_running for stable
# behavior — Foreplay's "newest" enum isn't documented in our client, so for
# the fresh bucket we cap the window at 14d and still order by longevity,
# which surfaces the most-aged-among-fresh ads first (more useful than
# literal 1-day-olds you can't yet judge).
PROVEN_FILTERS: dict[str, Any] = {
    "display_format": ["image"],
    "live": True,
    "order": "longest_running",
    "running_duration_min_days": 14,
    "limit": 20,
}
FRESH_FILTERS: dict[str, Any] = {
    "display_format": ["image"],
    "live": True,
    "order": "longest_running",
    "running_duration_max_days": 14,
    "limit": 10,
}


@dataclass
class CompetitorAdsStats:
    """Per-competitor run stats. Surfaced via on_progress and the results table."""
    competitor: str
    proven_fetched: int = 0
    fresh_fetched: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0
    note: str = ""

    def __str__(self) -> str:
        return (
            f"{self.competitor}: proven={self.proven_fetched} fresh={self.fresh_fetched} "
            f"downloaded={self.downloaded} skipped={self.skipped} errors={self.errors}"
        )


ProgressCb = Callable[[CompetitorAdsStats, "ForeplayAd | None", str], None] | None


# ─── Filesystem helpers ───────────────────────────────────────────────────────

def competitor_ads_dir(client_slug: str, competitor_slug: str) -> Path:
    """Return clients/<client>/research/competitor-ads/<competitor>/."""
    return CLIENTS_DIR / client_slug / "research" / "competitor-ads" / competitor_slug


def _image_extension_for(url: str) -> str:
    """Pick a sensible image extension from a CDN URL. Defaults to .png."""
    if not url:
        return ".png"
    lower = url.lower().split("?", 1)[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if lower.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".png"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def days_running(started_running_ms: int) -> int:
    """Days between Foreplay's started_running (unix ms) and now."""
    if not started_running_ms:
        return 0
    started = datetime.fromtimestamp(started_running_ms / 1000, tz=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - started).days)


def existing_ad_ids(dest_dir: Path) -> set[str]:
    """Set of ad_ids already on disk (from sidecar filenames). Powers dedup."""
    if not dest_dir.exists():
        return set()
    return {p.stem for p in dest_dir.glob("*.yaml") if not p.stem.startswith("_")}


# ─── Sidecar build / write ────────────────────────────────────────────────────

def _build_sidecar(
    ad: ForeplayAd,
    *,
    competitor: Competitor,
    bucket: str,
    filters: dict,
    image_filename: str,
) -> dict:
    """Build the per-ad sidecar yaml dict — captures everything Foreplay returned."""
    return {
        "ad_id": ad.ad_id,
        "foreplay_id": ad.foreplay_id,
        "brand": ad.name or competitor.name,
        "brand_id": ad.brand_id or competitor.foreplay_brand_id,
        "competitor_slug": competitor.slug,
        "bucket": bucket,
        "days_running": days_running(ad.started_running),
        "fetched_at": _now_iso(),
        "source": {
            "type": "foreplay-brand-ads",
            "filters": {k: v for k, v in filters.items() if k != "limit"},
        },
        "display_format": ad.display_format,
        "live": ad.live,
        "started_running": ad.started_running,
        "headline": ad.headline,
        "description": ad.description,
        "cta": {"type": ad.cta_type, "title": ad.cta_title},
        "link_url": ad.link_url,
        "publisher_platform": ad.publisher_platform,
        "niches": ad.niches,
        "languages": ad.languages,
        "market_target": ad.market_target,
        "product_category": ad.product_category,
        "persona": ad.persona,
        "emotional_drivers": ad.emotional_drivers,
        "ai_keywords": ad.ai_keywords,
        "assets": {
            "primary": image_filename,
            "source_image_url": ad.image_url,
            "source_thumbnail_url": ad.thumbnail_url,
        },
    }


def _write_sidecar(sidecar: dict, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as f:
        yaml.safe_dump(sidecar, f, sort_keys=False, allow_unicode=True, width=100)


# ─── Pull logic ───────────────────────────────────────────────────────────────

def _pull_bucket(
    competitor: Competitor,
    *,
    dest_dir: Path,
    bucket: str,
    filters: dict,
    seen: set[str],
    force: bool,
    stats: CompetitorAdsStats,
    on_progress: ProgressCb,
) -> None:
    """Pull one bucket (proven OR fresh) for one competitor. Mutates `seen`/`stats`."""
    try:
        ads, _ = fetch_brand_ads(competitor.foreplay_brand_id, **filters)
    except Exception as exc:  # noqa: BLE001 — surface API errors but keep run alive
        stats.errors += 1
        if on_progress:
            on_progress(stats, None,
                        f"fetch_error [{bucket}]: {type(exc).__name__}: {exc}")
        return

    if bucket == "proven":
        stats.proven_fetched += len(ads)
    else:
        stats.fresh_fetched += len(ads)

    for ad in ads:
        if not ad.ad_id:
            continue
        if not force and ad.ad_id in seen:
            stats.skipped += 1
            continue
        # Defensive: the API filter already restricts to image, but a carousel
        # or video could sneak in if Foreplay's classification differs from ours.
        if ad.is_video:
            continue

        primary_url = ad.primary_image_url
        if not primary_url:
            stats.errors += 1
            if on_progress:
                on_progress(stats, ad, f"no_image_url for {ad.ad_id}")
            continue

        ext = _image_extension_for(primary_url)
        image_filename = f"{ad.ad_id}{ext}"
        image_path = dest_dir / image_filename
        sidecar_path = dest_dir / f"{ad.ad_id}.yaml"

        try:
            download_asset(primary_url, image_path)
        except httpx.HTTPError as exc:
            stats.errors += 1
            if on_progress:
                on_progress(stats, ad, f"download_failed {ad.ad_id}: {exc}")
            continue

        sidecar = _build_sidecar(
            ad, competitor=competitor, bucket=bucket,
            filters=filters, image_filename=image_filename,
        )
        _write_sidecar(sidecar, sidecar_path)

        seen.add(ad.ad_id)
        stats.downloaded += 1
        if on_progress:
            on_progress(stats, ad,
                        f"saved {ad.ad_id} [{bucket}] ({days_running(ad.started_running)}d)")


def pull_competitor_ads(
    competitor: Competitor,
    client_slug: str,
    *,
    force: bool = False,
    on_progress: ProgressCb = None,
) -> CompetitorAdsStats:
    """Pull live image ads for one competitor in both buckets (proven + fresh)."""
    stats = CompetitorAdsStats(competitor=competitor.slug)
    if not competitor.foreplay_brand_id:
        stats.note = "no foreplay_brand_id"
        if on_progress:
            on_progress(stats, None, f"skip: no foreplay_brand_id for {competitor.slug}")
        return stats

    dest_dir = competitor_ads_dir(client_slug, competitor.slug)
    dest_dir.mkdir(parents=True, exist_ok=True)
    seen = set() if force else existing_ad_ids(dest_dir)

    _pull_bucket(competitor, dest_dir=dest_dir, bucket="proven",
                 filters=PROVEN_FILTERS, seen=seen, force=force,
                 stats=stats, on_progress=on_progress)
    _pull_bucket(competitor, dest_dir=dest_dir, bucket="fresh",
                 filters=FRESH_FILTERS, seen=seen, force=force,
                 stats=stats, on_progress=on_progress)

    _rewrite_index(dest_dir, competitor)
    return stats


def pull_all_competitors_for_client(
    client_slug: str,
    *,
    only: list[str] | None = None,
    force: bool = False,
    on_progress: ProgressCb = None,
) -> list[CompetitorAdsStats]:
    """Pull ads for every competitor in clients/<slug>/competitors.yaml that has
    a `foreplay_brand_id` set. `only` filters to specific competitor slugs."""
    competitors = load_competitors(client_slug)
    if only:
        wanted = set(only)
        competitors = [c for c in competitors if c.slug in wanted]
    return [pull_competitor_ads(c, client_slug, force=force, on_progress=on_progress)
            for c in competitors]


# ─── Index rendering ──────────────────────────────────────────────────────────

def _rewrite_index(dest_dir: Path, competitor: Competitor) -> None:
    """Regenerate _index.md ranked by days_running desc from all sidecars in dir.

    Image links are relative to the index file so previewers render thumbnails
    inline. Idempotent: re-running this with no new downloads still produces
    the same file.
    """
    sidecars: list[dict] = []
    for path in sorted(dest_dir.glob("*.yaml")):
        if path.stem.startswith("_"):
            continue
        try:
            with path.open(encoding="utf-8") as f:
                sidecars.append(yaml.safe_load(f) or {})
        except Exception:  # noqa: BLE001 — never let a malformed sidecar kill the index
            continue

    sidecars.sort(key=lambda s: s.get("days_running") or 0, reverse=True)

    lines = [
        f"# {competitor.name} — competitor ads (Foreplay)",
        "",
        f"_Last regenerated: {_now_iso()}_  ",
        f"_Brand: {competitor.name} (`{competitor.foreplay_brand_id}`) · "
        f"{len(sidecars)} ads_  ",
        "",
        "Ranked by days since first launch (longest at top). "
        "`bucket: proven` = currently running 14+ days uninterrupted (winners); "
        "`bucket: fresh` = current run <14d (recently launched OR relaunched — "
        "an ad's days-since-first-launch may still be high).",
        "",
        "| Days | Bucket | Ad ID | Headline | Image |",
        "|---|---|---|---|---|",
    ]
    for s in sidecars:
        ad_id = s.get("ad_id", "")
        days = s.get("days_running", 0)
        bucket = s.get("bucket", "")
        headline = (s.get("headline") or "").replace("|", "\\|").replace("\n", " ")[:80]
        image = (s.get("assets") or {}).get("primary", "")
        lines.append(
            f"| {days} | {bucket} | `{ad_id}` | {headline} | ![{ad_id}]({image}) |"
        )

    (dest_dir / "_index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
