"""Meta ad naming taxonomy — campaign name builder.

Convention (Slot 7 = Hook, slot 8 = Copy):

    [Brand]_[Persona]_[Angle]_[Format]_[Style]_[Source]_[Hook]_[Copy]_[Offer]_[Iteration]_[Date]

Example:
    SK_ProbioticBurnedPaige_Testimonial_UGC_Venn_Remix_H22_C00_NONE_V1_260515

Rules enforced here:
  1. Every ad has every slot — empty values become defined fallback codes
     ('NONE', 'NA', etc.)
  2. Underscores delimit slots; multi-word values use CamelCase.
  3. CamelCase preserves no internal punctuation, spaces, or hyphens.
  4. Hook codes (H##) are sourced from hook_library.yaml at repo root.
  5. Date is YYMMDD (six digits, no separators).

The Copy slot defaults to C00 (placeholder) — the copy library is built
manually outside this system, per project convention.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from models.avatar import CustomerAvatar
    from models.brand import Brand
    from models.brief import CreativeBrief
    from strategy.ad_remixer import AdAnalysis

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOOK_LIBRARY_PATH = REPO_ROOT / "hook_library.yaml"


# ─── Mapping tables ─────────────────────────────────────────────────────────


# ad_type (8-bucket taxonomy from strategy/ad_classifier.py) → Angle slot code
AD_TYPE_TO_ANGLE: dict[str, str] = {
    "testimonial-review": "Testimonial",
    "us-vs-them": "UsVsThem",
    "before-and-after": "BeforeAfter",
    "features-and-benefits": "Features",
    "promotion-and-discount": "Promotion",
    "ugc": "UGC",
    "facts-and-stats": "Stats",
    "reasons-why": "ReasonsWhy",
    "other": "Mixed",
}


# Substring → Format slot code. Checked in order; first match wins.
# Format is the TOP-LEVEL production category (how the ad reads at a glance).
FORMAT_SUBSTRINGS: list[tuple[str, str]] = [
    ("ugc", "UGC"),
    ("carousel", "Carousel"),
    ("video", "Video"),
    ("split", "Static"),
    ("text-on-product", "Static"),
    ("text on product", "Static"),
    ("static", "Static"),
    ("photo", "Static"),
    ("image", "Static"),
]


# Substring → Style slot code. Style = sub-format execution within the Format.
# Checked in order; first match wins. Defaults to "Mixed" if nothing matches.
STYLE_SUBSTRINGS: list[tuple[str, str]] = [
    ("venn", "Venn"),
    ("whiteboard", "Whiteboard"),
    ("split-screen", "SplitScreen"),
    ("split screen", "SplitScreen"),
    ("side-by-side", "SideBySide"),
    ("before/after", "BeforeAfter"),
    ("before and after", "BeforeAfter"),
    ("talking head", "TalkingHead"),
    ("mirror selfie", "MirrorSelfie"),
    ("mirror-selfie", "MirrorSelfie"),
    ("comparison", "Comparison"),
    ("testimonial", "Testimonial"),
    ("flat lay", "FlatLay"),
    ("hero", "ProductHero"),
    ("callout", "Callouts"),
    ("3x3", "Grid3x3"),
    ("grid", "Grid"),
    ("podcast", "Podcast"),
    ("editorial", "Editorial"),
    ("cinematic", "Cinematic"),
    ("portrait", "Portrait"),
]


# Diversity-matrix hook_type (from strategy/angle_multiplier.DIVERSITY_MATRIX)
# → list of H## candidates in hook_library.yaml. First candidate is preferred.
# These are scaffolding: the hook fuzzy-matcher tries text-similarity first
# and falls back to this mapping when no near-text match exists.
HOOK_TYPE_TO_CANDIDATES: dict[str, list[str]] = {
    "Surprising Stat": ["H16", "H07", "H19"],
    "Story / Result": ["H10", "H11", "H20"],
    "FOMO / Urgency": ["H09"],
    "Curiosity Gap": ["H01", "H04"],
    "Direct Address / Call-out": ["H17", "H22"],
    "Contrast / Enemy": ["H12", "H13", "H03"],
    "Question": ["H21"],
    "Pattern Interrupt": ["H05"],
    "Controversial": ["H14"],
    "Problem-Solution": ["H22", "H23"],
    # Hook tactics that don't map directly use these:
    "Social Proof": ["H06", "H07"],
    "Authority": ["H08", "H18", "H24"],
    "Transformation": ["H10", "H11"],
}


# Source slot — derived from how the ad was generated.
SOURCE_VALUES: frozenset[str] = frozenset({"Remix", "AI", "NA"})


# ─── Slot builders ──────────────────────────────────────────────────────────


def _camel_case(text: str, *, max_chars: int = 40) -> str:
    """Convert 'Probiotic-Burned Paige' → 'ProbioticBurnedPaige'.

    Strips non-alphanumeric characters, splits on whitespace/hyphens/
    underscores, capitalizes each segment, joins. Caps at max_chars to
    keep ad names within Meta's display limits."""
    if not text:
        return ""
    # Replace common separators with spaces, then split
    cleaned = re.sub(r"[\-_]+", " ", text)
    # Remove parenthetical content (e.g. "Founder (CEO)" → "Founder")
    cleaned = re.sub(r"\([^)]*\)", "", cleaned)
    parts = re.split(r"\s+", cleaned)
    cameled: list[str] = []
    for p in parts:
        # Keep only alphanumeric
        alnum = re.sub(r"[^A-Za-z0-9]", "", p)
        if not alnum:
            continue
        # If part is already mixed-case (e.g. iPhone, McDonald), preserve it
        if any(c.isupper() for c in alnum[1:]):
            cameled.append(alnum)
        else:
            cameled.append(alnum[0].upper() + alnum[1:].lower() if alnum else "")
    joined = "".join(cameled)
    return joined[:max_chars] if joined else "Unknown"


