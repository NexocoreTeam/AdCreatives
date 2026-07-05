"""Tests for the per-client competitor-ads pull pipeline.

Network is mocked at the `fetch_brand_ads` / `download_asset` seam — no
Foreplay credits are spent. Focus is on the invariants that protect the
weekly cron from regressions: yaml schema, dedup, bucket tagging, and the
graceful skip when a competitor has no foreplay_brand_id.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
import yaml

from strategy import competitor_ads
from strategy.competitor_ads import (
    CompetitorAdsStats,
    FRESH_FILTERS,
    PROVEN_FILTERS,
    _build_sidecar,
    competitor_ads_dir,
    days_running,
    existing_ad_ids,
    pull_competitor_ads,
)
from strategy.competitor_research import Competitor, load_competitors
from strategy.foreplay_client import ForeplayAd


def _competitor(**kwargs) -> Competitor:
    base = {"name": "RivalCo", "slug": "rivalco", "url": "https://rivalco.com",
            "foreplay_brand_id": "BRAND_ABCDEFG"}
    base.update(kwargs)
    return Competitor(**base)


def _ad(ad_id: str, *, days_ago: int, headline: str = "h", is_video: bool = False) -> ForeplayAd:
    """Build a minimal ForeplayAd whose started_running is `days_ago` days back."""
    started_ms = int((datetime.now(timezone.utc).timestamp() - days_ago * 86400) * 1000)
    return ForeplayAd(
        ad_id=ad_id,
        foreplay_id=f"fp_{ad_id}",
        name="RivalCo",
        brand_id="BRAND_ABCDEFG",
        headline=headline,
        display_format="video" if is_video else "image",
        type="video" if is_video else "image",
        live=True,
        started_running=started_ms,
        image_url=f"https://cdn.example.com/{ad_id}.jpg",
    )


# ─── Schema: Competitor.foreplay_brand_id ────────────────────────────────────


def test_competitor_loads_foreplay_brand_id_from_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    client_dir = tmp_path / "clients" / "demo"
    client_dir.mkdir(parents=True)
    (client_dir / "competitors.yaml").write_text(
        yaml.safe_dump({
            "competitors": [
                {"name": "WithId", "slug": "withid", "url": "https://withid.com",
                 "foreplay_brand_id": "BRAND_123"},
                {"name": "NoId", "slug": "noid", "url": "https://noid.com"},
            ],
        }),
        encoding="utf-8",
    )

    competitors = load_competitors("demo")
    by_slug = {c.slug: c for c in competitors}
    assert by_slug["withid"].foreplay_brand_id == "BRAND_123"
    # Backwards-compatible default — legacy yaml without the field must still load.
    assert by_slug["noid"].foreplay_brand_id == ""


# ─── Helpers ─────────────────────────────────────────────────────────────────


def test_days_running_zero_for_missing_timestamp():
    assert days_running(0) == 0


def test_days_running_computes_days_since_started():
    five_days_ms = int((datetime.now(timezone.utc).timestamp() - 5 * 86400) * 1000)
    # Allow ±1 day slack for run-time and rounding.
    assert 4 <= days_running(five_days_ms) <= 5


def test_existing_ad_ids_excludes_index_and_underscore_prefix(tmp_path: Path):
    (tmp_path / "111.yaml").write_text("ad_id: '111'\n", encoding="utf-8")
    (tmp_path / "222.yaml").write_text("ad_id: '222'\n", encoding="utf-8")
    (tmp_path / "_index.md").write_text("# index\n", encoding="utf-8")
    (tmp_path / "_other.yaml").write_text("internal: yes\n", encoding="utf-8")
    (tmp_path / "111.jpg").write_text("img", encoding="utf-8")

    assert existing_ad_ids(tmp_path) == {"111", "222"}


def test_existing_ad_ids_empty_when_dir_missing(tmp_path: Path):
    assert existing_ad_ids(tmp_path / "does-not-exist") == set()


# ─── Sidecar shape ───────────────────────────────────────────────────────────


def test_build_sidecar_captures_bucket_days_and_assets():
    comp = _competitor()
    ad = _ad("99999", days_ago=87, headline="Buy now")
    sidecar = _build_sidecar(
        ad, competitor=comp, bucket="proven",
        filters=PROVEN_FILTERS, image_filename="99999.jpg",
    )

    assert sidecar["ad_id"] == "99999"
    assert sidecar["competitor_slug"] == "rivalco"
    assert sidecar["bucket"] == "proven"
    assert 86 <= sidecar["days_running"] <= 87
    assert sidecar["headline"] == "Buy now"
    assert sidecar["assets"]["primary"] == "99999.jpg"
    # `limit` is a request param, not a substantive filter — must NOT appear in sidecar.
    assert "limit" not in sidecar["source"]["filters"]
    assert sidecar["source"]["filters"]["running_duration_min_days"] == 14


# ─── pull_competitor_ads behavior ────────────────────────────────────────────


def test_pull_skips_competitor_without_brand_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    # If fetch_brand_ads gets called, the test fails — skip must short-circuit.
    monkeypatch.setattr(
        competitor_ads, "fetch_brand_ads",
        lambda *a, **k: pytest.fail("fetch_brand_ads should not be called"),
    )

    comp = _competitor(foreplay_brand_id="")
    stats = pull_competitor_ads(comp, "demo")

    assert stats.note == "no foreplay_brand_id"
    assert stats.downloaded == 0
    assert stats.proven_fetched == 0
    assert stats.fresh_fetched == 0


def test_pull_dedups_against_existing_sidecars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)

    comp = _competitor()
    # Prepare dest dir with one already-saved sidecar.
    dest = competitor_ads_dir("demo", comp.slug)
    dest.mkdir(parents=True)
    (dest / "already_here.yaml").write_text("ad_id: already_here\n", encoding="utf-8")

    proven_ads = [_ad("already_here", days_ago=200), _ad("new_proven", days_ago=90)]
    fresh_ads = [_ad("new_fresh", days_ago=3)]

    def fake_fetch(brand_id, **kwargs):
        assert brand_id == "BRAND_ABCDEFG"
        if kwargs.get("running_duration_min_days") == 14:
            return proven_ads, None
        return fresh_ads, None

    downloaded: list[tuple[str, Path]] = []

    def fake_download(url, dest_path, **kwargs):
        downloaded.append((url, dest_path))
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(b"fake-image")
        return dest_path

    monkeypatch.setattr(competitor_ads, "fetch_brand_ads", fake_fetch)
    monkeypatch.setattr(competitor_ads, "download_asset", fake_download)

    stats = pull_competitor_ads(comp, "demo")

    # already_here was dedup'd; new_proven + new_fresh downloaded.
    assert stats.proven_fetched == 2
    assert stats.fresh_fetched == 1
    assert stats.downloaded == 2
    assert stats.skipped == 1
    assert stats.errors == 0

    # Two new sidecars + the pre-existing one + _index.md.
    yamls = {p.stem for p in dest.glob("*.yaml")}
    assert {"already_here", "new_proven", "new_fresh"}.issubset(yamls)
    assert (dest / "_index.md").exists()


def test_pull_skips_video_ads_defensively(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The API filter restricts to image, but a video sneaking through should be dropped."""
    monkeypatch.chdir(tmp_path)

    comp = _competitor()
    proven_ads = [_ad("video_one", days_ago=30, is_video=True),
                  _ad("image_one", days_ago=30)]

    def fake_fetch(brand_id, **kwargs):
        return (proven_ads if kwargs.get("running_duration_min_days") == 14
                else []), None

    monkeypatch.setattr(competitor_ads, "fetch_brand_ads", fake_fetch)
    monkeypatch.setattr(
        competitor_ads, "download_asset",
        lambda url, path, **k: path.parent.mkdir(parents=True, exist_ok=True)
        or path.write_bytes(b"x") or path,
    )

    stats = pull_competitor_ads(comp, "demo")

    # Only the image ad gets saved; the video is silently dropped (not an error).
    dest = competitor_ads_dir("demo", comp.slug)
    saved = {p.stem for p in dest.glob("*.yaml") if not p.stem.startswith("_")}
    assert saved == {"image_one"}
    assert stats.downloaded == 1


# ─── Filter sanity ───────────────────────────────────────────────────────────


def test_proven_and_fresh_filters_target_different_windows():
    """The two buckets must request opposite duration windows — otherwise we'd
    just be paying double credits for the same ad set."""
    assert PROVEN_FILTERS["running_duration_min_days"] == 14
    assert "running_duration_max_days" not in PROVEN_FILTERS
    assert FRESH_FILTERS["running_duration_max_days"] == 14
    assert "running_duration_min_days" not in FRESH_FILTERS
    # Both buckets pull live image ads sorted longest-first.
    for f in (PROVEN_FILTERS, FRESH_FILTERS):
        assert f["display_format"] == ["image"]
        assert f["live"] is True
        assert f["order"] == "longest_running"
