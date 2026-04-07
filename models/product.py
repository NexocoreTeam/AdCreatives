from __future__ import annotations

from pydantic import BaseModel, Field


class Product(BaseModel):
    name: str = Field(description="Product name")
    description: str = Field(description="Short product description (1-2 sentences)")
    benefits: list[str] = Field(
        description="Key product benefits for ad callouts, e.g. 'Saves 2 hours per day'"
    )
    price: str | None = Field(default=None, description="Price or price range, e.g. '$49/mo'")
    category: str = Field(default="", description="Product category for compliance rules")
    image_path: str | None = Field(
        default=None,
        description="Relative path to primary product image",
    )
    additional_images: list[str] = Field(
        default_factory=list,
        description="Relative paths to additional product images",
    )
    url: str | None = Field(default=None, description="Product landing page URL")
    unique_mechanism: str = Field(
        default="",
        description="What makes this product work / why it's different "
        "(the 'mechanism' in direct response terms)",
    )
    objections: list[str] = Field(
        default_factory=list,
        description="Common buyer objections to preemptively address",
    )
    social_proof: list[str] = Field(
        default_factory=list,
        description="Social proof elements: review quotes, stats, awards",
    )
