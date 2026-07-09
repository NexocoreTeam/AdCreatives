"""Tests for strategy/ad_card.py — validation, corrections, sidecar IO."""

from __future__ import annotations

import pytest
import yaml

from strategy.ad_card import (
    apply_corrections,
    load_all_cards,
    load_card,
    next_card_id,
    parse_corrections,
    render_display,
    save_card,
    update_card,
    validate_card,
)
from strategy.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


def good_draft() -> dict:
    return {
        "brand": "Soft Services",
        "source_link": "https://example.com/ad",
        "proxy_signal": "running ~4 months, 12 variations",
        "media_type": "static",
        "format": "Billboard",
        "hook_type": "Warning",
        "mechanic": "The Trojan Horse",
        "secondary_mechanic": None,
        "scan_path": ["headline", "product", "CTA"],
        "proof_element": "itemized receipt with real prices",
        "product_role": "hero",
        "awareness_stage": "problem_aware",
        "why_it_works": "The receipt format makes the savings claim feel audited.",
        "cultural_note": "none",
        "steal": "Reuse the receipt-as-proof structure.",
        "avoid": "Do not reuse the creator or exact copy.",
        "field_confidence": {"format": "high", "hook_type": "med", "mechanic": "high",
                             "awareness_stage": "high", "product_role": "high"},
        "reasoning": {"mechanic": "native format smuggles the ad",
                      "awareness_stage": "targets a felt pain"},
    }


class TestValidateCard:
    def test_clean_draft_passes(self, tax):
        result = validate_card(good_draft(), tax)
        assert result.ok
        assert result.card["mechanic"] == "The Trojan Horse"

    def test_loose_enum_values_normalize(self, tax):
        draft = good_draft() | {"mechanic": "trojan horse", "awareness_stage": "Problem-Aware"}
        result = validate_card(draft, tax)
        assert result.ok
        assert result.card["mechanic"] == "The Trojan Horse"
        assert result.card["awareness_stage"] == "problem_aware"

    def test_invalid_enum_kept_flagged_low(self, tax):
        result = validate_card(good_draft() | {"mechanic": "The Sneaky Pete"}, tax)
        assert not result.ok
        assert any("mechanic" in i for i in result.issues)
        assert result.card["mechanic"] == "The Sneaky Pete"  # visible, not blanked
        assert result.card["field_confidence"]["mechanic"] == "low"

    def test_other_escape_hatch_allowed(self, tax):
        result = validate_card(good_draft() | {"format": "Other (recipe card)"}, tax)
        assert result.ok

    def test_video_only_format_rejected_on_static(self, tax):
        result = validate_card(good_draft() | {"format": "ASMR"}, tax)
        assert not result.ok

    def test_video_media_type_allows_video_formats(self, tax):
        result = validate_card(good_draft() | {"media_type": "video", "format": "ASMR"}, tax)
        assert result.ok

    def test_scan_path_string_coerced(self, tax):
        result = validate_card(good_draft() | {"scan_path": "headline → product → CTA"}, tax)
        assert result.ok
        assert result.card["scan_path"] == ["headline", "product", "CTA"]

    def test_scan_path_too_short_is_issue(self, tax):
        result = validate_card(good_draft() | {"scan_path": ["headline"]}, tax)
        assert not result.ok

    def test_missing_steal_is_issue(self, tax):
        result = validate_card(good_draft() | {"steal": ""}, tax)
        assert any("steal" in i for i in result.issues)

    def test_secondary_same_as_primary_dropped(self, tax):
        result = validate_card(
            good_draft() | {"secondary_mechanic": "The Trojan Horse"}, tax)
        assert result.card["secondary_mechanic"] is None
        assert any("secondary_mechanic" in w for w in result.warnings)

    def test_other_secondary_dropped_not_blocking(self, tax):
        # Regression: first live card (Huel, 2026-07-08) — the model emitted
        # an Other(...) secondary and the save was blocked. Optional field →
        # drop to null with a warning, never a blocking issue.
        result = validate_card(
            good_draft() | {"secondary_mechanic":
                            "Other (familiar food as benchmark proof)"}, tax)
        assert result.ok
        assert result.card["secondary_mechanic"] is None
        assert any("dropped" in w for w in result.warnings)

    def test_unmatched_secondary_dropped_not_blocking(self, tax):
        result = validate_card(
            good_draft() | {"secondary_mechanic": "The Sneaky Pete"}, tax)
        assert result.ok
        assert result.card["secondary_mechanic"] is None

    def test_wordy_why_it_works_warns(self, tax):
        result = validate_card(good_draft() | {"why_it_works": "word " * 50}, tax)
        assert result.ok
        assert any("why_it_works" in w for w in result.warnings)

    def test_defaults_fill(self, tax):
        draft = good_draft() | {"brand": "", "proxy_signal": "", "cultural_note": ""}
        result = validate_card(draft, tax)
        assert result.card["brand"] == "unknown"
        assert result.card["proxy_signal"] == "unknown"
        assert result.card["cultural_note"] == "none"


class TestParseCorrections:
    def test_comma_and_newline_pairs(self):
        pairs = parse_corrections("mechanic = The Reframe, awareness = solution aware\n"
                                  "hook = warning")
        assert ("mechanic", "The Reframe") in pairs
        assert ("awareness", "solution aware") in pairs
        assert ("hook", "warning") in pairs

    def test_value_with_comma_survives(self):
        pairs = parse_corrections("steal = the receipt total, big and bold")
        assert pairs == [("steal", "the receipt total, big and bold")]

    def test_non_pairs_ignored(self):
        assert parse_corrections("looks good to me") == []


