"""Prompt Engine — the brain that writes Nano Banana 2 prompts.

Three modes:
1. prompt_from_reference: Analyze any ad image → write a NB2 prompt for your product
2. prompt_from_library: Take a library template → customize for your client/product
3. recommend_prompts: Given a client/product, recommend best-fit library prompts

In ALL modes, Claude writes/modifies the generation prompt AND the real
product images are passed alongside the prompt to Nano Banana 2.
"""

from __future__ import annotations

import base64
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.library import LibraryPrompt, list_prompts
from models.product import Product
from models.skills import load_skill
from generators.product_analyzer import characteristics_to_prompt_fragment
from strategy.llm import claude_complete, gpt4o_vision

# ─── System Prompts ──────────────────────────────────────────────────────────

PROMPT_WRITER_SYSTEM = """You are an expert ad creative prompt engineer for Nano Banana 2
(Google's Gemini image generation model). You write prompts that produce
ad-account-ready static images.

CRITICAL RULES:
1. The REAL product images will be passed alongside your prompt as reference.
   Your prompt must describe the product precisely so the model reproduces it
   faithfully — same colors, same text, same graphics, same shape.
2. Include "Use the attached images as brand reference. Match the exact product
   design, colors, and packaging precisely." at the start of every prompt.
3. Be extremely specific about text content — quote exact words in the prompt.
4. Specify aspect ratio at the end (e.g., "1:1 aspect ratio").
5. Include photography direction: lens, lighting, composition, mood.
6. The output should be a single prompt string ready to paste into Nano Banana 2.
   No explanations, no markdown — just the prompt.
7. If the brief specifies a creative_mechanic and visual_format, use them as
   the structural backbone of the prompt — see Motion's libraries below.

OUTPUT: Return ONLY the prompt text. Nothing else.

--- CREATIVE MECHANICS (Motion) ---

""" + load_skill("motion/creative-mechanics") + """

--- VISUAL FORMATS (Motion, 45+ formats) ---

""" + load_skill("motion/visual-formats") + """
"""

REFERENCE_ANALYZER_SYSTEM = """You are an ad creative analyst. Analyze advertisement images
and extract their structural format so it can be recreated with a different product.

Focus on:
- Layout structure (where product sits, where text goes, composition)
- Visual format (split screen, single hero, grid, screenshot mock, etc.)
- Text treatment (headline style, font weight, positioning)
- Color approach (gradient, solid, lifestyle photo background)
- Trust mechanics (review cards, star ratings, social comments, press logos)
- Mood and energy (premium, casual, urgent, editorial, UGC-native)

Output valid YAML only."""

RECOMMENDER_SYSTEM = """You are a performance marketing strategist who selects
ad creative formats based on brand, product, and audience data.

Given a set of available prompt templates, recommend the best ones for the
specific product and audience. Consider:
- Product type (apparel needs lifestyle shots, supplements need trust mechanics)
- Audience awareness level (unaware → curiosity gaps, product-aware → social proof)
- Brand tone (playful brands → bold statements, professional → editorial)
- Funnel stage (awareness → scroll-stoppers, conversion → offer/comparison)

Return a ranked list with reasoning for each pick."""


# ─── Mode 1: "Make it like this" ────────────────────────────────────────────


