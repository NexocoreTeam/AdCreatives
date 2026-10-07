"""Native phone/app-screen components for organic-looking statics.

Renders the screens that make a post read as *organic* rather than designed: the Instagram
question box, an iMessage thread, an iOS Notes card and an iOS reminder/alert pop-up. They are
composited with PIL onto a clean base photo (or a flat colour), so the text is pixel-exact and
the same photo can be re-used with new copy at ~$0.

Why this exists: image models and generic brand overlays get these screens wrong (wrong font,
wrong bubble shape, brand pills where the UI has none), and the result looks like an ad.
The specs below come from measured organic templates (organic-content repo,
`ops/resources/NATIVE-UI-TEMPLATES.md`) and Apple/Instagram UI conventions.

Rules baked into the design:
  - Native screens keep their native look. Do NOT pass brand fonts/colours into them.
  - Only the words change. Keep copy short enough that bubbles/cards don't reflow oddly.
  - Content must be real: genuine messages (with permission), questions actually received,
    or a question the brand itself is asking. Never write a fake testimonial into a bubble.

All geometry is specified at a 1080 px-wide reference and scaled to the base image width.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Sequence

from PIL import Image, ImageDraw, ImageFilter, ImageFont

REF_W = 1080

# ─── Fonts ──────────────────────────────────────────────────────────────────
# Apple UI is SF Pro; it isn't licensed for this use, so we use the closest installed neo-grotesk.
# Segoe UI Variable is near SF Pro Text in proportion and colour. Override with SF/Inter paths
# on machines that have them (see `UI_FONT_CANDIDATES`).
UI_FONT_CANDIDATES = [
    "C:/Windows/Fonts/SegUIVar.ttf",
    "/System/Library/Fonts/SFNS.ttf",
    "/Library/Fonts/Inter.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
EMOJI_FONT_CANDIDATES = [
    "C:/Windows/Fonts/seguiemj.ttf",
    "/System/Library/Fonts/Apple Color Emoji.ttc",
]
_VARIATION = {"regular": b"Regular", "medium": b"Semibold Text", "semibold": b"Semibold Text",
              "bold": b"Bold Text", "light": b"Light Text"}
_STATIC_FALLBACK = {"semibold": "C:/Windows/Fonts/seguisb.ttf", "medium": "C:/Windows/Fonts/seguisb.ttf",
                    "bold": "C:/Windows/Fonts/segoeuib.ttf", "light": "C:/Windows/Fonts/segoeuil.ttf"}

EMOJI_RE = re.compile(
    "([\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\u2B55\uFE0F\u200D\U0001F3FB-\U0001F3FF]+)"
)

Weight = Literal["regular", "medium", "semibold", "bold", "light"]


def _first_existing(paths: Iterable[str]) -> str | None:
    return next((p for p in paths if Path(p).exists()), None)


def ui_font(size: float, weight: Weight = "regular") -> ImageFont.FreeTypeFont:
    """The UI face at `size` px and `weight`, with static/bitmap fallbacks."""
    path = _first_existing(UI_FONT_CANDIDATES)
    if path is None:
        return ImageFont.load_default()
    font = ImageFont.truetype(path, max(1, round(size)))
    try:
        font.set_variation_by_name(_VARIATION[weight])
    except (OSError, KeyError, ValueError):
        static = _STATIC_FALLBACK.get(weight)
        if static and Path(static).exists():
            font = ImageFont.truetype(static, max(1, round(size)))
    return font


def emoji_font(size: float) -> ImageFont.FreeTypeFont | None:
    path = _first_existing(EMOJI_FONT_CANDIDATES)
    return ImageFont.truetype(path, max(1, round(size))) if path else None


# ─── Text primitives (emoji-aware) ──────────────────────────────────────────


def _runs(text: str) -> list[tuple[str, bool]]:
    """Split text into (segment, is_emoji) runs."""
    return [(seg, bool(EMOJI_RE.fullmatch(seg))) for seg in EMOJI_RE.split(text) if seg]


def text_width(draw: ImageDraw.ImageDraw, text: str, font, efont) -> float:
    w = 0.0
    for seg, is_e in _runs(text):
        f = efont if (is_e and efont) else font
        w += draw.textlength(seg, font=f, embedded_color=is_e) if is_e else draw.textlength(seg, font=f)
    return w


def draw_text(draw: ImageDraw.ImageDraw, xy: tuple[float, float], text: str, font, efont,
              fill, anchor_baseline: bool = True) -> None:
    """Draw text (with colour emoji) left-aligned from xy; y is the baseline."""
    x, y = xy
    for seg, is_e in _runs(text):
        if is_e and efont:
            draw.text((x, y), seg, font=efont, embedded_color=True, anchor="ls")
            x += draw.textlength(seg, font=efont, embedded_color=True)
        else:
            draw.text((x, y), seg, font=font, fill=fill, anchor="ls")
            x += draw.textlength(seg, font=font)


def wrap(draw: ImageDraw.ImageDraw, text: str, font, efont, max_w: float) -> list[str]:
    """Greedy word wrap honouring explicit newlines."""
    out: list[str] = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}".strip()
            if line and text_width(draw, trial, font, efont) > max_w:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


def wrap_balanced(draw: ImageDraw.ImageDraw, text: str, font, efont, max_w: float) -> list[str]:
    """Wrap to the same line count as `wrap`, but at the narrowest width that keeps it, so
    lines come out even (native UIs balance short text; no orphaned last word)."""
    lines = wrap(draw, text, font, efont, max_w)
    if len(lines) < 2 or "\n" in text:
        return lines
    lo, hi = max_w * 0.4, max_w
    for _ in range(14):
        mid = (lo + hi) / 2
        if len(wrap(draw, text, font, efont, mid)) == len(lines):
            hi = mid
        else:
            lo = mid
    return wrap(draw, text, font, efont, hi)


def _shadow(img: Image.Image, box: tuple[float, float, float, float], radius: float,
            blur: float, alpha: int, offset: float) -> None:
    """Soft drop shadow under a rounded rectangle (in place)."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(
        (box[0], box[1] + offset, box[2], box[3] + offset), radius=radius, fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(blur)))


