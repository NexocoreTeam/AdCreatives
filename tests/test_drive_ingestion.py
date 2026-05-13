"""Tests for the Drive ingestion pipeline.

Covers the deterministic pieces — DriveFile dataclass behavior, the cache's
staleness logic, brand-merge logic, JSON parsing, and the PDF page-selection
heuristic. Does NOT exercise the Drive API or LLM calls (those would test
Google/Anthropic, not us). For end-to-end validation, see the live smoke
test commands.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from models.brand import Brand, ColorPalette, Typography, VisualIdentity
from strategy.brand_enricher import (
    _diff_brand,
    _is_valid_hex,
    _merge_into_brand,
    _parse_json_response,
    _select_key_pages,
)
from strategy.drive_cache import DriveCache, _safe_filename
from strategy.drive_client import DriveFile, FOLDER_MIME


# ─── DriveFile ──────────────────────────────────────────────────────────────


class TestDriveFile:
    def test_cache_key_combines_id_and_modified_time(self):
        f = DriveFile(
            id="abc123",
            name="brandbook.pdf",
            mime_type="application/pdf",
            size=12345,
            modified_time="2026-05-12T10:00:00Z",
            parent_id="parent1",
        )
        assert f.cache_key == "abc123:2026-05-12T10:00:00Z"

    def test_cache_key_changes_when_modified_time_changes(self):
        a = DriveFile("id1", "x.png", "image/png", 1, "T1", "p")
        b = DriveFile("id1", "x.png", "image/png", 1, "T2", "p")
        assert a.cache_key != b.cache_key

    def test_is_folder_image_video_pdf(self):
        folder = DriveFile("1", "f", FOLDER_MIME, 0, "T", "p")
        image = DriveFile("2", "i.png", "image/png", 1, "T", "p")
        video = DriveFile("3", "v.mp4", "video/mp4", 1, "T", "p")
        pdf = DriveFile("4", "b.pdf", "application/pdf", 1, "T", "p")
        assert folder.is_folder and not folder.is_image
        assert image.is_image and not image.is_video
        assert video.is_video and not video.is_image
        assert pdf.is_pdf and not pdf.is_image


# ─── DriveCache ─────────────────────────────────────────────────────────────


class TestDriveCache:
    @pytest.fixture
    def drive_file(self) -> DriveFile:
        return DriveFile(
            id="fileA",
            name="logo.png",
            mime_type="image/png",
            size=1024,
            modified_time="2026-05-12T10:00:00Z",
            parent_id="brandfolder",
        )

    def _make_cache(self, tmp_path: Path) -> DriveCache:
        """Build a cache scoped to a temp client dir, not the real clients/."""
        from strategy import drive_cache

        original = drive_cache.CLIENTS_DIR
        drive_cache.CLIENTS_DIR = tmp_path
        cache = DriveCache("testclient")
        # Restore module global so subsequent tests aren't poisoned. The cache
        # instance keeps its own resolved `dir` path so its behavior is correct.
        drive_cache.CLIENTS_DIR = original
        return cache

    def test_put_then_get_returns_entry(self, tmp_path, drive_file):
        cache = self._make_cache(tmp_path)
        cache.put(drive_file, "brand_images", {"aesthetic": "playful"})
        entry = cache.get(drive_file)
        assert entry is not None
        assert entry.analyzer == "brand_images"
        assert entry.payload == {"aesthetic": "playful"}

    def test_get_returns_none_when_no_entry(self, tmp_path, drive_file):
        cache = self._make_cache(tmp_path)
        assert cache.get(drive_file) is None

    def test_get_returns_none_when_modified_time_changes(self, tmp_path, drive_file):
        cache = self._make_cache(tmp_path)
        cache.put(drive_file, "brand_images", {"aesthetic": "playful"})

        stale = DriveFile(
            id=drive_file.id,
            name=drive_file.name,
            mime_type=drive_file.mime_type,
            size=drive_file.size,
            modified_time="2026-06-01T12:00:00Z",  # different
            parent_id=drive_file.parent_id,
        )
        assert cache.get(stale) is None, "stale entry must not be returned"

    def test_invalidate_removes_entry(self, tmp_path, drive_file):
        cache = self._make_cache(tmp_path)
        cache.put(drive_file, "brand_images", {"x": 1})
        cache.invalidate(drive_file)
        assert cache.get(drive_file) is None

    def test_safe_filename_sanitizes_special_chars(self):
        assert "/" not in _safe_filename("abc/def", "../weird name.png")
        assert "../" not in _safe_filename("xyz", "../../bad.pdf")


# ─── _parse_json_response ───────────────────────────────────────────────────


class TestParseJsonResponse:
    def test_parses_clean_json(self):
        data = _parse_json_response('{"a": 1, "b": [2, 3]}', "brand_images")
        assert data == {"a": 1, "b": [2, 3]}

    def test_strips_markdown_fences(self):
        data = _parse_json_response('```json\n{"a": 1}\n```', "brand_images")
        assert data == {"a": 1}

    def test_strips_bare_fences(self):
        data = _parse_json_response('```\n{"a": 1}\n```', "brand_pdf")
        assert data == {"a": 1}

    def test_falls_back_to_yaml(self):
        # Valid YAML, invalid JSON (single quotes)
        text = "a: 1\nb: [2, 3]"
        data = _parse_json_response(text, "brand_pdf")
        assert data == {"a": 1, "b": [2, 3]}

    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match="Empty"):
            _parse_json_response("", "brand_images")

    def test_raises_on_unparseable(self):
        with pytest.raises(ValueError, match="parse"):
            _parse_json_response("{ this is { not valid", "brand_images")


# ─── _is_valid_hex ──────────────────────────────────────────────────────────


class TestIsValidHex:
    @pytest.mark.parametrize("value", ["#FF6B35", "#000000", "#ffffff", "#aBc123"])
    def test_accepts_six_digit_hex(self, value):
        assert _is_valid_hex(value)

    @pytest.mark.parametrize(
        "value",
        ["FF6B35", "#FFF", "#GGGGGG", "rgb(255,0,0)", "", "#1234567", "  #FF6B35  "],
    )
    def test_rejects_invalid(self, value):
        assert not _is_valid_hex(value)


# ─── _merge_into_brand ──────────────────────────────────────────────────────


class TestMergeIntoBrand:
    def _brand(self) -> Brand:
        return Brand(
            name="Test",
            colors=ColorPalette(primary="", secondary="", background="#FFFFFF"),
            typography=Typography(heading="", body=""),
            visual_identity=VisualIdentity(aesthetic="existing aesthetic"),
            guidelines_notes="existing notes",
        )

    def _drive_file(self, name: str) -> DriveFile:
        return DriveFile(name, name, "application/pdf", 1, "T", "p")

    def test_image_analysis_updates_visual_identity(self):
        brand = self._brand()
        image_analysis = {
            "visual_identity": {
                "aesthetic": "playful retro",
                "design_language": "flat illustration",
                "mood": ["playful", "nostalgic", "optimistic"],
                "notable_visual_signatures": ["arched wordmark"],
            }
        }
        merged = _merge_into_brand(brand, image_analysis, [])
        assert merged.visual_identity.aesthetic == "playful retro"
        assert merged.visual_identity.design_language == "flat illustration"
        assert merged.visual_identity.mood == ["playful", "nostalgic", "optimistic"]
        assert merged.visual_identity.notable_visual_signatures == ["arched wordmark"]

    def test_image_analysis_ignored_when_none(self):
        brand = self._brand()
        merged = _merge_into_brand(brand, None, [])
        assert merged.visual_identity.aesthetic == "existing aesthetic"

    def test_pdf_analysis_applies_hex_codes(self):
        brand = self._brand()
        pdf_analysis = {
            "colors": {"primary": "#FF6B35", "secondary": "#1A1A1A", "accent": "#FFD700"},
            "typography": {"heading": "Knockout HTF66", "body": "Untitled Sans"},
        }
        merged = _merge_into_brand(brand, None, [(self._drive_file("book.pdf"), pdf_analysis)])
        assert merged.colors.primary == "#FF6B35"
        assert merged.colors.secondary == "#1A1A1A"
        assert merged.colors.accent == "#FFD700"
        assert merged.typography.heading == "Knockout HTF66"
        assert merged.typography.body == "Untitled Sans"

    def test_pdf_analysis_rejects_invalid_hex(self):
        brand = self._brand()
        pdf_analysis = {"colors": {"primary": "not-a-hex", "secondary": "#FF6B35"}}
        merged = _merge_into_brand(brand, None, [(self._drive_file("b.pdf"), pdf_analysis)])
        assert merged.colors.primary == "", "invalid hex should be ignored"
        assert merged.colors.secondary == "#FF6B35"

    def test_voice_rules_append_to_guidelines_notes(self):
        brand = self._brand()
        pdf_analysis = {
            "voice_rules": ["Never use exclamation points.", "Em-dashes for emphasis."],
            "guidelines_notes": "Bold but never aggressive.",
        }
        merged = _merge_into_brand(brand, None, [(self._drive_file("voice.pdf"), pdf_analysis)])
        assert "existing notes" in merged.guidelines_notes
        assert "Never use exclamation points" in merged.guidelines_notes
        assert "Em-dashes for emphasis" in merged.guidelines_notes
        assert "Bold but never aggressive" in merged.guidelines_notes
        assert "voice.pdf" in merged.guidelines_notes  # provenance tag

    def test_later_pdf_wins_for_atomic_fields(self):
        brand = self._brand()
        first = {"colors": {"primary": "#FF0000"}}
        second = {"colors": {"primary": "#00FF00"}}
        merged = _merge_into_brand(
            brand,
            None,
            [
                (self._drive_file("first.pdf"), first),
                (self._drive_file("second.pdf"), second),
            ],
        )
        assert merged.colors.primary == "#00FF00"

    def test_empty_string_skipped(self):
        brand = self._brand()
        brand.typography.heading = "Existing"
        pdf_analysis = {"typography": {"heading": "", "body": "  "}}
        merged = _merge_into_brand(brand, None, [(self._drive_file("p.pdf"), pdf_analysis)])
        assert merged.typography.heading == "Existing"
        assert merged.typography.body == ""


# ─── _diff_brand ────────────────────────────────────────────────────────────


class TestDiffBrand:
    def test_returns_empty_when_no_changes(self):
        a = Brand(name="X")
        b = Brand(name="X")
        assert _diff_brand(a, b) == []

    def test_detects_color_change(self):
        a = Brand(name="X", colors=ColorPalette(primary=""))
        b = Brand(name="X", colors=ColorPalette(primary="#FF6B35"))
        changes = _diff_brand(a, b)
        paths = [c.path for c in changes]
        assert "colors.primary" in paths

    def test_detects_list_change(self):
        a = Brand(name="X", visual_identity=VisualIdentity(mood=["calm"]))
        b = Brand(name="X", visual_identity=VisualIdentity(mood=["playful", "nostalgic"]))
        changes = _diff_brand(a, b)
        paths = [c.path for c in changes]
        assert "visual_identity.mood" in paths


# ─── _select_key_pages ──────────────────────────────────────────────────────


class TestSelectKeyPages:
    def test_picks_pages_with_palette_keywords(self):
        text = "\f".join(
            [
                "Cover page",
                "Mission statement",
                "Color palette\nPrimary: #FF6B35\nSecondary: #1A1A1A",
                "Typography\nHeading: Knockout\nBody: Untitled Sans",
                "Random page",
                "Voice and tone rules\nDon't be preachy",
            ]
        )
        chosen = _select_key_pages(text, page_count=6)
        # First page always included
        assert 0 in chosen
        # Palette page (index 2) has highest score
        assert 2 in chosen
        # Typography page (index 3) included
        assert 3 in chosen
        # Voice page (index 5) included
        assert 5 in chosen

    def test_always_includes_first_page(self):
        text = "\f".join([f"page {i}" for i in range(20)])  # all generic
        chosen = _select_key_pages(text, page_count=20)
        assert 0 in chosen

    def test_caps_at_pdf_max_pages_for_vision(self):
        from strategy.brand_enricher import PDF_MAX_PAGES_FOR_VISION

        text = "\f".join(
            ["color palette swatch hex"] * 20
        )  # every page maximally relevant
        chosen = _select_key_pages(text, page_count=20)
        assert len(chosen) <= PDF_MAX_PAGES_FOR_VISION


# ─── DriveClient init (no network) ──────────────────────────────────────────


class TestDriveClientInit:
    def test_raises_when_env_var_missing(self, monkeypatch):
        from strategy.drive_client import DriveClient

        monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
        with pytest.raises(EnvironmentError, match="GOOGLE_APPLICATION_CREDENTIALS"):
            DriveClient()

    def test_raises_when_key_file_missing(self, tmp_path, monkeypatch):
        from strategy.drive_client import DriveClient

        bogus = tmp_path / "missing.json"
        monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(bogus))
        with pytest.raises(FileNotFoundError, match="not found"):
            DriveClient()
