"""Brand enrichment from Drive — vision over images + PDF parsing → brand.yaml.

Pulls assets from the client's Drive `brand/` subfolder, runs LLM vision over
images (Gemini multi-image via OpenRouter, Claude vision fallback) and over key
pages of brand-book PDFs, then merges the structured results into the client's
brand.yaml.

System context is the brandbook-ingestion skill. Output is JSON-only (strict
escaping). All entries cached by Drive's modifiedTime so re-runs against
unchanged assets cost zero LLM calls.

Default mode is dry-run — `apply=True` is required to mutate brand.yaml.
"""

from __future__ import annotations

import base64
import io
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
import yaml
from PIL import Image

from models.brand import Brand
from models.loader import CLIENTS_DIR, load_brand
from models.skills import load_skill
from strategy.drive_cache import DriveCache
from strategy.drive_client import DriveClient, DriveFile
from strategy.llm import gemini_vision

MAX_IMAGE_WIDTH = 1024
PDF_PAGE_RENDER_SCALE = 2.0  # ~144 dpi
PDF_MAX_PAGES_FOR_VISION = 6
PALETTE_KEYWORDS = ("color", "colour", "palette", "swatch", "rgb", "cmyk", "hex")
TYPOGRAPHY_KEYWORDS = ("type", "typography", "font", "typeface", "specimen")
VOICE_KEYWORDS = ("voice", "tone", "language", "writing", "do ", "don't", "rules")
HEX_RE_PATTERN = r"^#[0-9A-Fa-f]{6}$"


# ─── Result data ────────────────────────────────────────────────────────────


@dataclass
class FieldChange:
    """One proposed change to brand.yaml. Used to render the diff."""

    path: str
    before: Any
    after: Any
    source_file: str  # the Drive filename that produced this change


@dataclass
class EnrichmentResult:
    """Outcome of an enrich-brand run. Used for both display and downstream tests."""

    changes: list[FieldChange] = field(default_factory=list)
    applied: bool = False
    images_analyzed: int = 0
    pdfs_analyzed: int = 0
    cache_hits: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (filename, reason)
    image_analysis: dict[str, Any] | None = None
    pdf_analyses: list[dict[str, Any]] = field(default_factory=list)


# ─── Public entry point ─────────────────────────────────────────────────────


def enrich_brand_from_drive(
    client_slug: str,
    *,
    apply: bool = False,
    force: bool = False,
    backup: bool = True,
) -> EnrichmentResult:
    """Pull `brand/` assets from Drive, vision-analyze, merge into brand.yaml.

    When `force=True`, ignores cached analyses and re-runs vision on every file.
    When `apply=True`, writes proposed changes back to brand.yaml (with backup
    by default). Otherwise returns the proposed changes without mutating.
    """
    brand = load_brand(client_slug)
    if not brand.drive_folder_id:
        raise ValueError(
            f"Client '{client_slug}' has no drive_folder_id in brand.yaml. "
            f"Set it to the Google Drive folder ID containing brand/ and "
            f"reference-ads/ subfolders."
        )

    drive = DriveClient()
    cache = DriveCache(client_slug)

    files = drive.list_subfolder(brand.drive_folder_id, "brand")
    images = [f for f in files if f.is_image]
    pdfs = [f for f in files if f.is_pdf]
    skipped: list[tuple[str, str]] = [
        (f.name, f"unsupported mime: {f.mime_type}")
        for f in files
        if not (f.is_image or f.is_pdf)
    ]

    if not images and not pdfs:
        raise ValueError(
            f"No supported assets found in Drive brand/ for client '{client_slug}'. "
            f"Drop logos, brand books, or mood boards into the folder and re-run."
        )

    result = EnrichmentResult(skipped=skipped)

    # ─── Image batch (one vision call covering all images) ───────────────────
    image_analysis: dict[str, Any] | None = None
    if images:
        anchor = images[0]
        cached = None if force else cache.get(anchor)
        if cached and cached.analyzer == "brand_images":
            image_analysis = cached.payload
            result.cache_hits += len(images)
        else:
            image_analysis = _analyze_image_batch(drive, images)
            for f in images:
                cache.put(f, "brand_images", image_analysis)
            result.images_analyzed = len(images)
        result.image_analysis = image_analysis

    # ─── PDFs (one vision call per PDF) ──────────────────────────────────────
    pdf_analyses: list[tuple[DriveFile, dict[str, Any]]] = []
    for pdf in pdfs:
        cached = None if force else cache.get(pdf)
        if cached and cached.analyzer == "brand_pdf":
            pdf_analyses.append((pdf, cached.payload))
            result.cache_hits += 1
            continue

        analysis = _analyze_pdf(drive, pdf)
        cache.put(pdf, "brand_pdf", analysis)
        pdf_analyses.append((pdf, analysis))
        result.pdfs_analyzed += 1
    result.pdf_analyses = [a for _, a in pdf_analyses]

    # ─── Merge into proposed brand changes ───────────────────────────────────
    proposed = _merge_into_brand(brand, image_analysis, pdf_analyses)
    result.changes = _diff_brand(brand, proposed)

    if apply and result.changes:
        _save_brand_yaml(client_slug, proposed, backup=backup)
        result.applied = True

    return result


