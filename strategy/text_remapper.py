"""Fill a template's text_schema with brief-derived, ICP-language copy.

The template_extractor decomposes a reference ad into:
  - template_prompt: layout description with [SLOT_ID] placeholders
  - text_schema: list of TextSlot entries describing each slot's rhetorical
    job (intent), structure (pattern), word ceiling, and any parallel-to
    pairing for symmetric layouts.

This module supplies the FILL step: given a brief + the schema, generate one
ICP-language string per slot — written from the product's actual value props
and the avatar's actual pain language, never from the reference's verbatim
text. The reference's words are not part of this function's input by design;
the schema is the only artifact carried forward from the reference.

Output: dict[slot_id, str] mapping every slot in the schema to its fill.
Downstream, generators.prompt_engine substitutes [SLOT_ID] markers in the
template_prompt with these fills and also passes the map as a canonical
SLOT FILLS block to the NB2 prompt writer.

Single Claude call per brief. Same cost order of magnitude as the legacy
3-slot condenser it replaces on the template-driven path.
"""

from __future__ import annotations

import json
import re

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.library import TextSlot
from models.product import Product
from strategy.llm import claude_complete


TEXT_REMAPPER_SYSTEM = """You are an ad copy editor filling a TEXT SCHEMA for a
single static ad. The schema is a list of labeled slots, each with a clear
rhetorical JOB (intent), a structural PATTERN, and a MAX_WORDS ceiling.

Your output is ONE filled phrase per slot, written in the buyer's language
from the brief's product / persona context.

CORE RULES — non-negotiable:

1. NEVER LOOK UP REFERENCE TEXT. You are not given the words from any
   reference ad on purpose. Write fresh copy from the brief and product
   context alone. If a slot's `intent` describes a generic role like
   "competitor column label", do not default to specific words like
   "Others" or "Them" unless the intent itself requires it — let the
   brief's angle inform the framing (e.g. "Live-bacteria pills",
   "The old way", "Generic gut blends").

2. NEVER NAME COMPETITORS. Use category language only: "the probiotics
   you've tried", "the live-bacteria approach", "generic gut blends".
   Forbidden: Seed, Ritual, Pendulum, AG1, Hims, PetLab, or any other
   brand name.

3. HARD WORD CEILING per slot. Each slot has a `max_words` value. Your
   fill must be at or below that count. Count words by whitespace.
   IMPORTANT: write a COMPLETE phrase, not a fragment that ends
   mid-thought. If your idea won't fit in max_words, REPHRASE it more
   tightly — never just chop off trailing words. "Digestive comfort,
   daily" is fine; "Digestive comfort, day" (truncated "daily") is
   broken and unacceptable. "Compounds that work" is fine; "Compounds
   that actually" (truncated "work") is broken and unacceptable.

4. NO EM DASHES OR EN DASHES — EVER, ANYWHERE IN A FILL. The characters
   `—` (em dash, U+2014) and `–` (en dash, U+2013) are forbidden in
   every slot value. They are a known AI-content tell and the user has
   banned them in rendered ad text. Use commas, periods, ellipses, or
   line breaks instead. If you feel the urge to write "Compounds — not
   bacteria", rewrite as "Compounds, not bacteria" or "Compounds. Not
   bacteria.". This rule is absolute.

5. PARALLEL SLOTS MUST STAY PARALLEL. If a slot has `parallel_to: x`,
   its fill must match the partner slot's sentence shape and word count
   (within ±2), with opposite valence. Example:
     us_label: "secondkind" (1 word, brand-positive)
     them_label: "generic pills" (2 words, category-negative)
   Both are short noun phrases — symmetric structure, opposite valence.

6. ICP LANGUAGE ONLY. Pull phrasing from the avatar's actual pain quotes,
   the brand's voice, the product's benefits. Avoid strategist jargon
   ("scientifically-engineered postbiotic synergy"), buzzword strings
   ("clinically-proven", "industry-leading"), and meaningless
   modifiers. A real reader who has never heard of the product must
   immediately understand what each slot is saying.

7. HONOR BRAND VOICE AND PROHIBITED TERMS. The brand context lists tone
   and any forbidden words — these are hard constraints across every
   slot.

8. HONOR EACH SLOT'S `tone` OVERRIDE WHEN PRESENT. If a slot specifies
   `tone: snarky`, that slot is snarky even if the brand's default tone
   is warm.

9. RESPECT THE `pattern` for each slot. If a slot's pattern says
   "Two-line headline with one stat embedded", structure the fill that
   way. If it says "Negative bullet starting with a verb", start with
   a verb.

10. EVERY SLOT MUST BE FILLED. Even slots that feel minor (footnote,
    wordmark) get a fill. For brand wordmark slots, use the brand's
    actual name (or lowercase variant). For badge/footnote slots
    without strong content cues, leave them sharply minimal — never
    render strategist filler.

11. OUTPUT VALID JSON ONLY. Schema:
    {"<slot_id>": "<fill text>", ...}
    No prose, no markdown fences, no explanations. Every slot_id from
    the input schema appears as a key exactly once."""