def _brand_code(brand: "Brand") -> str:
    """Extract the brand code. Raises if missing."""
    code = (getattr(brand, "code", None) or "").strip()
    if not code:
        raise ValueError(
            f"Brand '{brand.name}' has no 'code' field in brand.yaml. "
            "Add a code (e.g. 'code: SK' for SecondKind) before generating "
            "campaign names. See docs/naming-conventions.md if it exists."
        )
    # Sanitize: alphanumeric only, no spaces or punctuation
    sanitized = re.sub(r"[^A-Za-z0-9]", "", code)
    if not sanitized:
        raise ValueError(
            f"Brand code '{code}' contains no alphanumeric characters."
        )
    return sanitized


def _persona_code(brief: "CreativeBrief") -> str:
    """Build the Persona slot from brief.persona — CamelCase, capped."""
    persona = (brief.persona or "").strip()
    if not persona:
        return "NA"
    return _camel_case(persona, max_chars=30)


def _angle_code(brief: "CreativeBrief", analysis: "AdAnalysis | None") -> str:
    """Build the Angle slot. Prefers analysis.ad_type, falls back to
    brief.framework + hook_tactic. Returns 'Mixed' if no signal."""
    if analysis is not None and analysis.ad_type:
        code = AD_TYPE_TO_ANGLE.get(analysis.ad_type)
        if code:
            return code
    # Fallback: derive from brief
    hook_tactic = (brief.hook_tactic or "").lower()
    if "social proof" in hook_tactic or "testimonial" in hook_tactic:
        return "Testimonial"
    if "before" in hook_tactic and "after" in hook_tactic:
        return "BeforeAfter"
    if "stat" in hook_tactic or "data" in hook_tactic:
        return "Stats"
    if "comparison" in hook_tactic or "versus" in hook_tactic or "vs" in hook_tactic:
        return "UsVsThem"
    return "Mixed"


def _format_code(brief: "CreativeBrief", analysis: "AdAnalysis | None") -> str:
    """Build the Format slot from creative_mechanic + visual_format."""
    candidates: list[str] = []
    if analysis is not None:
        candidates.append((analysis.visual_format or "").lower())
        candidates.append((analysis.creative_mechanic or "").lower())
    candidates.append((brief.visual_format or "").lower())
    candidates.append((brief.creative_mechanic or "").lower())
    haystack = " | ".join(c for c in candidates if c)
    for substring, code in FORMAT_SUBSTRINGS:
        if substring in haystack:
            return code
    return "Static"  # safe default — most ads are static images


