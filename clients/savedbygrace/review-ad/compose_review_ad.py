"""
Compose Beek-style review-quote ad for Saved by Grace Co.  (v2)
- 1080x1620 canvas (2:3 vertical, Beek-equivalent)
- Top: horizontal flat lay hero (4 color tees)
- Bottom-left: UGC mirror selfie (the new model)
- Bottom-right: cream quote card with SBG Co. logo + customer quote
- Thin white dividers between all three sections
- Quote-card content vertically centered
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(r"C:/Users/ReadyPlayerOne/AdCreatives/clients/savedbygrace")
TOP_HERO_PATH = BASE / "review-ad" / "source" / "top-hero-flatlay-2tee.png"
UGC_PATH      = BASE / "models" / "ugc-mirror-selfie.png"
LOGO_PATH     = BASE / "brand" / "logo.png"
OUT_DIR       = BASE / "review-ad"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FONT_DIR = BASE / "fonts"

for p, label in [(TOP_HERO_PATH, "top hero"), (UGC_PATH, "UGC selfie"), (LOGO_PATH, "SBG logo")]:
    assert p.exists(), f"MISSING: {label} at {p}"

# Fonts
georgia_italic = Path(r"C:/Windows/Fonts/georgiai.ttf")
poppins_font   = FONT_DIR / "Poppins-Medium.ttf"

# Canvas + palette
CANVAS_W, CANVAS_H = 1080, 1620
CREAM_BG = (245, 240, 230)
WHITE = (255, 255, 255)
DARK = (50, 35, 22)
MUTED = (130, 115, 95)

# Layout regions
TOP_H = 648
BOTTOM_H = CANVAS_H - TOP_H        # 972
HALF_W = CANVAS_W // 2             # 540
BORDER_W = 6                       # thin white dividers between sections

canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), CREAM_BG)


def cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Center-crop + resize to exactly fill target dimensions (object-fit: cover)."""
    iw, ih = img.size
    target_ratio = target_w / target_h
    src_ratio = iw / ih
    if src_ratio > target_ratio:
        new_w = int(ih * target_ratio)
        left = (iw - new_w) // 2
        img = img.crop((left, 0, left + new_w, ih))
    else:
        new_h = int(iw / target_ratio)
        top_off = (ih - new_h) // 2
        img = img.crop((0, top_off, iw, top_off + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)


# --- Top hero ---
top = cover_crop(Image.open(TOP_HERO_PATH).convert("RGB"), CANVAS_W, TOP_H)
canvas.paste(top, (0, 0))

# --- Bottom-left: UGC selfie ---
ugc = cover_crop(Image.open(UGC_PATH).convert("RGB"), HALF_W, BOTTOM_H)
canvas.paste(ugc, (0, TOP_H))

# --- Bottom-right: cream quote card (background already cream from canvas fill) ---
draw = ImageDraw.Draw(canvas)
card_x = HALF_W
card_y = TOP_H
card_w = HALF_W
card_h = BOTTOM_H

# --- Pre-measure content for vertical centering ---
quote = '“I seriously adore my shirt and how simple yet powerful the words are :)”'
q_font = ImageFont.truetype(str(georgia_italic), 34)

def wrap(text, font, max_w):
    words = text.split()
    lines, cur = [], []
    for w in words:
        trial = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines

q_lines = wrap(quote, q_font, card_w - 100)
line_h = q_font.size + 16
quote_h = line_h * len(q_lines)

attribution_spaced = " ".join(list("VERIFIED CUSTOMER"))
a_font = ImageFont.truetype(str(poppins_font), 17)
a_bbox = draw.textbbox((0, 0), attribution_spaced, font=a_font)
attrib_h = a_bbox[3] - a_bbox[1]

LOGO_H = 160
GAP_LOGO_NAME = 24
GAP_NAME_QUOTE = 40
GAP_QUOTE_ATTRIB = 44

# Product name label (letter-spaced caps under the logo)
product_name_spaced = " ".join(list("LOVES JESUS + AMERICA, TOO."))
n_font = ImageFont.truetype(str(poppins_font), 14)
n_bbox = draw.textbbox((0, 0), product_name_spaced, font=n_font)
name_h = n_bbox[3] - n_bbox[1]

total_content_h = LOGO_H + GAP_LOGO_NAME + name_h + GAP_NAME_QUOTE + quote_h + GAP_QUOTE_ATTRIB + attrib_h
content_top = card_y + (card_h - total_content_h) // 2

# --- Render logo ---
logo = Image.open(LOGO_PATH).convert("RGBA")
lw, lh = logo.size
scale = LOGO_H / lh
logo_resized = logo.resize((int(lw * scale), LOGO_H), Image.LANCZOS)
logo_x = card_x + (card_w - logo_resized.width) // 2
canvas.paste(logo_resized, (logo_x, content_top), logo_resized)

# --- Render product name (letter-spaced caps under logo) ---
draw = ImageDraw.Draw(canvas)  # refresh after paste with mask
name_y = content_top + LOGO_H + GAP_LOGO_NAME - n_bbox[1]
n_w = n_bbox[2] - n_bbox[0]
n_x = card_x + (card_w - n_w) // 2 - n_bbox[0]
draw.text((n_x, name_y), product_name_spaced, font=n_font, fill=MUTED)

# --- Render quote (centered lines) ---
q_y = content_top + LOGO_H + GAP_LOGO_NAME + name_h + GAP_NAME_QUOTE
for i, ln in enumerate(q_lines):
    bbox = draw.textbbox((0, 0), ln, font=q_font)
    lw_ = bbox[2] - bbox[0]
    lx = card_x + (card_w - lw_) // 2 - bbox[0]
    ly = q_y + i * line_h - bbox[1]
    draw.text((lx, ly), ln, font=q_font, fill=DARK)

# --- Render attribution (letter-spaced muted small caps) ---
a_w = a_bbox[2] - a_bbox[0]
a_x = card_x + (card_w - a_w) // 2 - a_bbox[0]
a_y = q_y + quote_h + GAP_QUOTE_ATTRIB - a_bbox[1]
draw.text((a_x, a_y), attribution_spaced, font=a_font, fill=MUTED)

# --- Thin white dividers between the three sections + outer frame ---
# Horizontal: between top hero and bottom row
draw.rectangle([0, TOP_H - BORDER_W // 2, CANVAS_W, TOP_H + BORDER_W // 2], fill=WHITE)
# Vertical: between bottom-left UGC and bottom-right card (bottom half only)
draw.rectangle([HALF_W - BORDER_W // 2, TOP_H, HALF_W + BORDER_W // 2, CANVAS_H], fill=WHITE)
# Outer frame: top, bottom, left, right edges
draw.rectangle([0, 0, CANVAS_W, BORDER_W], fill=WHITE)                          # top
draw.rectangle([0, CANVAS_H - BORDER_W, CANVAS_W, CANVAS_H], fill=WHITE)        # bottom
draw.rectangle([0, 0, BORDER_W, CANVAS_H], fill=WHITE)                          # left
draw.rectangle([CANVAS_W - BORDER_W, 0, CANVAS_W, CANVAS_H], fill=WHITE)        # right

out_path = OUT_DIR / "review-ad-v4.png"
canvas.save(out_path, "PNG", optimize=True)
print(f"Saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