TEXT_TIGHTENER_SYSTEM = """You are a tightening editor. The previous fill
pass produced slot values that exceed their word budget. Rewrite ONLY the
slots listed below to fit within max_words, while preserving the slot's
intent and any parallel-to relationship. Same hard rules:

- NO em dashes or en dashes (U+2014, U+2013). Use commas / periods.
- NO competitor names.
- COMPLETE phrases, not fragments. Rephrase tightly; do not chop trailing
  words.
- Parallel slots stay structurally parallel to their partner.

Output VALID JSON only — one key per slot_id passed in, value = tightened
fill. No prose, no fences."""


_WORD_RE = re.compile(r"\S+")

# U+2014 em dash, U+2013 en dash, U+2015 horizontal bar, U+2212 minus sign.
# All forbidden in rendered ad text — known AI-content tell per user
# preference (see memory: feedback_native_ad_design.md).
# Replace `<optional space>DASH<optional space>` with ", " so spacing
# normalizes regardless of how the source punctuated.
_DASH_RUN_RE = re.compile(r"\s*[—–―−]\s*")


def _count_words(text: str) -> int:
    """Whitespace-separated word count. Treats hyphenated compounds as 1."""
    return len(_WORD_RE.findall(text or ""))


def _scrub_em_dashes(text: str) -> str:
    """Strip em/en dashes from rendered ad text.

    The user has a hard rule against em-dashes appearing in any image-
    rendered text. Substitutes ", " for em/en dashes regardless of
    surrounding whitespace, so "Compounds — not bacteria",
    "Compounds—not bacteria", and "Compounds —not bacteria" all become
    "Compounds, not bacteria". ASCII hyphen-minus (U+002D) is preserved
    so "live-bacteria" stays intact.

    Collapses consecutive commas / dangling trailing punctuation that the
    substitution can produce at string edges.
    """
    if not text:
        return text

    out = _DASH_RUN_RE.sub(", ", text)
    # Collapse "x , , y" → "x, y" — happens when adjacent dashes are scrubbed.
    out = re.sub(r"(?:,\s*){2,}", ", ", out)
    # Normalize internal whitespace runs.
    out = re.sub(r"\s+", " ", out).strip()
    # If a dash sat at the very start or end of the string, the substitution
    # leaves a leading/trailing ", " — strip it.
    out = out.lstrip(",;: ").rstrip(",;: ")
    return out


def _format_slot_for_prompt(slot: TextSlot) -> str:
    """Render a TextSlot as a labeled block for the fill prompt."""
    lines = [
        f"- slot_id: {slot.slot_id}",
        f"  role: {slot.role}",
        f"  intent: {slot.intent}",
    ]
    if slot.pattern:
        lines.append(f"  pattern: {slot.pattern}")
    lines.append(f"  max_words: {slot.max_words}")
    if slot.parallel_to:
        lines.append(f"  parallel_to: {slot.parallel_to}")
    if slot.tone:
        lines.append(f"  tone: {slot.tone}")
    return "\n".join(lines)


def _build_avatar_context(avatar: CustomerAvatar | None) -> str:
    """Pull the avatar's most fill-relevant signals into a tight block."""
    if avatar is None:
        return "(no avatar context available)"
    parts: list[str] = []
    if avatar.name:
        parts.append(f"Persona: {avatar.name}")
    if avatar.demographic:
        parts.append(f"Demographic: {avatar.demographic}")
    if avatar.psychographic:
        parts.append(f"Psychographic: {avatar.psychographic}")
    if avatar.awareness_level:
        parts.append(f"Awareness level: {avatar.awareness_level}")
    if avatar.pain_points:
        top_pains = avatar.pain_points[:3]
        for p in top_pains:
            quotes = (p.customer_language or [])[:2]
            quote_block = (
                "; ".join(f'"{q}"' for q in quotes) if quotes else "(no quotes)"
            )
            parts.append(f"  Pain: {p.pain} — customer language: {quote_block}")
    if avatar.desires:
        top_desires = avatar.desires[:2]
        for d in top_desires:
            parts.append(f"  Desire: {d.desire}")
    if avatar.language_patterns:
        parts.append(
            "Language patterns: " + "; ".join(avatar.language_patterns[:3])
        )
    return "\n".join(parts) if parts else "(empty avatar)"


