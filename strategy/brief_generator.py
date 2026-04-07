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


def generate_briefs(
    client_slug: str,
    product: Product,
    brand: Brand,
    avatar: CustomerAvatar,
    count: int = 5,
    platform: str = "meta",
    winning_patterns: WinningPatterns | None = None,
) -> list[CreativeBrief]:
    """Generate a set of creative briefs for a product.

    If winning_patterns is provided, the generator will weight angles
    toward patterns that have historically performed well.
    """
    awareness = classify_awareness(avatar)
    strategy = get_awareness_strategy(awareness)
    frameworks = select_frameworks(awareness, count=2)
    primary_framework = frameworks[0]

    # Build extra context from winning patterns if available
    if winning_patterns and winning_patterns.recommendations:
        strategy = {
            **strategy,
            "approach": strategy["approach"]
            + "\n\nBased on past performance data:\n"
            + "\n".join(f"- {r}" for r in winning_patterns.recommendations[:3]),
        }

    angles = generate_angles(
        product=product,
        avatar=avatar,
        brand=brand,
        awareness_strategy=strategy,
        count=count,
        framework=primary_framework.value,
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
            pain_point=angle_data.get("pain_addressed", ""),
            benefit_callouts=angle_data.get("benefit_callouts", product.benefits[:3]),
            cta=angle_data.get("cta", strategy.get("cta", "Shop Now")),
            visual_direction=angle_data.get("visual_direction", ""),
            target_platform=platform,
            source_insight="angle_multiplier",
        )
        briefs.append(brief)

    return briefs
