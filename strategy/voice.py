"""ICP voice pack helper — shared by ad_remixer (differential mapping) and
prompt_engine (brief condensation).

The "voice pack" is a markdown-like block formatted from a CustomerAvatar's
language_patterns + verbatim customer_language quotes (from pain_points and
desires). It's dropped into LLM prompts as the "this is how the customer
talks" reference register, so target ad copy reads like the customer
observing/complaining/celebrating rather than like a marketer pitching.

Used by:
  - strategy.ad_remixer._generate_source_to_target_mapping (differential mode)
  - generators.prompt_engine.condense_brief_for_ad (every brief→prompt path)
"""

from __future__ import annotations

from models.avatar import CustomerAvatar


def format_voice_pack(
    avatar: CustomerAvatar | None,
    *,
    max_patterns: int = 5,
    max_pain_quotes: int = 8,
    max_outcome_quotes: int = 8,
) -> str:
    """Render an avatar's voice signal as an LLM prompt block.

    Returns "" if avatar is None or has no useful signal — callers should
    treat empty string as "no voice pack available, infer from persona name."

    The block format intentionally mirrors what a copy-aware Claude prompt
    would expect: a brief intro, language patterns, customer pain quotes,
    customer outcome quotes. Quotes are kept VERBATIM (the whole point —
    they're the register the customer actually uses, not a paraphrase).
    """
    if avatar is None:
        return ""

    lines: list[str] = []
    lines.append(
        "ICP VOICE PACK (this is how the customer talks — match this register):"
    )
    lines.append("")

    patterns = (avatar.language_patterns or [])[:max_patterns]
    if patterns:
        lines.append("Language patterns:")
        for p in patterns:
            lines.append(f"  - {p[:200]}")
        lines.append("")

    # Pain customer-language samples — voice register for failure-state /
    # "without your product" callouts.
    pain_quotes: list[str] = []
    for pp in (avatar.pain_points or [])[:5]:
        for q in (pp.customer_language or [])[:2]:
            qs = (q or "").strip()
            if qs:
                pain_quotes.append(qs)
    if pain_quotes:
        lines.append(
            "Customer pain quotes (verbatim) — voice register for pain callouts:"
        )
        for q in pain_quotes[:max_pain_quotes]:
            lines.append(f'  - "{q}"')
        lines.append("")

    # Desire customer-language samples — voice register for outcome-state /
    # "with your product" callouts.
    desire_quotes: list[str] = []
    for d in (avatar.desires or [])[:5]:
        for q in (d.customer_language or [])[:2]:
            qs = (q or "").strip()
            if qs:
                desire_quotes.append(qs)
    if desire_quotes:
        lines.append(
            "Customer outcome quotes (verbatim) — voice register for benefit callouts:"
        )
        for q in desire_quotes[:max_outcome_quotes]:
            lines.append(f'  - "{q}"')
        lines.append("")

    # If we have absolutely nothing (avatar exists but is empty of language
    # signal), return empty string — caller treats that as "no pack".
    if len(lines) <= 2:
        return ""

    return "\n".join(lines)