def _build_product_context(brand: Brand, product: Product) -> str:
    """Tight product/brand block — just what the fill step needs."""
    parts: list[str] = [
        f"Brand: {brand.name}",
        f"Brand tone: {brand.tone or '(none set)'}",
    ]
    if brand.prohibited_terms:
        parts.append(
            "PROHIBITED TERMS (NEVER use): " + ", ".join(brand.prohibited_terms)
        )
    parts.extend(
        [
            f"Product: {product.name}",
            f"Description: {product.description}",
        ]
    )
    if product.unique_mechanism:
        parts.append(f"Unique mechanism: {product.unique_mechanism}")
    if product.benefits:
        parts.append("Benefits: " + " | ".join(product.benefits[:5]))
    if product.objections:
        parts.append("Common objections: " + " | ".join(product.objections[:3]))
    return "\n".join(parts)


def _build_brief_context(brief: CreativeBrief) -> str:
    """The brief's strategic anchors — drives angle, hook, pain framing."""
    parts: list[str] = [
        f"Awareness level: {brief.awareness_level.value}",
        f"Framework: {brief.framework.value}",
        f"Angle: {brief.angle}",
        f"Hook (long form — compress for slot fills): {brief.hook}",
    ]
    if brief.hook_type:
        parts.append(f"Hook type: {brief.hook_type}")
    if brief.hook_tactic:
        parts.append(f"Hook tactic: {brief.hook_tactic}")
    if brief.pain_point:
        parts.append(f"Pain addressed: {brief.pain_point}")
    if brief.benefit_callouts:
        parts.append("Benefit callouts: " + " | ".join(brief.benefit_callouts[:4]))
    if brief.cta:
        parts.append(f"CTA (long form): {brief.cta}")
    if brief.creative_mechanic:
        parts.append(f"Creative mechanic: {brief.creative_mechanic}")
    if brief.persona:
        parts.append(f"Persona: {brief.persona}")
    return "\n".join(parts)


def _validate_and_repair(
    raw: dict[str, str],
    schema: list[TextSlot],
    brief: CreativeBrief,
    brand: Brand | None = None,
) -> dict[str, str]:
    """Ensure every slot is present and within its max_words ceiling.

    Missing slots → filled with a brief-derived default (hook for headline,
    benefit_callout[i] for bullets, brief.cta for cta, brand name for
    wordmark). Over-budget slots → tightened by truncating to max_words.

    The fallback path keeps the pipeline producing output even when the LLM
    misses a slot or runs over budget. Without this, a single bad fill
    would block the whole generation.

    Bullet slots use the slot's position among bullet slots in the schema
    (not its loop index) to look up the matching benefit_callout, so a
    partially-missed bullet sequence still maps to the right callout.
    """
    bullet_position: dict[str, int] = {}
    counter = 0
    for slot in schema:
        if slot.role.lower() == "bullet":
            bullet_position[slot.slot_id] = counter
            counter += 1

    out: dict[str, str] = {}
    for slot in schema:
        value = (raw.get(slot.slot_id) or "").strip()
        if not value:
            idx = bullet_position.get(slot.slot_id, 0)
            value = _fallback_for_slot(slot, brief, idx, brand)
        if _count_words(value) > slot.max_words:
            words = _WORD_RE.findall(value)
            value = " ".join(words[: slot.max_words]).rstrip(",;:- ")
        out[slot.slot_id] = value
    return out


