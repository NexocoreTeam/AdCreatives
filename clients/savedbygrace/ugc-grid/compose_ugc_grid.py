"""
Compose UGC 4-tile grid for Saved by Grace Co.

Workflow:
  1. Render clean 4-tile collage (no text) — ugc-grid-clean.png
  2. Apply brand text overlay via generators.text_overlay
     - v2a: brand standard (bottom wash + CTA pill) → ugc-grid-v2a-wash.png
     - v2b: centered floating pill (Oddbird-style)  → ugc-grid-v2b-centered.png

Caller can pick which one ships. Both use SAVEDBYGRACE_PRESET — same brand
colors and fonts, two different layouts.
"""

import sys
from pathlib import Path

# Make the project root importable so we can use generators/
REPO_ROOT = Path(r"C:/Users/ReadyPlayerOne/AdCreatives")
sys.path.insert(0, str(REPO_ROOT))

from PIL import Image, ImageDraw  # noqa: E402

from generators.text_overlay import (  # noqa: E402
    SAVEDBYGRACE_PRESET,
    render_ad_overlay,
    render_centered_pill_overlay,
    render_mixed_caption_overlay,
    render_tiktok_caption_overlay,
)

BASE = REPO_ROOT / "clients" / "savedbygrace"
SRC = BASE / "ugc-grid" / "source"
OUT = BASE / "ugc-grid"

tile_paths = {
    "TL": BASE / "models" / "ugc-mirror-selfie.png",
    "TR": SRC / "ugc-tr-overhead.png",
    "BL": SRC / "ugc-bl-mirror-phone-face.png",
    "BR": SRC / "ugc-br-candid-bed.png",
}

CANVAS_W, CANVAS_H = 1080, 1920
WHITE = (255, 255, 255)
GUTTER = 6
cell_w = (CANVAS_W - GUTTER) // 2
cell_h = (CANVAS_H - GUTTER) // 2


def cover_crop(img, w, h):
    iw, ih = img.size
    target = w / h
    src = iw / ih
    if src > target:
        nw = int(ih * target)
        img = img.crop(((iw - nw) // 2, 0, (iw + nw) // 2, ih))
    else:
        nh = int(iw / target)
        img = img.crop((0, (ih - nh) // 2, iw, (ih + nh) // 2))
    return img.resize((w, h), Image.LANCZOS)


# --- Step 1: build clean 4-tile collage ---
canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), WHITE)
positions = {
    "TL": (0, 0),
    "TR": (cell_w + GUTTER, 0),
    "BL": (0, cell_h + GUTTER),
    "BR": (cell_w + GUTTER, cell_h + GUTTER),
}
for pos_key, path in tile_paths.items():
    x, y = positions[pos_key]
    if not path.exists():
        ImageDraw.Draw(canvas).rectangle([x, y, x + cell_w, y + cell_h], fill=(245, 240, 230))
        continue
    img = Image.open(path).convert("RGB")
    img = cover_crop(img, cell_w, cell_h)
    canvas.paste(img, (x, y))

clean_path = OUT / "ugc-grid-clean.png"
canvas.save(clean_path, "PNG", optimize=True)
print(f"Saved clean base: {clean_path}")

# --- Step 2a: brand-standard overlay (bottom wash + CTA pill) ---
QUOTE = "Soft, comfy, says exactly what I mean. The Loves Jesus + America, Too. tee."
CTA = "Shop the Tee"

wash_out = render_ad_overlay(
    base_image=clean_path,
    hero_quote=QUOTE,
    cta_text=CTA,
    out_path=OUT / "ugc-grid-v2a-brand-wash.png",
    preset=SAVEDBYGRACE_PRESET,
)
print(f"Saved brand-wash version: {wash_out}")

# --- Step 2b: centered pill overlay (Oddbird-style) ---
centered_out = render_centered_pill_overlay(
    base_image=clean_path,
    quote=QUOTE,
    out_path=OUT / "ugc-grid-v2b-centered-pill.png",
    preset=SAVEDBYGRACE_PRESET,
    position=0.5,
)
print(f"Saved centered-pill version: {centered_out}")

# --- Step 2c: TikTok-native caption (one pill per line, no shadow, bold sans) ---
TIKTOK_LINES = [
    "soft, comfy, says it all.",
    "loves jesus + america, too. tee.",
]
tiktok_out = render_tiktok_caption_overlay(
    base_image=clean_path,
    lines=TIKTOK_LINES,
    out_path=OUT / "ugc-grid-v3-tiktok.png",
    preset=SAVEDBYGRACE_PRESET,
    position=0.5,
)
print(f"Saved TikTok-style version: {tiktok_out}")

# --- Step 2d: Mixed caption — red pill (product name) + handwritten supporting line ---
# Download Caveat (Google Fonts, OFL) for the handwritten line if not present
import urllib.request

FONT_DIR = BASE / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)
caveat_path = FONT_DIR / "Caveat-Variable.ttf"
if not caveat_path.exists():
    url = "https://github.com/google/fonts/raw/main/ofl/caveat/Caveat%5Bwght%5D.ttf"
    urllib.request.urlretrieve(url, caveat_path)

# Quote treatment (per user spec):
#   Line 1: "Loves Jesus + America Too 🇺🇸" — red pill with white text
#   Line 2: "Simple words. Deep meaning."     — handwritten (Caveat), warm dark brown
# Note: PIL won't render the emoji; we drop the flag for now (could composite Twemoji separately)
MIXED_ITEMS = [
    {"type": "pill",
     "text": "Loves Jesus + America, Too.",
     "pill_color": (178, 58, 72),    # warm brand red
     "text_color": (255, 255, 255)},  # white
    {"type": "handwritten",
     "text": "Simple words. Deep meaning.",
     "color": (40, 28, 18)},
]
mixed_out = render_mixed_caption_overlay(
    base_image=clean_path,
    items=MIXED_ITEMS,
    out_path=OUT / "ugc-grid-v4-mixed.png",
    preset=SAVEDBYGRACE_PRESET,
    position=0.5,
    handwritten_font_path=caveat_path,
    handwritten_size_frac=0.075,  # bumped up so handwritten reads at scroll-pace
)
print(f"Saved mixed-caption version: {mixed_out}")