def _style_code(brief: "CreativeBrief", analysis: "AdAnalysis | None") -> str:
    """Build the Style slot from creative_mechanic + visual_format."""
    candidates: list[str] = []
    if analysis is not None:
        candidates.append((analysis.creative_mechanic or "").lower())
        candidates.append((analysis.visual_format or "").lower())
    candidates.append((brief.creative_mechanic or "").lower())
    candidates.append((brief.visual_format or "").lower())
    haystack = " | ".join(c for c in candidates if c)
    for substring, code in STYLE_SUBSTRINGS:
        if substring in haystack:
            return code
    return "Mixed"


def _source_code(source: str) -> str:
    """Pass through Source — must be one of SOURCE_VALUES."""
    if not source:
        return "NA"
    candidate = re.sub(r"[^A-Za-z0-9]", "", source)
    if candidate in SOURCE_VALUES:
        return candidate
    # Best-effort title-case fallback
    if candidate.lower() == "remix":
        return "Remix"
    if candidate.lower() == "ai":
        return "AI"
    return "NA"


def _offer_code(offer: str) -> str:
    """Sanitize the Offer slot: alphanumeric uppercase, capped at 12 chars.
    Default 'NONE' for empty input."""
    if not offer or not offer.strip():
        return "NONE"
    sanitized = re.sub(r"[^A-Za-z0-9]", "", offer).upper()
    if not sanitized:
        return "NONE"
    return sanitized[:12]


def _iteration_code(version: int | str | None) -> str:
    """Build the Iteration slot — V1 (original), V2/V3/V4... for refinements.

    Accepts int (1, 2, 3...) or string ('V1', 'v2', '2'). Returns the
    standardized 'V<N>' form. Defaults to V1."""
    if version is None:
        return "V1"
    if isinstance(version, int):
        return f"V{version}"
    s = str(version).strip().upper()
    if not s:
        return "V1"
    if s.startswith("V"):
        s = s[1:]
    try:
        n = int(s)
        return f"V{n}"
    except ValueError:
        return "V1"


def _date_code(date: datetime | str | None) -> str:
    """Build the Date slot — YYMMDD. Defaults to today."""
    if date is None:
        date = datetime.now()
    if isinstance(date, str):
        # Try to parse common formats
        for fmt in ("%Y-%m-%d_%H%M%S", "%Y-%m-%d", "%Y%m%d", "%y%m%d"):
            try:
                date = datetime.strptime(date, fmt)
                break
            except ValueError:
                continue
        if isinstance(date, str):
            # Couldn't parse; use today
            date = datetime.now()
    return date.strftime("%y%m%d")


# ─── Hook library matching ──────────────────────────────────────────────────


def _load_hook_library(library_path: Path | None = None) -> list[dict]:
    """Load hook_library.yaml. Returns the list of hook entries."""
    path = library_path or DEFAULT_HOOK_LIBRARY_PATH
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    if isinstance(data, dict):
        hooks = data.get("hooks") or []
    elif isinstance(data, list):
        hooks = data
    else:
        return []
    return [h for h in hooks if isinstance(h, dict) and h.get("code")]


def _hook_text_similarity(brief_hook: str, library_text: str) -> float:
    """Rough text similarity — token overlap (Jaccard-style) on normalized
    words, ignoring stop words and library placeholders.

    Returns 0.0-1.0 where 1.0 = perfect overlap. Cheap, no LLM."""
    STOP = {
        "a", "an", "the", "of", "to", "is", "are", "was", "were", "and",
        "or", "but", "if", "in", "on", "at", "for", "with", "this", "that",
        "my", "your", "our", "their", "i", "you", "we", "they", "it",
    }

    def _tokenize(s: str) -> set[str]:
        # Remove placeholders [foo bar]
        s = re.sub(r"\[[^\]]*\]", "", s.lower())
        # Keep alphanumeric only
        tokens = re.findall(r"[a-z0-9]+", s)
        return {t for t in tokens if t not in STOP and len(t) > 2}

    a = _tokenize(brief_hook)
    b = _tokenize(library_text)
    if not a or not b:
        return 0.0
    overlap = len(a & b)
    union = len(a | b)
    return overlap / union if union else 0.0


