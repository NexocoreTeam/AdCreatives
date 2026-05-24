"""Tests for the hybrid UGC overlay pipeline.

Covers:
  - generators.ugc_overlay rendering primitives (registry + brief layouts)
  - models.brand.UgcVoice load/round-trip
  - models.brief.TextOverlay round-trip + CreativeBrief.text_layout
  - validators.brief_text_validator cross-concept leakage detection
  - validators.validated_assets known-issue lookup
  - generators.ad_metadata sidecar write + set_ship_version
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from PIL import Image

from generators.ad_metadata import (
    metadata_path_for,
    set_ship_version,
    write_ad_metadata,
)
from generators.ugc_overlay import (
    DEFAULT_UGC_STYLE,
    LAYOUTS,
    BoxStyle,
    PillStyle,
    UgcStyle,
    find_disallowed_ctas,
    list_layouts,
    render_native_ugc_ad,
    text_overlays_from_layout,
)
from models.brand import Brand, UgcVoice
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief, TextOverlay
from validators.brief_text_validator import validate_brief_text
from validators.validated_assets import find_issues_for_paths, load_issues


# ─── Fixtures ───────────────────────────────────────────────────────────────


def _make_base_image(path: Path, size: tuple[int, int] = (480, 640)) -> Path:
    """Build a tiny solid-color PNG to render onto."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, color=(120, 80, 50))
    img.save(path)
    return path


@pytest.fixture
def base_image(tmp_path: Path) -> Path:
    return _make_base_image(tmp_path / "base.png")


# ─── Registry layouts ───────────────────────────────────────────────────────


def test_list_layouts_contains_seed_concepts():
    names = list_layouts()
    for expected in ("social-mirror", "native-reel-woman", "native-reel-man", "native-pain-010"):
        assert expected in names


def test_text_overlays_from_layout_returns_dicts():
    overlays = text_overlays_from_layout("social-mirror")
    assert len(overlays) == len(LAYOUTS["social-mirror"])
    first = overlays[0]
    assert set(first.keys()) == {"text", "y_pct", "font_size_pct", "kind", "emoji"}
    assert isinstance(first["y_pct"], float)


def test_text_overlays_from_layout_raises_for_unknown():
    with pytest.raises(KeyError):
        text_overlays_from_layout("does-not-exist")


# ─── Renderer ───────────────────────────────────────────────────────────────


def test_render_with_registry_layout_writes_file(base_image: Path, tmp_path: Path):
    out = tmp_path / "out.png"
    result = render_native_ugc_ad(base_image, out, layout="social-mirror")
    assert result == out
    assert out.exists() and out.stat().st_size > 0
    # File should be readable as a valid image
    with Image.open(out) as im:
        assert im.size == (480, 640)


def test_render_with_brief_layout_uses_overlays(base_image: Path, tmp_path: Path):
    overlays = [
        TextOverlay(text="hello", y_pct=0.1, font_size_pct=3.0, kind="box"),
        TextOverlay(text="world", y_pct=0.5, font_size_pct=2.5, kind="pill", emoji=None),
    ]
    out = tmp_path / "brief-out.png"
    render_native_ugc_ad(base_image, out, layout=overlays)
    assert out.exists() and out.stat().st_size > 0


def test_render_missing_base_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        render_native_ugc_ad(tmp_path / "missing.png", tmp_path / "out.png")


# ─── Brand UgcVoice round-trip ──────────────────────────────────────────────


def test_ugc_voice_load_from_yaml_dict():
    raw = {
        "register": "wry, peer-recommendation",
        "approved_ctas": ["trust me ↓"],
        "do_not_use_ctas": ["shop now →"],
        "pill_highlight_color": "#fcb348",
        "pill_text_color": "#1c1917",
        "box_bg_color": "#ffffff",
        "box_text_color": "#000000",
        "font_preference": "segoe_ui_bold",
        "font_fallback": {"windows": "C:/Windows/Fonts/segoeuib.ttf"},
        "emoji_font_fallback": {"windows": "C:/Windows/Fonts/seguiemj.ttf"},
    }
    voice = UgcVoice(**raw)
    # The YAML key "register" is aliased to the Python attribute voice_register
    assert voice.voice_register == "wry, peer-recommendation"
    assert voice.approved_ctas == ["trust me ↓"]
    assert voice.do_not_use_ctas == ["shop now →"]
    assert voice.pill_highlight_color == "#fcb348"


def test_ugc_voice_optional_when_absent():
    """A Brand with no ugc_voice key should still construct."""
    b = Brand(name="Test", code="TST")
    assert b.ugc_voice is not None
    assert b.ugc_voice.voice_register == ""
    assert b.ugc_voice.approved_ctas == []


def test_secondkind_bold_brand_loads_ugc_voice():
    """The real secondkind-bold brand.yaml carries a populated ugc_voice."""
    from models.loader import load_brand
    b = load_brand("secondkind-bold")
    assert b.ugc_voice.voice_register, "ugc_voice.register should be populated"
    assert len(b.ugc_voice.approved_ctas) > 0
    assert b.ugc_voice.pill_highlight_color == "#fcb348"
    assert "windows" in b.ugc_voice.font_fallback


