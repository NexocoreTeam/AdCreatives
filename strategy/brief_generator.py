"""Assemble complete creative briefs from strategy components."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief, MentalStage
from models.product import Product
from models.result import WinningPatterns
from strategy.angle_multiplier import generate_angles
from strategy.awareness_mapper import (
    classify_awareness,
    distribute_across_stages,
    get_awareness_strategy,
    select_frameworks,
)


_BENEFIT_TAG_RE = re.compile(
    r"^\s*\[(?:functional|emotional|social|status|trust|safety|"
    r"convenience|ergonomic|aesthetic)\]\s*",
    re.IGNORECASE,
)


def _strip_benefit_tag(b: str) -> str:
    """Remove a leading `[functional]/[emotional]/[social]/...` category tag.

    Product YAMLs prefix benefits with their category for offline filtering;
    those tags MUST be stripped before they end up in briefs.yaml — otherwise
    they get drawn onto the rendered ad as literal text.
    """
    if not isinstance(b, str):
        return ""
    return _BENEFIT_TAG_RE.sub("", b).strip()


def _clean_callouts(
    raw: list | None, *, product: Product, brief_index: int, n: int = 3
) -> list[str]:
    """Return up to `n` clean (tag-stripped) benefit callouts for a brief.

    Order of preference:
      1. Use the LLM-supplied `raw` callouts if non-empty (persona-specific
         by definition). Always strip the category tag.
      2. Otherwise rotate a window of `n` over the product's full benefits
         list, offset by brief_index. Each brief in a batch gets a different
         3-callout mix, so we don't ship 5 briefs with the same [:3] slice.
    """
    cleaned = [_strip_benefit_tag(c) for c in (raw or []) if c]
    cleaned = [c for c in cleaned if c]
    if cleaned:
        return cleaned[:n] if n else cleaned

    all_benefits = [_strip_benefit_tag(b) for b in (product.benefits or []) if b]
    all_benefits = [b for b in all_benefits if b]
    if not all_benefits:
        return []
    if len(all_benefits) <= n:
        return all_benefits[:n]
    start = brief_index % len(all_benefits)
    rotated = all_benefits[start:] + all_benefits[:start]
    return rotated[:n]


def _make_brief_id(client: str, product: str, index: int, *, avatar: str = "") -> str:
    """Generate a short, run-unique brief ID.

    The hash incorporates:
      - The avatar name, so auto-spread across multiple avatars in one
        run produces distinct IDs (was previously colliding because each
        per-avatar call to `generate_briefs` restarted indexing at 0).
      - A microsecond-precision timestamp, so re-runs on the same day
        accumulate briefs instead of overwriting each other (was
        previously keyed on `date.today()` only, which meant indices
        0..N collided across every same-day run).
      - 4 bytes of secrets-grade randomness as a final tie-breaker for
        rapid-fire calls that share a microsecond.

    The visible ID shape (`<client>-<product>-<hash>`) is unchanged, so
    downstream code that pattern-matches on it keeps working.
    """
    ts = datetime.now().isoformat()  # includes microseconds
    nonce = secrets.token_hex(4)
    seed = f"{client}-{product}-{avatar}-{ts}-{index}-{nonce}"
    short_hash = hashlib.sha256(seed.encode()).hexdigest()[:6]
    return f"{client}-{product}-{short_hash}"


def _load_competitive_gaps(client_slug: str) -> dict | None:
    """Load competitive-gaps.yaml if it exists. Returns None if missing or empty."""
    from pathlib import Path
    import yaml as _yaml
    path = Path("clients") / client_slug / "research" / "competitive-gaps.yaml"
    if not path.exists():
        return None
    try:
        data = _yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("synthesis"):
            return data
    except Exception:
        return None
    return None


def generate_briefs(
    client_slug: str,
    product: Product,
    brand: Brand,
    avatar: CustomerAvatar,
    count: int = 5,
    platform: str = "meta",
    winning_patterns: WinningPatterns | None = None,
    competitive_gaps: dict | None = None,
    voice: dict | None = None,
    use_profile: bool = True,
    use_voice: bool = True,
    include_trending: bool = True,
    mental_stages: list[MentalStage] | None = None,
) -> list[CreativeBrief]:
    """Generate a set of creative briefs for a product.

    Two layered constraints are applied at angle-generation time:

    1. PSYCHOLOGY PROFILE (Stage 1.5) — when `use_profile=True` (default) and
       the avatar has a `psychology_profile`, the angle multiplier filters
       the diversity matrix by the avatar's dominant heuristics and applies
       hard constraints from the profile. Set `use_profile=False` to bypass —
       useful for before/after comparison or for avatars without a profile.

    2. COMPETITIVE GAP MAP (Stage 5.5) — when `competitive_gaps` is None
       (default), the function auto-loads it from
       clients/<slug>/research/competitive-gaps.yaml if that file exists.
       The synthesis block is injected so at least half of generated angles
       target a specific competitor weakness.

    If `winning_patterns` is provided, the generator will also weight angles
    toward patterns that have historically performed well.
    """
    awareness = classify_awareness(avatar)
    strategy = get_awareness_strategy(awareness)
    frameworks = select_frameworks(awareness, count=4)
    primary_framework = frameworks[0]

    # Build extra context from winning patterns if available
    if winning_patterns and winning_patterns.recommendations:
        strategy = {
            **strategy,
            "approach": strategy["approach"]
            + "\n\nBased on past performance data:\n"
            + "\n".join(f"- {r}" for r in winning_patterns.recommendations[:3]),
        }

    # Auto-load competitive gaps if not passed in
    if competitive_gaps is None:
        competitive_gaps = _load_competitive_gaps(client_slug)

    # Auto-load the brand voice (unspoken-truths bank) if not passed in
    if voice is None:
        from strategy.competitive_context import load_voice
        voice = load_voice(client_slug)

    # Spread the batch across mental stages — biased by the avatar's awareness
    # center of gravity but always covering all four stages when count >= 4.
    # Done here (not inside generate_angles) so brief_generator can stamp the
    # pre-computed stage onto the CreativeBrief as a fallback if the LLM
    # forgets to echo it back.
    #
    # If the caller supplied `mental_stages` explicitly (typical pattern: CLI
    # computes the full N-stage distribution once and slices per avatar so the
    # full output covers all four stages across the avatar fan-out), we use
    # the supplied slice instead. It must be length-matched to `count`.
    if mental_stages is None:
        mental_stages = distribute_across_stages(count, awareness)
    elif len(mental_stages) != count:
        raise ValueError(
            f"mental_stages length ({len(mental_stages)}) must match count ({count})."
        )

    angles = generate_angles(
        product=product,
        avatar=avatar,
        brand=brand,
        awareness_strategy=strategy,
        count=count,
        frameworks=[f.value for f in frameworks],
        competitive_gaps=competitive_gaps,
        use_profile=use_profile,
        mental_stages=mental_stages,
        voice=voice,
        use_voice=use_voice,
    )

    briefs = []
    for i, angle_data in enumerate(angles):
        framework_str = angle_data.get("framework", primary_framework.value)
        try:
            framework = CopyFramework(framework_str.lower())
        except ValueError:
            framework = primary_framework

        # Persona always uses the canonical avatar name (e.g. "Done-Everything
        # Danielle") so handoffs read cleanly. The LLM's free-text persona
        # description goes into persona_traits as supporting thumbnail.
        persona_name = (avatar.name or "").strip() or angle_data.get("persona", "")
        persona_traits = (
            angle_data.get("persona_traits")
            or angle_data.get("persona", "")  # backwards compat for older outputs
            or ""
        )

        # Visual format alternatives — gracefully handle the LLM emitting
        # either a list, a single string, or nothing.
        alt_raw = angle_data.get("visual_format_alternatives", []) or []
        if isinstance(alt_raw, str):
            alt_raw = [alt_raw]
        alternatives = [a for a in alt_raw if isinstance(a, str) and a.strip()]

        # Mental stage: trust the LLM's echoed value if it parses, otherwise
        # fall back to the pre-computed assignment for this index. The
        # pre-computed list is the source of truth in disagreement — the LLM
        # was told which stage to target for this slot.
        raw_stage = (angle_data.get("mental_stage") or "").strip().lower()
        try:
            mental_stage = MentalStage(raw_stage) if raw_stage else mental_stages[i]
        except ValueError:
            mental_stage = mental_stages[i]
        # trigger_moment is only meaningful for trigger-stage briefs. Strip it
        # off the others so a stale LLM field doesn't pollute non-trigger
        # briefs.
        trigger_moment = (
            (angle_data.get("trigger_moment") or "").strip()
            if mental_stage == MentalStage.TRIGGER
            else ""
        )

        brief = CreativeBrief(
            brief_id=_make_brief_id(
                client_slug,
                product.name.lower().replace(" ", "-"),
                i,
                avatar=(avatar.name or "").lower().replace(" ", "-"),
            ),
            client=client_slug,
            product=product.name,
            awareness_level=awareness,
            mental_stage=mental_stage,
            trigger_moment=trigger_moment,
            framework=framework,
            angle=angle_data.get("angle", ""),
            hook=angle_data.get("hook", ""),
            hook_type=angle_data.get("hook_type", ""),
            slot=angle_data.get("slot"),
            hook_source=angle_data.get("source", ""),
            hook_tactic=angle_data.get("hook_tactic", ""),
            persona=persona_name,
            persona_traits=persona_traits,
            creative_mechanic=angle_data.get("creative_mechanic", ""),
            visual_format=angle_data.get("visual_format", ""),
            visual_format_alternatives=alternatives,
            pain_point=angle_data.get("pain_addressed", ""),
            benefit_callouts=_clean_callouts(
                angle_data.get("benefit_callouts"),
                product=product,
                brief_index=i,
            ),
            cta=angle_data.get("cta", strategy.get("cta", "Shop Now")),
            visual_direction=angle_data.get("visual_direction", ""),
            target_platform=platform,
            source_insight="angle_multiplier",
        )
        briefs.append(brief)

    # Trending format recommendations (top 3) per brief — purely
    # informational, attached to each brief. Safe-fails to empty list if the
    # library is missing or LLM call errors. The image generation pipeline
    # ignores this field; it only shows up in the brief notes header and
    # the dashboard.
    if include_trending:
        try:
            from strategy.trending import recommend_trending_formats_for_briefs
            recs_by_id = recommend_trending_formats_for_briefs(briefs)
            for b in briefs:
                b.trending_format_recommendations = recs_by_id.get(b.brief_id, [])
        except Exception:
            for b in briefs:
                b.trending_format_recommendations = []

    return briefs
