from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


HEURISTIC_NAMES: frozenset[str] = frozenset({
    "scarcity",
    "social_proof",
    "authority_bias",
    "effect_heuristic",
    "processing_fluency",
    "temporal_discounting",
    "salience_bias",
    "goal_gradient",
    "framing_effect",
})

PAIRING_NAMES: frozenset[str] = frozenset({
    "first_principles_plus_loss_aversion",
    "status_signaling_plus_open_loop",
    "curiosity_plus_reverse_psychology",
    "shock_factor_plus_transformation_shortcut",
    "tribal_belonging_plus_vulnerability",
    "pattern_disruption_plus_hidden_truth",
    "what_if_scenario_plus_pain_amplification",
    "contrast_plus_aspirational_identity",
    "gamification_plus_time_sensitive_offer",
    "anonymity_plus_social_proof",
    "authority_borrowing_plus_data_insight",
    "micro_story_plus_suspense",
    "counterintuitive_insight_plus_specificity",
    "reframing_perception_plus_emotional_trigger",
})

CONFIDENCE_LEVELS: frozenset[str] = frozenset({"high", "medium", "low"})


class PainPoint(BaseModel):
    pain: str = Field(description="The core pain or frustration")
    intensity: str = Field(
        default="medium", description="How strongly they feel this: low, medium, high"
    )
    customer_language: list[str] = Field(
        default_factory=list,
        description="Exact phrases customers use to describe this pain "
        "(from reviews, Reddit, forums)",
    )
    source: str = Field(
        default="", description="Where this was found: 'amazon_reviews', 'reddit', 'interview'"
    )


class Desire(BaseModel):
    desire: str = Field(description="What they want to achieve or feel")
    customer_language: list[str] = Field(
        default_factory=list,
        description="Exact phrases customers use to describe this desire",
    )


class CustomerAvatar(BaseModel):
    """Deep customer avatar built from product data + VOC mining."""

    name: str = Field(
        default="",
        description="Avatar persona name for reference, e.g. 'Busy Professional Sarah'",
    )
    demographic: str = Field(
        description="Demographic summary, e.g. 'Women 28-38, urban, dual income household'"
    )
    psychographic: str = Field(
        default="",
        description="Values, beliefs, lifestyle, e.g. 'values efficiency, health-conscious, "
        "skeptical of hype'",
    )
    pain_points: list[PainPoint] = Field(
        default_factory=list, description="Top pain points ranked by intensity"
    )
    desires: list[Desire] = Field(
        default_factory=list, description="What they ultimately want"
    )
    objections: list[str] = Field(
        default_factory=list,
        description="Why they hesitate to buy: 'too expensive', 'will it actually work', etc.",
    )
    current_solutions: list[str] = Field(
        default_factory=list,
        description="What they're using now instead of your product",
    )
    trigger_events: list[str] = Field(
        default_factory=list,
        description="Life events that make them ready to buy, e.g. 'new job', 'health scare'",
    )
    awareness_level: str = Field(
        default="problem_aware",
        description="Schwartz awareness level: unaware, problem_aware, "
        "solution_aware, product_aware, most_aware",
    )
    language_patterns: list[str] = Field(
        default_factory=list,
        description="How they talk: formal/casual, jargon they use, emotional register",
    )
    psychology_profile: "PsychologyProfile | None" = Field(
        default=None,
        description="Buyer psychology diagnostic — dominant/weak heuristics, valence/intensity "
        "position, and pre-vetted Tether Lab pairings. Produced by `adc profile-psychology`.",
    )


# ─── Psychology Profile (Stage 1.5) ─────────────────────────────────────────
#
# Diagnostic layer produced by the psychology-profiling skill. Drives which
# heuristics the angle multiplier should activate, which valence/intensity
# quadrant to anchor in, and which Tether Lab pairings fit (vs backfire).
# See prompts/skills/psychology-profiling.md for the diagnostic methodology.


class DominantHeuristic(BaseModel):
    """A heuristic that is a top lever for this buyer, with evidence."""

    heuristic: str = Field(description="Heuristic name (snake_case from HEURISTIC_NAMES)")
    confidence: str = Field(description="high | medium | low")
    why: str = Field(description="One-sentence diagnosis")
    evidence: list[str] = Field(
        min_length=1,
        description="Verbatim quotes or specific avatar/VOC field references. Non-empty.",
    )
    ad_implications: str = Field(
        description="How copy and visuals should activate this heuristic"
    )

    @field_validator("heuristic")
    @classmethod
    def _valid_heuristic(cls, v: str) -> str:
        if v not in HEURISTIC_NAMES:
            raise ValueError(
                f"Unknown heuristic '{v}'. Must be one of: {sorted(HEURISTIC_NAMES)}"
            )
        return v

    @field_validator("confidence")
    @classmethod
    def _valid_confidence(cls, v: str) -> str:
        if v not in CONFIDENCE_LEVELS:
            raise ValueError(f"Confidence must be high/medium/low, got '{v}'")
        return v


