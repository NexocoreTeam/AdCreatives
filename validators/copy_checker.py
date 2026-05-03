"""Platform-specific char-limit validation for ad copy.

Char limits sourced from the ad-creative skill in
github.com/coreyhaines31/marketingskills (MIT). See prompts/skills/ for the
full skill reference.

Each platform field has:
- recommended: the soft limit (truncation/visibility threshold)
- hard_max: the absolute platform reject threshold (None means recommended IS the hard limit)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# fmt: off
PLATFORM_LIMITS: dict[str, dict[str, dict[str, int | None]]] = {
    "google": {
        "headline":         {"recommended": 30,  "hard_max": None},
        "description":      {"recommended": 90,  "hard_max": None},
        "display_url_path": {"recommended": 15,  "hard_max": None},
    },
    "meta": {
        "primary_text":     {"recommended": 125, "hard_max": 2200},
        "headline":         {"recommended": 40,  "hard_max": 200},
        "description":      {"recommended": 30,  "hard_max": 200},
        "url_display_link": {"recommended": 40,  "hard_max": None},
    },
    "linkedin": {
        "intro_text":       {"recommended": 150, "hard_max": 600},
        "headline":         {"recommended": 70,  "hard_max": 200},
        "description":      {"recommended": 100, "hard_max": 300},
    },
    "tiktok": {
        "ad_text":          {"recommended": 80,  "hard_max": 100},
        "display_name":     {"recommended": 40,  "hard_max": None},
    },
    "x": {
        "tweet_text":       {"recommended": 280, "hard_max": 280},
        "headline":         {"recommended": 70,  "hard_max": None},
        "description":      {"recommended": 200, "hard_max": None},
    },
}
# fmt: on


class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class CopyCheck:
    platform: str
    field: str
    text: str
    length: int
    recommended: int
    hard_max: int | None
    passed: bool
    severity: Severity
    detail: str


def list_platforms() -> list[str]:
    return sorted(PLATFORM_LIMITS.keys())


def list_fields(platform: str) -> list[str]:
    if platform not in PLATFORM_LIMITS:
        raise ValueError(
            f"unknown platform '{platform}'. Available: {', '.join(list_platforms())}"
        )
    return sorted(PLATFORM_LIMITS[platform].keys())


def check_copy(text: str, *, platform: str, field: str) -> CopyCheck:
    """Validate ad copy text against a specific platform field's char limit."""
    if platform not in PLATFORM_LIMITS:
        raise ValueError(
            f"unknown platform '{platform}'. Available: {', '.join(list_platforms())}"
        )
    if field not in PLATFORM_LIMITS[platform]:
        raise ValueError(
            f"unknown field '{field}' for platform '{platform}'. "
            f"Available: {', '.join(list_fields(platform))}"
        )

    limits = PLATFORM_LIMITS[platform][field]
    recommended = limits["recommended"]
    hard_max = limits["hard_max"]
    length = len(text)

    if length <= recommended:
        return CopyCheck(
            platform=platform,
            field=field,
            text=text,
            length=length,
            recommended=recommended,
            hard_max=hard_max,
            passed=True,
            severity=Severity.OK,
            detail=f"{length}/{recommended} chars — ok",
        )

    if hard_max is None:
        return CopyCheck(
            platform=platform,
            field=field,
            text=text,
            length=length,
            recommended=recommended,
            hard_max=hard_max,
            passed=False,
            severity=Severity.ERROR,
            detail=f"{length} chars exceeds {recommended} limit (no soft tier for this field)",
        )

    if length <= hard_max:
        return CopyCheck(
            platform=platform,
            field=field,
            text=text,
            length=length,
            recommended=recommended,
            hard_max=hard_max,
            passed=False,
            severity=Severity.WARNING,
            detail=f"{length} chars exceeds recommended {recommended} (hard max {hard_max})",
        )

    return CopyCheck(
        platform=platform,
        field=field,
        text=text,
        length=length,
        recommended=recommended,
        hard_max=hard_max,
        passed=False,
        severity=Severity.ERROR,
        detail=f"{length} chars over hard max {hard_max}",
    )


def suggest_trim(text: str, *, target: int, ellipsis: str = "…") -> str:
    """Trim text to fit within target characters, preferring word boundaries."""
    if len(text) <= target:
        return text

    budget = target - len(ellipsis)
    if budget <= 0:
        return text[:target]

    candidate = text[:budget]
    last_space = candidate.rfind(" ")
    if last_space > budget * 0.6:
        candidate = candidate[:last_space]

    return candidate.rstrip() + ellipsis
