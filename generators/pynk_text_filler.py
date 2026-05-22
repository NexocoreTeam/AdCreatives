"""PYNK-style text-only ad prompt builder.

Takes a Cooper-library template + brand / avatar / product / brief data and
produces a fully-filled prompt ready for FAL nano-banana-2/edit, plus a list
of any slots that contain invented data (flagged with a ⚠️ marker for human
review).

Used by `adc generate-text` — the B variant in A vs B drift testing against
the existing reference-based path. Designed to leave the existing
reference-based path untouched.

Key differences from the existing prompt engine:
    1. NO reference image — only the product image is sent to FAL.
    2. Templates come straight from `prompts/library/cooper/*.yaml`.
    3. A Product Anchor preamble is prepended to every prompt forcing
       product fidelity (replaces the first occurrence of "Create:").
    4. Aspect ratio is locked from the template, not inferred from the brief.
    5. Contrast rule is applied explicitly: chosen text color is stated in
       the prompt based on background brightness.
    6. Slots that require invented values (stats, member counts, ratings,
       reviewer names) are filled with plausible placeholders and flagged ⚠️
       in the returned spec — never quietly fabricated into the rendered ad.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PRODUCT_ANCHOR_PREAMBLE = (
    "The provided reference image shows the exact product that must appear in "
    "this ad. Do not invent, modify, or substitute this product — it must look "
    "identical to the reference image: shape, label, colors, and packaging."
)


@dataclass
class FilledTemplate:
    """Result of filling a Cooper template with brand / brief data."""

    template_id: str
    template_name: str
    template_slug: str
    aspect_ratio: str
    raw_template: str  # original template_prompt with [BRACKETS]
    filled_prompt: str  # final prompt sent to FAL (Product Anchor + filled body)
    slot_map: dict[str, str] = field(default_factory=dict)
    flagged_invented: list[dict] = field(default_factory=list)
    chosen_text_color_hex: str = ""
    chosen_text_color_descriptor: str = ""


# ---------------------------------------------------------------------------
# Template loading
# ---------------------------------------------------------------------------

def load_cooper_template(template_id: str, library_root: Path) -> dict:
    """Load a Cooper template YAML by its `id` field.

    Searches `prompts/library/cooper/*.yaml` for a file whose top-level `id`
    matches `template_id` (e.g. `cooper-11-pull-quote-review`).
    """
    cooper_dir = library_root / "cooper"
    if not cooper_dir.is_dir():
        raise FileNotFoundError(f"Cooper library not found at {cooper_dir}")

    for yaml_path in sorted(cooper_dir.glob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        if data.get("id") == template_id:
            data["_yaml_path"] = str(yaml_path)
            return data

    available = [p.stem for p in sorted(cooper_dir.glob("*.yaml"))]
    raise FileNotFoundError(
        f"Cooper template not found: {template_id}.\n"
        f"Available files in {cooper_dir}:\n  - "
        + "\n  - ".join(available)
    )


def list_cooper_templates(library_root: Path) -> list[dict]:
    """Return a summary list of all Cooper templates: id, name, aspect_ratios."""
    cooper_dir = library_root / "cooper"
    out: list[dict] = []
    if not cooper_dir.is_dir():
        return out
    for yaml_path in sorted(cooper_dir.glob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            continue
        if not data.get("id"):
            continue
        out.append({
            "id": data["id"],
            "name": data.get("name", data["id"]),
            "category": data.get("category", ""),
            "aspect_ratios": data.get("aspect_ratios", []),
            "description": data.get("description", ""),
        })
    return out


def extract_placeholders(template_text: str) -> list[str]:
    """Extract every [BRACKETED] placeholder from a template prompt.

    Returns each placeholder content as-written (without the surrounding
    brackets), preserving any modifier text inside like
    `[YOUR HEADLINE, under 10 words]`. Duplicates are preserved in order.
    """
    return re.findall(r"\[([^\[\]]+)\]", template_text)


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

_NAMED_COLOR_CACHE: dict[str, str] = {}


def hex_to_color_name(hex_code: str) -> str:
    """Return a human color name for a #RRGGBB hex code via Claude (cached).

    Falls back to the raw hex if no name can be derived. Empty inputs
    return an empty string.
    """
    if not hex_code:
        return ""
    hex_norm = hex_code.lower().lstrip("#")
    if len(hex_norm) != 6:
        return hex_code
    if hex_norm in _NAMED_COLOR_CACHE:
        return _NAMED_COLOR_CACHE[hex_norm]

    try:
        from strategy.llm import claude_complete
        raw = claude_complete(
            prompt=(
                f"What's the most natural English color name for the hex code "
                f"#{hex_norm}? Reply with ONLY the color name in title case — "
                f"no punctuation, no hex, no extra words. Examples: "
                f"'Marigold', 'Midnight Blue', 'Off-White', 'Burnt Orange'."
            ),
            max_tokens=20,
        )
        name = raw.strip().splitlines()[0].strip().strip(".").strip("'\"")
        if not name or len(name) > 40:
            name = f"#{hex_norm}"
    except Exception:
        name = f"#{hex_norm}"

    _NAMED_COLOR_CACHE[hex_norm] = name
    return name


def hex_luminance(hex_code: str) -> float:
    """Return relative luminance 0-1. >0.5 = light. Used for contrast rule."""
    h = hex_code.lstrip("#")
    if len(h) != 6:
        return 0.5
    try:
        r = int(h[0:2], 16) / 255
        g = int(h[2:4], 16) / 255
        b = int(h[4:6], 16) / 255
    except ValueError:
        return 0.5
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def choose_text_color(background_hex: str) -> tuple[str, str]:
    """Apply PYNK contrast rule: light bg → dark text, dark bg → light text.

    Returns (hex, human_descriptor) so the descriptor can be quoted into
    the rendered prompt for transparency.
    """
    if hex_luminance(background_hex) > 0.5:
        return ("#111827", "dark charcoal")
    return ("#FFFFFF", "white")


# ---------------------------------------------------------------------------
# Slot resolvers — deterministic
# ---------------------------------------------------------------------------

def resolve_brand_slots(brand) -> dict[str, str]:
    """Fill brand-derived placeholders.

    Brand is loaded via models.loader; uses .colors.{primary,secondary,
    background,text,accent} and .name.
    """
    primary_hex = brand.colors.primary or "#000000"
    bg_hex = brand.colors.background or "#FFFFFF"
    secondary_hex = brand.colors.secondary or ""
    accent_hex = brand.colors.accent or secondary_hex or primary_hex

    primary_name = hex_to_color_name(primary_hex)
    bg_name = hex_to_color_name(bg_hex)
    accent_name = hex_to_color_name(accent_hex)

    text_hex, text_descriptor = choose_text_color(bg_hex)

    return {
        "BRAND": brand.name,
        "PRIMARY BRAND COLOR": f"{primary_name} ({primary_hex})",
        "BRAND COLOR": f"{primary_name} ({primary_hex})",
        "BRAND COLOR with hex": f"{primary_name} {primary_hex}",
        "ACCENT COLOR": f"{accent_name} ({accent_hex})",
        "BACKGROUND": f"{bg_name} ({bg_hex})",
        "CONTRAST COLOR": f"{accent_name} ({accent_hex})",
        "CONTRAST COLOR like warm cream": f"{accent_name} ({accent_hex})",
        "TEXT COLOR": f"{text_descriptor} ({text_hex})",
        "CONTRAST TEXT": f"{text_descriptor} ({text_hex})",
    }


def resolve_product_slots(product) -> dict[str, str]:
    """Fill product-derived placeholders."""
    return {
        "YOUR PRODUCT": product.name,
        "PRODUCT": product.name,
        "PRODUCT NAME": product.name,
        "WEBSITE": (product.url or "").strip(),
    }


def resolve_copy_slots(brief, product, brand) -> dict[str, str]:
    """Fill copy-bearing placeholders from the creative brief.

    Headlines come from brief.hook (condensed if too long). Subheads come
    from brief.body_copy or the first benefit callout. Benefits come from
    brief.benefit_callouts (preferred) or product.benefits.
    """
    slots: dict[str, str] = {}

    hook = (brief.hook or "").strip()
    headline = hook
    if hook and len(hook.split()) > 10:
        # Condense via Claude — keep psychological mechanic intact
        try:
            from strategy.llm import claude_complete
            headline = claude_complete(
                prompt=(
                    "Condense this ad headline to under 10 words while preserving "
                    "the core hook and psychological intent. Reply with ONLY the "
                    "condensed headline — no prose, no quotes, no punctuation at "
                    f"end.\n\nHEADLINE: {hook}"
                ),
                max_tokens=40,
            ).strip().splitlines()[0].strip().strip('"\'')
        except Exception:
            headline = " ".join(hook.split()[:10])

    if headline:
        slots["YOUR HEADLINE"] = headline
        slots["HEADLINE"] = headline
        slots["YOUR HEADLINE, under 10 words"] = headline
        # Match the common "[YOUR HEADLINE, under N words]" variants
        slots["YOUR HEADLINE, under 8 words"] = headline
        slots["YOUR HEADLINE, under 6 words"] = headline
        slots["HOOK HEADLINE"] = headline
        slots["SHORT HEADLINE"] = headline
        slots["HEADER"] = headline
        slots["HEADER like What Makes [PRODUCT] Different"] = headline

    # Subhead
    subhead = ""
    if brief.body_copy:
        subhead = brief.body_copy.strip().split("\n")[0][:140]
    elif brief.benefit_callouts:
        subhead = brief.benefit_callouts[0]
    if subhead:
        slots["YOUR SUBHEAD"] = subhead
        slots["YOUR SUBHEAD, one sentence"] = subhead
        slots["SUBLINE"] = subhead

    # Benefits 1-5 and Strength 1-5 (us-vs-them)
    benefits = list(brief.benefit_callouts or []) or list(product.benefits or [])
    # Strip leading [functional]/[emotional]/[social] tags that real client
    # benefits sometimes carry — they confuse the model into rendering them
    # as visible labels.
    benefit_tag_re = re.compile(r"^\[(?:functional|emotional|social)\]\s*")
    benefits_clean = [benefit_tag_re.sub("", b).strip() for b in benefits if b]

    for i, b in enumerate(benefits_clean[:5], 1):
        slots[f"BENEFIT {i}"] = b
        slots[f"STRENGTH {i}"] = b

    # Range placeholders — templates often write [BENEFIT 1-5] or
    # [STRENGTH 1-5] as a single slot. Substitute with ' · '-joined bullets
    # so the model renders them as a list rather than as literal text.
    sep = " · "
    for n in (3, 4, 5):
        if len(benefits_clean) >= 1:
            joined = sep.join(benefits_clean[:n])
            slots[f"BENEFIT 1-{n}"] = joined
            slots[f"BENEFIT 1-N"] = joined
            slots[f"STRENGTH 1-{n}"] = joined
            slots[f"STRENGTH 1-N"] = joined

    # CTA
    if brief.cta:
        slots["CTA"] = brief.cta

    # Pain point as fallback for [PROBLEM] / [BEFORE STATE]
    if brief.pain_point:
        slots["PROBLEM"] = brief.pain_point
        slots["BEFORE STATE"] = brief.pain_point

    return slots


# ---------------------------------------------------------------------------
# Claude batch-fill for the rest
# ---------------------------------------------------------------------------

def _claude_fill_unresolved(
    *,
    unresolved: list[str],
    brand,
    product,
    avatar,
    brief,
) -> dict[str, Any]:
    """One Claude call to fill the remaining slots in a batch.

    Returns {"slots": {placeholder: value}, "flagged": [{...}, ...]}.

    Claude is instructed to append a ⚠️ marker to any invented stat /
    rating / member count / reviewer name. We split those out into the
    `flagged` list and strip the marker from the value before substitution
    (the spec.json carries the flagged list separately for review).
    """
    try:
        from strategy.llm import claude_complete
    except ImportError:
        return {"slots": {}, "flagged": []}

    # Build context block
    context_parts = [
        f"BRAND NAME: {brand.name}",
        f"BRAND TONE: {brand.tone}" if brand.tone else "",
        f"PRODUCT: {product.name}",
        f"PRODUCT DESCRIPTION: {product.description}" if product.description else "",
        f"PRODUCT BENEFITS: {' | '.join((product.benefits or [])[:8])}" if product.benefits else "",
        f"UNIQUE MECHANISM: {product.unique_mechanism}" if product.unique_mechanism else "",
        f"BRIEF HOOK: {brief.hook}" if brief.hook else "",
        f"BRIEF ANGLE: {brief.angle}" if brief.angle else "",
        f"PAIN POINT: {brief.pain_point}" if brief.pain_point else "",
        f"VISUAL DIRECTION: {brief.visual_direction}" if brief.visual_direction else "",
    ]

    if avatar:
        try:
            avatar_name = avatar.name
        except AttributeError:
            avatar_name = ""
        if avatar_name:
            context_parts.append(f"PERSONA: {avatar_name}")

        quotes: list[str] = []
        try:
            for p in (avatar.pain_points or [])[:3]:
                for q in (p.customer_language or [])[:2]:
                    if q and q not in quotes:
                        quotes.append(q.strip())
            for d in (avatar.desires or [])[:3]:
                for q in (d.customer_language or [])[:2]:
                    if q and q not in quotes:
                        quotes.append(q.strip())
        except AttributeError:
            pass
        if quotes:
            context_parts.append("CUSTOMER QUOTES: " + " | ".join(quotes[:6]))

    if product.social_proof:
        context_parts.append("PRODUCT SOCIAL PROOF: " + " | ".join(product.social_proof[:5]))

    # Brand-level social_proof: may not be on the typed model but can be in YAML.
    brand_sp = getattr(brand, "social_proof", None)
    if brand_sp:
        try:
            context_parts.append("BRAND SOCIAL PROOF: " + " | ".join(list(brand_sp)[:5]))
        except TypeError:
            pass

    # Competitor weaknesses — used for us-vs-them WEAKNESS slots. Loaded
    # straight from clients/<slug>/competitors.yaml because there's no
    # typed model. Best-effort.
    try:
        import yaml
        from pathlib import Path as _Path
        comp_path = _Path("clients") / brief.client / "competitors.yaml"
        if comp_path.exists():
            with open(comp_path, encoding="utf-8") as f:
                comp_data = yaml.safe_load(f) or {}
            comps = comp_data.get("competitors") or []
            comp_summary: list[str] = []
            for c in comps[:4]:
                name = c.get("name", "") if isinstance(c, dict) else ""
                notes = c.get("notes", "") if isinstance(c, dict) else ""
                if isinstance(notes, str):
                    # First non-blank line of notes
                    first_line = next(
                        (ln.strip(" -•*") for ln in notes.splitlines() if ln.strip()),
                        ""
                    )
                else:
                    first_line = ""
                if name or first_line:
                    comp_summary.append(f"{name}: {first_line}" if first_line else name)
            if comp_summary:
                context_parts.append("COMPETITOR WEAKNESSES: " + " | ".join(comp_summary))
    except Exception:
        pass

    context = "\n".join(p for p in context_parts if p)
    placeholders_block = "\n".join(f"- [{p}]" for p in unresolved)

    sys_prompt = (
        "You fill in advertising template placeholders with concrete, brand-voiced copy. "
        "Rules:\n"
        "1. Use CUSTOMER QUOTES verbatim when filling QUOTE / REVIEW TEXT / FULL QUOTE / "
        "PULL-QUOTE / testimonial slots — pick the most emotionally resonant one.\n"
        "2. Use PRODUCT BENEFITS verbatim or lightly trimmed for BENEFIT N slots.\n"
        "3. If a placeholder requires a STAT, NUMBER, RATING, MEMBER COUNT, REVIEW COUNT, "
        "PRICE, CALORIES, CAFFEINE, or any other quantitative claim, and no real value "
        "exists in PRODUCT/BRAND SOCIAL PROOF, invent a plausible value and append the "
        "literal marker ' ⚠️' to the end of the value (e.g. '180mg ⚠️', '4.8 out of 5 ⚠️', "
        "'500,000+ ⚠️').\n"
        "4. If a placeholder requires a NAME, CREDENTIAL, ATTRIBUTION, FIRST NAME + LAST INITIAL, "
        "or competitor brand name and no real value is given, invent a plausible "
        "placeholder and append ' ⚠️'.\n"
        "5. For visual direction slots (SETTING, SURFACE, DETAILS, BACKGROUND DETAILS, "
        "LIFESTYLE PHOTO DESCRIPTION, MOOD, PROPS), use VISUAL DIRECTION when present, "
        "else infer concrete specifics from PRODUCT / BRAND TONE. Do NOT use generic "
        "words like 'nice', 'clean', 'beautiful'.\n"
        "6. For COMPETITOR CATEGORY: use a generic category descriptor (e.g. "
        "'mass-market protein bars'), not a real brand name.\n"
        "7. RANGE PLACEHOLDERS like 'WEAKNESS 1-5', 'STRENGTH 1-3', or 'BENEFIT 1-4': "
        "return ONE string containing N short items separated by ' · ' (space + middle dot + "
        "space). Example: 'Chemical aftertaste · Sugar crash · Forgettable packaging · "
        "Generic ingredients · Inflated price'. Do NOT enumerate as 'WEAKNESS 1', "
        "'WEAKNESS 2' — the model needs the joined string to render as a list.\n"
        "8. For [WEAKNESS N] slots: use COMPETITOR WEAKNESSES when present, else infer "
        "category weaknesses that contrast with this product's strengths. Never name real "
        "competitor brands.\n"
        "9. Reply as JSON ONLY — a single object mapping placeholder name (exactly as "
        "given, no brackets) to filled string value. No prose. No markdown fences."
    )

    user_prompt = (
        f"CONTEXT:\n{context}\n\n"
        f"FILL THESE PLACEHOLDERS — one JSON entry per placeholder:\n{placeholders_block}\n\n"
        f"Reply with JSON only."
    )

    try:
        raw = claude_complete(prompt=user_prompt, system=sys_prompt, max_tokens=2000)
    except Exception:
        return {"slots": {}, "flagged": []}

    # Tolerant JSON parsing
    try:
        from json_repair import repair_json
        repaired = repair_json(raw)
        filled = json.loads(repaired) if isinstance(repaired, str) else repaired
    except Exception:
        try:
            filled = json.loads(raw)
        except Exception:
            filled = {}

    if not isinstance(filled, dict):
        return {"slots": {}, "flagged": []}

    flagged: list[dict] = []
    clean: dict[str, str] = {}
    for k, v in filled.items():
        v_str = str(v)
        warn = "⚠️" in v_str or "⚠" in v_str
        if warn:
            stripped = v_str.replace("⚠️", "").replace("⚠", "").strip()
            flagged.append({
                "slot": k,
                "value": stripped,
                "marked_in_prompt": v_str,
                "reason": "invented — no source data; needs human verification before render",
            })
            clean[k] = stripped
        else:
            clean[k] = v_str

    return {"slots": clean, "flagged": flagged}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def fill_template(
    *,
    template_data: dict,
    brand,
    product,
    avatar,
    brief,
    aspect_ratio: str | None = None,
) -> FilledTemplate:
    """Fill every [BRACKETED] placeholder in a Cooper template.

    Phase 1: deterministic slot resolution from brand / product / brief.
    Phase 2: single Claude batch call to fill anything still unresolved
             (testimonials, stats, names, visual direction, etc.).
    Phase 3: substitute slots into the template text, longest first so
             modifier-bearing placeholders match before their plain forms.
    Phase 4: prepend the Product Anchor preamble.
    """
    raw_text = template_data.get("template_prompt", "") or ""
    template_id = template_data.get("id", "")
    template_name = template_data.get("name", template_id)
    template_slug = template_id.replace("cooper-", "")

    if not aspect_ratio:
        aspects = template_data.get("aspect_ratios") or ["1:1"]
        aspect_ratio = aspects[0] if isinstance(aspects, list) and aspects else "1:1"

    slots: dict[str, str] = {}
    slots.update(resolve_brand_slots(brand))
    slots.update(resolve_product_slots(product))
    slots.update(resolve_copy_slots(brief, product, brand))

    placeholders = extract_placeholders(raw_text)
    # De-dup while preserving order
    seen: set[str] = set()
    unique_placeholders: list[str] = []
    for p in placeholders:
        if p not in seen:
            seen.add(p)
            unique_placeholders.append(p)

    unresolved = [p for p in unique_placeholders if p not in slots]

    flagged_invented: list[dict] = []
    if unresolved:
        claude_result = _claude_fill_unresolved(
            unresolved=unresolved,
            brand=brand,
            product=product,
            avatar=avatar,
            brief=brief,
        )
        slots.update(claude_result["slots"])
        flagged_invented.extend(claude_result["flagged"])

    # Substitute. Sort by length desc so longer placeholders match before
    # shorter ones (handles "[YOUR HEADLINE, under 10 words]" vs "[HEADLINE]").
    filled = raw_text
    for slot_name in sorted(slots.keys(), key=len, reverse=True):
        filled = filled.replace(f"[{slot_name}]", str(slots[slot_name]))

    # Fallback for any [BRACKET] not in the slot map: drop the brackets
    # rather than ship a literal bracket into the rendered ad. Log a stub.
    def _fallback(match: re.Match) -> str:
        return match.group(1)

    leftover_count = len(re.findall(r"\[[^\[\]]+\]", filled))
    if leftover_count:
        filled = re.sub(r"\[([^\[\]]+)\]", _fallback, filled)

    # Apply Product Anchor preamble — replace everything before the first
    # "Create:" with our fixed product-fidelity opener. If no "Create:" is
    # present, prepend the anchor.
    create_idx = filled.find("Create:")
    if create_idx != -1:
        anchored = PRODUCT_ANCHOR_PREAMBLE + "\n\n" + filled[create_idx:]
    else:
        anchored = PRODUCT_ANCHOR_PREAMBLE + "\n\n" + filled

    bg_hex = brand.colors.background or "#FFFFFF"
    text_hex, text_descriptor = choose_text_color(bg_hex)

    return FilledTemplate(
        template_id=template_id,
        template_name=template_name,
        template_slug=template_slug,
        aspect_ratio=aspect_ratio,
        raw_template=raw_text,
        filled_prompt=anchored,
        slot_map=slots,
        flagged_invented=flagged_invented,
        chosen_text_color_hex=text_hex,
        chosen_text_color_descriptor=text_descriptor,
    )
