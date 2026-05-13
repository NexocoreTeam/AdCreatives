"""Sync ads from Foreplay boards into the local swipe library.

Walks a library's `_meta.yaml`, fetches ads from each category's Foreplay
board, downloads the primary image (or video thumbnail), and writes a
sidecar `.yaml` capturing the full metadata.

Layout produced:
    references/swipe/<library>/<category>/<ad_id>.png
    references/swipe/<library>/<category>/<ad_id>.yaml

Idempotent: ads already on disk are skipped unless `force=True`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import json

import httpx
import yaml

from strategy.foreplay_client import (
    ForeplayAd,
    download_asset,
    fetch_ad_by_id,
    fetch_brand_ads,
    fetch_discovery_ads,
    iter_expert_board,
)


SWIPE_ROOT = Path("references/swipe")
META_FILE = "_meta.yaml"


@dataclass
class SyncStats:
    library: str
    category: str
    fetched: int = 0
    downloaded: int = 0
    skipped: int = 0
    errors: int = 0

    def __str__(self) -> str:
        return (
            f"{self.library}/{self.category}: "
            f"fetched={self.fetched} downloaded={self.downloaded} "
            f"skipped={self.skipped} errors={self.errors}"
        )


def load_library_meta(library: str) -> dict:
    """Load the _meta.yaml describing a swipe library."""
    path = SWIPE_ROOT / library / META_FILE
    if not path.exists():
        raise FileNotFoundError(f"No metadata for library '{library}' at {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _slug(s: str) -> str:
    """Lowercase + hyphen-safe slug for category folder names."""
    return s.lower().replace("_", "-").replace(" ", "-").replace("/", "-")


# Map Foreplay's UI Content Style labels → our category slugs.
# Labels like "Features and Benefits", "Us vs Them" etc.
FOREPLAY_STYLE_TO_SLUG: dict[str, str] = {
    "features and benefits": "features-and-benefits",
    "us vs them": "us-vs-them",
    "testimonial review": "testimonial-review",
    "testimonial - review": "testimonial-review",
    "before and after": "before-and-after",
    "promotion and discount": "promotion-and-discount",
    "ugc": "ugc",
    "facts and stats": "facts-and-stats",
    "reasons why": "reasons-why",
    "media and press": "media-and-press",
    # Labels we explicitly DON'T bucket (not in our standard categories):
    # "Holiday Seasonal", "Unboxing", "Green Screen", "Podcast", "Other"
}


def _load_classification_cache(library: str) -> dict[str, str]:
    """Load Foreplay-scraped ad_id → content_style_slug mapping for a library.

    Returns empty dict if cache is absent. Cache file:
        references/swipe/<library>/_classifications-cache.json
    """
    cache_path = SWIPE_ROOT / library / "_classifications-cache.json"
    if not cache_path.exists():
        return {}
    with cache_path.open(encoding="utf-8") as f:
        raw = json.load(f)
    out: dict[str, str] = {}
    for brand_id, brand_data in (raw.get("brands") or {}).items():
        for record in brand_data.get("records") or []:
            style = record.get("content_style")
            ad_id = record.get("ad_id")
            if not style or not ad_id:
                continue
            slug = FOREPLAY_STYLE_TO_SLUG.get(style.strip().lower())
            if slug:
                out[str(ad_id)] = slug
    return out


def _sync_from_classification_cache(
    library: str,
    meta: dict,
    style_to_slug: dict[str, str],
    *,
    force: bool,
    on_progress,
) -> list[SyncStats]:
    """Sync by iterating cached classifications directly via /api/ad/{ad_id}.

    Faster + more accurate than per-brand fetch when the cache is populated:
    we fetch only the ads we know we want to classify, no wasted credits on
    ads we'll throw away.
    """
    cache_path = SWIPE_ROOT / library / "_classifications-cache.json"
    with cache_path.open(encoding="utf-8") as f:
        raw_cache = json.load(f)

    categories = meta.get("categories") or {}
    defaults = meta.get("defaults") or {}
    total_cap_per_category = int(defaults.get("total_cap_per_category", 50))
    per_brand_per_category_cap = int(defaults.get("per_brand_per_category_cap", 4))
    filters = (meta.get("source") or {}).get("filters") or {}

    all_stats = {slug: SyncStats(library=library, category=slug) for slug in categories}
    per_cat_count: dict[str, int] = {slug: 0 for slug in categories}
    per_brand_cat_count: dict[tuple[str, str], int] = {}

    if not force:
        for slug in categories:
            existing = list((SWIPE_ROOT / library / slug).glob("*.yaml"))
            per_cat_count[slug] = len(existing)

    for brand_id, brand_data in (raw_cache.get("brands") or {}).items():
        brand_name = brand_data.get("name") or brand_id
        records = brand_data.get("records") or []
        for record in records:
            ad_id = record.get("ad_id")
            style = record.get("content_style")
            if not ad_id or not style:
                continue
            cat_slug = style_to_slug.get(style.strip().lower())
            if not cat_slug or cat_slug not in categories:
                continue
            if per_cat_count.get(cat_slug, 0) >= total_cap_per_category:
                continue
            brand_cat_key = (brand_id, cat_slug)
            if per_brand_cat_count.get(brand_cat_key, 0) >= per_brand_per_category_cap:
                continue
            if not force and _find_existing_ad(library, ad_id):
                continue

            if on_progress:
                on_progress(all_stats[cat_slug], None,
                            f"fetching {ad_id} -> {cat_slug} [{brand_name}]")
            try:
                ad = fetch_ad_by_id(ad_id)
            except Exception as exc:
                all_stats[cat_slug].errors += 1
                if on_progress:
                    on_progress(all_stats[cat_slug], None,
                                f"fetch_error for {ad_id}: {exc}")
                continue
            if not ad:
                all_stats[cat_slug].errors += 1
                continue

            primary_url = ad.primary_image_url
            if not primary_url:
                all_stats[cat_slug].errors += 1
                if on_progress:
                    on_progress(all_stats[cat_slug], ad,
                                f"no_image_url for {ad_id}")
                continue

            ext = _image_extension_for(primary_url, ad.is_video)
            image_filename = f"{ad.ad_id}{ext}"
            dest_dir = SWIPE_ROOT / library / cat_slug
            image_path = dest_dir / image_filename
            sidecar_path = dest_dir / f"{ad.ad_id}.yaml"

            try:
                download_asset(primary_url, image_path)
            except httpx.HTTPError as exc:
                all_stats[cat_slug].errors += 1
                if on_progress:
                    on_progress(all_stats[cat_slug], ad,
                                f"download_failed {ad.ad_id}: {exc}")
                continue

            sidecar_source = {
                "type": "foreplay-brand-aggregation",
                "brand": brand_name,
                "brand_id": brand_id,
                "niche": record.get("niche"),
                "classifier": "foreplay-ui-content-style",
                "classification": {"category": cat_slug, "source": "scraped",
                                   "foreplay_label": style},
                "filters": filters,
            }
            sidecar = _build_sidecar(
                ad,
                library=library,
                category=cat_slug,
                library_meta=meta,
                source=sidecar_source,
                primary_filename=image_filename,
            )
            _write_sidecar(sidecar, sidecar_path)

            all_stats[cat_slug].downloaded += 1
            all_stats[cat_slug].fetched += 1
            per_cat_count[cat_slug] += 1
            per_brand_cat_count[brand_cat_key] = per_brand_cat_count.get(brand_cat_key, 0) + 1

            if on_progress:
                on_progress(all_stats[cat_slug], ad,
                            f"saved {ad.ad_id} -> {cat_slug} [{brand_name}]")

    return list(all_stats.values())


def _find_existing_ad(library: str, ad_id: str) -> Path | None:
    """Return the existing sidecar path for ad_id anywhere in this library, if any."""
    library_root = SWIPE_ROOT / library
    if not library_root.exists():
        return None
    for path in library_root.glob(f"*/{ad_id}.yaml"):
        return path
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _build_sidecar(
    ad: ForeplayAd,
    *,
    library: str,
    category: str,
    library_meta: dict,
    source: dict,
    primary_filename: str,
) -> dict:
    """Build the sidecar YAML dict for an ad. `source` is library-type specific."""
    purpose = library_meta.get("purpose") or {}
    return {
        "ad_id": ad.ad_id,
        "foreplay_id": ad.foreplay_id,
        "brand": ad.name,
        "brand_id": ad.brand_id,
        "library": library,
        "category": category,
        # purpose travels with each ad so downstream prompt generation knows
        # which signal type this reference carries.
        "purpose": {
            "signal": purpose.get("signal", ""),
            "use_for": purpose.get("use_for", []),
            "not_for": purpose.get("not_for", []),
        },
        "source": {**source, "fetched_at": _now_iso()},
        "display_format": ad.display_format,
        "is_video": ad.is_video,
        "is_carousel": ad.is_carousel,
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
        "creative_targeting": ad.creative_targeting,
        "persona": ad.persona,
        "emotional_drivers": ad.emotional_drivers,
        "content_filter": ad.content_filter,
        "ai_keywords": ad.ai_keywords,
        "video_duration": ad.video_duration,
        "assets": {
            "primary": primary_filename,
            "source_image_url": ad.image_url,
            "source_video_url": ad.video_url,
            "source_thumbnail_url": ad.thumbnail_url,
            "card_image_urls": ad.card_image_urls,
            "mobile_screenshot_url": ad.mobile_screenshot,
        },
    }


def _write_sidecar(sidecar: dict, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with dest_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(sidecar, f, sort_keys=False, allow_unicode=True, width=100)


def _image_extension_for(url: str, is_video: bool) -> str:
    """Pick a sensible file extension. Thumbnails for videos are .jpeg."""
    if not url:
        return ".png"
    lower = url.lower().split("?", 1)[0]
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if lower.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg" if is_video else ".png"


def sync_category(
    library: str,
    category: str,
    *,
    max_ads: int = 10,
    force: bool = False,
    on_progress=None,
) -> SyncStats:
    """Sync ads from a single category in a library.

    Args:
        library: e.g. 'psychology'
        category: e.g. 'belonging'
        max_ads: cap on ads to pull from this category's board
        force: re-download even if the file exists
        on_progress: optional callable(stats, ad_or_None, msg) for live updates
    """
    meta = load_library_meta(library)
    source = meta.get("source") or {}
    cats = meta.get("categories") or {}

    if category not in cats:
        raise KeyError(f"Category '{category}' not in {library}/_meta.yaml")

    board_id = cats[category].get("board_id")
    if not board_id:
        raise ValueError(f"No board_id for {library}/{category}")

    expert_user_id = source.get("expert_user_id")
    if not expert_user_id:
        raise ValueError(f"No expert_user_id in {library}/_meta.yaml source")

    dest_dir = SWIPE_ROOT / library / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    stats = SyncStats(library=library, category=category)
    if on_progress:
        on_progress(stats, None, f"start {library}/{category} (board {board_id[:8]}...)")

    for ad in iter_expert_board(expert_user_id, board_id, max_ads=max_ads):
        stats.fetched += 1
        if not ad.ad_id:
            stats.errors += 1
            if on_progress:
                on_progress(stats, ad, "skip: missing ad_id")
            continue

        primary_url = ad.primary_image_url
        ext = _image_extension_for(primary_url, ad.is_video)
        image_filename = f"{ad.ad_id}{ext}"
        image_path = dest_dir / image_filename
        sidecar_path = dest_dir / f"{ad.ad_id}.yaml"

        image_already_present = image_path.exists() and image_path.stat().st_size > 0
        need_download = force or not image_already_present

        if need_download:
            if not primary_url:
                stats.errors += 1
                if on_progress:
                    on_progress(stats, ad, f"error: no image url for {ad.ad_id} ({ad.display_format})")
                continue
            try:
                download_asset(primary_url, image_path)
            except httpx.HTTPError as exc:
                stats.errors += 1
                if on_progress:
                    on_progress(stats, ad, f"error: download failed for {ad.ad_id}: {exc}")
                continue
            stats.downloaded += 1
        else:
            stats.skipped += 1

        # Always (re)write the sidecar — cheap and ensures schema stays current.
        sidecar_source = {
            "type": source.get("type", "foreplay-expert"),
            "expert_name": source.get("expert_name", ""),
            "expert_url": source.get("expert_url", ""),
            "expert_user_id": source.get("expert_user_id", ""),
            "board_id": board_id,
        }
        sidecar = _build_sidecar(
            ad,
            library=library,
            category=category,
            library_meta=meta,
            source=sidecar_source,
            primary_filename=image_filename,
        )
        _write_sidecar(sidecar, sidecar_path)
        if on_progress:
            verb = "saved" if need_download else "refreshed sidecar"
            on_progress(stats, ad, f"{verb} {ad.ad_id} ({ad.name[:30]})")

    if on_progress:
        on_progress(stats, None, f"done {library}/{category}: {stats}")
    return stats


def sync_library(
    library: str,
    *,
    categories: list[str] | None = None,
    max_per_category: int = 10,
    max_per_niche: int = 30,
    force: bool = False,
    on_progress=None,
) -> list[SyncStats]:
    """Sync a swipe library. Routes to expert vs discovery flow per _meta.yaml."""
    meta = load_library_meta(library)
    src_type = ((meta.get("source") or {}).get("type") or "").strip()

    if src_type == "foreplay-expert":
        return _sync_expert_library(
            library,
            categories=categories,
            max_per_category=max_per_category,
            force=force,
            on_progress=on_progress,
        )
    if src_type == "foreplay-discovery":
        return _sync_discovery_library(
            library,
            max_per_niche=max_per_niche,
            force=force,
            on_progress=on_progress,
        )
    if src_type == "foreplay-brand-aggregation":
        return _sync_brand_library(
            library,
            force=force,
            on_progress=on_progress,
        )
    raise ValueError(
        f"Unknown source.type '{src_type}' in {library}/_meta.yaml — "
        f"expected 'foreplay-expert', 'foreplay-discovery', or 'foreplay-brand-aggregation'"
    )


def _sync_expert_library(
    library: str,
    *,
    categories: list[str] | None,
    max_per_category: int,
    force: bool,
    on_progress,
) -> list[SyncStats]:
    """Sync an expert-board-sourced library (one Foreplay board per category)."""
    meta = load_library_meta(library)
    all_cats = list((meta.get("categories") or {}).keys())
    targets = categories or all_cats

    out: list[SyncStats] = []
    for cat in targets:
        if cat not in all_cats:
            if on_progress:
                on_progress(
                    SyncStats(library=library, category=cat),
                    None,
                    f"warn: '{cat}' not defined in {library}/_meta.yaml",
                )
            continue
        out.append(
            sync_category(
                library, cat,
                max_ads=max_per_category, force=force, on_progress=on_progress,
            )
        )
    return out


def _sync_brand_library(
    library: str,
    *,
    force: bool,
    on_progress,
    limit_brands: int | None = None,
    limit_per_brand: int | None = None,
) -> list[SyncStats]:
    """Sync a brand-aggregation library.

    Classification source (in order of preference):
      1. Foreplay-scraped cache at <library>/_classifications-cache.json
         (populated by `adc scrape-classifications`). Uses Foreplay's own
         Content Style labels — the user-trusted source.
      2. Claude Haiku text-only classifier (strategy/ad_classifier.py) as
         fallback for ads not in the cache.

    Per-category and per-brand-per-category caps from _meta.yaml are enforced.
    """
    from strategy.ad_classifier import classify_ad as classify  # lazy import (Anthropic dep)

    # Try cache first — if present, this skips Haiku entirely for cached ads.
    scraped: dict[str, str] = _load_classification_cache(library)
    use_cache = bool(scraped)

    meta = load_library_meta(library)

    # CACHE-DRIVEN PATH: when scraped cache is present, iterate cached ad_ids
    # directly via /api/ad/{ad_id} instead of pulling per-brand pages (which
    # may not include the cached ad_ids in their first N results).
    if use_cache:
        return _sync_from_classification_cache(library, meta, FOREPLAY_STYLE_TO_SLUG,
                                               force=force, on_progress=on_progress)
    source_meta = meta.get("source") or {}
    filters = source_meta.get("filters") or {}
    defaults = meta.get("defaults") or {}
    brands = meta.get("brands") or []
    categories = meta.get("categories") or {}

    if not brands:
        raise ValueError(f"No brands in {library}/_meta.yaml")
    if not categories:
        raise ValueError(f"No categories in {library}/_meta.yaml")

    per_brand_cap = int(defaults.get("per_brand_cap", 30))
    per_brand_per_category_cap = int(defaults.get("per_brand_per_category_cap", 4))
    total_cap_per_category = int(defaults.get("total_cap_per_category", 50))
    min_conf = float(source_meta.get("min_classifier_confidence", 0.5))

    if limit_per_brand is not None:
        per_brand_cap = min(per_brand_cap, int(limit_per_brand))

    valid_keys = {cat_meta.get("key", slug) for slug, cat_meta in categories.items()}
    # Map classifier-returned key → folder slug. Usually identity.
    key_to_slug = {(cat_meta.get("key") or slug): slug for slug, cat_meta in categories.items()}

    all_stats = {slug: SyncStats(library=library, category=slug) for slug in categories}
    per_cat_count: dict[str, int] = {slug: 0 for slug in categories}
    per_brand_cat_count: dict[tuple[str, str], int] = {}

    # Respect prior runs unless --force
    if not force:
        for slug in categories:
            existing = list((SWIPE_ROOT / library / slug).glob("*.yaml"))
            per_cat_count[slug] = len(existing)

    brand_iter = brands if limit_brands is None else brands[:limit_brands]

    for brand_entry in brand_iter:
        brand_name = brand_entry.get("name") or "?"
        brand_id = brand_entry.get("brand_id")
        niche = brand_entry.get("niche") or ""
        if not brand_id:
            if on_progress:
                on_progress(
                    SyncStats(library=library, category=f"_brand:{brand_name}"),
                    None, f"skip: no brand_id for {brand_name}",
                )
            continue

        # Stop entirely if every category is full
        if all(per_cat_count[slug] >= total_cap_per_category for slug in categories):
            break

        if on_progress:
            on_progress(
                SyncStats(library=library, category=f"_brand:{brand_name}"),
                None,
                f"fetching '{brand_name}' (cap {per_brand_cap} ads)",
            )

        try:
            ads, _ = fetch_brand_ads(
                brand_id,
                display_format=filters.get("display_format"),
                live=filters.get("live"),
                market_target=filters.get("market_target"),
                order=filters.get("order", "longest_running"),
                running_duration_min_days=filters.get("running_duration_min_days"),
                running_duration_max_days=filters.get("running_duration_max_days"),
                limit=per_brand_cap,
            )
        except Exception as exc:
            if on_progress:
                on_progress(
                    SyncStats(library=library, category=f"_brand:{brand_name}"),
                    None, f"error fetching {brand_name}: {exc}",
                )
            continue

        for ad in ads:
            if not ad.ad_id:
                continue
            if not force and _find_existing_ad(library, ad.ad_id):
                continue

            # Prefer scraped Foreplay classification over Haiku
            cls = None
            cat_slug: str | None = None
            cached_slug = scraped.get(ad.ad_id) if use_cache else None
            if cached_slug and cached_slug in {key_to_slug.get(k, k) for k in valid_keys}:
                # Direct hit from Foreplay's classifier
                cat_slug = cached_slug
            else:
                # Fall back to Haiku — but only if cache wasn't supposed to cover this ad
                if use_cache:
                    # Cache exists but doesn't classify this ad (video, "other", or not scraped)
                    # — skip rather than mix sources
                    continue
                try:
                    cls = classify(
                        brand=ad.name or brand_name,
                        headline=ad.headline,
                        description=ad.description,
                        cta_title=ad.cta_title,
                        cta_type=ad.cta_type,
                        keywords=ad.keywords,
                        ai_keywords=ad.ai_keywords,
                        niches=ad.niches or [niche],
                    )
                except Exception as exc:
                    if on_progress:
                        on_progress(
                            SyncStats(library=library, category=f"_brand:{brand_name}"),
                            ad, f"classifier_error on {ad.ad_id}: {exc}",
                        )
                    continue

                cat_key = cls.category
                if cat_key == "other" or cat_key not in valid_keys:
                    continue
                if cls.confidence < min_conf:
                    continue
                cat_slug = key_to_slug.get(cat_key, cat_key)
            if per_cat_count[cat_slug] >= total_cap_per_category:
                continue
            brand_cat_key = (brand_id, cat_slug)
            if per_brand_cat_count.get(brand_cat_key, 0) >= per_brand_per_category_cap:
                continue

            primary_url = ad.primary_image_url
            if not primary_url:
                all_stats[cat_slug].errors += 1
                continue

            ext = _image_extension_for(primary_url, ad.is_video)
            image_filename = f"{ad.ad_id}{ext}"
            dest_dir = SWIPE_ROOT / library / cat_slug
            image_path = dest_dir / image_filename
            sidecar_path = dest_dir / f"{ad.ad_id}.yaml"

            try:
                download_asset(primary_url, image_path)
            except httpx.HTTPError as exc:
                all_stats[cat_slug].errors += 1
                if on_progress:
                    on_progress(all_stats[cat_slug], ad,
                                f"download_failed {ad.ad_id}: {exc}")
                continue

            if cls is not None:
                # Haiku-classified
                classifier_info = {
                    "classifier": "claude-haiku-4-5-20251001",
                    "classification": {
                        "category": cls.category,
                        "confidence": round(cls.confidence, 3),
                        "reasoning": cls.reasoning,
                    },
                }
            else:
                # Foreplay-scraped classification
                classifier_info = {
                    "classifier": "foreplay-ui-content-style",
                    "classification": {"category": cat_slug, "source": "scraped"},
                }
            sidecar_source = {
                "type": "foreplay-brand-aggregation",
                "brand": brand_name,
                "brand_id": brand_id,
                "niche": niche,
                **classifier_info,
                "filters": filters,
            }
            sidecar = _build_sidecar(
                ad,
                library=library,
                category=cat_slug,
                library_meta=meta,
                source=sidecar_source,
                primary_filename=image_filename,
            )
            _write_sidecar(sidecar, sidecar_path)

            all_stats[cat_slug].downloaded += 1
            all_stats[cat_slug].fetched += 1
            per_cat_count[cat_slug] += 1
            per_brand_cat_count[brand_cat_key] = per_brand_cat_count.get(brand_cat_key, 0) + 1

            if on_progress:
                src_tag = "scraped" if cls is None else f"haiku@{cls.confidence:.2f}"
                on_progress(
                    all_stats[cat_slug], ad,
                    f"saved {ad.ad_id} -> {cat_slug} [{src_tag}] [{brand_name}]",
                )

    return list(all_stats.values())


def _sync_discovery_library(
    library: str,
    *,
    max_per_niche: int,
    force: bool,
    on_progress,
) -> list[SyncStats]:
    """Sync a discovery-sourced library by walking niches and bucketing by contentFilter argmax.

    For each niche, fetches up to `max_per_niche` ads matching the library's
    filter spec. Each ad is assigned to a category by argmax over its
    content_filter scores. Ads are accepted only if their argmax category is
    listed in the library's _meta.yaml AND we haven't hit per-category or
    per-niche-per-category caps.
    """
    meta = load_library_meta(library)
    source_meta = meta.get("source") or {}
    niches = meta.get("niches") or []
    categories = meta.get("categories") or {}
    filters = source_meta.get("filters") or {}

    # Build a lookup: content_filter_key -> (slug, total_cap, per_niche_cap)
    category_lookup: dict[str, tuple[str, int, int]] = {}
    for cat_slug, cat_meta in categories.items():
        cfk = (cat_meta or {}).get("content_filter_key")
        if not cfk:
            continue
        category_lookup[cfk] = (
            cat_slug,
            int((cat_meta or {}).get("total_cap", 50)),
            int((cat_meta or {}).get("per_niche_cap", 5)),
        )

    if not category_lookup:
        raise ValueError(f"No categories with content_filter_key in {library}/_meta.yaml")

    all_stats = {slug: SyncStats(library=library, category=slug) for slug, _, _ in category_lookup.values()}
    per_cat_count: dict[str, int] = {slug: 0 for slug in all_stats}
    per_niche_cat_count: dict[tuple[str, str], int] = {}

    # Pre-count what's already on disk so per-category caps respect prior runs.
    if not force:
        for slug in all_stats:
            existing = list((SWIPE_ROOT / library / slug).glob("*.yaml"))
            per_cat_count[slug] = len(existing)

    min_score = float(source_meta.get("min_content_filter_score", 0.15))

    for niche in niches:
        # Skip the niche entirely if all categories are full.
        if all(per_cat_count[s] >= cap for s, cap, _ in category_lookup.values()):
            break

        if on_progress:
            on_progress(
                SyncStats(library=library, category=f"_niche:{niche}"),
                None,
                f"fetching niche '{niche}' (cap {max_per_niche} ads)",
            )

        ads, _ = fetch_discovery_ads(
            niches=[niche],
            display_format=filters.get("display_format"),
            publisher_platform=filters.get("publisher_platform"),
            market_target=filters.get("market_target"),
            live=filters.get("live"),
            order=filters.get("order", "longest_running"),
            running_duration_min_days=filters.get("running_duration_min_days"),
            running_duration_max_days=filters.get("running_duration_max_days"),
            limit=max_per_niche,
        )

        for ad in ads:
            if not ad.ad_id:
                continue

            # Skip if we've already saved this ad anywhere in this library
            if not force and _find_existing_ad(library, ad.ad_id):
                continue

            cf = ad.content_filter or {}
            if not cf:
                continue

            # Argmax over content_filter scores
            try:
                argmax_key, score = max(
                    ((k, float(v)) for k, v in cf.items() if isinstance(v, (int, float))),
                    key=lambda kv: kv[1],
                )
            except ValueError:
                continue

            if score < min_score:
                continue
            if argmax_key not in category_lookup:
                continue

            cat_slug, total_cap, niche_cap = category_lookup[argmax_key]
            if per_cat_count[cat_slug] >= total_cap:
                continue
            niche_key = (niche, cat_slug)
            if per_niche_cat_count.get(niche_key, 0) >= niche_cap:
                continue

            primary_url = ad.primary_image_url
            if not primary_url:
                all_stats[cat_slug].errors += 1
                continue

            ext = _image_extension_for(primary_url, ad.is_video)
            image_filename = f"{ad.ad_id}{ext}"
            dest_dir = SWIPE_ROOT / library / cat_slug
            image_path = dest_dir / image_filename
            sidecar_path = dest_dir / f"{ad.ad_id}.yaml"

            try:
                download_asset(primary_url, image_path)
            except httpx.HTTPError as exc:
                all_stats[cat_slug].errors += 1
                if on_progress:
                    on_progress(all_stats[cat_slug], ad, f"error: download failed {ad.ad_id}: {exc}")
                continue

            sidecar_source = {
                "type": "foreplay-discovery",
                "niche": niche,
                "filters": filters,
                "content_filter_argmax": argmax_key,
                "content_filter_score": round(score, 3),
            }
            sidecar = _build_sidecar(
                ad,
                library=library,
                category=cat_slug,
                library_meta=meta,
                source=sidecar_source,
                primary_filename=image_filename,
            )
            _write_sidecar(sidecar, sidecar_path)

            all_stats[cat_slug].downloaded += 1
            all_stats[cat_slug].fetched += 1
            per_cat_count[cat_slug] += 1
            per_niche_cat_count[niche_key] = per_niche_cat_count.get(niche_key, 0) + 1

            if on_progress:
                on_progress(
                    all_stats[cat_slug], ad,
                    f"saved {ad.ad_id} -> {cat_slug} (niche={niche}, score={score:.2f}) [{ad.name[:25]}]",
                )

    return list(all_stats.values())