def prompt_from_reference(
    reference_image_path: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str = "1:1",
) -> str:
    """Analyze a reference ad image and write a NB2 prompt that recreates
    that format using the client's real product."""

    # Step 1: Analyze the reference ad with GPT-4o vision
    path = Path(reference_image_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference image not found: {path}")

    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    suffix = path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(
        suffix.lstrip("."), "image/png"
    )
    data_url = f"data:{mime};base64,{image_data}"

    analysis = gpt4o_vision(
        prompt=(
            "Analyze this advertisement and extract its structural format as YAML. "
            "Include: layout, text_elements (exact text content and positioning), "
            "visual_format, color_approach, trust_mechanics, mood, aspect_ratio, "
            "and a suggested_prompt_structure that describes how to recreate this "
            "format for a different product."
        ),
        image_url=data_url,
        system=REFERENCE_ANALYZER_SYSTEM,
    )

    # Step 2: Build product context
    product_context = _build_product_context(brand, product, avatar)

    # Step 3: Claude writes the generation prompt
    prompt = claude_complete(
        prompt=(
            f"Write a Nano Banana 2 prompt that recreates this ad format "
            f"for the following product.\n\n"
            f"REFERENCE AD ANALYSIS:\n{analysis}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n"
            f"ASPECT RATIO: {aspect_ratio}\n\n"
            f"Write the prompt now. Start with 'Use the attached images as brand reference.'"
        ),
        system=PROMPT_WRITER_SYSTEM,
    )

    return prompt.strip()


# ─── Mode 2: "Use this library prompt" ──────────────────────────────────────


def prompt_from_library(
    library_prompt: LibraryPrompt,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str | None = None,
    modifications: dict | None = None,
) -> str:
    """Take a template prompt from the library and customize it for a
    specific client, product, and audience."""

    product_context = _build_product_context(brand, product, avatar)

    # Build modification instructions if any
    mod_instructions = ""
    if modifications:
        mod_parts = []
        for key, value in modifications.items():
            mod_parts.append(f"- Change {key} to: {value}")
        mod_instructions = (
            "\n\nUSER MODIFICATIONS (apply these changes):\n" + "\n".join(mod_parts)
        )

    # Use the first recommended aspect ratio from the template if not specified
    if not aspect_ratio:
        aspect_ratio = library_prompt.aspect_ratios[0] if library_prompt.aspect_ratios else "1:1"

    prompt = claude_complete(
        prompt=(
            f"Take this template prompt and fill in ALL [PLACEHOLDERS] with "
            f"specific details for the product and brand below. The output must "
            f"be a complete, ready-to-use Nano Banana 2 prompt.\n\n"
            f"TEMPLATE PROMPT:\n{library_prompt.template_prompt}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n"
            f"ASPECT RATIO: {aspect_ratio}"
            f"{mod_instructions}\n\n"
            f"Fill in every placeholder. Keep the structural format of the template "
            f"exactly — only replace the bracketed placeholders with real details. "
            f"Make sure the product description matches the real product precisely."
        ),
        system=PROMPT_WRITER_SYSTEM,
    )

    return prompt.strip()


# ─── Mode 3: "What would you recommend?" ────────────────────────────────────


def recommend_prompts(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    count: int = 10,
    product_type: str | None = None,
    platform: str = "meta",
) -> list[dict]:
    """Search the prompt library and recommend the best-fit templates
    for a specific client/product/audience."""

    # Load all available prompts
    all_prompts = list_prompts(
        product_type=product_type or product.category or None,
        platform=platform,
    )

    if not all_prompts:
        # No filters matched — load everything
        all_prompts = list_prompts()

    # Build a summary of available prompts for Claude
    prompt_summaries = []
    for p in all_prompts:
        prompt_summaries.append(
            f"- ID: {p.id} | Name: {p.name} | Category: {p.category} | "
            f"Tags: {', '.join(p.tags[:5])} | Audience: {', '.join(p.audience_fit)} | "
            f"Description: {p.description[:100]}"
        )

    prompts_list = "\n".join(prompt_summaries)
    product_context = _build_product_context(brand, product, avatar)

    result = claude_complete(
        prompt=(
            f"From this library of {len(all_prompts)} ad creative templates, "
            f"recommend the top {count} for the following product and brand.\n\n"
            f"AVAILABLE TEMPLATES:\n{prompts_list}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n\n"
            f"Return your recommendations as YAML:\n"
            f"recommendations:\n"
            f"  - id: \"prompt-id\"\n"
            f"    rank: 1\n"
            f"    reasoning: \"Why this template fits this product/brand\"\n"
            f"    suggested_modifications: \"Any changes to make it better for this brand\"\n"
        ),
        system=RECOMMENDER_SYSTEM,
        max_tokens=2048,
    )

    # Parse YAML response
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    try:
        parsed = yaml.safe_load(result)
        return parsed.get("recommendations", [])
    except Exception:
        return [{"id": "error", "reasoning": result}]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _build_product_context(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
) -> str:
    """Build a comprehensive context string for Claude to use when
    writing generation prompts."""

    # Product characteristics (from image analysis)
    product_details = ""
    if product.product_characteristics:
        product_details = characteristics_to_prompt_fragment(product.product_characteristics)

    parts = [
        f"BRAND: {brand.name}",
        f"BRAND TONE: {brand.tone}",
        f"BRAND COLORS: primary={brand.colors.primary}, secondary={brand.colors.secondary}, "
        f"background={brand.colors.background}, accent={brand.colors.accent or 'none'}",
        f"",
        f"PRODUCT: {product.name}",
        f"DESCRIPTION: {product.description}",
        f"BENEFITS: {', '.join(product.benefits[:5])}",
        f"PRICE: {product.price or 'not specified'}",
        f"SOCIAL PROOF: {', '.join(product.social_proof[:3])}",
    ]

    if product_details:
        parts.append(f"\nPRODUCT VISUAL DETAILS (from real product image analysis):\n{product_details}")

    if product.unique_mechanism:
        parts.append(f"UNIQUE MECHANISM: {product.unique_mechanism.strip()}")

    if avatar:
        parts.extend([
            f"",
            f"TARGET AUDIENCE: {avatar.demographic}",
            f"AWARENESS LEVEL: {avatar.awareness_level}",
            f"UGC PERSON DESCRIPTION: {brand.audience.demographics_for_ugc}",
        ])
        if avatar.pain_points:
            top_pains = [p.pain for p in avatar.pain_points[:3]]
            parts.append(f"TOP PAIN POINTS: {', '.join(top_pains)}")
        if avatar.language_patterns:
            parts.append(f"LANGUAGE STYLE: {', '.join(avatar.language_patterns[:3])}")

    if brand.guidelines_notes:
        parts.append(f"\nBRAND GUIDELINES:\n{brand.guidelines_notes.strip()}")

    if brand.prohibited_terms:
        parts.append(f"PROHIBITED TERMS: {', '.join(brand.prohibited_terms)}")

    return "\n".join(parts)
