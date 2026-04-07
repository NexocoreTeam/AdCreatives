from __future__ import annotations

from pydantic import BaseModel, Field


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
