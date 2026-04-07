"""Main image generation orchestrator — ties everything together."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.product import Product
from models.style import Style

from generators.composer import compose_prompt, get_negative_prompt, get_sizes_for_platform
from generators.fal_client import GenerationResult, generate_and_save
from generators.platform_adapter import get_platform_prompt_suffix


@dataclass
class GenerationJob:
    client: str
    product: str
    style: str
    brief_id: str = ""
    platform: str = "meta"
    count: int = 1
    results: list[GenerationResult] = field(default_factory=list)


def generate_ad_image(
    brand: Brand,
    product: Product,
    style: Style,
    brief: CreativeBrief | None = None,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    output_dir: Path | None = None,
    count: int = 1,
    client_slug: str = "",
) -> list[GenerationResult]:
    """Generate ad images for a product using a style template.

    Returns one image per size defined in the style for the target platform,
    multiplied by count (for variations).
    """
    sizes = get_sizes_for_platform(style, platform)
    if not sizes:
        sizes = [(1080, 1080, "default")]

    # Compose the base prompt
    base_prompt = compose_prompt(
        brand=brand,
        product=product,
        style=style,
        brief=brief,
        avatar=avatar,
        platform=platform,
    )

    negative = get_negative_prompt(style)

    # Build output directory
    if output_dir is None:
        today = date.today().isoformat()
        output_dir = Path("output") / client_slug / today / style.name.lower().replace(" ", "-")

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get model and params from style
    model = style.fal_model
    extra_params = dict(style.fal_params)

    results = []
    product_slug = product.name.lower().replace(" ", "-")

    for variant in range(count):
        for width, height, label in sizes:
            # Add platform-specific suffix
            platform_suffix = get_platform_prompt_suffix(platform)
            full_prompt = base_prompt
            if platform_suffix:
                full_prompt = f"{base_prompt} {platform_suffix}"

            # Build filename
            size_label = f"{width}x{height}"
            filename = f"{product_slug}_{size_label}_v{variant + 1}.png"
            save_path = output_dir / filename

            result = generate_and_save(
                prompt=full_prompt,
                save_path=save_path,
                model=model,
                width=width,
                height=height,
                negative_prompt=negative,
                **extra_params,
            )
            results.append(result)

    return results


def generate_from_reference(
    brand: Brand,
    product: Product,
    reference_analysis: dict,
    platform: str = "meta",
    output_dir: Path | None = None,
    client_slug: str = "",
) -> list[GenerationResult]:
    """Generate ad images based on a reference image analysis."""
    from generators.reference_analyzer import reference_to_prompt_context

    ref_context = reference_to_prompt_context(reference_analysis)

    # Use the suggested prompt from the analysis, filling in product details
    suggested = ref_context.get("suggested_prompt", "")
    if suggested:
        prompt = suggested.format(
            product_name=product.name,
            product_description=product.description,
            background_color=brand.colors.background,
            primary_color=brand.colors.primary,
            secondary_color=brand.colors.secondary,
            brand_tone=brand.tone,
            benefits=", ".join(product.benefits[:3]),
        )
    else:
        # Fallback: construct prompt from analysis context
        prompt = (
            f"Professional advertisement for {product.name}. {product.description}. "
            f"{ref_context.get('visual_direction', '')} "
            f"Color scheme: {ref_context.get('primary_color', '')} and "
            f"{ref_context.get('secondary_color', '')}. "
            f"Commercial quality, 4K resolution."
        )

    if output_dir is None:
        today = date.today().isoformat()
        output_dir = Path("output") / client_slug / today / "reference-match"

    output_dir.mkdir(parents=True, exist_ok=True)

    product_slug = product.name.lower().replace(" ", "-")
    sizes = [(1080, 1080, "square"), (1080, 1350, "portrait")]

    results = []
    for width, height, label in sizes:
        filename = f"{product_slug}_ref_{label}.png"
        save_path = output_dir / filename
        result = generate_and_save(
            prompt=prompt,
            save_path=save_path,
            width=width,
            height=height,
        )
        results.append(result)

    return results
