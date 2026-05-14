"""Tests for strategy/ad_remixer.py — parsing, pairing, coercion.

LLM-driven functions (analyze_local_image, analyze_foreplay, generate_remix_angles,
remix) are not exercised here — those would measure the model, not our logic.
To test end-to-end, run `adc remix --client <slug> --product <slug> --reference <path>`
against a real reference image.
"""

from __future__ import annotations

import yaml
import pytest

from models.avatar import (
    CustomerAvatar,
    DominantHeuristic,
    PainPoint,
    PsychologyProfile,
    WeakHeuristic,
)
from models.brief import AwarenessLevel, CopyFramework
from strategy.ad_remixer import (
    DEFAULT_LEVER_ROTATION,
    AdAnalysis,
    _coerce_awareness,
    _coerce_framework,
    _extract_foreplay_id,
    _foreplay_top_content_filter,
    _foreplay_top_emotion,
    _format_reference_style_block,
    _format_variation_block,
    _parse_strategic_yaml,
    _select_avatar_lever_pairs,
    _select_fidelity_tiers,
)


# ─── Foreplay ID extraction ─────────────────────────────────────────────────


class TestForeplayIdExtraction:
    def test_raw_numeric_id(self):
        assert _extract_foreplay_id("12345678") == "12345678"

    def test_app_url_with_ad_path(self):
        assert _extract_foreplay_id("https://app.foreplay.co/ad/12345678") == "12345678"

    def test_app_url_with_ads_path(self):
        assert _extract_foreplay_id("https://app.foreplay.co/ads/9876543") == "9876543"

    def test_url_with_query_params(self):
        assert (
            _extract_foreplay_id("https://app.foreplay.co/ad/12345?ref=email")
            == "12345"
        )

    def test_trailing_numeric_in_path(self):
        # No /ad/ segment but a long numeric trailing — fallback regex picks it up
        assert (
            _extract_foreplay_id("https://app.foreplay.co/discovery/87654321")
            == "87654321"
        )

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            _extract_foreplay_id("")

    def test_rejects_unparseable(self):
        with pytest.raises(ValueError, match="Could not extract"):
            _extract_foreplay_id("https://example.com/whatever")


# ─── Strategic YAML parsing ─────────────────────────────────────────────────


class TestStrategicYamlParsing:
    def _valid_yaml(self, **overrides) -> str:
        base = {
            "ad_type": "us-vs-them",
            "ad_type_confidence": 0.9,
            "ad_type_reasoning": "Split layout, checkmarks vs Xs.",
            "psych_levers": ["social_proof", "framing_effect"],
            "dominant_emotion": "frustration",
            "framework": "bab",
            "hook_tactic": "Specific stat with a story",
            "creative_mechanic": "Split-screen comparison",
            "visual_format": "Side-by-side product comparison",
            "awareness_level": "solution_aware",
            "pain_attacked": "Aluminum residue and chalky deodorant",
            "enemy": "drugstore competitor",
            "visible_copy": {
                "headline": "Stop wasting nights",
                "description": "Switch to refillable",
                "cta": "Shop now",
                "callouts": ["24h protection", "No aluminum"],
            },
        }
        base.update(overrides)
        return yaml.safe_dump(base)

    def test_parses_clean_yaml(self):
        result = _parse_strategic_yaml(self._valid_yaml())
        assert result["ad_type"] == "us-vs-them"
        assert result["psych_levers"] == ["social_proof", "framing_effect"]

    def test_strips_markdown_fences(self):
        body = self._valid_yaml()
        text = f"```yaml\n{body}\n```"
        result = _parse_strategic_yaml(text)
        assert result["ad_type"] == "us-vs-them"

    def test_strips_bare_code_fences(self):
        body = self._valid_yaml()
        text = f"```\n{body}\n```"
        result = _parse_strategic_yaml(text)
        assert result["framework"] == "bab"

    def test_normalizes_ad_type_with_underscores(self):
        result = _parse_strategic_yaml(self._valid_yaml(ad_type="us_vs_them"))
        assert result["ad_type"] == "us-vs-them"

    def test_normalizes_ad_type_with_spaces(self):
        result = _parse_strategic_yaml(self._valid_yaml(ad_type="us vs them"))
        assert result["ad_type"] == "us-vs-them"

    def test_unknown_ad_type_falls_to_other(self):
        result = _parse_strategic_yaml(self._valid_yaml(ad_type="meme-format"))
        assert result["ad_type"] == "other"

    def test_filters_invalid_heuristics(self):
        result = _parse_strategic_yaml(
            self._valid_yaml(
                psych_levers=["social_proof", "made_up_lever", "authority_bias"]
            )
        )
        assert result["psych_levers"] == ["social_proof", "authority_bias"]

    def test_caps_levers_at_three(self):
        result = _parse_strategic_yaml(
            self._valid_yaml(
                psych_levers=[
                    "social_proof",
                    "authority_bias",
                    "scarcity",
                    "framing_effect",
                ]
            )
        )
        assert len(result["psych_levers"]) == 3

    def test_rejects_non_mapping_yaml(self):
        # Top-level list, not a mapping
        with pytest.raises(ValueError, match="non-mapping"):
            _parse_strategic_yaml("- not\n- a\n- mapping")


