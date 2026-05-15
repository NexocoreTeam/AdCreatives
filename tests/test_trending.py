"""Tests for strategy/trending.py — pure logic.

LLM-driven `rank_top_3` is exercised via stubbing the claude_complete call.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from strategy.trending import (
    _parse_ranker_response,
    load_trending_formats,
    prefilter_formats,
    rank_top_3,
    recommend_trending_formats,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _brief(
    *,
    persona: str = "Probiotic-Burned Paige",
    awareness: AwarenessLevel = AwarenessLevel.PROBLEM_AWARE,
    hook: str = "I tried probiotics for years and nothing worked.",
    hook_type: str = "Contrast / Enemy",
    persona_traits: str = "Gen-Z, casual, skeptical of brands",
) -> CreativeBrief:
    return CreativeBrief(
        brief_id="test-001",
        client="secondkind",
        product="Gut Balance",
        awareness_level=awareness,
        framework=CopyFramework.BAB,
        angle="postbiotic mechanism",
        hook=hook,
        hook_type=hook_type,
        persona=persona,
        persona_traits=persona_traits,
        creative_mechanic="Venn Diagram",
        visual_format="Static",
    )


def _library_fixture(tmp_path: Path) -> Path:
    """Mini trending library covering all the prefilter branches."""
    data = {
        "trending_formats": [
            {
                "id": "david-and-goliath",
                "name": "David & Goliath",
                "summary": "Underdog vs giant.",
                "best_when": {
                    "awareness_levels": ["problem_aware", "solution_aware"],
                    "persona_types": ["skeptic", "switcher"],
                    "product_categories": ["supplement", "dtc"],
                },
                "format_type": "both",
                "production_complexity": "medium",
                "status": "Active",
            },
            {
                "id": "obvious-ai-slop",
                "name": "Obvious AI Slop",
                "summary": "Cringe animated characters.",
                "best_when": {
                    "awareness_levels": ["problem_aware", "solution_aware"],
                    "persona_types": ["gen-z", "irreverent"],
                    "product_categories": ["supplement"],
                },
                "format_type": "video",
                "production_complexity": "medium",
                "status": "Active",
            },
            {
                "id": "tiktok-love-letter",
                "name": "TikTok Love Letter",
                "summary": "Long text overlay on B-roll.",
                "best_when": {
                    "awareness_levels": ["unaware", "problem_aware"],
                    "persona_types": ["community-driven"],
                    "product_categories": ["any"],
                },
                "format_type": "video",
                "production_complexity": "low",
                "status": "Active",
            },
            {
                "id": "were-not-cheap",
                "name": "We're Not Cheap",
                "summary": "Direct objection handling.",
                "best_when": {
                    "awareness_levels": ["solution_aware", "product_aware"],
                    "persona_types": ["premium-shopper"],
                    "product_categories": ["premium"],
                },
                "format_type": "both",
                "production_complexity": "low",
                "status": "Active",
            },
            {
                "id": "retired-old-format",
                "name": "Retired Old Format",
                "summary": "Should be filtered out.",
                "best_when": {
                    "awareness_levels": ["problem_aware"],
                    "persona_types": ["any"],
                    "product_categories": ["any"],
                },
                "format_type": "video",
                "production_complexity": "low",
                "status": "Retired",
            },
        ]
    }
    path = tmp_path / "trending_formats.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return path


# ─── load_trending_formats ──────────────────────────────────────────────────


class TestLoadTrendingFormats:
    def test_loads_active_only(self, tmp_path):
        path = _library_fixture(tmp_path)
        formats = load_trending_formats(path)
        ids = [f["id"] for f in formats]
        assert "retired-old-format" not in ids
        assert len(formats) == 4

    def test_missing_file_returns_empty(self, tmp_path):
        assert load_trending_formats(tmp_path / "nonexistent.yaml") == []

    def test_malformed_yaml_returns_empty(self, tmp_path):
        path = tmp_path / "broken.yaml"
        path.write_text("not: valid: ::yaml", encoding="utf-8")
        assert load_trending_formats(path) == []

    def test_missing_id_skipped(self, tmp_path):
        data = {"trending_formats": [{"name": "no id here"}]}
        path = tmp_path / "lib.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        assert load_trending_formats(path) == []


# ─── prefilter_formats ──────────────────────────────────────────────────────


class TestPrefilterFormats:
    def test_awareness_match_boosts_score(self, tmp_path):
        formats = load_trending_formats(_library_fixture(tmp_path))
        # problem_aware brief — should rank david-and-goliath, obvious-ai-slop, tiktok-love-letter higher
        brief = _brief(awareness=AwarenessLevel.PROBLEM_AWARE)
        ranked = prefilter_formats(brief, formats, top_n=4)
        # we're-not-cheap requires solution_aware/product_aware → should rank LAST
        last = ranked[-1]
        assert last["id"] == "were-not-cheap"

    def test_persona_token_match(self, tmp_path):
        formats = load_trending_formats(_library_fixture(tmp_path))
        # Persona traits contain "gen-z" → obvious-ai-slop should rank well
        brief = _brief(persona_traits="Gen-Z buyer, irreverent")
        ranked = prefilter_formats(brief, formats, top_n=3)
        ids = [f["id"] for f in ranked]
        assert "obvious-ai-slop" in ids

    def test_returns_at_most_n(self, tmp_path):
        formats = load_trending_formats(_library_fixture(tmp_path))
        brief = _brief()
        assert len(prefilter_formats(brief, formats, top_n=2)) == 2

    def test_empty_library(self):
        assert prefilter_formats(_brief(), [], top_n=3) == []


# ─── _parse_ranker_response ─────────────────────────────────────────────────


class TestParseRankerResponse:
    def test_parses_valid_json(self):
        text = json.dumps({
            "recommendations": [
                {"format_id": "david-and-goliath", "rank": 1, "rationale": "x", "production_notes": "y"},
                {"format_id": "tiktok-love-letter", "rank": 2, "rationale": "a", "production_notes": "b"},
            ]
        })
        recs = _parse_ranker_response(text)
        assert len(recs) == 2
        assert recs[0]["format_id"] == "david-and-goliath"

    def test_strips_markdown_fences(self):
        text = '```json\n{"recommendations":[{"format_id":"x","rank":1,"rationale":"r","production_notes":"n"}]}\n```'
        recs = _parse_ranker_response(text)
        assert len(recs) == 1

    def test_malformed_returns_empty(self):
        assert _parse_ranker_response("not json at all") == []

    def test_missing_format_id_skipped(self):
        text = json.dumps({
            "recommendations": [
                {"rank": 1, "rationale": "x"},  # missing format_id
                {"format_id": "valid", "rank": 2, "rationale": "y", "production_notes": ""},
            ]
        })
        recs = _parse_ranker_response(text)
        assert len(recs) == 1
        assert recs[0]["format_id"] == "valid"


# ─── rank_top_3 (stubbed LLM) ───────────────────────────────────────────────


class TestRankTop3:
    def test_enriches_with_source_metadata(self, monkeypatch, tmp_path):
        formats = load_trending_formats(_library_fixture(tmp_path))
        # Stub claude_complete
        import strategy.trending as t

        def _fake_complete(prompt, system="", max_tokens=4096):
            return json.dumps({
                "recommendations": [
                    {"format_id": "david-and-goliath", "rank": 1, "rationale": "fits skeptic persona", "production_notes": "pick a real enemy"},
                    {"format_id": "obvious-ai-slop", "rank": 2, "rationale": "good for gen-z", "production_notes": "keep it short"},
                    {"format_id": "tiktok-love-letter", "rank": 3, "rationale": "low-lift test", "production_notes": "use real comments"},
                ]
            })

        monkeypatch.setattr(t, "claude_complete", _fake_complete)
        result = rank_top_3(_brief(), formats[:4])
        assert len(result) == 3
        # Enriched with name + format_type from source
        first = result[0]
        assert first["format_id"] == "david-and-goliath"
        assert first["name"] == "David & Goliath"
        assert first["format_type"] == "both"
        assert first["rank"] == 1
        assert "skeptic" in first["rationale"]

    def test_unknown_format_id_dropped(self, monkeypatch, tmp_path):
        formats = load_trending_formats(_library_fixture(tmp_path))
        import strategy.trending as t

        def _fake_complete(prompt, system="", max_tokens=4096):
            return json.dumps({
                "recommendations": [
                    {"format_id": "made-up-id", "rank": 1, "rationale": "r", "production_notes": "n"},
                    {"format_id": "david-and-goliath", "rank": 2, "rationale": "r", "production_notes": "n"},
                ]
            })

        monkeypatch.setattr(t, "claude_complete", _fake_complete)
        result = rank_top_3(_brief(), formats)
        assert len(result) == 1  # made-up-id dropped
        assert result[0]["format_id"] == "david-and-goliath"

    def test_empty_candidates_returns_empty(self):
        assert rank_top_3(_brief(), []) == []


# ─── recommend_trending_formats (end-to-end with stubbed LLM) ───────────────


class TestRecommendTrendingFormats:
    def test_end_to_end(self, monkeypatch, tmp_path):
        path = _library_fixture(tmp_path)
        import strategy.trending as t

        def _fake_complete(prompt, system="", max_tokens=4096):
            return json.dumps({
                "recommendations": [
                    {"format_id": "david-and-goliath", "rank": 1, "rationale": "underdog narrative fits", "production_notes": ""},
                    {"format_id": "tiktok-love-letter", "rank": 2, "rationale": "low lift to test", "production_notes": ""},
                    {"format_id": "obvious-ai-slop", "rank": 3, "rationale": "gen-z friendly", "production_notes": ""},
                ]
            })

        monkeypatch.setattr(t, "claude_complete", _fake_complete)
        result = recommend_trending_formats(_brief(), library_path=path)
        assert len(result) == 3
        assert result[0]["format_id"] == "david-and-goliath"

    def test_returns_empty_when_no_library(self, tmp_path):
        assert recommend_trending_formats(_brief(), library_path=tmp_path / "nope.yaml") == []
