"""Map audience to Schwartz awareness levels and select appropriate messaging strategy.

Two layered models live here:

1. Schwartz **awareness levels** (5 stages, unaware → most_aware) describe
   where an *audience* sits — set per avatar, used to pick copy frameworks
   and tone for the brief batch.

2. **Mental stages** (4 stages: trigger / exploration / evaluation / purchase)
   describe where any one *customer's head* is at the moment an ad lands.
   Customers cycle between these stages, so a brief batch should span all
   four — even for a single-awareness-level avatar — to catch the customer
   wherever they happen to be.

The two models are complementary: awareness picks the messaging frame for the
batch, mental stage picks the moment each individual brief targets.
"""

from __future__ import annotations

from models.avatar import CustomerAvatar
from models.brief import AwarenessLevel, CopyFramework, MentalStage

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
        "approach": "They know your product but haven't bought. The decision is "
        "already emotional — give them logical PERMISSION to act on it. Show "
        "people like them who chose this and didn't regret it. Stack proof of "
        "decision confidence (specific outcomes from specific buyers), not "
        "features and not manufactured urgency. Earned reassurance outperforms "
        "countdown timers in this stage; if you need a discount to close, the "
        "upstream creative didn't do its job.",
        "hook_style": "permission-frame, 'people like you' social proof, "
        "specific-outcome story, decision-confidence",
        "tone": "calm, specific, 'this is the obvious choice' energy",
        "cta": "Try It",
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


# ─── Mental stages (Sarah Levener / McKinsey Consumer Decision Journey) ──────
#
# Per-stage briefing rules. The angle multiplier inlines these into the prompt
# scoped to each slot's assigned stage. Keys map 1:1 to MentalStage members.
#
# `approach` is the strategic frame for the LLM. `brief_on` and `avoid` are
# the imperative rules that prevent each stage from collapsing back to product-
# centric copy — the failure mode the framework is built to counter.

MENTAL_STAGE_STRATEGIES: dict[MentalStage, dict[str, str]] = {
    MentalStage.TRIGGER: {
        "approach": "Surface the MOMENT a need becomes conscious, not the "
        "product. Recreate the specific scene — a life event, social "
        "comparison, internal frustration tipping over, or external "
        "disruption — that flips a passive viewer into someone actively "
        "looking for a solution. The hook IS the trigger event. The product "
        "either does not appear or appears as a quiet fade-in at the end.",
        "brief_on": "ONE specific trigger_event from the avatar, anchored "
        "verbatim. Recreate that scene visually and in the hook. Stamp the "
        "chosen event into the trigger_moment field.",
        "avoid": "Product hero shots. Generic 'tired of X?' openers. "
        "Mechanism explanations. Social proof. Discounts. CTAs that say "
        "'Buy' or 'Shop'.",
    },
    MentalStage.EXPLORATION: {
        "approach": "Speak to the CATEGORY, not the product. The customer "
        "knows they have a need and is forming a mental picture of what "
        "'good' looks like in this space. Teach them what to look for and "
        "what to avoid. Position the brand as 'the people who get it,' not "
        "'the product to buy.' If the ad would still make sense with a "
        "competitor's product swapped in, you've nailed the exploration "
        "frame — downstream conversion improves because by evaluation time "
        "the customer's picture of the right solution already looks like "
        "your brand.",
        "brief_on": "Category-level education. Mechanism explanations that "
        "apply to all good options (yours happens to qualify). Buying "
        "guides, what-to-look-for content, common-mistakes content. Product "
        "as background, not hero.",
        "avoid": "Feature lists. Direct competitor comparisons. Urgency. "
        "'Buy now' CTAs. Anything that pushes toward a single product "
        "decision before they're done shaping their preferences.",
    },
    MentalStage.EVALUATION: {
        "approach": "The customer has a shortlist and is actively comparing. "
        "They want PERMISSION to choose — a logical reason to act on an "
        "emotional decision they've mostly already made. They're scanning "
        "for risk. Social proof works at this stage because seeing someone "
        "like them make this choice makes the choice feel safe. Compete on "
        "CERTAINTY, not features. 'Here's why people like you chose this "
        "and didn't regret it.'",
        "brief_on": "Decision-confidence framing. Specific outcomes from "
        "specific buyers (not aggregate review counts). Mechanism that "
        "justifies the feeling. Reasons not to second-guess. Risk reducers "
        "that make the choice feel obvious.",
        "avoid": "Feature dumps. Manufactured urgency or scarcity. "
        "Discount-led hooks. Anything that re-opens a decision the customer "
        "has mostly closed — that just resets them to exploration.",
    },
    MentalStage.PURCHASE: {
        "approach": "The psychological decision is made. Remove friction. "
        "The brain is now looking for reasons NOT to expend energy — "
        "pre-empt them with guarantees, easy returns, low-risk first steps. "
        "Discounts here are a final nudge, not a substitute for conviction; "
        "if you have to discount heavily to close, the trigger / exploration "
        "/ evaluation creative didn't do its job and you're wallpapering "
        "over a deeper gap.",
        "brief_on": "Guarantee. Easy return / cancel. Shipping speed. "
        "Low-commitment first step (single bottle, 30-day money back). "
        "Final-mile objection handlers. Direct CTA.",
        "avoid": "Heavy discounts as the lead. Re-explaining the value "
        "prop. Anything that re-opens the decision rather than closes it.",
    },
}


