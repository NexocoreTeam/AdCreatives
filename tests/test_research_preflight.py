from strategy.competitor_research import Competitor
from strategy.research_preflight import (
    amazon_preflight_line,
    grade_social_sources,
    social_preflight_lines,
)


def _competitor(**overrides):
    base = dict(name="Stumptown", slug="stumptown", url="https://x.com")
    base.update(overrides)
    return Competitor(**base)


def test_search_queries_grade_strong():
    grades = grade_social_sources([
        _competitor(youtube_search_queries=["stumptown review"]),
    ])
    youtube = next(g for g in grades if g.platform == "youtube")
    assert youtube.grade == "strong"


def test_handles_only_grade_weak():
    grades = grade_social_sources([
        _competitor(youtube_handle="@stumptowncoffee", tiktok_handle="@stumptown"),
    ])
    assert {g.grade for g in grades if g.platform in ("youtube", "tiktok")} == {"weak"}


def test_verdict_low_when_no_strong_sources():
    lines = social_preflight_lines(
        [_competitor(youtube_handle="@stumptowncoffee")], "zoka-coffee"
    )
    assert any("expected yield LOW" in line for line in lines)
    assert any("scaffold-competitors" in line for line in lines)


def test_verdict_ok_when_strong_present():
    lines = social_preflight_lines(
        [_competitor(youtube_search_queries=["stumptown review"])], "zoka-coffee"
    )
    assert any(line.startswith("VERDICT: OK") for line in lines)


def test_verdict_nothing_configured():
    lines = social_preflight_lines([_competitor()], "zoka-coffee")
    assert any("nothing configured" in line for line in lines)


def test_amazon_preflight_lines():
    no_urls = amazon_preflight_line([_competitor()], "zoka-coffee")
    assert "suggest-amazon" in no_urls
    with_urls = amazon_preflight_line(
        [_competitor(amazon_urls=["https://www.amazon.com/dp/B000TEST12"])],
        "zoka-coffee",
    )
    assert "1/1" in with_urls


def test_homepage_preflight_flags_blank_urls():
    from strategy.research_preflight import homepage_preflight_line

    warn = homepage_preflight_line(
        [_competitor(url=""), _competitor(name="Onyx", url="https://x.com")],
        "expand-furniture",
    )
    assert warn is not None
    assert "1 competitor(s) have no url" in warn
    assert "Stumptown" in warn

    assert homepage_preflight_line([_competitor(url="https://x.com")], "c") is None