# ─── Components ─────────────────────────────────────────────────────────────


@dataclass
class QuestionBox:
    """Instagram question sticker. `bold` = the one word to set in bold (optional).

    With `answer=None` it shows the grey "Type something..." field (the brand asking).
    With `answer` it shows a shared response (the answer replaces the field text).
    """
    question: str
    bold: str | None = None
    answer: str | None = None
    placeholder: str = "Type something..."
    center_y: float = 0.45          # fraction of image height for the card centre
    avatar: Path | None = None      # brand profile picture; grey disc if None


def render_question_box(img: Image.Image, spec: QuestionBox) -> Image.Image:
    W, H = img.size
    s = W / REF_W
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    q_font, q_bold = ui_font(30 * s), ui_font(30 * s, "semibold")
    f_font = ui_font(31 * s)
    ef = emoji_font(30 * s)

    card_w = 524 * s
    pad = 40 * s
    lines = wrap_balanced(d, spec.question, q_font, ef, card_w - 2 * pad)
    line_h = 30 * s * 1.35
    field_h = 103 * s if spec.answer is None else max(103 * s, 44 * s * len(wrap(d, spec.answer, f_font, ef, 440 * s - 40 * s)) + 40 * s)
    card_h = 62 * s + line_h * len(lines) + 22 * s + field_h + 34 * s
    x0 = (W - card_w) / 2
    y0 = spec.center_y * H - card_h / 2
    radius = 34 * s

    _shadow(out, (x0, y0, x0 + card_w, y0 + card_h), radius, 18 * s, 50, 6 * s)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((x0, y0, x0 + card_w, y0 + card_h), radius=radius, fill="#FFFFFF")

    # avatar disc overlapping the top edge
    av = 80 * s
    ax, ay = W / 2 - av / 2, y0 - av / 2
    d.ellipse((ax - 4 * s, ay - 4 * s, ax + av + 4 * s, ay + av + 4 * s), fill="#FFFFFF")
    if spec.avatar and Path(spec.avatar).exists():
        pic = Image.open(spec.avatar).convert("RGBA").resize((round(av), round(av)))
        mask = Image.new("L", pic.size, 0)
        ImageDraw.Draw(mask).ellipse((0, 0, pic.size[0], pic.size[1]), fill=255)
        out.paste(pic, (round(ax), round(ay)), mask)
    else:
        d.ellipse((ax, ay, ax + av, ay + av), fill="#D9D9D9")

    # question lines, centred; optional single bold word
    y = y0 + 62 * s + 30 * s
    for line in lines:
        words = line.split(" ")
        widths = [text_width(d, w + " ", q_bold if spec.bold and w.strip("?.,!") == spec.bold else q_font, ef)
                  for w in words]
        x = W / 2 - sum(widths) / 2
        for w, ww in zip(words, widths):
            f = q_bold if spec.bold and w.strip("?.,!") == spec.bold else q_font
            draw_text(d, (x, y), w, f, ef, "#000000")
            x += ww
        y += line_h

    # answer field
    fw = 440 * s
    fx0, fy0 = W / 2 - fw / 2, y - 30 * s + 22 * s
    d.rounded_rectangle((fx0, fy0, fx0 + fw, fy0 + field_h), radius=16 * s, fill="#F0F0F0")
    if spec.answer is None:
        tw = text_width(d, spec.placeholder, f_font, ef)
        layer = Image.new("RGBA", out.size, (0, 0, 0, 0))
        draw_text(ImageDraw.Draw(layer), (W / 2 - tw / 2, fy0 + field_h / 2 + 11 * s), spec.placeholder,
                  f_font, ef, (0, 0, 0, 120))
        out.alpha_composite(layer)
    else:
        a_lines = wrap(d, spec.answer, f_font, ef, fw - 40 * s)
        ay0 = fy0 + (field_h - 44 * s * len(a_lines)) / 2 + 33 * s
        for i, line in enumerate(a_lines):
            tw = text_width(d, line, f_font, ef)
            draw_text(d, (W / 2 - tw / 2, ay0 + i * 44 * s), line, f_font, ef, "#000000")
    return out.convert("RGB")


