"""Generate multiple messaging angles from a single product/avatar combination."""

from __future__ import annotations

import yaml

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.product import Product
from strategy.llm import claude_complete

ANGLE_SYSTEM = """You are a direct response advertising strategist trained by the best:
Eugene Schwartz, Gary Halbert, David Ogilvy, and modern performance marketers.

Your job is to generate MULTIPLE distinct messaging angles for the same product.
Each angle attacks a different pain point, desire, or emotional trigger.

Rules:
- Each angle must be genuinely different — not just rewording the same idea
- Use the customer's actual language from the avatar data (pain points, desires)
- Be specific with numbers, timeframes, and outcomes
- Sound human, not corporate. Write like a person talking to a friend.
- Every hook must stop the scroll in under 2 seconds of reading
- Match the tone to the awareness level

Output valid YAML only, no markdown fences."""

ANGLE_PROMPT = """Generate {count} distinct messaging angles for this product.

PRODUCT:
  Name: {product_name}
  Description: {product_description}
  Key Benefits: {benefits}
  Unique Mechanism: {mechanism}
  Social Proof: {social_proof}

CUSTOMER AVATAR:
  Demographic: {demographic}
  Top Pain Points: {pain_points}
  Desires: {desires}
  Objections: {objections}
  Awareness Level: {awareness_level}
  How They Talk: {language_patterns}

BRAND TONE: {brand_tone}
MESSAGING APPROACH: {approach}

For each angle, return:

angles:
  - angle: "brief description of the angle (e.g., 'time savings for busy parents')"
    hook: "the actual scroll-stopping hook text"
    pain_addressed: "which pain point this targets"
    framework: "{framework}"
    benefit_callouts:
      - "Short punchy callout 1"
      - "Short punchy callout 2"
      - "Short punchy callout 3"
    cta: "Call to action text"
    visual_direction: "What the image should convey to support this angle"
    why_it_works: "1-sentence explanation of the psychological trigger"

Make each angle attack a DIFFERENT pain point or desire. Vary the hooks between
questions, stats, empathy statements, and provocative claims."""


def generate_angles(
    product: Product,
    avatar: CustomerAvatar,
    brand: Brand,
    awareness_strategy: dict,
    count: int = 5,
    framework: str = "pas",
) -> list[dict]:
    """Generate multiple messaging angles for a product/avatar combo."""
    pain_summary = "\n".join(
        f"  - [{p.intensity}] {p.pain}: {', '.join(p.customer_language[:2])}"
        for p in avatar.pain_points[:5]
    )
    desire_summary = "\n".join(
        f"  - {d.desire}: {', '.join(d.customer_language[:2])}"
        for d in avatar.desires[:3]
    )

    prompt = ANGLE_PROMPT.format(
        count=count,
        product_name=product.name,
        product_description=product.description,
        benefits=", ".join(product.benefits[:5]),
        mechanism=product.unique_mechanism or "Not specified",
        social_proof=", ".join(product.social_proof[:3]) or "None provided",
        demographic=avatar.demographic,
        pain_points=pain_summary or "Not specified",
        desires=desire_summary or "Not specified",
        objections=", ".join(avatar.objections[:3]) or "Not specified",
        awareness_level=avatar.awareness_level,
        language_patterns=", ".join(avatar.language_patterns[:3]) or "casual and direct",
        brand_tone=brand.tone,
        approach=awareness_strategy.get("approach", ""),
        framework=framework,
    )

    result = claude_complete(prompt, system=ANGLE_SYSTEM)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    parsed = yaml.safe_load(result)
    return parsed.get("angles", [])
