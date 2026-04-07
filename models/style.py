from __future__ import annotations

from pydantic import BaseModel, Field


class PlatformSize(BaseModel):
    width: int
    height: int
    label: str = Field(default="", description="Human label, e.g. 'Meta Feed Square'")


class CompositionRule(BaseModel):
    layout: str = Field(
        description="Layout descriptor, e.g. 'product-center-callouts-right'"
    )
    callout_count: int = Field(default=0, description="Number of text callout boxes")
    callout_style: str = Field(default="", description="Visual style of callouts")
    text_position: str = Field(default="", description="Where text appears in the composition")
    person_position: str = Field(
        default="", description="Where UGC person appears, if applicable"
    )


class Variant(BaseModel):
    """A themed variation of a style (e.g., different color, mood, or season)."""

    name: str = Field(description="Variant name, e.g. 'dark-chocolate', 'summer-vibe'")
    prompt_override: str = Field(
        default="",
        description="Partial prompt text that replaces or appends to the base template",
    )
    color_override: str = Field(default="", description="Color palette override for this variant")
    mood: str = Field(default="", description="Mood/atmosphere for this variant")


class CameraSpec(BaseModel):
    """Camera and photography specifications for realistic product shots."""

    camera_body: str = Field(default="", description="e.g. 'Canon EOS R5', 'ARRI Alexa 65'")
    lens: str = Field(default="", description="e.g. '85mm f/1.4', '50mm macro'")
    film_emulation: str = Field(default="", description="e.g. 'Kodak Portra 400', 'Fuji Velvia'")
    lighting_rig: str = Field(
        default="",
        description="Lighting setup description, e.g. 'soft key light from left, "
        "rim light from behind, white bounce fill'",
    )


class Style(BaseModel):
    name: str = Field(description="Style name, e.g. 'benefit-callout'")
    description: str = Field(description="What this style looks like and when to use it")
    prompt_template: str = Field(
        description="Prompt template with {placeholders} for brand/product/brief data. "
        "Can be plain text or structured JSON manifest."
    )
    prompt_format: str = Field(
        default="text",
        description="Prompt format: 'text' (plain template), 'json_manifest' (structured JSON), "
        "'grid' (multi-cell contact sheet)",
    )
    negative_prompt: str = Field(
        default="",
        description="Negative prompt to avoid unwanted elements",
    )
    composition: CompositionRule | None = Field(
        default=None, description="Composition/layout rules"
    )
    camera: CameraSpec | None = Field(
        default=None,
        description="Camera/photography specs for realistic product shots",
    )
    platforms: dict[str, list[PlatformSize]] = Field(
        default_factory=dict,
        description="Platform-specific output sizes",
    )
    fal_model: str = Field(
        default="fal-ai/flux-pro/v1.1",
        description="fal.ai model identifier to use for this style",
    )
    fal_params: dict = Field(
        default_factory=dict,
        description="Additional fal.ai API parameters (guidance_scale, steps, etc.)",
    )
    reference_images: list[str] = Field(
        default_factory=list,
        description="Paths to reference images showing this style",
    )
    platform_modifiers: dict[str, str] = Field(
        default_factory=dict,
        description="Platform-specific prompt additions, e.g. "
        "{'tiktok': 'casual handheld feel, slightly imperfect, raw authentic'}",
    )
    variants: list[Variant] = Field(
        default_factory=list,
        description="Themed variations of this style (different colors, moods, seasons). "
        "Generate all variants from one style in a batch.",
    )
    grid_cells: list[dict] = Field(
        default_factory=list,
        description="For grid/contact-sheet styles: list of cell definitions, "
        "each with 'concept' and 'prompt' keys for multi-shot ad sets.",
    )
    source: str = Field(
        default="",
        description="Attribution: where this prompt came from (repo URL, author handle)",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Searchable tags: 'product-focused', 'ugc', 'text-heavy', etc.",
    )
