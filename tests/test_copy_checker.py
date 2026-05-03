"""Tests for validators/copy_checker.py — platform char limits for ad copy."""

from __future__ import annotations

import pytest

from validators.copy_checker import (
    PLATFORM_LIMITS,
    CopyCheck,
    Severity,
    check_copy,
    list_platforms,
    list_fields,
    suggest_trim,
)


class TestPlatformLimitsTable:
    def test_meta_has_primary_text_headline_description(self):
        assert "primary_text" in PLATFORM_LIMITS["meta"]
        assert "headline" in PLATFORM_LIMITS["meta"]
        assert "description" in PLATFORM_LIMITS["meta"]

    def test_google_rsa_headline_is_30(self):
        assert PLATFORM_LIMITS["google"]["headline"]["recommended"] == 30

    def test_meta_primary_text_visible_125(self):
        assert PLATFORM_LIMITS["meta"]["primary_text"]["recommended"] == 125

    def test_tiktok_ad_text_recommended_80(self):
        assert PLATFORM_LIMITS["tiktok"]["ad_text"]["recommended"] == 80

    def test_x_tweet_text_280(self):
        assert PLATFORM_LIMITS["x"]["tweet_text"]["recommended"] == 280

    def test_linkedin_intro_text_150(self):
        assert PLATFORM_LIMITS["linkedin"]["intro_text"]["recommended"] == 150


class TestCheckCopy:
    def test_passes_when_under_recommended(self):
        result = check_copy("Buy our thing", platform="meta", field="headline")
        assert result.passed
        assert result.severity == Severity.OK
        assert result.length == len("Buy our thing")

    def test_warns_when_between_recommended_and_max(self):
        text = "x" * 150
        result = check_copy(text, platform="meta", field="primary_text")
        assert not result.passed
        assert result.severity == Severity.WARNING
        assert "exceeds recommended" in result.detail

    def test_fails_when_over_hard_max(self):
        text = "x" * 250
        result = check_copy(text, platform="meta", field="headline")
        assert not result.passed
        assert result.severity == Severity.ERROR
        assert "over hard max" in result.detail or "exceeds" in result.detail

    def test_fails_when_no_max_and_over_recommended_for_strict_field(self):
        text = "x" * 35
        result = check_copy(text, platform="google", field="headline")
        assert not result.passed
        assert result.severity == Severity.ERROR

    def test_unknown_platform_raises(self):
        with pytest.raises(ValueError, match="unknown platform"):
            check_copy("hi", platform="myspace", field="headline")

    def test_unknown_field_raises(self):
        with pytest.raises(ValueError, match="unknown field"):
            check_copy("hi", platform="meta", field="banana")

    def test_field_with_only_recommended_treats_recommended_as_hard_limit(self):
        text = "x" * 31
        result = check_copy(text, platform="google", field="headline")
        assert not result.passed
        assert result.severity == Severity.ERROR


class TestSuggestTrim:
    def test_returns_text_unchanged_when_within_limit(self):
        text = "Short copy"
        assert suggest_trim(text, target=125) == text

    def test_trims_to_target_length_with_ellipsis(self):
        text = "x" * 200
        trimmed = suggest_trim(text, target=125)
        assert len(trimmed) <= 125
        assert trimmed.endswith("…") or trimmed.endswith("...")

    def test_trims_at_word_boundary_when_possible(self):
        text = "This is a longer sentence that needs to be trimmed at a word boundary"
        trimmed = suggest_trim(text, target=30)
        assert len(trimmed) <= 30
        assert " " not in trimmed[-2:]


class TestListing:
    def test_list_platforms_includes_all_five(self):
        platforms = set(list_platforms())
        assert {"meta", "google", "tiktok", "linkedin", "x"}.issubset(platforms)

    def test_list_fields_for_meta(self):
        fields = set(list_fields("meta"))
        assert {"primary_text", "headline", "description"}.issubset(fields)

    def test_list_fields_unknown_platform_raises(self):
        with pytest.raises(ValueError):
            list_fields("myspace")


class TestCopyCheckDataclass:
    def test_check_has_all_fields(self):
        c = CopyCheck(
            platform="meta",
            field="headline",
            text="hi",
            length=2,
            recommended=40,
            hard_max=None,
            passed=True,
            severity=Severity.OK,
            detail="ok",
        )
        assert c.platform == "meta"
        assert c.length == 2
        assert c.passed is True