# ─── Foreplay metadata priors ───────────────────────────────────────────────


class TestForeplayPriors:
    def test_content_filter_direct_match(self):
        result = _foreplay_top_content_filter(
            {"us-vs-them": 0.85, "ugc": 0.10, "testimonial-review": 0.05}
        )
        assert result == "us-vs-them"

    def test_content_filter_alias_resolution(self):
        result = _foreplay_top_content_filter(
            {"comparison": 0.8, "testimonial": 0.2}
        )
        assert result == "us-vs-them"

    def test_content_filter_underscore_normalization(self):
        result = _foreplay_top_content_filter(
            {"features_and_benefits": 0.9, "ugc": 0.1}
        )
        assert result == "features-and-benefits"

    def test_content_filter_unknown_label_returns_empty(self):
        result = _foreplay_top_content_filter({"meme": 0.9, "viral": 0.1})
        assert result == ""

    def test_content_filter_empty_dict(self):
        assert _foreplay_top_content_filter({}) == ""

    def test_top_emotion_picks_highest(self):
        result = _foreplay_top_emotion({"frustration": 8, "joy": 3, "fear": 1})
        assert result == "frustration"

    def test_top_emotion_empty(self):
        assert _foreplay_top_emotion({}) == ""


# ─── Avatar lever pairing ───────────────────────────────────────────────────


def _make_avatar(
    name: str,
    *,
    dominant: list[tuple[str, str]] | None = None,
    weak: list[str] | None = None,
) -> CustomerAvatar:
    """Build a CustomerAvatar with optional psychology profile."""
    profile = None
    if dominant or weak:
        profile = PsychologyProfile(
            dominant_heuristics=[
                DominantHeuristic(
                    heuristic=h,
                    confidence=conf,
                    why="test",
                    evidence=["test-evidence"],
                    ad_implications="test",
                )
                for h, conf in (dominant or [])
            ],
            weak_heuristics=[
                WeakHeuristic(heuristic=h, why="test", avoid="test")
                for h in (weak or [])
            ],
        )
    return CustomerAvatar(
        name=name,
        demographic=f"{name} demographic",
        pain_points=[PainPoint(pain="test pain")],
        psychology_profile=profile,
    )


class TestAvatarLeverPairing:
    def test_single_avatar_cycles_lever(self):
        a = _make_avatar("solo")
        pairs = _select_avatar_lever_pairs([a], 3, ["social_proof", "scarcity"])
        assert len(pairs) == 3
        assert all(p[0] is a for p in pairs)
        levers = [p[1] for p in pairs]
        # All three levers should be distinct within the same avatar
        assert len(set(levers)) == 3

    def test_multiple_avatars_round_robin(self):
        a1 = _make_avatar("a1")
        a2 = _make_avatar("a2")
        pairs = _select_avatar_lever_pairs([a1, a2], 4, [])
        # Round-robin assignment
        assert pairs[0][0] is a1
        assert pairs[1][0] is a2
        assert pairs[2][0] is a1
        assert pairs[3][0] is a2

    def test_skips_weak_heuristics(self):
        a = _make_avatar("careful", weak=["scarcity"])
        pairs = _select_avatar_lever_pairs([a], 5, ["scarcity", "social_proof"])
        assigned = [lever for _, lever in pairs]
        assert "scarcity" not in assigned

    def test_prefers_dominant_heuristics_that_match_analysis(self):
        # Avatar dominant: authority_bias, social_proof
        # Analysis levers: social_proof, scarcity
        # Should prefer social_proof first (dominant ∩ analysis)
        a = _make_avatar(
            "matched",
            dominant=[("authority_bias", "high"), ("social_proof", "high")],
        )
        pairs = _select_avatar_lever_pairs([a], 1, ["social_proof", "scarcity"])
        assert pairs[0][1] == "social_proof"

    def test_then_falls_to_remaining_dominant(self):
        # 2nd variation for same avatar should pick the other dominant
        a = _make_avatar(
            "matched",
            dominant=[("authority_bias", "high"), ("social_proof", "high")],
        )
        pairs = _select_avatar_lever_pairs([a], 2, ["social_proof", "scarcity"])
        assert pairs[0][1] == "social_proof"
        assert pairs[1][1] == "authority_bias"

    def test_falls_back_to_defaults_when_dominant_exhausted(self):
        a = _make_avatar("simple", dominant=[("social_proof", "high")])
        pairs = _select_avatar_lever_pairs([a], 3, [])
        levers = [p[1] for p in pairs]
        assert levers[0] == "social_proof"
        # Subsequent levers come from DEFAULT_LEVER_ROTATION
        for lever in levers[1:]:
            assert lever in DEFAULT_LEVER_ROTATION

    def test_rejects_zero_variations(self):
        a = _make_avatar("solo")
        with pytest.raises(ValueError, match="variations"):
            _select_avatar_lever_pairs([a], 0, [])

    def test_rejects_empty_avatar_list(self):
        with pytest.raises(ValueError, match="No avatars"):
            _select_avatar_lever_pairs([], 1, [])


