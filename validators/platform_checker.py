"""Platform-specific validation for generated images."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class PlatformCheck:
    passed: bool
    check: str
    detail: str


PLATFORM_SPECS = {
    "meta": {
        "min_width": 600,
        "max_file_size_mb": 30,
        "accepted_formats": [".jpg", ".jpeg", ".png"],
        "recommended_sizes": [
            (1080, 1080, "Feed Square"),
            (1080, 1350, "Feed Portrait"),
            (1080, 1920, "Story/Reel"),
        ],
    },
    "tiktok": {
        "min_width": 540,
        "max_file_size_mb": 20,
        "accepted_formats": [".jpg", ".jpeg", ".png"],
        "recommended_sizes": [
            (1080, 1920, "Full Screen"),
        ],
    },
}


def check_image(image_path: Path, platform: str = "meta") -> list[PlatformCheck]:
    """Run platform-specific checks on a generated image."""
    checks: list[PlatformCheck] = []
    specs = PLATFORM_SPECS.get(platform, PLATFORM_SPECS["meta"])

    if not image_path.exists():
        return [PlatformCheck(False, "file_exists", f"File not found: {image_path}")]

    # Format check
    suffix = image_path.suffix.lower()
    accepted = specs["accepted_formats"]
    checks.append(PlatformCheck(
        passed=suffix in accepted,
        check="format",
        detail=f"Format {suffix} {'accepted' if suffix in accepted else f'not accepted (need {accepted})'}",
    ))

    # File size check
    size_mb = image_path.stat().st_size / (1024 * 1024)
    max_size = specs["max_file_size_mb"]
    checks.append(PlatformCheck(
        passed=size_mb <= max_size,
        check="file_size",
        detail=f"{size_mb:.1f}MB {'OK' if size_mb <= max_size else f'exceeds {max_size}MB limit'}",
    ))

    # Dimension checks
    try:
        with Image.open(image_path) as img:
            width, height = img.size

            min_w = specs["min_width"]
            checks.append(PlatformCheck(
                passed=width >= min_w,
                check="min_width",
                detail=f"{width}px {'meets' if width >= min_w else f'below'} {min_w}px minimum",
            ))

            # Check if it matches a recommended size
            recommended = specs.get("recommended_sizes", [])
            matches_recommended = any(
                width == rw and height == rh for rw, rh, _ in recommended
            )
            rec_labels = ", ".join(f"{w}x{h}" for w, h, _ in recommended)
            checks.append(PlatformCheck(
                passed=matches_recommended,
                check="recommended_size",
                detail=(
                    f"{width}x{height} "
                    f"{'matches' if matches_recommended else f'not in'} "
                    f"recommended sizes ({rec_labels})"
                ),
            ))
    except Exception as e:
        checks.append(PlatformCheck(False, "readable", f"Cannot read image: {e}"))

    return checks
