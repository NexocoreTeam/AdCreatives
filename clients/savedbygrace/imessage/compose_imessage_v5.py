"""
Compose RTR-style iMessage ad for Saved by Grace Co. (v5)
- 1080x1920 canvas (9:16 vertical, Stories/Reels native)
- Full-bleed mom+baby photo background
- 2 iMessage bubbles with iOS tail pointers + timestamps
- Brand name in white letter-spaced caps at very bottom
- Color emojis via Twemoji PNG composite
"""

import json
import urllib.request
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(r"C:/Users/ReadyPlayerOne/AdCreatives/clients/savedbygrace")
BG_PATH = BASE / "imessage" / "source" / "v5-bg-vertical.png"
OUT_DIR = BASE / "imessage"
OUT_DIR.mkdir(parents=True, exist_ok=True)
TWEMOJI_DIR = BASE / "assets" / "twemoji"
TWEMOJI_DIR.mkdir(parents=True, exist_ok=True)

assert BG_PATH.exists(), f"MISSING: 9:16 background at {BG_PATH}"

# ---- Twemoji loader ----
def get_twemoji(codepoint: str, size_px: int) -> Image.Image:
    """Fetch (and cache) a Twemoji 72x72 PNG, resize to size_px."""
    local = TWEMOJI_DIR / f"{codepoint}.png"
    if not local.exists():
        # Try jdecked's maintained fork first (post-Twitter), then fall back
        candidates = [
            f"https://cdn.jsdelivr.net/gh/jdecked/twemoji@latest/assets/72x72/{codepoint}.png",
            f"https://raw.githubusercontent.com/jdecked/twemoji/main/assets/72x72/{codepoint}.png",
            f"https://raw.githubusercontent.com/twitter/twemoji/master/assets/72x72/{codepoint}.png",
        ]
        ok = False
        for url in candidates:
            try:
                print(f"Trying {url}...")
                urllib.request.urlretrieve(url, local)
                ok = True
                break
            except Exception as e:
                print(f"  failed: {e}")
        if not ok:
            raise RuntimeError(f"Could not fetch twemoji {codepoint} from any source")
    img = Image.open(local).convert("RGBA")
    return img.resize((size_px, size_px), Image.LANCZOS)

# ---- Canvas + colors ----
CANVAS_W, CANVAS_H = 1080, 1920
BLUE = (0, 122, 255)
GRAY = (229, 229, 234)
WHITE = (255, 255, 255)
DARK = (20, 20, 20)
TIMESTAMP_GRAY = (160, 160, 165)

# ---- Bubble layout ----
BUBBLE_RADIUS = 26
BUBBLE_PAD_X = 22
BUBBLE_PAD_Y = 14
SIDE_MARGIN = 56
TAIL_W = 16
TAIL_H = 16
BETWEEN_BUBBLES = 90
TIMESTAMP_FONT_SIZE = 22
BUBBLE_FONT_SIZE = 34

# ---- Fonts ----
font_text = ImageFont.truetype(r"C:/Windows/Fonts/segoeui.ttf", BUBBLE_FONT_SIZE)
font_ts   = ImageFont.truetype(r"C:/Windows/Fonts/segoeui.ttf", TIMESTAMP_FONT_SIZE)
font_brand = ImageFont.truetype(r"C:/Windows/Fonts/segoeuib.ttf", 26)

# ---- Chat content ----
# Tokens: list of either {"text": "..."} or {"emoji": "codepoint"}
# Codepoints: ☀️=2600, 🥹=1f979, ❤️=2764, 🤍=1f90d, 💙=1f499
gray_tokens = [
    {"text": "we are ready for summer "},
    {"emoji": "2600"},
]
gray_timestamp = "2:47 PM"

blue_tokens = [
    {"emoji": "1f979"},
    {"emoji": "2764"},
    {"emoji": "1f90d"},
    {"emoji": "1f499"},
]
blue_timestamp = "2:48 PM"

