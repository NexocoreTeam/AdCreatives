"""Tests for strategy/competitive_context.py — shared loaders + formatters.

Covers the three things this module is responsible for:
    1. Loading research artifacts from disk (gap map, VoC pains)
    2. Formatting those artifacts as prompt-ready blocks
    3. Falling back to a placeholder string when data is missing

The actual LLM consumers (psychology_profiler, matrix) are tested elsewhere —
this file exercises only the loader + formatter contract.
"""

from __future__ import annotations

import yaml

import pytest

from strategy.competitive_context import (
    NO_GAPS_PLACEHOLDER,
    NO_PSYCH_PLACEHOLDER,
    NO_VOC_PLACEHOLDER,
    format_competitive_block,
    format_psychology_summary,
    format_voc_block,
    load_competitive_gaps,
    load_voc_pains,
)


# ─── load_competitive_gaps ──────────────────────────────────────────────────


def test_load_competitive_gaps_returns_none_when_file_missing(tmp_path, monkeypatch):
    """No competitive-gaps.yaml on disk → loader returns None, doesn't raise."""
    monkeypatch.chdir(tmp_path)
    assert load_competitive_gaps("nonexistent") is None


def test_load_competitive_gaps_returns_dict_when_file_present(tmp_path, monkeypatch):
    """When competitive-gaps.yaml exists with a `synthesis` block, loader returns it."""
    monkeypatch.chdir(tmp_path)
    research_dir = tmp_path / "clients" / "test-client" / "research"
    research_dir.mkdir(parents=True)
    payload = {
        "synthesis": {
            "exploitable_gaps": [
                {"gap": "Delayed results", "evidence": "Multiple 1★ Amazon reviews"},
            ]
        }
    }
    (research_dir / "competitive-gaps.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )

    result = load_competitive_gaps("test-client")
    assert result is not None
    assert result["synthesis"]["exploitable_gaps"][0]["gap"] == "Delayed results"


def test_load_competitive_gaps_returns_none_when_synthesis_missing(tmp_path, monkeypatch):
    """File exists but lacks a `synthesis` key → treat as empty, return None."""
    monkeypatch.chdir(tmp_path)
    research_dir = tmp_path / "clients" / "test-client" / "research"
    research_dir.mkdir(parents=True)
    (research_dir / "competitive-gaps.yaml").write_text(
        yaml.safe_dump({"other_key": "value"}), encoding="utf-8"
    )
    assert load_competitive_gaps("test-client") is None


# ─── format_competitive_block ───────────────────────────────────────────────


def test_format_competitive_block_returns_placeholder_for_none():
    assert format_competitive_block(None) == NO_GAPS_PLACEHOLDER


def test_format_competitive_block_returns_placeholder_for_empty_synthesis():
    assert format_competitive_block({"synthesis": {}}) == NO_GAPS_PLACEHOLDER


def test_format_competitive_block_renders_exploitable_gaps():
    gaps = {
        "synthesis": {
            "exploitable_gaps": [
                {"gap": "Slow shipping", "evidence": "20% of 1★ mention delays"},
                {"gap": "Confusing dosage instructions"},
            ]
        }
    }
    out = format_competitive_block(gaps)
    assert "Exploitable competitor gaps" in out
    assert "Slow shipping" in out
    assert "20% of 1★ mention delays" in out
    assert "Confusing dosage" in out


def test_format_competitive_block_renders_all_three_sections():
    gaps = {
        "synthesis": {
            "exploitable_gaps": [{"gap": "Gap A"}],
            "recurring_complaints": [{"complaint": "Complaint B"}],
            "competitor_strengths_to_concede": [{"strength": "Strength C"}],
        }
    }
    out = format_competitive_block(gaps)
    assert "Gap A" in out
    assert "Complaint B" in out
    assert "Strength C" in out


def test_format_competitive_block_caps_long_lists():
    """Long pulls get truncated so the prompt doesn't blow the token budget."""
    many_gaps = [{"gap": f"Gap {i}"} for i in range(20)]
    gaps = {"synthesis": {"exploitable_gaps": many_gaps}}
    out = format_competitive_block(gaps)
    assert "Gap 0" in out
    assert "Gap 7" in out
    assert "Gap 19" not in out  # capped at 8


# ─── load_voc_pains ─────────────────────────────────────────────────────────


def test_load_voc_pains_returns_none_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_voc_pains("nonexistent") is None


def test_load_voc_pains_returns_dict_when_file_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    voc_dir = tmp_path / "clients" / "test-client" / "voc"
    voc_dir.mkdir(parents=True)
    payload = {"pain_points": ["bloating", "fatigue"], "desires": ["energy"]}
    (voc_dir / "extracted_pains.yaml").write_text(
        yaml.safe_dump(payload), encoding="utf-8"
    )

    result = load_voc_pains("test-client")
    assert result is not None
    assert result["pain_points"] == ["bloating", "fatigue"]


# ─── format_voc_block ───────────────────────────────────────────────────────


def test_format_voc_block_returns_placeholder_for_none():
    assert format_voc_block(None) == NO_VOC_PLACEHOLDER


def test_format_voc_block_returns_placeholder_for_empty_dict():
    assert format_voc_block({}) == NO_VOC_PLACEHOLDER


def test_format_voc_block_returns_placeholder_when_no_high_signal_keys():
    """VoC dict exists but has only irrelevant keys → placeholder."""
    assert format_voc_block({"random_key": ["foo"]}) == NO_VOC_PLACEHOLDER


def test_format_voc_block_renders_pain_points():
    voc = {
        "pain_points": ["chronic bloating", "low energy"],
        "money_quotes": ["I've tried everything and nothing works"],
    }
    out = format_voc_block(voc)
    assert "pain_points" in out
    assert "chronic bloating" in out
    assert "money_quotes" in out
    assert out.startswith("```yaml")
    assert out.rstrip().endswith("```")


# ─── format_psychology_summary ──────────────────────────────────────────────


def test_format_psychology_summary_returns_placeholder_for_empty_list():
    assert format_psychology_summary([]) == NO_PSYCH_PLACEHOLDER


def test_format_psychology_summary_skips_avatars_without_profile():
    class FakeAvatar:
        def __init__(self, name, profile=None):
            self.name = name
            self.psychology_profile = profile

    avatars = [FakeAvatar("Alice"), FakeAvatar("Bob")]
    assert format_psychology_summary(avatars) == NO_PSYCH_PLACEHOLDER


def test_format_psychology_summary_renders_profile_when_present():
    class FakeAvatar:
        def __init__(self, name, profile):
            self.name = name
            self.psychology_profile = profile

    profile = {
        "dominant_heuristics": [
            {"heuristic": "social_proof", "confidence": "high"},
            {"heuristic": "scarcity", "confidence": "medium"},
        ],
        "weak_heuristics": [{"heuristic": "authority_bias"}],
        "emotional_position": {
            "primary": {"valence": "negative", "intensity": "high"}
        },
        "recommended_prompt_pairings": [
            {"pairing": "ugc_creator"},
            {"pairing": "before_after"},
        ],
        "avoid_pairings": [{"pairing": "celebrity_endorsement"}],
    }
    out = format_psychology_summary([FakeAvatar("Sarah, 38", profile)])
    assert "Sarah, 38" in out
    assert "social_proof" in out
    assert "scarcity" in out
    assert "authority_bias" in out
    assert "negative valence" in out
    assert "high intensity" in out
    assert "ugc_creator" in out
    assert "before_after" in out
    assert "celebrity_endorsement" in out


def test_format_psychology_summary_handles_model_dump_objects():
    """Profile may be a pydantic-style object exposing model_dump()."""

    class FakeProfile:
        def model_dump(self, mode="json"):
            return {
                "dominant_heuristics": [{"heuristic": "goal_gradient"}],
                "emotional_position": {
                    "primary": {"valence": "positive", "intensity": "low"}
                },
            }

    class FakeAvatar:
        name = "Tester"
        psychology_profile = FakeProfile()

    out = format_psychology_summary([FakeAvatar()])
    assert "Tester" in out
    assert "goal_gradient" in out
