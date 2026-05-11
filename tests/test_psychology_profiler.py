"""Tests for strategy/psychology_profiler.py — schema enforcement + writeback.

Covers the value-add of this skill (confidence/evidence/ceiling rules) plus
the in-place merge that preserves existing avatar fields. The LLM call itself
is not exercised — those tests would just measure Anthropic's API, not our
logic. To test end-to-end, run `adc profile-psychology --client olipop` against
real avatars.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from models.avatar import (
    CustomerAvatar,
    DominantHeuristic,
    PsychologyProfile,
)
from strategy.psychology_profiler import (
    parse_profile_yaml,
    write_profile_into_avatar,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


VALID_DOMINANT = {
    "heuristic": "social_proof",
    "confidence": "high",
    "why": "Triggers gated by friend/creator recommendations.",
    "evidence": ["trigger_events[2]: friend recommended"],
    "ad_implications": "Lead with UGC + creator endorsements.",
}


def _profile_dict(**overrides) -> dict:
    """A minimal, valid psychology_profile dict, with optional overrides.

    Deep-copied per call so test mutations don't leak across cases.
    """
    base = {
        "dominant_heuristics": [copy.deepcopy(VALID_DOMINANT)],
        "weak_heuristics": [
            {
                "heuristic": "scarcity",
                "why": "Deliberate slow upgrader — urgency reads as gimmicky.",
                "avoid": "Countdowns, limited-edition framing.",
            },
        ],
        "emotional_position": {
            "primary": {
                "valence": "positive",
                "intensity": "low",
                "rationale": "Relief-driven desire language dominates.",
            },
            "secondary": {
                "valence": "negative",
                "intensity": "low",
                "use_for": "Quiet-ache variant testing.",
            },
        },
        "recommended_prompt_pairings": [
            {
                "pairing": "tribal_belonging_plus_vulnerability",
                "fits_because": "Activates social_proof + effect; matches HV/LI.",
            },
        ],
        "avoid_pairings": [
            {
                "pairing": "gamification_plus_time_sensitive_offer",
                "avoid_because": "Violates deliberate decision style.",
            },
        ],
    }
    base.update(overrides)
    return base


# ─── Pydantic validation ─────────────────────────────────────────────────────


class TestPsychologyProfileValidation:
    def test_valid_minimal_profile_validates(self):
        profile = PsychologyProfile(**_profile_dict())
        assert len(profile.dominant_heuristics) == 1
        assert profile.dominant_heuristics[0].heuristic == "social_proof"
        assert profile.source == "auto_from_psychology_profiling"

    def test_empty_profile_validates(self):
        """A profile with no heuristics/pairings is allowed (e.g. thin avatar)."""
        profile = PsychologyProfile()
        assert profile.dominant_heuristics == []
        assert profile.emotional_position is None

    def test_rejects_unknown_heuristic_name(self):
        bad = _profile_dict()
        bad["dominant_heuristics"][0]["heuristic"] = "made_up_heuristic"
        with pytest.raises(ValidationError, match="Unknown heuristic"):
            PsychologyProfile(**bad)

    def test_rejects_unknown_weak_heuristic_name(self):
        bad = _profile_dict()
        bad["weak_heuristics"][0]["heuristic"] = "invented"
        with pytest.raises(ValidationError, match="Unknown heuristic"):
            PsychologyProfile(**bad)

    def test_rejects_unknown_pairing_name(self):
        bad = _profile_dict()
        bad["recommended_prompt_pairings"][0]["pairing"] = "made_up_plus_invented"
        with pytest.raises(ValidationError, match="Unknown pairing"):
            PsychologyProfile(**bad)

    def test_rejects_unknown_avoid_pairing_name(self):
        bad = _profile_dict()
        bad["avoid_pairings"][0]["pairing"] = "fake_pairing"
        with pytest.raises(ValidationError, match="Unknown pairing"):
            PsychologyProfile(**bad)

    def test_rejects_invalid_confidence(self):
        bad = _profile_dict()
        bad["dominant_heuristics"][0]["confidence"] = "very_high"
        with pytest.raises(ValidationError, match="Confidence"):
            PsychologyProfile(**bad)

    def test_rejects_empty_evidence_on_dominant_heuristic(self):
        bad = _profile_dict()
        bad["dominant_heuristics"][0]["evidence"] = []
        with pytest.raises(ValidationError):
            PsychologyProfile(**bad)

    def test_rejects_invalid_valence(self):
        bad = _profile_dict()
        bad["emotional_position"]["primary"]["valence"] = "neutral"
        with pytest.raises(ValidationError, match="Valence"):
            PsychologyProfile(**bad)

    def test_rejects_invalid_intensity(self):
        bad = _profile_dict()
        bad["emotional_position"]["primary"]["intensity"] = "medium"
        with pytest.raises(ValidationError, match="Intensity"):
            PsychologyProfile(**bad)

    def test_rejects_more_than_three_high_confidence(self):
        """Hard rule from psychology-profiling.md: max 3 high-confidence heuristics."""
        four_high = [
            {**VALID_DOMINANT, "heuristic": h}
            for h in ["social_proof", "authority_bias", "framing_effect", "effect_heuristic"]
        ]
        bad = _profile_dict(dominant_heuristics=four_high)
        with pytest.raises(ValidationError, match="At most 3 dominant heuristics"):
            PsychologyProfile(**bad)

    def test_allows_three_high_plus_lower_confidence(self):
        mixed = [
            {**VALID_DOMINANT, "heuristic": "social_proof", "confidence": "high"},
            {**VALID_DOMINANT, "heuristic": "authority_bias", "confidence": "high"},
            {**VALID_DOMINANT, "heuristic": "framing_effect", "confidence": "high"},
            {**VALID_DOMINANT, "heuristic": "effect_heuristic", "confidence": "medium"},
        ]
        profile = PsychologyProfile(**_profile_dict(dominant_heuristics=mixed))
        assert len(profile.dominant_heuristics) == 4

    def test_rejects_more_than_six_recommended_pairings(self):
        seven = [
            {"pairing": p, "fits_because": "x"}
            for p in [
                "tribal_belonging_plus_vulnerability",
                "reframing_perception_plus_emotional_trigger",
                "authority_borrowing_plus_data_insight",
                "anonymity_plus_social_proof",
                "micro_story_plus_suspense",
                "contrast_plus_aspirational_identity",
                "first_principles_plus_loss_aversion",
            ]
        ]
        bad = _profile_dict(recommended_prompt_pairings=seven)
        with pytest.raises(ValidationError, match="At most 6 recommended pairings"):
            PsychologyProfile(**bad)


# ─── Avatar integration ─────────────────────────────────────────────────────


class TestAvatarWithPsychologyProfile:
    def test_avatar_accepts_psychology_profile(self):
        avatar = CustomerAvatar(
            demographic="Women 27–38",
            psychology_profile=PsychologyProfile(**_profile_dict()),
        )
        assert avatar.psychology_profile is not None
        assert avatar.psychology_profile.dominant_heuristics[0].heuristic == "social_proof"

    def test_avatar_without_psychology_profile_validates(self):
        avatar = CustomerAvatar(demographic="Women 27–38")
        assert avatar.psychology_profile is None

    def test_round_trip_through_yaml(self):
        original = CustomerAvatar(
            demographic="Women 27–38",
            psychology_profile=PsychologyProfile(**_profile_dict()),
        )
        dumped = yaml.safe_dump(original.model_dump(mode="json"), sort_keys=False)
        reloaded = CustomerAvatar(**yaml.safe_load(dumped))
        assert reloaded.psychology_profile is not None
        assert (
            reloaded.psychology_profile.dominant_heuristics[0].heuristic == "social_proof"
        )


# ─── parse_profile_yaml ─────────────────────────────────────────────────────


class TestParseProfileYaml:
    def test_parses_clean_yaml(self):
        text = yaml.safe_dump({"psychology_profile": _profile_dict()})
        profile = parse_profile_yaml(text)
        assert profile.dominant_heuristics[0].heuristic == "social_proof"

    def test_parses_yaml_without_wrapping_key(self):
        """LLMs sometimes return the inner block directly, not wrapped."""
        text = yaml.safe_dump(_profile_dict())
        profile = parse_profile_yaml(text)
        assert profile.dominant_heuristics[0].heuristic == "social_proof"

    def test_strips_markdown_code_fences(self):
        body = yaml.safe_dump({"psychology_profile": _profile_dict()})
        text = f"```yaml\n{body}\n```"
        profile = parse_profile_yaml(text)
        assert profile.dominant_heuristics[0].heuristic == "social_proof"

    def test_strips_bare_code_fences(self):
        body = yaml.safe_dump({"psychology_profile": _profile_dict()})
        text = f"```\n{body}\n```"
        profile = parse_profile_yaml(text)
        assert profile.dominant_heuristics[0].heuristic == "social_proof"

    def test_raises_validation_error_on_invalid_profile(self):
        bad = _profile_dict()
        bad["dominant_heuristics"][0]["heuristic"] = "fake"
        text = yaml.safe_dump({"psychology_profile": bad})
        with pytest.raises(ValidationError):
            parse_profile_yaml(text)


# ─── write_profile_into_avatar ──────────────────────────────────────────────


class TestWriteProfileIntoAvatar:
    def _make_avatar_file(self, tmp_path: Path) -> Path:
        path = tmp_path / "primary.yaml"
        existing = {
            "name": "Clean-Label Cara",
            "demographic": "Woman, 27–38, urban",
            "psychographic": "Cara grew up on Coke...",
            "pain_points": [
                {"pain": "Sparkling water doesn't scratch the itch",
                 "intensity": "high",
                 "customer_language": ["LaCroix is fine but it's not a Coke."],
                 "source": "auto_from_brand_context"},
            ],
            "desires": [],
            "objections": ["$3+ a can is steep"],
            "trigger_events": ["Starts Whole30"],
            "awareness_level": "solution_aware",
            "language_patterns": ["Casual but informed"],
        }
        path.write_text(yaml.safe_dump(existing, sort_keys=False), encoding="utf-8")
        return path

    def test_writes_profile_into_existing_avatar_yaml(self, tmp_path):
        avatar_path = self._make_avatar_file(tmp_path)
        profile = PsychologyProfile(**_profile_dict())

        write_profile_into_avatar(avatar_path, profile, backup=False)

        result = yaml.safe_load(avatar_path.read_text(encoding="utf-8"))
        assert "psychology_profile" in result
        assert (
            result["psychology_profile"]["dominant_heuristics"][0]["heuristic"]
            == "social_proof"
        )

    def test_preserves_all_existing_avatar_fields(self, tmp_path):
        avatar_path = self._make_avatar_file(tmp_path)
        profile = PsychologyProfile(**_profile_dict())

        write_profile_into_avatar(avatar_path, profile, backup=False)

        result = yaml.safe_load(avatar_path.read_text(encoding="utf-8"))
        assert result["name"] == "Clean-Label Cara"
        assert result["awareness_level"] == "solution_aware"
        assert result["pain_points"][0]["intensity"] == "high"
        assert result["objections"] == ["$3+ a can is steep"]

    def test_creates_backup_when_requested(self, tmp_path):
        avatar_path = self._make_avatar_file(tmp_path)
        original = avatar_path.read_text(encoding="utf-8")
        profile = PsychologyProfile(**_profile_dict())

        write_profile_into_avatar(avatar_path, profile, backup=True)

        backup_path = avatar_path.with_suffix(".yaml.bak")
        assert backup_path.exists()
        assert backup_path.read_text(encoding="utf-8") == original

    def test_no_backup_when_disabled(self, tmp_path):
        avatar_path = self._make_avatar_file(tmp_path)
        profile = PsychologyProfile(**_profile_dict())

        write_profile_into_avatar(avatar_path, profile, backup=False)

        assert not avatar_path.with_suffix(".yaml.bak").exists()

    def test_overwrites_existing_psychology_profile(self, tmp_path):
        """Re-running profile-psychology should replace the old block, not duplicate."""
        avatar_path = self._make_avatar_file(tmp_path)
        first = PsychologyProfile(**_profile_dict())
        write_profile_into_avatar(avatar_path, first, backup=False)

        # Second run with a different dominant heuristic.
        second_dict = _profile_dict()
        second_dict["dominant_heuristics"][0]["heuristic"] = "authority_bias"
        second = PsychologyProfile(**second_dict)
        write_profile_into_avatar(avatar_path, second, backup=False)

        result = yaml.safe_load(avatar_path.read_text(encoding="utf-8"))
        assert (
            result["psychology_profile"]["dominant_heuristics"][0]["heuristic"]
            == "authority_bias"
        )
