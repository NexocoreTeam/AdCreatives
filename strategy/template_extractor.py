"""Extract Cooper-style prompt templates from client reference ads.

For each ad in `clients/<slug>/reference_ads/raw/<category>/`, this module:
    1. Loads the existing vision analysis (creative_mechanic, mood, elements_present,
       composition_notes — produced by `adc analyze-references`)
    2. Re-runs vision on the actual image with a TEMPLATE-EXTRACTION prompt
       that asks Claude/Gemini to describe the ad's compositional pattern as
       a Nano Banana 2 prompt with [PLACEHOLDERS] for brand-specific parts
       (HEADLINE, PRODUCT, CTA, etc.)
    3. Saves the result as a LibraryPrompt-compatible YAML at
       `clients/<slug>/templates/<category>/<ad_stem>.yaml`

The output structure mirrors Alex Cooper / Nanobana templates so the
existing `list_prompts()` / `find_library_examples_for_brief()` machinery
picks them up automatically when we point it at the client folder.

Cost: ~$0.02 per ad (Gemini Pro vision call).
Idempotent: re-runs skip ads whose template YAML already exists, unless
`force=True`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from strategy.brand_enricher import _downscale_to_data_uri, _parse_json_response
from strategy.llm import gemini_vision

CLIENT_TEMPLATES_DIRNAME = "templates"
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


TEMPLATE_EXTRACTOR_SYSTEM = """You are an expert ad creative analyst extracting
a reusable PROMPT TEMPLATE from a single ad image. The template will be used
to generate similar ads for a DIFFERENT brand's product, so your job is to
describe the COMPOSITIONAL PATTERN — not the specific copy or product — and
include [PLACEHOLDERS] in caps for the brand-specific parts that would vary.

Standard placeholders to use:
  [HEADLINE]    — the main hook text (1 line)
  [SUBHEAD]     — supporting copy below the headline
  [BODY]        — longer body copy if the layout has one
  [PRODUCT]     — the product name (or visual)
  [BRAND]       — the brand wordmark
  [CTA]         — call to action button or arrow text
  [STAT]        — specific statistic (e.g. "92%", "1 trillion")
  [BENEFIT]     — single benefit callout
  [BACKGROUND]  — background color or scene
  [ACCENT]      — accent color (where the ad uses one)
  [DETAILS]     — small details specific to the brand

Output schema is YAML matching LibraryPrompt:

  id: "<short kebab-case identifier, e.g. 'us-vs-them-pill-callout-split'>"
  name: "<2-4 word descriptive name>"
  source: "client-secondkind reference library"
  category: "<one of: us-vs-them, testimonial-review, features-and-benefits,
             facts-and-stats, before-and-after, promotion-and-discount,
             media-and-press, reasons-why, headline, editorial, ugc, ai-unique>"
  product_types: ["any"]
  audience_fit: <list of: unaware, problem_aware, solution_aware, product_aware, most_aware>
  funnel_stage: "<awareness | consideration | conversion | retention>"
  aspect_ratios: ["1:1"]
  tags: <list of 3-7 specific compositional tags like 'pill-callout',
         'headline-overlay', 'split-screen', 'stat-hero', 'editorial-serif',
         'ugc-handheld', 'product-corner-anchor', 'comparison-vertical-split'>
  template_prompt: |
    <The full prompt with [PLACEHOLDERS]. Start with "Image 1 is the actual
    product — replicate it exactly." Describe layout, text treatment,
    product placement, graphic elements, photography style.>
  description: "<1-2 sentences: when to use this template>"

Be SPECIFIC and COMPOSITIONAL. Bad: "A clean ad with text." Good: "Vertical
split with dark left half carrying a large white serif headline and small
generic-product photo, light right half carrying the brand product hero with
3 pill-style benefit callouts stacked vertically; SecondKind-style apothecary
warm-cream palette; product anchored bottom-right; small wordmark below."