class WeakHeuristic(BaseModel):
    """A heuristic that will backfire for this buyer."""

    heuristic: str = Field(description="Heuristic name (snake_case from HEURISTIC_NAMES)")
    why: str = Field(description="Why this lever backfires for this buyer")
    avoid: str = Field(description="What NOT to do — concrete creative guidance")

    @field_validator("heuristic")
    @classmethod
    def _valid_heuristic(cls, v: str) -> str:
        if v not in HEURISTIC_NAMES:
            raise ValueError(
                f"Unknown heuristic '{v}'. Must be one of: {sorted(HEURISTIC_NAMES)}"
            )
        return v


class EmotionalQuadrant(BaseModel):
    """One quadrant of the valence × intensity map."""

    valence: str = Field(description="positive | negative")
    intensity: str = Field(description="high | low")
    rationale: str = Field(default="", description="Evidence-based placement (primary)")
    use_for: str = Field(default="", description="When to anchor variants here (secondary)")

    @field_validator("valence")
    @classmethod
    def _valid_valence(cls, v: str) -> str:
        if v not in {"positive", "negative"}:
            raise ValueError(f"Valence must be positive/negative, got '{v}'")
        return v

    @field_validator("intensity")
    @classmethod
    def _valid_intensity(cls, v: str) -> str:
        if v not in {"high", "low"}:
            raise ValueError(f"Intensity must be high/low, got '{v}'")
        return v


class EmotionalPosition(BaseModel):
    """Primary + secondary quadrant placement for the avatar's purchase decision."""

    primary: EmotionalQuadrant = Field(description="Default anchor for the strongest ad")
    secondary: EmotionalQuadrant = Field(description="Contrast quadrant for variant testing")


class RecommendedPairing(BaseModel):
    """A Tether Lab paired-mechanism prompt that fits this buyer."""

    pairing: str = Field(description="Pairing name (snake_case from PAIRING_NAMES)")
    fits_because: str = Field(description="Which heuristic / quadrant it activates")

    @field_validator("pairing")
    @classmethod
    def _valid_pairing(cls, v: str) -> str:
        if v not in PAIRING_NAMES:
            raise ValueError(
                f"Unknown pairing '{v}'. Must be one of: {sorted(PAIRING_NAMES)}"
            )
        return v


class AvoidPairing(BaseModel):
    """A Tether Lab paired-mechanism prompt that will backfire for this buyer."""

    pairing: str = Field(description="Pairing name (snake_case from PAIRING_NAMES)")
    avoid_because: str = Field(description="Which dominant pattern it violates")

    @field_validator("pairing")
    @classmethod
    def _valid_pairing(cls, v: str) -> str:
        if v not in PAIRING_NAMES:
            raise ValueError(
                f"Unknown pairing '{v}'. Must be one of: {sorted(PAIRING_NAMES)}"
            )
        return v


class PsychologyProfile(BaseModel):
    """Buyer psychology diagnostic — feeds the angle multiplier downstream."""

    dominant_heuristics: list[DominantHeuristic] = Field(default_factory=list)
    weak_heuristics: list[WeakHeuristic] = Field(default_factory=list)
    emotional_position: EmotionalPosition | None = None
    recommended_prompt_pairings: list[RecommendedPairing] = Field(default_factory=list)
    avoid_pairings: list[AvoidPairing] = Field(default_factory=list)
    source: str = Field(
        default="auto_from_psychology_profiling",
        description="Provenance marker — matches `auto_from_brand_context` convention",
    )

    @model_validator(mode="after")
    def _enforce_confidence_ceiling(self) -> "PsychologyProfile":
        high = sum(1 for h in self.dominant_heuristics if h.confidence == "high")
        if high > 3:
            raise ValueError(
                f"At most 3 dominant heuristics may be high-confidence, got {high}. "
                "Force a ranking — strong profiles concentrate."
            )
        return self

    @model_validator(mode="after")
    def _enforce_pairing_ceiling(self) -> "PsychologyProfile":
        if len(self.recommended_prompt_pairings) > 6:
            raise ValueError(
                f"At most 6 recommended pairings allowed, got "
                f"{len(self.recommended_prompt_pairings)}. Filter to the 3–6 that fit best."
            )
        return self


# Resolve the forward reference now that PsychologyProfile is defined.
CustomerAvatar.model_rebuild()
