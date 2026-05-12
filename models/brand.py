from __future__ import annotations

from pydantic import BaseModel, Field


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


class Brand(BaseModel):
    name: str = Field(description="Brand/company name")
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