def _hook_code(
    brief: "CreativeBrief",
    library: list[dict] | None = None,
    library_path: Path | None = None,
    text_match_threshold: float = 0.4,
) -> str:
    """Find the best H## for a brief's hook.

    Strategy:
      1. Compute text similarity against every library entry.
         If max similarity ≥ threshold → return that entry's code.
      2. Else use brief.hook_type to look up candidates in
         HOOK_TYPE_TO_CANDIDATES; return the first candidate that exists
         in the library.
      3. Else return 'H00' (placeholder code reserved for unmatched).

    No auto-append in Phase 1 — that requires write coordination across
    parallel remix runs. Operators can manually inspect H00 outputs and
    promote them to library entries."""
    if library is None:
        library = _load_hook_library(library_path)
    if not library or not brief.hook:
        return "H00"

    # 1. Text similarity match
    best_score = 0.0
    best_code = ""
    for entry in library:
        score = _hook_text_similarity(brief.hook, entry.get("text", ""))
        if score > best_score:
            best_score = score
            best_code = entry["code"]
    if best_score >= text_match_threshold and best_code:
        return best_code

    # 2. Diversity-matrix candidate fallback
    candidates = HOOK_TYPE_TO_CANDIDATES.get(brief.hook_type, [])
    library_codes = {h["code"] for h in library}
    for candidate in candidates:
        if candidate in library_codes:
            return candidate

    return "H00"


# ─── Top-level: build the full campaign name ────────────────────────────────


def build_campaign_name(
    brief: "CreativeBrief",
    brand: "Brand",
    *,
    analysis: "AdAnalysis | None" = None,
    offer: str = "NONE",
    iteration: int | str = 1,
    date: datetime | str | None = None,
    source: str = "Remix",
    copy_code: str = "C00",
    hook_library: list[dict] | None = None,
    hook_library_path: Path | None = None,
) -> str:
    """Build the 11-slot Meta ad campaign name for a brief.

    Convention:
      [Brand]_[Persona]_[Angle]_[Format]_[Style]_[Source]_[Hook]_[Copy]_[Offer]_[Iteration]_[Date]

    Example:
      SK_ProbioticBurnedPaige_Testimonial_UGC_Venn_Remix_H22_C00_NONE_V1_260515

    Arguments:
      brief — the CreativeBrief to name. Provides persona, hook, mechanic,
        format, and hook_type.
      brand — the Brand object. Must have a non-empty `code` field.
      analysis — the AdAnalysis (when available, e.g. from the remix
        flow). Adds high-fidelity Angle / Format / Style classification.
      offer — promotion code (e.g. 'FREESHIP'). Sanitized to alphanumeric
        uppercase, capped at 12 chars. 'NONE' for no-offer ads.
      iteration — refinement version number (1, 2, 3...) or 'V1'/'V2' form.
      date — datetime or string. Defaults to today (YYMMDD).
      source — how the ad was generated. One of: 'Remix', 'AI', 'NA'.
      copy_code — Copy slot. Defaults to C00 (placeholder; copy library
        is maintained manually).
      hook_library — pre-loaded list of hook entries. If None, loads from
        hook_library_path (default: hook_library.yaml at repo root).
      hook_library_path — optional override for the hook library file.

    Raises ValueError if brand.code is missing."""
    parts = [
        _brand_code(brand),
        _persona_code(brief),
        _angle_code(brief, analysis),
        _format_code(brief, analysis),
        _style_code(brief, analysis),
        _source_code(source),
        _hook_code(brief, library=hook_library, library_path=hook_library_path),
        copy_code,
        _offer_code(offer),
        _iteration_code(iteration),
        _date_code(date),
    ]
    return "_".join(parts)
