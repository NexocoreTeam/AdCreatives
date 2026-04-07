"""Creative matrix generator — systematic combinatorial testing."""

from __future__ import annotations

import itertools
from dataclasses import dataclass

from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.product import Product


@dataclass
class MatrixDimension:
    name: str
    values: list[str]


@dataclass
class MatrixConfig:
    hooks: list[str]
    styles: list[str]
    color_variants: list[str] | None = None
    frameworks: list[str] | None = None
    platforms: list[str] | None = None


def build_matrix(config: MatrixConfig) -> list[dict]:
    """Generate all combinations from the matrix dimensions."""
    dimensions = {"hook": config.hooks, "style": config.styles}

    if config.color_variants:
        dimensions["color_variant"] = config.color_variants
    if config.frameworks:
        dimensions["framework"] = config.frameworks
    if config.platforms:
        dimensions["platform"] = config.platforms

    keys = list(dimensions.keys())
    values = list(dimensions.values())
    combinations = list(itertools.product(*values))

    return [dict(zip(keys, combo)) for combo in combinations]


def matrix_to_briefs(
    matrix: list[dict],
    client_slug: str,
    product: Product,
    brand: Brand,
    awareness_level: AwarenessLevel = AwarenessLevel.PROBLEM_AWARE,
) -> list[CreativeBrief]:
    """Convert matrix combinations into creative briefs."""
    briefs = []
    for i, combo in enumerate(matrix):
        framework_str = combo.get("framework", "pas")
        try:
            framework = CopyFramework(framework_str.lower())
        except ValueError:
            framework = CopyFramework.PAS

        brief = CreativeBrief(
            brief_id=f"{client_slug}-matrix-{i:03d}",
            client=client_slug,
            product=product.name,
            awareness_level=awareness_level,
            framework=framework,
            angle=combo.get("hook", ""),
            hook=combo.get("hook", ""),
            benefit_callouts=product.benefits[:3],
            cta="Shop Now",
            visual_direction=f"Style: {combo.get('style', 'default')}",
            target_platform=combo.get("platform", "meta"),
            source_insight="matrix_test",
        )
        briefs.append(brief)

    return briefs


def estimate_matrix_cost(
    matrix: list[dict],
    cost_per_image: float = 0.05,
    sizes_per_image: int = 2,
) -> dict:
    """Estimate generation cost for a matrix."""
    total_combos = len(matrix)
    total_images = total_combos * sizes_per_image
    total_cost = total_images * cost_per_image

    return {
        "combinations": total_combos,
        "total_images": total_images,
        "estimated_cost": f"${total_cost:.2f}",
        "cost_per_image": f"${cost_per_image:.3f}",
    }
