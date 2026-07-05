from types import SimpleNamespace

import strategy.youtube_comments as yt
from strategy.social_comments import SocialCommentBundle


def _competitor(**overrides):
    base = dict(
        name="Stumptown Coffee Roasters",
        slug="stumptown",
        youtube_video_ids=[],
        youtube_search_queries=[],
        youtube_channel_id="",
        youtube_handle="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _bundle_for(video_id: str) -> SocialCommentBundle:
    return SocialCommentBundle(platform="youtube", post_id=video_id)


def test_search_queries_discover_videos(monkeypatch):
    searched: list[str] = []

    def fake_search(query, max_videos):
        searched.append(query)
        return [
            {"video_id": "vid1", "title": "Stumptown review", "url": "u1"},
            {"video_id": "vid2", "title": "Stumptown vs Onyx", "url": "u2"},
            {"video_id": "vid1", "title": "dup", "url": "u1"},  # dedupe check
        ]

    monkeypatch.setattr(yt, "search_videos", fake_search)
    monkeypatch.setattr(
        yt, "fetch_comments_for_video",
        lambda video_id, **kwargs: _bundle_for(video_id),
    )

    competitor = _competitor(youtube_search_queries=["stumptown coffee review"])
    bundles = yt.fetch_youtube_for_competitor(competitor, max_videos_per_channel=8)

    assert searched == ["stumptown coffee review"]
    assert [b.post_id for b in bundles] == ["vid1", "vid2"]


def test_search_total_capped_across_queries(monkeypatch):
    def fake_search(query, max_videos):
        return [
            {"video_id": f"{query}-{i}", "title": "", "url": ""}
            for i in range(max_videos)
        ]

    monkeypatch.setattr(yt, "search_videos", fake_search)
    monkeypatch.setattr(
        yt, "fetch_comments_for_video",
        lambda video_id, **kwargs: _bundle_for(video_id),
    )

    competitor = _competitor(youtube_search_queries=["q1", "q2", "q3"])
    bundles = yt.fetch_youtube_for_competitor(competitor, max_videos_per_channel=4)
    assert len(bundles) == 4


def test_explicit_video_ids_win_over_search(monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("search_videos must not be called when video IDs are set")

    monkeypatch.setattr(yt, "search_videos", explode)
    monkeypatch.setattr(
        yt, "fetch_comments_for_video",
        lambda video_id, **kwargs: _bundle_for(video_id),
    )

    competitor = _competitor(
        youtube_video_ids=["explicit1"],
        youtube_search_queries=["should not run"],
    )
    bundles = yt.fetch_youtube_for_competitor(competitor)
    assert [b.post_id for b in bundles] == ["explicit1"]


def test_no_sources_returns_empty():
    assert yt.fetch_youtube_for_competitor(_competitor()) == []


def test_unresolved_handle_raises_diagnosable_error(monkeypatch):
    """'status: ok, 0 comments' told the Zoka run nothing — a dead handle
    must say so."""
    monkeypatch.setattr(yt, "resolve_handle_to_channel_id", lambda h: "")
    competitor = _competitor(youtube_handle="@doesnotexist")
    try:
        yt.fetch_youtube_for_competitor(competitor)
        raise AssertionError("expected YouTubeSourceEmpty")
    except yt.YouTubeSourceEmpty as e:
        assert "@doesnotexist" in str(e)


def test_dry_search_raises_diagnosable_error(monkeypatch):
    monkeypatch.setattr(yt, "search_videos", lambda q, max_videos: [])
    competitor = _competitor(youtube_search_queries=["obscure query"])
    try:
        yt.fetch_youtube_for_competitor(competitor)
        raise AssertionError("expected YouTubeSourceEmpty")
    except yt.YouTubeSourceEmpty as e:
        assert "obscure query" in str(e)