def _fallback_for_slot(
    slot: TextSlot,
    brief: CreativeBrief,
    bullet_index: int,
    brand: Brand | None = None,
) -> str:
    """Slot-shaped default when the LLM omits a slot.

    Keeps the pipeline running and never injects reference verbatim text —
    every fallback comes from the brief or brand context.
    """
    role = slot.role.lower()
    if role == "cta":
        return (brief.cta or "Shop now")[: max(2, slot.max_words) * 12]
    if role == "headline":
        hook = (brief.hook or brief.angle or "").strip()
        words = _WORD_RE.findall(hook)
        return " ".join(words[: slot.max_words]) or "See the difference"
    if role == "bullet":
        callouts = brief.benefit_callouts or []
        if bullet_index < len(callouts):
            words = _WORD_RE.findall(callouts[bullet_index])
            return " ".join(words[: slot.max_words])
        return ""
    if role == "wordmark":
        # The brand name (lowercased) is the right fallback for a wordmark
        # slot. Without `brand`, we degrade to a blank — slot_id is a
        # snake_case identifier and would render as nonsense ("brand wordmark").
        if brand and brand.name:
            return brand.name.lower()
        return ""
    if role == "subhead":
        pain = (brief.pain_point or brief.angle or "").strip()
        words = _WORD_RE.findall(pain)
        return " ".join(words[: slot.max_words])
    return ""


def _strip_code_fences(text: str) -> str:
    """Remove ```json / ``` fences if Claude wrapped its output."""
    t = text.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        if nl != -1:
            t = t[nl + 1 :]
    if t.endswith("```"):
        t = t.rsplit("```", 1)[0].rstrip()
    return t.strip()


def _tighten_over_budget_slots(
    fills: dict[str, str], schema: list[TextSlot]
) -> dict[str, str]:
    """One additional Claude call to semantically tighten any slot that
    exceeds its max_words budget. Preserves intent; avoids mid-phrase chop.

    Returns the input map with over-budget entries replaced by tightened
    versions. Slots that were already within budget are unchanged.
    On call failure, returns the input unchanged (caller's truncation
    fallback still runs downstream).
    """
    over_budget: list[TextSlot] = []
    for slot in schema:
        value = fills.get(slot.slot_id, "") or ""
        if _count_words(value) > slot.max_words:
            over_budget.append(slot)

    if not over_budget:
        return fills

    parallel_partners: dict[str, str] = {}
    for slot in over_budget:
        if slot.parallel_to:
            parallel_partners[slot.parallel_to] = (
                fills.get(slot.parallel_to, "") or ""
            )

    over_block_lines = []
    for slot in over_budget:
        cur = fills.get(slot.slot_id, "")
        cur_count = _count_words(cur)
        parts = [
            f"- slot_id: {slot.slot_id}",
            f"  role: {slot.role}",
            f"  intent: {slot.intent}",
        ]
        if slot.pattern:
            parts.append(f"  pattern: {slot.pattern}")
        parts.append(f"  max_words: {slot.max_words}")
        if slot.parallel_to:
            partner_value = parallel_partners.get(slot.parallel_to, "")
            parts.append(
                f"  parallel_to: {slot.parallel_to} (partner = "
                f'"{partner_value}")'
            )
        parts.append(
            f'  current_value: "{cur}" (current word count: {cur_count}; '
            f"OVER by {cur_count - slot.max_words})"
        )
        over_block_lines.append("\n".join(parts))
    over_block = "\n".join(over_block_lines)

    user_prompt = (
        "These slots exceed their word budget. Rewrite each ONE to fit "
        "within max_words while preserving the intent and (if applicable) "
        "structural parallel with the partner slot. Complete phrases only — "
        "no truncated fragments.\n\n"
        f"{over_block}\n\n"
        "Output JSON only — one key per slot_id above, no extra keys."
    )

    try:
        response = claude_complete(
            user_prompt, system=TEXT_TIGHTENER_SYSTEM, max_tokens=512
        )
        tightened = json.loads(_strip_code_fences(response))
        if not isinstance(tightened, dict):
            return fills
    except Exception:
        return fills

    out = dict(fills)
    for slot in over_budget:
        new_value = (tightened.get(slot.slot_id) or "").strip()
        if new_value and _count_words(new_value) <= slot.max_words:
            out[slot.slot_id] = new_value
    return out


