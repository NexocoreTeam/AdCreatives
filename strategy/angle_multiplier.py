"""Generate multiple messaging angles from a single product/avatar combination.

Uses four layered skills as system context (loaded from prompts/skills/):
- hook-methodology (DV0x): research-first hook extraction
- hook-formulas (DV0x): 10 hook types with psychology and structure
- motion/creative-strategy-engine (Motion): pain × persona × awareness matrix
- motion/hook-tactics (Motion): 35+ tactical hook formats
- motion/hook-writing (Motion): psychologically driven hook composition
- motion/hook-voice-patterns (Motion): native-feed voice swipe file

The diversity matrix enforces one hook per emotional trigger; Motion's strategic
framework anchors the *what* (pain × persona); the hook libraries supply the *how*.
"""

from __future__ import annotations

import yaml

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.product import Product
from models.skills import load_skill
from strategy.llm import claude_complete

# Diversity matrix — adapted from DV0x/creative-ad-agent's hook-methodology.
# Each slot covers a different emotional trigger so the generated set varies
# meaningfully across cognitive levers, not just surface phrasing.
DIVERSITY_MATRIX = [
    {"slot": 1, "hook_type": "Surprising Stat", "trigger": "Social Proof / Credibility"},
    {"slot": 2, "hook_type": "Story / Result", "trigger": "Empathy + Relief"},
    {"slot": 3, "hook_type": "FOMO / Urgency", "trigger": "Loss Aversion"},
    {"slot": 4, "hook_type": "Curiosity Gap", "trigger": "Intrigue"},
    {"slot": 5, "hook_type": "Direct Address / Call-out", "trigger": "Recognition"},
    {"slot": 6, "hook_type": "Contrast / Enemy", "trigger": "Differentiation"},
    {"slot": 7, "hook_type": "Question", "trigger": "Self-reference"},
    {"slot": 8, "hook_type": "Pattern Interrupt", "trigger": "Pattern break"},
    {"slot": 9, "hook_type": "Controversial", "trigger": "Polarization"},
    {"slot": 10, "hook_type": "Problem-Solution", "trigger": "Pain → relief"},
]


def _diversity_matrix_text(count: int) -> str:
    """Format the first N slots of the diversity matrix as a readable list."""
    rows = [
        f"  Slot {row['slot']}: {row['hook_type']} ({row['trigger']})"
        for row in DIVERSITY_MATRIX[:count]
    ]
    return "\n".join(rows)


ANGLE_SYSTEM = """You are a direct response advertising strategist trained by the best:
Eugene Schwartz, Gary Halbert, David Ogilvy, and modern performance marketers.

Your job is to generate MULTIPLE distinct messaging angles for the same product.
Each angle attacks a different pain × persona intersection, occupies a DIFFERENT
slot in the diversity matrix below (no hook_type repeats), uses a different
copy framework, and selects a different creative mechanic + visual format.

Rules:
- Every hook is traceable to a specific source in the avatar/product data
- Each angle must be genuinely different — not just rewording the same idea
- Use the customer's actual language from the avatar data (pain, desires, money quotes)
- Be specific with numbers, timeframes, and outcomes
- Sound human, not corporate. Write like a person talking to a friend.
- Every hook must stop the scroll in under 2 seconds of reading
- Match the tone to the awareness level

You operate under SIX layered skills below. Use them together:

--- HOOK METHODOLOGY (DV0x) ---

""" + load_skill("hook-methodology") + """

--- HOOK FORMULAS (DV0x) ---

""" + load_skill("hook-formulas") + """

--- CREATIVE STRATEGY ENGINE (Motion) ---

""" + load_skill("motion/creative-strategy-engine") + """

--- HOOK TACTICS (Motion, 35+ tactics) ---

""" + load_skill("motion/hook-tactics") + """

--- HOOK WRITING (Motion) ---

""" + load_skill("motion/hook-writing") + """

--- HOOK VOICE PATTERNS (Motion, native-feed swipe file) ---

""" + load_skill("motion/hook-voice-patterns") + """

---

Output valid YAML only, no markdown fences."""

