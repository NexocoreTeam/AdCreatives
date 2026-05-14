from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AwarenessLevel(str, Enum):
    UNAWARE = "unaware"
    PROBLEM_AWARE = "problem_aware"
    SOLUTION_AWARE = "solution_aware"
    PRODUCT_AWARE = "product_aware"
    MOST_AWARE = "most_aware"


class CopyFramework(str, Enum):
    PAS = "pas"               # Problem - Agitation - Solution
    AIDA = "aida"             # Attention - Interest - Desire - Action
    BAB = "bab"               # Before - After - Bridge
    FAB = "fab"               # Features - Advantages - Benefits
    FOUR_CS = "four_cs"       # Clear - Concise - Compelling - Credible
    QUEST = "quest"           # Qualify - Understand - Educate - Stimulate - Transition
    PASTOR = "pastor"         # Problem - Amplify - Story - Testimony - Offer - Response
    SLAP = "slap"             # Stop - Look - Act - Purchase


class CreativeBrief(BaseModel):
    """A complete creative brief that drives both copy and visual generation."""

    brief_id: str = Field(description="Unique identifier for this brief")
    client: str = Field(description="Client slug")
    product: str = Field(description="Product slug")
    awareness_level: AwarenessLevel = Field(
        description="Target audience awareness level — drives messaging tone"
    )
    framework: CopyFramework = Field(
        description="Copy framework used to structure the message"
    )
    angle: str = Field(
        description="The specific messaging angle, e.g. 'time savings for busy parents'"
    )
    hook: str = Field(
        description="The opening hook / headline that stops the scroll"
    )
    hook_type: str = Field(
        default="",
        description="Diversity matrix hook type: Surprising Stat, Story / Result, "
        "FOMO / Urgency, Curiosity Gap, Direct Address / Call-out, Contrast / Enemy, "
        "Question, Pattern Interrupt, Controversial, Problem-Solution",
    )
    slot: int | None = Field(
        default=None,
        description="Slot in the diversity matrix (1-10) — used to verify the brief "
        "set covers distinct emotional triggers",
    )
    hook_source: str = Field(
        default="",
        description="Which research element this hook came from (pain X, benefit Y, "
        "verbatim quote Z). Enforces the research-first methodology.",
    )
    hook_tactic: str = Field(
        default="",
        description="Specific tactic from Motion's hook-tactics library "
        "(e.g. 'Specific stat with a story', 'Pattern interrupt with a confession')",
    )
    persona: str = Field(
        default="",
        description="Persona segment this brief targets (from Motion's "
        "creative-strategy-engine pain × persona mapping)",
    )
    creative_mechanic: str = Field(
        default="",
        description="Structural mechanic from Motion's creative-mechanics library "
        "(e.g. 'Pattern Interrupt with Reveal', 'Before/After Split')",
    )
    visual_format: str = Field(
        default="",
        description="Primary visual format from Motion's visual-formats library "
        "(e.g. 'UGC Static', 'Split-screen video', 'Text-on-product photo')",
    )
    visual_format_alternatives: list[str] = Field(
        default_factory=list,
        description="2-3 alternate visual formats that could also execute this "
        "brief's mechanic. Used for variance testing — the brief's psychological "
        "lever stays the same, only the shoot format changes.",
    )
    persona_traits: str = Field(
        default="",
        description="One-sentence elaboration of the persona this brief targets — "
        "kept separately from the canonical `persona` name so handoffs read "
        "cleanly ('Done-Everything Danielle' is the name; this field gives the "
        "buyer thumbnail).",
    )
    pain_point: str = Field(
        default="",
        description="The specific pain being addressed (in customer language)",
    )
    benefit_callouts: list[str] = Field(
        default_factory=list,
        description="2-4 benefit callouts for the ad (short, punchy)",
    )
    cta: str = Field(
        default="Shop Now", description="Call to action text"
    )
    body_copy: str = Field(
        default="",
        description="Optional longer body copy (for text-heavy formats)",
    )
    visual_direction: str = Field(
        default="",
        description="Description of what the image should convey emotionally/visually",
    )
    tone_override: str = Field(
        default="",
        description="Override the brand's default tone for this specific ad",
    )
    target_platform: str = Field(
        default="meta",
        description="Primary platform this brief targets (affects style modifiers)",
    )
    source_insight: str = Field(
        default="",
        description="What inspired this brief: 'voc_mining', 'competitor_analysis', "
        "'winning_pattern', 'manual'",
    )