# ─── Image batch analysis ───────────────────────────────────────────────────


def _analyze_image_batch(drive: DriveClient, images: list[DriveFile]) -> dict[str, Any]:
    """Run Gemini multi-image vision over all brand-asset images at once."""
    data_uris: list[str] = []
    for f in images:
        raw = drive.download_bytes(f.id)
        downscaled = _downscale_to_data_uri(raw, f.mime_type)
        data_uris.append(downscaled)

    system_prompt = (
        "You are an expert brand strategist analyzing visual identity from a set of "
        "brand assets a client has dropped into a folder. Apply the brandbook-ingestion "
        "skill (Mode B: brand_images) to extract visual_identity fields. Be specific. "
        "Never invent. Output JSON only.\n\n"
        "--- BRANDBOOK INGESTION SKILL ---\n\n"
        + load_skill("brandbook-ingestion")
    )

    asset_list = "\n".join(f"- {f.name} ({f.mime_type}, {f.size // 1024} KB)" for f in images)
    user_prompt = (
        f"Analyze these {len(images)} brand asset image(s) as a SET. They were all "
        f"dropped into the client's `brand/` Drive folder by their team.\n\n"
        f"Assets in order:\n{asset_list}\n\n"
        f"Output the brand_images JSON schema from the skill. No prose, no fences."
    )

    response = gemini_vision(
        prompt=user_prompt,
        image_urls=data_uris,
        system=system_prompt,
        max_tokens=2048,
    )
    return _parse_json_response(response, "brand_images")


# ─── PDF analysis ───────────────────────────────────────────────────────────


