from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _as_str_list(v):
    """LLM extractions sometimes return a prose string where the schema wants
    list[str]. Wrap instead of failing — a one-item list is lossless, and a
    type error here bricks every downstream load_brand() call."""
    if isinstance(v, str):
        return [v.strip()] if v.strip() else []
    return v


def _as_joined_str(v):
    """Inverse wobble: a list where the schema wants a string."""
    if isinstance(v, list):
        return ", ".join(str(item).strip() for item in v if str(item).strip())
    return v


class UgcVoice(BaseModel):
    """Brand-level UGC overlay voice spec.

    Drives the `adc ugc-ad` command — provides the register, approved CTAs,
    pill / box colors, and cross-platform font paths used by the PIL overlay
    renderer. All fields optional so existing brands without a `ugc_voice`
    block continue to load. The CLI falls back to a hardcoded SecondKind
    preset when a brand defines no UGC voice.

    `font_fallback` / `emoji_font_fallback` are platform-keyed maps so the
    same brand.yaml works on Windows / macOS / Linux dev machines without
    edits.

    Note on the `register` YAML key: Pydantic v2's BaseModel already has a
    classmethod named `register`, so the Python attribute is `voice_register`
    while the on-disk YAML key stays `register` (via the field alias).
    `populate_by_name=True` keeps both name and alias accepted on load.
    """

    model_config = ConfigDict(populate_by_name=True)

    voice_register: str = Field(
        default="",
        alias="register",
        description="One-line description of the UGC voice register, e.g. "
        "'friend-to-friend, not influencer-cheese. wry, confident, "
        "peer-recommendation.'",
    )
    approved_ctas: list[str] = Field(
        default_factory=list,
        description="Whitelist of CTA phrases that fit the UGC voice. Used to "
        "auto-suggest the right CTA when a brief doesn't specify one.",
    )
    do_not_use_ctas: list[str] = Field(
        default_factory=list,
        description="Phrases that violate the UGC register. The CLI warns when "
        "a brief text contains any of these.",
    )
    pill_highlight_color: str = Field(
        default="",
        description="Hex color for the marigold/coral highlight pill, e.g. '#fcb348'",
    )
    pill_text_color: str = Field(
        default="",
        description="Hex color for text inside the highlight pill",
    )
    box_bg_color: str = Field(
        default="",
        description="Hex color for the solid white-style caption box background",
    )
    box_text_color: str = Field(
        default="",
        description="Hex color for text inside the caption box",
    )
    font_preference: str = Field(
        default="",
        description="Symbolic font name (e.g. 'segoe_ui_bold'). Informational — "
        "resolution happens via `font_fallback` per platform.",
    )
    font_fallback: dict[str, str] = Field(
        default_factory=dict,
        description="Platform-keyed font paths. Keys: 'windows', 'macos', "
        "'linux'. Values are absolute paths to .ttf / .otf files.",
    )
    emoji_font_fallback: dict[str, str] = Field(
        default_factory=dict,
        description="Platform-keyed paths to the color emoji font (e.g. Segoe "
        "UI Emoji, Apple Color Emoji, Noto Color Emoji).",
    )


class EditorialExample(BaseModel):
    """A concrete example of a background/visual treatment that has worked
    in past editorial ads for this brand. Used as a starter palette — NOT
    as the exclusive list of allowed treatments. See `EditorialDesign`."""

    name: str = Field(description="Short identifier, e.g. 'apothecary_amber_gradient'")
    where: str = Field(
        default="",
        description="Brief note on where this treatment shipped, e.g. "
        "'pain-010 v2 — deep amber → dark brown'",
    )
    why: str = Field(
        default="",
        description="One-sentence reason it worked for this brand",
    )


class EditorialDesign(BaseModel):
    """Brand-level design principles for editorial-format ads.

    Captures lessons-learned about what makes editorial ads work for this
    brand without prescribing exact aesthetics — the model is given firm
    principles + a starter palette of proven examples + explicit don'ts +
    explicit permission to invent within those bounds.

    Hooked into `strategy/creative_matrix.py`'s static-treatment prompt so
    every editorial brief auto-includes these rules at generation time. The
    AI sees principles to honor and policy don'ts to avoid, plus license
    to propose novel treatments that satisfy both.

    All fields optional so brands without an `editorial_design` block load
    cleanly and the prompt builder gracefully skips the injection.
    """

    model_config = ConfigDict(populate_by_name=True)

    principles: list[str] = Field(
        default_factory=list,
        description="Firm constraints the model must honor on every editorial "
        "ad — e.g. 'Background must have atmospheric depth.' These are the "
        "non-negotiable lessons.",
    )
    examples_that_worked: list[EditorialExample] = Field(
        default_factory=list,
        description="Starter palette of proven treatments. NOT exhaustive — "
        "the model should treat these as proof-of-concept and feel free to "
        "propose variations.",
    )
    do_not_use: list[str] = Field(
        default_factory=list,
        description="Hard-policy violations — these are brand-voice or "
        "category-positioning conflicts, not just style preferences. E.g. "
        "'lifestyle_imagery (grass/moss/nature) — pattern-matches wellness "
        "fluff which we explicitly indict.'",
    )
    freedom_to_explore: str = Field(
        default="",
        description="Explicit permission for the model to invent novel "
        "treatments. Without this, the model tends to pick the first example "
        "verbatim and never deviate. Phrase as license, not as instruction "
        "to be wild.",
    )


