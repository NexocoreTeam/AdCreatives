"""
Compose 4-tile Americana collage for Saved by Grace Co.
- 1080x1080 canvas, cream linen background
- 2x2 grid of source frames + cursive script overlay
- Brand voice: "her two loves."
"""

import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(r"C:/Users/ReadyPlayerOne/AdCreatives/clients/savedbygrace")
FRAMES_DIR = BASE / "collage" / "source-frames-v4"
OUT_DIR = BASE / "collage"
FONT_DIR = BASE / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)

# Download fonts (Google Fonts, OFL) if not present
font_path = FONT_DIR / "Sacramento-Regular.ttf"
if not font_path.exists():
    url = "https://github.com/google/fonts/raw/main/ofl/sacramento/Sacramento-Regular.ttf"
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, font_path)

sub_font_path = FONT_DIR / "Poppins-Medium.ttf"
if not sub_font_path.exists():
    url = "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Medium.ttf"
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, sub_font_path)

# Canvas + palette
CANVAS_W, CANVAS_H = 1080, 1080
BG = (242, 234, 216)          # cream linen
RED = (178, 58, 72)           # washed brand red
TILE = 420
GAP = 14
TOP_PAD = 30
H_PAD = (CANVAS_W - (TILE * 2 + GAP)) // 2  # center the grid horizontally
GRID_BOTTOM = TOP_PAD + TILE * 2 + GAP

canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)

# Frame mapping (visual narrative: hook -> baby -> mom -> product)
frames = [
    ("frame1-mom-baby-quilt.png", (H_PAD, TOP_PAD)),                          # TL: wide hook
    ("frame3-baby-closeup.png",   (H_PAD + TILE + GAP, TOP_PAD)),             # TR: baby
    ("frame2-mom-solo.png",       (H_PAD, TOP_PAD + TILE + GAP)),             # BL: mom
    ("frame4-flatlay.png",        (H_PAD + TILE + GAP, TOP_PAD + TILE + GAP)),# BR: product
]

for fname, pos in frames:
    img = Image.open(FRAMES_DIR / fname).convert("RGB")
    # Center-crop to square
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    img = img.crop((left, top, left + s, top + s)).resize((TILE, TILE), Image.LANCZOS)
    canvas.paste(img, pos)

# Bottom strip: cursive headline + sans-serif sub-headline naming the products
draw = ImageDraw.Draw(canvas)
strip_top = GRID_BOTTOM
strip_h = CANVAS_H - strip_top  # ~196 px

# Headline (cursive script)
headline = "matching."
h_font = ImageFont.truetype(str(font_path), 92)
h_bbox = draw.textbbox((0, 0), headline, font=h_font)
h_w = h_bbox[2] - h_bbox[0]
h_h = h_bbox[3] - h_bbox[1]

# Sub-headline (clean sans, brand-voice fragments naming the products)
sub = "loves jesus + america, too.   adult + baby sizes."
s_font = ImageFont.truetype(str(sub_font_path), 22)
s_bbox = draw.textbbox((0, 0), sub, font=s_font)
s_w = s_bbox[2] - s_bbox[0]
s_h = s_bbox[3] - s_bbox[1]

# Layout: headline above, sub below, vertically centered in strip
inner_gap = 14
total_h = h_h + inner_gap + s_h
block_top = strip_top + (strip_h - total_h) // 2

h_x = (CANVAS_W - h_w) // 2 - h_bbox[0]
h_y = block_top - h_bbox[1] - 6  # slight optical nudge up
draw.text((h_x, h_y), headline, font=h_font, fill=RED)

s_x = (CANVAS_W - s_w) // 2 - s_bbox[0]
s_y = block_top + h_h + inner_gap - s_bbox[1]
DARK = (60, 38, 20)  # warm dark brown, matches brand palette
draw.text((s_x, s_y), sub, font=s_font, fill=DARK)

out_path = OUT_DIR / "collage-v4-americana.png"
canvas.save(out_path, "PNG", optimize=True)
print(f"Saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
