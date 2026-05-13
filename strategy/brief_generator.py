"""Assemble complete creative briefs from strategy components."""

from __future__ import annotations

import hashlib
from datetime import date

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.product import Product
from models.result import WinningPatterns
from strategy.angle_multiplier import generate_angles
from strategy.awareness_mapper import (
    classify_awareness,
    get_awareness_strategy,
    select_frameworks,
)


def _make_brief_id(client: str, product: str, index: int) -> str:
    """Generate a short unique brief ID."""
    seed = f"{client}-{product}-{date.today().isoformat()}-{index}"
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
    use_profile: bool = True,
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

    angles = generate_angles(
        product=product,
        avatar=avatar,
        brand=brand,
        awareness_strategy=strategy,
        count=count,
        frameworks=[f.value for f in frameworks],
        competitive_gaps=competitive_gaps,
        use_profile=use_profile,
    )

    briefs = []
    for i, angle_data in enumerate(angles):
        framework_str = angle_data.get("framework", primary_framework.value)
        try:
            framework = CopyFramework(framework_str.lower())
        except ValueError:
            framework = primary_framework

        brief = CreativeBrief(
            brief_id=_make_brief_id(client_slug, product.name.lower().replace(" ", "-"), i),
            client=client_slug,
            product=product.name,
            awareness_level=awareness,
            framework=framework,
            angle=angle_data.get("angle", ""),
            hook=angle_data.get("hook", ""),
            hook_type=angle_data.get("hook_type", ""),
            slot=angle_data.get("slot"),
            hook_source=angle_data.get("source", ""),
            hook_tactic=angle_data.get("hook_tactic", ""),
            persona=angle_data.get("persona", ""),
            creative_mechanic=angle_data.get("creative_mechanic", ""),
            visual_format=angle_data.get("visual_format", ""),
            pain_point=angle_data.get("pain_addressed", ""),
            benefit_callouts=angle_data.get("benefit_callouts", product.benefits[:3]),
            cta=angle_data.get("cta", strategy.get("cta", "Shop Now")),
            visual_direction=angle_data.get("visual_direction", ""),
            target_platform=platform,
            source_insight="angle_multiplier",
        )
        briefs.append(brief)

    return briefs
