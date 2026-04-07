"""Brand compliance checking — verify generated images match brand guidelines."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class BrandCheck:
    passed: bool
    check: str
    detail: str


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def color_distance(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> float:
    """Euclidean distance between two RGB colors."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


def extract_dominant_colors(image_path: Path, n_colors: int = 5) -> list[tuple[int, int, int]]:
    """Extract dominant colors from an image using simple quantization."""
    with Image.open(image_path) as img:
        # Resize for speed
        img = img.resize((150, 150))
        img = img.convert("RGB")

        # Quantize to reduce colors
        quantized = img.quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()
        if not palette:
            return []

        colors = []
        for i in range(n_colors):
            r, g, b = palette[i * 3 : i * 3 + 3]
            colors.append((r, g, b))
        return colors


def check_brand_colors(
    image_path: Path,
    brand_colors: dict[str, str],
    tolerance: float = 80.0,
) -> list[BrandCheck]:
    """Check if generated image contains brand colors within tolerance."""
    checks: list[BrandCheck] = []

    if not image_path.exists():
        return [BrandCheck(False, "file_exists", f"File not found: {image_path}")]

    dominant = extract_dominant_colors(image_path)
    if not dominant:
        return [BrandCheck(False, "color_extraction", "Could not extract colors from image")]

    for color_name, hex_val in brand_colors.items():
        if not hex_val or hex_val == "null":
            continue

        target_rgb = hex_to_rgb(hex_val)
        min_dist = min(color_distance(target_rgb, d) for d in dominant)
        in_tolerance = min_dist <= tolerance

        checks.append(BrandCheck(
            passed=in_tolerance,
            check=f"brand_color_{color_name}",
            detail=(
                f"{color_name} ({hex_val}): "
                f"{'found' if in_tolerance else 'NOT found'} in image "
                f"(closest distance: {min_dist:.0f}, tolerance: {tolerance})"
            ),
        ))

    return checks


def check_prohibited_terms(text: str, prohibited: list[str]) -> list[BrandCheck]:
    """Check if any prohibited terms appear in ad copy."""
    checks: list[BrandCheck] = []
    text_lower = text.lower()

    for term in prohibited:
        found = term.lower() in text_lower
        checks.append(BrandCheck(
            passed=not found,
            check=f"prohibited_term",
            detail=f"'{term}': {'FOUND — must remove' if found else 'not found (OK)'}",
        ))

    return checks
