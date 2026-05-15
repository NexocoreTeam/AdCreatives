"""Ad Remixer — reverse-engineer a reference ad and remix it for your product.

Given a reference ad (local image OR Foreplay URL/ID), extract its strategic
DNA (ad-type, psychological levers, framework, creative mechanic, visual
format) plus its visual DNA, then produce N briefs that re-use the
reference's structure but vary across the client's personas × psychology
heuristics.

Pipeline:
  1. Analyze the reference → AdAnalysis (strategic + visual DNA)
  2. Load the client's avatars (one per persona)
  3. Pair each variation with (avatar, heuristic) — cycles avatars when
     variations > avatars, varies the lever each pass, skips weak heuristics
  4. Single Sonnet call generates N angles sharing the locked structure
  5. Wrap angles in CreativeBrief schema, source_insight="ad_remix"
  6. Run each brief through prompt_from_brief() → NB2 prompt
  7. Write everything under clients/<slug>/remixes/<timestamp>/

Reuses (no new strategic skills loaded — borrows the existing system prompt):
  - generators/reference_analyzer.analyze_reference_image — visual DNA
  - strategy/ad_classifier.CATEGORIES — 8-bucket ad-type taxonomy
  - strategy/foreplay_client.fetch_ad_by_id + download_asset — Foreplay fetch
  - strategy/angle_multiplier.ANGLE_SYSTEM — skill-loaded system prompt
  - models/avatar.HEURISTIC_NAMES — 9 valid lever names (snake_case)
  - generators/prompt_engine.prompt_from_brief — final NB2 prompt
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from generators.reference_analyzer import (
    ANALYSIS_PROMPT as VISUAL_DNA_PROMPT,
    ANALYSIS_SYSTEM as VISUAL_DNA_SYSTEM,
)
from models.avatar import HEURISTIC_NAMES, CustomerAvatar
from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.loader import load_brand, load_product
from models.product import Product
from strategy.ad_classifier import CATEGORIES as AD_TYPE_CATEGORIES
from strategy.angle_multiplier import ANGLE_SYSTEM
from strategy.foreplay_client import download_asset, fetch_ad_by_id
from strategy.llm import claude_complete, get_anthropic_client

CLIENTS_DIR = Path("clients")

# When the strategic analyzer can't pin a framework, fall back to this default
# per ad-type. Matches CopyFramework enum values in models/brief.py.
AD_TYPE_TO_FRAMEWORK: dict[str, str] = {
    "us-vs-them": "bab",
    "before-and-after": "bab",
    "testimonial-review": "fab",
    "features-and-benefits": "fab",
    "promotion-and-discount": "aida",
    "ugc": "pas",
    "facts-and-stats": "aida",
    "reasons-why": "fab",
    "other": "pas",
}

# Lever rotation when the analysis's psych_levers don't fill all variations.
# Each entry spans a distinct family of the diversity matrix so variations
# read as genuinely different cognitive levers, not surface rewordings.
DEFAULT_LEVER_ROTATION: list[str] = [
    "social_proof",          # tribe / credibility
    "authority_bias",        # expertise / data
    "scarcity",              # loss aversion / FOMO
    "framing_effect",        # contrast / reframe
    "salience_bias",         # curiosity / pattern interrupt
    "effect_heuristic",      # emotional appeal / story
    "processing_fluency",    # clarity / simplicity
    "goal_gradient",         # progress / momentum
    "temporal_discounting",  # urgency
]


# ─── Data model ─────────────────────────────────────────────────────────────


@dataclass
class AdAnalysis:
    """Strategic + visual DNA extracted from a reference ad."""

    # Strategic DNA
    ad_type: str
    ad_type_confidence: float
    ad_type_reasoning: str
    psych_levers: list[str]
    dominant_emotion: str
    framework: str
    hook_tactic: str
    creative_mechanic: str
    visual_format: str
    awareness_level: str
    pain_attacked: str
    enemy: str
    visible_copy: dict

    # Visual DNA (output of generators/reference_analyzer.analyze_reference_image)
    visual: dict

    # Source provenance
    source_type: str           # 'local' | 'foreplay'
    source_ref: str            # path | foreplay ad_id
    foreplay_metadata: dict = field(default_factory=dict)

    def to_yaml_dict(self) -> dict:
        return asdict(self)


# ─── Strategic analysis prompts ─────────────────────────────────────────────


_AD_TYPE_LINES = "\n".join(
    f"- {key}: {desc}" for key, desc in AD_TYPE_CATEGORIES.items()
)
_HEURISTIC_LINES = "\n".join(f"- {h}" for h in sorted(HEURISTIC_NAMES))


def _strategic_analysis_system() -> str:
    return f"""You are an expert ad strategist. Given an advertisement image (and
optional pre-extracted copy), extract its STRATEGIC DNA so the ad can be
remixed for a different product.

Classify against these fixed taxonomies. Use the EXACT key names — they are
validated downstream.

AD TYPE (pick exactly one):
{_AD_TYPE_LINES}
- other: doesn't fit the 8 above

PSYCHOLOGICAL LEVERS (pick 1-3 the ad primarily activates, snake_case names only):
{_HEURISTIC_LINES}

COPY FRAMEWORK (pick one): pas | aida | bab | fab | four_cs | quest | pastor | slap

AWARENESS LEVEL (pick one): unaware | problem_aware | solution_aware | product_aware | most_aware

For creative_mechanic and visual_format, use phrasing from Motion's
creative-mechanics and visual-formats libraries (e.g. 'Split-screen comparison',
'Before/After Split', 'Talking Head Confession', 'UGC Static',
'Text-on-product photo', 'Side-by-side product comparison').

Output VALID YAML only — no markdown fences, no commentary."""


def _strategic_analysis_prompt(
    *,
    extracted_copy: dict | None = None,
    ad_type_hint: str = "",
    emotion_hint: str = "",
) -> str:
    hint_parts: list[str] = []
    if extracted_copy:
        hint_parts.append(
            "PRE-EXTRACTED COPY (don't re-read from the image, use these verbatim):"
        )
        hint_parts.append(f"  headline: {extracted_copy.get('headline', '')}")
        hint_parts.append(f"  description: {extracted_copy.get('description', '')}")
        hint_parts.append(f"  cta: {extracted_copy.get('cta', '')}")
        hint_parts.append("")
    if ad_type_hint:
        hint_parts.append(f"PRIOR (Foreplay classifier): ad_type ≈ {ad_type_hint}")
    if emotion_hint:
        hint_parts.append(f"PRIOR (Foreplay classifier): dominant_emotion ≈ {emotion_hint}")
    if hint_parts:
        hint_parts.append("")
    hints = "\n".join(hint_parts)

    return f"""{hints}Analyze this ad and return YAML with this exact structure:

ad_type: "<one of the 8 keys or 'other'>"
ad_type_confidence: <0.0-1.0>
ad_type_reasoning: "<one sentence>"

psych_levers:
  - "<heuristic_name>"
  - "<heuristic_name>"

dominant_emotion: "<natural-language label, e.g. 'frustration', 'aspiration', 'relief'>"

framework: "<pas|aida|bab|fab|four_cs|quest|pastor|slap>"

hook_tactic: "<specific tactic, e.g. 'Specific stat with a story', 'Pattern interrupt with a confession'>"

creative_mechanic: "<from Motion's creative-mechanics library>"

visual_format: "<from Motion's visual-formats library>"

awareness_level: "<unaware|problem_aware|solution_aware|product_aware|most_aware>"

pain_attacked: "<the specific pain or status quo this ad attacks>"

enemy: "<for us-vs-them: the competitor or status-quo being attacked. Empty string for other ad types.>"

visible_copy:
  headline: "<visible headline text>"
  description: "<short body copy if visible>"
  cta: "<call-to-action button label>"
  callouts:
    - "<visible callout 1>"
    - "<visible callout 2>"
