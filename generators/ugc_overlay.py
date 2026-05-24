"""Hybrid UGC overlay renderer — PIL caption boxes + pills on top of an
AI-generated clean photo.

This is the first-class module behind the `adc ugc-ad` CLI command. It was
promoted from `scripts/native_ugc_overlay.py` (left as a thin wrapper) so
the rendering primitives are importable and the layout is data-driven
(brief-driven layouts or named registry entries).

Pipeline:
  1. hf-web (or any source) produces a clean base photo with NO text.
  2. This module composites Instagram-style caption boxes + brand-colored
     highlight pills onto the photo.
  3. Output is a deterministic PNG — pixel-perfect text, ~$0 cost.

Why split AI photo from PIL text:
  - AI image models render unreliable text (gibberish letterforms, drift)
  - PIL gives total control over font, color, position, brand consistency
  - Same photo can be re-overlaid with different copy without re-paying
    the AI-edit cost

The layout system has two parallel paths:

  REGISTRY  Named layouts in LAYOUTS dict (legacy fallback for the four
            seed concepts: social-mirror, native-reel-woman/man,
            native-pain-010). Each is a list of (text, y_pct, font_size_pct,
            kind, emoji) tuples.

  BRIEF     List of models.brief.TextOverlay entries on a CreativeBrief.
            Used by `adc ugc-ad --brief <path>` so per-ad copy lives with
            the brief instead of in hardcoded Python.

Brand styling (pill color, font path, etc.) comes from the brand.yaml
`ugc_voice` block via `UgcStyle.from_brand_voice()`. The legacy
SecondKind-Bold preset is hardcoded as `DEFAULT_UGC_STYLE` so the script
works without a brand argument.
"""

from __future__ import annotations

import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Union

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from models.brand import UgcVoice
    from models.brief import TextOverlay


# ─── Font fallbacks ─────────────────────────────────────────────────────────

