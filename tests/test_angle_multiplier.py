"""Tests for strategy/angle_multiplier.py — diversity matrix filtering and prompt assembly.

LLM call itself is not exercised (mocking a generative call tests Anthropic,
not us). Focus is on the deterministic logic: which slots survive a given
profile, what the psychology block looks like, and how the prompt template
interpolates with and without a profile.
"""

from __future__ import annotations

import pytest

from models.avatar import (
    AvoidPairing,
    DominantHeuristic,
    EmotionalPosition,
    EmotionalQuadrant,
    PsychologyProfile,
    RecommendedPairing,
    WeakHeuristic,
)
from strategy.angle_multiplier import (
    DIVERSITY_MATRIX,
    SLOT_TO_HEURISTICS,
    build_psychology_block,
    filter_matrix_by_profile,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _cara_profile() -> PsychologyProfile:
    """A profile shaped like the calibrated Olipop Cara reference."""
    return PsychologyProfile(
        dominant_heuristics=[
            DominantHeuristic(
                heuristic="framing_effect",
                confidence="high",
                why="x",
                evidence=["e"],
                ad_implications="Reframe price as cost-per-day.",
            ),
            DominantHeuristic(
                heuristic="social_proof",
                confidence="high",
                why="x",
                evidence=["e"],
                ad_implications="Lead with UGC voices.",
            ),
            DominantHeuristic(
                heuristic="effect_heuristic",
                confidence="medium",
                why="x",
                evidence=["e"],
                ad_implications="Sensory cues over functional claims.",
            ),
        ],
        weak_heuristics=[
            WeakHeuristic(heuristic="scarcity", why="x", avoid="No countdowns."),
            WeakHeuristic(heuristic="temporal_discounting", why="x", avoid="No instant promises."),
            WeakHeuristic(heuristic="authority_bias", why="x", avoid="No white-coat imagery."),
        ],
        emotional_position=EmotionalPosition(
            primary=EmotionalQuadrant(
                valence="positive", intensity="low", rationale="Relief and permission."
            ),
            secondary=EmotionalQuadrant(
                valence="negative", intensity="low", use_for="Variant testing."
            ),
        ),
        recommended_prompt_pairings=[
            RecommendedPairing(
                pairing="reframing_perception_plus_emotional_trigger",
                fits_because="x",
            ),
            RecommendedPairing(
                pairing="tribal_belonging_plus_vulnerability",
                fits_because="x",
            ),
        ],
        avoid_pairings=[
            AvoidPairing(
                pairing="gamification_plus_time_sensitive_offer",
                avoid_because="Urgency undermines wellness credibility.",
            ),
        ],
    )


# ─── filter_matrix_by_profile ───────────────────────────────────────────────


class TestFilterMatrixByProfile:
    def test_no_profile_returns_first_n_slots(self):
        result = filter_matrix_by_profile(None, count=5)
        assert len(result) == 5
        assert [r["slot"] for r in result] == [1, 2, 3, 4, 5]

    def test_empty_profile_returns_first_n_slots(self):
        empty = PsychologyProfile()
        result = filter_matrix_by_profile(empty, count=5)
        assert len(result) == 5

    def test_drops_slots_whose_heuristics_are_all_weak(self):
        """Cara's weak set (scarcity, temporal_discounting, authority_bias) should
        eliminate slots 1 (Surprising Stat → authority_bias) and 3 (FOMO → scarcity
        + temporal_discounting)."""
        result = filter_matrix_by_profile(_cara_profile(), count=6)
        slots_kept = [r["slot"] for r in result]
        assert 1 not in slots_kept, "slot 1 (authority_bias-only) should be dropped"
        assert 3 not in slots_kept, "slot 3 (scarcity+temporal_discounting-only) should be dropped"

    def test_returns_exactly_count_slots(self):
        result = filter_matrix_by_profile(_cara_profile(), count=6)
        assert len(result) == 6

    def test_keeps_slots_with_at_least_one_non_weak_heuristic(self):
        """Slot 2 (effect + social_proof), 5 (framing + social_proof), and 10
        (framing + effect) have no overlap with Cara's weak set — must all
        appear in the kept set when count=8 (the surviving total for Cara)."""
        result = filter_matrix_by_profile(_cara_profile(), count=8)
        slots_kept = [r["slot"] for r in result]
        assert 2 in slots_kept
        assert 5 in slots_kept
        assert 10 in slots_kept

    def test_raises_when_filter_drops_below_count(self):
        """Profile that weakens everything → count > surviving → error."""
        all_weak = PsychologyProfile(
            weak_heuristics=[
                WeakHeuristic(heuristic=h, why="x", avoid="x")
                for h in {
                    "scarcity",
                    "temporal_discounting",
                    "authority_bias",
                    "framing_effect",
                    "social_proof",
                    "effect_heuristic",
                    "salience_bias",
                }
            ],
        )
        with pytest.raises(ValueError, match="diversity slots survive"):
            filter_matrix_by_profile(all_weak, count=3)

    def test_raises_when_count_exceeds_matrix_size_with_no_profile(self):
        with pytest.raises(ValueError, match="exceeds diversity matrix size"):
            filter_matrix_by_profile(None, count=99)


class TestSlotToHeuristicsTable:
    def test_every_slot_has_a_mapping(self):
        for slot_def in DIVERSITY_MATRIX:
            assert slot_def["slot"] in SLOT_TO_HEURISTICS, (
                f"Slot {slot_def['slot']} ({slot_def['hook_type']}) needs an entry "
                f"in SLOT_TO_HEURISTICS"
            )

    def test_no_unknown_heuristic_names_in_mapping(self):
        from models.avatar import HEURISTIC_NAMES

        for slot, heuristics in SLOT_TO_HEURISTICS.items():
            for h in heuristics:
                assert h in HEURISTIC_NAMES, f"Slot {slot} references unknown heuristic '{h}'"


# ─── build_psychology_block ─────────────────────────────────────────────────


class TestBuildPsychologyBlock:
    def test_no_profile_returns_empty_string(self):
        assert build_psychology_block(None) == ""

    def test_includes_quadrants(self):
        block = build_psychology_block(_cara_profile())
        assert "positive / low" in block
        assert "negative / low" in block

    def test_includes_dominant_heuristics_with_ad_implications(self):
        block = build_psychology_block(_cara_profile())
        assert "framing_effect" in block
        assert "social_proof" in block
        assert "effect_heuristic" in block
        assert "Reframe price as cost-per-day" in block

    def test_includes_weak_heuristics_with_avoid_text(self):
        block = build_psychology_block(_cara_profile())
        assert "scarcity" in block
        assert "No countdowns" in block

    def test_includes_recommended_pairings(self):
        block = build_psychology_block(_cara_profile())
        assert "reframing_perception_plus_emotional_trigger" in block
        assert "Pre-approved" in block or "pre-approved" in block.lower()

    def test_includes_banned_pairings(self):
        block = build_psychology_block(_cara_profile())
        assert "gamification_plus_time_sensitive_offer" in block
        assert "BANNED" in block

    def test_marks_constraints_as_hard(self):
        """The block must signal hard constraints, not soft suggestions."""
        block = build_psychology_block(_cara_profile())
        assert "HARD CONSTRAINTS" in block or "MUST" in block