"""


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first = text.find("\n")
        if first != -1:
            text = text[first + 1:]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()
    return text


def _parse_strategic_yaml(text: str) -> dict:
    """Parse the strategic-analysis LLM output. Tolerates code fences and
    minor format drift; normalizes ad_type and psych_levers against the
    fixed taxonomies."""
    body = _strip_code_fences(text)
    data = yaml.safe_load(body) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Strategic analysis returned non-mapping YAML ({type(data).__name__}): "
            f"{body[:200]!r}"
        )

    # Normalize ad_type
    raw_at = str(data.get("ad_type") or "other").strip().lower()
    if raw_at not in AD_TYPE_CATEGORIES and raw_at != "other":
        norm = raw_at.replace("_", "-").replace(" ", "-")
        raw_at = norm if norm in AD_TYPE_CATEGORIES else "other"
    data["ad_type"] = raw_at

    # Filter psych_levers to the 9 valid heuristic names, keep first 3
    raw_levers = data.get("psych_levers") or []
    valid_levers = [str(h).strip() for h in raw_levers if str(h).strip() in HEURISTIC_NAMES]
    data["psych_levers"] = valid_levers[:3]

    return data


# ─── Local-image analyzer ───────────────────────────────────────────────────

_CLAUDE_VISION_MODEL = "claude-sonnet-4-6"

# File-signature → MIME map. We detect MIME from the actual bytes because
# Anthropic strictly validates that the declared media_type matches the
# image content. Trusting the file extension alone fails when someone
# uploads e.g. a PNG saved with a .jpg extension.
_EXT_MIME_FALLBACK: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def _detect_image_mime(raw_bytes: bytes, ext_hint: str = "") -> str:
    """Detect image MIME type from magic bytes, falling back to the
    file-extension hint if the signature is unrecognized.

    Magic bytes:
      PNG:  89 50 4E 47 0D 0A 1A 0A
      JPEG: FF D8 FF
      GIF:  47 49 46 38 (37|39) 61    ('GIF87a' / 'GIF89a')
      WEBP: 52 49 46 46 ?? ?? ?? ?? 57 45 42 50  ('RIFF....WEBP')
    """
    header = raw_bytes[:12]
    if len(header) >= 8 and header[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(header) >= 3 and header[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(header) >= 6 and header[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if (
        len(header) >= 12
        and header[:4] == b"RIFF"
        and header[8:12] == b"WEBP"
    ):
        return "image/webp"
    # Unknown signature — fall back to the extension hint, then JPEG.
    return _EXT_MIME_FALLBACK.get(ext_hint.lower(), "image/jpeg")


def _claude_vision_local(
    *,
    prompt: str,
    image_path: Path,
    system: str,
    max_tokens: int = 2048,
) -> str:
    """Claude vision on a LOCAL image file using base64 source.

    Used instead of strategy.llm.claude_vision because that helper takes a URL
    and we're working with a path on disk. Keeps the dependency on the
    Anthropic SDK only (no OpenAI key needed)."""
    import base64

    with open(image_path, "rb") as f:
        raw_bytes = f.read()
    media_type = _detect_image_mime(raw_bytes, image_path.suffix.lower())
    data = base64.standard_b64encode(raw_bytes).decode()

    client = get_anthropic_client()
    content = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": data,
            },
        },
        {"type": "text", "text": prompt},
    ]
    response = client.messages.create(
        model=_CLAUDE_VISION_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": content}],
    )
    return response.content[0].text


def _claude_visual_dna(image_path: Path) -> dict:
    """Visual DNA extraction via Claude vision. Reuses the prompt/system from
    generators/reference_analyzer.py so output shape matches that module."""
    raw = _claude_vision_local(
        prompt=VISUAL_DNA_PROMPT,
        image_path=image_path,
        system=VISUAL_DNA_SYSTEM,
    )
    body = _strip_code_fences(raw)
    data = yaml.safe_load(body)
    if not isinstance(data, dict):
        return {}
    return data


def analyze_local_image(path: str | Path) -> AdAnalysis:
    """Analyze a reference ad from a local file. Two vision calls:
    one for visual DNA, one for strategic DNA. Both via Claude vision."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Reference image not found: {p}")

    visual = _claude_visual_dna(p)

    raw = _claude_vision_local(
        prompt=_strategic_analysis_prompt(),
        image_path=p,
        system=_strategic_analysis_system(),
    )
    strategic = _parse_strategic_yaml(raw)

    return _build_analysis(
        strategic=strategic,
        visual=visual,
        source_type="local",
        source_ref=str(p),
        foreplay_metadata={},
    )


# ─── Foreplay analyzer ──────────────────────────────────────────────────────


def _extract_foreplay_id(url_or_id: str) -> str:
    """Extract a Foreplay numeric ad ID from a URL or accept a raw ID."""
    s = (url_or_id or "").strip()
    if not s:
        raise ValueError("Empty foreplay URL/ID")
    if s.isdigit():
        return s
    m = re.search(r"/(?:ad|ads)/(\d+)", s)
    if m:
        return m.group(1)
    m = re.search(r"(\d{6,})", s)
    if m:
        return m.group(1)
    raise ValueError(
        f"Could not extract a Foreplay ad ID from '{url_or_id}'. "
        "Pass a Foreplay URL like https://app.foreplay.co/ad/12345 or a raw numeric ID."
    )


def _foreplay_top_content_filter(content_filter: dict) -> str:
    """Map Foreplay's content_filter top key to our 8-bucket taxonomy.
    Returns empty string if no usable mapping."""
    if not content_filter:
        return ""
    try:
        top_key, _ = max(content_filter.items(), key=lambda kv: float(kv[1] or 0))
    except (ValueError, TypeError):
        return ""
    label = str(top_key).lower().replace("_", "-").replace(" ", "-")
    if label in AD_TYPE_CATEGORIES:
        return label
    aliases = {
        "social-proof": "testimonial-review",
        "testimonial": "testimonial-review",
        "comparison": "us-vs-them",
        "vs": "us-vs-them",
        "versus": "us-vs-them",
        "discount": "promotion-and-discount",
        "promotion": "promotion-and-discount",
        "sale": "promotion-and-discount",
        "stat": "facts-and-stats",
        "statistic": "facts-and-stats",
        "listicle": "reasons-why",
        "features": "features-and-benefits",
        "benefits": "features-and-benefits",
        "transformation": "before-and-after",
        "before-after": "before-and-after",
    }
    return aliases.get(label, "")


def _foreplay_top_emotion(emotional_drivers: dict) -> str:
    if not emotional_drivers:
        return ""
    try:
        top_key, _ = max(emotional_drivers.items(), key=lambda kv: float(kv[1] or 0))
    except (ValueError, TypeError):
        return ""
    return str(top_key).lower()


def analyze_foreplay(
    url_or_id: str,
    *,
    image_dest: Path | None = None,
) -> AdAnalysis:
    """Fetch a Foreplay ad and analyze it. Uses Foreplay's prebuilt
    content_filter and emotional_drivers as priors so we don't pay for a
    text-extraction vision pass."""
    ad_id = _extract_foreplay_id(url_or_id)
    fa = fetch_ad_by_id(ad_id)
    if fa is None:
        raise ValueError(f"Foreplay ad '{ad_id}' not found.")
    if not fa.primary_image_url:
        raise ValueError(f"Foreplay ad '{ad_id}' has no primary image URL.")

    if image_dest is None:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        image_dest = Path(tmp.name)
        tmp.close()
    download_asset(fa.primary_image_url, image_dest)

    visual = _claude_visual_dna(image_dest)

    pre_ad_type = _foreplay_top_content_filter(fa.content_filter)
    pre_emotion = _foreplay_top_emotion(fa.emotional_drivers)

    raw = _claude_vision_local(
        prompt=_strategic_analysis_prompt(
            extracted_copy={
                "headline": fa.headline,
                "description": fa.description,
                "cta": fa.cta_title or fa.cta_type,
            },
            ad_type_hint=pre_ad_type,
            emotion_hint=pre_emotion,
        ),
        image_path=image_dest,
        system=_strategic_analysis_system(),
    )
    strategic = _parse_strategic_yaml(raw)

    # If the model couldn't classify, fall back to Foreplay's prior
    if strategic["ad_type"] == "other" and pre_ad_type:
        strategic["ad_type"] = pre_ad_type
        strategic["ad_type_reasoning"] = (
            strategic.get("ad_type_reasoning") or "from foreplay content_filter prior"
        )

    # Preserve the pre-extracted Foreplay copy (more reliable than vision-OCR)
    foreplay_copy = {
        "headline": fa.headline,
        "description": fa.description,
        "cta": fa.cta_title or fa.cta_type,
        "callouts": (strategic.get("visible_copy") or {}).get("callouts", []),
    }
    strategic["visible_copy"] = foreplay_copy

    if not strategic.get("dominant_emotion") and pre_emotion:
        strategic["dominant_emotion"] = pre_emotion

    foreplay_metadata = {
        "ad_id": fa.ad_id,
        "foreplay_id": fa.foreplay_id,
        "brand": fa.name,
        "niches": fa.niches,
        "ai_keywords": (fa.ai_keywords or [])[:20],
        "image_url": fa.image_url,
        "started_running": fa.started_running,
        "live": fa.live,
        "publisher_platform": fa.publisher_platform,
        "image_local_path": str(image_dest),
    }

    return _build_analysis(
        strategic=strategic,
        visual=visual,
        source_type="foreplay",
        source_ref=ad_id,
        foreplay_metadata=foreplay_metadata,
    )


def _build_analysis(
    *,
    strategic: dict,
    visual: dict,
    source_type: str,
    source_ref: str,
    foreplay_metadata: dict,
) -> AdAnalysis:
    """Assemble an AdAnalysis with defensive defaults for every field."""
    ad_type = strategic.get("ad_type") or "other"
    framework = strategic.get("framework") or AD_TYPE_TO_FRAMEWORK.get(ad_type, "pas")
    return AdAnalysis(
        ad_type=ad_type,
        ad_type_confidence=float(strategic.get("ad_type_confidence") or 0.7),
        ad_type_reasoning=str(strategic.get("ad_type_reasoning") or ""),
        psych_levers=list(strategic.get("psych_levers") or []),
        dominant_emotion=str(strategic.get("dominant_emotion") or ""),
        framework=str(framework).lower(),
        hook_tactic=str(strategic.get("hook_tactic") or ""),
        creative_mechanic=str(strategic.get("creative_mechanic") or ""),
        visual_format=str(strategic.get("visual_format") or ""),
        awareness_level=str(strategic.get("awareness_level") or "problem_aware"),
        pain_attacked=str(strategic.get("pain_attacked") or ""),
        enemy=str(strategic.get("enemy") or ""),
        visible_copy=dict(strategic.get("visible_copy") or {}),
        visual=visual,
        source_type=source_type,
        source_ref=source_ref,
        foreplay_metadata=foreplay_metadata,
    )


