"""De-AI post-processing pass for generated photos.

Kills the synthetic-pristine fingerprint of raw model output: downscales to web
size, softens synthetic micro-sharpness, flattens contrast slightly, desaturates
a touch, adds luminance-weighted grain, and re-encodes as a web-grade JPEG.

Usage: python scripts/deai_post.py <input.png> [more inputs...]
Writes <input-stem>-web.jpg next to each input. Originals are never modified.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

WEB_WIDTH = 1600
BLUR_RADIUS = 0.4
GRAIN_SIGMA = 5.0
DESATURATE = 0.07
CONTRAST_FLATTEN = 0.97
BLACK_LIFT = 5.0
JPEG_QUALITY = 85


def de_ai(src: Path) -> Path:
    img = Image.open(src).convert("RGB")

    if img.width > WEB_WIDTH:
        height = round(img.height * WEB_WIDTH / img.width)
        img = img.resize((WEB_WIDTH, height), Image.LANCZOS)

    img = img.filter(ImageFilter.GaussianBlur(BLUR_RADIUS))

    arr = np.asarray(img).astype(np.float32)

    luma = arr.mean(axis=2, keepdims=True)
    arr = arr * (1.0 - DESATURATE) + luma * DESATURATE

    arr = arr * CONTRAST_FLATTEN + BLACK_LIFT

    rng = np.random.default_rng()
    shadow_weight = 1.0 - (luma / 255.0) * 0.5
    grain = rng.normal(0.0, GRAIN_SIGMA, arr.shape[:2])[..., None] * shadow_weight
    arr = arr + grain

    out_img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    dest = src.with_name(src.stem + "-web.jpg")
    out_img.save(dest, "JPEG", quality=JPEG_QUALITY, optimize=True)
    return dest


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/deai_post.py <image> [image...]")
    for raw in sys.argv[1:]:
        src = Path(raw)
        if not src.is_file():
            sys.exit(f"not a file: {src}")
        dest = de_ai(src)
        print(dest)


if __name__ == "__main__":
    main()
