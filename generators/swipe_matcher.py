"""Match a CreativeBrief to relevant swipe library reference ads.

Two libraries:
    * references/swipe/standard/  — bucketed by AD TYPE (us-vs-them,
      features-and-benefits, testimonial-review, etc.). Provides
      compositional / layout references.
    * references/swipe/psychology/ — bucketed by EMOTIONAL NEED (belonging,
      competence, engagement, etc.). Provides vibe / tone references.

For each brief we pick a small handful (default: 2 from standard, 1 from
psychology) so NB2 has visual style references to follow, but the prompt
input list stays focused (1 product image + 2-3 style references).

Matching is keyword-heuristic; cheap and deterministic. If no clean match,
we fall back to the largest available folder for the brief's resolved
category.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

SWIPE_ROOT = Path("references/swipe")
STANDARD_ROOT = SWIPE_ROOT / "standard"
PSYCHOLOGY_ROOT = SWIPE_ROOT / "psychology"

# Image extensions the matcher will surface as reference candidates.
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}


# ─── Visual format → standard folder mapping ────────────────────────────────


# Each tuple = (keyword phrases that signal this ad type, folder name).
# Order matters — earlier matches win. Keywords are lowercased substring tests.
# More-specific signals come FIRST so generic terms like "clinical" don't
# capture a brief that's primarily a carousel / feature explainer.
STANDARD_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("comparison", "vs", "versus", "split between", "side by side", "side-by-side"),
        "us-vs-them"),
    (("testimonial", "review", "talking head", "ugc", "founder-to-camera",
      "founder to camera", "voice-note", "voice note", "pull-quote"),
        "testimonial-review"),
    (("before", "after", "transform"),
        "before-and-after"),
    (("offer", "promo", "discount", "% off", "deal", "sale"),
        "promotion-and-discount"),
    (("press", "as seen on", "media", "publication"),
        "media-and-press"),
    # features-and-benefits — moved up so "carousel" / "educational" /
    # "explainer" win over the broader "clinical" / "study" hits. Briefs
    # built around carousels are nearly always feature/benefit ads even if
    # the body copy mentions a clinical study.
    (("carousel", "feature", "benefit", "callout", "explainer", "educational",
      "editorial", "infographic"),
        "features-and-benefits"),
    # facts-and-stats is the narrow case: the ad LEADS with a number or
    # statistic, not a carousel that happens to reference a study.
    (("stat", "%", "percent", "data point", "study leads", "research-driven hero"),
        "facts-and-stats"),
]

STANDARD_FALLBACK = "features-and-benefits"


# ─── Mechanic → psychology folder mapping ───────────────────────────────────


MECHANIC_TO_PSYCHOLOGY: dict[str, str] = {
    # Rational / credibility levers — competence
    "first_principles_plus_loss_aversion": "competence",
    "authority_borrowing_plus_data_insight": "competence",
    "counterintuitive_insight_plus_specificity": "competence",
    # Intrigue / pattern-break levers — engagement
    "pattern_disruption_plus_hidden_truth": "engagement",
    "micro_story_plus_suspense": "engagement",
    "curiosity_plus_reverse_psychology": "engagement",
    "gamification_plus_time_sensitive_offer": "engagement",
    # Tribal / kinship levers — belonging
    "tribal_belonging_plus_vulnerability": "belonging",
    "anonymity_plus_social_proof": "belonging",
    # Reframe + warmth levers — nurturance
    "reframing_perception_plus_emotional_trigger": "nurturance",
    # Threat / consequence levers — security
    "what_if_scenario_plus_pain_amplification": "security",
    # Aspiration / status — achievement / esteem
    "contrast_plus_aspirational_identity": "achievement",
    "status_signaling_plus_open_loop": "esteem",
    # High-arousal transformation — empowerment
    "shock_factor_plus_transformation_shortcut": "empowerment",
}

PSYCHOLOGY_FALLBACK = "competence"


# ─── Result ─────────────────────────────────────────────────────────────────


@dataclass
class SwipeMatch:
    """Reference images chosen for a brief, plus the labels that picked them."""

    standard_folder: str = ""
    standard_images: list[Path] = field(default_factory=list)
    psychology_folder: str = ""
    psychology_images: list[Path] = field(default_factory=list)

    @property
    def all_images(self) -> list[Path]:
        return self.standard_images + self.psychology_images

    def to_prompt_block(self) -> str:
        """Render the match as a labeled block for inclusion in the NB2 prompt."""
        if not self.all_images:
            return ""
        lines = ["STYLE REFERENCE IMAGES (passed alongside the product image):"]
        if self.standard_images:
            lines.append(
                f"  - LAYOUT/COMPOSITION refs from `{self.standard_folder}` "
                f"({len(self.standard_images)} image(s)). Match the layout pattern, "
                "pill styling, type treatment, element placement — DO NOT copy "
                "their products."
            )
        if self.psychology_images:
            lines.append(
                f"  - VIBE/TONE ref from `{self.psychology_folder}` "
                f"({len(self.psychology_images)} image(s)). Match the emotional "
                "register and mood — DO NOT copy the visuals literally."
            )
        return "\n".join(lines)


# ─── Public API ─────────────────────────────────────────────────────────────


def pick_standard_folder(visual_format: str) -> str:
    """Pick the best-matching standard/ folder for a visual_format string."""
    fmt = (visual_format or "").lower()
    for keywords, folder in STANDARD_KEYWORDS:
        if any(kw in fmt for kw in keywords):
            return folder
    return STANDARD_FALLBACK


def pick_psychology_folder(creative_mechanic: str) -> str:
    """Pick the best-matching psychology/ folder for a mechanic name."""
    return MECHANIC_TO_PSYCHOLOGY.get(creative_mechanic, PSYCHOLOGY_FALLBACK)


def _list_images(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        p for p in folder.iterdir()
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS
    )


def match_for_brief(
    visual_format: str,
    creative_mechanic: str,
    *,
    n_standard: int = 2,
    n_psychology: int = 1,
    seed: int | None = None,
) -> SwipeMatch:
    """Resolve a brief's preferred standard + psychology folders, then sample
    up to `n_standard` + `n_psychology` reference images.

    Deterministic when `seed` is provided — useful for reproducible runs.
    Falls back to the catch-all folder when the brief's first-choice folder
    is empty.
    """
    rng = random.Random(seed) if seed is not None else random

    standard_folder = pick_standard_folder(visual_format)
    psychology_folder = pick_psychology_folder(creative_mechanic)

    standard_pool = _list_images(STANDARD_ROOT / standard_folder)
    if not standard_pool and standard_folder != STANDARD_FALLBACK:
        # Folder exists but is empty — back off to the catch-all
        standard_folder = STANDARD_FALLBACK
        standard_pool = _list_images(STANDARD_ROOT / standard_folder)

    psychology_pool = _list_images(PSYCHOLOGY_ROOT / psychology_folder)
    if not psychology_pool and psychology_folder != PSYCHOLOGY_FALLBACK:
        psychology_folder = PSYCHOLOGY_FALLBACK
        psychology_pool = _list_images(PSYCHOLOGY_ROOT / psychology_folder)

    standard_pick = rng.sample(standard_pool, min(n_standard, len(standard_pool))) if standard_pool else []
    psych_pick = rng.sample(psychology_pool, min(n_psychology, len(psychology_pool))) if psychology_pool else []

    return SwipeMatch(
        standard_folder=standard_folder,
        standard_images=standard_pick,
        psychology_folder=psychology_folder,
        psychology_images=psych_pick,
    )
