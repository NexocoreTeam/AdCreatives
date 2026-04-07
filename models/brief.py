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