# ─── Brief field coercion ───────────────────────────────────────────────────


class TestFrameworkCoercion:
    def test_valid_lowercase(self):
        assert _coerce_framework("bab", "pas") is CopyFramework.BAB

    def test_valid_uppercase(self):
        assert _coerce_framework("BAB", "pas") is CopyFramework.BAB

    def test_falls_back_to_default(self):
        assert _coerce_framework("nonsense", "fab") is CopyFramework.FAB

    def test_falls_back_to_pas_when_default_invalid(self):
        assert _coerce_framework("nonsense", "alsonotreal") is CopyFramework.PAS

    def test_handles_none(self):
        assert _coerce_framework(None, "aida") is CopyFramework.AIDA


class TestAwarenessCoercion:
    def test_valid_value(self):
        assert (
            _coerce_awareness("solution_aware", "problem_aware")
            is AwarenessLevel.SOLUTION_AWARE
        )

    def test_normalizes_dashes(self):
        assert (
            _coerce_awareness("solution-aware", "problem_aware")
            is AwarenessLevel.SOLUTION_AWARE
        )

    def test_falls_back_on_invalid(self):
        assert (
            _coerce_awareness("invented_level", "problem_aware")
            is AwarenessLevel.PROBLEM_AWARE
        )

    def test_handles_none(self):
        assert (
            _coerce_awareness(None, "most_aware")
            is AwarenessLevel.MOST_AWARE
        )


# ─── AdAnalysis dataclass ───────────────────────────────────────────────────


class TestAdAnalysisDataclass:
    def _make(self) -> AdAnalysis:
        return AdAnalysis(
            ad_type="us-vs-them",
            ad_type_confidence=0.9,
            ad_type_reasoning="split layout",
            psych_levers=["social_proof", "framing_effect"],
            dominant_emotion="frustration",
            framework="bab",
            hook_tactic="Specific stat with a story",
            creative_mechanic="Split-screen comparison",
            visual_format="Side-by-side product",
            awareness_level="solution_aware",
            pain_attacked="aluminum residue",
            enemy="drugstore competitor",
            visible_copy={"headline": "Stop the chalk"},
            visual={"layout": {"composition": "left/right split"}},
            source_type="local",
            source_ref="/tmp/ref.png",
        )

    def test_to_yaml_dict_roundtrips(self):
        analysis = self._make()
        as_dict = analysis.to_yaml_dict()
        # All fields present, including default-factory ones
        assert as_dict["ad_type"] == "us-vs-them"
        assert as_dict["psych_levers"] == ["social_proof", "framing_effect"]
        assert as_dict["foreplay_metadata"] == {}
        assert as_dict["visual"]["layout"]["composition"] == "left/right split"

    def test_serializes_through_yaml(self):
        analysis = self._make()
        serialized = yaml.safe_dump(analysis.to_yaml_dict(), sort_keys=False)
        reloaded = yaml.safe_load(serialized)
        assert reloaded["ad_type"] == "us-vs-them"
        assert reloaded["enemy"] == "drugstore competitor"


# ─── Variation block formatting ─────────────────────────────────────────────