def test_ugc_style_from_brand_voice():
    voice = UgcVoice(
        pill_highlight_color="#ff0000",
        pill_text_color="#00ff00",
        box_bg_color="#0000ff",
        box_text_color="#ffffff",
        font_fallback={"windows": "C:/Windows/Fonts/segoeuib.ttf"},
        emoji_font_fallback={"windows": "C:/Windows/Fonts/seguiemj.ttf"},
    )
    style = UgcStyle.from_brand_voice(voice)
    assert style.pill.bg_color == (255, 0, 0)
    assert style.pill.text_color == (0, 255, 0)
    assert style.box.bg_color == (0, 0, 255)
    assert style.box.text_color == (255, 255, 255)


def test_ugc_style_from_none_uses_defaults():
    style = UgcStyle.from_brand_voice(None)
    assert style.pill.bg_color == (252, 179, 72)  # default marigold
    assert style.box.bg_color == (255, 255, 255)


# ─── Brief TextOverlay round-trip ───────────────────────────────────────────


def _minimal_brief(text_layout=None, source_matrix_row=None) -> CreativeBrief:
    return CreativeBrief(
        brief_id="test-1",
        client="secondkind-bold",
        product="Gut Balance",
        awareness_level=AwarenessLevel.PROBLEM_AWARE,
        framework=CopyFramework.PAS,
        angle="x",
        hook="y",
        text_layout=text_layout,
        source_matrix_row=source_matrix_row,
    )


