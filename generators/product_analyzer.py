"""Analyze real product images to extract portable visual characteristics.

Adapted from the Hollywood-Quality-UGC-Ad-Generator pattern:
GPT-4o vision extracts structured YAML describing the product's visual DNA —
colors, materials, textures, shape, branding elements — so the generation
model can reproduce the REAL product accurately in new compositions.

This is MANDATORY before image generation. We never generate without
real product images.
"""

from __future__ import annotations

import base64
from pathlib import Path

import yaml

from strategy.llm import gpt4o_vision

ANALYZER_SYSTEM = """You are a product photography analyst specializing in e-commerce
and advertising. Your job is to extract PORTABLE CHARACTERISTICS from a product
image — details that must be preserved when the product appears in any new scene,
composition, or advertisement.

CRITICAL RULES:
- Describe ONLY the product itself. IGNORE background, props, hands, environment.
- Focus on characteristics that would follow the product into ANY new scene.
- Be extremely precise about colors (provide hex codes), materials, and textures.
- Describe the exact text/graphics printed on the product if any.
- Note the product's shape, proportions, and distinctive features.

Output valid YAML only, no markdown fences."""

ANALYZER_PROMPT = """Analyze this product image and extract its portable visual characteristics.

Return YAML with this exact structure:

product_type: "what this product is (e.g., 'crewneck sweatshirt', 'glass tumbler')"

colors:
  primary: "#hex — the dominant color of the product"
  secondary: "#hex — second most prominent color"
  accent: "#hex — any accent colors (trim, graphics, etc.)"
  color_description: "human description (e.g., 'oatmeal cream with white text')"

materials:
  fabric_or_material: "what it's made of (e.g., 'heavyweight cotton fleece')"
  texture: "how the surface looks/feels (e.g., 'soft brushed, slight pilling texture')"
  finish: "matte, glossy, distressed, etc."

graphics_and_text:
  has_text: true/false
  text_content: "exact text printed on the product"
  text_style: "font style description (e.g., 'bold sans-serif, white, centered on chest')"
  has_graphics: true/false
  graphic_description: "describe any logos, images, or design elements"

shape_and_structure:
  silhouette: "overall shape (e.g., 'oversized crewneck, dropped shoulders')"
  fit: "how it would fit (e.g., 'relaxed/oversized', 'fitted', 'boxy')"
  distinctive_features: "anything unique about the construction"

branding:
  visible_brand_marks: "any visible brand tags, labels, or marks"
  brand_placement: "where brand elements appear"

generation_notes: |
  Specific instructions for AI image generation to reproduce this product
  accurately. Include the most critical details that must not be changed.
  Example: "The text MUST read 'Boy Mama' in white bold serif font,
  centered on the chest. The sweatshirt is cream/oatmeal colored with
  ribbed cuffs and hem."
"""


def analyze_product_image(
    image_path: str | Path,
) -> dict:
    """Analyze a product image and extract portable visual characteristics.

    This MUST be run before generating any ads. The returned characteristics
    ensure the AI reproduces the real product accurately.
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Product image not found: {path}. "
            "Real product images are REQUIRED for ad generation."
        )

    # Encode to base64
    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    suffix = path.suffix.lower()
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    mime = mime_types.get(suffix, "image/png")
    data_url = f"data:{mime};base64,{image_data}"

    result = gpt4o_vision(
        prompt=ANALYZER_PROMPT,
        image_url=data_url,
        system=ANALYZER_SYSTEM,
    )

    # Clean up potential markdown fences
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    return yaml.safe_load(result)


def analyze_product_from_url(image_url: str) -> dict:
    """Analyze a product image from a public URL."""
    result = gpt4o_vision(
        prompt=ANALYZER_PROMPT,
        image_url=image_url,
        system=ANALYZER_SYSTEM,
    )

    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    return yaml.safe_load(result)


def characteristics_to_prompt_fragment(characteristics: dict) -> str:
    """Convert product characteristics into a prompt fragment that ensures
    the AI reproduces the real product accurately.

    This fragment is injected into EVERY generation prompt.
    """
    parts = []

    # Product type
    product_type = characteristics.get("product_type", "")
    if product_type:
        parts.append(f"The product is a {product_type}.")

    # Colors
    colors = characteristics.get("colors", {})
    color_desc = colors.get("color_description", "")
    if color_desc:
        parts.append(f"Product colors: {color_desc}.")

    # Materials
    materials = characteristics.get("materials", {})
    fabric = materials.get("fabric_or_material", "")
    texture = materials.get("texture", "")
    if fabric:
        parts.append(f"Material: {fabric}.")
    if texture:
        parts.append(f"Texture: {texture}.")

    # Graphics and text — CRITICAL for branded products
    graphics = characteristics.get("graphics_and_text", {})
    if graphics.get("has_text"):
        text_content = graphics.get("text_content", "")
        text_style = graphics.get("text_style", "")
        parts.append(
            f"IMPORTANT: The product has text that reads exactly '{text_content}' "
            f"in {text_style}. This text must be reproduced accurately."
        )
    if graphics.get("has_graphics"):
        parts.append(f"Graphics: {graphics.get('graphic_description', '')}.")

    # Shape
    shape = characteristics.get("shape_and_structure", {})
    silhouette = shape.get("silhouette", "")
    fit = shape.get("fit", "")
    if silhouette:
        parts.append(f"Silhouette: {silhouette}.")
    if fit:
        parts.append(f"Fit: {fit}.")

    # Generation notes (the most important part)
    gen_notes = characteristics.get("generation_notes", "")
    if gen_notes:
        parts.append(f"CRITICAL PRODUCT DETAILS: {gen_notes.strip()}")

    return " ".join(parts)


def save_characteristics(
    client_slug: str,
    product_slug: str,
    characteristics: dict,
) -> Path:
    """Save analyzed characteristics alongside the product YAML."""
    output_path = (
        Path("clients") / client_slug / "products" / f"{product_slug}_characteristics.yaml"
    )
    with open(output_path, "w") as f:
        yaml.dump(characteristics, f, default_flow_style=False, sort_keys=False)
    return output_path
