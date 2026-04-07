"""Compose final image generation prompts from brand + style + brief."""

from __future__ import annotations

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.product import Product
from models.style import Style


def compose_prompt(
    brand: Brand,
    product: Product,
    style: Style,
    brief: CreativeBrief | None = None,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
) -> str:
    """Merge brand + product + style + brief into a final fal.ai prompt."""
    # Build substitution context
    context = {
        # Brand
        "brand_name": brand.name,
        "primary_color": brand.colors.primary,
        "secondary_color": brand.colors.secondary,
        "background_color": brand.colors.background,
        "text_color": brand.colors.text,
        "brand_tone": brand.tone,
        # Product
        "product_name": product.name,
        "product_description": product.description,
        "benefits": ", ".join(product.benefits[:4]),
        "price": product.price or "",
        "unique_mechanism": product.unique_mechanism or "",
        "social_proof": ", ".join(product.social_proof[:2]) or "",
        # Style composition
        "callout_count": str(style.composition.callout_count) if style.composition else "0",
        # Platform modifier
        "platform_modifier": style.platform_modifiers.get(platform, ""),
    }

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

    # Clean up any unfilled placeholders
    import re
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
        # Default sizes
        return [(1080, 1080, "default")]
    return [(s.width, s.height, s.label) for s in platform_sizes]
