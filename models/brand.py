from __future__ import annotations

from pydantic import BaseModel, Field


class ColorPalette(BaseModel):
    primary: str = Field(description="Primary brand color hex code, e.g. #1E40AF")
    secondary: str = Field(description="Secondary brand color hex code")
    background: str = Field(default="#FFFFFF", description="Default background color")
    text: str = Field(default="#111827", description="Default text color")
    accent: str | None = Field(default=None, description="Optional accent color")


class Typography(BaseModel):
    heading: str = Field(description="Heading font name, e.g. 'Montserrat Bold'")
    body: str = Field(description="Body font name, e.g. 'Inter'")
    accent: str | None = Field(default=None, description="Optional accent/display font")


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
    colors: ColorPalette
    typography: Typography
    tone: str = Field(
        description="Brand voice description, e.g. 'professional, trustworthy, modern'"
    )
    audience: AudienceProfile
    platforms: list[str] = Field(
        default_factory=lambda: ["meta", "tiktok"],
        description="Target ad platforms",
    )
    logo_path: str | None = Field(default=None, description="Relative path to logo file")
    guidelines_notes: str = Field(
        default="",
        description="Additional brand guidelines or notes for the AI",
    )
    prohibited_terms: list[str] = Field(
        default_factory=list,
        description="Words/phrases that must never appear in ads for this brand",
    )