# ─── Avatar loading + lever pairing ─────────────────────────────────────────


def _load_competitive_gaps(
    client_slug: str,
    clients_dir: Path | None = None,
) -> dict | None:
    """Load competitive-gaps.yaml for a client if it exists and has a
    'synthesis' section. Returns None otherwise.

    clients_dir defaults to CLIENTS_DIR — overridable for testing."""
    base = clients_dir if clients_dir is not None else CLIENTS_DIR
    path = base / client_slug / "research" / "competitive-gaps.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict) and data.get("synthesis"):
        return data
    return None


def _load_client_avatars(client_slug: str) -> list[CustomerAvatar]:
    """Load all avatars for a client. Prefers clients/<slug>/avatars/*.yaml
    (multi-persona), falls back to legacy clients/<slug>/avatar.yaml."""
    avatars_dir = CLIENTS_DIR / client_slug / "avatars"
    if avatars_dir.exists():
        avatars: list[CustomerAvatar] = []
        for path in sorted(avatars_dir.glob("*.yaml")):
            if path.name.startswith("_") or path.name.endswith(".bak"):
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            avatars.append(CustomerAvatar(**data))
        if avatars:
            return avatars

    single = CLIENTS_DIR / client_slug / "avatar.yaml"
    if single.exists():
        data = yaml.safe_load(single.read_text(encoding="utf-8"))
        return [CustomerAvatar(**data)]

    raise FileNotFoundError(
        f"No avatars found for '{client_slug}'. "
        f"Expected {avatars_dir}/*.yaml or {single}. "
        f"Run `adc personas --client {client_slug}` first."
    )


def _select_avatar_lever_pairs(
    avatars: list[CustomerAvatar],
    variations: int,
    analysis_levers: list[str],
) -> list[tuple[CustomerAvatar, str]]:
    """Pair each variation with (avatar, heuristic).

    Cycles avatars when variations > len(avatars). Lever priority per pair:
      1. Avatar's dominant_heuristics that ALSO appear in analysis_levers
      2. Avatar's other dominant_heuristics
      3. analysis_levers not already used for this avatar
      4. DEFAULT_LEVER_ROTATION

    Always skips levers in avatar.psychology_profile.weak_heuristics. Falls
    back to DEFAULT_LEVER_ROTATION even if it means reusing a lever across
    avatars (never reuses within the same avatar's slot list)."""
    if not avatars:
        raise ValueError("No avatars provided for lever pairing")
    if variations < 1:
        raise ValueError(f"variations must be ≥ 1, got {variations}")

    pairs: list[tuple[CustomerAvatar, str]] = []
    used_per_avatar: dict[str, set[str]] = {}

    for i in range(variations):
        avatar = avatars[i % len(avatars)]
        key = avatar.name or avatar.demographic
        used = used_per_avatar.setdefault(key, set())

        weak: set[str] = set()
        dominant: list[str] = []
        if avatar.psychology_profile:
            if avatar.psychology_profile.weak_heuristics:
                weak = {h.heuristic for h in avatar.psychology_profile.weak_heuristics}
            dominant = [h.heuristic for h in avatar.psychology_profile.dominant_heuristics]

        candidates: list[str] = []
        candidates.extend(h for h in dominant if h in analysis_levers and h not in candidates)
        candidates.extend(h for h in dominant if h not in candidates)
        candidates.extend(h for h in analysis_levers if h not in candidates)
        candidates.extend(h for h in DEFAULT_LEVER_ROTATION if h not in candidates)

        selected: str | None = None
        for lever in candidates:
            if lever in used or lever in weak:
                continue
            selected = lever
            break
        if selected is None:
            # All candidates filtered. Pick the first non-weak default,
            # even if we already used it for this avatar.
            for lever in DEFAULT_LEVER_ROTATION:
                if lever not in weak:
                    selected = lever
                    break
        if selected is None:
            # Pathological case: every heuristic is weak. Use first default anyway.
            selected = DEFAULT_LEVER_ROTATION[0]

        pairs.append((avatar, selected))
        used.add(selected)

    return pairs


# ─── Remix angle generation ─────────────────────────────────────────────────


def _select_fidelity_tiers(
    variations: int,
    max_high: int = 2,
    max_medium: int = 2,
) -> list[str]:
    """Distribute fidelity tiers across N variations.

    Default: 2 high (mimic the reference's visual style closely — same
    setting/person/background/typography), then up to 2 medium (small
    persona-tuned variation in mood/accent), then any remainder as low
    (more creative variation, only the mechanic + format are locked).

    For 5 variations the default produces: ["high", "high", "medium",
    "medium", "low"]. Override max_high / max_medium to change the mix."""
    if variations < 1:
        raise ValueError(f"variations must be ≥ 1, got {variations}")
    if max_high < 0 or max_medium < 0:
        raise ValueError("max_high and max_medium must be non-negative")

    tiers: list[str] = []
    for i in range(variations):
        if i < max_high:
            tiers.append("high")
        elif i < max_high + max_medium:
            tiers.append("medium")
        else:
            tiers.append("low")
    return tiers


def _format_reference_style_block(analysis: AdAnalysis) -> str:
    """Format the reference's visual DNA into a 'must-mimic' block for the
    remix prompt. Used for high-fidelity variations to keep them close to
    the reference's exact look (setting, person, typography, background)."""
    visual = analysis.visual or {}
    parts: list[str] = ["REFERENCE VISUAL STYLE (high-fidelity variations MUST mimic this):"]

    people = visual.get("people") or {}
    if people.get("present"):
        desc = (people.get("description") or "").strip()
        rel = (people.get("relationship_to_product") or "").strip()
        parts.append(f"  - PERSON in frame: yes — {desc}")
        if rel:
            parts.append(f"    relationship to product: {rel}")
    else:
        parts.append("  - PERSON in frame: no — product stands alone")

    style = visual.get("visual_style") or {}
    palette = style.get("color_palette") or {}
    bg = palette.get("background")
    if bg:
        parts.append(f"  - Background color: {bg}")
    lighting = style.get("lighting")
    if lighting:
        parts.append(f"  - Lighting: {lighting}")
    mood = style.get("mood")
    if mood:
        parts.append(f"  - Mood: {mood}")
    texture = style.get("texture")
    if texture:
        parts.append(f"  - Texture / surface: {texture}")

    typo = visual.get("typography_style") or {}
    heading = typo.get("heading_style")
    if heading:
        parts.append(f"  - Typography (headings): {heading}")
    treatment = typo.get("text_treatment")
    if treatment:
        parts.append(f"  - Text treatment: {treatment}")

    layout = visual.get("layout") or {}
    comp = layout.get("composition")
    if comp:
        parts.append(f"  - Composition: {comp}")

    overall = visual.get("overall") or {}
    energy = overall.get("energy")
    if energy:
        parts.append(f"  - Energy: {energy}")

    return "\n".join(parts)


def _compact_psychology_snapshot(profile) -> str:
    """Distill a PsychologyProfile into a 5-8 line scannable snapshot.

    No LLM call — pure formatting. Includes:
      - dominant heuristics with confidence + first sentence of ad_implications
      - weak heuristics with first sentence of `avoid`
      - emotional position (primary + secondary quadrants)
      - recommended Tether Lab pairings
      - banned pairings

    Returns "" if profile is None or empty, so callers can drop it cleanly."""
    if profile is None:
        return ""

    parts: list[str] = ["    persona_snapshot:"]
    rendered_any = False

    def _first_sentence(text: str, max_chars: int = 100) -> str:
        s = (text or "").strip()
        if not s:
            return ""
        head = s.split(".")[0].strip()
        if len(head) > max_chars:
            head = head[:max_chars].rstrip() + "..."
        return head

    if profile.dominant_heuristics:
        items = []
        for h in profile.dominant_heuristics[:3]:
            impl = _first_sentence(h.ad_implications)
            tail = f": {impl}" if impl else ""
            items.append(f"{h.heuristic} ({h.confidence}{tail})")
        parts.append(f"      wired_for: {' | '.join(items)}")
        rendered_any = True

    if profile.weak_heuristics:
        items = []
        for h in profile.weak_heuristics[:3]:
            avoid = _first_sentence(h.avoid)
            tail = f": {avoid}" if avoid else ""
            items.append(f"{h.heuristic}{tail}")
        parts.append(f"      wired_against: {' | '.join(items)}")
        rendered_any = True

    if profile.emotional_position:
        p = profile.emotional_position.primary
        s = profile.emotional_position.secondary
        p_rat = _first_sentence(p.rationale, max_chars=80)
        p_tail = f" ({p_rat})" if p_rat else ""
        parts.append(
            f"      emotional_anchor: primary {p.valence}/{p.intensity}{p_tail}"
            f"; secondary {s.valence}/{s.intensity}"
        )
        rendered_any = True

    if profile.recommended_prompt_pairings:
        items = [p.pairing for p in profile.recommended_prompt_pairings[:4]]
        parts.append(f"      pre_approved_mechanics: {', '.join(items)}")
        rendered_any = True

    if profile.avoid_pairings:
        items = [p.pairing for p in profile.avoid_pairings[:3]]
        parts.append(f"      banned_mechanics: {', '.join(items)}")
        rendered_any = True

    return "\n".join(parts) if rendered_any else ""