def _analyze_pdf(drive: DriveClient, pdf_file: DriveFile) -> dict[str, Any]:
    """Download a PDF, extract text + render key pages as images, run vision."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        pdf_path = tmp_path / pdf_file.name
        drive.download_to(pdf_file.id, pdf_path)

        text = _pdf_extract_text(pdf_path)
        page_data_uris = _pdf_render_key_pages(pdf_path, text)

    system_prompt = (
        "You are an expert brand strategist parsing a brand-book PDF. Apply the "
        "brandbook-ingestion skill (Mode A: brand_pdf). The text was extracted via "
        "pdftotext; the page images are the renderable pages most likely to contain "
        "palette, typography, and voice content. Be specific. Never invent hex codes. "
        "Output JSON only.\n\n"
        "--- BRANDBOOK INGESTION SKILL ---\n\n"
        + load_skill("brandbook-ingestion")
    )

    truncated_text = text[:8000]
    user_prompt = (
        f"Brand book filename: {pdf_file.name}\n"
        f"Total pages rendered: {len(page_data_uris)}\n\n"
        f"--- EXTRACTED TEXT (truncated to 8000 chars) ---\n"
        f"{truncated_text}\n\n"
        f"Output the brand_pdf JSON schema from the skill. No prose, no fences."
    )

    response = gemini_vision(
        prompt=user_prompt,
        image_urls=page_data_uris,
        system=system_prompt,
        max_tokens=2048,
    )
    return _parse_json_response(response, "brand_pdf")


def _pdf_extract_text(pdf_path: Path) -> str:
    """Run pdftotext -layout. Returns empty string if pdftotext not available."""
    if not shutil.which("pdftotext"):
        return ""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        return result.stdout if result.returncode == 0 else ""
    except (subprocess.SubprocessError, OSError):
        return ""


def _pdf_render_key_pages(pdf_path: Path, text: str) -> list[str]:
    """Render the most relevant pages of a PDF as data-URI PNGs.

    For PDFs ≤ PDF_MAX_PAGES_FOR_VISION pages, render all. Otherwise pick pages
    whose text contains palette / typography / voice keywords, then fall back to
    the first page if no matches.
    """
    doc = pdfium.PdfDocument(str(pdf_path))
    page_count = len(doc)

    if page_count <= PDF_MAX_PAGES_FOR_VISION:
        page_indices = list(range(page_count))
    else:
        page_indices = _select_key_pages(text, page_count)

    data_uris: list[str] = []
    for idx in page_indices:
        page = doc[idx]
        bitmap = page.render(scale=PDF_PAGE_RENDER_SCALE).to_pil()
        png_bytes = _pil_to_downscaled_png_bytes(bitmap)
        b64 = base64.b64encode(png_bytes).decode("ascii")
        data_uris.append(f"data:image/png;base64,{b64}")
        page.close()
    doc.close()
    return data_uris


def _select_key_pages(text: str, page_count: int) -> list[int]:
    """Pick pages by keyword presence (heuristic). Always include first page."""
    # pdftotext -layout emits form-feed (\f) between pages; split on it.
    pages_text = text.split("\f") if "\f" in text else [text]
    scored: list[tuple[int, int]] = []
    for i, page_text in enumerate(pages_text[:page_count]):
        lower = page_text.lower()
        score = 0
        for kw in PALETTE_KEYWORDS:
            score += 3 * lower.count(kw)
        for kw in TYPOGRAPHY_KEYWORDS:
            score += 2 * lower.count(kw)
        for kw in VOICE_KEYWORDS:
            score += 1 * lower.count(kw)
        scored.append((score, i))

    # Highest-scoring pages first, then fill from start
    scored.sort(reverse=True)
    chosen = {0}  # always include first page
    for _, idx in scored:
        if len(chosen) >= PDF_MAX_PAGES_FOR_VISION:
            break
        chosen.add(idx)
    return sorted(chosen)


# ─── Image utilities ────────────────────────────────────────────────────────


def _downscale_to_data_uri(raw: bytes, mime_type: str) -> str:
    """Decode → downscale (preserve aspect) → re-encode as PNG data URI."""
    img = Image.open(io.BytesIO(raw))
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")
    png_bytes = _pil_to_downscaled_png_bytes(img)
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _pil_to_downscaled_png_bytes(img: Image.Image) -> bytes:
    """Downscale to MAX_IMAGE_WIDTH preserving aspect, return PNG bytes."""
    if img.width > MAX_IMAGE_WIDTH:
        ratio = MAX_IMAGE_WIDTH / img.width
        new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


# ─── JSON parsing ───────────────────────────────────────────────────────────


def _parse_json_response(text: str, expected_mode: str) -> dict[str, Any]:
    """Parse the LLM's JSON output. Tolerates code fences + malformed JSON.

    Strategy:
    1. Strip markdown code fences if present
    2. Try strict json.loads (fastest path)
    3. Fall back to yaml.safe_load (forgiving of single quotes, missing commas)
    4. Fall back to json_repair (heuristic LLM-output fixer)
    5. Raise with diagnostic snippet of the response
    """
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()

    if not text:
        raise ValueError(f"Empty LLM response for {expected_mode}")

    # Path 1: strict JSON
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Path 2: YAML (handles single quotes, missing commas in many cases)
    try:
        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except yaml.YAMLError:
        pass

    # Path 3: json_repair — last-ditch for LLM-malformed JSON
    try:
        import json_repair

        repaired = json_repair.repair_json(text, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
    except Exception:
        pass

    raise ValueError(
        f"Could not parse {expected_mode} response as JSON, YAML, or via repair. "
        f"First 400 chars: {text[:400]!r}"
    )


# ─── Merge logic ────────────────────────────────────────────────────────────


def _merge_into_brand(
    brand: Brand,
    image_analysis: dict[str, Any] | None,
    pdf_analyses: list[tuple[DriveFile, dict[str, Any]]],
) -> Brand:
    """Apply image + PDF analyses to a copy of the Brand. Drive-derived wins on conflict.

    Strategy:
    - Image analysis updates `visual_identity` fields (descriptive).
    - PDF analyses update `colors`, `typography`, and append to `guidelines_notes`.
    - When multiple PDFs disagree, the last one wins for atomic fields; lists merge.
    """
    proposed = brand.model_copy(deep=True)

    if image_analysis:
        vi = image_analysis.get("visual_identity") or {}
        for key in (
            "aesthetic",
            "design_language",
            "photography_style",
            "typography_feel",
            "mascot_or_character",
            "color_mood",
        ):
            value = vi.get(key, "")
            if value and isinstance(value, str):
                setattr(proposed.visual_identity, key, value)
        for list_key in ("visual_references", "mood", "notable_visual_signatures"):
            new_list = vi.get(list_key) or []
            if new_list and isinstance(new_list, list):
                setattr(proposed.visual_identity, list_key, [str(x) for x in new_list])

    notes_lines: list[str] = []
    for pdf_file, pdf_analysis in pdf_analyses:
        colors = pdf_analysis.get("colors") or {}
        for slot in ("primary", "secondary", "background"):
            hex_val = colors.get(slot)
            if isinstance(hex_val, str) and _is_valid_hex(hex_val):
                setattr(proposed.colors, slot, hex_val)
        accent_val = colors.get("accent")
        if isinstance(accent_val, str) and _is_valid_hex(accent_val):
            proposed.colors.accent = accent_val

        typography = pdf_analysis.get("typography") or {}
        for slot in ("heading", "body"):
            value = typography.get(slot)
            if isinstance(value, str) and value.strip():
                setattr(proposed.typography, slot, value.strip())
        accent_font = typography.get("accent")
        if isinstance(accent_font, str) and accent_font.strip():
            proposed.typography.accent = accent_font.strip()

        voice_rules = pdf_analysis.get("voice_rules") or []
        logo_usage = pdf_analysis.get("logo_usage") or []
        gn = pdf_analysis.get("guidelines_notes") or ""

        for rule in voice_rules:
            if isinstance(rule, str) and rule.strip():
                notes_lines.append(f"[voice from {pdf_file.name}] {rule.strip()}")
        for rule in logo_usage:
            if isinstance(rule, str) and rule.strip():
                notes_lines.append(f"[logo from {pdf_file.name}] {rule.strip()}")
        if isinstance(gn, str) and gn.strip():
            notes_lines.append(f"[notes from {pdf_file.name}] {gn.strip()}")

    if notes_lines:
        existing = proposed.guidelines_notes.strip()
        appended = "\n".join(notes_lines)
        proposed.guidelines_notes = (
            f"{existing}\n\n{appended}" if existing else appended
        )

    return proposed


def _is_valid_hex(value: str) -> bool:
    import re

    return bool(re.match(HEX_RE_PATTERN, value))


# ─── Diff + save ────────────────────────────────────────────────────────────


def _diff_brand(before: Brand, after: Brand) -> list[FieldChange]:
    """Produce a flat list of (path, before, after) entries for changed fields."""
    changes: list[FieldChange] = []

    def compare(path: str, b: Any, a: Any) -> None:
        if b != a:
            changes.append(FieldChange(path=path, before=b, after=a, source_file=""))

    compare("colors.primary", before.colors.primary, after.colors.primary)
    compare("colors.secondary", before.colors.secondary, after.colors.secondary)
    compare("colors.background", before.colors.background, after.colors.background)
    compare("colors.accent", before.colors.accent, after.colors.accent)
    compare("typography.heading", before.typography.heading, after.typography.heading)
    compare("typography.body", before.typography.body, after.typography.body)
    compare("typography.accent", before.typography.accent, after.typography.accent)

    for slot in (
        "aesthetic",
        "design_language",
        "photography_style",
        "typography_feel",
        "mascot_or_character",
        "color_mood",
    ):
        compare(
            f"visual_identity.{slot}",
            getattr(before.visual_identity, slot),
            getattr(after.visual_identity, slot),
        )
    for slot in ("visual_references", "mood", "notable_visual_signatures"):
        compare(
            f"visual_identity.{slot}",
            getattr(before.visual_identity, slot),
            getattr(after.visual_identity, slot),
        )

    compare("guidelines_notes", before.guidelines_notes, after.guidelines_notes)

    return changes


def _save_brand_yaml(client_slug: str, brand: Brand, *, backup: bool) -> Path:
    """Write the merged Brand back to clients/<slug>/brand.yaml."""
    path = CLIENTS_DIR / client_slug / "brand.yaml"
    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            brand.model_dump(mode="json", exclude_none=True),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return path