# ---- Background ----
bg = Image.open(BG_PATH).convert("RGB")
# Cover-crop to 1080x1920
iw, ih = bg.size
target = CANVAS_W / CANVAS_H
src = iw / ih
if src > target:
    nw = int(ih * target)
    bg = bg.crop(((iw - nw) // 2, 0, (iw + nw) // 2, ih))
else:
    nh = int(iw / target)
    bg = bg.crop((0, (ih - nh) // 2, iw, (ih + nh) // 2))
bg = bg.resize((CANVAS_W, CANVAS_H), Image.LANCZOS)
canvas = bg.copy()
draw = ImageDraw.Draw(canvas)

# ---- Measure + render a bubble ----
def measure_tokens(tokens, emoji_size: int):
    """Return (total_width, height) for inline rendering."""
    w = 0
    h = emoji_size
    for t in tokens:
        if "text" in t:
            bbox = draw.textbbox((0, 0), t["text"], font=font_text)
            w += (bbox[2] - bbox[0])
            h = max(h, font_text.size + 4)
        else:
            w += emoji_size
    return w, h

def render_bubble(side: str, tokens, timestamp: str, top_y: int):
    """Render bubble + timestamp. side='left' (gray) or 'right' (blue). Returns bottom y."""
    emoji_size = font_text.size  # match line height
    text_w, text_h = measure_tokens(tokens, emoji_size)

    bubble_w = text_w + BUBBLE_PAD_X * 2
    bubble_h = text_h + BUBBLE_PAD_Y * 2

    # Center-split layout: both bubbles meet near canvas center
    # (more visually cohesive than full edge-anchored alignment)
    SPLIT_GAP = 30
    if side == "left":
        x = CANVAS_W // 2 - SPLIT_GAP - bubble_w
        fill = GRAY
        tcol = DARK
    else:
        x = CANVAS_W // 2 + SPLIT_GAP
        fill = BLUE
        tcol = WHITE

    y = top_y

    # Soft shadow
    sh = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
    shd = ImageDraw.Draw(sh)
    shd.rounded_rectangle((x + 2, y + 4, x + bubble_w + 2, y + bubble_h + 4),
                          radius=BUBBLE_RADIUS, fill=(0, 0, 0, 80))
    from PIL import ImageFilter
    sh = sh.filter(ImageFilter.GaussianBlur(radius=5))
    canvas.paste(sh, (0, 0), sh)
    d2 = ImageDraw.Draw(canvas)

    # Bubble body
    d2.rounded_rectangle((x, y, x + bubble_w, y + bubble_h), radius=BUBBLE_RADIUS, fill=fill)

    # Tail (iOS pointer)
    if side == "left":
        tail = [
            (x + 4, y + bubble_h - 4),
            (x - TAIL_W + 6, y + bubble_h + TAIL_H - 4),
            (x + 24, y + bubble_h),
        ]
    else:
        tail = [
            (x + bubble_w - 4, y + bubble_h - 4),
            (x + bubble_w + TAIL_W - 6, y + bubble_h + TAIL_H - 4),
            (x + bubble_w - 24, y + bubble_h),
        ]
    d2.polygon(tail, fill=fill)

    # Render tokens (text + emoji) inline
    cur_x = x + BUBBLE_PAD_X
    text_baseline_y = y + BUBBLE_PAD_Y
    emoji_size = font_text.size
    for t in tokens:
        if "text" in t:
            d2.text((cur_x, text_baseline_y - 4), t["text"], font=font_text, fill=tcol)
            bbox = d2.textbbox((0, 0), t["text"], font=font_text)
            cur_x += (bbox[2] - bbox[0])
        else:
            em = get_twemoji(t["emoji"], emoji_size)
            canvas.paste(em, (int(cur_x), text_baseline_y), em)
            cur_x += emoji_size

    # Timestamp below bubble, aligned to bubble's outer edge
    ts_bbox = d2.textbbox((0, 0), timestamp, font=font_ts)
    ts_w = ts_bbox[2] - ts_bbox[0]
    if side == "left":
        ts_x = x + 6
    else:
        ts_x = x + bubble_w - ts_w - 6
    ts_y = y + bubble_h + TAIL_H + 4
    d2.text((ts_x, ts_y), timestamp, font=font_ts, fill=TIMESTAMP_GRAY)

    return ts_y + (ts_bbox[3] - ts_bbox[1]) + 8

# ---- Place bubbles in lower half (~y=1180 start) ----
START_Y = 1200
y1_end = render_bubble("left", gray_tokens, gray_timestamp, START_Y)
y2_end = render_bubble("right", blue_tokens, blue_timestamp, y1_end + 24)

# ---- Brand line at the very bottom, white letter-spaced caps ----
from PIL import ImageFilter
d2 = ImageDraw.Draw(canvas)
brand = " ".join(list("SAVED BY GRACE CO."))
b_bbox = d2.textbbox((0, 0), brand, font=font_brand)
b_w = b_bbox[2] - b_bbox[0]
b_x = (CANVAS_W - b_w) // 2 - b_bbox[0]
b_y = CANVAS_H - 64 - b_bbox[1]
d2.text((b_x, b_y), brand, font=font_brand, fill=WHITE)

# ---- Product tag pill above brand line (bigger, footer-style) ----
tag_text = "LOVES JESUS + AMERICA, TOO.   ·   ADULT + BABY SIZES"
tag_font = ImageFont.truetype(r"C:/Windows/Fonts/segoeuib.ttf", 28)
tag_bbox = d2.textbbox((0, 0), tag_text, font=tag_font)
tag_w_text = tag_bbox[2] - tag_bbox[0]
tag_h_text = tag_bbox[3] - tag_bbox[1]
tag_pad_x = 32
tag_pad_y = 18
pill_w = tag_w_text + tag_pad_x * 2
pill_h = tag_h_text + tag_pad_y * 2
pill_x = (CANVAS_W - pill_w) // 2
pill_y = CANVAS_H - 64 - (b_bbox[3] - b_bbox[1]) - 28 - pill_h

# Soft shadow behind pill
sh = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
shd = ImageDraw.Draw(sh)
shd.rounded_rectangle((pill_x + 2, pill_y + 5, pill_x + pill_w + 2, pill_y + pill_h + 5),
                      radius=pill_h // 2, fill=(0, 0, 0, 70))
sh = sh.filter(ImageFilter.GaussianBlur(radius=7))
canvas.paste(sh, (0, 0), sh)
d2 = ImageDraw.Draw(canvas)

# White pill body with subtle warm cream tint
d2.rounded_rectangle((pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
                     radius=pill_h // 2, fill=(252, 248, 240))

# Dark warm brown text inside pill
tag_x = pill_x + tag_pad_x - tag_bbox[0]
tag_y = pill_y + tag_pad_y - tag_bbox[1]
d2.text((tag_x, tag_y), tag_text, font=tag_font, fill=(50, 35, 22))

out_path = OUT_DIR / "imessage-v8.png"
canvas.save(out_path, "PNG", optimize=True)
print(f"Saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