Output VALID YAML only — no markdown fences, no commentary."""


@dataclass
class TemplateExtractionResult:
    templates_created: list[Path] = field(default_factory=list)
    cache_hits: int = 0
    new_extractions: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)


def _load_existing_analysis(client_slug: str, category: str, ad_stem: str) -> dict | None:
    """Load the vision analysis YAML produced by `adc analyze-references` if it
    exists. Provides additional context to the template extractor without
    requiring a second vision call."""
    analyses_root = Path("clients") / client_slug / "reference_ads" / "analyses"
    candidates = [
        analyses_root / category / f"{ad_stem[:60]}.yaml",
        analyses_root / f"{ad_stem[:60]}.yaml",
    ]
    for path in candidates:
        if path.exists():
            try:
                return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue
    return None


def _build_user_prompt(ad_filename: str, category: str, analysis: dict | None) -> str:
    """Compose the user prompt for the template extractor."""
    parts = [
        f"Reference ad filename: {ad_filename}",
        f"Category folder: {category}",
        "",
        "Look at the attached image. Extract a reusable PROMPT TEMPLATE that "
        "captures its compositional pattern with [PLACEHOLDERS] for brand-specific parts.",
    ]
    if analysis and isinstance(analysis.get("analysis"), dict):
        a = analysis["analysis"]
        parts.append("")
        parts.append("Existing analysis (use as additional context, do not echo verbatim):")
        for key in ("creative_mechanic", "visual_format", "copy_treatment",
                    "elements_present", "mood", "composition_notes"):
            value = a.get(key)
            if value:
                parts.append(f"  {key}: {value}")
    parts.append("")
    parts.append("Output the YAML template now. Use [PLACEHOLDERS] in caps for variable parts.")
    return "\n".join(parts)


def extract_template_from_ad(
    image_path: Path,
    client_slug: str,
    category: str,
) -> dict[str, Any]:
    """Extract a single template from one ad image. Returns the parsed YAML
    as a dict matching the LibraryPrompt schema."""
    if not image_path.exists():
        raise FileNotFoundError(f"Ad image not found: {image_path}")

    # Build a data URI for the image — same pattern used by brand_enricher
    suffix = image_path.suffix.lower()
    mime = (
        "image/png" if suffix == ".png"
        else "image/jpeg" if suffix in (".jpg", ".jpeg")
        else "image/webp" if suffix == ".webp"
        else "application/octet-stream"
    )
    raw = image_path.read_bytes()
    data_uri = _downscale_to_data_uri(raw, mime)

    # Pull in any existing analysis for richer context
    analysis = _load_existing_analysis(client_slug, category, image_path.stem)

    user_prompt = _build_user_prompt(image_path.name, category, analysis)

    response = gemini_vision(
        prompt=user_prompt,
        image_urls=[data_uri],
        system=TEMPLATE_EXTRACTOR_SYSTEM,
        max_tokens=2048,
    )

    return _parse_yaml_response(response)


def _parse_yaml_response(response: str) -> dict[str, Any]:
    """Parse the LLM YAML response into a dict. Strips markdown fences."""
    text = response.strip()
    if text.startswith("```"):
        # strip the opening fence (may be ```yaml)
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        # Try JSON as a fallback in case the model used JSON shape
        try:
            data = json.loads(text)
        except Exception:
            raise ValueError(f"Could not parse template YAML: {e}") from e

    if not isinstance(data, dict):
        raise ValueError(f"Template response is not a mapping: {type(data).__name__}")

    return data


def extract_all_client_templates(
    client_slug: str,
    *,
    force: bool = False,
) -> TemplateExtractionResult:
    """Walk every reference ad and extract its compositional template.

    Output structure mirrors the source:
        clients/<slug>/reference_ads/raw/<category>/<ad>.jpg  (source)
        clients/<slug>/templates/<category>/<ad_stem>.yaml    (extracted template)
    """
    raw_root = Path("clients") / client_slug / "reference_ads" / "raw"
    templates_root = Path("clients") / client_slug / CLIENT_TEMPLATES_DIRNAME

    if not raw_root.exists():
        raise FileNotFoundError(
            f"No reference ads at {raw_root}. Run `adc analyze-references` first."
        )

    result = TemplateExtractionResult()

    for category_dir in sorted(raw_root.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name
        out_dir = templates_root / category
        out_dir.mkdir(parents=True, exist_ok=True)

        for ad_path in sorted(category_dir.iterdir()):
            if not ad_path.is_file() or ad_path.suffix.lower() not in IMAGE_EXTS:
                continue

            template_path = out_dir / f"{ad_path.stem[:60]}.yaml"
            if template_path.exists() and not force:
                result.cache_hits += 1
                continue

            try:
                template = extract_template_from_ad(ad_path, client_slug, category)
            except Exception as e:
                result.skipped.append((ad_path.name, f"extraction failed: {e}"))
                continue

            # Ensure required fields are present (defaults where missing)
            template.setdefault("id", f"{client_slug}-{category}-{ad_path.stem[:30]}")
            template.setdefault("source", f"client-{client_slug} reference library")
            template.setdefault("category", category)
            template.setdefault("product_types", ["any"])
            template.setdefault("audience_fit", [])
            template.setdefault("funnel_stage", "consideration")
            template.setdefault("aspect_ratios", ["1:1"])
            template.setdefault("tags", [])
            template.setdefault("template_prompt", "")
            template.setdefault("description", "")
            template.setdefault("platforms", ["meta", "tiktok"])
            template["source_ad"] = str(ad_path.relative_to(Path("clients").parent))

            template_path.write_text(
                yaml.safe_dump(template, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )
            result.templates_created.append(template_path)
            result.new_extractions += 1

    return result