# Each Schwartz awareness level has a primary mental stage — the customer's
# *center of gravity*. Used by `distribute_across_stages` to bias extra briefs
# in a large batch toward the stage this avatar spends most time in, while
# still always covering all four.
_AWARENESS_TO_MENTAL_STAGE: dict[AwarenessLevel, MentalStage] = {
    AwarenessLevel.UNAWARE: MentalStage.TRIGGER,
    AwarenessLevel.PROBLEM_AWARE: MentalStage.EXPLORATION,
    AwarenessLevel.SOLUTION_AWARE: MentalStage.EVALUATION,
    AwarenessLevel.PRODUCT_AWARE: MentalStage.EVALUATION,
    AwarenessLevel.MOST_AWARE: MentalStage.PURCHASE,
}


def get_mental_stage_strategy(stage: MentalStage) -> dict[str, str]:
    """Return the briefing strategy for a single mental stage."""
    return MENTAL_STAGE_STRATEGIES[stage]


def primary_mental_stage(awareness: AwarenessLevel) -> MentalStage:
    """The mental stage this avatar's awareness level maps to most naturally."""
    return _AWARENESS_TO_MENTAL_STAGE.get(awareness, MentalStage.EXPLORATION)


def distribute_across_stages(
    count: int,
    avatar_awareness: AwarenessLevel,
) -> list[MentalStage]:
    """Spread `count` briefs across the four mental stages.

    Behaviour by batch size:

    - **count = 1** → just the avatar's primary stage. A single brief should
      target the customer's center of gravity, not blindly the top of the
      funnel. (Critical for callers like the CLI that fan briefs out at
      1-per-avatar — without this, every avatar would always get a trigger
      brief regardless of awareness.)
    - **count = 2–3** → walk funnel order, but guarantee the avatar's primary
      stage is included (swapped into the last slot if it would otherwise
      fall off the slice).
    - **count = 4** → all four stages in funnel order.
    - **count > 4** → all four, then extras cycle through
      [primary, exploration, trigger, primary] — biases the gap stages
      (upper funnel) most brands underindex on.

    Returns a list of length exactly `count`.
    """
    if count <= 0:
        return []

    stages = [
        MentalStage.TRIGGER,
        MentalStage.EXPLORATION,
        MentalStage.EVALUATION,
        MentalStage.PURCHASE,
    ]
    primary = primary_mental_stage(avatar_awareness)

    if count == 1:
        return [primary]

    if count <= 4:
        slice_ = list(stages[:count])
        if primary not in slice_:
            slice_[-1] = primary
        return slice_

    result = list(stages)
    extras = [primary, MentalStage.EXPLORATION, MentalStage.TRIGGER, primary]
    for i in range(count - 4):
        result.append(extras[i % len(extras)])
    return result
