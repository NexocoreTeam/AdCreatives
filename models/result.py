from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class CreativeResult(BaseModel):
    """Performance data for a single generated creative."""

    creative_id: str = Field(description="Unique ID matching the output filename")
    client: str
    product: str
    style: str = Field(description="Style template used")
    brief_id: str = Field(default="", description="Brief that drove this creative")
    hook: str = Field(default="", description="The hook/headline used")
    angle: str = Field(default="", description="Messaging angle")
    framework: str = Field(default="", description="Copy framework used")
    callouts: list[str] = Field(default_factory=list, description="Benefit callouts shown")
    platform: str = Field(default="meta", description="Platform where it ran")
    date_launched: date | None = Field(default=None)
    date_logged: date = Field(default_factory=date.today)

    # Performance metrics
    impressions: int | None = Field(default=None)
    clicks: int | None = Field(default=None)
    ctr: float | None = Field(default=None, description="Click-through rate as percentage")
    cpa: float | None = Field(default=None, description="Cost per acquisition in dollars")
    roas: float | None = Field(default=None, description="Return on ad spend ratio")
    spend: float | None = Field(default=None, description="Total spend in dollars")
    conversions: int | None = Field(default=None)

    # Qualitative
    notes: str = Field(default="", description="What worked or didn't and why")
    verdict: str = Field(
        default="",
        description="Quick verdict: 'winner', 'loser', 'control', 'testing'",
    )


class StylePerformance(BaseModel):
    style: str
    avg_ctr: float
    avg_cpa: float | None = None
    avg_roas: float | None = None
    sample_size: int = 0


class HookPerformance(BaseModel):
    hook_type: str = Field(description="Category: 'pain-number', 'question', 'shock-stat', etc.")
    avg_ctr: float
    sample_size: int = 0
    best_example: str = Field(default="", description="The actual hook text that performed best")


class WinningPatterns(BaseModel):
    """Auto-computed summary of what's working for a client."""

    client: str
    analysis_date: date = Field(default_factory=date.today)
    days_analyzed: int = Field(default=90)
    total_creatives_analyzed: int = Field(default=0)

    best_styles: list[StylePerformance] = Field(default_factory=list)
    worst_styles: list[StylePerformance] = Field(default_factory=list)
    best_hooks: list[HookPerformance] = Field(default_factory=list)
    best_angles: list[str] = Field(
        default_factory=list, description="Messaging angles that consistently perform"
    )
    best_callout_themes: list[str] = Field(
        default_factory=list,
        description="Benefit themes that resonate: 'time savings', 'ease of use', etc.",
    )
    best_frameworks: list[str] = Field(
        default_factory=list, description="Copy frameworks with highest avg performance"
    )
    platform_insights: dict[str, str] = Field(
        default_factory=dict,
        description="Platform-specific observations, e.g. {'tiktok': 'UGC outperforms polished'}",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="AI-generated recommendations for next creative batch",
    )
