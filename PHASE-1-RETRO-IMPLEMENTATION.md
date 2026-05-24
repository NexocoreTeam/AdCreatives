# Phase 1 Retro — Implementation Report

Implementation of the 7 improvements from the `secondkind-bold` Phase 1
retrospective. All work is on the working tree (uncommitted) — review with
`git diff` and `git status`.

## Status

| # | Improvement | Status | Notes |
|---|-------------|--------|-------|
| 1 | First-class `adc ugc-ad` command | done | Registry + brief layouts; brand-driven style; auto warns on disallowed CTAs |
| 2 | Brief-driven `text_layout` | done | `TextOverlay` model + `CreativeBrief.text_layout` field; migration script seeded 4 per-concept YAMLs |
| 3 | Brand-level `ugc_voice` spec | done | `UgcVoice` Pydantic model + populated `secondkind-bold` brand.yaml |
| 4 | `adc fetch-references` | done | Drive folder mirror with cache; reads `brand.references.swipe_folder_id` |
| 5 | Cross-concept text leakage validator | done | `validators/brief_text_validator.py`; hooked into `save_brief` as non-blocking warning |
| 6 | Iteration metadata + ship-version pointer | done | `generators/ad_metadata.py`; wired into `adc edit`, `adc ugc-ad`, `adc creative-matrix --build`; `adc set-ship` command |
| 7 | Source-asset pre-generation validation | done | `validators/validated_assets.py`; seeded `secondkind-bold/validated_assets.yaml` with Posthiotic typo |

## Files added

- `generators/ugc_overlay.py` — promoted overlay renderer (importable; replaces hardcoded script logic)
- `generators/ad_metadata.py` — sidecar metadata writer + `set_ship_version`
- `validators/brief_text_validator.py` — cross-concept leakage detector
- `validators/validated_assets.py` — known-issue registry lookup
- `scripts/migrate_layouts_to_yaml.py` — one-shot dump of LAYOUTS dict to per-concept YAMLs
- `clients/secondkind-bold/validated_assets.yaml` — seeded with the Posthiotic typo
- `clients/secondkind-bold/ai-ads/phase-1/social-mirror/text-layout.yaml` — seeded layout
- `clients/secondkind-bold/ai-ads/phase-1/native-reel/text-layout-woman.yaml` — seeded layout
- `clients/secondkind-bold/ai-ads/phase-1/native-reel/text-layout-man.yaml` — seeded layout
- `clients/secondkind-bold/ai-ads/phase-1/pain-010/text-layout.yaml` — seeded layout
- `tests/test_ugc_overlay.py` — 26 new tests

## Files modified

- `cli.py` — added `ugc-ad`, `fetch-references`, `set-ship` commands; metadata writes in `edit` and `creative-matrix --build`; validated-asset warnings in `edit`
- `models/brand.py` — `UgcVoice`, `ReferencesConfig` models added to `Brand`
- `models/brief.py` — `TextOverlay` model + `text_layout` and `source_matrix_row` fields on `CreativeBrief`
- `models/loader.py` — `save_brief` runs the text validator (soft warnings)
- `scripts/native_ugc_overlay.py` — gutted to a thin wrapper around `generators/ugc_overlay.py` (legacy invocation still works)
- `clients/secondkind-bold/brand.yaml` — added `ugc_voice` + `references` blocks

## How to use

```bash
# Discover registry layouts
adc ugc-ad --list-layouts

# Render with a registry layout
adc ugc-ad \
  --base clients/secondkind-bold/ai-ads/phase-1/social-mirror/clean-base.png \
  --layout social-mirror \
  --brand secondkind-bold \
  --output clients/secondkind-bold/ai-ads/phase-1/social-mirror/v14-ship.png

# Render with a brief that carries a text_layout block
adc ugc-ad \
  --base clients/secondkind-bold/ai-ads/phase-1/pain-010/clean-base-native.png \
  --brief clients/secondkind-bold/briefs/my-brief.yaml \
  --output clients/secondkind-bold/ai-ads/phase-1/pain-010/v5-ship.png

# Re-seed per-concept text-layout.yaml files from the Python registry
python scripts/migrate_layouts_to_yaml.py --client secondkind-bold

# Promote a version to ship (creates current.png + demotes prior ship)
adc set-ship \
  --concept clients/secondkind-bold/ai-ads/phase-1/social-mirror \
  --version v13-pil-brand-marigold.png

# Mirror a Drive folder of reference ads into the client's raw/ cache
adc fetch-references --client secondkind-bold --folder <drive_folder_id>

# Or set brand.references.swipe_folder_id and just run:
adc fetch-references --client secondkind-bold
```

### What changed in the brief schema

`CreativeBrief` now carries two new optional fields:

