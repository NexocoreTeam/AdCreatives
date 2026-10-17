"""Video observations are evidence, never instructions or recovered original prompts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Shot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    camera: str = Field(min_length=1, max_length=1000)
    action: str = Field(min_length=1, max_length=2000)
    dialogue: str = Field(default="", max_length=2000)
    overlay: str = Field(default="", max_length=1000)


class VideoAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    provenance: Literal["manual_review", "higgsfield_video_analysis"]
    evidence: str = Field(min_length=1, max_length=2000)
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    duration: float = Field(gt=0, le=180, allow_inf_nan=False)
    shots: list[Shot] = Field(min_length=1, max_length=100)
    limitations: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def timeline(self):
        end = 0.0
        for shot in self.shots:
            if abs(shot.start - end) > 0.05 or shot.end <= shot.start:
                raise ValueError("Shots must cover the source in order without gaps or overlaps")
            end = shot.end
        if abs(end - self.duration) > 0.05:
            raise ValueError("Shot timeline must cover the full source duration")
        return self


class RemakeBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    product: str = Field(min_length=1, max_length=200)
    product_truth: str = Field(min_length=1, max_length=2000)
    purpose: str = Field(min_length=1, max_length=1000)
    direction: str = Field(min_length=1, max_length=3000)
    duration: int = Field(ge=4, le=30)
    duration_change_reason: str = Field(default="", max_length=500)
    audio: Literal["silent", "spoken"] = "silent"
    script: str = Field(default="", max_length=2000)
    resolution: Literal["480p", "720p", "1080p"] = "1080p"
    aspect_ratio: Literal["9:16", "16:9", "1:1", "4:3", "3:4"] = "9:16"

    @model_validator(mode="after")
    def sound(self):
        if self.audio == "silent" and self.script:
            raise ValueError("Silent video cannot contain a spoken script")
        if self.audio == "spoken" and not self.script.strip():
            raise ValueError("Spoken video needs an explicitly supplied script")
        if "—" in self.script:
            raise ValueError("Em-dashes are not allowed in ad copy")
        return self