class TestVariationBlock:
    def test_contains_locked_heuristic(self):
        a = _make_avatar("Stressed Parent")
        block = _format_variation_block(1, a, "scarcity")
        assert "locked_heuristic: scarcity" in block
        assert "Variation 1" in block

    def test_truncates_long_persona_name(self):
        long_demo = "x" * 200
        a = CustomerAvatar(name="", demographic=long_demo)
        block = _format_variation_block(2, a, "social_proof")
        # persona_name line should be capped at 60 chars
        line = next(
            (ln for ln in block.splitlines() if "persona_name:" in ln), ""
        )
        # Strip the "    persona_name: " prefix (18 chars) then check length
        value = line.split("persona_name:", 1)[1].strip()
        assert len(value) <= 60

    def test_handles_empty_pains_and_desires(self):
        a = CustomerAvatar(name="Empty", demographic="empty")
        block = _format_variation_block(1, a, "authority_bias")
        assert "none provided" in block

    def test_includes_fidelity_tier(self):
        a = _make_avatar("test")
        block = _format_variation_block(1, a, "social_proof", fidelity_tier="high")
        assert "fidelity_tier: high" in block

    def test_default_fidelity_tier_is_medium(self):
        a = _make_avatar("test")
        block = _format_variation_block(1, a, "social_proof")
        assert "fidelity_tier: medium" in block


# ─── Fidelity tier selection ────────────────────────────────────────────────


class TestFidelityTierSelection:
    def test_five_variations_default(self):
        tiers = _select_fidelity_tiers(5)
        assert tiers == ["high", "high", "medium", "medium", "low"]

    def test_two_variations_all_high(self):
        tiers = _select_fidelity_tiers(2)
        assert tiers == ["high", "high"]

    def test_one_variation(self):
        tiers = _select_fidelity_tiers(1)
        assert tiers == ["high"]

    def test_seven_variations_overflow_to_low(self):
        tiers = _select_fidelity_tiers(7)
        assert tiers == ["high", "high", "medium", "medium", "low", "low", "low"]

    def test_zero_high_zero_medium_all_low(self):
        tiers = _select_fidelity_tiers(3, max_high=0, max_medium=0)
        assert tiers == ["low", "low", "low"]

    def test_all_high_when_max_high_exceeds(self):
        tiers = _select_fidelity_tiers(3, max_high=10, max_medium=0)
        assert tiers == ["high", "high", "high"]

    def test_rejects_zero_variations(self):
        with pytest.raises(ValueError, match="variations"):
            _select_fidelity_tiers(0)

    def test_rejects_negative_max(self):
        with pytest.raises(ValueError, match="non-negative"):
            _select_fidelity_tiers(3, max_high=-1)


# ─── Reference style block ──────────────────────────────────────────────────


class TestReferenceStyleBlock:
    def _make_analysis(self, **visual_overrides) -> AdAnalysis:
        visual = {
            "people": {
                "present": True,
                "description": "hand from bottom holding product",
                "relationship_to_product": "holding upright",
            },
            "visual_style": {
                "color_palette": {"background": "#F2F2F0"},
                "lighting": "soft natural indoor",
                "mood": "approachable, honest",
                "texture": "matte whiteboard",
            },
            "typography_style": {
                "heading_style": "casual handwritten + bold serif",
                "text_treatment": "underline emphasis",
            },
            "layout": {"composition": "logo top, product center, CTA bottom-left"},
            "overall": {"energy": "casual/educational"},
        }
        visual.update(visual_overrides)
        return AdAnalysis(
            ad_type="testimonial-review",
            ad_type_confidence=0.8,
            ad_type_reasoning="",
            psych_levers=[],
            dominant_emotion="",
            framework="bab",
            hook_tactic="",
            creative_mechanic="",
            visual_format="",
            awareness_level="problem_aware",
            pain_attacked="",
            enemy="",
            visible_copy={},
            visual=visual,
            source_type="local",
            source_ref="/test.png",
        )

    def test_includes_person_when_present(self):
        block = _format_reference_style_block(self._make_analysis())
        assert "PERSON in frame: yes" in block
        assert "hand from bottom" in block

    def test_marks_no_person_when_absent(self):
        analysis = self._make_analysis(people={"present": False})
        block = _format_reference_style_block(analysis)
        assert "PERSON in frame: no" in block
        assert "product stands alone" in block

    def test_includes_background_color(self):
        block = _format_reference_style_block(self._make_analysis())
        assert "#F2F2F0" in block

    def test_includes_typography(self):
        block = _format_reference_style_block(self._make_analysis())
        assert "handwritten" in block.lower()

    def test_handles_missing_visual_fields_gracefully(self):
        # Sparse visual DNA — just the header should still render
        analysis = AdAnalysis(
            ad_type="other", ad_type_confidence=0.5, ad_type_reasoning="",
            psych_levers=[], dominant_emotion="", framework="pas", hook_tactic="",
            creative_mechanic="", visual_format="", awareness_level="problem_aware",
            pain_attacked="", enemy="", visible_copy={}, visual={},
            source_type="local", source_ref="",
        )
        block = _format_reference_style_block(analysis)
        # Should not raise; just contains the header
        assert "REFERENCE VISUAL STYLE" in block
