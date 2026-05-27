"""PIL text-overlay layer for ad images.

Why this exists: AI image models (soul_2, NB2, etc.) are unreliable at
rendering legible text. soul_2 in particular produces gibberish letterforms
because it's tuned for portrait photography, not typography. Production
ad workflows split the two passes:

    1. AI generates the photo (face, scene, product, mood)
    2. PIL renders the text overlay (quote, CTA, badge) on top

The PIL pass is deterministic, pixel-perfect, ~$0 in cost, and gives
total control over brand presets (font, color, position, wash).

This module exposes one main function — `render_ad_overlay()` — plus
the `BrandPreset` dataclass that defines the visual register per
client. SecondKind preset is included; new clients add their own.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ─── Brand presets ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BrandPreset:
    """Visual register for ad text overlays — one per client.

    Colors are RGB tuples. `wash_alpha` is the bottom-wash opacity (0-255).
    Font paths default to Windows system fonts; override per client.
    """

    name: str
    accent_color: tuple[int, int, int]            # CTA pill fill, body-text accents
    text_color: tuple[int, int, int]              # main quote text
    wash_color: tuple[int, int, int]              # bottom-third background wash
    wash_alpha: int = 230                          # 0 (transparent) → 255 (opaque)
    cta_text_color: tuple[int, int, int] = (255, 255, 255)
    font_regular: Path = field(
        default_factory=lambda: Path("C:/Windows/Fonts/segoeui.ttf")
    )
    font_semibold: Path = field(
        default_factory=lambda: Path("C:/Windows/Fonts/seguisb.ttf")
    )
    font_bold: Path = field(
        default_factory=lambda: Path("C:/Windows/Fonts/segoeuib.ttf")
    )


# SecondKind defaults — sample from the Rheal reference + Gut Balance label palette
SECONDKIND_PRESET = BrandPreset(
    name="secondkind",
    accent_color=(27, 94, 75),         # #1B5E4B deep teal-green
    text_color=(27, 94, 75),
    wash_color=(254, 252, 246),        # #FEFCF6 warm cream
    wash_alpha=235,
)


# Saved by Grace Co. — modern Christian farmhouse, warm-red accent on cream wash
SAVEDBYGRACE_PRESET = BrandPreset(
    name="savedbygrace",
    accent_color=(178, 58, 72),        # #B23A48 washed warm brand red
    text_color=(50, 35, 22),           # #322316 warm dark brown
    wash_color=(245, 240, 230),        # #F5F0E6 cream linen
    wash_alpha=235,
)


# ─── Public API ─────────────────────────────────────────────────────────────


def render_ad_overlay(
    base_image: Path,
    *,
    hero_quote: str,
    cta_text: str,
    out_path: Path,
    preset: BrandPreset = SECONDKIND_PRESET,
    trustpilot_icon: Path | None = None,
) -> Path:
    """Composite a quote + CTA pill onto a base image and save the final ad.

    Layout (fixed for MVP — vision-LLM smart-layout comes later):
        Upper 60%: untouched base image
        Lower 40%: soft cream wash, gradient-faded into the photo
        Quote: large sans-serif centered in the wash zone
        CTA: rounded pill bottom-center
        Trustpilot icon (optional): small, bottom-left of the wash zone
    """
    base_image = Path(base_image)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(base_image).convert("RGB")
    W, H = img.size

    # Layer the overlay onto an RGBA canvas so the wash gradient blends nicely
    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # ── Bottom wash (gradient fade from transparent → cream) ─────────────
    wash_top = int(H * 0.55)
    wash_bottom = H
    wash_height = wash_bottom - wash_top
    wash_rgb = preset.wash_color
    wash_alpha_max = preset.wash_alpha
    fade_band = int(wash_height * 0.18)  # 18% of wash is gradient fade-in

    for y in range(wash_top, wash_bottom):
        rel = y - wash_top
        if rel < fade_band:
            alpha = int(wash_alpha_max * (rel / fade_band))
        else:
            alpha = wash_alpha_max
        draw.line([(0, y), (W, y)], fill=(*wash_rgb, alpha))

    # ── Hero quote (centered in the bottom wash zone) ────────────────────
    quote_size = _scale(W, 0.038)  # ~38px at 1000px wide
    quote_font = _load_font(preset.font_semibold, quote_size)
    quote_text = _normalize_quote(hero_quote)

    # Wrap to fit within 84% of the image width
    max_text_width = int(W * 0.84)
    wrapped_lines = _wrap_text(quote_text, quote_font, max_text_width, draw)

    # Stack lines centered, vertically positioned within the wash
    line_height = int(quote_size * 1.25)
    block_height = line_height * len(wrapped_lines)
    quote_top = wash_top + int(wash_height * 0.28)
    for i, line in enumerate(wrapped_lines):
        bbox = draw.textbbox((0, 0), line, font=quote_font)
        line_w = bbox[2] - bbox[0]
        x = (W - line_w) // 2
        y = quote_top + i * line_height
        draw.text((x, y), line, font=quote_font, fill=(*preset.text_color, 255))

    # ── CTA pill (bottom-center, below the quote) ─────────────────────────
    cta_size = _scale(W, 0.022)
    cta_font = _load_font(preset.font_semibold, cta_size)
    cta_label = cta_text.upper().strip()
    cta_bbox = draw.textbbox((0, 0), cta_label, font=cta_font)
    cta_text_w = cta_bbox[2] - cta_bbox[0]
    cta_text_h = cta_bbox[3] - cta_bbox[1]

    pill_pad_x = int(cta_size * 1.4)
    pill_pad_y = int(cta_size * 0.7)
    pill_w = cta_text_w + 2 * pill_pad_x
    pill_h = cta_text_h + 2 * pill_pad_y

    pill_y_top = quote_top + block_height + int(wash_height * 0.06)
    pill_x_left = (W - pill_w) // 2

    draw.rounded_rectangle(
        (pill_x_left, pill_y_top, pill_x_left + pill_w, pill_y_top + pill_h),
        radius=pill_h // 2,
        fill=(*preset.accent_color, 255),
    )
    # Center the text precisely inside the pill — use the textbbox top
    # to correct for fonts whose ascent doesn't match the bbox y=0.
    text_x = pill_x_left + (pill_w - cta_text_w) // 2 - cta_bbox[0]
    text_y = pill_y_top + (pill_h - cta_text_h) // 2 - cta_bbox[1]
    draw.text(
        (text_x, text_y),
        cta_label,
        font=cta_font,
        fill=(*preset.cta_text_color, 255),
    )

    # ── Trustpilot icon (optional small badge bottom-left) ────────────────
    if trustpilot_icon and Path(trustpilot_icon).exists():
        badge = Image.open(trustpilot_icon).convert("RGBA")
        badge_w = int(W * 0.14)
        badge_h = int(badge.height * (badge_w / badge.width))
        badge = badge.resize((badge_w, badge_h), Image.LANCZOS)
        badge_x = int(W * 0.05)
        badge_y = pill_y_top + (pill_h - badge_h) // 2
        overlay.alpha_composite(badge, (badge_x, badge_y))

    # Final composite + save (PNG to preserve quality; switch to JPEG if size matters)
    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    final.save(out_path, format="PNG", optimize=True)
    return out_path


# ─── Helpers ────────────────────────────────────────────────────────────────


def _scale(width: int, fraction: float) -> int:
    """Scale a font/size relative to image width. Min 16px floor."""
    return max(16, int(width * fraction))


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    """Load a TTF with a graceful fallback to PIL's default bitmap font."""
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _normalize_quote(text: str) -> str:
    """Strip any wrapping quote marks the caller might have included.

    The renderer adds proper curly quotes itself (or omits them entirely
    based on the preset). Caller passes the bare text.
    """
    s = text.strip()
    # Remove paired ASCII or curly quotes if they wrap the whole string
    pairs = [('"', '"'), ("'", "'"), ("“", "”"), ("‘", "’")]
    for open_q, close_q in pairs:
        if s.startswith(open_q) and s.endswith(close_q):
            s = s[len(open_q):-len(close_q)].strip()
            break
    return f"“{s}”"


