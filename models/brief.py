from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class TextOverlay(BaseModel):
    """One overlay entry for the brief-driven UGC layout pipeline.

    Used by `adc ugc-ad --brief <path>` (or `--layout` registry entries) to
    drive the PIL renderer. Coordinates are expressed as fractions of frame
    dimensions so layouts work across any aspect ratio.

    `text` may include `\\n` for multi-line caption boxes.
    `emoji` is optional and renders to the right of the text via the
    brand's `ugc_voice.emoji_font_fallback` font.
    """

    text: str = Field(description="Caption text. Use \\n for line breaks.")
    y_pct: float = Field(
        ge=0.0,
        le=1.0,
        description="Vertical position of the box's top edge as fraction of "
        "frame height (0.0 = top, 1.0 = bottom)",
    )
    font_size_pct: float = Field(
        gt=0.0,
        le=20.0,
        description="Text height as percent of frame height (~2.0-3.0 is "
        "native social-feed scale).",
    )
    kind: Literal["box", "pill"] = Field(
        default="box",
        description="'box' = solid caption rectangle. 'pill' = fully-rounded "
        "highlight pill in the brand's marigold/coral accent.",
    )
    emoji: str | None = Field(
        default=None,
        description="Optional emoji glyph to render to the right of the text "
        "(e.g. '💀', '✅').",
    )


class AwarenessLevel(str, Enum):
    UNAWARE = "unaware"
    PROBLEM_AWARE = "problem_aware"
    SOLUTION_AWARE = "solution_aware"
    PRODUCT_AWARE = "product_aware"
    MOST_AWARE = "most_aware"


class MentalStage(str, Enum):
    """Customer mental state when an ad lands — orthogonal to Schwartz awareness.

    Schwartz puts an *audience* at one awareness level; MentalStage tracks
    where any one customer's head is in the buying decision *right now*.
    Customers cycle between these stages, stall, re-enter. A batch of briefs
    should span all four so the creative reaches the right moment whoever the
    impression lands on.

    TRIGGER     — a need just became conscious. Lead with the moment, not the
                  product.
    EXPLORATION — knows they have a need, exploring the CATEGORY (not your
                  product yet). Brand sits in the background; the ad teaches
                  what good looks like.
    EVALUATION  — shortlist phase. They want PERMISSION to choose, not more
                  features. Compete on certainty.
    PURCHASE    — decision already made. Remove friction. Discounts here are
                  a crutch if the upstream stages didn't do their job.
    """

    TRIGGER = "trigger"
    EXPLORATION = "exploration"
    EVALUATION = "evaluation"
    PURCHASE = "purchase"


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
    mental_stage: MentalStage = Field(
        default=MentalStage.EXPLORATION,
        description="Customer mental state when this ad lands (trigger / "
        "exploration / evaluation / purchase). Briefs in a batch should span "
        "all four so creative meets customers wherever they happen to be in "
        "their decision journey, not just at the avatar's center of gravity.",
    )
    trigger_moment: str = Field(
        default="",
        description="For trigger-stage briefs only: the specific recognition "
        "moment this ad recreates, sourced verbatim or near-verbatim from "
        "avatar.trigger_events (e.g. 'finishes another probiotic bottle and "
        "realizes she feels exactly the same'). Empty for non-trigger briefs.",
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
    campaign_name: str = Field(
        default="",
        description="Meta ad campaign name built via strategy/naming.py. "
        "Format: [Brand]_[Persona]_[Angle]_[Format]_[Style]_[Source]_[Hook]_"
        "[Copy]_[Offer]_[Iteration]_[Date] — e.g. "
        "'SK_ProbioticBurnedPaige_Testimonial_UGC_Venn_Remix_H22_C00_NONE_V1_260515'. "
        "Empty for briefs generated before naming integration; populated for "
        "every new brief via remix / generate flows.",
    )
    trending_format_recommendations: list[dict] = Field(
        default_factory=list,
        description="Top 3 trending ad format recommendations from "
        "trending_formats.yaml, scored against this brief's persona, "
        "awareness, and angle by strategy/trending.py. Each entry: "
        "{format_id, name, summary, format_type, production_complexity, "
        "rank, rationale, production_notes}. Informational only — "
        "suggests alternative video/static executions to try alongside the "
        "primary ad. Empty if recommendation was skipped or unavailable.",
    )
    text_layout: list[TextOverlay] | None = Field(
        default=None,
        description="Optional PIL overlay layout for the hybrid UGC pipeline "
        "(hf-web base photo + PIL caption overlay). When set, `adc ugc-ad "
        "--brief <path>` uses this instead of a layout-registry key. Each "
        "entry positions a caption box or pill at a fractional y position "
        "with a font size relative to frame height.",
    )
    source_matrix_row: str | None = Field(
        default=None,
        description="ID of the creative-matrix row this brief was derived from "
        "(e.g. 'pain-010'). Used by validators/brief_text_validator.py to "
        "detect cross-concept text leakage. Set to None or 'new' for briefs "
        "with no matrix lineage.",
    )
