"""Compose final image generation prompts from brand + style + brief + product characteristics.

CRITICAL: All prompts include real product characteristics extracted from the
actual product image. We NEVER describe an imagined product — only the real one.
"""

from __future__ import annotations

import re

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.product import Product
from models.style import Style
from generators.product_analyzer import characteristics_to_prompt_fragment


def compose_prompt(
    brand: Brand,
    product: Product,
    style: Style,
    brief: CreativeBrief | None = None,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
) -> str:
    """Merge brand + product + style + brief into a final fal.ai prompt.

    If product.product_characteristics is populated (from analyze-product),
    those real product details are injected into the prompt to ensure
    the generated image shows the ACTUAL product.
    """
    # Build the real product description from analyzed characteristics
    product_detail = ""
    if product.product_characteristics:
        product_detail = characteristics_to_prompt_fragment(product.product_characteristics)

    # Build substitution context
    context = {
        # Brand
        "brand_name": brand.name,
        "primary_color": brand.colors.primary,
        "secondary_color": brand.colors.secondary,
        "background_color": brand.colors.background,
        "text_color": brand.colors.text,
        "brand_tone": brand.tone,
        # Product — use real characteristics when available
        "product_name": product.name,
        "product_description": (
            f"{product.description} {product_detail}"
            if product_detail
            else product.description
        ),
        "product_characteristics": product_detail,
        "benefits": ", ".join(product.benefits[:4]),
        "price": product.price or "",
        "unique_mechanism": product.unique_mechanism or "",
        "social_proof": ", ".join(product.social_proof[:2]) or "",
        # Style composition
        "callout_count": str(style.composition.callout_count) if style.composition else "0",
        # Platform modifier
        "platform_modifier": style.platform_modifiers.get(platform, ""),
    }

    # Camera specs from style
    if style.camera:
        context["camera_body"] = style.camera.camera_body
        context["lens"] = style.camera.lens
        context["film_emulation"] = style.camera.film_emulation
        context["lighting_rig"] = style.camera.lighting_rig
    else:
        context["camera_body"] = ""
        context["lens"] = ""
        context["film_emulation"] = ""
        context["lighting_rig"] = ""

    # Brief-specific context
    if brief:
        context.update({
            "hook": brief.hook,
            "pain_point": brief.pain_point,
            "benefit_callouts": ", ".join(brief.benefit_callouts),
            "cta": brief.cta,
            "visual_direction": brief.visual_direction,
            "tone_override": brief.tone_override or brand.tone,
        })
    else:
        context.update({
            "hook": "",
            "pain_point": "",
            "benefit_callouts": ", ".join(product.benefits[:3]),
            "cta": "Shop Now",
            "visual_direction": "",
            "tone_override": "",
        })

    # Avatar/UGC person context
    if avatar and brand.audience.demographics_for_ugc:
        context["ugc_person_description"] = brand.audience.demographics_for_ugc
    else:
        context["ugc_person_description"] = f"person aged {brand.audience.age_range}"

    # Determine setting from avatar if available
    context["setting"] = "modern home" if not avatar else _infer_setting(avatar)
    context["emotion"] = "satisfied and confident"

    # Fill the template
    prompt = style.prompt_template
    for key, value in context.items():
        prompt = prompt.replace(f"{{{key}}}", str(value))

    # If we have real product characteristics, prepend a strong instruction
    # to use the reference image as the source of truth for the product
    if product.product_characteristics:
        reference_instruction = (
            "IMPORTANT: Use the provided reference image as the definitive source "
            "for the product's appearance. The product in the output MUST match "
            "the reference image exactly — same colors, text, graphics, and shape. "
        )
        prompt = reference_instruction + prompt

    # Clean up any unfilled placeholders
    prompt = re.sub(r"\{[a-z_]+\}", "", prompt)

    # Remove empty lines and extra whitespace
    lines = [line.strip() for line in prompt.split("\n") if line.strip()]
    return " ".join(lines)


def _infer_setting(avatar: CustomerAvatar) -> str:
    """Infer a natural setting from avatar data."""
    psychographic = avatar.psychographic.lower()
    if any(w in psychographic for w in ["office", "corporate", "professional"]):
        return "modern office"
    if any(w in psychographic for w in ["home", "family", "parent"]):
        return "cozy home"
    if any(w in psychographic for w in ["outdoor", "active", "fitness"]):
        return "outdoor lifestyle"
    return "casual everyday"


def get_negative_prompt(style: Style) -> str:
    """Get the negative prompt for a style."""
    return style.negative_prompt


def get_sizes_for_platform(style: Style, platform: str) -> list[tuple[int, int, str]]:
    """Get output image sizes for a platform."""
    platform_sizes = style.platforms.get(platform, [])
    if not platform_sizes:
        return [(1080, 1080, "default")]
    return [(s.width, s.height, s.label) for s in platform_sizes]
