"""Portable, versioned production records. A record is not a production approval."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipeStep(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tool: str = Field(min_length=1)
    prompt: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(min_length=1)
    notes: str = ""


class RecipeAsset(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_path: str


class CreativeRecipe(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal[1] = 1
    kind: Literal["creative_recipe"] = "creative_recipe"
    client: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]*$")
    product: str = Field(min_length=1)
    concept_id: UUID
    version_id: UUID
    parent_version_id: UUID | None = None
    created_at: str
    provenance: Literal["recorded", "reconstructed"]
    limitations: list[str] = Field(default_factory=list)
    changes: dict[str, str] = Field(default_factory=dict)
    brief: dict[str, Any] | None = None
    runtime: dict[str, str] = Field(default_factory=dict)
    assets: dict[str, RecipeAsset] = Field(min_length=1)
    steps: list[RecipeStep] = Field(min_length=1)

    @model_validator(mode="after")
    def check_recipe(self) -> "CreativeRecipe":
        if self.provenance == "reconstructed" and not self.limitations:
            raise ValueError("Reconstructed recipes must describe missing history")
        if self.parent_version_id and not self.changes:
            raise ValueError("A variation must record what changed")
        for step in self.steps:
            for role in step.inputs + step.outputs:
                if role not in self.assets:
                    raise ValueError(f"Step references unknown asset: {role}")
        return self