def _format_variation_block(
    index: int,
    avatar: CustomerAvatar,
    lever: str,
    fidelity_tier: str = "medium",
) -> str:
    """Format one variation's input block for the remix prompt.

    Includes top-level persona attributes, the locked lever and fidelity
    tier, and a distilled psychology snapshot (if the avatar has a
    psychology_profile). Trigger events and current solutions are also
    included as hook fodder."""
    pains = "; ".join(
        f"[{p.intensity}] {p.pain} — "
        f"\"{(p.customer_language[0] if p.customer_language else '')[:80]}\""
        for p in avatar.pain_points[:3]
    ) or "none provided"
    desires = "; ".join(d.desire for d in avatar.desires[:2]) or "none provided"
    objections = ", ".join(avatar.objections[:3]) or "none provided"
    triggers = "; ".join(avatar.trigger_events[:3]) or "none specified"
    solutions = ", ".join(avatar.current_solutions[:3]) or "none specified"
    lang = ", ".join(avatar.language_patterns[:2]) or "casual and direct"

    lines = [
        f"  Variation {index}:",
        f"    persona_name: {avatar.name or avatar.demographic[:60]}",
        f"    demographic: {avatar.demographic}",
        f"    psychographic: {avatar.psychographic}",
        f"    awareness_level: {avatar.awareness_level}",
        f"    top_pains: {pains}",
        f"    desires: {desires}",
        f"    objections: {objections}",
        f"    trigger_events: {triggers}",
        f"    current_solutions: {solutions}",
        f"    language_patterns: {lang}",
        f"    locked_heuristic: {lever}",
        f"    fidelity_tier: {fidelity_tier}",
    ]
    snapshot = _compact_psychology_snapshot(avatar.psychology_profile)
    if snapshot:
        lines.append(snapshot)
    return "\n".join(lines) + "\n"


