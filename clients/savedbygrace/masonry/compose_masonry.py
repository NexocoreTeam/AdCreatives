"""
Compose true 3-column masonry collage for Saved by Grace Co. (v4)
- 1080x1350 canvas (4:5)
- THREE equal-width columns running vertically, each with its own card stack
- Cards within a column have varied heights → vertical offset between columns
- Rounded corners on every card, visible white space (gutter + outer margin)
- Mix of lifestyle, white-bg product shots, CTA tile, brand mark, solid accents
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE = Path(r"C:/Users/ReadyPlayerOne/AdCreatives/clients/savedbygrace")
SRC = BASE / "masonry" / "source"
PRODUCT_IMG = BASE / "products" / "images"
OUT = BASE / "masonry"
LOGO = BASE / "brand" / "logo.png"

sources = {
    "fl1":             SRC / "fl1-feral-3color.png",
    "ls1":             SRC / "ls1-kid-feral.png",
    "ls2":             SRC / "ls2-kid-wlmc.png",
    "ls5":             SRC / "ls5-group-feral.png",
    "ls_wide":         SRC / "ls-wide-hero.png",
    "ls_mom_kid":      SRC / "ls-mom-kid-coord.png",
    "ls_mom_tall":     SRC / "ls-mom-tall.png",
    "prod_feral":      PRODUCT_IMG / "feral-1.jpg",
    "prod_aamc":       PRODUCT_IMG / "aamc-2.png",
    "prod_lja":        PRODUCT_IMG / "lja-1.png",
    "prod_lhba":       PRODUCT_IMG / "lhba-1.png",
}

# Canvas + palette
CANVAS_W, CANVAS_H = 1080, 1350
CREAM = (245, 240, 230)
WARM_RED = (178, 58, 72)
WHITE = (255, 255, 255)

MARGIN = 30
GUTTER_COL = 18         # space between columns
GUTTER_TILE = 14        # space between tiles within a column
CORNER_RADIUS = 24

COLS = 3
col_w = (CANVAS_W - MARGIN * 2 - GUTTER_COL * (COLS - 1)) // COLS

# Each column = list of tiles. Each tile = {"kind": str, "height": int, **payload}
# kind: "img" | "cta" | "brand" | "solid"
# payload: img -> key; cta -> text; brand -> (none); solid -> color
# Tile heights chosen so each column totals ~1290 (= CANVAS_H - 2*MARGIN)
# Three CTA copy options to render — collection / relational / seasonal angles
CTA_VARIANTS = [
    ("a-shop-the-edit",    "SHOP THE\nALL-AMERICAN EDIT"),
    ("b-matching-mama-me", "MATCHING SETS\nFOR MAMA + ME"),
    ("c-red-white-family", "RED, WHITE\n+ FAMILY"),
]


def build_columns(cta_text: str):
    return [
        [
            {"kind": "img",   "key": "fl1",          "height": 240},
            {"kind": "img",   "key": "ls1",          "height": 320},
            {"kind": "img",   "key": "ls2",          "height": 280},
            {"kind": "img",   "key": "prod_feral",   "height": 400},
        ],
        [
            {"kind": "img",   "key": "ls_wide",      "height": 280},
            {"kind": "cta",   "text": cta_text,      "height": 440},
            {"kind": "img",   "key": "ls_mom_kid",   "height": 360},
            {"kind": "brand", "height": 168},
        ],
        [
            {"kind": "solid", "color": WARM_RED,     "height": 160},
            {"kind": "img",   "key": "ls_mom_tall",  "height": 480},
            {"kind": "img",   "key": "prod_aamc",    "height": 280},
            {"kind": "img",   "key": "prod_lja",     "height": 320},
        ],
    ]

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


def round_paste(target: Image.Image, layer: Image.Image, x: int, y: int, radius: int):
    """Paste an image onto target with rounded corners via alpha mask."""
    mask = Image.new("L", layer.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, layer.size[0], layer.size[1]), radius=radius, fill=255
    )
    target.paste(layer.convert("RGB"), (x, y), mask)


def render_image_tile(target, x, y, w, h, key):
    path = sources.get(key)
    if not path or not path.exists():
        layer = Image.new("RGB", (w, h), CREAM)
    else:
        layer = Image.open(path).convert("RGB")
        layer = cover_crop(layer, w, h)
    round_paste(target, layer, x, y, CORNER_RADIUS)


def render_solid_tile(target, x, y, w, h, color):
    layer = Image.new("RGB", (w, h), color)
    round_paste(target, layer, x, y, CORNER_RADIUS)


def render_cta_tile(target, x, y, w, h, text):
    layer = Image.new("RGBA", (w, h), (*WARM_RED, 255))
    draw = ImageDraw.Draw(layer)

    font_path = r"C:/Windows/Fonts/georgiab.ttf"
    lines = text.split("\n")
    pad = 28
    max_fs = 120
    chosen_fs = max_fs
    for fs in range(max_fs, 18, -2):
        f = ImageFont.truetype(font_path, fs)
        widest = max(draw.textbbox((0, 0), ln, font=f)[2] for ln in lines)
        if widest <= (w - pad * 2):
            chosen_fs = fs
            break

    f = ImageFont.truetype(font_path, chosen_fs)
    line_metrics = [draw.textbbox((0, 0), ln, font=f) for ln in lines]
    line_height = chosen_fs + 14
    total_h = line_height * len(lines)
    ty = (h - total_h) // 2

    for i, ln in enumerate(lines):
        bbox = line_metrics[i]
        lw = bbox[2] - bbox[0]
        lx = (w - lw) // 2 - bbox[0]
        ly = ty + i * line_height - bbox[1]
        draw.text((lx, ly), ln, font=f, fill=(*CREAM, 255))

    round_paste(target, layer, x, y, CORNER_RADIUS)


def render_brand_tile(target, x, y, w, h):
    layer = Image.new("RGBA", (w, h), (*CREAM, 255))
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA")
        max_dim = int(min(w, h) * 0.82)
        lw, lh = logo.size
        scale = max_dim / max(lw, lh)
        logo = logo.resize((int(lw * scale), int(lh * scale)), Image.LANCZOS)
        lx = (w - logo.width) // 2
        ly = (h - logo.height) // 2
        layer.paste(logo, (lx, ly), logo)
    round_paste(target, layer, x, y, CORNER_RADIUS)


# Render one masonry per CTA variant
for slug, cta_text in CTA_VARIANTS:
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), WHITE)
    cols = build_columns(cta_text)
    for col_idx, col_tiles in enumerate(cols):
        x = MARGIN + col_idx * (col_w + GUTTER_COL)
        y = MARGIN
        for tile in col_tiles:
            h = tile["height"]
            kind = tile["kind"]
            if kind == "img":
                render_image_tile(canvas, x, y, col_w, h, tile["key"])
            elif kind == "cta":
                render_cta_tile(canvas, x, y, col_w, h, tile["text"])
            elif kind == "brand":
                render_brand_tile(canvas, x, y, col_w, h)
            elif kind == "solid":
                render_solid_tile(canvas, x, y, col_w, h, tile["color"])
            y += h + GUTTER_TILE
    out_path = OUT / f"masonry-v5-cta-{slug}.png"
    canvas.save(out_path, "PNG", optimize=True)
    print(f"Saved: {out_path}  ({out_path.stat().st_size:,} bytes)")