@dataclass
class Message:
    text: str
    sender: Literal["them", "me"] = "them"


@dataclass
class IMessageThread:
    """iMessage-style thread. Only use with a real conversation (shared with permission)."""
    messages: Sequence[Message]
    timestamp: str | None = "Today 9:41 AM"
    top: float = 0.22                # fraction of image height where the thread starts
    panel: bool = True               # white screenshot panel behind the bubbles


def render_imessage_thread(img: Image.Image, spec: IMessageThread) -> Image.Image:
    W, H = img.size
    s = W / REF_W
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    font, ef = ui_font(33 * s), emoji_font(33 * s)
    ts_font = ui_font(24 * s)
    line_h = 33 * s * 1.28
    max_text_w = 546 * s - 2 * 30 * s
    margin = 64 * s

    # measure
    blocks = []
    for m in spec.messages:
        lines = wrap_balanced(d, m.text, font, ef, max_text_w)
        tw = max(text_width(d, ln, font, ef) for ln in lines)
        blocks.append((m, lines, tw + 2 * 30 * s, len(lines) * line_h + 2 * 20 * s))
    ts_h = 60 * s if spec.timestamp else 0
    gaps = [(8 if i and blocks[i - 1][0].sender == b[0].sender else 22) * s for i, b in enumerate(blocks)]
    total_h = ts_h + sum(b[3] for b in blocks) + sum(gaps)

    y = spec.top * H
    if spec.panel:
        px0, px1 = margin - 28 * s, W - margin + 28 * s
        _shadow(out, (px0, y - 40 * s, px1, y + total_h + 40 * s), 44 * s, 22 * s, 55, 8 * s)
        d = ImageDraw.Draw(out)
        d.rounded_rectangle((px0, y - 40 * s, px1, y + total_h + 40 * s), radius=44 * s, fill="#FFFFFF")
    if spec.timestamp:
        tw = text_width(d, spec.timestamp, ts_font, None)
        draw_text(d, (W / 2 - tw / 2, y + 30 * s), spec.timestamp, ts_font, None, "#8E8E93")
        y += ts_h
    for (m, lines, bw, bh), gap in zip(blocks, gaps):
        y += gap
        me = m.sender == "me"
        x0 = W - margin - bw if me else margin
        fill, color = ("#0A84FF", "#FFFFFF") if me else ("#E9E9EB", "#1C1C1E")
        d.rounded_rectangle((x0, y, x0 + bw, y + bh), radius=min(38 * s, bh / 2), fill=fill)
        # tail on the bottom outer corner
        if me:
            d.polygon([(x0 + bw - 22 * s, y + bh - 30 * s), (x0 + bw + 12 * s, y + bh), (x0 + bw - 34 * s, y + bh)], fill=fill)
        else:
            d.polygon([(x0 + 22 * s, y + bh - 30 * s), (x0 - 12 * s, y + bh), (x0 + 34 * s, y + bh)], fill=fill)
        ty = y + 20 * s + 33 * s * 0.98
        for ln in lines:
            draw_text(d, (x0 + 30 * s, ty), ln, font, ef, color)
            ty += line_h
        y += bh
    return out.convert("RGB")