- `text_layout: list[TextOverlay] | None`  — overlay caption boxes / pills for the hybrid UGC pipeline. `TextOverlay` has `text`, `y_pct`, `font_size_pct`, `kind` (`box` | `pill`), and optional `emoji`.
- `source_matrix_row: str | None`  — the creative-matrix row this brief was derived from (e.g. `pain-010`). Drives the cross-concept text-leakage validator that runs at `save_brief` time.

### What changed in brand.yaml

Two new optional top-level keys:

- `ugc_voice` — register, approved/disallowed CTAs, pill / box colors, platform-keyed font + emoji-font fallbacks. Reasonable defaults if absent.
- `references.swipe_folder_id` — Drive folder ID for `adc fetch-references` to default to.

### Metadata sidecars

Each generated ad now gets `<filename>.meta.yaml`:

```yaml
version: v13-pil-brand-marigold
timestamp: '2026-05-24T07:50:00'
engine: pil-overlay
prompt_or_layout: social-mirror
references_used:
  - clients/secondkind-bold/ai-ads/phase-1/social-mirror/clean-base.png
ship_status: ship  # or alt | superseded
brief_id: ''
notes: adc ugc-ad on brand=secondkind-bold
```

`adc set-ship` updates one sidecar to `ship`, demotes prior winners to
`superseded`, and creates `current.png` (symlink on POSIX / Dev-Mode
Windows; otherwise a copy) plus `current.png.meta.yaml` pointing at the
chosen filename.

## Tests

26 new tests in `tests/test_ugc_overlay.py`; all 289 tests pass (excluding
the pre-existing `test_ad_remixer.py` collection error from
`strategy/ad_remixer.py:1098` — unrelated to this work).

```
============================= test session starts =============================
platform win32 -- Python 3.11.9, pytest-9.0.3, pluggy-1.6.0
configfile: pyproject.toml
collected 289 items

tests\test_angle_multiplier.py ......................                    [  7%]
tests\test_awareness_mapper.py ......................                    [ 15%]
tests\test_competitive_context.py ..................                     [ 21%]
tests\test_copy_checker.py ....................                          [ 28%]
tests\test_creative_matrix.py ...................                        [ 34%]
tests\test_drive_ingestion.py ........................................   [ 48%]
tests\test_gap_analyzer.py .......                                       [ 51%]
tests\test_naming.py ............................................... ... [ 68%]
tests\test_psychology_profiler.py ..........................             [ 77%]
tests\test_tier3_scrapers.py .....................                       [ 85%]
tests\test_trending.py .................                                 [ 91%]
tests\test_ugc_overlay.py ..........................                     [100%]

============================= 289 passed in 4.33s =============================
```

End-to-end CLI also exercised (no money spent — these all hit local files):

- `adc ugc-ad --list-layouts` → prints 4 registry layouts
- `adc ugc-ad --base ... --layout social-mirror --brand secondkind-bold --output ...` → renders, writes sidecar
- `adc ugc-ad --base ... --brief <yaml-with-text_layout> --output ...` → renders brief-driven, writes sidecar
- `adc ugc-ad --base <_refs/gut-balance-product.png> ...` → emits the Posthiotic warning before render
- `adc set-ship --concept .../social-mirror --version v13-pil-brand-marigold.png` → demoted prior ship, created `current.png`, wrote pointer sidecar

## Follow-ups / clarifications needed

- **`adc fetch-references` not run live** — needs Drive credentials + a real folder ID to exercise end-to-end. Code mirrors the existing `analyze_references_from_drive_folder` pattern (DriveClient + DriveCache) so it should work; if Drive perms surface a new error path, log it and we can extend the error handling.
- **`base_image` inference from briefs** — the `adc ugc-ad` command currently requires `--base` explicitly even when `--brief` is provided. The brief schema does not yet carry a `base_image_path` field; we left this as a follow-up since the retro didn't define one.
- **Pre-existing test_ad_remixer.py syntax error** — `strategy/ad_remixer.py:1098` has an f-string parse error that prevents collection of one test file. Out of scope for this work but worth a separate fix.
- **`current.png` symlinks on Windows** — `os.symlink` requires Developer Mode or admin on Windows. We fall back to `shutil.copy2` automatically, but operators should know that the pointer is a copy unless Dev Mode is enabled.
- **`UgcVoice.register` field** — Pydantic v2 reserves `register` as a classmethod on `BaseModel`. The on-disk YAML key stays `register` (via alias) but the Python attribute is `voice_register`. Documented in the model's docstring.
- **Brand-voice validation in matrix --build path** — `adc creative-matrix --build static` now writes ad sidecar metadata but does NOT run the disallowed-CTA validator (no overlay step). The validator fires only on `adc ugc-ad`. Worth wiring if `--build static` ever grows an overlay phase.
