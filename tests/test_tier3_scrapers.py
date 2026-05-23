"""Tests for the Tier 3 social-comment scrapers and the shared voc-dump path.

Each platform scraper is exercised with a mocked client so no network or API
key is required. The shared `social_comments` module is covered via round-trip
through cache + voc-dump.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from strategy import apify_instagram, apify_tiktok, youtube_comments
from strategy.competitor_research import Competitor, load_competitors
from strategy.social_comments import (
    SocialComment,
    SocialCommentBundle,
    cache_bundle,
    load_cached_bundles,
    write_voc_dump,
)

# ─── Shared helpers ─────────────────────────────────────────────────────────


def _competitor(**kwargs) -> Competitor:
    base = {
        "name": "RivalCo",
        "slug": "rivalco",
        "url": "https://rivalco.com",
    }
    base.update(kwargs)
    return Competitor(**base)


# ─── Competitor schema extension ────────────────────────────────────────────


def test_competitor_loads_social_handles_from_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    client_dir = tmp_path / "clients" / "demo"
    client_dir.mkdir(parents=True)
    (client_dir / "competitors.yaml").write_text(
        yaml.safe_dump({
            "competitors": [
                {
                    "name": "RivalCo",
                    "slug": "rivalco",
                    "url": "https://rivalco.com",
                    "tiktok_handle": "@rivalco",
                    "instagram_handle": "rivalco",
                    "youtube_handle": "@RivalCo",
                    "youtube_video_ids": ["abc123", "def456"],
                },
                {
                    # Legacy competitor with no social handles — must still load
                    "name": "OldCo",
                    "slug": "oldco",
                    "url": "https://oldco.com",
                },
            ],
        }),
        encoding="utf-8",
    )

    competitors = load_competitors("demo")
    assert len(competitors) == 2
    rival, old = competitors
    assert rival.tiktok_handle == "@rivalco"
    assert rival.instagram_handle == "rivalco"
    assert rival.youtube_handle == "@RivalCo"
    assert rival.youtube_video_ids == ["abc123", "def456"]
    assert rival.tiktok_post_urls == []
    assert old.tiktok_handle == ""
    assert old.youtube_video_ids == []


# ─── social_comments shared module ──────────────────────────────────────────


def test_cache_and_load_round_trip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = SocialCommentBundle(
        platform="tiktok",
        competitor_slug="rivalco",
        competitor_name="RivalCo",
        post_id="vid-1",
        post_url="https://www.tiktok.com/@rivalco/video/vid-1",
        post_caption="Our latest gut-health drop",
        comments=[
            SocialComment(
                platform="tiktok",
                text="this didn't work for me at all, gave me cystic acne",
                author="user_a",
                likes=42,
                post_id="vid-1",
                post_url="https://www.tiktok.com/@rivalco/video/vid-1",
            ),
            SocialComment(
                platform="tiktok",
                text="finally something that doesn't smell beefy",
                author="user_b",
                likes=7,
                post_id="vid-1",
                post_url="https://www.tiktok.com/@rivalco/video/vid-1",
            ),
        ],
    )
    path = cache_bundle("demo", bundle)
    assert path.exists()

    reloaded = load_cached_bundles("demo", "tiktok")
    assert len(reloaded) == 1
    assert reloaded[0].post_id == "vid-1"
    assert len(reloaded[0].comments) == 2
    assert reloaded[0].comments[0].likes == 42


def test_write_voc_dump_orders_by_likes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    bundle = SocialCommentBundle(
        platform="instagram",
        competitor_slug="rivalco",
        competitor_name="RivalCo",
        post_id="post-1",
        post_url="https://instagram.com/p/post-1",
        post_caption="Drop day",
        comments=[
            SocialComment(platform="instagram", text="cheap comment", likes=1),
            SocialComment(platform="instagram", text="HIGH SIGNAL", likes=999),
            SocialComment(platform="instagram", text="mid", likes=50),
        ],
    )
    cache_bundle("demo", bundle)

    out = write_voc_dump("demo", "instagram")
    assert out is not None
    records = json.loads(out.read_text(encoding="utf-8"))
    assert [r["body"] for r in records] == ["HIGH SIGNAL", "mid", "cheap comment"]
    assert all(r["rating"] == "N/A" for r in records)
    # Source label includes competitor + caption snippet
    assert "instagram:RivalCo" in records[0]["source"]
    assert "Drop day" in records[0]["source"]


def test_write_voc_dump_returns_none_when_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    assert write_voc_dump("demo", "tiktok") is None


# ─── TikTok scraper ─────────────────────────────────────────────────────────


class _FakeApifyDataset:
    def __init__(self, items):
        self._items = items

    def iterate_items(self):
        return iter(self._items)


class _FakeApifyActor:
    def __init__(self, dataset_id):
        self._dataset_id = dataset_id

    def call(self, run_input, timeout_secs):
        return {"defaultDatasetId": self._dataset_id}


class _FakeApifyClient:
    """Drop-in stand-in for ApifyClient with per-actor and per-dataset shims."""

    def __init__(self, actor_datasets: dict[str, str], datasets: dict[str, list[dict]]):
        self._actor_datasets = actor_datasets
        self._datasets = datasets

    def actor(self, actor_id):
        return _FakeApifyActor(self._actor_datasets.get(actor_id, "missing"))

    def dataset(self, dataset_id):
        return _FakeApifyDataset(self._datasets.get(dataset_id, []))


def test_tiktok_scrapes_comments_from_explicit_post_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    fake = _FakeApifyClient(
        actor_datasets={apify_tiktok.COMMENTS_ACTOR_ID: "ds-comments"},
        datasets={
            "ds-comments": [
                {
                    "cid": "c1",
                    "text": "this gave me cystic acne after 6 weeks",
                    "uniqueId": "user_a",
                    "diggCount": 88,
                    "replyCommentTotal": 3,
                    "createTimeISO": "2026-05-01T00:00:00Z",
                },
                {
                    "cid": "c2",
                    "text": "",  # empty — should be skipped
                    "uniqueId": "user_b",
                    "diggCount": 0,
                },
                {
                    "cid": "c3",
                    "text": "love it tho, no notes",
                    "uniqueId": "user_c",
                    "diggCount": 22,
                },
            ]
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    competitor = _competitor(
        tiktok_post_urls=["https://www.tiktok.com/@rivalco/video/7300000000000000001"],
    )
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)

    assert len(bundles) == 1
    bundle = bundles[0]
    assert bundle.post_id == "7300000000000000001"
    assert len(bundle.comments) == 2  # empty one filtered out
    assert bundle.comments[0].text == "this gave me cystic acne after 6 weeks"
    assert bundle.comments[0].likes == 88


def test_tiktok_falls_back_to_profile_listing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    fake = _FakeApifyClient(
        actor_datasets={
            apify_tiktok.VIDEO_ACTOR_ID: "ds-videos",
            apify_tiktok.COMMENTS_ACTOR_ID: "ds-comments",
        },
        datasets={
            "ds-videos": [
                {
                    "id": "vid-1",
                    "webVideoUrl": "https://www.tiktok.com/@rivalco/video/vid-1",
                    "text": "drop day",
                    "playCount": 10000,
                },
            ],
            "ds-comments": [
                {"cid": "c1", "text": "underwhelming", "uniqueId": "u1", "diggCount": 5},
            ],
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    competitor = _competitor(tiktok_handle="@rivalco")
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)
    assert len(bundles) == 1
    assert bundles[0].post_caption == "drop day"
    assert bundles[0].comments[0].text == "underwhelming"


def test_tiktok_returns_empty_when_no_handle_configured():
    competitor = _competitor()
    assert apify_tiktok.scrape_tiktok_for_competitor(competitor) == []


def test_tiktok_handle_normalization():
    assert apify_tiktok._normalize_handle("@brand") == "brand"
    assert apify_tiktok._normalize_handle("brand") == "brand"
    assert apify_tiktok._normalize_handle("https://tiktok.com/@brand") == "brand"


# ─── TikTok UGC search ──────────────────────────────────────────────────────


def test_tiktok_search_returns_video_metadata(monkeypatch: pytest.MonkeyPatch):
    """search_tiktok_videos calls the search actor and returns the same shape
    as profile-based discovery so downstream consumers don't need to branch."""
    fake = _FakeApifyClient(
        actor_datasets={apify_tiktok.SEARCH_ACTOR_ID: "ds-search"},
        datasets={
            "ds-search": [
                {
                    "id": "vid-1",
                    "webVideoUrl": "https://www.tiktok.com/@reviewer/video/vid-1",
                    "text": "Arrae review — does it actually work?",
                    "playCount": 50000,
                    "diggCount": 1200,
                    "commentCount": 88,
                },
                {
                    "id": "vid-2",
                    "webVideoUrl": "https://www.tiktok.com/@critic/video/vid-2",
                    "text": "Honest Arrae review after 30 days",
                },
            ],
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    videos = apify_tiktok.search_tiktok_videos("arrae review", max_videos=5)
    assert len(videos) == 2
    assert videos[0]["url"].endswith("/vid-1")
    assert "Arrae review" in videos[0]["caption"]
    assert videos[0]["metrics"]["diggs"] == 1200
    assert videos[0]["discovered_via"] == "search:arrae review"


def test_tiktok_search_used_as_third_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    """When a competitor has no post_urls and no handle, search_queries kick
    in. The search actor is called once per query, then comments are scraped
    on the resulting URLs."""
    monkeypatch.chdir(tmp_path)
    fake = _FakeApifyClient(
        actor_datasets={
            apify_tiktok.SEARCH_ACTOR_ID: "ds-search",
            apify_tiktok.COMMENTS_ACTOR_ID: "ds-comments",
        },
        datasets={
            "ds-search": [
                {
                    "id": "ugc-1",
                    "webVideoUrl": "https://www.tiktok.com/@a/video/ugc-1",
                    "text": "Arrae review",
                },
            ],
            "ds-comments": [
                {"cid": "c1", "text": "actually worked for me", "uniqueId": "u1", "diggCount": 9},
            ],
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    competitor = _competitor(tiktok_search_queries=["arrae review"])
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)
    assert len(bundles) == 1
    assert bundles[0].comments[0].text == "actually worked for me"


def test_tiktok_search_dedupes_videos_across_queries(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    """Two queries surfacing the same video shouldn't get scraped twice."""
    monkeypatch.chdir(tmp_path)
    # Both searches return the same video (7000000000000000001).
    fake = _FakeApifyClient(
        actor_datasets={
            apify_tiktok.SEARCH_ACTOR_ID: "ds-search",
            apify_tiktok.COMMENTS_ACTOR_ID: "ds-comments",
        },
        datasets={
            "ds-search": [
                {
                    "id": "7000000000000000001",
                    "webVideoUrl": "https://www.tiktok.com/@a/video/7000000000000000001",
                    "text": "review",
                },
            ],
            "ds-comments": [
                {"cid": "c1", "text": "comment", "uniqueId": "u1", "diggCount": 1},
            ],
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    competitor = _competitor(
        tiktok_search_queries=["arrae review", "arrae honest"],
    )
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)
    # Two queries × same video → still only one bundle.
    assert len(bundles) == 1
    assert bundles[0].post_id == "7000000000000000001"


def test_tiktok_priority_order_post_urls_beats_search(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
):
    """When both post_urls and search_queries are set, post_urls wins —
    no search actor call happens."""
    monkeypatch.chdir(tmp_path)
    search_called = {"count": 0}

    def _search_spy(query, max_videos):
        search_called["count"] += 1
        return []

    fake = _FakeApifyClient(
        actor_datasets={apify_tiktok.COMMENTS_ACTOR_ID: "ds-comments"},
        datasets={
            "ds-comments": [
                {"cid": "c1", "text": "from explicit post", "uniqueId": "u1", "diggCount": 5},
            ],
        },
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)
    monkeypatch.setattr(apify_tiktok, "search_tiktok_videos", _search_spy)

    competitor = _competitor(
        tiktok_post_urls=["https://www.tiktok.com/@a/video/exp-1"],
        tiktok_search_queries=["should not be used"],
    )
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)
    assert len(bundles) == 1
    assert search_called["count"] == 0  # search was never invoked


# ─── Instagram scraper ──────────────────────────────────────────────────────


def test_instagram_scrapes_from_explicit_post_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(tmp_path)
    fake = _FakeApifyClient(
        actor_datasets={apify_instagram.COMMENTS_ACTOR_ID: "ds-comments"},
        datasets={
            "ds-comments": [
                {
                    "id": "ig-c1",
                    "text": "wish this didn't smell beefy",
                    "ownerUsername": "user_a",
                    "likesCount": 15,
                    "repliesCount": 2,
                    "timestamp": "2026-05-01T00:00:00Z",
                },
            ]
        },
    )
    monkeypatch.setattr(apify_instagram, "_get_client", lambda: fake)

    competitor = _competitor(instagram_post_urls=["https://www.instagram.com/p/CXxXxXxXxXX/"])
    bundles = apify_instagram.scrape_instagram_for_competitor(competitor)
    assert len(bundles) == 1
    assert bundles[0].post_id == "CXxXxXxXxXX"
    assert bundles[0].comments[0].text == "wish this didn't smell beefy"
    assert bundles[0].comments[0].likes == 15


def test_instagram_handle_normalization():
    assert apify_instagram._normalize_handle("@brand") == "brand"
    assert apify_instagram._normalize_handle("brand") == "brand"
    assert apify_instagram._normalize_handle("https://instagram.com/brand/") == "brand"


# ─── YouTube comments ──────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


class _FakeHttpxClient:
    def __init__(self, route_responses: dict[str, list[_FakeResponse]]):
        # Each endpoint key maps to an in-order queue of responses (for pagination).
        self._routes = route_responses

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, params=None, **_):
        for key, queue in self._routes.items():
            if key in url and queue:
                return queue.pop(0)
        return _FakeResponse(404, {"error": f"no fake for {url}"})


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, route_responses: dict[str, list[_FakeResponse]]):
    fake = _FakeHttpxClient(route_responses)
    monkeypatch.setattr(youtube_comments.httpx, "Client", lambda timeout=None: fake)


def test_youtube_resolves_handle_to_channel_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")
    _patch_httpx(monkeypatch, {
        "/channels": [_FakeResponse(200, {"items": [{"id": "UCabc123"}]})],
    })
    assert youtube_comments.resolve_handle_to_channel_id("@rivalco") == "UCabc123"


def test_youtube_fetch_comments_paginates(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")

    def _comment_item(cid, text, likes):
        return {
            "id": cid,
            "snippet": {
                "topLevelComment": {
                    "snippet": {
                        "textDisplay": text,
                        "authorDisplayName": f"author_{cid}",
                        "likeCount": likes,
                        "publishedAt": "2026-05-01T00:00:00Z",
                    },
                },
                "totalReplyCount": 0,
            },
        }

    page_1 = _FakeResponse(200, {
        "items": [_comment_item("c1", "no real change after 2 months", 12)],
        "nextPageToken": "next-token",
    })
    page_2 = _FakeResponse(200, {
        "items": [_comment_item("c2", "smells like a steakhouse", 88)],
    })
    _patch_httpx(monkeypatch, {"/commentThreads": [page_1, page_2]})

    bundle = youtube_comments.fetch_comments_for_video(
        "vid-1", competitor_slug="rivalco", competitor_name="RivalCo",
        max_comments=200,
    )
    assert len(bundle.comments) == 2
    assert bundle.comments[1].text == "smells like a steakhouse"
    assert bundle.comments[1].likes == 88
    assert bundle.notes == ""


def test_youtube_handles_comments_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")
    _patch_httpx(monkeypatch, {
        "/commentThreads": [_FakeResponse(403, {"error": {"message": "commentsDisabled"}})],
    })
    bundle = youtube_comments.fetch_comments_for_video(
        "vid-1", competitor_slug="rivalco", competitor_name="RivalCo",
    )
    assert bundle.comments == []
    assert "403" in bundle.notes


def test_youtube_missing_api_key_raises():
    # Make sure stale env from other tests doesn't shadow this assertion.
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(youtube_comments.YouTubeAuthError):
            youtube_comments.resolve_handle_to_channel_id("@brand")


def test_youtube_handle_normalization():
    assert youtube_comments._normalize_handle("@brand") == "@brand"
    assert youtube_comments._normalize_handle("brand") == "@brand"
    assert youtube_comments._normalize_handle("youtube.com/@brand") == "@brand"


# ─── CLI registration smoke ────────────────────────────────────────────────


def test_research_social_command_registered():
    """Verify the CLI command is wired so future regressions break loudly."""
    from cli import cli as cli_group
    assert "research-social" in cli_group.commands


# ─── End-to-end: cache → voc-dump → ready for voc_miner ────────────────────


def test_e2e_tiktok_dump_is_voc_miner_compatible(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """The voc dump must be a list[dict] with body/rating fields — the exact
    shape voc_miner.load_reviews_from_file expects."""
    monkeypatch.chdir(tmp_path)
    fake = _FakeApifyClient(
        actor_datasets={apify_tiktok.COMMENTS_ACTOR_ID: "ds-1"},
        datasets={"ds-1": [
            {"cid": "c1", "text": "no signal", "uniqueId": "u1", "diggCount": 3},
            {"cid": "c2", "text": "BIG signal", "uniqueId": "u2", "diggCount": 999},
        ]},
    )
    monkeypatch.setattr(apify_tiktok, "_get_client", lambda: fake)

    competitor = _competitor(
        tiktok_post_urls=["https://www.tiktok.com/@rivalco/video/9999"],
    )
    bundles = apify_tiktok.scrape_tiktok_for_competitor(competitor)
    for b in bundles:
        cache_bundle("demo", b)

    out = write_voc_dump("demo", "tiktok")
    assert out is not None
    assert out.name == "tiktok-comments.json"

    # Verify the dump shape matches what voc_miner.load_reviews_from_file expects.
    # That function does: data = json.load(f); for r in data: r.get("rating"), r.get("body")
    # We don't import voc_miner here because its module-level system prompt
    # eagerly loads a skill file that doesn't exist in tmp_path.
    records = json.loads(out.read_text(encoding="utf-8"))
    assert isinstance(records, list)
    assert all(isinstance(r, dict) for r in records)
    assert all("body" in r and "rating" in r for r in records)
    bodies = [r["body"] for r in records]
    assert bodies == ["BIG signal", "no signal"]  # likes-sorted
    assert all(r["rating"] == "N/A" for r in records)