@dataclass
class NotesCard:
    """iOS Notes card: back chevron + 'Notes', a title, then lines or a checklist."""
    title: str
    lines: Sequence[str]
    checklist: bool = False
    checked: Sequence[int] = ()       # indexes of checked items
    theme: Literal["light", "dark"] = "light"
    top: float = 0.20


def render_notes_card(img: Image.Image, spec: NotesCard) -> Image.Image:
    W, H = img.size
    s = W / REF_W
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    dark = spec.theme == "dark"
    bg, ink, accent, ring = (("#1C1C1E", "#F5F5F0", "#E2B13C", "#8E8E93") if dark
                             else ("#FFFFFF", "#1C1C1E", "#E2A226", "#C7C7CC"))
    hdr, title_f, body_f = ui_font(37 * s), ui_font(44 * s, "bold"), ui_font(33 * s)
    ef = emoji_font(33 * s)
    x0, x1 = 90 * s, W - 90 * s
    pad = 56 * s
    text_x = x0 + pad + (52 * s if spec.checklist else 0)
    body_lines = [wrap(d, ln, body_f, ef, x1 - pad - text_x) for ln in spec.lines]
    row_h = 33 * s * 1.75
    height = pad + 50 * s + 40 * s + 60 * s + sum(len(b) for b in body_lines) * row_h + pad
    y0 = spec.top * H

    _shadow(out, (x0, y0, x1, y0 + height), 40 * s, 22 * s, 55, 8 * s)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((x0, y0, x1, y0 + height), radius=40 * s, fill=bg)
    # header: chevron + Notes
    cy = y0 + pad + 22 * s
    d.line([(x0 + pad + 14 * s, cy - 14 * s), (x0 + pad, cy), (x0 + pad + 14 * s, cy + 14 * s)],
           fill=accent, width=max(2, round(4 * s)), joint="curve")
    draw_text(d, (x0 + pad + 30 * s, cy + 13 * s), "Notes", hdr, None, accent)
    # title
    ty = cy + 40 * s + 62 * s
    draw_text(d, (x0 + pad, ty), spec.title, title_f, emoji_font(44 * s), ink)
    y = ty + 26 * s
    for i, lines in enumerate(body_lines):
        for j, ln in enumerate(lines):
            y += row_h
            if spec.checklist and j == 0:
                r = 17 * s
                cx, ccy = x0 + pad + r, y - 11 * s
                if i in spec.checked:
                    d.ellipse((cx - r, ccy - r, cx + r, ccy + r), fill=accent)
                    d.line([(cx - 8 * s, ccy), (cx - 2 * s, ccy + 6 * s), (cx + 9 * s, ccy - 7 * s)],
                           fill=bg, width=max(2, round(3.5 * s)), joint="curve")
                else:
                    d.ellipse((cx - r, ccy - r, cx + r, ccy + r), outline=ring, width=max(2, round(2.5 * s)))
            draw_text(d, (text_x, y), ln, body_f, ef, ink)
    return out.convert("RGB")


@dataclass
class ReminderPopup:
    """iOS alert-style reminder: bold title, body, divider, one blue button."""
    body: str
    title: str = "Reminder"
    button: str = "OK"
    center_y: float = 0.42


