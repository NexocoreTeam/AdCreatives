"""Tests for strategy/gap_analyzer.py — focused on the Tier 3 social-comment
integration since the rest of the module is exercised end-to-end by the
analyze-gaps CLI command.

We test `_gather_brand_content` directly so no LLM call is required. The test
fixtures are SocialCommentBundle objects (deterministic, no scraping).
"""

from __future__ import annotations

from strategy.gap_analyzer import (
    MAX_SOCIAL_COMMENTS_PER_PLATFORM,
    _gather_brand_content,
)
from strategy.social_comments import SocialComment, SocialCommentBundle

# ─── Fixtures ───────────────────────────────────────────────────────────────


def _make_comment(
    platform: str,
    text: str,
    likes: int = 0,
    reply_count: int = 0,
    author: str = "tester",
) -> SocialComment:
    return SocialComment(
        platform=platform,
        text=text,
        likes=likes,
        reply_count=reply_count,
        author=author,
    )


def _make_bundle(
    platform: str,
    competitor_slug: str,
    comments: list[SocialComment],
) -> SocialCommentBundle:
    return SocialCommentBundle(
        platform=platform,
        competitor_slug=competitor_slug,
        competitor_name=competitor_slug.title(),
        post_id=f"{competitor_slug}-post-1",
        post_url=f"https://example.com/{platform}/{competitor_slug}",
        comments=comments,
    )


# ─── Tests ──────────────────────────────────────────────────────────────────


def test_gather_brand_content_with_no_social_returns_empty_content():
    """Backwards compatible — calling without social_bundles produces no content."""
    content, meta = _gather_brand_content(
        brand_name="DemoCo", exa_results=[],
    )
    assert content == ""
    assert meta["tiktok_comments"] == 0
    assert meta["instagram_comments"] == 0
    assert meta["youtube_comments"] == 0


def test_gather_brand_content_includes_tiktok_comments():
    """A single TikTok bundle's comments appear in the content + meta."""
    bundle = _make_bundle(
        platform="tiktok",
        competitor_slug="arrae",
        comments=[
            _make_comment("tiktok", "this gave me cystic acne", likes=42),
            _make_comment("tiktok", "love the formula", likes=12),
        ],
    )
    content, meta = _gather_brand_content(
        brand_name="Arrae", exa_results=[], social_bundles=[bundle],
    )
    assert "TIKTOK COMMENT" in content
    assert "cystic acne" in content
    assert "love the formula" in content
    assert meta["tiktok_comments"] == 2
    assert "tiktok_comments" in meta["sources"]


def test_gather_brand_content_sorts_comments_by_likes_desc():
    """High-engagement comments survive the per-platform cap."""
    high = _make_comment("tiktok", "HIGH SIGNAL", likes=999)
    low = _make_comment("tiktok", "low signal", likes=1)
    bundle = _make_bundle(
        platform="tiktok",
        competitor_slug="arrae",
        comments=[low, high],  # intentionally inserted out of order
    )
    content, _ = _gather_brand_content(
        brand_name="Arrae", exa_results=[], social_bundles=[bundle],
    )
    # The HIGH SIGNAL comment must appear BEFORE the low-signal one
    assert content.index("HIGH SIGNAL") < content.index("low signal")


def test_gather_brand_content_caps_per_platform():
    """Per-platform sample is bounded — overflow is dropped, not truncated mid-comment."""
    over_limit = [
        _make_comment("tiktok", f"comment {i}", likes=i)
        for i in range(MAX_SOCIAL_COMMENTS_PER_PLATFORM + 20)
    ]
    bundle = _make_bundle(
        platform="tiktok", competitor_slug="arrae", comments=over_limit,
    )
    _content, meta = _gather_brand_content(
        brand_name="Arrae", exa_results=[], social_bundles=[bundle],
    )
    assert meta["tiktok_comments"] == MAX_SOCIAL_COMMENTS_PER_PLATFORM


def test_gather_brand_content_handles_multiple_platforms_independently():
    """Three platforms each get their own cap; one quiet platform doesn't starve the others."""
    tiktok = _make_bundle(
        "tiktok", "arrae", [_make_comment("tiktok", "tt", likes=10) for _ in range(50)],
    )
    instagram = _make_bundle(
        "instagram", "arrae", [_make_comment("instagram", "ig", likes=5) for _ in range(3)],
    )
    youtube = _make_bundle(
        "youtube", "arrae", [_make_comment("youtube", "yt", likes=2) for _ in range(1)],
    )
    content, meta = _gather_brand_content(
        brand_name="Arrae",
        exa_results=[],
        social_bundles=[tiktok, instagram, youtube],
    )
    assert meta["tiktok_comments"] == MAX_SOCIAL_COMMENTS_PER_PLATFORM  # capped
    assert meta["instagram_comments"] == 3
    assert meta["youtube_comments"] == 1
    assert "TIKTOK COMMENT" in content
    assert "INSTAGRAM COMMENT" in content
    assert "YOUTUBE COMMENT" in content
    # All three platforms register in sources
    assert {"tiktok_comments", "instagram_comments", "youtube_comments"}.issubset(
        meta["sources"],
    )


def test_gather_brand_content_skips_empty_bundles():
    """A bundle with zero comments doesn't pollute the content string or sources."""
    empty = _make_bundle("tiktok", "arrae", comments=[])
    _content, meta = _gather_brand_content(
        brand_name="Arrae", exa_results=[], social_bundles=[empty],
    )
    assert meta["tiktok_comments"] == 0
    assert "tiktok_comments" not in meta["sources"]


def test_gather_brand_content_combines_social_with_other_sources():
    """Social comments concatenate alongside existing review sources, not replace."""
    from strategy.apify_amazon import AmazonReviewBundle
    from strategy.reviews import Review
    amazon_bundle = AmazonReviewBundle(
        product_url="https://amazon.com/x",
        competitor_slug="arrae",
        competitor_name="Arrae",
        asin="B000ABC123",
        product_title="Arrae Bloat",
        reviews=[
            Review(
                title="works",
                body="my bloat is gone",
                rating=5,
                reviewer="u1",
                date="",
                product_id="B000ABC123",
            ),
        ],
    )
    social = _make_bundle(
        "tiktok", "arrae",
        [_make_comment("tiktok", "this gave me acne", likes=10)],
    )
    content, meta = _gather_brand_content(
        brand_name="Arrae",
        exa_results=[],
        amazon_bundles=[amazon_bundle],
        social_bundles=[social],
    )
    assert "AMAZON REVIEW" in content
    assert "my bloat is gone" in content
    assert "TIKTOK COMMENT" in content
    assert "this gave me acne" in content
    assert meta["amazon_reviews"] == 1
    assert meta["tiktok_comments"] == 1
    assert "amazon" in meta["sources"]
    assert "tiktok_comments" in meta["sources"]
