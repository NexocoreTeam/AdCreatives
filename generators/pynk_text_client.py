"""PYNK-style text-only ad generator (FAL wrapper).

Sends ONLY the product image to nano-banana-2/edit alongside a fully-filled
text prompt that describes the entire ad layout. NO reference ad image.

This is the B-variant in the A vs B drift experiment. The existing
reference-based path (generators/image_generator.py) is left untouched.

Layout decisions in this module:
    - image_urls is always [product_url] — single image, product-only.
    - aspect_ratio is locked from the Cooper template, not inferred.
    - Output folder structure mirrors PYNK's:
      ai-ads/<client>/text-only/<brief_id>_<YYYYMMDD-HHMMSS>/<NN>-<template-slug>/
      with ad-spec.json + <output-name>_v1.png inside.
    - Auto-versioning never overwrites: _v1 → _v2 → _v3.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from generators.fal_client import (
    GenerationResult,
    download_image,
    generate as fal_generate,
    upload_image,
)
from generators.pynk_text_filler import FilledTemplate


@dataclass
class TextOnlyRenderResult:
    """Outcome of a single text-only ad render."""

    template_id: str
    template_slug: str
    aspect_ratio: str
    output_dir: Path
    spec_path: Path
    image_paths: list[Path] = field(default_factory=list)
    seed: int | None = None
    flagged_invented: list[dict] = field(default_factory=list)


def _slugify(text: str) -> str:
    """Lowercase hyphenated slug for filenames."""
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text or "ad"


def _next_versioned_path(base: Path, stem: str, suffix: str = ".png") -> Path:
    """Return base / f'{stem}_v{N}{suffix}' for the next free N (>=1)."""
    v = 1
    while True:
        candidate = base / f"{stem}_v{v}{suffix}"
        if not candidate.exists():
            return candidate
        v += 1


def generate_text_only_ad(
    *,
    filled: FilledTemplate,
    product_image_ref: str | Path,
    output_dir: Path,
    output_name: str,
    num_images: int = 1,
    brand_slug: str = "",
    product_name: str = "",
    brief_id: str = "",
    resolution: str = "1K",
    thinking_level: str = "disabled",
) -> TextOnlyRenderResult:
    """Render a single filled template using PYNK-style text-only flow.

    `product_image_ref` may be either a public URL (used as-is) or a local
    file path / Path (uploaded to fal.ai before generation). Sends
    `image_urls=[product_url]` only — no reference ad.

    The aspect ratio is taken from the FilledTemplate (locked at template
    selection time). Writes ad-spec.json next to the output PNG so the
    generation can be replayed or diffed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    ref_str = str(product_image_ref)
    if ref_str.lower().startswith(("http://", "https://")):
        product_url = ref_str
        product_source_for_spec = ref_str
    else:
        product_path = Path(product_image_ref)
        if not product_path.exists():
            raise FileNotFoundError(f"Product image not found: {product_path}")
        product_url = upload_image(product_path)
        product_source_for_spec = str(product_path)

    results: list[GenerationResult] = fal_generate(
        prompt=filled.filled_prompt,
        product_image_urls=[product_url],  # ← single image. Product only.
        aspect_ratio=filled.aspect_ratio,
        resolution=resolution,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    image_paths: list[Path] = []
    for r in results:
        out_path = _next_versioned_path(output_dir, output_name)
        download_image(r.image_url, out_path)
        r.local_path = out_path
        image_paths.append(out_path)

    seed = results[0].seed if results else None

    spec = {
        "engine": "pynk-text",
        "model": "fal-ai/nano-banana-2/edit",
        "image_urls_sent": [product_source_for_spec],
        "aspect_ratio": filled.aspect_ratio,
        "resolution": resolution,
        "num_images": num_images,
        "seed": seed,
        "brand": brand_slug,
        "product": product_name,
        "brief_id": brief_id,
        "template_id": filled.template_id,
        "template_name": filled.template_name,
        "template_slug": filled.template_slug,
        "product_anchor_applied": True,
        "chosen_text_color_hex": filled.chosen_text_color_hex,
        "chosen_text_color_descriptor": filled.chosen_text_color_descriptor,
        "flagged_invented": filled.flagged_invented,
        "slot_map": filled.slot_map,
        "raw_template": filled.raw_template,
        "filled_prompt": filled.filled_prompt,
        "output_images": [str(p) for p in image_paths],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    spec_path = output_dir / "ad-spec.json"
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    return TextOnlyRenderResult(
        template_id=filled.template_id,
        template_slug=filled.template_slug,
        aspect_ratio=filled.aspect_ratio,
        output_dir=output_dir,
        spec_path=spec_path,
        image_paths=image_paths,
        seed=seed,
        flagged_invented=filled.flagged_invented,
    )


def build_run_dir(
    *,
    ai_ads_root: Path,
    client_slug: str,
    brief_id: str = "",
) -> Path:
    """Create the parent folder for a text-only run.

    Layout: ai-ads/<client>/text-only/<brief_id>_<YYYYMMDD-HHMMSS>/
    (or <YYYYMMDD-HHMMSS>/ if no brief_id supplied — for ad-hoc runs)
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    stem = f"{brief_id}_{ts}" if brief_id else ts
    run_dir = ai_ads_root / client_slug / "text-only" / stem
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def build_template_subdir(
    *,
    run_dir: Path,
    template_number: int,
    template_slug: str,
) -> Path:
    """Per-template subfolder: NN-template-slug/."""
    nn = f"{template_number:02d}"
    sub = run_dir / f"{nn}-{template_slug}"
    sub.mkdir(parents=True, exist_ok=True)
    return sub


def parse_template_number(template_id: str) -> int:
    """Extract the numeric suffix from 'cooper-11-pull-quote-review' → 11."""
    m = re.match(r"cooper-(\d+)", template_id)
    return int(m.group(1)) if m else 0