def render_mixed_caption_overlay(
    base_image: Path,
    *,
    items: list[dict],
    out_path: Path,
    preset: BrandPreset = SECONDKIND_PRESET,
    position: float = 0.5,
    line_gap: int | None = None,
    font_size_frac: float = 0.034,
    handwritten_font_path: Path | None = None,
    handwritten_size_frac: float = 0.052,
) -> Path:
    """Mixed caption overlay — each item is a pill or handwritten line.

    items: list of dicts. Each dict has type "pill" or "handwritten":
        {"type": "pill",       "text": str,
         "pill_color": (r,g,b)|None,  # None = preset.wash_color
         "text_color": (r,g,b)|None}  # None = preset.text_color
        {"type": "handwritten","text": str,
         "color": (r,g,b)|None,
         "size_frac": float|None}     # optional override

    Lines stacked vertically, centered on canvas around `position` (0..1).
    No drop shadows — flat native style.
    """
    base_image = Path(base_image)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(base_image).convert("RGB")
    W, H = img.size

    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pill_font_size = _scale(W, font_size_frac)
    hw_font_size_default = _scale(W, handwritten_size_frac)

    bold_candidates = [
        Path(r"C:/Windows/Fonts/seguisb.ttf"),
        Path(r"C:/Windows/Fonts/segoeuib.ttf"),
        preset.font_bold,
    ]
    pill_font_path = next((p for p in bold_candidates if Path(p).exists()), preset.font_bold)
    pill_font = _load_font(pill_font_path, pill_font_size)

    # Handwritten font: caller-supplied or fallback to brand regular
    hw_font_path = handwritten_font_path or preset.font_regular
    hw_font = _load_font(hw_font_path, hw_font_size_default)

    pad_x = int(pill_font_size * 0.7)
    pad_y = int(pill_font_size * 0.32)
    gap = line_gap if line_gap is not None else int(pill_font_size * 0.45)

    # Pre-measure all items
    prepped = []
    for it in items:
        if it["type"] == "pill":
            bbox = draw.textbbox((0, 0), it["text"], font=pill_font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            pill_w = text_w + 2 * pad_x
            pill_h = text_h + 2 * pad_y
            prepped.append({**it, "font": pill_font, "bbox": bbox,
                            "box_w": pill_w, "box_h": pill_h})
        elif it["type"] == "handwritten":
            font = hw_font
            if it.get("size_frac"):
                font = _load_font(hw_font_path, _scale(W, it["size_frac"]))
            bbox = draw.textbbox((0, 0), it["text"], font=font)
            text_w = bbox[2] - bbox[0]
            text_h = bbox[3] - bbox[1]
            prepped.append({**it, "font": font, "bbox": bbox,
                            "box_w": text_w, "box_h": text_h})

    total_h = sum(p["box_h"] for p in prepped) + gap * (len(prepped) - 1)
    stack_top = int(H * position) - total_h // 2

    y = stack_top
    for p in prepped:
        bbox = p["bbox"]
        box_w, box_h = p["box_w"], p["box_h"]
        x_left = (W - box_w) // 2

        if p["type"] == "pill":
            pill_color = p.get("pill_color") or preset.wash_color
            text_color = p.get("text_color") or preset.text_color
            draw.rounded_rectangle(
                (x_left, y, x_left + box_w, y + box_h),
                radius=box_h // 2,
                fill=(*pill_color, 255),
            )
            text_x = x_left + pad_x - bbox[0]
            text_y = y + pad_y - bbox[1]
            draw.text((text_x, text_y), p["text"], font=p["font"], fill=(*text_color, 255))
        else:  # handwritten
            text_color = p.get("color") or preset.text_color
            text_x = x_left - bbox[0]
            text_y = y - bbox[1]
            draw.text((text_x, text_y), p["text"], font=p["font"], fill=(*text_color, 255))

        y += box_h + gap

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    final.save(out_path, format="PNG", optimize=True)
    return out_path


def render_tiktok_caption_overlay(
    base_image: Path,
    *,
    lines: list[str],
    out_path: Path,
    preset: BrandPreset = SECONDKIND_PRESET,
    position: float = 0.5,
    pill_color: tuple[int, int, int] | None = None,
    text_color: tuple[int, int, int] | None = None,
    line_gap: int | None = None,
    font_size_frac: float = 0.034,
) -> Path:
    """Native TikTok-style caption overlay — one auto-width pill per line.

    Unlike a single multi-line pill, TikTok captions render each line of
    text in its own background pill, stacked vertically. No drop shadow,
    bold sans typography, tight padding, optical-baseline-correct vertical
    centering.

    Per-line pills auto-fit to their text width. Vertical stack is centered
    horizontally on the image and centered vertically around `position`.
    """
    base_image = Path(base_image)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(base_image).convert("RGB")
    W, H = img.size

    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    pill_fill = (*(pill_color or preset.wash_color), 255)
    txt_fill = (*(text_color or preset.text_color), 255)

    # Bold sans for TikTok-native feel — fall back to brand bold font
    font_size = _scale(W, font_size_frac)
    bold_candidates = [
        Path(r"C:/Windows/Fonts/seguisb.ttf"),  # Segoe UI Semibold
        Path(r"C:/Windows/Fonts/segoeuib.ttf"), # Segoe UI Bold
        preset.font_bold,
    ]
    font_path = next((p for p in bold_candidates if Path(p).exists()), preset.font_bold)
    font = _load_font(font_path, font_size)

    pad_x = int(font_size * 0.7)
    pad_y = int(font_size * 0.32)
    gap = line_gap if line_gap is not None else int(font_size * 0.30)

    # Pre-measure each line's pill dimensions using the actual rendered bbox
    items = []
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        pill_w = text_w + 2 * pad_x
        pill_h = text_h + 2 * pad_y
        items.append({
            "text": ln,
            "bbox": bbox,
            "pill_w": pill_w,
            "pill_h": pill_h,
        })

    total_h = sum(it["pill_h"] for it in items) + gap * (len(items) - 1)
    stack_top = int(H * position) - total_h // 2

    y = stack_top
    for it in items:
        bbox = it["bbox"]
        pill_w, pill_h = it["pill_w"], it["pill_h"]
        pill_x = (W - pill_w) // 2

        # Pill body (NO shadow — flat TikTok style)
        draw.rounded_rectangle(
            (pill_x, y, pill_x + pill_w, y + pill_h),
            radius=pill_h // 2,
            fill=pill_fill,
        )

        # Optically centered text inside pill
        # Subtract bbox[0] for x to compensate for left-side glyph offset
        # Subtract bbox[1] for y to align top of rendered glyph
        text_x = pill_x + pad_x - bbox[0]
        text_y = y + pad_y - bbox[1]
        draw.text((text_x, text_y), it["text"], font=font, fill=txt_fill)

        y += pill_h + gap

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    final.save(out_path, format="PNG", optimize=True)
    return out_path


def render_centered_pill_overlay(
    base_image: Path,
    *,
    quote: str,
    out_path: Path,
    preset: BrandPreset = SECONDKIND_PRESET,
    position: float = 0.5,
    use_quotes: bool = False,
) -> Path:
    """Composite a centered rounded-pill quote onto a base image.

    Alternative to `render_ad_overlay()` for collage / Oddbird-style layouts
    where the text floats in the middle of the image rather than sitting in
    a bottom wash. Pill background uses `preset.wash_color` (cream), text
    uses `preset.text_color`. No CTA pill — caller composes the conversion
    layer separately if needed.

    `position` is the vertical center of the pill as a fraction of image
    height (0.5 = middle, 0.4 = upper-middle, 0.6 = lower-middle).
    """
    base_image = Path(base_image)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img = Image.open(base_image).convert("RGB")
    W, H = img.size

    canvas = img.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    text = _normalize_quote(quote) if use_quotes else quote.strip()
    quote_size = _scale(W, 0.032)
    quote_font = _load_font(preset.font_regular, quote_size)

    max_text_width = int(W * 0.74)
    lines = _wrap_text(text, quote_font, max_text_width, draw)
    line_height = int(quote_size * 1.32)

    # Measure widest line for pill width
    widest = 0
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=quote_font)
        widest = max(widest, bbox[2] - bbox[0])

    pad_x = int(quote_size * 1.1)
    pad_y = int(quote_size * 0.8)
    pill_w = widest + 2 * pad_x
    pill_h = line_height * len(lines) + 2 * pad_y
    pill_x = (W - pill_w) // 2
    pill_y = int(H * position) - pill_h // 2

    # Soft drop shadow
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        (pill_x + 3, pill_y + 6, pill_x + pill_w + 3, pill_y + pill_h + 6),
        radius=pill_h // 2,
        fill=(0, 0, 0, 80),
    )
    from PIL import ImageFilter as _IF
    shadow = shadow.filter(_IF.GaussianBlur(radius=8))
    overlay.alpha_composite(shadow)

    # Pill body
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
        radius=pill_h // 2,
        fill=(*preset.wash_color, 255),
    )

    # Text lines, centered horizontally per line
    ty = pill_y + pad_y
    for ln in lines:
        bbox = draw.textbbox((0, 0), ln, font=quote_font)
        lw = bbox[2] - bbox[0]
        lx = (W - lw) // 2 - bbox[0]
        draw.text((lx, ty - bbox[1]), ln, font=quote_font, fill=(*preset.text_color, 255))
        ty += line_height

    final = Image.alpha_composite(canvas, overlay).convert("RGB")
    final.save(out_path, format="PNG", optimize=True)
    return out_path


def _wrap_text(
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Word-wrap text to fit max_width when rendered with `font`."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines
