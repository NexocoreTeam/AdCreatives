"""Brand voice — the sender-side voice layer (Phase 1, Step 11).

Reads the personas (verbatim customer language), the VoC corpus, and the
competitive context, then finds the brand's ownable voice in the gap between
how customers actually talk and how the category sounds. Produces a
human-readable voice.md plus a structured voice.yaml whose
`personas[].unspoken_truths` bank downstream brief + hook generation pulls
from before inventing anything.

Sender-side twin of psychology_profiler.py (which maps how the customer
decides). System context is the brand-voice skill. Output feeds the brief
generator and any copywriting.

NB: distinct from strategy/voice.py, which is the lower-level "voice pack"
helper that injects a customer's verbatim register into a single prompt. This
module defines the brand's ownable voice + the persona-tagged truths bank.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.skills import load_skill
from models.voice import BrandVoice
from strategy.competitive_context import (
    format_competitive_block,
    format_voc_block,
    load_competitive_gaps,
    load_voc_pains,
)
from strategy.llm import claude_complete

CLIENTS_DIR = Path("clients")


VOICE_SYSTEM = """You are a brand voice strategist. You find the way a brand
should SOUND so its copy feels like a human who gets the customer, not a brand
selling at them. You diagnose and define — you do not write finished ads.

Follow the skill below as your method. The single most important rule: derive
the voice from the GAP between how customers actually talk and how the category
sounds. NEVER from the brand's own self-description.

--- BRAND VOICE SKILL ---

""" + load_skill("brand-voice") + """

---

Output VALID JSON ONLY — no prose, no markdown fences. Use double-quoted
strings and escape inner quotes with a backslash. The shape:

{
  "territory": "the ownable voice territory, one sentence",
  "why_open": "why this register is open — the competitor-voice whitespace (internal)",
  "voice_register": "how the brand sounds, named",
  "structural_move": "the structural pattern, e.g. open in the customer's register, close in the brand's proof register",
  "guardrail_test": "the one-line test that keeps a line on-side vs shaming the customer",
  "hard_rules_retained": ["existing brand rule that still holds", "..."],
  "personas": [
    {
      "persona_id": "primary",
      "persona_name": "matches the avatar name",
      "register_note": "how the voice flexes for this persona, including any off-limits topics",
      "unspoken_truths": ["a specific lived-experience truth in their own register", "..."]
    }
  ],
  "founder_voice": "where the founder voice goes further than the brand, with one example — empty string if no founder",
  "changes_vs_existing": ["explicit delta vs the brand's current tone/rules", "..."]
}"""


@dataclass
class BrandVoiceResult:
    voice_md: str
    voice: BrandVoice


def _format_personas_for_voice(avatars: list[CustomerAvatar]) -> str:
    """Dump each avatar's verbatim language as YAML for the prompt.

    The verbatim customer_language, trigger_events, and language_patterns are
    the raw material for unspoken truths — keep them whole, do not summarize.
    """
    blocks: list[str] = []
    for av in avatars:
        relevant = {
            "name": av.name,
            "demographic": av.demographic,
            "awareness_level": av.awareness_level,
            "pain_points": [
                {"pain": p.pain, "customer_language": p.customer_language}
                for p in av.pain_points
            ],
            "desires": [
                {"desire": d.desire, "customer_language": d.customer_language}
                for d in av.desires
            ],
            "objections": av.objections,
            "trigger_events": av.trigger_events,
            "language_patterns": av.language_patterns,
        }
        body = yaml.safe_dump(relevant, sort_keys=False, allow_unicode=True)
        blocks.append(f"```yaml\n{body}```")
    return "\n\n".join(blocks) if blocks else "(no personas defined)"


def _parse_voice(text: str, client_slug: str | None = None) -> dict:
    """Parse LLM output into a dict. JSON first, json-repair, then YAML.

    Creative output is quote-heavy, so JSON with proper escaping is the safest
    format. json-repair catches the common LLM JSON slips (trailing commas,
    unescaped newlines); YAML is the last resort. Unwraps a `brand_voice`
    top-level key if present.
    """
    text = text.strip()
    if text.startswith("```"):
        nl = text.find("\n")
        if nl != -1:
            text = text[nl + 1:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()
    text = text.strip()
    if not text:
        raise ValueError("LLM returned empty response for brand voice")

    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            from json_repair import repair_json

            obj = repair_json(text, return_objects=True)
            if isinstance(obj, dict) and obj:
                data = obj
        except Exception:
            data = None

    if data is None:
        try:
            loaded = yaml.safe_load(text)
            if isinstance(loaded, dict):
                data = loaded
        except yaml.YAMLError:
            data = None

    if not isinstance(data, dict):
        dump_path = CLIENTS_DIR / (client_slug or "_unknown") / "voice.raw.txt"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(text, encoding="utf-8")
        raise ValueError(
            f"Brand voice LLM output failed to parse as JSON or YAML. "
            f"Raw output saved to {dump_path} for inspection."
        )

    if "brand_voice" in data and isinstance(data["brand_voice"], dict):
        data = data["brand_voice"]
    return data


def build_voice(
    brand: Brand,
    avatars: list[CustomerAvatar],
    brand_context_md: str = "",
    client_slug: str | None = None,
    competitive_gaps: dict | None = None,
    voc_pains: dict | None = None,
) -> BrandVoiceResult:
    """Find the brand's ownable voice and return md + structured artifact.

    Upstream research auto-loads when `client_slug` is supplied and the files
    exist (competitive gaps + VoC corpus). Each slice degrades gracefully when
    missing — the voice still builds, just with thinner grounding. Pass
    `competitive_gaps`/`voc_pains` explicitly to override the auto-load (tests).
    """
    if not avatars:
        raise ValueError(
            "No personas to build a voice for. Run `adc personas` (or `adc research`) "
            "first — the voice is mined from verbatim persona language."
        )

    if client_slug:
        if competitive_gaps is None:
            competitive_gaps = load_competitive_gaps(client_slug)
        if voc_pains is None:
            voc_pains = load_voc_pains(client_slug)

    personas_text = _format_personas_for_voice(avatars)
    competitive_block = format_competitive_block(competitive_gaps)
    voc_block = format_voc_block(voc_pains)
    founder = getattr(brand, "founder", "") or "(none named)"

    prompt = f"""Find the ownable brand voice for {brand.name}.

Work the three reads from the skill. Mine the personas' verbatim language and
the VoC corpus for unspoken truths and native register. Map the category voice
from the competitive context to find the empty register. Claim the gap.

BRAND:
  Name: {brand.name}
  Current tone (this is the SELF-DESCRIPTION — do not just echo it): {getattr(brand, 'tone', '') or '(not specified)'}
  Mission: {getattr(brand, 'mission', '') or '(not specified)'}
  Founder: {founder}

PERSONAS (verbatim language is the raw material for unspoken truths):
{personas_text}

BRAND CONTEXT (excerpt for grounding — again, do not just echo the brand's framing):
{brand_context_md[:6000]}

# COMPETITIVE INTELLIGENCE (use to find the empty register)

{competitive_block}

# VOICE-OF-CUSTOMER EVIDENCE (the unfiltered register lives here)

{voc_block}

---

Produce the brand voice JSON per the schema in the system prompt.

Requirements:
1. Apply the generative guardrail: at least one unspoken truth must be a line the
   brand would currently NEVER say. If every line is comfortable, go deeper.
2. Give EACH persona 4-6 unspoken truths, tagged to that persona. Each must pass
   the guardrail test (something she would say about herself, to a friend).
3. Honor per-persona sensitivities surfaced in the context (off-limits topics).
   When unsure, keep truths on the side of lived experience, not appearance.
4. Source the register from how customers actually talk, not from the brand's tone line.
5. If a founder is named, fill `founder_voice` with where the founder goes further,
   plus one example. Otherwise leave it an empty string.
6. List real `changes_vs_existing` when the new voice diverges from the current tone,
   and `hard_rules_retained` for the existing rules that still hold.

Output JSON only — no prose, no markdown fences:"""

    raw = claude_complete(prompt, system=VOICE_SYSTEM, max_tokens=12000)
    data = _parse_voice(raw, client_slug)
    voice = BrandVoice(**data)
    voice_md = _render_markdown(brand, voice)
    return BrandVoiceResult(voice_md=voice_md, voice=voice)


def _render_markdown(brand: Brand, voice: BrandVoice) -> str:
    """Render the structured voice as a human-readable guideline doc."""
    lines: list[str] = []
    lines.append(f"# {brand.name} — Voice")
    lines.append("")
    lines.append(
        "The sender-side layer: who the brand is and how it sounds, as distinct "
        "from who the customer is. Found in the gap between how customers talk and "
        "how the category sounds."
    )
    lines.append("")

    if voice.territory:
        lines.append("## The territory we own")
        lines.append("")
        lines.append(voice.territory)
        lines.append("")
        if voice.why_open:
            lines.append(f"*Why it's open (internal):* {voice.why_open}")
            lines.append("")

    if voice.voice_register or voice.structural_move:
        lines.append("## How we sound")
        lines.append("")
        if voice.voice_register:
            lines.append(voice.voice_register)
            lines.append("")
        if voice.structural_move:
            lines.append(f"**Structural move:** {voice.structural_move}")
            lines.append("")

    if voice.guardrail_test or voice.hard_rules_retained:
        lines.append("## The line we won't cross")
        lines.append("")
        if voice.guardrail_test:
            lines.append(voice.guardrail_test)
            lines.append("")
        for rule in voice.hard_rules_retained:
            lines.append(f"- {rule}")
        if voice.hard_rules_retained:
            lines.append("")

    if voice.personas:
        lines.append("## The unspoken-truths bank")
        lines.append("")
        lines.append(
            "The raw material for hooks. Each line is already a hook, because a true "
            "thing said plainly stops the scroll. Pull from here before inventing anything."
        )
        lines.append("")
        for pv in voice.personas:
            header = pv.persona_name or pv.persona_id or "Persona"
            lines.append(f"### {header}")
            lines.append("")
            if pv.register_note:
                lines.append(f"*{pv.register_note}*")
                lines.append("")
            for truth in pv.unspoken_truths:
                lines.append(f"- {truth}")
            lines.append("")

    if voice.founder_voice:
        lines.append("## Founder voice")
        lines.append("")
        lines.append(voice.founder_voice)
        lines.append("")

    if voice.changes_vs_existing:
        lines.append("## What this changes vs the current rules")
        lines.append("")
        for change in voice.changes_vs_existing:
            lines.append(f"- {change}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "*Provenance: territory and register found in the gap between how customers "
        "actually talk (VoC + personas) and how the category sounds (competitive context). "
        "The bank is drawn from verbatim persona language. Generated by `adc voice`.*"
    )
    return "\n".join(lines)


def save_voice(client_slug: str, result: BrandVoiceResult) -> tuple[Path, Path]:
    """Persist the voice as both markdown and structured YAML."""
    client_dir = CLIENTS_DIR / client_slug
    md_path = client_dir / "voice.md"
    yaml_path = client_dir / "voice.yaml"

    md_path.write_text(result.voice_md, encoding="utf-8")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(
            result.voice.model_dump(mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return md_path, yaml_path