class TestApplyCorrections:
    def test_exact_correction(self, tax):
        card, report = apply_corrections(good_draft(), "mechanic = The Reframe", tax)
        assert card["mechanic"] == "The Reframe"
        assert report.applied and not report.rejected
        assert card["field_confidence"]["mechanic"] == "high"

    def test_fuzzy_correction_flagged_for_confirm(self, tax):
        card, report = apply_corrections(good_draft(), "awareness = solution", tax)
        assert card["awareness_stage"] == "solution_aware"
        assert report.fuzzy

    def test_unknown_field_rejected(self, tax):
        _, report = apply_corrections(good_draft(), "vibe = immaculate", tax)
        assert report.rejected

    def test_unmatched_value_rejected_not_guessed(self, tax):
        card, report = apply_corrections(good_draft(), "mechanic = The Sneaky Pete", tax)
        assert card["mechanic"] == "The Trojan Horse"  # unchanged
        assert report.rejected

    def test_secondary_none_clears(self, tax):
        draft = good_draft() | {"secondary_mechanic": "The Reframe"}
        card, report = apply_corrections(draft, "secondary = none", tax)
        assert card["secondary_mechanic"] is None
        assert "secondary_mechanic = none" in report.applied

    def test_scan_path_correction(self, tax):
        card, _ = apply_corrections(good_draft(), "scan_path = badge -> product -> price", tax)
        assert card["scan_path"] == ["badge", "product", "price"]

    def test_free_text_field_correction(self, tax):
        card, report = apply_corrections(good_draft(), "steal = the proof stacking order", tax)
        assert card["steal"] == "the proof stacking order"
        assert report.applied

    def test_corrected_mechanic_clears_stale_model_reasoning(self, tax):
        card, _ = apply_corrections(good_draft(), "mechanic = The Reframe", tax)
        assert card["reasoning"]["mechanic"] == "(corrected by reviewer)"
        assert card["reasoning"]["awareness_stage"] == "targets a felt pain"  # untouched

    def test_same_value_correction_keeps_reasoning(self, tax):
        card, _ = apply_corrections(good_draft(), "mechanic = The Trojan Horse", tax)
        assert card["reasoning"]["mechanic"] == "native format smuggles the ad"


class TestRenderDisplay:
    def test_low_confidence_gets_warning_prefix(self, tax):
        draft = good_draft()
        draft["field_confidence"]["mechanic"] = "low"
        display = render_display(validate_card(draft, tax).card)
        assert "⚠️ *Mechanic:*" in display
        assert "*Format:* Billboard" in display
        assert "⚠️ *Format:*" not in display

    def test_card_id_and_status_shown(self, tax):
        display = render_display(good_draft(), card_id="AD-007", status="needs-strategist")
        assert "AD-007" in display and "needs-strategist" in display


class TestSidecarIO:
    def _save(self, root, tax, image=None, status="approved", **overrides):
        return save_card(
            good_draft() | overrides, status=status, image_path=image, tax=tax,
            provenance={"model": "claude-test", "taxonomy_version": tax.version,
                        "analyzed_at": "2026-07-06T00:00:00+00:00"},
            added_by="devin", root=root)

    def test_sequential_ids_and_roundtrip(self, tmp_path, tax):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"fakejpg")
        card_id, path = self._save(tmp_path, tax, image=img)
        assert card_id == "AD-001"
        card_id2, _ = self._save(tmp_path, tax)
        assert card_id2 == "AD-002"
        assert next_card_id(tmp_path) == "AD-003"

        loaded = load_card("AD-001", root=tmp_path)
        assert loaded["brand"] == "Soft Services"
        assert loaded["analysis"]["mechanic"] == "The Trojan Horse"
        assert loaded["analysis"]["status"] == "approved"
        assert loaded["assets"]["primary"] == "ad-001.jpg"
        assert (path.parent / "ad-001.jpg").read_bytes() == b"fakejpg"
        assert len(load_all_cards(tmp_path)) == 2

    def test_sidecar_is_valid_yaml_with_provenance(self, tmp_path, tax):
        _, path = self._save(tmp_path, tax)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["provenance"]["model"] == "claude-test"
        assert data["analysis"]["field_confidence"]["format"] == "high"

    def test_save_with_issues_raises(self, tmp_path, tax):
        with pytest.raises(ValueError, match="unresolved issues"):
            self._save(tmp_path, tax, steal="")

    def test_bad_status_raises(self, tmp_path, tax):
        with pytest.raises(ValueError, match="status"):
            self._save(tmp_path, tax, status="looks-fine")

    def test_update_closes_escalation_with_trail(self, tmp_path, tax):
        self._save(tmp_path, tax, status="needs-strategist")
        sidecar, report = update_card(
            "AD-001", corrections="mechanic = The Reframe", status="approved",
            strategist_notes="classic reframe", updated_by="@strategist",
            tax=tax, root=tmp_path)
        assert sidecar["analysis"]["mechanic"] == "The Reframe"
        assert sidecar["analysis"]["status"] == "approved"
        assert sidecar["analysis"]["strategist_notes"] == "classic reframe"
        trail = sidecar["provenance"]["corrections"]
        assert any("The Reframe" in line and "@strategist" in line for line in trail)
        assert any("status = approved" in line for line in trail)

    def test_update_missing_card_raises(self, tmp_path, tax):
        with pytest.raises(FileNotFoundError):
            update_card("AD-404", status="approved", tax=tax, root=tmp_path)