class ReferencesConfig(BaseModel):
    """Brand-level reference-asset config for the `adc fetch-references` cache.

    `swipe_folder_id` lets the operator run `adc fetch-references --client X`
    without re-typing the folder ID every time.
    """

    swipe_folder_id: str = Field(
        default="",
        description="Default Google Drive folder ID for the brand's swipe / "
        "reference-ads gallery. When set, `adc fetch-references --client X` "
        "uses it without needing --folder. Separate from `drive_folder_id` "
        "(the top-level brand assets folder).",
    )


class ColorPalette(BaseModel):
    """Brand colors. All fields optional — clients fill these in directly
    (research no longer attempts to extract them, since site CSS extraction
    and logo vision are both unreliable proxies for actual brand palette)."""

    primary: str = Field(default="", description="Primary brand color hex code, e.g. #1E40AF")
    secondary: str = Field(default="", description="Secondary brand color hex code")
    background: str = Field(default="#FFFFFF", description="Default background color")
    text: str = Field(default="#111827", description="Default text color")
    accent: str | None = Field(default=None, description="Optional accent color")


class Typography(BaseModel):
    heading: str = Field(default="", description="Heading font name, e.g. 'Montserrat Bold'")
    body: str = Field(default="", description="Body font name, e.g. 'Inter'")
    accent: str | None = Field(default=None, description="Optional accent/display font")


class VisualIdentity(BaseModel):
    """Rich descriptive visual identity for a brand — what a creative
    strategist would document. Captured automatically by research using
    multi-image vision (Gemini via OpenRouter, or Claude vision fallback).
    Far more useful for ad generation than raw hex color codes."""

    aesthetic: str = Field(default="", description="1-2 sentence overall vibe")
    photography_style: str = Field(default="", description="studio / lifestyle / UGC / editorial / flat lay / etc.")
    design_language: str = Field(default="", description="minimalist / maximalist / retro / cartoon / editorial / etc.")
    typography_feel: str = Field(default="", description="modern sans / handwritten / serif / display / etc.")
    mascot_or_character: str = Field(default="", description="describe any mascot/character, or empty if none")
    visual_references: list[str] = Field(default_factory=list, description="adjacent brands, design movements, cultural references")
    mood: list[str] = Field(default_factory=list, description="3-5 adjectives capturing emotional register")
    notable_visual_signatures: list[str] = Field(default_factory=list, description="specific visual elements that define this brand")
    color_mood: str = Field(default="", description="palette feel WITHOUT hex codes — warm, vibrant, muted, monochromatic, etc.")

    _coerce_lists = field_validator(
        "visual_references", "mood", "notable_visual_signatures", mode="before"
    )(_as_str_list)
    _coerce_strs = field_validator(
        "aesthetic", "photography_style", "design_language", "typography_feel",
        "mascot_or_character", "color_mood", mode="before"
    )(_as_joined_str)


class AudienceProfile(BaseModel):
    age_range: str = Field(description="Target age range, e.g. '25-45'")
    gender: str = Field(default="mixed", description="Target gender: male, female, mixed")
    interests: list[str] = Field(default_factory=list, description="Key interest categories")
    demographics_for_ugc: str = Field(
        default="",
        description="Description of person to depict in UGC-style ads, e.g. "
        "'professional millennial woman, diverse'",
    )
    locations: list[str] = Field(default_factory=list, description="Target geographic locations")

    _coerce_lists = field_validator("interests", "locations", mode="before")(_as_str_list)


class Brand(BaseModel):
    name: str = Field(description="Brand/company name")
    code: str = Field(
        default="",
        description="Short alphanumeric brand code used as Slot 1 of the Meta "
        "ad naming taxonomy (e.g. 'SK' for SecondKind, 'OP' for Olipop). "
        "2-6 chars, no spaces or punctuation. Required when generating campaign "
        "names — `strategy/naming.py:build_campaign_name` raises if empty.",
    )
    colors: ColorPalette = Field(default_factory=ColorPalette)
    typography: Typography = Field(default_factory=Typography)
    visual_identity: VisualIdentity = Field(default_factory=VisualIdentity)
    tone: str = Field(
        default="",
        description="Brand voice description, e.g. 'professional, trustworthy, modern'"
    )
    audience: AudienceProfile = Field(default_factory=lambda: AudienceProfile(age_range=""))
    platforms: list[str] = Field(
        default_factory=lambda: ["meta", "tiktok"],
        description="Target ad platforms",
    )
    logo_path: str | None = Field(default=None, description="Relative path to logo file")
    drive_folder_id: str | None = Field(
        default=None,
        description="Google Drive folder ID for client assets. Folder must be shared "
        "with the GOOGLE_APPLICATION_CREDENTIALS service account. Expected layout: "
        "<folder>/brand/* (logos, brand books, mood boards) + <folder>/reference-ads/* "
        "(past performant ads). Consumed by `adc enrich-brand` and `adc analyze-references`.",
    )
    guidelines_notes: str = Field(
        default="",
        description="Additional brand guidelines or notes for the AI",
    )
    prohibited_terms: list[str] = Field(
        default_factory=list,
        description="Words/phrases that must never appear in ads for this brand",
    )
    ugc_voice: UgcVoice = Field(
        default_factory=UgcVoice,
        description="Brand-level UGC overlay voice spec — drives the `adc "
        "ugc-ad` command (CTA whitelist, pill colors, font fallbacks).",
    )
    references: ReferencesConfig = Field(
        default_factory=ReferencesConfig,
        description="Brand-level reference-asset config (Drive swipe folder, etc.)",
    )
    editorial_design: EditorialDesign = Field(
        default_factory=EditorialDesign,
        description="Brand-level design principles for editorial-format ads — "
        "injected into the `creative_matrix` static_treatment prompt so the "
        "AI sees principles + proven examples + don'ts + permission-to-invent "
        "every time it generates an editorial brief.",
    )
