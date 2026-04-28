"""fal.ai client for Nano Banana 2 image generation.

Uses fal-ai/nano-banana-2/edit for all ad generation — this endpoint
accepts product images as reference alongside the text prompt.

Real product images are ALWAYS required. We never generate without them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import fal_client
import httpx

# Model endpoints
NB2_TEXT = "fal-ai/nano-banana-2"
NB2_EDIT = "fal-ai/nano-banana-2/edit"


@dataclass
class GenerationResult:
    image_url: str
    seed: int | None = None
    model: str = ""
    prompt_used: str = ""
    local_path: Path | None = None
    product_images_used: list[str] = field(default_factory=list)
    aspect_ratio: str = ""
    resolution: str = ""


def _ensure_fal_key() -> None:
    if not os.environ.get("FAL_KEY"):
        raise EnvironmentError("FAL_KEY not set. See .env.example")


def upload_image(image_path: Path) -> str:
    """Upload a local image to fal.ai and return a URL."""
    _ensure_fal_key()
    return fal_client.upload_file(image_path)


def resolve_product_images(
    product_image_urls: list[str] | None = None,
    product_image_paths: list[Path] | None = None,
) -> list[str]:
    """Resolve product images to URLs usable by fal.ai.

    Accepts URLs (already public) or local paths (uploaded to fal.ai).
    At least one product image is REQUIRED.
    """
    urls = []

    if product_image_urls:
        urls.extend(product_image_urls)

    if product_image_paths:
        for path in product_image_paths:
            if path.exists():
                urls.append(upload_image(path))
            else:
                raise FileNotFoundError(f"Product image not found: {path}")

    if not urls:
        raise ValueError(
            "No product images provided. Real product images are REQUIRED. "
            "Pass image URLs or local file paths."
        )

    return urls


def generate(
    prompt: str,
    product_image_urls: list[str],
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    num_images: int = 1,
    seed: int | None = None,
    thinking_level: str = "disabled",
    output_format: str = "png",
    safety_tolerance: int = 4,
) -> list[GenerationResult]:
    """Generate images using Nano Banana 2 with product images as reference.

    Uses the /edit endpoint which accepts image_urls as reference.
    The model sees both the text prompt AND the product images,
    so it can reproduce the real product faithfully.
    """
    _ensure_fal_key()

    arguments: dict = {
        "prompt": prompt,
        "image_urls": product_image_urls,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "num_images": num_images,
        "output_format": output_format,
        "safety_tolerance": safety_tolerance,
    }

    if seed is not None:
        arguments["seed"] = seed
    if thinking_level != "disabled":
        arguments["thinking_level"] = thinking_level

    result = fal_client.subscribe(NB2_EDIT, arguments=arguments)

    results = []
    for image in result.get("images", []):
        results.append(GenerationResult(
            image_url=image.get("url", ""),
            seed=result.get("seed"),
            model=NB2_EDIT,
            prompt_used=prompt,
            product_images_used=product_image_urls,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        ))

    if not results:
        raise RuntimeError(f"No images returned. Response keys: {list(result.keys())}")

    return results


def generate_text_only(
    prompt: str,
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    num_images: int = 1,
    seed: int | None = None,
    thinking_level: str = "disabled",
    output_format: str = "png",
) -> list[GenerationResult]:
    """Generate images using Nano Banana 2 text-to-image (no reference images).

    Use sparingly — most ad generation should use product images as reference.
    This is only for cases like generating backgrounds or scenes without products.
    """
    _ensure_fal_key()

    arguments: dict = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "num_images": num_images,
        "output_format": output_format,
    }

    if seed is not None:
        arguments["seed"] = seed
    if thinking_level != "disabled":
        arguments["thinking_level"] = thinking_level

    result = fal_client.subscribe(NB2_TEXT, arguments=arguments)

    results = []
    for image in result.get("images", []):
        results.append(GenerationResult(
            image_url=image.get("url", ""),
            seed=result.get("seed"),
            model=NB2_TEXT,
            prompt_used=prompt,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
        ))

    return results


def download_image(url: str, save_path: Path) -> Path:
    """Download an image from URL to local path."""
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60) as client:
        response = client.get(url)
        response.raise_for_status()
        save_path.write_bytes(response.content)
    return save_path


def generate_and_save(
    prompt: str,
    product_image_urls: list[str],
    save_dir: Path,
    filename_prefix: str = "ad",
    aspect_ratio: str = "1:1",
    resolution: str = "1K",
    num_images: int = 1,
    thinking_level: str = "disabled",
    **kwargs,
) -> list[GenerationResult]:
    """Generate images and save them locally."""
    results = generate(
        prompt=prompt,
        product_image_urls=product_image_urls,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        num_images=num_images,
        thinking_level=thinking_level,
        **kwargs,
    )

    save_dir.mkdir(parents=True, exist_ok=True)

    for i, result in enumerate(results):
        suffix = f"_v{i + 1}" if len(results) > 1 else ""
        filename = f"{filename_prefix}_{aspect_ratio.replace(':', 'x')}{suffix}.png"
        local_path = download_image(result.image_url, save_dir / filename)
        result.local_path = local_path

    return results
