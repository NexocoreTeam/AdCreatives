"""Map audience to Schwartz awareness levels and select appropriate messaging strategy."""

from __future__ import annotations

from models.avatar import CustomerAvatar
from models.brief import AwarenessLevel, CopyFramework

# Mapping: awareness level → best copy frameworks and messaging approach
AWARENESS_STRATEGIES: dict[AwarenessLevel, dict] = {
    AwarenessLevel.UNAWARE: {
        "frameworks": [CopyFramework.PAS, CopyFramework.AIDA],
        "approach": "Lead with a pattern interrupt. Don't mention the product yet. "
        "Start with a shocking stat, provocative question, or relatable scenario "
        "that makes them realize they have a problem they didn't know about.",
        "hook_style": "shock-stat, provocative-question, story-opener",
        "tone": "educational, eye-opening, 'did you know' energy",
        "cta": "Learn More",
    },
    AwarenessLevel.PROBLEM_AWARE: {
        "frameworks": [CopyFramework.PAS, CopyFramework.BAB, CopyFramework.PASTOR],
        "approach": "Agitate the pain they already feel. Use their exact language. "
        "Show you understand their frustration deeply before introducing any solution. "
        "The hook should make them feel seen.",
        "hook_style": "pain-number, empathy-hook, 'tired of X' question",
        "tone": "empathetic, validating, 'I've been there' energy",
        "cta": "See How",
    },
    AwarenessLevel.SOLUTION_AWARE: {
        "frameworks": [CopyFramework.FAB, CopyFramework.FOUR_CS, CopyFramework.QUEST],
        "approach": "They know solutions exist but haven't picked yours. "
        "Differentiate through the unique mechanism — WHY your approach works "
        "when others don't. Lead with the benefit, back with proof.",
        "hook_style": "differentiator, 'unlike other X' comparison, mechanism-reveal",
        "tone": "confident, specific, proof-driven",
        "cta": "Try It Free",
    },
    AwarenessLevel.PRODUCT_AWARE: {
        "frameworks": [CopyFramework.FAB, CopyFramework.SLAP],
        "approach": "They know your product but haven't bought. Overcome specific "
        "objections, stack social proof, create urgency. Focus on removing "
        "the last barrier to purchase.",
        "hook_style": "social-proof, objection-crusher, scarcity-urgency",
        "tone": "direct, proof-heavy, confident",
        "cta": "Get Started",
    },
    AwarenessLevel.MOST_AWARE: {
        "frameworks": [CopyFramework.SLAP, CopyFramework.AIDA],
        "approach": "They're ready to buy — just need a nudge. Lead with the offer: "
        "discount, bonus, limited time, or new feature. Minimal persuasion needed. "
        "Make the CTA impossible to ignore.",
        "hook_style": "offer-lead, discount, new-feature",
        "tone": "direct, urgent, deal-focused",
        "cta": "Shop Now",
    },
}


def get_awareness_strategy(level: AwarenessLevel) -> dict:
    """Get the full messaging strategy for an awareness level."""
    return AWARENESS_STRATEGIES[level]


def classify_awareness(avatar: CustomerAvatar) -> AwarenessLevel:
    """Classify awareness level from avatar data."""
    level_str = avatar.awareness_level.lower().strip()
    for level in AwarenessLevel:
        if level.value == level_str:
            return level
    return AwarenessLevel.PROBLEM_AWARE  # Safe default


def select_frameworks(
    level: AwarenessLevel,
    count: int = 2,
) -> list[CopyFramework]:
    """Select the best copy frameworks for an awareness level."""
    strategy = AWARENESS_STRATEGIES[level]
    frameworks = strategy["frameworks"]
    return frameworks[:count]
