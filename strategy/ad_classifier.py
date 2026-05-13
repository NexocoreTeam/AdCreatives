"""Ad-type classifier — Haiku-powered, text-only.

Classifies a Foreplay ad into one of 8 standard ad-type categories based on
its headline, description, CTA, and AI-extracted keywords. No image vision
(text-only keeps cost ~$0.0007/ad).

Returns (category_key, confidence, reasoning). If no category fits well,
returns ('other', confidence, reasoning).

Uses prompt caching on the system prompt so repeat calls in a short window
get 90% input discount.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from strategy.llm import get_anthropic_client

HAIKU_MODEL = "claude-haiku-4-5-20251001"

# Canonical category keys + definitions. Mirrored in
# references/swipe/standard/_meta.yaml.
CATEGORIES: dict[str, str] = {
    "testimonial-review": (
        "Customer voice + ratings. Hallmarks: 5-star ratings, named reviewer "
        "quotes ('Sarah K. says…'), 'real customer said…', screenshot-style "
        "review cards, quote marks around customer testimony. Social proof is "
        "the lead element."
    ),
    "features-and-benefits": (
        "Specs + outcomes. Iconned/bulleted feature list, 'feature → benefit' "
        "callouts pointing to the product, capability rundown ('Reduces wrinkles. "
        "Boosts collagen. Made in USA.'). Product is hero with feature callouts."
    ),
    "us-vs-them": (
        "Comparison with a competitor or the status quo. Split layout, "
        "'old way vs new way', checkmarks vs Xs, direct competitor naming, "
        "side-by-side products. Establishes superiority via contrast."
    ),
    "before-and-after": (
        "Visual transformation. Two states shown — problem visible (before) "
        "then resolved (after). Skin transformations, weight changes, room "
        "makeovers, hair regrowth. Power comes from the visual contrast."
    ),
    "promotion-and-discount": (
        "Price-led offer. Big % off, urgency language ('today only', 'limited "
        "time'), price comparison ('was $X, now $Y'), sale stickers, BFCM "
        "framing. The DEAL is the hook, not the product itself."
    ),
    "ugc": (
        "User-generated-content style. Reads as creator/customer-shot — phone-"
        "camera feel, casual or selfie-angle framing, low-production, person "
        "speaking to camera, conversational tone in copy ('Just tried this and "
        "OMG'). Designed to feel organic, not produced."
    ),
    "facts-and-stats": (
        "Data-led authority. Big stat hero ('30,000 women trust X', '47% "
        "improvement', '3x more effective'), clinical studies, citations, "
        "scale numbers. ONE big number dominates the hook."
    ),
    "reasons-why": (
        "Numbered listicle hook. '5 reasons you need X', 'Why we beat Y', "
        "'3 things every Z should know'. The number + enumeration is the "
        "primary hook structure."
    ),
}

CATEGORY_KEYS = tuple(CATEGORIES.keys())


def _system_prompt() -> str:
    lines = [
        "You are an expert ad classifier. You receive a single advertisement's text content "
        "and classify it into EXACTLY ONE of these 8 ad-type categories.",
        "",
        "CATEGORIES (use the lowercase key, exactly as written):",
        "",
    ]
    for key, desc in CATEGORIES.items():
        lines.append(f"- {key}: {desc}")
    lines.extend([
        "",
        "If none of the 8 categories fit with confidence ≥ 0.5, output category 'other'.",
        "",
        "OUTPUT FORMAT — strict JSON ONLY (no prose, no markdown fences):",
        '{"category": "<key>", "confidence": <0.0-1.0>, "reasoning": "<one sentence>"}',
        "",
        "Confidence rubric:",
        "  0.9+  — unambiguous: dominant cue for the category is present in headline/copy",
        "  0.7-0.9 — strong signal but some ambiguity",
        "  0.5-0.7 — plausible classification, weak cues",
        "  <0.5  — use 'other'",
    ])
    return "\n".join(lines)


def _build_user_msg(*, brand: str, headline: str, description: str,
                    cta_title: str, cta_type: str, keywords: list[str],
                    ai_keywords: list[str], niches: list[str]) -> str:
    desc = (description or "").strip()
    if len(desc) > 600:
        desc = desc[:600] + "…"
    kws = ", ".join((ai_keywords or keywords or [])[:25])
    return (
        f"Brand: {brand}\n"
        f"Niche: {', '.join(niches)}\n"
        f"Headline: {headline}\n"
        f"Description: {desc}\n"
        f"CTA: {cta_title or cta_type}\n"
        f"Keywords: {kws}\n"
        f"\n"
        f"Classify this ad."
    )


@dataclass
class Classification:
    category: str
    confidence: float
    reasoning: str


def _parse_json_response(text: str) -> dict:
    """Robust JSON extraction — strips markdown fences, finds first {..} block."""
    text = text.strip()
    # Strip ```json ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {text[:200]}")
    return json.loads(text[start : end + 1])


def classify_ad(
    *,
    brand: str,
    headline: str = "",
    description: str = "",
    cta_title: str = "",
    cta_type: str = "",
    keywords: list[str] | None = None,
    ai_keywords: list[str] | None = None,
    niches: list[str] | None = None,
) -> Classification:
    """Classify one ad. Uses Haiku with prompt caching on system prompt."""
    client = get_anthropic_client()
    user_msg = _build_user_msg(
        brand=brand,
        headline=headline,
        description=description,
        cta_title=cta_title,
        cta_type=cta_type,
        keywords=keywords or [],
        ai_keywords=ai_keywords or [],
        niches=niches or [],
    )

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=200,
        # Cache the long category-definition system prompt so subsequent calls
        # within ~5 minutes pay 10% of normal input cost on the cached portion.
        system=[
            {
                "type": "text",
                "text": _system_prompt(),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_msg}],
    )
    raw_text = response.content[0].text

    try:
        parsed = _parse_json_response(raw_text)
    except (ValueError, json.JSONDecodeError) as exc:
        # Fall back to 'other' on parse failure so the pipeline doesn't crash.
        return Classification(category="other", confidence=0.0, reasoning=f"parse_error: {exc}")

    cat = str(parsed.get("category") or "other").strip().lower()
    conf = float(parsed.get("confidence") or 0.0)
    reasoning = str(parsed.get("reasoning") or "").strip()

    # Normalize: only allow our 8 keys + 'other'
    if cat not in CATEGORY_KEYS and cat != "other":
        # Sometimes models return e.g. "testimonial review" with space — coerce
        normalized = cat.replace("_", "-").replace(" ", "-")
        if normalized in CATEGORY_KEYS:
            cat = normalized
        else:
            cat = "other"

    return Classification(category=cat, confidence=conf, reasoning=reasoning)