def render_reminder_popup(img: Image.Image, spec: ReminderPopup) -> Image.Image:
    W, H = img.size
    s = W / REF_W
    out = img.convert("RGBA")
    d = ImageDraw.Draw(out)
    t_font, b_font, btn_font = ui_font(34 * s, "semibold"), ui_font(28 * s), ui_font(34 * s)
    ef = emoji_font(28 * s)
    card_w = 540 * s
    pad = 36 * s
    lines = wrap(d, spec.body, b_font, ef, card_w - 2 * pad)
    line_h = 28 * s * 1.35
    btn_h = 92 * s
    card_h = pad + 44 * s + 14 * s + len(lines) * line_h + pad + btn_h
    x0, y0 = (W - card_w) / 2, spec.center_y * H - card_h / 2
    radius = 30 * s
    _shadow(out, (x0, y0, x0 + card_w, y0 + card_h), radius, 26 * s, 70, 8 * s)
    d = ImageDraw.Draw(out)
    d.rounded_rectangle((x0, y0, x0 + card_w, y0 + card_h), radius=radius, fill="#F2F2F2")
    tw = text_width(d, spec.title, t_font, None)
    y = y0 + pad + 34 * s
    draw_text(d, (W / 2 - tw / 2, y), spec.title, t_font, None, "#000000")
    y += 14 * s
    for ln in lines:
        y += line_h
        lw = text_width(d, ln, b_font, ef)
        draw_text(d, (W / 2 - lw / 2, y), ln, b_font, ef, "#000000")
    div_y = y0 + card_h - btn_h
    d.line([(x0, div_y), (x0 + card_w, div_y)], fill="#C6C6C8", width=max(1, round(1.5 * s)))
    bw = text_width(d, spec.button, btn_font, None)
    draw_text(d, (W / 2 - bw / 2, div_y + btn_h / 2 + 12 * s), spec.button, btn_font, None, "#0A84FF")
    return out.convert("RGB")


# ─── Convenience ────────────────────────────────────────────────────────────

RENDERERS = {
    QuestionBox: render_question_box,
    IMessageThread: render_imessage_thread,
    NotesCard: render_notes_card,
    ReminderPopup: render_reminder_popup,
}

SIZES = {"4x5": (1080, 1350), "9x16": (1080, 1920), "1x1": (1080, 1080)}
COMPONENTS = ("question_box", "imessage", "notes", "reminder")


def component_from_spec(spec) -> QuestionBox | IMessageThread | NotesCard | ReminderPopup:
    """Build a component from a `models.brief.NativeUiSpec` (or an equivalent dict)."""
    get = spec.get if isinstance(spec, dict) else (lambda k, d=None: getattr(spec, k, d))
    kind, placement = get("component"), get("placement")
    if kind == "question_box":
        avatar = get("avatar")
        c = QuestionBox(question=get("question"), bold=get("bold"), answer=get("answer"),
                        avatar=Path(avatar) if avatar else None)
        if placement is not None:
            c.center_y = placement
        return c
    if kind == "imessage":
        msgs = [Message(m["text"], m.get("sender", "them")) if isinstance(m, dict)
                else Message(m.text, m.sender) for m in get("messages") or []]
        c = IMessageThread(messages=msgs, timestamp=get("timestamp", "Today 9:41 AM"))
        if placement is not None:
            c.top = placement
        return c
    if kind == "notes":
        c = NotesCard(title=get("title"), lines=list(get("lines") or []), checklist=bool(get("checklist")),
                      checked=list(get("checked") or []), theme=get("theme") or "light")
        if placement is not None:
            c.top = placement
        return c
    if kind == "reminder":
        c = ReminderPopup(body=get("body"), title=get("reminder_title") or "Reminder",
                          button=get("button") or "OK")
        if placement is not None:
            c.center_y = placement
        return c
    raise ValueError(f"unknown native_ui component: {kind!r} (expected one of {COMPONENTS})")


def render_native(base: Path | Image.Image, component, out_path: Path | None = None,
                  size: tuple[int, int] | None = None) -> Image.Image:
    """Composite one native component onto `base` (path or image), optionally cover-cropped
    to `size` first (e.g. (1080, 1350) feed, (1080, 1920) story). Saves PNG if `out_path`."""
    img = Image.open(base) if isinstance(base, (str, Path)) else base
    img = img.convert("RGB")
    if size:
        img = _cover(img, size)
    result = RENDERERS[type(component)](img, component)
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        result.save(out_path)
    return result


def _cover(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    tw, th = size
    scale = max(tw / img.width, th / img.height)
    rs = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    left, top = (rs.width - tw) // 2, (rs.height - th) // 2
    return rs.crop((left, top, left + tw, top + th))