# Platform-specific defaults used when a brand has no ugc_voice.font_fallback.
# These mirror the historical SecondKind preset (Windows-only) so existing
# invocations of the old script keep working.
_DEFAULT_FONT_FALLBACKS: dict[str, str] = {
    "windows": "C:/Windows/Fonts/segoeuib.ttf",
    "macos": "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "linux": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}

_DEFAULT_EMOJI_FALLBACKS: dict[str, str] = {
    "windows": "C:/Windows/Fonts/seguiemj.ttf",
    "macos": "/System/Library/Fonts/Apple Color Emoji.ttc",
    "linux": "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
}


def _detect_platform() -> str:
    """Return 'windows', 'macos', or 'linux' for the current platform."""
    sysname = platform.system().lower()
    if sysname == "darwin":
        return "macos"
    if sysname == "windows":
        return "windows"
    return "linux"


def _resolve_font_path(fallbacks: dict[str, str], default: dict[str, str]) -> str:
    """Pick the font path matching the current platform, falling back to defaults."""
    plat = _detect_platform()
    return fallbacks.get(plat) or default.get(plat) or default["windows"]


# ─── Style dataclasses ──────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert '#fcb348' or 'fcb348' to (r, g, b). Returns black on parse fail."""
    if not hex_color:
        return (0, 0, 0)
    s = hex_color.lstrip("#").strip()
    if len(s) != 6:
        return (0, 0, 0)
    try:
        return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    except ValueError:
        return (0, 0, 0)


@dataclass
class BoxStyle:
    """A single solid caption box (white-on-photo, Instagram-style)."""

    bg_color: tuple[int, int, int] = (255, 255, 255)
    text_color: tuple[int, int, int] = (0, 0, 0)
    corner_radius_pct: float = 1.3   # % of frame width — slight rounding
    pad_x_pct: float = 1.4
    pad_y_pct: float = 1.1


@dataclass
class PillStyle:
    """A fully-rounded colored highlight pill (brand marigold by default)."""

    bg_color: tuple[int, int, int] = (252, 179, 72)   # #fcb348
    text_color: tuple[int, int, int] = (28, 25, 23)   # #1c1917
    pad_x_pct: float = 1.8
    pad_y_pct: float = 1.0


@dataclass
class UgcStyle:
    """Brand-resolved styling bundle for an entire render.

    Built either from a brand's `ugc_voice` block via `from_brand_voice()`
    or assembled manually for the legacy SecondKind preset.
    """

    box: BoxStyle = field(default_factory=BoxStyle)
    pill: PillStyle = field(default_factory=PillStyle)
    font_path: str = field(
        default_factory=lambda: _resolve_font_path({}, _DEFAULT_FONT_FALLBACKS)
    )
    emoji_font_path: str = field(
        default_factory=lambda: _resolve_font_path({}, _DEFAULT_EMOJI_FALLBACKS)
    )

    @classmethod
    def from_brand_voice(cls, voice: "UgcVoice | None") -> "UgcStyle":
        """Build a UgcStyle from a brand's `ugc_voice` block.

        Empty / missing fields fall back to the SecondKind-Bold defaults so
        partially-configured brands still render.
        """
        if voice is None:
            return cls()

        box = BoxStyle(
            bg_color=_hex_to_rgb(voice.box_bg_color) if voice.box_bg_color else (255, 255, 255),
            text_color=_hex_to_rgb(voice.box_text_color) if voice.box_text_color else (0, 0, 0),
        )
        pill = PillStyle(
            bg_color=_hex_to_rgb(voice.pill_highlight_color) if voice.pill_highlight_color else (252, 179, 72),
            text_color=_hex_to_rgb(voice.pill_text_color) if voice.pill_text_color else (28, 25, 23),
        )
        font_path = _resolve_font_path(voice.font_fallback or {}, _DEFAULT_FONT_FALLBACKS)
        emoji_path = _resolve_font_path(voice.emoji_font_fallback or {}, _DEFAULT_EMOJI_FALLBACKS)

        return cls(box=box, pill=pill, font_path=font_path, emoji_font_path=emoji_path)


# Single hardcoded default — keeps the old script working with no args.
DEFAULT_UGC_STYLE = UgcStyle()


# ─── Layout registry ────────────────────────────────────────────────────────
# Each entry: (text, y_position_pct, font_size_pct, kind, emoji)
#   kind: "box" = white text box, "pill" = brand-marigold highlight pill
#   y_position_pct: 0.0 (top) to 1.0 (bottom)
#   font_size_pct: text height as % of frame height (~2.0-2.8 = native scale)

LayoutTuple = tuple[str, float, float, str, Union[str, None]]

LAYOUTS: dict[str, list[LayoutTuple]] = {
    # Social Mirror — UGC hand sweeping bottles aside
    "social-mirror": [
        ("tried 4 different probiotics.",     0.075, 2.4, "box", None),
        ("50 billion CFU each",               0.140, 2.4, "pill", "💀"),
        ("none of them worked.",              0.205, 2.4, "box", None),
        ("you can stop trying\nnew probiotics now.", 0.770, 2.8, "box", None),
        ("trust me on this ↓",                0.905, 2.0, "box", None),
    ],

    # native-reel-woman — frustrated-user persona holding the jar
    "native-reel-woman": [
        ("i've tried 4 different probiotics.", 0.060, 2.3, "box", None),
        ("50 billion CFUs each",               0.122, 2.3, "pill", "💀"),
        ("still bloated by 7pm.",              0.184, 2.3, "box", None),
        ("turns out roughly 70%\ndie before reaching your gut.", 0.770, 2.6, "box", None),
        ("trust me on this ↓",                 0.910, 2.0, "box", None),
    ],

    # native-reel-man — credentialed-peer persona at kitchen island
    # Bottom headline is the mechanism punchline (NOT social-mirror's headline)
    "native-reel-man": [
        ("the reason your probiotic isn't working",  0.060, 2.1, "box", None),
        ("has nothing to do with the brand.",        0.118, 2.1, "box", None),
        ("~70% die before reaching your gut",        0.180, 2.1, "pill", None),
        ("the bacteria isn't the problem.\nthe delivery is.", 0.770, 2.6, "box", None),
        ("trust me on this ↓",                       0.910, 2.0, "box", None),
    ],

    # native-pain-010 — vindication-first UGC version of Concept 1
    "native-pain-010": [
        ("if your probiotic did nothing,",           0.060, 2.3, "box", None),
        ("you weren't the problem.",                 0.122, 2.3, "box", None),
        ("70% die before reaching your gut",         0.184, 2.3, "pill", "💀"),
        ("you weren't lazy.\nyour probiotic was dead.", 0.770, 2.6, "box", None),
        ("trust me on this ↓",                       0.910, 2.0, "box", None),
    ],
}


def list_layouts() -> list[str]:
    """Return the registry layout names. Used by CLI help text."""
    return sorted(LAYOUTS.keys())


def text_overlays_from_layout(layout_name: str) -> list[dict]:
    """Convert a registry layout to TextOverlay-compatible dicts.

    Returned dicts use `models.brief.TextOverlay` field names so callers
    can homogenize the brief-driven and registry-driven code paths.
    """
    if layout_name not in LAYOUTS:
        raise KeyError(
            f"Layout '{layout_name}' not found. Available: {list_layouts()}"
        )
    return [
        {
            "text": text,
            "y_pct": y_pct,
            "font_size_pct": font_size_pct,
            "kind": kind,
            "emoji": emoji,
        }
        for (text, y_pct, font_size_pct, kind, emoji) in LAYOUTS[layout_name]
    ]


# ─── Font loader ────────────────────────────────────────────────────────────


def _load_font(size: int, font_path: str) -> ImageFont.FreeTypeFont:
    """Load a TTF. Falls back to PIL's default bitmap font if the file is missing."""
    try:
        return ImageFont.truetype(font_path, size)
    except OSError:
        return ImageFont.load_default()


# ─── Text measurement / drawing primitives ──────────────────────────────────


def _render_pixel_bbox(
    draw: ImageDraw.ImageDraw,
    text: str,
    emoji: str | None,
    font: ImageFont.FreeTypeFont,
    emoji_font: ImageFont.FreeTypeFont | None,
) -> tuple[int, int]:
    """Return (width, height) of actually-rendered pixels for text+optional emoji."""
    if "\n" in text:
        lines = text.split("\n")
        line_bboxes = [draw.textbbox((0, 0), l, font=font, anchor="lt") for l in lines]
        line_widths = [b[2] - b[0] for b in line_bboxes]
        line_heights = [b[3] - b[1] for b in line_bboxes]
        line_slot = max(line_heights)
        line_gap = int(line_slot * 0.2)
        total_h = line_slot * len(lines) + line_gap * (len(lines) - 1)
        return max(line_widths), total_h

    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    if emoji and emoji_font:
        ebbox = draw.textbbox(
            (0, 0), emoji, font=emoji_font, anchor="lt", embedded_color=True
        )
        ew = ebbox[2] - ebbox[0]
        eh = ebbox[3] - ebbox[1]
        gap = int(font.size * 0.25)
        w += ew + gap
        h = max(h, eh)
    return w, h


def _draw_text_at_pixel(
    draw: ImageDraw.ImageDraw,
    top_left: tuple[int, int],
    text: str,
    emoji: str | None,
    font: ImageFont.FreeTypeFont,
    emoji_font: ImageFont.FreeTypeFont | None,
    fill: tuple,
) -> None:
    """Draw text so its actually-rendered pixels start at top_left."""
    x, y = top_left
    if "\n" in text:
        lines = text.split("\n")
        line_bboxes = [draw.textbbox((0, 0), l, font=font, anchor="lt") for l in lines]
        line_widths = [b[2] - b[0] for b in line_bboxes]
        line_heights = [b[3] - b[1] for b in line_bboxes]
        line_slot = max(line_heights)
        line_gap = int(line_slot * 0.2)
        max_w = max(line_widths)
        for i, line in enumerate(lines):
            lb = line_bboxes[i]
            lw = line_widths[i]
            line_x = x + (max_w - lw) // 2
            draw_x = line_x - lb[0]
            draw_y = y + i * (line_slot + line_gap) - lb[1]
            draw.text((draw_x, draw_y), line, font=font, fill=fill, anchor="lt")
        return

    bbox = draw.textbbox((0, 0), text, font=font, anchor="lt")
    draw_x = x - bbox[0]
    draw_y = y - bbox[1]
    draw.text((draw_x, draw_y), text, font=font, fill=fill, anchor="lt")

    if emoji and emoji_font:
        text_w = bbox[2] - bbox[0]
        ebbox = draw.textbbox(
            (0, 0), emoji, font=emoji_font, anchor="lt", embedded_color=True
        )
        gap = int(font.size * 0.25)
        text_visual_h = bbox[3] - bbox[1]
        emoji_visual_h = ebbox[3] - ebbox[1]
        emoji_y_target = y + (text_visual_h - emoji_visual_h) // 2
        emoji_draw_x = x + text_w + gap - ebbox[0]
        emoji_draw_y = emoji_y_target - ebbox[1]
        draw.text(
            (emoji_draw_x, emoji_draw_y),
            emoji,
            font=emoji_font,
            embedded_color=True,
            anchor="lt",
        )


def _draw_rounded_box(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    radius: int,
    fill: tuple,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


# ─── Layout normalization ───────────────────────────────────────────────────


def _normalize_layout(
    layout: Union[str, list["TextOverlay"], list[dict], list[LayoutTuple]],
) -> list[dict]:
    """Coerce any supported layout input into a list of overlay dicts.

    Supported inputs:
      - str: a key in the LAYOUTS registry
      - list of TextOverlay models (from a brief)
      - list of dicts (already in the canonical schema)
      - list of (text, y_pct, font_size_pct, kind, emoji) tuples (legacy)
    """
    if isinstance(layout, str):
        return text_overlays_from_layout(layout)

    if not isinstance(layout, list):
        raise TypeError(
            f"Unsupported layout type: {type(layout).__name__}. "
            f"Expected str, list[TextOverlay], list[dict], or list[tuple]."
        )

    normalized: list[dict] = []
    for entry in layout:
        if isinstance(entry, dict):
            normalized.append(entry)
            continue
        # Tuple form (legacy)
        if isinstance(entry, tuple) and len(entry) == 5:
            text, y_pct, font_size_pct, kind, emoji = entry
            normalized.append({
                "text": text,
                "y_pct": y_pct,
                "font_size_pct": font_size_pct,
                "kind": kind,
                "emoji": emoji,
            })
            continue
        # Pydantic model form (TextOverlay)
        if hasattr(entry, "model_dump"):
            normalized.append(entry.model_dump())
            continue
        raise TypeError(
            f"Unsupported layout entry type: {type(entry).__name__}. "
            f"Expected dict, tuple, or TextOverlay model."
        )
    return normalized


# ─── Main render function ───────────────────────────────────────────────────


def render_native_ugc_ad(
    base_image: Path,
    out_path: Path,
    layout: Union[str, list["TextOverlay"], list[dict]] = "social-mirror",
    style: UgcStyle | None = None,
) -> Path:
    """Composite caption boxes + pills onto a base photo and write to out_path.

    Args:
      base_image:  Path to the AI-generated clean photo (no text).
      out_path:    Where to write the final composite PNG.
      layout:      Either a registry name (str), a list of TextOverlay
                   models from a brief, or a pre-built list of dicts /
                   legacy tuples. See `_normalize_layout`.
      style:       Brand-resolved styling. Defaults to SecondKind-Bold preset.

    Returns:
      The output path (same as `out_path`).

    Raises:
      FileNotFoundError if base_image doesn't exist.
      KeyError if layout is a string not in the registry.
    """
    base_image = Path(base_image)
    out_path = Path(out_path)

    if not base_image.exists():
        raise FileNotFoundError(f"Base image not found: {base_image}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    style = style or DEFAULT_UGC_STYLE
    overlays = _normalize_layout(layout)

    img = Image.open(base_image).convert("RGBA")
    W, H = img.size

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    box_style = style.box
    pill_style = style.pill

    for entry in overlays:
        text = entry["text"]
        y_pct = float(entry["y_pct"])
        font_size_pct = float(entry["font_size_pct"])
        kind = entry.get("kind", "box")
        emoji = entry.get("emoji")

        font_size = int(H * font_size_pct / 100)
        font = _load_font(font_size, style.font_path)
        emoji_font = (
            _load_font(int(font_size * 0.95), style.emoji_font_path)
            if emoji
            else None
        )

        if kind == "box":
            pad_x = int(W * box_style.pad_x_pct / 100)
            pad_y = int(H * box_style.pad_y_pct / 100)
            corner_radius = int(W * box_style.corner_radius_pct / 100)
            bg_color = box_style.bg_color + (255,)
            text_color = box_style.text_color
        else:  # pill
            pad_x = int(W * pill_style.pad_x_pct / 100)
            pad_y = int(H * pill_style.pad_y_pct / 100)
            bg_color = pill_style.bg_color + (255,)
            text_color = pill_style.text_color
            corner_radius = None  # computed after we know box height

        text_w, text_h = _render_pixel_bbox(draw, text, emoji, font, emoji_font)

        box_w = text_w + 2 * pad_x
        box_h = text_h + 2 * pad_y
        box_x = (W - box_w) // 2
        box_y = int(H * y_pct)

        if corner_radius is None:
            corner_radius = box_h // 2

        _draw_rounded_box(
            draw,
            (box_x, box_y, box_x + box_w, box_y + box_h),
            radius=corner_radius,
            fill=bg_color,
        )

        _draw_text_at_pixel(
            draw,
            (box_x + pad_x, box_y + pad_y),
            text,
            emoji,
            font,
            emoji_font,
            text_color,
        )

    composite = Image.alpha_composite(img, overlay).convert("RGB")
    composite.save(out_path)
    return out_path


# ─── CTA validator ──────────────────────────────────────────────────────────


def find_disallowed_ctas(
    overlays: list[dict] | list["TextOverlay"],
    voice: "UgcVoice | None",
) -> list[tuple[str, str]]:
    """Return (overlay_text, disallowed_phrase) pairs for every overlay that
    contains a phrase from `voice.do_not_use_ctas`.

    Returns [] if voice is None or has no do_not_use_ctas list.
    Matching is case-insensitive substring matching — `do_not_use_ctas`
    entries are short CTA phrases so substring matches stay precise.
    """
    if voice is None or not voice.do_not_use_ctas:
        return []

    normalized = _normalize_layout(overlays) if overlays and not isinstance(overlays[0], dict) else overlays
    if not normalized:
        return []

    bad: list[tuple[str, str]] = []
    for entry in normalized:
        text = entry["text"] if isinstance(entry, dict) else entry.text
        text_lower = text.lower()
        for phrase in voice.do_not_use_ctas:
            if phrase.lower().strip() in text_lower:
                bad.append((text, phrase))
    return bad