def fill_text_schema_for_brief(
    brief: CreativeBrief,
    schema: list[TextSlot],
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
) -> dict[str, str]:
    """Generate one ICP-language fill per slot in `schema`.

    Returns `{slot_id: fill_text}` for every slot. Missing/over-budget slots
    are repaired against `brief` so the caller always gets a complete map.
    """
    if not schema:
        return {}

    schema_block = "\n".join(_format_slot_for_prompt(s) for s in schema)
    avatar_block = _build_avatar_context(avatar)
    product_block = _build_product_context(brand, product)
    brief_block = _build_brief_context(brief)

    user_prompt = (
        "Fill every slot in the TEXT SCHEMA below. Write one ICP-language "
        "string per slot, honoring max_words, parallel_to, and tone for each.\n\n"
        "TEXT SCHEMA:\n"
        f"{schema_block}\n\n"
        "BRIEF (strategic input — drives angle, pain framing, voice):\n"
        f"{brief_block}\n\n"
        "PRODUCT & BRAND CONTEXT:\n"
        f"{product_block}\n\n"
        "AVATAR / ICP CONTEXT (use this language register):\n"
        f"{avatar_block}\n\n"
        "Output JSON only — one key per slot_id, exact ids preserved."
    )

    parsed: dict = {}
    import os as _os
    debug = _os.environ.get("TEXT_REMAPPER_DEBUG") == "1"
    response = ""
    try:
        response = claude_complete(
            user_prompt, system=TEXT_REMAPPER_SYSTEM, max_tokens=2048
        )
        parsed = json.loads(_strip_code_fences(response))
        if not isinstance(parsed, dict):
            parsed = {}
    except json.JSONDecodeError as exc:
        # Surface the failure to stderr so callers can debug a malformed
        # Claude response. The pipeline still degrades gracefully via
        # _validate_and_repair below — empty `parsed` means every slot
        # uses its brief-derived fallback.
        import sys as _sys
        _sys.stderr.write(
            f"[text_remapper] JSON parse failed: {exc}\n"
            f"[text_remapper] Raw response (first 800 chars):\n"
            f"{response[:800]}\n"
        )
    except Exception as exc:  # noqa: BLE001
        import sys as _sys
        _sys.stderr.write(f"[text_remapper] fill call failed: {exc}\n")

    if debug:
        import sys as _sys
        _sys.stderr.write(
            f"[text_remapper.DEBUG] Claude raw response:\n{response}\n"
            f"[text_remapper.DEBUG] Parsed dict keys: {sorted(parsed.keys())}\n"
            f"[text_remapper.DEBUG] Schema slot_ids: "
            f"{[s.slot_id for s in schema]}\n"
        )

    # Scrub em/en dashes BEFORE measuring word budgets — the substitution
    # can change word counts (", " adds whitespace where "—" had none).
    parsed = {k: _scrub_em_dashes(v) if isinstance(v, str) else v
              for k, v in parsed.items()}

    # If anything is over its word budget, try a single tightening call
    # before falling through to the lossy truncation in _validate_and_repair.
    parsed = _tighten_over_budget_slots(parsed, schema)

    # Final scrub in case the tightener slipped a dash through.
    parsed = {k: _scrub_em_dashes(v) if isinstance(v, str) else v
              for k, v in parsed.items()}

    out = _validate_and_repair(parsed, schema, brief, brand)

    # Belt-and-suspenders: scrub the validated output too, in case a
    # fallback path inserted a dash from the brief / brand.
    return {k: _scrub_em_dashes(v) for k, v in out.items()}


def substitute_slot_fills(template_prompt: str, fills: dict[str, str]) -> str:
    """Mechanically replace [SLOT_ID] markers in `template_prompt` with their
    fills. Uppercases each slot_id to match the placeholder convention used
    by the template extractor.

    Unknown placeholders are left intact so a future audit can spot them.
    """
    out = template_prompt
    for slot_id, fill in fills.items():
        marker = "[" + slot_id.upper() + "]"
        out = out.replace(marker, fill)
    return out


def render_slot_fills_block(
    fills: dict[str, str], schema: list[TextSlot]
) -> str:
    """Format the fills as a SLOT FILLS block for inclusion in the NB2 prompt
    writer's user prompt.

    The block doubles as a canonical source of truth: even if the LLM strips
    the in-line placeholders during prompt rewriting, this block lists each
    slot's exact rendered text. The accompanying instructions tell the
    writer the reference image's text is for layout only.
    """
    if not fills or not schema:
        return ""
    lines = [
        "SLOT FILLS — SOURCE OF TRUTH FOR ON-IMAGE TEXT:",
        "These are the exact strings NB2 should render. The reference image's "
        "text is for typography and layout reference ONLY — do NOT transcribe "
        "any text visible on Image 2. Use only the values below.",
        "",
    ]
    for slot in schema:
        value = fills.get(slot.slot_id, "")
        lines.append(
            f'  [{slot.slot_id.upper()}] ({slot.role}, '
            f'max {slot.max_words}w): "{value}"'
        )
    return "\n".join(lines)