def test_text_layout_round_trips_through_yaml(tmp_path: Path):
    overlays = [
        TextOverlay(text="hello", y_pct=0.1, font_size_pct=2.5, kind="box"),
        TextOverlay(text="world", y_pct=0.5, font_size_pct=2.5, kind="pill", emoji="💀"),
    ]
    brief = _minimal_brief(text_layout=overlays)
    path = tmp_path / "brief.yaml"
    path.write_text(
        yaml.safe_dump(brief.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    loaded_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    loaded = CreativeBrief(**loaded_data)
    assert loaded.text_layout is not None
    assert len(loaded.text_layout) == 2
    assert loaded.text_layout[0].text == "hello"
    assert loaded.text_layout[1].emoji == "💀"
    assert loaded.text_layout[1].kind == "pill"


def test_text_layout_rejects_bad_kind():
    with pytest.raises(Exception):
        TextOverlay(text="x", y_pct=0.5, font_size_pct=2.0, kind="square")


def test_text_layout_rejects_out_of_range_y():
    with pytest.raises(Exception):
        TextOverlay(text="x", y_pct=1.5, font_size_pct=2.0, kind="box")


# ─── Disallowed CTA detection ───────────────────────────────────────────────


def test_find_disallowed_ctas_flags_bad_phrase():
    voice = UgcVoice(do_not_use_ctas=["shop now →"])
    overlays = [
        {"text": "you're welcome ↓", "y_pct": 0.9, "font_size_pct": 2.0, "kind": "box", "emoji": None},
        {"text": "Shop Now → today", "y_pct": 0.95, "font_size_pct": 2.0, "kind": "box", "emoji": None},
    ]
    bad = find_disallowed_ctas(overlays, voice)
    assert len(bad) == 1
    assert bad[0][1] == "shop now →"


def test_find_disallowed_ctas_skips_when_no_voice():
    overlays = [{"text": "shop now", "y_pct": 0.9, "font_size_pct": 2.0, "kind": "box", "emoji": None}]
    assert find_disallowed_ctas(overlays, None) == []


# ─── Brief text validator (cross-concept leakage) ───────────────────────────


def _write_minimal_matrix(path: Path, rows: list[dict]) -> None:
    """Write a creative_matrix.yaml stub with the given rows in pain_vs_competitor."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "client": "test",
        "generated_at": "2026-05-23T00:00:00",
        "matrix_version": 1,
        "pain_vs_competitor": rows,
        "what_they_love": [],
        "wishes_gaps": [],
        "hook_angles": [],
    }
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_validate_brief_text_flags_leakage_from_other_row(tmp_path: Path):
    matrix_path = tmp_path / "creative_matrix.yaml"
    _write_minimal_matrix(matrix_path, [
        {
            "id": "pain-010",
            "complaint": "tried four probiotics nothing worked",
            "what_people_say": "you can stop trying new probiotics now",
            "static_treatment": "",
        },
        {
            "id": "pain-011",
            "complaint": "this is a totally separate concept about transparency",
            "what_people_say": "EpiCor RCT named published traceable",
            "static_treatment": "",
        },
    ])
    # Brief tied to pain-011 but its hero text comes from pain-010 — leakage.
    brief = _minimal_brief(source_matrix_row="pain-011")
    brief.hook = "you can stop trying new probiotics now"

    warnings = validate_brief_text(brief, matrix_path)
    leakage = [w for w in warnings if w.kind == "cross_concept_leakage"]
    assert any(w.matched_row_id == "pain-010" for w in leakage), (
        f"expected cross_concept_leakage flag on pain-010, got: {warnings}"
    )


def test_validate_brief_text_missing_source_row(tmp_path: Path):
    matrix_path = tmp_path / "creative_matrix.yaml"
    _write_minimal_matrix(matrix_path, [
        {
            "id": "pain-010",
            "complaint": "x",
            "what_people_say": "you can stop trying new probiotics now",
        },
    ])
    # Brief points at a row that doesn't exist
    brief = _minimal_brief(source_matrix_row="pain-999")
    brief.hook = "this is some entirely different opening line about gut bloat"
    warnings = validate_brief_text(brief, matrix_path)
    assert any(w.kind == "missing_in_source" for w in warnings)


def test_validate_brief_text_clean_when_source_matches(tmp_path: Path):
    matrix_path = tmp_path / "creative_matrix.yaml"
    _write_minimal_matrix(matrix_path, [
        {
            "id": "pain-010",
            "complaint": "",
            "what_people_say": "you can stop trying new probiotics now",
            "static_treatment": "",
        },
    ])
    brief = _minimal_brief(source_matrix_row="pain-010")
    brief.hook = "you can stop trying new probiotics now"
    warnings = validate_brief_text(brief, matrix_path)
    # No 'missing_in_source' warning since the text appears in pain-010
    assert not any(w.kind == "missing_in_source" for w in warnings)


def test_validate_brief_text_no_matrix_returns_empty(tmp_path: Path):
    brief = _minimal_brief()
    assert validate_brief_text(brief, tmp_path / "nonexistent.yaml") == []


# ─── Validated assets ───────────────────────────────────────────────────────


def test_validated_assets_loads_known_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    client_dir = tmp_path / "clients" / "demo"
    client_dir.mkdir(parents=True)
    (client_dir / "validated_assets.yaml").write_text(yaml.safe_dump({
        "known_issues": [
            {
                "file": "_refs/product.png",
                "issue": "label typo",
                "severity": "warning",
                "workaround": "fix at brand level",
            },
        ],
    }), encoding="utf-8")
    issues = load_issues("demo")
    assert len(issues) == 1
    assert issues[0].file == "_refs/product.png"
    assert issues[0].issue == "label typo"


def test_validated_assets_finds_suffix_match(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    client_dir = tmp_path / "clients" / "demo"
    client_dir.mkdir(parents=True)
    (client_dir / "validated_assets.yaml").write_text(yaml.safe_dump({
        "known_issues": [
            {"file": "_refs/product.png", "issue": "typo"},
        ],
    }), encoding="utf-8")
    matches = find_issues_for_paths("demo", [
        Path("clients/demo/ai-ads/phase-1/_refs/product.png"),
        Path("clients/demo/random-other.png"),
    ])
    assert len(matches) == 1
    assert matches[0][1].issue == "typo"


def test_secondkind_bold_validated_assets_has_postbiotic_issue():
    """The seeded secondkind-bold registry carries the Posthiotic typo issue."""
    issues = load_issues("secondkind-bold")
    assert any("Posthiotic" in i.issue or "Postbiotic" in i.issue for i in issues), (
        f"expected Postbiotic-typo issue, got: {[i.issue for i in issues]}"
    )


# ─── Ad metadata + set ship ─────────────────────────────────────────────────


def test_write_ad_metadata_creates_sidecar(tmp_path: Path):
    ad = tmp_path / "v1.png"
    ad.write_bytes(b"fake")
    meta = write_ad_metadata(
        ad,
        engine="pil-overlay",
        prompt_or_layout="social-mirror",
        ship_status="alt",
    )
    assert meta == metadata_path_for(ad)
    assert meta.exists()
    loaded = yaml.safe_load(meta.read_text(encoding="utf-8"))
    assert loaded["version"] == "v1"
    assert loaded["engine"] == "pil-overlay"
    assert loaded["ship_status"] == "alt"
    assert "timestamp" in loaded


def test_set_ship_version_demotes_previous_ship(tmp_path: Path):
    a = tmp_path / "v1.png"
    b = tmp_path / "v2.png"
    a.write_bytes(b"a")
    b.write_bytes(b"b")
    write_ad_metadata(a, ship_status="ship")
    write_ad_metadata(b, ship_status="alt")

    current = set_ship_version(tmp_path, "v2.png")

    # v1 should be demoted to superseded
    a_meta = yaml.safe_load(metadata_path_for(a).read_text(encoding="utf-8"))
    assert a_meta["ship_status"] == "superseded"
    # v2 should now be ship
    b_meta = yaml.safe_load(metadata_path_for(b).read_text(encoding="utf-8"))
    assert b_meta["ship_status"] == "ship"
    # current.png exists and is either a symlink or a copy
    assert current.exists()
    assert current.name.startswith("current")


def test_set_ship_version_raises_on_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        set_ship_version(tmp_path, "nonexistent.png")
