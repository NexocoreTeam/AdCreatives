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
