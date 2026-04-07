"""Analyze reference ad images to extract style and composition for replication."""

from __future__ import annotations

import base64
from pathlib import Path

import yaml

from strategy.llm import gpt4o_vision

ANALYSIS_SYSTEM = """You are an expert ad creative analyst. Analyze advertisement images
and extract their visual and strategic components so they can be replicated for a
different product/brand.

Focus on PORTABLE characteristics — things that can transfer to a new product:
- Layout and composition (where elements are placed)
- Color palette (actual hex codes if possible)
- Lighting style and mood
- Typography style (not the actual text)
- Whether there's a person and how they're posed/styled
- Background treatment
- Overall energy (premium, casual, urgent, playful, etc.)

Ignore product-specific details that won't transfer.
Output valid YAML only, no markdown fences."""

ANALYSIS_PROMPT = """Analyze this advertisement image and extract its visual DNA.

Return YAML with this structure:

layout:
  composition: "describe element placement (e.g., 'product left, text right, person behind')"
  text_areas: "where text/callouts appear"
  focal_point: "what draws the eye first"

visual_style:
  color_palette:
    primary: "#hex"
    secondary: "#hex"
    background: "#hex"
    accent: "#hex"
  lighting: "describe the lighting (e.g., 'soft studio, rim light from left')"
  mood: "overall emotional feel (e.g., 'premium and aspirational')"
  texture: "any notable textures or patterns"

typography_style:
  heading_style: "bold sans-serif, large" (describe style, not read the text)
  body_style: "light weight, small"
  text_treatment: "any effects like shadows, outlines, gradients"

people:
  present: true/false
  description: "if present, describe pose, styling, framing"
  relationship_to_product: "holding it, using it, standing near it"

callouts:
  count: 0
  style: "rounded boxes, floating labels, etc."
  placement: "right side, bottom strip, etc."

overall:
  energy: "premium/casual/urgent/playful/educational"
  platform_fit: "which platform this feels designed for"
  ad_format: "product hero, UGC, comparison, testimonial, etc."
  closest_style_template: "which of these it most resembles: product-hero, benefit-callout, lifestyle-ugc, split-comparison, social-proof"

prompt_suggestion: |
  A complete image generation prompt that would recreate this visual style
  but with placeholder variables like {product_name}, {background_color}, etc."""


def analyze_reference_image(image_path: str | Path) -> dict:
    """Analyze a reference ad image and extract its visual DNA."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference image not found: {path}")

    # Encode image to base64 data URL
    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    suffix = path.suffix.lower()
    mime_types = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
    mime = mime_types.get(suffix, "image/png")
    data_url = f"data:{mime};base64,{image_data}"

    result = gpt4o_vision(
        prompt=ANALYSIS_PROMPT,
        image_url=data_url,
        system=ANALYSIS_SYSTEM,
    )

    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    return yaml.safe_load(result)


def reference_to_prompt_context(analysis: dict) -> dict:
    """Convert reference analysis into context variables for the composer."""
    visual = analysis.get("visual_style", {})
    palette = visual.get("color_palette", {})
    people = analysis.get("people", {})
    callouts = analysis.get("callouts", {})
    overall = analysis.get("overall", {})

    return {
        "background_color": palette.get("background", "#FFFFFF"),
        "primary_color": palette.get("primary", "#000000"),
        "secondary_color": palette.get("secondary", "#666666"),
        "visual_direction": (
            f"{visual.get('lighting', '')}. "
            f"Mood: {visual.get('mood', '')}. "
            f"Energy: {overall.get('energy', '')}."
        ),
        "callout_count": str(callouts.get("count", 0)),
        "has_person": people.get("present", False),
        "person_description": people.get("description", ""),
        "closest_style": overall.get("closest_style_template", "product-hero"),
        "suggested_prompt": analysis.get("prompt_suggestion", ""),
    }