def generate_remix_angles(
    analysis: AdAnalysis,
    brand: Brand,
    product: Product,
    avatar_lever_pairs: list[tuple[CustomerAvatar, str]],
    fidelity_tiers: list[str] | None = None,
    competitive_gaps: dict | None = None,
) -> list[dict]:
    """Generate one angle per (avatar, lever) pair. All angles share the
    analysis's locked structural fields. Single Sonnet call.

    `fidelity_tiers`, if provided, must have the same length as
    `avatar_lever_pairs`. Each tier ('high' | 'medium' | 'low') controls
    how closely that variation should mimic the reference's visual style.
    Defaults to all 'medium' if not provided.

    `competitive_gaps`, if provided, is the parsed synthesis dict from
    `clients/<slug>/research/competitive-gaps.yaml`. When present, the
    prompt instructs the LLM that at least half of variations should
    exploit a specific competitor weakness. Caller is expected to load
    this via `_load_competitive_gaps()` and pass it in.

    Returns angle dicts compatible with CreativeBrief construction."""
    if not avatar_lever_pairs:
        return []

    if fidelity_tiers is None:
        fidelity_tiers = ["medium"] * len(avatar_lever_pairs)
    if len(fidelity_tiers) != len(avatar_lever_pairs):
        raise ValueError(
            f"fidelity_tiers length ({len(fidelity_tiers)}) must match "
            f"avatar_lever_pairs length ({len(avatar_lever_pairs)})"
        )

    variations_text = "\n".join(
        _format_variation_block(i + 1, avatar, lever, fidelity)
        for i, ((avatar, lever), fidelity) in enumerate(
            zip(avatar_lever_pairs, fidelity_tiers)
        )
    )

    structure_lines = [
        "REFERENCE AD STRUCTURE (LOCKED — every variation MUST share these):",
        f"  ad_type: {analysis.ad_type}",
        f"  creative_mechanic: {analysis.creative_mechanic}",
        f"  visual_format: {analysis.visual_format}",
        f"  framework: {analysis.framework}",
        f"  hook_tactic_inspiration: {analysis.hook_tactic}",
        f"  pain_pattern: {analysis.pain_attacked}",
    ]
    if analysis.enemy:
        structure_lines.append(
            f"  enemy_concept: {analysis.enemy} — replace with our product's "
            "equivalent enemy (status quo, competitor, or the wrong way)"
        )

    visible = analysis.visible_copy or {}
    callouts_list = visible.get("callouts") or []
    if visible.get("headline") or visible.get("description"):
        structure_lines.append("")
        structure_lines.append("REFERENCE COPY (for tonal inspiration only — DO NOT plagiarize):")
        if visible.get("headline"):
            structure_lines.append(f"  reference_headline: {visible['headline']}")
        if visible.get("description"):
            structure_lines.append(f"  reference_description: {visible['description'][:240]}")
        if visible.get("cta"):
            structure_lines.append(f"  reference_cta: {visible['cta']}")

    structure_lines.append("")
    structure_lines.append("REFERENCE TEXT INVENTORY — this is ALL the text the reference shows:")
    if visible.get("headline"):
        structure_lines.append(f"  - Hook / Venn quotes / headline: {visible['headline']}")
    structure_lines.append("  - Product label text (on the bottle/package itself)")
    if visible.get("cta"):
        structure_lines.append(f"  - CTA button: {visible['cta']}")
    if callouts_list:
        structure_lines.append(
            f"  - {len(callouts_list)} visible callout(s): {', '.join(str(c) for c in callouts_list[:4])}"
        )
    else:
        structure_lines.append(
            "  - NO benefit callouts strip — the hook/quotes carry the entire message"
        )

    structure_block = "\n".join(structure_lines)
    reference_style_block = _format_reference_style_block(analysis)

    # Lazy import to avoid a circular dep at module load
    from strategy.angle_multiplier import _format_competitive_gaps
    competitive_gaps_block = _format_competitive_gaps(competitive_gaps).strip()
    has_gaps = bool(competitive_gaps_block)

    n = len(avatar_lever_pairs)
    high_count = fidelity_tiers.count("high")
    min_gap_variations = (n // 2) + (n % 2)  # ceil(n/2) — at least half
    user_prompt = f"""Generate {n} distinct ad variations that REMIX a reference ad for our product.
Every variation MUST share the locked structural fields below — same ad_type,
same creative_mechanic, same visual_format, same framework. What varies across
variations is the PERSONA and the PRIMARY PSYCHOLOGICAL LEVER (heuristic).

{structure_block}

{reference_style_block}

FIDELITY TIERS (each variation has a `fidelity_tier` below — honor it strictly):

  - "high" ({high_count} of {n} variations): produce a NEAR-CLONE of the reference's
    visual look. Use the SAME setting, SAME person/hand (or no-person) as captured
    above, SAME background color, SAME lighting, SAME typography style, SAME
    illustration treatment. Only the product (swap to ours) and the persona's
    spoken language change. The viewer should be able to set this side-by-side
    with the reference and feel they belong to the same campaign.

  - "medium": match the core visual identity (setting type, person-or-not,
    typography family) but allow small persona-tuned variation — e.g. slightly
    different background tone, accent color, or mood lighting.

  - "low": keep ONLY the locked mechanic + visual_format. Setting, props,
    background palette, and accent style can be tuned to the persona.

PRODUCT:
  name: {product.name}
  description: {product.description}
  benefits: {', '.join(product.benefits[:5])}
  unique_mechanism: {product.unique_mechanism or 'not specified'}
  social_proof: {', '.join(product.social_proof[:3]) or 'none provided'}

BRAND:
  name: {brand.name}
  tone: {brand.tone}

{competitive_gaps_block}

VARIATIONS TO GENERATE (one angle per variation, IN ORDER):
{variations_text}
Each variation must:
  1. Use the locked ad_type / creative_mechanic / visual_format / framework — do NOT vary these fields.
     (For "low" fidelity_tier variations only, you MAY substitute creative_mechanic with a
      pairing from the variation's `pre_approved_mechanics` if it fits the persona better
      than the reference's mechanic. NEVER substitute for high or medium fidelity.)
  2. PRIMARILY activate the variation's `locked_heuristic` from the 9-name taxonomy
     (scarcity, social_proof, authority_bias, effect_heuristic, processing_fluency,
     temporal_discounting, salience_bias, goal_gradient, framing_effect).
  3. RESPECT the variation's `persona_snapshot`:
       - The `wired_for` line tells you how to ACTIVATE the locked_heuristic for this
         specific persona (e.g. authority_bias activates differently for a clinician
         vs a wellness influencer follower).
       - The `wired_against` line lists heuristics that will BACKFIRE — do not let
         them creep into the hook or callouts (e.g. if scarcity is wired_against,
         do not add countdowns, "limited stock", urgency language).
       - The `emotional_anchor` tells you which valence/intensity quadrant to anchor
         in (e.g. negative/high = frustration → relief; positive/low = quiet satisfaction).
       - The `banned_mechanics` list MUST NOT appear in your visual_direction.
  4. Speak to that variation's persona — pull verbatim phrases from `top_pains` and
     `language_patterns`. If `trigger_events` or `current_solutions` give you a
     concrete hook (e.g. "left my last brand after they recalled" → "Why I left X
     after the recall"), use them.
  5. Stop the scroll in under 2 seconds. Use the customer's actual phrasing from `top_pains`.
  6. Be genuinely different from the other variations — different angle, different
     hook, different callouts. Even variations sharing a persona must hit a
     different cognitive lever.{"  " if not has_gaps else f"""
  7. COMPETITIVE GAPS — at least {min_gap_variations} of the {n} variations MUST
     exploit one of the EXPLOITABLE GAPS above. When you use a gap:
       - Cite it in `source` (e.g. "competitive-gap: <competitor>'s claim X is
         legally discredited").
       - Use the customer evidence quote as scaffolding for the hook.
       - Make sure the persona's `wired_for` heuristic aligns with the gap's lever
         (e.g. authority_bias persona → gaps about lab data; social_proof persona →
         gaps where competitors lack customer trust)."""}

TEXT DENSITY — HARD RULES (critical: ads with too much text underperform):

  A. TRUST BADGES vs TEXT CALLOUTS — read the reference inventory carefully:
       - Items like "Certified B Corporation", "Trustpilot 4.5 stars", star ratings,
         certification logos = BADGE icons (not text). These belong in
         `visual_direction` as "render B Corp + Trustpilot badges at bottom".
       - Items like "30% off", "Free shipping" = TEXT callouts (real text strips).
       - For THIS reference: if all visible callouts are trust badges, your
         `benefit_callouts` MUST be EMPTY array [].

  B. Where does the hook go? Look at the locked creative_mechanic:
       - "Venn Diagram" / "Whiteboard Venn" / "Split-screen comparison":
         The hook IS the labels INSIDE the two zones (left circle, right circle,
         or left half, right half). Format your hook as
         "left-zone-text | right-zone-text". Do NOT add a separate headline bar
         above the composition.
       - "Before/After Split": same — hook is the two state labels.
       - "Talking Head" / UGC: hook is on-image text overlay.
       - Default if unsure: hook is the single dominant text element.

  C. Your `visual_direction` MUST NOT describe any of:
       - A top headline bar above the main composition (when the mechanic puts
         text INSIDE the structure, e.g. Venn circles)
       - A horizontal "benefit pills" row or callout strip below the product
       - FDA / disclaimer / "These statements have not been evaluated" text —
         even for supplements, the reference doesn't show one, so your variation
         doesn't either
       - Trust legalese / fine print rendered as text bars
       - Body copy paragraphs or feature lists
       - Any text element NOT present in the reference inventory

  D. Your `visual_direction` MUST end with this exact line, filled in:
       TEXT INVENTORY (render ONLY these text elements, nothing else):
       <bullet list of every text element the final image should contain>

     This tells the downstream prompt-writer EXACTLY what text to include and
     suppresses any tendency to add FDA disclaimers, fine print, or extra strips.

  E. `visual_direction` should describe composition + persona-tuned visual cues
     (setting, mood, illustration style, badge icons) — not extra text rendering.

Output VALID JSON ONLY — no prose, no markdown fences. Use double-quoted strings,
escape inner quotes with backslash, no trailing commas. Example shape:

{{
  "angles": [
    {{
      "variation": 1,
      "slot": <integer 1-10>,
      "hook_type": "<matching hook type from the diversity matrix>",
      "hook_tactic": "<specific Motion hook tactic that fits this lever>",
      "angle": "<one-line angle description>",
      "hook": "<scroll-stopping hook text — quote the persona's language>",
      "source": "<which research element this hook came from>",
      "pain_addressed": "<the specific pain this hits>",
      "persona": "<the variation's persona_name>",
      "awareness_stage": "<the persona's awareness_level>",
      "framework": "{analysis.framework}",
      "creative_mechanic": "{analysis.creative_mechanic}",
      "visual_format": "{analysis.visual_format}",
      "primary_heuristic": "<the locked_heuristic>",
      "benefit_callouts": ["<callout 1>", "<callout 2>", "<callout 3>"],
      "cta": "<short CTA>",
      "visual_direction": "<SAME composition as reference, visual cues tuned to this persona>",
      "why_it_works": "<one sentence on the psychological trigger>"
    }}
  ]
}}
"""

    raw = claude_complete(user_prompt, system=ANGLE_SYSTEM, max_tokens=4096)
    parsed = _parse_angles_json_or_yaml(raw)
    return parsed.get("angles") or []


def _parse_angles_json_or_yaml(text: str) -> dict:
    """Parse angle output. Tries JSON first (preferred — strict escaping),
    falls back to YAML for tolerance. Strips markdown fences either way."""
    body = _strip_code_fences(text)
    if not body.strip():
        raise ValueError("Remix angle generation returned empty output.")

    # Try JSON first
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        data = None

    # Fallback: YAML
    if data is None:
        try:
            data = yaml.safe_load(body)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"Remix angle generation returned unparseable output "
                f"(neither JSON nor YAML): {exc}. First 300 chars: {body[:300]!r}"
            ) from exc

    if not isinstance(data, dict):
        raise ValueError(
            f"Remix angle generation returned non-mapping output "
            f"({type(data).__name__}): {body[:200]!r}"
        )
    return data


# ─── Top-level orchestrator ─────────────────────────────────────────────────


def _make_remix_brief_id(
    client_slug: str, product_name: str, timestamp: str, index: int
) -> str:
    seed = f"remix-{client_slug}-{product_name}-{timestamp}-{index}"
    short = hashlib.sha256(seed.encode()).hexdigest()[:6]
    return f"{client_slug}-remix-{short}"


def _coerce_framework(value: str | None, default: str) -> CopyFramework:
    raw = str(value or default or "pas").lower().strip()
    try:
        return CopyFramework(raw)
    except ValueError:
        try:
            return CopyFramework(default.lower())
        except ValueError:
            return CopyFramework.PAS


def _coerce_awareness(value: str | None, default: str) -> AwarenessLevel:
    raw = str(value or default or "problem_aware").lower().strip().replace("-", "_")
    try:
        return AwarenessLevel(raw)
    except ValueError:
        return AwarenessLevel.PROBLEM_AWARE


def _angle_to_brief(
    *,
    angle: dict,
    avatar: CustomerAvatar,
    analysis: AdAnalysis,
    client_slug: str,
    product: Product,
    timestamp: str,
    index: int,
) -> CreativeBrief:
    framework = _coerce_framework(
        angle.get("framework"), analysis.framework or "pas"
    )
    awareness = _coerce_awareness(
        angle.get("awareness_stage"), avatar.awareness_level or "problem_aware"
    )
    persona_label = (
        angle.get("persona")
        or avatar.name
        or avatar.demographic[:60]
        or "primary"
    )
    callouts = angle.get("benefit_callouts") or product.benefits[:3]
    return CreativeBrief(
        brief_id=_make_remix_brief_id(client_slug, product.name, timestamp, index),
        client=client_slug,
        product=product.name,
        awareness_level=awareness,
        framework=framework,
        angle=angle.get("angle", ""),
        hook=angle.get("hook", ""),
        hook_type=angle.get("hook_type", ""),
        slot=angle.get("slot"),
        hook_source=angle.get("source", "ad_remix"),
        hook_tactic=angle.get("hook_tactic", ""),
        persona=persona_label,
        creative_mechanic=angle.get("creative_mechanic") or analysis.creative_mechanic,
        visual_format=angle.get("visual_format") or analysis.visual_format,
        pain_point=angle.get("pain_addressed", ""),
        benefit_callouts=list(callouts),
        cta=angle.get("cta", "Shop Now"),
        visual_direction=angle.get("visual_direction", ""),
        target_platform="meta",
        source_insight="ad_remix",
    )


def _load_product_flexible(client_slug: str, product_ref: str) -> Product:
    """Try loading a product by slug first, then by name. Mirrors what
    `adc generate` accepts so the CLI feels consistent."""
    products_dir = CLIENTS_DIR / client_slug / "products"
    if not products_dir.exists():
        raise FileNotFoundError(f"Products dir not found: {products_dir}")

    direct = products_dir / f"{product_ref}.yaml"
    if direct.exists():
        return load_product(client_slug, product_ref)

    target = product_ref.lower().strip()
    for path in products_dir.glob("*.yaml"):
        prod = Product(**yaml.safe_load(path.read_text(encoding="utf-8")))
        candidates = {
            prod.name.lower(),
            prod.name.lower().replace(" ", "-"),
            prod.name.lower().replace(" ", "_"),
            path.stem.lower(),
        }
        if target in candidates:
            return prod

    raise FileNotFoundError(
        f"No product matching '{product_ref}' for client '{client_slug}'. "
        f"Available: {sorted(p.stem for p in products_dir.glob('*.yaml'))}"
    )


def _save_analysis(out_dir: Path, analysis: AdAnalysis) -> Path:
    path = out_dir / "analysis.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            analysis.to_yaml_dict(),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return path


def _save_briefs(out_dir: Path, briefs: list[CreativeBrief]) -> Path:
    path = out_dir / "briefs.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            [b.model_dump(mode="json") for b in briefs],
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return path


def _enforce_text_density_suffix(
    prompt_text: str,
    brief: CreativeBrief,
    analysis: AdAnalysis,
) -> str:
    """Append a hard text-density override after the LLM-written NB2 prompt.

    `prompt_from_brief` calls Claude to write the final NB2 prompt and can
    independently inject supplement disclaimers / FDA legalese / bottom fine
    print regardless of what visual_direction says. This suffix tells NB2
    directly to ignore those additions and match the reference's restraint."""
    visible = analysis.visible_copy or {}
    inventory_items: list[str] = []
    if brief.hook:
        inventory_items.append(f"Hook text (this variation's): {brief.hook}")
    if brief.cta:
        inventory_items.append(f"CTA button: {brief.cta}")
    inventory_items.append("Product label (on the bottle/package itself)")
    callouts = visible.get("callouts") or []
    badges_present = any(
        kw in str(c).lower()
        for c in callouts
        for kw in ("certified", "trustpilot", "stars", "b corp", "verified", "rated")
    )
    if badges_present:
        inventory_items.append(
            "Trust badges as ICONS (e.g. B Corp logo, Trustpilot stars) — render as icons, NOT text"
        )

    inventory_block = "\n".join(f"  - {item}" for item in inventory_items)

    suffix = (
        "\n\n---\n"
        "CRITICAL TEXT DENSITY OVERRIDE — applies to the entire image:\n\n"
        "Render ONLY the following text elements. Do NOT add anything else:\n"
        f"{inventory_block}\n\n"
        "Strictly forbidden — do NOT include in the image:\n"
        "  - FDA disclaimers or 'These statements have not been evaluated by the Food and Drug Administration' text\n"
        "  - 'This product is not intended to diagnose, treat, cure, or prevent any disease' text\n"
        "  - Supplement legalese, fine print, or asterisk footnotes at the bottom\n"
        "  - Benefit-pill rows, callout strips, or feature lists below the main composition\n"
        "  - Body copy paragraphs or explanatory text\n"
        "  - Any text element not listed in the TEXT INVENTORY above\n\n"
        "Match the reference ad's text restraint exactly. When in doubt, render LESS text, not more."
    )
    return prompt_text.rstrip() + suffix


def _format_remix_notes(
    brief: CreativeBrief,
    product: Product,
    aspect_ratio: str,
    analysis: AdAnalysis,
) -> str:
    lines = [
        "***** REMIX NOTES *****",
        f"Brief:           {brief.brief_id}",
        f"Product:         {product.name}",
        f"Persona:         {brief.persona}",
        f"Locked ad-type:  {analysis.ad_type}",
        f"Mechanic:        {brief.creative_mechanic or '—'}",
        f"Format:          {brief.visual_format or '—'}",
        f"Framework:       {brief.framework.value}",
        f"Hook tactic:     {brief.hook_tactic or '—'}",
        f"Aspect ratio:    {aspect_ratio}",
        f"Model:           fal-ai/nano-banana-2/edit",
        f"Source:          {analysis.source_type} ({analysis.source_ref})",
        f"Generated:       {datetime.now().date().isoformat()}",
    ]
    if brief.campaign_name:
        lines.append(f"Campaign name:   {brief.campaign_name}")
    lines.append("***** END NOTES *****")
    return "\n".join(lines)


def remix(
    *,
    client_slug: str,
    product_ref: str,
    reference: str | Path | None = None,
    foreplay_url_or_id: str | None = None,
    variations: int = 5,
    high_fidelity: int = 2,
    medium_fidelity: int = 2,
    output_root: Path | None = None,
    creative_direction: str = "",
    offer: str = "NONE",
) -> dict:
    """Run the full remix pipeline.

    Exactly one of `reference` (local image path) or `foreplay_url_or_id`
    must be provided.

    Returns a dict with keys: out_dir, analysis, briefs, prompts (list of
    Paths), so the CLI can render a summary."""
    from generators.prompt_engine import infer_aspect_ratio, prompt_from_brief

    if bool(reference) == bool(foreplay_url_or_id):
        raise ValueError(
            "Provide exactly one of `reference` (local path) or `foreplay_url_or_id`."
        )
    if variations < 1:
        raise ValueError(f"variations must be ≥ 1, got {variations}")

    brand = load_brand(client_slug)
    product = _load_product_flexible(client_slug, product_ref)
    avatars = _load_client_avatars(client_slug)

    if output_root is None:
        output_root = CLIENTS_DIR / client_slug / "remixes"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    out_dir = output_root / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    if reference:
        ref_path = Path(reference)
        analysis = analyze_local_image(ref_path)
        archive_dest = out_dir / f"reference{ref_path.suffix or '.png'}"
        shutil.copy2(ref_path, archive_dest)
    else:
        archive_dest = out_dir / "reference.jpg"
        analysis = analyze_foreplay(foreplay_url_or_id, image_dest=archive_dest)

    pairs = _select_avatar_lever_pairs(avatars, variations, analysis.psych_levers)
    fidelity_tiers = _select_fidelity_tiers(
        variations, max_high=high_fidelity, max_medium=medium_fidelity
    )
    competitive_gaps = _load_competitive_gaps(client_slug)
    angles = generate_remix_angles(
        analysis,
        brand,
        product,
        pairs,
        fidelity_tiers=fidelity_tiers,
        competitive_gaps=competitive_gaps,
    )
    if len(angles) < len(pairs):
        raise RuntimeError(
            f"Remix angle generation returned {len(angles)} angles, expected "
            f"{len(pairs)}. Inspect the LLM output or retry with fewer variations."
        )

    briefs: list[CreativeBrief] = []
    for i, (angle, (avatar, _lever)) in enumerate(zip(angles, pairs)):
        briefs.append(
            _angle_to_brief(
                angle=angle,
                avatar=avatar,
                analysis=analysis,
                client_slug=client_slug,
                product=product,
                timestamp=timestamp,
                index=i,
            )
        )

    # Build campaign_name per brief BEFORE saving briefs.yaml so it
    # round-trips through disk. Iteration is always V1 at this step
    # (V2+ come from refinements). Date uses the run timestamp so all
    # variations in a remix run share a consistent date.
    from strategy.naming import build_campaign_name
    try:
        run_date_dt = datetime.strptime(timestamp, "%Y-%m-%d_%H%M%S")
    except ValueError:
        run_date_dt = datetime.now()
    naming_skipped_reason = ""
    for brief in briefs:
        try:
            brief.campaign_name = build_campaign_name(
                brief,
                brand,
                analysis=analysis,
                offer=offer,
                iteration=1,
                date=run_date_dt,
                source="Remix",
            )
        except ValueError as exc:
            # Brand.code missing — log once, leave campaign_name empty.
            naming_skipped_reason = str(exc)
            brief.campaign_name = ""

    _save_analysis(out_dir, analysis)
    _save_briefs(out_dir, briefs)

    # Persist the creative direction so subsequent operations (refinement,
    # image regeneration) can auto-load it.
    if creative_direction and creative_direction.strip():
        (out_dir / "creative_directive.txt").write_text(
            creative_direction.strip() + "\n", encoding="utf-8"
        )

    prompt_paths: list[Path] = []
    for brief, (avatar, _lever) in zip(briefs, pairs):
        aspect = infer_aspect_ratio(brief)
        prompt_text = prompt_from_brief(
            brief=brief,
            brand=brand,
            product=product,
            avatar=avatar,
            aspect_ratio=aspect,
            creative_direction=creative_direction,
        )
        prompt_text = _enforce_text_density_suffix(prompt_text, brief, analysis)
        notes = _format_remix_notes(brief, product, aspect, analysis)
        out_path = prompts_dir / f"{brief.brief_id}.txt"
        out_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")
        prompt_paths.append(out_path)

    return {
        "out_dir": out_dir,
        "analysis": analysis,
        "briefs": briefs,
        "prompts": prompt_paths,
        "pairs": pairs,
        "fidelity_tiers": fidelity_tiers,
        "creative_direction": creative_direction,
    }


def _load_persisted_creative_direction(remix_dir: Path) -> str:
    """Load the saved `creative_directive.txt` from a remix folder if present."""
    p = remix_dir / "creative_directive.txt"
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# ─── Image generation from a saved remix ────────────────────────────────────


_NOTES_END_MARKER = "***** END NOTES *****"


def _strip_notes_header(text: str) -> str:
    """Strip the '***** REMIX NOTES *****' block from a saved prompt file.

    Returns the cleaned prompt text that gets sent to Nano Banana 2."""
    idx = text.find(_NOTES_END_MARKER)
    if idx == -1:
        return text.strip()
    return text[idx + len(_NOTES_END_MARKER):].strip()


def generate_remix_images(
    remix_dir: str | Path,
    *,
    num_images: int = 1,
    thinking_level: str = "disabled",
    aspect_ratio: str = "1:1",
) -> list[Path]:
    """Fire fal.ai (Nano Banana 2) for each brief in a saved remix directory.

    Reads briefs.yaml + the corresponding prompts/*.txt files (notes header
    stripped), uploads/uses the product's reference image, and writes the
    generated images to `<remix-dir>/images/`.

    Returns the list of saved image paths."""
    from generators.fal_client import generate_and_save
    from generators.image_generator import _get_product_image_urls

    remix_path = Path(remix_dir)
    if not remix_path.exists():
        raise FileNotFoundError(f"Remix directory not found: {remix_path}")

    briefs_path = remix_path / "briefs.yaml"
    if not briefs_path.exists():
        raise FileNotFoundError(f"No briefs.yaml in {remix_path}")

    briefs_data = yaml.safe_load(briefs_path.read_text(encoding="utf-8"))
    if not briefs_data or not isinstance(briefs_data, list):
        raise ValueError(f"briefs.yaml is empty or malformed in {remix_path}")

    client_slug = briefs_data[0]["client"]
    product_name = briefs_data[0]["product"]
    product = _load_product_flexible(
        client_slug, product_name.lower().replace(" ", "-")
    )
    product_urls = _get_product_image_urls(product, client_slug)

    images_dir = remix_path / "images"
    images_dir.mkdir(exist_ok=True)

    saved_paths: list[Path] = []
    for brief_data in briefs_data:
        brief_id = brief_data["brief_id"]
        prompt_file = remix_path / "prompts" / f"{brief_id}.txt"
        if not prompt_file.exists():
            raise FileNotFoundError(
                f"Missing prompt file for brief '{brief_id}': {prompt_file}"
            )

        prompt_text = _strip_notes_header(prompt_file.read_text(encoding="utf-8"))
        if not prompt_text:
            raise ValueError(
                f"Empty prompt after stripping notes header: {prompt_file}"
            )

        results = generate_and_save(
            prompt=prompt_text,
            product_image_urls=product_urls,
            save_dir=images_dir,
            filename_prefix=brief_id,
            aspect_ratio=aspect_ratio,
            num_images=num_images,
            thinking_level=thinking_level,
        )
        # Write a sidecar <stem>_campaign.txt next to each image with the
        # brief's campaign_name. Operators copy this into Meta Ads Manager.
        campaign_name = brief_data.get("campaign_name") or ""
        for r in results:
            if r.local_path:
                saved_paths.append(r.local_path)
                if campaign_name:
                    sidecar = r.local_path.with_name(
                        r.local_path.stem + "_campaign.txt"
                    )
                    sidecar.write_text(campaign_name + "\n", encoding="utf-8")

    return saved_paths


# ─── Iterative refinement of an existing image ──────────────────────────────


_REFINEMENT_SYSTEM = """You are refining a Nano Banana 2 ad prompt based on user feedback.

You will receive:
  1. The ORIGINAL prompt that was used to generate an image.
  2. USER FEEDBACK describing what they want changed about that image.

Your job: rewrite the prompt to address the feedback. Two strict rules:

  A. PRESERVE everything the user did NOT mention — composition, brand wordmark,
     product packaging, typography, structural mechanic, on-image text content,
     CTA, badges. If they didn't say to change it, don't change it.

  B. The previous output image will be passed to NB2 as a SECOND reference image
     alongside the product image. Add this line near the top of your prompt,
     directly after "Use the attached images as brand reference.":

       "Use the second reference image as the LAYOUT REFERENCE — preserve
       its composition, lighting, framing, color palette, and on-image
       text exactly, modifying ONLY the elements described below."

Output ONLY the new prompt text. No explanations, no markdown fences."""


_TEXT_INVENTORY_SYSTEM = """You are an OCR + transcription specialist analyzing an
advertisement image. Be exhaustive and exact — preserve case, punctuation, and
any special characters."""


def _extract_visible_text_inventory(image_path: Path) -> list[str]:
    """Vision call that lists every text element visible in an ad image.

    Used during refinement to anchor "what text should stay" to the actual
    previous output, not to whatever the original prompt described. The
    original prompt may have described callouts the model dropped — we don't
    want to add them back during refinement."""
    raw = _claude_vision_local(
        prompt=(
            "List EVERY visible text element in this advertisement image, "
            "EXACTLY as it appears (case preserved, punctuation included). "
            "Each text element on its own line.\n\n"
            "Include: headlines, body text, callouts, button labels, "
            "brand wordmarks, badges with text, fine print, product label text.\n"
            "EXCLUDE: pure icons or emojis without text, decorative elements.\n\n"
            "Output VALID YAML only (no markdown fences) with this structure:\n\n"
            "text_elements:\n"
            '  - "exact text 1"\n'
            '  - "exact text 2"\n'
            '  - "exact text 3"\n'
        ),
        image_path=image_path,
        system=_TEXT_INVENTORY_SYSTEM,
        max_tokens=1024,
    )
    body = _strip_code_fences(raw)
    try:
        data = yaml.safe_load(body) or {}
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("text_elements") or []
    return [str(item).strip() for item in items if str(item).strip()]


def _rewrite_prompt_with_feedback(
    original_prompt: str,
    feedback: str,
    brand: Brand | None = None,
    locked_text_inventory: list[str] | None = None,
) -> str:
    """Single Claude call to rewrite a NB2 prompt incorporating user feedback.

    When `brand` is provided, brand identity (name, colors as hex, tone) is
    injected as context so natural-language feedback like "our brand yellow"
    or "make it on-brand" maps to specific values. The Claude rewrite knows
    to translate these references to the actual hex codes / brand
    descriptors in the rewritten prompt."""
    brand_block = ""
    if brand is not None:
        colors = brand.colors
        brand_lines = [
            "BRAND CONTEXT (use these EXACT values when the user references brand identity):",
            f"  Name: {brand.name}",
            f"  Tone: {brand.tone}",
            f"  Primary color: {colors.primary or '(not set)'}",
            f"  Secondary color: {colors.secondary or '(not set)'}",
            f"  Background color: {colors.background or '(not set)'}",
            f"  Text color: {colors.text or '(not set)'}",
            f"  Accent color: {colors.accent or '(not set)'}",
        ]
        if getattr(brand, "visual_identity", None):
            vi = brand.visual_identity
            if vi.color_mood:
                brand_lines.append(f"  Palette mood: {vi.color_mood}")
            if vi.typography_feel:
                brand_lines.append(f"  Typography feel: {vi.typography_feel}")
            if vi.aesthetic:
                brand_lines.append(f"  Aesthetic: {vi.aesthetic[:160]}")
        brand_lines.append("")
        brand_lines.append(
            "When the user says 'brand yellow', 'our accent color', 'on-brand',"
            " 'in our colors', or any reference to brand identity, RESOLVE it to"
            " the specific hex codes / descriptors above. Quote the hex value"
            " explicitly in the rewritten prompt so NB2 renders it correctly."
        )
        brand_block = "\n".join(brand_lines) + "\n\n"

    inventory_block = ""
    if locked_text_inventory:
        items = "\n".join(f'  - "{t}"' for t in locked_text_inventory)
        inventory_block = (
            "LOCKED TEXT INVENTORY — these are the EXACT text elements VISIBLE in the\n"
            "previous output (extracted via vision). They are GROUND TRUTH for what the\n"
            "refined image should contain. Use these rules:\n"
            "  - These elements MUST remain in the refined image, modified only as the\n"
            "    user explicitly requests below.\n"
            "  - The ORIGINAL PROMPT may describe additional text elements (callouts,\n"
            "    body copy, fine print) that the previous output DID NOT actually render.\n"
            "    REMOVE those descriptions from your rewritten prompt — they would add\n"
            "    text the user clearly didn't want.\n"
            "  - Do NOT introduce NEW text elements unless the user explicitly asks.\n\n"
            f"{items}\n\n"
        )

    user_prompt = f"""{brand_block}{inventory_block}ORIGINAL PROMPT (sent to NB2 when the image was generated):
---
{original_prompt}
---

USER FEEDBACK ON THE GENERATED IMAGE:
{feedback}

Rewrite the prompt now. Output ONLY the new full prompt text."""

    rewritten = claude_complete(
        user_prompt, system=_REFINEMENT_SYSTEM, max_tokens=4096
    ).strip()

    # Append a hard text-density suffix mirroring the locked inventory so
    # NB2 itself receives an unambiguous "render ONLY these" instruction.
    if locked_text_inventory:
        suffix_items = "\n".join(f"  - {t}" for t in locked_text_inventory)
        rewritten = rewritten.rstrip() + "\n\n" + (
            "---\n"
            "CRITICAL TEXT INVENTORY OVERRIDE — applies to the entire image:\n\n"
            "Render ONLY the following text elements (these are the EXACT elements "
            "present in the second reference image, which is the previous output). "
            "Do not add any text element not in this list, except to the extent the "
            "feedback above explicitly asks for it:\n\n"
            f"{suffix_items}\n\n"
            "Strictly forbidden — do NOT introduce text NOT in the inventory above:\n"
            "  - Extra benefit callouts, pills, or strips\n"
            "  - FDA disclaimers, supplement legalese, fine print\n"
            "  - Body copy or feature lists\n"
            "  - Any text element not visible in the second reference image\n\n"
            "When in doubt, render LESS text. Match the second reference image's "
            "text density exactly."
        )
    return rewritten


def _find_latest_image_for_brief(
    images_dir: Path, brief_id: str
) -> Path | None:
    """Find the highest-version output image for a brief.

    Naming conventions:
      - Original: <brief_id>_1x1.png  (or any other aspect-ratio suffix)
      - Refinement: <brief_id>_v<N>.png  or  <brief_id>_v<N>_<letter>.png

    Returns the highest-version refinement if any exist, else the base output."""
    if not images_dir.exists():
        return None

    candidates = sorted(images_dir.glob(f"{brief_id}_*.png"))
    if not candidates:
        return None

    versioned = [p for p in candidates if re.search(r"_v\d+", p.stem)]
    if versioned:
        def _version_key(p: Path) -> tuple[int, str]:
            m = re.search(r"_v(\d+)", p.stem)
            n = int(m.group(1)) if m else 0
            return (n, p.name)
        return sorted(versioned, key=_version_key)[-1]

    return candidates[0]


def _next_refinement_version(images_dir: Path, brief_id: str) -> int:
    """Determine the next refinement version number for a brief.

    Looks for files matching `<brief_id>_v<N>*.png` and returns max(N) + 1,
    starting from 2 if no refinements exist (v1 is implicitly the original)."""
    versions: list[int] = []
    if images_dir.exists():
        for p in images_dir.glob(f"{brief_id}_v*.png"):
            m = re.search(r"_v(\d+)", p.stem)
            if m:
                versions.append(int(m.group(1)))
    return max(versions, default=1) + 1


def _format_refinement_notes(
    brief_data: dict,
    feedback: str,
    version: int,
    base_image: Path,
) -> str:
    """Notes header written above the refined NB2 prompt on disk."""
    lines = [
        "***** REFINEMENT NOTES *****",
        f"Brief:           {brief_data.get('brief_id', '?')}",
        f"Version:         v{version}",
        f"Base image:      {base_image.name}",
        f"Feedback:        {feedback}",
        f"Persona:         {brief_data.get('persona', '?')}",
        f"Model:           fal-ai/nano-banana-2/edit",
        f"Generated:       {datetime.now().date().isoformat()}",
        "***** END NOTES *****",
    ]
    return "\n".join(lines)


def _append_refinement_log(
    remix_dir: Path,
    *,
    brief_id: str,
    feedback: str,
    version: int,
    base_image_name: str,
    output_image_names: list[str],
) -> Path:
    """Append a refinement record to refinement_log.yaml in the remix folder."""
    log_path = remix_dir / "refinement_log.yaml"
    existing: list[dict] = []
    if log_path.exists():
        try:
            loaded = yaml.safe_load(log_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:
            existing = []

    existing.append({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "brief_id": brief_id,
        "version": version,
        "feedback": feedback,
        "base_image": base_image_name,
        "output_images": output_image_names,
    })

    with open(log_path, "w", encoding="utf-8") as f:
        yaml.dump(
            existing,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return log_path


def refine_image(
    *,
    remix_dir: str | Path,
    brief_id: str,
    feedback: str,
    num_images: int = 1,
    thinking_level: str = "disabled",
    aspect_ratio: str = "1:1",
    base_image: str | Path | None = None,
) -> list[Path]:
    """Refine an existing remix image with user feedback.

    Pipeline:
      1. Load the original brief + NB2 prompt + previous output image.
      2. Single Claude call rewrites the prompt to incorporate the feedback.
      3. Upload the previous output to fal.ai so NB2 can use it as a layout
         reference alongside the product image.
      4. Fire fal.ai with [product_image, previous_output] + new prompt, asking
         for `num_images` variations.
      5. Save each output as <brief_id>_v<N>.png (single) or
         <brief_id>_v<N>_<letter>.png (multiple), increment N from the highest
         existing refinement version.
      6. Append a record to refinement_log.yaml.

    Returns the list of saved image paths."""
    from generators.fal_client import generate, upload_image
    from generators.image_generator import _get_product_image_urls

    if num_images < 1:
        raise ValueError(f"num_images must be ≥ 1, got {num_images}")
    if not feedback.strip():
        raise ValueError("feedback must be non-empty")

    remix_path = Path(remix_dir)
    if not remix_path.exists():
        raise FileNotFoundError(f"Remix directory not found: {remix_path}")

    briefs_path = remix_path / "briefs.yaml"
    if not briefs_path.exists():
        raise FileNotFoundError(f"No briefs.yaml in {remix_path}")
    briefs_data = yaml.safe_load(briefs_path.read_text(encoding="utf-8")) or []
    brief = next(
        (b for b in briefs_data if b.get("brief_id") == brief_id),
        None,
    )
    if brief is None:
        raise ValueError(
            f"Brief '{brief_id}' not found in {briefs_path}. "
            f"Available: {[b.get('brief_id') for b in briefs_data]}"
        )

    prompt_path = remix_path / "prompts" / f"{brief_id}.txt"
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Original prompt file not found: {prompt_path}. "
            "Run `adc remix` first to generate the base brief + prompt."
        )
    original_prompt = _strip_notes_header(prompt_path.read_text(encoding="utf-8"))
    if not original_prompt:
        raise ValueError(f"Original prompt is empty after stripping notes: {prompt_path}")

    images_dir = remix_path / "images"
    if base_image is not None:
        candidate = Path(base_image)
        # Allow either a full path or just a filename; resolve relative names
        # against the run's images/ directory.
        if not candidate.is_absolute() and not candidate.exists():
            candidate = images_dir / candidate.name
        if not candidate.exists():
            available = [p.name for p in images_dir.glob(f"{brief_id}*.png")]
            raise FileNotFoundError(
                f"Specified base_image '{base_image}' not found. "
                f"Available for {brief_id}: {available}"
            )
        previous_image = candidate
    else:
        previous_image = _find_latest_image_for_brief(images_dir, brief_id)
        if previous_image is None:
            raise FileNotFoundError(
                f"No previous output image found for brief '{brief_id}' in {images_dir}. "
                "Generate the base image first via `adc remix-images`."
            )

    client_slug = brief.get("client", "")
    product_name = brief.get("product", "")
    product_slug_guess = product_name.lower().replace(" ", "-")
    product = _load_product_flexible(client_slug, product_slug_guess)
    product_urls = _get_product_image_urls(product, client_slug)

    # Load the brand so the refinement Claude can resolve natural-language
    # references like "our brand yellow" → actual hex values.
    try:
        brand = load_brand(client_slug)
    except FileNotFoundError:
        brand = None

    previous_image_url = upload_image(previous_image)

    # Vision-extract the actual text inventory from the previous output. This
    # is the GROUND TRUTH for what text should remain — overrides whatever
    # the original NB2 prompt described, so callouts that were in the brief
    # but the model dropped in the first render don't get added back.
    try:
        locked_inventory = _extract_visible_text_inventory(previous_image)
    except Exception:
        # Vision call failed — proceed without inventory locking (degrades
        # to the previous behavior, with brand context still active).
        locked_inventory = None

    refined_prompt = _rewrite_prompt_with_feedback(
        original_prompt,
        feedback,
        brand=brand,
        locked_text_inventory=locked_inventory,
    )

    version = _next_refinement_version(images_dir, brief_id)
    images_dir.mkdir(parents=True, exist_ok=True)

    image_refs = list(product_urls) + [previous_image_url]

    results = generate(
        prompt=refined_prompt,
        product_image_urls=image_refs,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    # Build a new campaign_name for this refinement — iteration bumps to
    # the new version, date refreshes, everything else stays the same.
    new_campaign_name = ""
    if brand is not None:
        try:
            from models.brief import CreativeBrief
            from strategy.naming import build_campaign_name
            # Reconstruct a CreativeBrief from the dict so naming helpers work.
            brief_obj = CreativeBrief(**brief)
            # Carry forward the offer slot from the original campaign name
            # if present (slot 9, 0-indexed slot 8).
            existing_name = brief.get("campaign_name", "") or ""
            existing_parts = existing_name.split("_") if existing_name else []
            carried_offer = (
                existing_parts[8]
                if len(existing_parts) >= 11
                else "NONE"
            )
            new_campaign_name = build_campaign_name(
                brief_obj,
                brand,
                offer=carried_offer,
                iteration=version,
                date=datetime.now(),
                source="Remix",
            )
        except (ValueError, Exception):
            new_campaign_name = ""

    saved_paths: list[Path] = []
    from generators.fal_client import download_image

    for i, result in enumerate(results):
        if num_images == 1:
            filename = f"{brief_id}_v{version}.png"
        else:
            letter = chr(ord("a") + i)  # a, b, c, ...
            filename = f"{brief_id}_v{version}_{letter}.png"
        local_path = download_image(result.image_url, images_dir / filename)
        result.local_path = local_path
        saved_paths.append(local_path)
        if new_campaign_name:
            sidecar = local_path.with_name(local_path.stem + "_campaign.txt")
            sidecar.write_text(new_campaign_name + "\n", encoding="utf-8")

    refined_prompt_path = remix_path / "prompts" / f"{brief_id}_v{version}.txt"
    refined_prompt_path.write_text(
        _format_refinement_notes(brief, feedback, version, previous_image)
        + "\n\n"
        + refined_prompt
        + "\n",
        encoding="utf-8",
    )

    _append_refinement_log(
        remix_path,
        brief_id=brief_id,
        feedback=feedback,
        version=version,
        base_image_name=previous_image.name,
        output_image_names=[p.name for p in saved_paths],
    )

    return saved_paths
