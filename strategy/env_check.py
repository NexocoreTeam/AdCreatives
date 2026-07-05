"""Presence-only environment key check. Values are never read back out.

Answers "does THIS machine have the keys the pipeline uses?" — the question
that comes up every time a second machine (OpenClaw box, new laptop) runs a
client. Presence does not prove validity: a stale key still shows present;
per-layer failures surface in run output and `adc status` diagnostics.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

TIER_REQUIRED = "required"
TIER_RECOMMENDED = "recommended"
TIER_OPTIONAL = "optional"
TIER_PHASE2 = "phase-2"

KEY_SPECS: list[tuple[str, str, str]] = [
    ("ANTHROPIC_API_KEY", TIER_REQUIRED,
     "every strategy stage (research, personas, gaps, briefs)"),
    ("EXA_API_KEY", TIER_REQUIRED,
     "web sentiment + Amazon suggestions (research-competitors, suggest-amazon)"),
    ("APIFY_API_TOKEN", TIER_RECOMMENDED,
     "TikTok/Instagram comments, Amazon reviews, Reddit bridge"),
    ("YOUTUBE_API_KEY", TIER_RECOMMENDED,
     "YouTube comments (research-social)"),
    ("FIRECRAWL_API_KEY", TIER_RECOMMENDED,
     "JS-rendered scraping (on-site reviews, brand research)"),
    ("REDDIT_CLIENT_ID", TIER_OPTIONAL,
     "official Reddit API (preferred over the Apify bridge)"),
    ("REDDIT_CLIENT_SECRET", TIER_OPTIONAL,
     "official Reddit API"),
    ("OPENROUTER_API_KEY", TIER_OPTIONAL,
     "visual identity capture during research (skipped gracefully if absent)"),
    ("OPENAI_API_KEY", TIER_OPTIONAL,
     "vision analysis + structured prompt writing"),
    ("FAL_KEY", TIER_PHASE2,
     "image generation (adc generate)"),
    ("HF_CREDENTIALS", TIER_PHASE2,
     "Higgsfield engine (--engine higgsfield-soul)"),
]


@dataclass
class KeyStatus:
    name: str
    tier: str
    unlocks: str
    present: bool


def check_env() -> list[KeyStatus]:
    return [
        KeyStatus(
            name=name,
            tier=tier,
            unlocks=unlocks,
            present=bool(os.environ.get(name, "").strip()),
        )
        for name, tier, unlocks in KEY_SPECS
    ]


def missing_required(statuses: list[KeyStatus]) -> list[str]:
    return [s.name for s in statuses if s.tier == TIER_REQUIRED and not s.present]
