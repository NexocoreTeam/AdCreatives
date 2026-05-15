"""Tests for strategy/naming.py — Meta ad campaign name builder.

LLM-driven matching is not tested here (no Claude call in this module).
Tests focus on slot builders, mapping tables, fallback codes, fuzzy hook
matching against a fixture library, and the full taxonomy assembly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import yaml

from models.avatar import CustomerAvatar
from models.brand import (
    AudienceProfile,
    Brand,
    ColorPalette,
)
from models.brief import (
    AwarenessLevel,
    CopyFramework,
    CreativeBrief,
)
from strategy.naming import (
    AD_TYPE_TO_ANGLE,
    HOOK_TYPE_TO_CANDIDATES,
    _angle_code,
    _brand_code,
    _camel_case,
    _date_code,
    _format_code,
    _hook_code,
    _hook_text_similarity,
    _iteration_code,
    _load_hook_library,
    _offer_code,
    _persona_code,
    _source_code,
    _style_code,
    build_campaign_name,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _brand(code: str = "SK", name: str = "SecondKind") -> Brand:
    return Brand(
        name=name,
        code=code,
        colors=ColorPalette(primary="#2B2B2B", accent="#FFD700"),
        audience=AudienceProfile(age_range="28-45"),
        tone="credible, science-forward",
    )


def _brief(
    *,
    persona: str = "Probiotic-Burned Paige",
    hook: str = "I tried probiotics for years and it never worked",
    hook_type: str = "Surprising Stat",
    hook_tactic: str = "Specific stat with a story",
    creative_mechanic: str = "Venn Diagram Whiteboard",
    visual_format: str = "Text-on-product photo",
) -> CreativeBrief:
    return CreativeBrief(
        brief_id="test-brief-001",
        client="secondkind",
        product="Gut Balance",
        awareness_level=AwarenessLevel.PROBLEM_AWARE,
        framework=CopyFramework.BAB,
        angle="postbiotic mechanism",
        hook=hook,
        hook_type=hook_type,
        hook_tactic=hook_tactic,
        persona=persona,
        creative_mechanic=creative_mechanic,
        visual_format=visual_format,
    )


def _hook_library_fixture(tmp_path: Path) -> Path:
    """Mini hook library — 5 entries covering the matching paths."""
    data = {
        "hooks": [
            {
                "code": "H01",
                "text": "I tried [product] for 30 days and here's what happened…",
                "tactic_type": "Curiosity / Time-Bound",
                "original_angle": "Education",
                "status": "Active",
                "date_added": "2026-05-15",
            },
            {
                "code": "H05",
                "text": "Stop scrolling — this is what saved my [pain point].",
                "tactic_type": "Pattern Interrupt",
                "original_angle": "PainPoint",
                "status": "Active",
                "date_added": "2026-05-15",
            },
            {
                "code": "H07",
                "text": "[Specific number] of [people] can't be wrong.",
                "tactic_type": "Social Proof / Numbers",
                "original_angle": "SocialProof",
                "status": "Active",
                "date_added": "2026-05-15",
            },
            {
                "code": "H12",
                "text": "[Old approach] = hoping it works. [New approach] = it already did.",
                "tactic_type": "Mechanism Contrast",
                "original_angle": "Mechanism",
                "status": "Active",
                "date_added": "2026-05-15",
            },
            {
                "code": "H16",
                "text": "[Specific %] of [body fact] is [counterintuitive truth].",
                "tactic_type": "Educational Stat",
                "original_angle": "Education",
                "status": "Active",
                "date_added": "2026-05-15",
            },
        ]
    }
    path = tmp_path / "hook_library.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# ─── Slot builders ──────────────────────────────────────────────────────────


class TestCamelCase:
    def test_multi_word_with_hyphen(self):
        assert _camel_case("Probiotic-Burned Paige") == "ProbioticBurnedPaige"

    def test_lowercase(self):
        assert _camel_case("busy mom") == "BusyMom"

    def test_preserves_internal_caps(self):
        # e.g. brand names like iPhone, McDonald
        assert _camel_case("iPhone Mom") == "iPhoneMom"

    def test_strips_punctuation(self):
        assert _camel_case("Mom (CEO)") == "Mom"

    def test_caps_max_chars(self):
        long = "a" * 50 + " b"
        result = _camel_case(long, max_chars=20)
        assert len(result) <= 20

    def test_empty_returns_unknown(self):
        assert _camel_case("") == ""
        assert _camel_case("!!!") == "Unknown"


class TestBrandCode:
    def test_valid_code(self):
        b = _brand(code="SK")
        assert _brand_code(b) == "SK"

    def test_sanitizes_punctuation(self):
        b = _brand(code="S-K!")
        assert _brand_code(b) == "SK"

    def test_missing_code_raises(self):
        b = _brand(code="")
        with pytest.raises(ValueError, match="no 'code' field"):
            _brand_code(b)

    def test_punctuation_only_raises(self):
        b = _brand(code="!!!")
        with pytest.raises(ValueError, match="no alphanumeric"):
            _brand_code(b)


class TestPersonaCode:
    def test_camelcases(self):
        b = _brief(persona="Probiotic-Burned Paige")
        assert _persona_code(b) == "ProbioticBurnedPaige"

    def test_empty_persona_falls_to_na(self):
        b = _brief(persona="")
        assert _persona_code(b) == "NA"


class TestAngleCode:
    def test_from_analysis_ad_type(self):
        b = _brief()
        # mock-like minimal: just provide the ad_type
        class _A:
            ad_type = "us-vs-them"
        assert _angle_code(b, _A()) == AD_TYPE_TO_ANGLE["us-vs-them"]

    def test_unknown_ad_type_falls_to_brief(self):
        b = _brief(hook_tactic="Specific stat with a story")
        class _A:
            ad_type = "made_up"
        assert _angle_code(b, _A()) == "Stats"

    def test_falls_back_to_mixed_when_nothing(self):
        b = _brief(hook_tactic="")
        assert _angle_code(b, None) == "Mixed"


class TestFormatCode:
    def test_static_default(self):
        b = _brief(creative_mechanic="", visual_format="")
        assert _format_code(b, None) == "Static"

    def test_ugc_substring(self):
        b = _brief(visual_format="UGC static")
        assert _format_code(b, None) == "UGC"

    def test_text_on_product_means_static(self):
        b = _brief(visual_format="Text-on-product photo")
        assert _format_code(b, None) == "Static"


class TestStyleCode:
    def test_venn_match(self):
        b = _brief(creative_mechanic="Venn Diagram Whiteboard")
        assert _style_code(b, None) == "Venn"

    def test_split_screen(self):
        b = _brief(creative_mechanic="Split-screen comparison")
        assert _style_code(b, None) == "SplitScreen"

    def test_default_mixed_when_no_match(self):
        b = _brief(creative_mechanic="some weird mechanic", visual_format="")
        assert _style_code(b, None) == "Mixed"


class TestSourceCode:
    def test_valid_remix(self):
        assert _source_code("Remix") == "Remix"

    def test_valid_ai_case_insensitive(self):
        assert _source_code("ai") == "AI"
        assert _source_code("AI") == "AI"

    def test_empty_falls_to_na(self):
        assert _source_code("") == "NA"

    def test_unknown_falls_to_na(self):
        assert _source_code("Foreplay") == "NA"


class TestOfferCode:
    def test_default_none_for_empty(self):
        assert _offer_code("") == "NONE"
        assert _offer_code("   ") == "NONE"
        assert _offer_code(None) == "NONE"  # type: ignore[arg-type]

    def test_uppercase_and_sanitize(self):
        assert _offer_code("freeship") == "FREESHIP"
        assert _offer_code("BF-CM25!") == "BFCM25"

    def test_caps_at_12_chars(self):
        assert len(_offer_code("a" * 20)) == 12


class TestIterationCode:
    def test_int_input(self):
        assert _iteration_code(1) == "V1"
        assert _iteration_code(3) == "V3"

    def test_string_with_v_prefix(self):
        assert _iteration_code("V2") == "V2"
        assert _iteration_code("v3") == "V3"

    def test_string_numeric(self):
        assert _iteration_code("4") == "V4"

    def test_invalid_falls_to_v1(self):
        assert _iteration_code("abc") == "V1"
        assert _iteration_code(None) == "V1"


class TestDateCode:
    def test_default_today_format(self):
        result = _date_code(None)
        assert len(result) == 6
        assert result.isdigit()

    def test_explicit_datetime(self):
        dt = datetime(2026, 5, 15)
        assert _date_code(dt) == "260515"

    def test_iso_string(self):
        assert _date_code("2026-05-15") == "260515"

    def test_remix_timestamp_format(self):
        assert _date_code("2026-05-15_193045") == "260515"


# ─── Hook fuzzy matching ────────────────────────────────────────────────────


class TestHookTextSimilarity:
    def test_identical_text_high_similarity(self):
        score = _hook_text_similarity(
            "I tried probiotics for years and nothing worked",
            "I tried probiotics for years and nothing worked",
        )
        assert score == 1.0

    def test_no_overlap_zero(self):
        score = _hook_text_similarity(
            "abc xyz qqq",
            "totally different content here",
        )
        assert score == 0.0

    def test_partial_overlap(self):
        score = _hook_text_similarity(
            "I tried [product] for 30 days and here's what happened",
            "I tried probiotics for 30 days and nothing happened",
        )
        # Should have meaningful overlap
        assert 0.2 < score < 1.0


class TestHookCode:
    def test_returns_h00_for_empty_library(self, tmp_path):
        b = _brief(hook="anything")
        # Use empty library
        empty_path = tmp_path / "empty.yaml"
        empty_path.write_text("hooks: []", encoding="utf-8")
        assert _hook_code(b, library_path=empty_path) == "H00"

    def test_returns_h00_for_empty_hook(self, tmp_path):
        b = _brief(hook="")
        path = _hook_library_fixture(tmp_path)
        assert _hook_code(b, library_path=path) == "H00"

    def test_text_match_wins(self, tmp_path):
        # Brief hook closely matches H01 in library
        b = _brief(
            hook="I tried probiotics for 30 days and here's what happened",
            hook_type="Curiosity Gap",
        )
        path = _hook_library_fixture(tmp_path)
        assert _hook_code(b, library_path=path) == "H01"

    def test_falls_back_to_hook_type_candidate(self, tmp_path):
        # Hook text far from library, but hook_type 'Surprising Stat'
        # candidates include H16, H07
        b = _brief(
            hook="Different unrelated text completely",
            hook_type="Surprising Stat",
        )
        path = _hook_library_fixture(tmp_path)
        result = _hook_code(b, library_path=path, text_match_threshold=0.99)
        assert result in ("H16", "H07")  # both in library

    def test_unknown_type_returns_h00(self, tmp_path):
        b = _brief(
            hook="Completely unrelated text here",
            hook_type="Made-up Type That Doesn't Exist",
        )
        path = _hook_library_fixture(tmp_path)
        assert _hook_code(b, library_path=path, text_match_threshold=0.99) == "H00"


class TestLoadHookLibrary:
    def test_loads_full_library(self, tmp_path):
        path = _hook_library_fixture(tmp_path)
        lib = _load_hook_library(library_path=path)
        assert len(lib) == 5
        assert lib[0]["code"] == "H01"

    def test_missing_file_returns_empty(self, tmp_path):
        lib = _load_hook_library(library_path=tmp_path / "nonexistent.yaml")
        assert lib == []

    def test_malformed_yaml_returns_empty(self, tmp_path):
        path = tmp_path / "broken.yaml"
        path.write_text("not: valid: yaml: ::", encoding="utf-8")
        assert _load_hook_library(library_path=path) == []


# ─── End-to-end builder ─────────────────────────────────────────────────────


class TestBuildCampaignName:
    def test_full_taxonomy_assembly(self, tmp_path):
        b = _brand(code="SK")
        brief = _brief(
            persona="Probiotic-Burned Paige",
            hook="I tried probiotics for 30 days",
            hook_type="Curiosity Gap",
            creative_mechanic="Venn Diagram Whiteboard",
            visual_format="Text-on-product photo",
        )

        class _A:
            ad_type = "testimonial-review"
            creative_mechanic = "Venn Diagram Whiteboard"
            visual_format = "Text-on-product photo"

        path = _hook_library_fixture(tmp_path)
        name = build_campaign_name(
            brief,
            b,
            analysis=_A(),
            offer="FREESHIP",
            iteration=2,
            date=datetime(2026, 5, 15),
            source="Remix",
            hook_library_path=path,
        )
        parts = name.split("_")
        assert len(parts) == 11
        assert parts[0] == "SK"
        assert parts[1] == "ProbioticBurnedPaige"
        assert parts[2] == "Testimonial"
        assert parts[3] == "Static"  # Text-on-product → Static
        assert parts[4] == "Venn"
        assert parts[5] == "Remix"
        assert parts[6] == "H01"  # text match to library H01
        assert parts[7] == "C00"  # placeholder
        assert parts[8] == "FREESHIP"
        assert parts[9] == "V2"
        assert parts[10] == "260515"

    def test_missing_brand_code_raises(self, tmp_path):
        b = _brand(code="")
        brief = _brief()
        with pytest.raises(ValueError, match="no 'code' field"):
            build_campaign_name(brief, b, hook_library_path=tmp_path / "x.yaml")

    def test_defaults_for_optional_params(self, tmp_path):
        b = _brand(code="SK")
        brief = _brief()
        path = _hook_library_fixture(tmp_path)
        name = build_campaign_name(brief, b, hook_library_path=path)
        parts = name.split("_")
        assert parts[8] == "NONE"  # default offer
        assert parts[9] == "V1"  # default iteration
        assert parts[5] == "Remix"  # default source
        assert parts[7] == "C00"  # default copy code

    def test_ai_source_for_generate_flow(self, tmp_path):
        b = _brand(code="SK")
        brief = _brief()
        path = _hook_library_fixture(tmp_path)
        name = build_campaign_name(brief, b, source="AI", hook_library_path=path)
        parts = name.split("_")
        assert parts[5] == "AI"
