"""Image generation orchestrator — ties prompt engine + fal client + validators together.

Four generation modes matching the prompt engine:
1. generate_from_reference: "Make it like this" ad
2. generate_from_library: Use a library prompt template
3. generate_from_recommendation: Let the system pick the best templates
4. generate_from_brief: Drive both prompt + image from a CreativeBrief

All modes pass real product images alongside the prompt to Nano Banana 2.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.library import LibraryPrompt, load_prompt
from models.product import Product
from generators.fal_client import (
    GenerationResult,
    generate_and_save,
    resolve_product_images,
)
from generators.prompt_engine import (
    infer_aspect_ratio,
    prompt_from_brief,
    prompt_from_library,
    prompt_from_reference,
    recommend_prompts,
)


def _get_product_image_urls(product: Product, client_slug: str) -> list[str]:
    """Collect all product image URLs for passing to Nano Banana 2."""
    urls = []

    # Primary image URL (preferred)
    if product.image_url:
        urls.append(product.image_url)

    # If no URL, try uploading local files
    if not urls and product.image_path:
        local = Path("clients") / client_slug / product.image_path
        if not local.exists():
            local = Path(product.image_path)
        urls = resolve_product_images(product_image_paths=[local])

    if not urls:
        raise ValueError(
            f"No product images found for '{product.name}'. "
            "Real product images are REQUIRED. Add image_url or image_path to the product YAML."
        )

    return urls


def _build_output_dir(client_slug: str, label: str) -> Path:
    today = date.today().isoformat()
    return Path("output") / client_slug / today / label


# ─── Mode 1: "Make it like this" ────────────────────────────────────────────


def generate_like_this(
    reference_image_path: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str = "1:1",
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    thinking_level: str = "disabled",
) -> tuple[str, list[GenerationResult]]:
    """Analyze a reference ad and generate a similar one for your product.

    Returns (prompt_used, generation_results).
    """
    # Get real product images
    product_urls = _get_product_image_urls(product, client_slug)

    # Claude writes the prompt based on the reference ad
    prompt = prompt_from_reference(
        reference_image_path=reference_image_path,
        brand=brand,
        product=product,
        avatar=avatar,
        platform=platform,
        aspect_ratio=aspect_ratio,
    )

    # Generate with Nano Banana 2
    if output_dir is None:
        output_dir = _build_output_dir(client_slug, "make-like-this")

    product_slug = product.name.lower().replace(" ", "-")
    results = generate_and_save(
        prompt=prompt,
        product_image_urls=product_urls,
        save_dir=output_dir,
        filename_prefix=product_slug,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    return prompt, results


# ─── Mode 2: "Use this library prompt" ──────────────────────────────────────


def generate_from_library(
    prompt_id: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str | None = None,
    modifications: dict | None = None,
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    thinking_level: str = "disabled",
) -> tuple[str, list[GenerationResult]]:
    """Generate an ad using a library prompt template customized for your product.

    Returns (prompt_used, generation_results).
    """
    # Load the template
    library_prompt = load_prompt(prompt_id)

    # Get real product images
    product_urls = _get_product_image_urls(product, client_slug)

    # Claude customizes the template
    prompt = prompt_from_library(
        library_prompt=library_prompt,
        brand=brand,
        product=product,
        avatar=avatar,
        platform=platform,
        aspect_ratio=aspect_ratio,
        modifications=modifications,
    )

    # Use template's aspect ratio if not overridden
    final_ratio = aspect_ratio or (
        library_prompt.aspect_ratios[0] if library_prompt.aspect_ratios else "1:1"
    )

    # Generate with Nano Banana 2
    if output_dir is None:
        output_dir = _build_output_dir(client_slug, library_prompt.id)

    product_slug = product.name.lower().replace(" ", "-")
    results = generate_and_save(
        prompt=prompt,
        product_image_urls=product_urls,
        save_dir=output_dir,
        filename_prefix=f"{product_slug}_{library_prompt.id}",
        aspect_ratio=final_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    return prompt, results


# ─── Mode 3: "What would you recommend?" ────────────────────────────────────


def get_recommendations(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    count: int = 10,
    platform: str = "meta",
) -> list[dict]:
    """Get prompt recommendations for a product. Does NOT generate images.

    Returns a ranked list of recommended prompt IDs with reasoning.
    Use generate_from_library() to actually generate images from a recommendation.
    """
    return recommend_prompts(
        brand=brand,
        product=product,
        avatar=avatar,
        count=count,
        product_type=product.category or None,
        platform=platform,
    )


# ─── Batch generation ────────────────────────────────────────────────────────


def generate_batch(
    prompt_ids: list[str],
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    client_slug: str = "",
    num_images: int = 1,
) -> list[tuple[str, list[GenerationResult]]]:
    """Generate ads from multiple library prompts in sequence.

    Returns list of (prompt_used, results) tuples.
    """
    all_results = []
    for prompt_id in prompt_ids:
        prompt, results = generate_from_library(
            prompt_id=prompt_id,
            brand=brand,
            product=product,
            avatar=avatar,
            platform=platform,
            client_slug=client_slug,
            num_images=num_images,
        )
        all_results.append((prompt, results))
    return all_results


# ─── Mode 4: "Turn this brief into a finished ad image" ──────────────────────


def generate_from_brief(
    brief: CreativeBrief,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    aspect_ratio: str | None = None,
    thinking_level: str = "disabled",
) -> tuple[str, list[GenerationResult]]:
    """Take a CreativeBrief, write the prompt with prompt_from_brief(), then
    generate the image(s) with Nano Banana 2 using the product's real images.

    Returns (prompt_used, generation_results). Each GenerationResult has
    its local_path populated.
    """
    product_urls = _get_product_image_urls(product, client_slug)

    if aspect_ratio is None:
        aspect_ratio = infer_aspect_ratio(brief)

    prompt = prompt_from_brief(
        brief=brief,
        brand=brand,
        product=product,
        avatar=avatar,
        aspect_ratio=aspect_ratio,
    )

    if output_dir is None:
        output_dir = Path("ai-ads") / client_slug / "images"

    results = generate_and_save(
        prompt=prompt,
        product_image_urls=product_urls,
        save_dir=output_dir,
        filename_prefix=brief.brief_id,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    return prompt, results