ANGLE_PROMPT = """Generate {count} distinct messaging angles for this product, one per
diversity slot. Do not repeat hook_type across slots. Vary the framework across
slots — do not pick one framework and apply it to all angles.

DIVERSITY MATRIX (use these hook types in this order):
{diversity_matrix}

AVAILABLE FRAMEWORKS (pick one per slot, vary across the set):
{frameworks}

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
  - slot: <integer matching the diversity matrix>
    hook_type: "exact hook type from the matrix"
    hook_tactic: "specific tactic from Motion's 35+ hook-tactics (e.g. 'Specific stat with a story', 'Pattern interrupt with a confession')"
    angle: "brief description of the angle (e.g., 'time savings for busy parents')"
    hook: "the actual scroll-stopping hook text"
    source: "which research element this hook came from (pain X, benefit Y, quote Z)"
    pain_addressed: "which pain point this targets"
    persona: "which persona segment this targets (from creative-strategy-engine pain × persona mapping)"
    awareness_stage: "unaware | problem_aware | solution_aware | product_aware | most_aware"
    framework: "one of the frameworks above — pick the best fit for this slot"
    creative_mechanic: "name a structural mechanic from Motion's creative-mechanics that fits this angle (e.g. 'Pattern Interrupt with Reveal', 'Before/After Split', 'Talking Head Confession')"
    visual_format: "name a visual format from Motion's visual-formats library that fits this concept (e.g. 'UGC Static', 'Split-screen video', 'Text-on-product photo')"
    benefit_callouts:
      - "Short punchy callout 1"
      - "Short punchy callout 2"
      - "Short punchy callout 3"
    cta: "Call to action text"
    visual_direction: "What the image should convey to support this angle"
    why_it_works: "1-sentence explanation of the psychological trigger"

Quality checks before returning:
1. Every hook must be traceable to a specific research element via `source`.
2. Frameworks vary across slots — no repeats.
3. Creative mechanics vary across slots — no repeats.
4. Visual formats vary across slots when possible.
5. Hooks read like real human language, not ad copy."""


def generate_angles(
    product: Product,
    avatar: CustomerAvatar,
    brand: Brand,
    awareness_strategy: dict,
    count: int = 6,
    frameworks: list[str] | None = None,
) -> list[dict]:
    """Generate multiple messaging angles for a product/avatar combo.

    Default count is 6 to fill the first six slots of the diversity matrix
    (Stat, Story, FOMO, Curiosity, Call-out, Contrast/Enemy) — the same set
    DV0x's creative-ad-agent uses for one campaign.

    `frameworks` is a list of CopyFramework values (e.g. ["pas", "bab", "fab"]);
    the model is instructed to vary the framework across slots. Defaults to a
    sensible set covering most awareness levels.
    """
    if count > len(DIVERSITY_MATRIX):
        raise ValueError(
            f"count={count} exceeds diversity matrix size ({len(DIVERSITY_MATRIX)}). "
            "Extend DIVERSITY_MATRIX or request fewer angles."
        )

    if not frameworks:
        frameworks = ["pas", "aida", "bab", "fab"]

    pain_summary = "\n".join(
        f"  - [{p.intensity}] {p.pain}: {', '.join(p.customer_language[:2])}"
        for p in avatar.pain_points[:5]
    )
    desire_summary = "\n".join(
        f"  - {d.desire}: {', '.join(d.customer_language[:2])}"
        for d in avatar.desires[:3]
    )
    frameworks_text = "\n".join(f"  - {f}" for f in frameworks)

    prompt = ANGLE_PROMPT.format(
        count=count,
        diversity_matrix=_diversity_matrix_text(count),
        frameworks=frameworks_text,
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
    )

    result = claude_complete(prompt, system=ANGLE_SYSTEM)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    parsed = yaml.safe_load(result)
    return parsed.get("angles", [])
