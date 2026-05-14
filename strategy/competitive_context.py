"""Shared helpers for loading + formatting competitive/voc/psychology context.

Used by `strategy/matrix.py`, `strategy/psychology_profiler.py`, and
`strategy/brief_generator.py` to inject upstream research data into their
LLM prompts. All loaders return None (or empty string for formatters) when
the underlying file is missing — every downstream stage degrades gracefully.

The same data is loaded in two formats:
    * `load_*` returns the raw dict (used for programmatic consumers like the
      brief angle multiplier)
    * `format_*_block` returns a prompt-ready markdown block (used for
      injection into LLM prompts)
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml

CLIENTS_DIR = Path("clients")

NO_GAPS_PLACEHOLDER = (
    "(No competitive gap map available — proceed from brand + audience alone.)"
)
NO_VOC_PLACEHOLDER = (
    "(No VOC corpus available — proceed from avatar + brand alone.)"
)
NO_PSYCH_PLACEHOLDER = (
    "(No psychology profiles available — proceed from raw avatar data.)"
)


# ─── Competitive gap map ────────────────────────────────────────────────────


def load_competitive_gaps(client_slug: str) -> dict | None:
    """Return parsed competitive-gaps.yaml or None if missing/empty."""
    path = CLIENTS_DIR / client_slug / "research" / "competitive-gaps.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if isinstance(data, dict) and data.get("synthesis"):
        return data
    return None


def format_competitive_block(gaps: dict | None) -> str:
    """Format the gap synthesis as a prompt-ready markdown block.

    Surfaces only the high-signal fields: exploitable_gaps, recurring_complaints,
    competitor_strengths_to_concede. Caps each list so we don't blow the token
    budget on long pulls.
    """
    if not gaps or not isinstance(gaps, dict):
        return NO_GAPS_PLACEHOLDER

    synthesis = gaps.get("synthesis") or {}
    if not isinstance(synthesis, dict):
        return NO_GAPS_PLACEHOLDER

    lines: list[str] = []

    exploitable = synthesis.get("exploitable_gaps") or []
    if exploitable:
        lines.append("**Exploitable competitor gaps:**")
        for g in exploitable[:8]:
            if isinstance(g, dict):
                desc = g.get("gap") or g.get("description") or g.get("title") or ""
                ev = g.get("evidence") or g.get("rationale") or ""
                lines.append(f"  - {desc}" + (f" — _{ev}_" if ev else ""))
            else:
                lines.append(f"  - {g}")

    complaints = synthesis.get("recurring_complaints") or []
    if complaints:
        lines.append("")
        lines.append("**Recurring complaints against competitors:**")
        for c in complaints[:8]:
            if isinstance(c, dict):
                desc = c.get("complaint") or c.get("description") or c.get("title") or ""
                lines.append(f"  - {desc}")
            else:
                lines.append(f"  - {c}")

    concede = synthesis.get("competitor_strengths_to_concede") or []
    if concede:
        lines.append("")
        lines.append("**Competitor strengths to concede (do not attack):**")
        for s in concede[:5]:
            if isinstance(s, dict):
                desc = s.get("strength") or s.get("description") or s.get("title") or ""
                lines.append(f"  - {desc}")
            else:
                lines.append(f"  - {s}")

    if not lines:
        return NO_GAPS_PLACEHOLDER
    return "\n".join(lines)


# ─── Voice of customer pains ────────────────────────────────────────────────


def load_voc_pains(client_slug: str) -> dict | None:
    """Return parsed voc/extracted_pains.yaml or None if missing/empty."""
    path = CLIENTS_DIR / client_slug / "voc" / "extracted_pains.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return None
    if isinstance(data, dict) and data:
        return data
    return None


def format_voc_block(voc: dict | None) -> str:
    """Format the VOC corpus as a prompt-ready yaml block.

    Surfaces only the high-signal sections; pass-through can blow the
    token budget on long mines.
    """
    if not voc or not isinstance(voc, dict):
        return NO_VOC_PLACEHOLDER

    relevant_keys = (
        "pain_points",
        "desires",
        "objections",
        "trigger_events",
        "trigger_moments",
        "transformations",
        "language_patterns",
        "money_quotes",
    )
    relevant = {k: voc.get(k, []) for k in relevant_keys if voc.get(k)}
    if not relevant:
        return NO_VOC_PLACEHOLDER

    body = yaml.safe_dump(relevant, sort_keys=False, allow_unicode=True)
    return f"```yaml\n{body}\n```"


# ─── Avatar psychology profiles ─────────────────────────────────────────────


def format_psychology_summary(avatars: Iterable) -> str:
    """One-paragraph summary per avatar of their psychology profile.

    Accepts CustomerAvatar instances; reads `psychology_profile` off each
    one. Avatars without a profile are skipped silently. Returns the
    no-psych placeholder if no avatar in the iterable has a profile.
    """
    blocks: list[str] = []
    for av in avatars:
        profile = getattr(av, "psychology_profile", None)
        if not profile:
            continue

        name = getattr(av, "name", None) or "Avatar"

        # Profile may be a model instance (PsychologyProfile) or a dict
        if hasattr(profile, "model_dump"):
            pdata = profile.model_dump(mode="json")
        elif isinstance(profile, dict):
            pdata = profile
        else:
            continue

        dom = pdata.get("dominant_heuristics") or []
        dom_names = [h.get("heuristic", "?") for h in dom if isinstance(h, dict)]

        weak = pdata.get("weak_heuristics") or []
        weak_names = [h.get("heuristic", "?") for h in weak if isinstance(h, dict)]

        emo = pdata.get("emotional_position") or {}
        primary_emo = emo.get("primary") or {}
        valence = primary_emo.get("valence", "?")
        intensity = primary_emo.get("intensity", "?")

        recommended = pdata.get("recommended_prompt_pairings") or []
        rec_names = [
            p.get("pairing", "?") for p in recommended[:4] if isinstance(p, dict)
        ]

        avoid = pdata.get("avoid_pairings") or []
        avoid_names = [
            p.get("pairing", "?") for p in avoid[:3] if isinstance(p, dict)
        ]

        lines = [
            f"**{name}**",
            f"  - Dominant heuristics: {', '.join(dom_names) or '(none)'}",
            f"  - Weak heuristics (avoid leaning on these): {', '.join(weak_names) or '(none)'}",
            f"  - Emotional position: {valence} valence / {intensity} intensity",
            f"  - Recommended pairings: {', '.join(rec_names) or '(none)'}",
            f"  - Avoid pairings: {', '.join(avoid_names) or '(none)'}",
        ]
        blocks.append("\n".join(lines))

    if not blocks:
        return NO_PSYCH_PLACEHOLDER
    return "\n\n".join(blocks)
