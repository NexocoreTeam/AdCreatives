"""
Compose iMessage-format ad for Saved by Grace Co.
- 1080x1080 canvas
- Blurred picnic background (mom+baby in matching Loves Jesus + America Too tees)
- Floating iMessage-style chat bubbles
- Brand voice: casual texting, names savedbygraceco + product, hooks 'adult + baby sizes'
"""

import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = Path(r"C:/Users/ReadyPlayerOne/AdCreatives/clients/savedbygrace")
BG_PATH = BASE / "collage" / "source-frames-v4" / "frame1-mom-baby-quilt.png"
OUT_DIR = BASE / "imessage"
OUT_DIR.mkdir(parents=True, exist_ok=True)
FONT_DIR = BASE / "fonts"
FONT_DIR.mkdir(parents=True, exist_ok=True)

# Use Windows system fonts (Segoe UI — iMessage-adjacent sans, always available)
inter_regular = Path(r"C:/Windows/Fonts/segoeui.ttf")
inter_semibold = Path(r"C:/Windows/Fonts/segoeuib.ttf")
assert inter_regular.exists(), f"Missing: {inter_regular}"
assert inter_semibold.exists(), f"Missing: {inter_semibold}"

# --- Canvas + visual settings ---
CANVAS_W, CANVAS_H = 1080, 1080

# iMessage palette
BLUE = (0, 122, 255)        # outgoing bubble fill (iOS blue)
GRAY = (229, 229, 234)      # incoming bubble fill (iOS gray)
WHITE = (255, 255, 255)
DARK = (20, 20, 20)         # incoming bubble text

# Bubble layout — ultra-compact, must fit within top ~140px (above mom's head)
BUBBLE_RADIUS = 14
BUBBLE_PAD_X = 10
BUBBLE_PAD_Y = 5
BUBBLE_MAX_W = 360
BUBBLE_GAP_SAME = 3
BUBBLE_GAP_DIFF = 7
SIDE_MARGIN = 24

# Font (smaller still)
font_text = ImageFont.truetype(str(inter_regular), 18)

# Chat content — 3 messages only, must fit above mom's head (no em-dashes per brand rule)
chat = [
    {"sender": "friend", "text": "okay where did you get those matching tees"},
    {"sender": "you",    "text": "savedbygraceco. loves jesus + america, too."},
    {"sender": "friend", "text": "ordering NOW"},
]


def wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Greedy word-wrap text to fit max_width."""
    words = text.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        trial = " ".join(cur + [w])
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width or not cur:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    return lines


def measure_lines(lines: list[str], font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw) -> tuple[int, int, int]:
    """Return (total_width, total_height, line_height)."""
    line_h = font.size + 8  # leading
    max_w = 0
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        max_w = max(max_w, bbox[2] - bbox[0])
    return max_w, line_h * len(lines), line_h


# --- Build background (sharp, no blur, no darken — subject + shirts must stay in focus) ---
bg = Image.open(BG_PATH).convert("RGB")
w, h = bg.size
s = min(w, h)
bg = bg.crop(((w - s) // 2, (h - s) // 2, (w + s) // 2, (h + s) // 2))
bg = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)

canvas = bg.copy()
draw = ImageDraw.Draw(canvas)

# --- Pre-measure all bubbles to compute total chat block height ---
prepped = []
for i, msg in enumerate(chat):
    lines = wrap_text(msg["text"], font_text, BUBBLE_MAX_W, draw)
    text_w, text_h, line_h = measure_lines(lines, font_text, draw)
    bubble_w = text_w + BUBBLE_PAD_X * 2
    bubble_h = text_h + BUBBLE_PAD_Y * 2
    prev = chat[i - 1] if i > 0 else None
    gap = 0 if prev is None else (BUBBLE_GAP_SAME if prev["sender"] == msg["sender"] else BUBBLE_GAP_DIFF)
    prepped.append({
        "lines": lines,
        "line_h": line_h,
        "bubble_w": bubble_w,
        "bubble_h": bubble_h,
        "gap": gap,
        "sender": msg["sender"],
    })

total_h = sum(p["bubble_h"] for p in prepped) + sum(p["gap"] for p in prepped)
chat_top = 24  # anchor tight at top — must finish above mom's head (~y=180)

# --- Draw bubbles ---
y = chat_top
for p in prepped:
    y += p["gap"]
    if p["sender"] == "you":
        x = CANVAS_W - SIDE_MARGIN - p["bubble_w"]
        fill = BLUE
        text_color = WHITE
    else:
        x = SIDE_MARGIN
        fill = GRAY
        text_color = DARK

    # Soft drop shadow (subtle — bubbles are small now, less shadow needed)
    shadow_layer = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow_layer)
    shadow_draw.rounded_rectangle(
        (x + 2, y + 3, x + p["bubble_w"] + 2, y + p["bubble_h"] + 3),
        radius=BUBBLE_RADIUS,
        fill=(0, 0, 0, 55),
    )
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=4))
    canvas.paste(shadow_layer, (0, 0), shadow_layer)
    draw = ImageDraw.Draw(canvas)

    # Bubble background
    draw.rounded_rectangle(
        (x, y, x + p["bubble_w"], y + p["bubble_h"]),
        radius=BUBBLE_RADIUS,
        fill=fill,
    )

    # Text inside bubble
    ty = y + BUBBLE_PAD_Y - 4  # slight optical nudge for Segoe UI baseline
    for ln in p["lines"]:
        draw.text((x + BUBBLE_PAD_X, ty), ln, font=font_text, fill=text_color)
        ty += p["line_h"]

    y += p["bubble_h"]

out_path = OUT_DIR / "imessage-v4.png"
canvas.save(out_path, "PNG", optimize=True)
print(f"Saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
