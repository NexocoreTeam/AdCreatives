"""fal.ai API client for image generation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import fal_client
import httpx


@dataclass
class GenerationResult:
    image_url: str
    seed: int | None = None
    model: str = ""
    prompt_used: str = ""
    local_path: Path | None = None


def _ensure_fal_key() -> None:
    if not os.environ.get("FAL_KEY"):
        raise EnvironmentError("FAL_KEY not set. See .env.example")


def generate_image(
    prompt: str,
    model: str = "fal-ai/flux-pro/v1.1",
    width: int = 1080,
    height: int = 1080,
    negative_prompt: str = "",
    guidance_scale: float = 7.5,
    num_inference_steps: int = 28,
    seed: int | None = None,
    **extra_params,
) -> GenerationResult:
    """Generate a single image via fal.ai."""
    _ensure_fal_key()

    arguments: dict = {
        "prompt": prompt,
        "image_size": {"width": width, "height": height},
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
    }

    if negative_prompt:
        arguments["negative_prompt"] = negative_prompt
    if seed is not None:
        arguments["seed"] = seed

    arguments.update(extra_params)

    result = fal_client.subscribe(
        model,
        arguments=arguments,
    )

    # fal.ai returns different response shapes per model
    images = result.get("images", [])
    if images:
        image_url = images[0].get("url", "")
    elif "image" in result:
        image_url = result["image"].get("url", "")
    else:
        raise RuntimeError(f"Unexpected fal.ai response format: {list(result.keys())}")

    return GenerationResult(
        image_url=image_url,
        seed=result.get("seed"),
        model=model,
        prompt_used=prompt,
    )


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
    save_path: Path,
    model: str = "fal-ai/flux-pro/v1.1",
    width: int = 1080,
    height: int = 1080,
    **kwargs,
) -> GenerationResult:
    """Generate an image and save it locally."""
    result = generate_image(
        prompt=prompt,
        model=model,
        width=width,
        height=height,
        **kwargs,
    )
    local = download_image(result.image_url, save_path)
    return GenerationResult(
        image_url=result.image_url,
        seed=result.seed,
        model=result.model,
        prompt_used=result.prompt_used,
        local_path=local,
    )
