"""Composite advertorial text over a generated background image.

Deterministic PIL typesetting so headlines never suffer AI-rendered glyph
artifacts. Spec-driven: a JSON file describes scrim, quote glyph, text blocks,
and dashed-leader labels in resolution-independent fractional coordinates.

Usage: python scripts/ad_text_overlay.py <background.jpg> <spec.json> <out.jpg>

Spec schema (all coords are 0-1 fractions of canvas width/height):
{
  "scrim": {"start": 0.55, "strength": 0.82},          # optional bottom gradient
  "quote": {"x": 0.09, "y": 0.575, "size": 0.075, "color": "#F2C14E"},  # optional
  "blocks": [
    {"text": "Line one\nLine two", "font": "serif|sans|mono",
     "size": 0.052, "color": "#F0D084", "x": 0.09, "y": 0.63,
     "line_spacing": 1.22, "tracking": 0}
  ],
  "labels": [                                           # optional dashed leaders
    {"text": "vagus nerve", "color": "#9AA0A6", "size": 0.021,
     "tx": 0.14, "ty": 0.35, "lx1": 0.30, "ly1": 0.357, "lx2": 0.46, "ly2": 0.357}
  ],
  "out_size": [1080, 1620]
}
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS = {
    "serif": "C:/Windows/Fonts/georgiab.ttf",
    "serif_reg": "C:/Windows/Fonts/georgia.ttf",
    "sans": "C:/Windows/Fonts/segoeuib.ttf",
    "sans_reg": "C:/Windows/Fonts/segoeui.ttf",
    "mono": "C:/Windows/Fonts/consolab.ttf",
}


def load_font(kind: str, px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONTS[kind], px)


def apply_scrim(img: Image.Image, start: float, strength: float) -> Image.Image:
    w, h = img.size
    overlay = Image.new("L", (1, h), 0)
    y0 = int(h * start)
    for y in range(y0, h):
        t = (y - y0) / max(1, h - y0)
        overlay.putpixel((0, y), int(255 * strength * (t ** 1.2)))
    alpha = overlay.resize((w, h))
    black = Image.new("RGB", (w, h), (4, 5, 8))
    return Image.composite(black, img, alpha)


def draw_dashed(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, color, width, dash=9, gap=7):
    length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    if length == 0:
        return
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    dist = 0.0
    while dist < length:
        seg = min(dash, length - dist)
        sx, sy = x1 + ux * dist, y1 + uy * dist
        ex, ey = x1 + ux * (dist + seg), y1 + uy * (dist + seg)
        draw.line([(sx, sy), (ex, ey)], fill=color, width=width)
        dist += dash + gap


def render(background: Path, spec_path: Path, out_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    img = Image.open(background).convert("RGB")
    w, h = img.size

    if "scrim" in spec:
        img = apply_scrim(img, spec["scrim"]["start"], spec["scrim"]["strength"])

    draw = ImageDraw.Draw(img)

    if "quote" in spec:
        q = spec["quote"]
        qfont = load_font("serif", int(h * q["size"]))
        draw.text((int(w * q["x"]), int(h * q["y"])), "“", font=qfont, fill=q["color"])

    for block in spec.get("blocks", []):
        font = load_font(block["font"], int(h * block["size"]))
        x = int(w * block["x"])
        y = int(h * block["y"])
        spacing = block.get("line_spacing", 1.22)
        for line in block["text"].split("\n"):
            draw.text((x, y), line, font=font, fill=block["color"])
            y += int(h * block["size"] * spacing)

    for label in spec.get("labels", []):
        font = load_font("sans", int(h * label["size"]))
        draw.text(
            (int(w * label["tx"]), int(h * label["ty"])),
            label["text"], font=font, fill=label["color"],
        )
        draw_dashed(
            draw,
            int(w * label["lx1"]), int(h * label["ly1"]),
            int(w * label["lx2"]), int(h * label["ly2"]),
            label["color"], max(2, int(h * 0.0012)),
        )

    if "battery" in spec:
        b = spec["battery"]
        cx, cy = w * b["cx"], h * b["cy"]
        bw, bh = w * b["w"], h * b["h"]
        segs = b.get("seg_count", 5)
        shell = [cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2]
        radius = bh * 0.22
        outline_w = max(2, int(bh * 0.09))
        draw.rounded_rectangle(shell, radius=radius, outline="#7A7F87", width=outline_w)
        nub_w, nub_h = bw * 0.03, bh * 0.42
        draw.rounded_rectangle(
            [shell[2] + nub_w * 0.6, cy - nub_h / 2, shell[2] + nub_w * 1.9, cy + nub_h / 2],
            radius=nub_w * 0.5, fill="#7A7F87",
        )
        pad = bh * 0.22
        gap = bw * 0.012
        seg_w = (bw - 2 * pad - gap * (segs - 1)) / segs
        for i in range(segs):
            x0 = shell[0] + pad + i * (seg_w + gap)
            box = [x0, shell[1] + pad, x0 + seg_w, shell[3] - pad]
            if i == 0:
                draw.rounded_rectangle(box, radius=radius * 0.4, fill="#D8442B")
                pfont = load_font("sans", int(bh * 0.42))
                ptext = f"{b['pct']}%"
                tb = draw.textbbox((0, 0), ptext, font=pfont)
                draw.text(
                    (x0 + seg_w / 2 - (tb[2] - tb[0]) / 2, cy - (tb[3] - tb[1]) / 2 - tb[1]),
                    ptext, font=pfont, fill="#2B0F0A",
                )
            else:
                draw.rounded_rectangle(box, radius=radius * 0.4, fill="#23262C")
        if b.get("label"):
            lfont = load_font("serif", int(h * b.get("label_size", 0.022)))
            ltext = b["label"]
            lb = draw.textbbox((0, 0), ltext, font=lfont)
            ly = cy - bh * 3.4
            draw.text((cx - (lb[2] - lb[0]) / 2, ly), ltext, font=lfont, fill=b.get("label_color", "#F0D084"))
            ax = cx
            draw_dashed(draw, ax, ly + (lb[3] - lb[1]) * 1.7, ax, shell[1] - bh * 0.35,
                        b.get("label_color", "#F0D084"), max(2, int(h * 0.0012)))
            ah = bh * 0.28
            draw.polygon(
                [(ax - ah * 0.55, shell[1] - bh * 0.35 - ah), (ax + ah * 0.55, shell[1] - bh * 0.35 - ah), (ax, shell[1] - bh * 0.35)],
                fill=b.get("label_color", "#F0D084"),
            )

    out_w, out_h = spec.get("out_size", [1080, 1620])
    img = img.resize((out_w, out_h), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=88, optimize=True)
    print(out_path)


def main() -> None:
    if len(sys.argv) != 4:
        sys.exit("usage: python scripts/ad_text_overlay.py <background> <spec.json> <out.jpg>")
    render(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))


if __name__ == "__main__":
    main()
