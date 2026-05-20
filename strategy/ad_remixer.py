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


# Anthropic's vision API caps individual image payloads at 5 MiB raw bytes.
# Photos straight from a phone routinely blow past this (8-12 MB), so we
# downscale + recompress before sending. Target a comfortable headroom.
_ANTHROPIC_VISION_MAX_BYTES = 5 * 1024 * 1024
_VISION_SHRINK_TARGET_BYTES = 4_500_000


def _shrink_for_vision(raw_bytes: bytes, ext_hint: str) -> tuple[bytes, str]:
    """Return (raw_bytes, mime) safely under Anthropic's 5 MiB image cap.

    If already under target, passes through unchanged. Otherwise re-encodes
    as JPEG, iteratively dropping quality and max dimension until it fits.
    Always returns a JPEG when shrinking — fine for ad screenshots and
    photo references; transparency is flattened onto white if present.
    """
    if len(raw_bytes) <= _VISION_SHRINK_TARGET_BYTES:
        return raw_bytes, _detect_image_mime(raw_bytes, ext_hint)

    from io import BytesIO
    from PIL import Image

    img = Image.open(BytesIO(raw_bytes))
    # Flatten alpha onto white so JPEG encoding doesn't error.
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
        img = bg
    elif img.mode != "RGB":
        img = img.convert("RGB")

    original_size = len(raw_bytes)
    # Walk from gentle to aggressive. Stops at the first attempt that fits.
    attempts = [
        (2048, 85),
        (2048, 75),
        (1600, 80),
        (1280, 75),
        (1024, 70),
        (1024, 60),
    ]
    for max_dim, quality in attempts:
        work = img.copy()
        if max(work.size) > max_dim:
            work.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = BytesIO()
        work.save(buf, format="JPEG", quality=quality, optimize=True)
        out = buf.getvalue()
        if len(out) <= _VISION_SHRINK_TARGET_BYTES:
            print(
                f"[remix] Shrunk image for vision API: "
                f"{original_size / 1_048_576:.1f}MB -> {len(out) / 1_048_576:.1f}MB "
                f"({max_dim}px, q{quality})",
                flush=True,
            )
            return out, "image/jpeg"
    raise RuntimeError(
        f"Could not shrink image under {_VISION_SHRINK_TARGET_BYTES} bytes "
        f"even at 1024px / q60 (started at {original_size} bytes)."
    )


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
    raw_bytes, media_type = _shrink_for_vision(raw_bytes, image_path.suffix.lower())
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

    # 8192 because visual_direction strings carry NEAR-CLONE detail per
    # variation and 5+ variations at 4096 truncates mid-string, producing
    # an unparseable response.
    raw = claude_complete(user_prompt, system=ANGLE_SYSTEM, max_tokens=8192)
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

    # The hook from the brief is often 15-40 words — way longer than the
    # reference's ~10-word quote. NB2 ignores "CONDENSE to N words"
    # instructions when the literal long version is also in the prompt
    # — it just renders the longer text. So we have to actually shorten
    # the hook here, before NB2 sees it.
    #
    # Strategy: pull the first sentence of the hook, then cap to roughly
    # the reference's word count (or 15 words, whichever is greater).
    # If the first sentence is itself longer than the cap, hard-truncate
    # at the cap. This matches the reference's quote length without
    # needing another LLM round trip.
    ref_quote = (visible.get("headline") or "").strip()
    ref_word_count = len(ref_quote.split()) if ref_quote else 0
    target_words = max(ref_word_count, 12) if ref_word_count else 15

    def _condense_for_render(text: str) -> str:
        s = (text or "").strip().strip('"').strip("'")
        # First-sentence split on . ! ? — keep the punctuation.
        import re as _re
        m = _re.match(r"^(.*?[.!?])\s+", s)
        first = m.group(1) if m else s
        words = first.split()
        if len(words) > target_words:
            first = " ".join(words[:target_words]).rstrip(",;:") + "."
        return first

    if brief.hook:
        rendered_hook = _condense_for_render(brief.hook)
        inventory_items.append(
            f'Hook text — render EXACTLY this short customer-quote-style line, '
            f'do not extend or add to it (target ≈{target_words} words): '
            f'"{rendered_hook}"'
        )
    if brief.cta:
        inventory_items.append(f"CTA button (rounded pill, standard sans-serif): {brief.cta}")
    inventory_items.append("Product label (on the bottle/package itself — leave verbatim)")

    # ONE optional brand mark, only if the reference shows one. The
    # checking logic looks at the analysis's callouts list. Even when
    # present, we cap to ONE element — no stacking of Trustpilot + B Corp
    # + wordmark.
    callouts = visible.get("callouts") or []
    badge_keywords = ("trustpilot", "stars", "rated")
    has_trustpilot = any(
        any(kw in str(c).lower() for kw in badge_keywords) for c in callouts
    )
    if has_trustpilot:
        inventory_items.append(
            "ONE small Trustpilot icon (stars only, no wordmark text) — the SINGLE optional brand element"
        )

    inventory_block = "\n".join(f"  - {item}" for item in inventory_items)

    suffix = (
        "\n\n---\n"
        "CRITICAL TEXT DENSITY + STYLE OVERRIDE — applies to the entire image:\n\n"
        "Render ONLY the following text elements. Do NOT add anything else:\n"
        f"{inventory_block}\n\n"
        "TYPOGRAPHY: Use clean modern sans-serif, medium weight, tight kerning.\n"
        "Quote marks (if rendered) are small and neutral. DO NOT use italic\n"
        "serif, decorative serif, ornate scripts, or large curly quotation\n"
        "marks unless the reference explicitly uses that style.\n\n"
        "BRAND MARK RULE: At most ONE brand element beyond the product label\n"
        "itself. If a Trustpilot icon is in the inventory above, that is the\n"
        "ONE allowed element — do NOT also add a SecondKind wordmark, B Corp\n"
        "icon, dot-cluster, CO2-neutral badge, or 'as seen in' strip. If no\n"
        "Trustpilot icon is in the inventory, render zero brand elements\n"
        "beyond the product label.\n\n"
        "Strictly forbidden — do NOT include in the image:\n"
        "  - FDA disclaimers or 'These statements have not been evaluated by the Food and Drug Administration' text\n"
        "  - 'This product is not intended to diagnose, treat, cure, or prevent any disease' text\n"
        "  - Supplement legalese, fine print, or asterisk footnotes at the bottom\n"
        "  - Benefit-pill rows, callout strips, or feature lists below the main composition\n"
        "  - Body copy paragraphs or explanatory text\n"
        "  - Supporting subheaders or sub-hooks below the main quote\n"
        "  - Invented 'verified buyer' quotes, customer reviews, or testimonials beyond the inventory\n"
        "  - Multiple stacked brand badges (Trustpilot + B Corp + wordmark + CO2)\n"
        "  - Any text element not listed in the TEXT INVENTORY above\n\n"
        "Match the reference ad's text restraint AND its typographic register.\n"
        "When in doubt, render LESS text and FEWER brand elements, not more."
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
    scene_cleanup: str = "",
    model_descriptor: str = "",
    offer: str = "NONE",
    include_trending: bool = True,
    mode: str = "strategic",
    analyze_only: bool = False,
) -> dict:
    """Run the full remix pipeline.

    Exactly one of `reference` (local image path) or `foreplay_url_or_id`
    must be provided.

    `mode`:
      - "strategic" (default): generates verbose prompts that DESCRIBE a new
        ad inspired by the reference. Best for fresh-brief generation where
        psychology + persona drive a different visual.
      - "differential": vision-extracts the reference's text, asks Claude to
        map each source phrase to a target phrase based on the brief, and
        produces a SHORT surgical-edit prompt ("swap product, swap text,
        preserve everything else"). Best for layout-faithful remixes like
        us-vs-them comparison ads. Operator-supplied `creative_direction`
        becomes the ONLY allowed deviation (e.g. background swap).

    `analyze_only`: when True, stops after the cheap analysis + text
    extraction passes and writes a `.analyze_only.txt` sentinel. The
    operator reviews/edits source_text_inventory.yaml in the dashboard,
    then `remix_continue()` (or `adc remix-continue`) picks up to do the
    expensive brief generation + mapping. This mirrors the manual workflow
    of "see what was read before paying for briefs."

    Returns a dict with keys: out_dir, analysis, briefs, prompts (list of
    Paths), so the CLI can render a summary."""
    from generators.prompt_engine import infer_aspect_ratio, prompt_from_brief

    if bool(reference) == bool(foreplay_url_or_id):
        raise ValueError(
            "Provide exactly one of `reference` (local path) or `foreplay_url_or_id`."
        )
    if variations < 1:
        raise ValueError(f"variations must be ≥ 1, got {variations}")
    if mode not in ("strategic", "differential"):
        raise ValueError(
            f"mode must be 'strategic' or 'differential', got '{mode}'"
        )

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
        print(f"[remix] Analyzing reference image {ref_path.name} (2 vision calls)...", flush=True)
        analysis = analyze_local_image(ref_path)
        archive_dest = out_dir / f"reference{ref_path.suffix or '.png'}"
        shutil.copy2(ref_path, archive_dest)
    else:
        print(f"[remix] Fetching + analyzing Foreplay ad {foreplay_url_or_id}...", flush=True)
        archive_dest = out_dir / "reference.jpg"
        analysis = analyze_foreplay(foreplay_url_or_id, image_dest=archive_dest)
    print(
        f"[remix] Reference analyzed: ad_type={analysis.ad_type} "
        f"levers={','.join(analysis.psych_levers) or '-'}",
        flush=True,
    )

    # ─── Persist analysis + directives + text inventory early ──────────
    # These all happen BEFORE brief generation so analyze-only mode can
    # save them and exit cleanly. (Brief generation is what spends real
    # money — analysis + extraction together are ~$0.04, briefs are
    # ~$0.10-0.30 depending on variation count.) Moving these saves
    # earlier also means the dashboard can show the analysis preview
    # immediately after an analyze-only run completes.
    _save_analysis(out_dir, analysis)

    # Persist product_ref so remix_continue() can reload product without
    # the caller having to re-pass it. Tiny sidecar file.
    (out_dir / ".product_ref.txt").write_text(
        str(product_ref).strip() + "\n", encoding="utf-8"
    )

    # Persist directives so subsequent operations (refinement, image
    # regeneration, remix_continue) can auto-load them.
    if creative_direction and creative_direction.strip():
        (out_dir / "creative_directive.txt").write_text(
            creative_direction.strip() + "\n", encoding="utf-8"
        )
    if scene_cleanup and scene_cleanup.strip():
        (out_dir / "scene_cleanup.txt").write_text(
            scene_cleanup.strip() + "\n", encoding="utf-8"
        )
    if model_descriptor and model_descriptor.strip():
        (out_dir / "model_descriptor.txt").write_text(
            model_descriptor.strip() + "\n", encoding="utf-8"
        )

    # Differential mode: pre-extract the reference's text inventory once
    # (one vision call regardless of variation count). Now structured —
    # role + position per element. Editorial overlay only; product-label
    # text is filtered at the vision prompt level.
    source_items: list[dict] = []
    if mode == "differential":
        print(
            f"[remix] Differential mode — extracting structured source text "
            f"inventory from reference (1 vision call)...",
            flush=True,
        )
        try:
            source_items = _extract_visible_text_inventory_structured(archive_dest)
            if not source_items:
                fallback = _extract_visible_text_inventory(archive_dest)
                source_items = [
                    {
                        "text": t,
                        "position": "",
                        "role": "callout",
                        "word_count": len(t.split()),
                        "char_count": len(t),
                    }
                    for t in fallback
                ]
            n_callouts = sum(
                1 for s in source_items
                if s.get("role", "").startswith("callout")
            )
            print(
                f"[remix] Extracted {len(source_items)} editorial overlay "
                f"element(s) "
                f"({n_callouts} callout-slot{'s' if n_callouts != 1 else ''}).",
                flush=True,
            )
        except Exception as e:
            print(
                f"[remix] WARNING: text extraction failed ({e}). "
                f"Falling back to strategic mode for prompt writing.",
                flush=True,
            )
            mode = "strategic"

    if mode == "differential" and source_items:
        (out_dir / "source_text_inventory.yaml").write_text(
            yaml.dump(
                {"source_texts": source_items},
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    # ─── EARLY EXIT for analyze-only mode ─────────────────────────────
    # Operator wanted to review the analysis + text inventory before paying
    # for brief generation. Write a sentinel and return — `remix_continue()`
    # (or `adc remix-continue`) picks up from here once the operator OKs
    # what was extracted.
    if analyze_only:
        (out_dir / ".analyze_only.txt").write_text(
            "Run paused after analysis. Review source_text_inventory.yaml "
            "in the dashboard, then click 'Continue' or run "
            "`adc remix-continue --remix-dir <dir> --variations N`.\n",
            encoding="utf-8",
        )
        print(
            f"[remix] Analyze-only mode — paused at {out_dir}. "
            f"Review the analysis + text inventory, then continue.",
            flush=True,
        )
        return {
            "out_dir": out_dir,
            "analysis": analysis,
            "briefs": [],
            "prompts": [],
            "pairs": [],
            "fidelity_tiers": [],
            "creative_direction": creative_direction,
            "analyze_only": True,
        }

    pairs = _select_avatar_lever_pairs(avatars, variations, analysis.psych_levers)
    fidelity_tiers = _select_fidelity_tiers(
        variations, max_high=high_fidelity, max_medium=medium_fidelity
    )
    competitive_gaps = _load_competitive_gaps(client_slug)
    print(
        f"[remix] Generating {len(pairs)} angle(s) "
        f"(fidelity tiers: {','.join(fidelity_tiers)})...",
        flush=True,
    )
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

    print(f"[remix] Building {len(angles)} brief(s)...", flush=True)
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

    # Trending format recommendations (top 3) — purely informational, attached
    # to each brief so operators can spin off video/static alternatives.
    # Safe-fails to empty list if the library is missing or LLM call errors.
    if include_trending:
        try:
            from strategy.trending import recommend_trending_formats_for_briefs
            recs_by_id = recommend_trending_formats_for_briefs(briefs)
            for brief in briefs:
                brief.trending_format_recommendations = recs_by_id.get(
                    brief.brief_id, []
                )
        except Exception:
            # Don't let a trending failure block the remix — just skip.
            for brief in briefs:
                brief.trending_format_recommendations = []

    _save_briefs(out_dir, briefs)

    # Mappings dir for differential mode (created lazily here, after the
    # analyze-only early exit, because mappings only get written below).
    if mode == "differential" and source_items:
        mappings_dir = out_dir / "mappings"
        mappings_dir.mkdir(exist_ok=True)

    print(
        f"[remix] Writing {len(briefs)} NB2 prompt(s) "
        f"({mode} mode) to {prompts_dir}...",
        flush=True,
    )
    prompt_paths: list[Path] = []
    for brief, (avatar, _lever) in zip(briefs, pairs):
        aspect = infer_aspect_ratio(brief)

        if mode == "differential" and source_items:
            # Per-brief: Claude maps each source text → target text based on
            # the brief's hook + benefit_callouts + persona, REWRITTEN in the
            # avatar's ICP voice (language_patterns + customer_language
            # quotes) and FITTED to the source's word-count envelope. The
            # differential prompt is short (~250 words) and structured as
            # edit instructions.
            try:
                mapping = _generate_source_to_target_mapping(
                    source_items=source_items,
                    brief=brief,
                    brand=brand,
                    product=product,
                    avatar=avatar,
                )
            except Exception as e:
                print(
                    f"  [brief {brief.brief_id[-6:]}] mapping failed ({e}); "
                    f"writing [MAPPING_FAILED] sentinel targets — operator "
                    f"will see them in the dashboard editor.",
                    flush=True,
                )
                # Sentinel pattern instead of silent identity fallback: the
                # dashboard mapping editor detects this string and flags the
                # row so the operator knows manual editing is required. NB2
                # also receives this string verbatim if not edited, which is
                # noisier than identity (= obviously wrong output) — exactly
                # the goal: silent failures cost the operator money.
                mapping = [
                    {
                        "source": item["text"],
                        "position": item.get("position", ""),
                        "role": item.get("role", "callout"),
                        "target": "[MAPPING_FAILED — edit me]",
                    }
                    for item in source_items
                ]

            # Save the mapping for operator inspection.
            (mappings_dir / f"{brief.brief_id}.yaml").write_text(
                yaml.dump(
                    {"mapping": mapping},
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )

            prompt_text = _build_differential_prompt(
                brief=brief,
                product=product,
                mapping=mapping,
                creative_direction=creative_direction,
                aspect_ratio=aspect,
                scene_cleanup=scene_cleanup,
            )
            # No _enforce_text_density_suffix here — the differential prompt
            # is already strict about text inventory (only the swap-table
            # targets are rendered) and the suffix's "render only these"
            # language would conflict with the swap framing.
        else:
            # Strategic mode (default): existing verbose prompt path.
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
        # Annotate the mode in the notes header so operators can see which
        # prompt style was used after the fact.
        notes = f"# MODE: {mode}\n" + notes
        out_path = prompts_dir / f"{brief.brief_id}.txt"
        out_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")
        prompt_paths.append(out_path)
    print(f"[remix] Done. Output: {out_dir}", flush=True)

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


def remix_continue(
    remix_dir: str | Path,
    *,
    variations: int = 5,
    high_fidelity: int = 2,
    medium_fidelity: int = 2,
    include_trending: bool = True,
    offer: str = "NONE",
) -> dict:
    """Resume an analyze-only remix run — generates briefs + mappings + prompts.

    Picks up after `remix(..., analyze_only=True)` paused the run. Expects:
      - reference.<ext> on disk
      - analysis.yaml on disk
      - source_text_inventory.yaml on disk (if mode was differential)
      - .analyze_only.txt sentinel (will be removed on successful completion)
      - creative_directive.txt / scene_cleanup.txt / model_descriptor.txt
        (optional — operator may have set any of these at analyze time)

    The mode is detected from the presence of source_text_inventory.yaml —
    if it exists, this is a differential run; otherwise strategic.

    The operator may have edited source_text_inventory.yaml between analyze
    and continue (e.g. to remove a row the vision misread) — those edits
    flow through automatically since we just reload from disk."""
    rd = Path(remix_dir)
    if not rd.exists():
        raise FileNotFoundError(f"Remix directory not found: {rd}")

    # Detect client + product slugs from the run path. Standard layout is
    # clients/<slug>/remixes/<timestamp>/. Fall back to scanning analysis
    # for client info if the path doesn't conform.
    client_slug = ""
    if "clients" in rd.parts:
        idx = rd.parts.index("clients")
        if idx + 1 < len(rd.parts):
            client_slug = rd.parts[idx + 1]
    if not client_slug:
        raise ValueError(
            f"Could not infer client_slug from {rd}. Expected "
            f"clients/<slug>/remixes/<timestamp>/ layout."
        )

    # Reload analysis.
    analysis_path = rd / "analysis.yaml"
    if not analysis_path.exists():
        raise FileNotFoundError(
            f"No analysis.yaml in {rd} — run `adc remix --analyze-only` first."
        )
    from strategy.ad_remixer import AdAnalysis  # type: ignore  # local import for clarity
    analysis_data = yaml.safe_load(analysis_path.read_text(encoding="utf-8")) or {}
    analysis = _analysis_from_dict(analysis_data)

    # Reload directives — operator may have edited the .txt files in the
    # dashboard between analyze and continue.
    def _read_txt(name: str) -> str:
        p = rd / name
        return p.read_text(encoding="utf-8").strip() if p.exists() else ""
    creative_direction = _read_txt("creative_directive.txt")
    scene_cleanup = _read_txt("scene_cleanup.txt")
    model_descriptor = _read_txt("model_descriptor.txt")

    # Reload product (slug taken from analysis's client_slug + the brief's
    # `product` field — but we don't have a brief yet, so look it up in
    # the inventory or use the most-recent product YAML).
    # Simplest: scan clients/<slug>/products/ and pick the only product
    # if there's exactly one, else raise. The operator should pass product
    # at analyze time anyway, persisted via... actually we never persist
    # product_ref. Let me look for a product hint in the run dir.
    # For now, require it: continue MUST be called with the same product as
    # analyze. We persist it during analyze for round-trip safety.
    product_ref_file = rd / ".product_ref.txt"
    if not product_ref_file.exists():
        raise FileNotFoundError(
            f"{product_ref_file} missing — analyze run wasn't recorded "
            f"with a product slug. Re-run `adc remix --analyze-only` with "
            f"--product to record it."
        )
    product_ref = product_ref_file.read_text(encoding="utf-8").strip()

    brand = load_brand(client_slug)
    product = _load_product_flexible(client_slug, product_ref)
    avatars = _load_client_avatars(client_slug)

    # Load source items if differential.
    inventory_path = rd / "source_text_inventory.yaml"
    source_items: list[dict] = []
    if inventory_path.exists():
        try:
            inv_data = yaml.safe_load(inventory_path.read_text(encoding="utf-8")) or {}
            raw = inv_data.get("source_texts") or []
            if isinstance(raw, list):
                source_items = [
                    item if isinstance(item, dict) else {"text": str(item)}
                    for item in raw
                ]
        except Exception:
            source_items = []
    mode = "differential" if source_items else "strategic"

    # Find the archived reference for filename + product-uploading hints.
    archive_dest = _find_remix_reference_image(rd)
    if archive_dest is None:
        raise FileNotFoundError(
            f"No reference.<ext> in {rd}. Re-run analyze."
        )

    # Now run the brief-and-mapping pipeline, mirroring what remix() does
    # after its analyze-only early exit point. Kept inline rather than
    # factored into a helper to keep remix() readable.
    timestamp = rd.name  # the run-dir name is the timestamp
    out_dir = rd
    prompts_dir = out_dir / "prompts"
    prompts_dir.mkdir(exist_ok=True)

    from generators.prompt_engine import infer_aspect_ratio, prompt_from_brief

    pairs = _select_avatar_lever_pairs(avatars, variations, analysis.psych_levers)
    fidelity_tiers = _select_fidelity_tiers(
        variations, max_high=high_fidelity, max_medium=medium_fidelity
    )
    competitive_gaps = _load_competitive_gaps(client_slug)
    print(
        f"[remix-continue] Generating {len(pairs)} angle(s) "
        f"(fidelity tiers: {','.join(fidelity_tiers)})...",
        flush=True,
    )
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

    print(f"[remix-continue] Building {len(angles)} brief(s)...", flush=True)
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

    from strategy.naming import build_campaign_name
    try:
        run_date_dt = datetime.strptime(timestamp, "%Y-%m-%d_%H%M%S")
    except ValueError:
        run_date_dt = datetime.now()
    for brief in briefs:
        try:
            brief.campaign_name = build_campaign_name(
                brief, brand, analysis=analysis, offer=offer,
                iteration=1, date=run_date_dt, source="Remix",
            )
        except ValueError:
            brief.campaign_name = ""

    if include_trending:
        try:
            from strategy.trending import recommend_trending_formats_for_briefs
            recs_by_id = recommend_trending_formats_for_briefs(briefs)
            for brief in briefs:
                brief.trending_format_recommendations = recs_by_id.get(
                    brief.brief_id, []
                )
        except Exception:
            for brief in briefs:
                brief.trending_format_recommendations = []

    _save_briefs(out_dir, briefs)

    if mode == "differential" and source_items:
        mappings_dir = out_dir / "mappings"
        mappings_dir.mkdir(exist_ok=True)

    print(
        f"[remix-continue] Writing {len(briefs)} NB2 prompt(s) "
        f"({mode} mode) to {prompts_dir}...",
        flush=True,
    )
    prompt_paths: list[Path] = []
    for brief, (avatar, _lever) in zip(briefs, pairs):
        aspect = infer_aspect_ratio(brief)

        if mode == "differential" and source_items:
            try:
                mapping = _generate_source_to_target_mapping(
                    source_items=source_items,
                    brief=brief,
                    brand=brand,
                    product=product,
                    avatar=avatar,
                )
            except Exception as e:
                print(
                    f"  [brief {brief.brief_id[-6:]}] mapping failed ({e}); "
                    f"writing [MAPPING_FAILED] sentinel targets.",
                    flush=True,
                )
                mapping = [
                    {
                        "source": item["text"],
                        "position": item.get("position", ""),
                        "role": item.get("role", "callout"),
                        "target": "[MAPPING_FAILED — edit me]",
                    }
                    for item in source_items
                ]

            (out_dir / "mappings" / f"{brief.brief_id}.yaml").write_text(
                yaml.dump(
                    {"mapping": mapping},
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                ),
                encoding="utf-8",
            )

            prompt_text = _build_differential_prompt(
                brief=brief,
                product=product,
                mapping=mapping,
                creative_direction=creative_direction,
                aspect_ratio=aspect,
                scene_cleanup=scene_cleanup,
            )
        else:
            prompt_text = prompt_from_brief(
                brief=brief, brand=brand, product=product, avatar=avatar,
                aspect_ratio=aspect, creative_direction=creative_direction,
            )
            prompt_text = _enforce_text_density_suffix(prompt_text, brief, analysis)

        notes = _format_remix_notes(brief, product, aspect, analysis)
        notes = f"# MODE: {mode}\n" + notes
        out_path = prompts_dir / f"{brief.brief_id}.txt"
        out_path.write_text(notes + "\n\n" + prompt_text + "\n", encoding="utf-8")
        prompt_paths.append(out_path)

    # Remove the analyze-only sentinel — run is complete.
    sentinel = out_dir / ".analyze_only.txt"
    if sentinel.exists():
        sentinel.unlink()

    print(f"[remix-continue] Done. Output: {out_dir}", flush=True)

    return {
        "out_dir": out_dir,
        "analysis": analysis,
        "briefs": briefs,
        "prompts": prompt_paths,
        "pairs": pairs,
        "fidelity_tiers": fidelity_tiers,
        "creative_direction": creative_direction,
    }


def _analysis_from_dict(data: dict) -> "AdAnalysis":
    """Rebuild an AdAnalysis dataclass from the saved analysis.yaml dict.

    `_save_analysis` uses asdict() to serialize; this is the inverse. Kept
    here as a helper for `remix_continue` rather than as a method on the
    dataclass since the dataclass module is shared by other call sites that
    don't need this."""
    return AdAnalysis(**{
        k: data.get(k)
        for k in AdAnalysis.__dataclass_fields__.keys()
        if k in data
    })


# ─── Image generation from a saved remix ────────────────────────────────────


_NOTES_END_MARKER = "***** END NOTES *****"


def _strip_notes_header(text: str) -> str:
    """Strip the '***** REMIX NOTES *****' block from a saved prompt file.

    Returns the cleaned prompt text that gets sent to Nano Banana 2."""
    idx = text.find(_NOTES_END_MARKER)
    if idx == -1:
        return text.strip()
    return text[idx + len(_NOTES_END_MARKER):].strip()


def _get_soul_id_for_brief(brief_data: dict) -> str | None:
    """Look up the higgsfield.soul_id from the avatar YAML for this brief's persona.

    Returns None if no avatar matches or the avatar has no Soul Character trained
    yet. Returning None is non-fatal — the caller can fall back to text-only
    generation, or raise if a Soul is strictly required.
    """
    client_slug = brief_data.get("client", "")
    persona_name = (brief_data.get("persona") or "").strip()
    if not client_slug or not persona_name:
        return None

    avatars_dir = CLIENTS_DIR / client_slug / "avatars"
    if not avatars_dir.exists():
        return None

    # Match by `name:` field across all avatar YAMLs (the slug is filename stem,
    # not always derivable from the persona display name).
    for path in sorted(avatars_dir.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if (data.get("name") or "").strip().lower() == persona_name.lower():
            hf = data.get("higgsfield") or {}
            soul_id = hf.get("soul_id")
            soul_status = hf.get("soul_status", "")
            if soul_id and soul_status == "ready":
                return soul_id
            return None
    return None


def generate_remix_images(
    remix_dir: str | Path,
    *,
    num_images: int = 1,
    thinking_level: str = "disabled",
    aspect_ratio: str = "1:1",
    engine: str = "nb2",
    fallback_engine: str | None = None,
    staged: bool = False,
) -> list[Path]:
    """Fire the image-generation engine for each brief in a saved remix directory.

    Engines:
      - "nb2"              fal.ai Nano Banana 2 (existing) — product-aware,
                            multi-image edit endpoint, no identity lock.
      - "higgsfield-soul"  Higgs Field soul_2 with the persona's trained
                            soul_id — identity-locked face, phone-camera
                            aesthetic. Requires HF_CREDENTIALS in env and a
                            'ready' Soul Character on each avatar.

    `staged` (differential mode only): split the single-shot differential
    edit into 3 sequential passes — product swap, then text swap, then
    optional model/character swap via Higgsfield Soul. Each pass has ONE
    job, mirroring the operator's manual workflow that produced the best
    results. Costs ~3x more API calls (~$0.24/brief). Intermediate stage
    images are saved for inspection.

    `fallback_engine`: if HF fails because of missing credits (the common
    case when running standalone CLI against an HF account whose REST
    API pool is empty), automatically retry the whole run with the
    fallback engine instead of aborting. Set to "nb2" from the dashboard
    when the operator wants graceful degradation.

    Returns the list of saved image paths.
    """
    remix_path = Path(remix_dir)
    if not remix_path.exists():
        raise FileNotFoundError(f"Remix directory not found: {remix_path}")

    briefs_path = remix_path / "briefs.yaml"
    if not briefs_path.exists():
        raise FileNotFoundError(f"No briefs.yaml in {remix_path}")

    briefs_data = yaml.safe_load(briefs_path.read_text(encoding="utf-8"))
    if not briefs_data or not isinstance(briefs_data, list):
        raise ValueError(f"briefs.yaml is empty or malformed in {remix_path}")

    images_dir = remix_path / "images"
    images_dir.mkdir(exist_ok=True)

    # Staged mode short-circuits the single-shot path. It needs differential
    # mappings + an uploadable reference; the staged orchestrator validates
    # those preconditions itself and raises if they're missing. Final pass
    # uses Higgsfield Soul when engine implies HF, or when the avatar has a
    # ready soul; the orchestrator decides per brief.
    if staged:
        try:
            return _generate_remix_images_staged(
                briefs_data,
                remix_path=remix_path,
                images_dir=images_dir,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
                thinking_level=thinking_level,
                final_pass_soul=(engine == "higgsfield-soul"),
            )
        except Exception as e:
            if fallback_engine and "credit" in str(e).lower():
                print(
                    f"  [fallback] Staged mode hit credits issue ({e}). "
                    f"Falling back to single-shot engine={fallback_engine}.",
                    flush=True,
                )
                return generate_remix_images(
                    remix_dir,
                    num_images=num_images,
                    thinking_level=thinking_level,
                    aspect_ratio=aspect_ratio,
                    engine=fallback_engine,
                    fallback_engine=None,
                    staged=False,
                )
            raise

    if engine == "higgsfield-soul":
        try:
            paths = _generate_remix_images_higgsfield(
                briefs_data,
                remix_path=remix_path,
                images_dir=images_dir,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
            )
        except Exception as e:
            # HF blew up before we could even submit a single brief. If
            # the operator opted into fallback, log + recurse with NB2.
            if fallback_engine and "credit" in str(e).lower():
                print(
                    f"  [fallback] Higgs Field unavailable ({e}). "
                    f"Falling back to engine={fallback_engine}."
                )
                return generate_remix_images(
                    remix_dir,
                    num_images=num_images,
                    thinking_level=thinking_level,
                    aspect_ratio=aspect_ratio,
                    engine=fallback_engine,
                    fallback_engine=None,
                )
            raise
        if paths or fallback_engine is None:
            return paths
        # HF ran but produced no images (e.g. every persona missing a
        # ready soul_id). Fall through to NB2 if configured.
        print(
            f"  [fallback] Higgs Field produced 0 images. "
            f"Falling back to engine={fallback_engine}."
        )
        engine = fallback_engine

    # Default path: NB2 via fal.ai (existing behavior, unchanged below).
    from generators.fal_client import generate_and_save
    from generators.image_generator import _get_product_image_urls

    client_slug = briefs_data[0]["client"]
    product_name = briefs_data[0]["product"]
    product = _load_product_flexible(
        client_slug, product_name.lower().replace(" ", "-")
    )
    product_urls = _get_product_image_urls(product, client_slug)

    # Differential mode bug fix: the saved prompts open with "This is a
    # SURGICAL EDIT of Image 1 (the reference ad). Image 2 is the
    # replacement product." For that framing to be true, Image 1 must
    # actually be the reference. Before this fix, only the product was
    # uploaded and NB2 had to imagine the reference layout from the prompt
    # text — which is exactly when text density inflates. Upload the
    # archived reference once for the run and prepend it to image_urls.
    reference_url: str | None = None
    if briefs_data:
        first_prompt = remix_path / "prompts" / f"{briefs_data[0]['brief_id']}.txt"
        if first_prompt.exists():
            run_mode = _detect_remix_mode_from_prompt(first_prompt)
            if run_mode == "differential":
                reference_url = _resolve_remix_reference_url(remix_path)
                if reference_url:
                    print(
                        f"[remix] Differential mode: reference uploaded to fal.ai. "
                        f"NB2 will see [reference, product] as Image 1 + Image 2.",
                        flush=True,
                    )

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

        # In differential mode the reference is Image 1, product is Image 2,
        # matching the prompt's "Image 1 (reference) / Image 2 (product)"
        # framing. Strategic mode keeps the product-only behavior.
        image_urls = ([reference_url] + product_urls) if reference_url else product_urls

        results = generate_and_save(
            prompt=prompt_text,
            product_image_urls=image_urls,
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


def _strip_text_from_prompt(prompt: str) -> str:
    """Remove text-rendering instructions from a prompt before sending to soul_2.

    soul_2 produces gibberish letterforms when asked to render legible
    text inline (e.g. "I wan resmenoineg broobitics" instead of the actual
    quote). We strip the TEXT INVENTORY / TYPOGRAPHY / CTA blocks and tell
    soul_2 to generate a clean scene with empty negative-space for text.
    PIL renders the actual text overlay in a separate pass after.

    Conservative approach: keep the scene/subject/lighting/camera blocks
    intact; truncate at the first section header that introduces text
    elements; append explicit "no text" guidance + reserve the lower
    third for PIL overlay.
    """
    import re

    # Drop everything from the first text-related section header onward.
    text_section_markers = [
        "TYPOGRAPHY AND TEXT ELEMENTS",
        "TYPOGRAPHY:",
        "TEXT INVENTORY",
        "TEXT ELEMENTS",
        "CRITICAL TEXT DENSITY",
        "CTA BUTTON",
        "HOOK TEXT",
        "HERO TEXT",
        "QUOTE OVERLAY",
        "OVERLAY TEXT",
    ]
    cutoff = len(prompt)
    for marker in text_section_markers:
        idx = prompt.upper().find(marker.upper())
        if idx != -1 and idx < cutoff:
            cutoff = idx
    stripped = prompt[:cutoff].rstrip()

    # Also strip any "Image 1 is the actual product…" preamble that's specific
    # to NB2 multi-image edits — soul_2 doesn't get a product image here.
    stripped = re.sub(
        r"^Image 1 is the actual product[^\n]*\n*(Any additional images[^\n]*\n*)?",
        "",
        stripped,
        flags=re.IGNORECASE,
    )

    suffix = (
        "\n\n"
        "TEXT-FREE OUTPUT: Render ONLY the scene — subject, environment, "
        "lighting, product. The lower third of the frame should be empty, "
        "uncluttered warm cream space ready for a separate text overlay. "
        "DO NOT render any letters, words, quotation marks, captions, "
        "headlines, logos, brand wordmarks, CTAs, badges, ratings, or "
        "review text anywhere in the image. The output is a photograph "
        "only; text is composited in a downstream pass.\n\n"
        "Negative prompt: any text, any letters, any words, any captions, "
        "any quotation marks, any logos, any badges, any wordmarks, any "
        "Trustpilot, any star rating, any number ratings, any overlay text."
    )
    return stripped + suffix


def _load_brief_mapping(remix_path: Path, brief_id: str) -> list[dict]:
    """Read the saved source→target mapping for a brief, if any.

    Returns a list of `{source, position, role, target}` dicts (older
    mapping files without position/role are read as-is — missing fields
    default to empty strings). Returns an empty list when the run is not
    differential-mode or the mapping file is absent.
    """
    mapping_file = remix_path / "mappings" / f"{brief_id}.yaml"
    if not mapping_file.exists():
        return []
    try:
        data = yaml.safe_load(mapping_file.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("mapping") or []
    out: list[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append({
            "source": str(item.get("source") or "").strip(),
            "position": str(item.get("position") or "").strip(),
            "role": str(item.get("role") or "callout").strip(),
            "target": str(item.get("target") or "").strip(),
        })
    return out


def _pick_overlay_text_from_mapping(
    mapping: list[dict],
    fallback_hero: str,
    fallback_cta: str,
) -> tuple[str, str]:
    """From a role-aware mapping, pick the headline + cta target strings.

    Used by the Higgsfield path so the PIL overlay renders the operator-
    reviewed mapping targets instead of the raw brief.hook / brief.cta.
    Falls back to the brief values when the mapping lacks a matching role
    or when no mapping is supplied at all.

    Selection rules:
      hero_quote ← first non-[REMOVE] target with role in (headline,
                   subheadline). Otherwise the first non-[REMOVE] target
                   regardless of role. Otherwise fallback_hero.
      cta_text   ← first non-[REMOVE] target with role == cta. Otherwise
                   fallback_cta.
    """
    placeholders = ("[REMOVE]", "[PRESERVE AS-IS]")

    def _useful(item: dict) -> bool:
        tgt = (item.get("target") or "").strip()
        return bool(tgt) and tgt.upper() not in placeholders

    hero = ""
    for item in mapping:
        if not _useful(item):
            continue
        role = (item.get("role") or "").lower()
        if role in ("headline", "subheadline"):
            hero = item["target"].strip()
            break
    if not hero:
        for item in mapping:
            if _useful(item):
                hero = item["target"].strip()
                break

    cta = ""
    for item in mapping:
        if not _useful(item):
            continue
        if (item.get("role") or "").lower() == "cta":
            cta = item["target"].strip()
            break

    return (hero or fallback_hero, cta or fallback_cta)


def _generate_remix_images_higgsfield(
    briefs_data: list[dict],
    *,
    remix_path: Path,
    images_dir: Path,
    num_images: int,
    aspect_ratio: str,
) -> list[Path]:
    """Higgs Field soul_2 image generation + PIL text overlay, identity-locked.

    Two-pass per brief:
      1. soul_2(soul_id=<persona>, reference_image_url=<archived reference>,
                prompt=<text-stripped>)
         → photoreal scene with identity-locked face and layout guided by
           the archived reference, no inline text
      2. PIL overlay
         → mapped headline + mapped CTA composited onto the scene.
           Differential-mode mappings drive hero_quote/cta_text; strategic
           or no-mapping runs fall back to brief.hook / brief.cta.

    For each brief, look up the persona's trained `soul_id` from the avatar
    YAML. If the persona has no Soul Character, skip the brief and log a
    warning — operator can train via the Higgs Field MCP.
    """
    from generators.higgsfield_client import HiggsfieldError, soul_generate_and_save
    from generators.text_overlay import render_ad_overlay, SECONDKIND_PRESET

    # Upload the archived reference once per run (if present) so soul_2 can
    # use it as a composition reference for layout fidelity. This mirrors
    # the NB2 differential fix at the start of generate_remix_images.
    reference_url = _resolve_remix_reference_url(remix_path)
    if reference_url:
        print(
            f"[remix] Higgsfield: reference uploaded for layout guidance.",
            flush=True,
        )

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

        soul_id = _get_soul_id_for_brief(brief_data)
        if not soul_id:
            print(
                f"  [skip] {brief_id} — persona "
                f"'{brief_data.get('persona', '?')}' has no Soul Character "
                f"(higgsfield.soul_status != 'ready'). Train one first."
            )
            continue

        # Load the saved mapping (differential mode only) so the PIL
        # overlay renders the operator-reviewed target text instead of the
        # raw brief content. Missing/strategic-mode runs return [].
        mapping = _load_brief_mapping(remix_path, brief_id)

        # Pass 1: scene-only prompt for soul_2 (no text)
        scene_prompt = _strip_text_from_prompt(prompt_text)

        for i in range(num_images):
            suffix = f"_{i+1}" if num_images > 1 else ""
            scene_path = images_dir / f"{brief_id}{suffix}_scene.png"
            final_path = images_dir / f"{brief_id}{suffix}_1x1.png"
            try:
                soul_generate_and_save(
                    soul_id=soul_id,
                    prompt=scene_prompt,
                    out_path=scene_path,
                    reference_image_url=reference_url,
                    aspect_ratio=aspect_ratio,
                    quality="2k",
                )
            except HiggsfieldError as e:
                # Credits errors at the API level — bubble up so the
                # outer fallback handler can swap engines for the whole
                # run rather than continuing brief-by-brief with no hope.
                if "credit" in str(e).lower():
                    raise
                print(f"  [fail soul] {brief_id}: {e}")
                continue

            # Pass 2: PIL text overlay.
            # Differential-mode mapping → operator-reviewed targets per role.
            # Strategic-mode or no-mapping → fall back to brief.hook / brief.cta.
            fallback_hero = (brief_data.get("hook") or "").strip()
            fallback_cta = (brief_data.get("cta") or "Learn more").strip()
            hero_quote, cta_text = _pick_overlay_text_from_mapping(
                mapping, fallback_hero, fallback_cta
            )
            # CTA in briefs sometimes ends with " →" — strip; PIL will not add an arrow yet
            cta_text = cta_text.rstrip("→").strip()

            try:
                render_ad_overlay(
                    base_image=scene_path,
                    hero_quote=hero_quote,
                    cta_text=cta_text,
                    out_path=final_path,
                    preset=SECONDKIND_PRESET,
                )
            except Exception as e:
                print(f"  [fail overlay] {brief_id}: {e}")
                continue
            saved_paths.append(final_path)

            # Campaign-name sidecar (same convention as NB2 path)
            campaign_name = brief_data.get("campaign_name") or ""
            if campaign_name:
                sidecar = final_path.with_name(final_path.stem + "_campaign.txt")
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


# Role taxonomy for structured text extraction. Mirrors how operators describe
# ad anatomy: headlines anchor the hierarchy, callouts decorate panels,
# brand/CTA carry the action layer, decoration is "don't translate", fine-print
# is legalese the new brand likely doesn't need.
_TEXT_ROLES = (
    "headline",        # primary on-image text, biggest type, top of hierarchy
    "subheadline",     # secondary headline / lede
    "callout-pain",    # ❌-side callout in us-vs-them comparisons
    "callout-benefit", # ✅-side callout in us-vs-them comparisons
    "callout",         # generic callout (single-sided)
    "brand",           # brand wordmark / product name on a label
    "cta",             # button / pill / action prompt
    "bodycopy",        # paragraph-form supporting copy
    "fine-print",      # legalese, disclaimers, footnotes
    "decoration",      # decorative product-label text we PRESERVE AS-IS
)

_TEXT_POSITIONS = (
    "top-left", "top-center", "top-right",
    "middle-left", "center", "middle-right",
    "bottom-left", "bottom-center", "bottom-right",
    "left-side", "right-side", "top", "bottom",
)

_STRUCTURED_TEXT_INVENTORY_PROMPT = (
    "List the EDITORIAL TEXT elements overlaid on this advertisement image, "
    "EXACTLY as they appear (case preserved, punctuation included). For each "
    "element, also label its position and its role in the ad's anatomy.\n\n"
    "CRITICAL — INCLUDE vs EXCLUDE:\n\n"
    "INCLUDE (editorial text added on top of the photo by the ad designer):\n"
    "  - Headlines and subheadlines overlaid on the image\n"
    "  - Callout pills / bubbles / strips with benefit or pain text\n"
    "  - CTAs (Shop Now, Learn More, etc.) — buttons or pill-shaped labels\n"
    "  - Brand wordmarks that appear in the ad header / footer area as an "
    "ad-design element (NOT the wordmark printed on the product label itself)\n"
    "  - Trust badges with text (Trustpilot 4.5, B-Corp Certified, As Seen In…)\n"
    "  - Fine print / disclaimers / footnotes overlaid at the bottom of the ad\n"
    "  - Offer text overlays (30% OFF, FREE SHIPPING, LIMITED TIME)\n"
    "  - Body copy paragraphs overlaid on the photo\n\n"
    "EXCLUDE — DO NOT LIST any of the following (this is critical):\n"
    "  - ANY text physically printed on the product package itself "
    "(jar, bottle, box, can, tube, pouch). This includes the brand/product "
    "name on the label, ingredient lists, flavor descriptors ('SALMON "
    "FLAVOR', 'VANILLA'), weight/count ('30 SOFT CHEWS', 'Net Wt 4.23 oz'), "
    "barcodes, certification stamps printed on the bottle, supplement-facts "
    "panels, audience labels ('ALL DOGS', '12+ WEEKS'), and any other text "
    "that is part of the product's physical packaging artwork.\n"
    "  - Reason: the product image will be swapped to the new brand's "
    "package, so the source's package text is irrelevant — it gets carried "
    "over from the new product image automatically, not via the swap table.\n"
    "  - Pure icons / emojis without text, purely decorative shapes, "
    "pictograms.\n\n"
    "The litmus test: 'If I removed the product from the photo, would this "
    "text still be there as an ad overlay?' If YES → include. If the text "
    "would disappear with the bottle/jar/box → exclude.\n\n"
    "POSITION — pick the single best match from: "
    + ", ".join(_TEXT_POSITIONS) + ". For us-vs-them comparison ads, the "
    "❌-side callouts are typically left-side and the ✅-side callouts are "
    "right-side; use those specifically.\n\n"
    "ROLE — pick the single best match from:\n"
    "  - headline:        the largest top-of-hierarchy text (max 1-2 per ad)\n"
    "  - subheadline:     secondary larger text\n"
    "  - callout-pain:    a callout marked with ❌ / X / red color / 'before' / "
    "framed as the pain state\n"
    "  - callout-benefit: a callout marked with ✅ / check / green color / "
    "'after' / framed as the result state\n"
    "  - callout:         a generic callout that isn't clearly pain or benefit "
    "(single-sided ads)\n"
    "  - brand:           a brand wordmark in the ad header / footer area "
    "(NOT on the product label)\n"
    "  - cta:             a button, pill, or action prompt (Shop Now, Learn "
    "More, etc.)\n"
    "  - bodycopy:        sentence/paragraph-form supporting copy overlay\n"
    "  - fine-print:      legalese, asterisks, disclaimers, footnotes\n\n"
    "Output VALID YAML only (no markdown fences), in top-to-bottom order. "
    "If the ad has no overlay text at all (pure photo with the product "
    "speaking for itself), return an empty list.\n\n"
    "text_elements:\n"
    '  - text: "exact text 1"\n'
    "    position: top-center\n"
    "    role: headline\n"
    '  - text: "exact text 2"\n'
    "    position: bottom-left\n"
    "    role: callout-pain\n"
)


def _extract_visible_text_inventory_structured(image_path: Path) -> list[dict]:
    """Vision call that returns each text element with position + role.

    Returns a list of dicts: {text, position, role, word_count, char_count}.
    Position and role are best-effort labels from a fixed vocabulary —
    `_TEXT_POSITIONS` / `_TEXT_ROLES`. Word/char counts are computed locally.

    Used by differential remix mode so the mapper knows which source slots
    are callouts (and how many) before redistributing brief content into them.
    """
    raw = _claude_vision_local(
        prompt=_STRUCTURED_TEXT_INVENTORY_PROMPT,
        image_path=image_path,
        system=_TEXT_INVENTORY_SYSTEM,
        max_tokens=2048,
    )
    body = _strip_code_fences(raw)
    try:
        data = yaml.safe_load(body) or {}
    except Exception:
        return []
    if not isinstance(data, dict):
        return []
    items = data.get("text_elements") or []
    out: list[dict] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
            position, role = "", "callout"
        elif isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            position = str(item.get("position") or "").strip().lower()
            role = str(item.get("role") or "").strip().lower()
        else:
            continue
        if not text:
            continue
        if role not in _TEXT_ROLES:
            role = "callout"  # safe default
        if position and position not in _TEXT_POSITIONS:
            position = ""
        words = text.split()
        out.append({
            "text": text,
            "position": position,
            "role": role,
            "word_count": len(words),
            "char_count": len(text),
        })
    return out


def _extract_visible_text_inventory(image_path: Path) -> list[str]:
    """Backward-compat wrapper: returns just the visible text strings.

    Used by the refinement path (which only needs the strings) and as a
    fallback when structured extraction fails. Differential remix mode uses
    `_extract_visible_text_inventory_structured` instead so it gets role +
    position metadata.

    Excludes product-package text — the litmus test is whether the text
    would still exist if you removed the product from the photo. Editorial
    overlays survive; package labels don't."""
    raw = _claude_vision_local(
        prompt=(
            "List the EDITORIAL TEXT elements overlaid on this advertisement "
            "image, EXACTLY as they appear (case preserved, punctuation "
            "included). Each text element on its own line.\n\n"
            "INCLUDE — editorial overlays added by the ad designer:\n"
            "  - Headlines, subheadlines, body copy overlays\n"
            "  - Callout pills / bubbles / strips with benefit or pain text\n"
            "  - CTAs (Shop Now, Learn More, button labels)\n"
            "  - Brand wordmarks in the AD HEADER / FOOTER area (not on the "
            "product label)\n"
            "  - Trust badges with text, offer overlays, fine print\n\n"
            "EXCLUDE — do NOT list any of the following:\n"
            "  - Text physically printed on the product package itself "
            "(jar/bottle/box label): brand/product name on the label, "
            "ingredient lists, flavor descriptors, weight/count, barcodes, "
            "certification stamps, supplement-facts panels, audience tags.\n"
            "  - Pure icons or emojis without text, decorative shapes.\n\n"
            "Litmus test: 'If I removed the product from the photo, would "
            "this text still be there?' Yes → include. No → exclude.\n\n"
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


# ─── Reference-image helpers (shared by differential NB2 + Higgsfield paths)


def _find_remix_reference_image(remix_path: Path) -> Path | None:
    """Find the archived reference ad image in a remix directory.

    `remix()` saves the reference as `reference.<ext>` at the run root. This
    helper returns the first match by common extension (png/jpg/jpeg/webp),
    or None if nothing matches."""
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = remix_path / f"reference{ext}"
        if p.exists():
            return p
    return None


def _detect_remix_mode_from_prompt(prompt_file: Path) -> str:
    """Read the saved prompt notes header to determine which mode produced it.

    The remix-writer prepends `# MODE: <mode>` to every prompt file. We need
    this at image-generation time to decide whether to upload the reference
    as Image 1 (differential) or skip it (strategic). Returns 'differential'
    or 'strategic' (default)."""
    try:
        with open(prompt_file, encoding="utf-8") as f:
            for _ in range(5):
                line = f.readline()
                if not line:
                    break
                if line.startswith("# MODE:"):
                    return line.split(":", 1)[1].strip().split()[0]
    except OSError:
        pass
    return "strategic"


def _resolve_remix_reference_url(remix_path: Path) -> str | None:
    """Upload the run's archived reference ad to fal.ai once and cache the URL.

    fal.ai's NB2/edit endpoint accepts arbitrary public URLs as input
    images. Higgsfield's soul_2 also accepts arbitrary public URLs in its
    `medias` param. So one upload → one URL → reused across both engines
    and across all briefs in the run.

    Cache lives at `<remix_path>/.reference_url.txt`. Returns None if the
    reference is missing or the upload fails."""
    ref_path = _find_remix_reference_image(remix_path)
    if ref_path is None:
        return None
    cache = remix_path / ".reference_url.txt"
    if cache.exists():
        try:
            cached = cache.read_text(encoding="utf-8").strip()
            if cached:
                return cached
        except OSError:
            pass
    try:
        from generators.fal_client import upload_image as _fal_upload
        url = _fal_upload(ref_path)
    except Exception as e:
        print(
            f"[remix] WARNING: failed to upload reference {ref_path.name} to "
            f"fal.ai ({e}). Differential mode will fall back to product-only "
            f"image_urls, which is the pre-fix behavior.",
            flush=True,
        )
        return None
    try:
        cache.write_text(url, encoding="utf-8")
    except OSError:
        pass
    return url


# ─── Differential-edit mode (surgical clone with source→target text swaps) ──
#
# Background: the default ("strategic") remix mode generates a verbose
# 1500-word prompt that *describes* a fresh image inspired by the reference.
# That works for fresh-brief generation but loses fidelity when the operator
# wants a near-identical layout with surgical text swaps (e.g. us-vs-them
# comparison ads). The differential mode produces a much shorter prompt
# that says "edit Image 1 with these specific swaps, preserve everything
# else." Mirrors how the operator manually prompts Higgsfield by hand.
#
# Cost: +$0.01 per remix run (one vision call) and +$0.02 per brief
# (one Claude mapping call). Significantly cheaper than the verbose
# strategic prompt because we skip the angle-rich brief→prompt step.


_DIFFERENTIAL_MAPPING_SYSTEM = """You are mapping advertisement copy from a
reference ad to a new brand, preserving the source ad's STRUCTURAL SHAPE
(word counts, grammatical patterns, line lengths) while rewriting the
content in the target customer's AUTHENTIC VOICE — not in brand-side
marketing language.

CRITICAL — IDENTITY OUTPUT IS FORBIDDEN.
The operator is paying for new copy. Returning `target: <same as source>`
defeats the entire purpose: NB2 will render the source ad's text exactly,
unchanged. This is a CORRECTNESS FAILURE — never do it.

  - If the source's literal content doesn't translate (e.g. source headline
    is "Probiotic Chew for dogs" and the new product is for humans), DO
    NOT echo the source. Compress the brief's hook to fit the source's
    word count, OR paraphrase the persona's main pain.
  - If you genuinely cannot produce a target (you've thought hard and
    nothing fits), output the literal string "[MAPPING_FAILED]" as the
    target — the operator will edit it manually. NEVER echo the source as
    a fallback.

INPUTS YOU WILL RECEIVE:
  1. SOURCE TEXT INVENTORY — every text element from the reference, each
     annotated with its exact word count. This is the structural envelope
     your targets must fit. Typography fidelity depends on word-count match.
  2. TARGET BRIEF — the ad concept being remixed (hook, callouts, CTA).
     The brief is written in BRAND voice (marketing jargon, clinical
     terms). You will translate that intent into ICP voice for the ad.
  3. ICP VOICE PACK — the persona's language_patterns + verbatim
     customer_language quotes pulled from their avatar. THIS IS THE
     REGISTER your target text must match. The customer talks this way.
     The brand does not.

RULES (priority order — break ties in favor of the higher rule):

  R1. WORD COUNT FIT (hard constraint).
      Target word count MUST be within ±1 of source word count.
        - source 1 word  → target 1-2 words
        - source 2 words → target 1-3 words
        - source 3 words → target 2-4 words
        - source 5+ words → target source_words-1 to source_words+1
      If you cannot fit the brief's idea into the source's envelope,
      COMPRESS the idea, do NOT exceed the envelope. A 2-word source
      slot cannot hold a 6-word brief callout — the layout breaks.

  R2. ICP VOICE (strong rewrite).
      The brief's wording is brand-side marketing voice ("Viability
      failure", "Colonization lottery", "1 trillion stable bioactives
      delivered directly"). Customers don't talk this way. They talk
      like the avatar's customer_language quotes.

      Rewrite the brief's content as if the customer is observing or
      complaining or describing the result. Lean on the avatar quotes.

      Example translations for a Burnout Biohacker avatar whose customer_
      language includes "I've tried probiotics before and honestly didn't
      notice much" and "Eating clean, working out, and still bloated":

        brief: "Viability failure"           → "Same bloat"
        brief: "Colonization lottery"        → "Still off"
        brief: "Delivery gauntlet"           → "No change"
        brief: "Improved gut regularity"     → "Regular again"
        brief: "1 trillion stable bioactives" → "Actually works"

      The customer's voice is short, plain, observational. The brand's
      voice is long, technical, claim-rich. ALWAYS lean toward the
      customer's voice for pain callouts, benefit callouts, and headlines
      that describe state. Lean toward the brand's wording ONLY for
      explicit brand wordmarks (brand name, product name).

  R3. ROLE PRESERVATION.
      A source headline maps to a headline. A source callout maps to a
      callout. A source CTA maps to a CTA. Brand wordmarks map to the
      target brand name (e.g. "PetLab Co." → "SecondKind"). Decorative
      product-label text ("Net Contents: 4.23 oz", "SALMON FLAVOR")
      maps to "[PRESERVE AS-IS]" — these belong on the bottle, not the
      ad copy, and we don't try to translate them.

  R4. MARKER PRESERVATION.
      If the source line starts with ❌, X, •, ★, ✅, →, ™, or ®, KEEP
      those exact markers at the start of the target. They are part of
      the typographic role.

  R5. [REMOVE] is RESTRICTED to fine-print / decoration / bodycopy roles.
      [REMOVE] is the escape hatch for content that genuinely has no
      analog in the new brand: competitor legalese, "All dogs 12+ weeks",
      category-specific badges, paragraph-length supporting copy the new
      brand doesn't need.

      [REMOVE] is FORBIDDEN for these roles — they are MUST-REPLACE:
        - headline / subheadline
        - callout / callout-pain / callout-benefit
        - brand
        - cta

      When the source's literal content seems untranslatable (e.g.
      source headline is "Probiotic Chew for dogs" and the new product
      is a human supplement), DO NOT default to [REMOVE]. Instead:
        (a) Paraphrase the brief's hook to fit the source's word count,
            ignoring the source's specific category words.
        (b) Lean on the persona's customer_language to express the
            brief's intent in their voice.
        (c) Compress aggressively — a 7-word source slot can hold any
            6-8-word hook.
      Outputting [REMOVE] for a headline / callout / brand / cta line is
      a CORRECTNESS FAILURE. The operator wants their copy in that slot.

  R6. Two side panels (us-vs-them).
      When the source is a us-vs-them comparison (one side has ❌, other
      has ✅), the ❌ side describes the FAILURE STATE the persona is in
      WITHOUT your product. Use customer-language pain phrasing. The ✅
      side describes the RESULT STATE after your product. Use customer-
      language outcome phrasing. Both sides should sound like the same
      customer talking, not like a brand pitching.

THINK SILENTLY BEFORE WRITING. The reasoning steps below happen IN YOUR
HEAD ONLY. Your visible output is YAML only — see OUTPUT FORMAT at the
bottom of these rules. Do NOT print the plan, do not narrate, do not
write "Let me work through this" — those break the parser downstream.

STEP 0 (INTERNAL ONLY) — PLAN THE AD'S NARRATIVE.
  An ad is one connected idea, not a stack of disconnected sentences. Before
  filling slots, decide silently:
    - CORE MESSAGE: in one sentence, what is this ad saying?
    - SUPPORTING BEATS: 3 proof points / hooks that reinforce the core
      message — these will become your callouts.
    - ACTION: what does the headline ask the viewer to do or feel?
  Every target you write must serve this single narrative. Disjoint targets
  (headline says X, callouts say unrelated Y) produce broken ads.

  Example for a "probiotics don't survive" hook (this is YOUR INTERNAL
  thinking — DO NOT print this):
    CORE: "Most probiotics die before they help — ours doesn't."
    BEATS: (1) survival rate, (2) what makes ours different (mechanism),
           (3) the result the user feels
    ACTION: investigate the science

  The headline target compresses the CORE. The 3 callout targets are the
  3 BEATS. The CTA aligns with the ACTION. Brand wordmark just swaps names.

STEP 1 (INTERNAL ONLY) — FOR EACH SOURCE LINE, work through:
  (a) What's the role? (headline / callout-pain / callout-benefit / brand /
      CTA / fine-print)
  (b) What's the word count budget? (source_words ± 1)
  (c) Which part of the NARRATIVE goes here?
      - headline / subheadline → the CORE
      - callout-pain / callout (1st) → BEAT 1 (pain or survival problem)
      - callout-benefit / callout (2nd) → BEAT 2 (mechanism / proof)
      - callout (3rd) → BEAT 3 (result / payoff)
      - cta → the ACTION
      - brand → wordmark swap
      - fine-print → adapted legalese OR [PRESERVE AS-IS] only when the
        source's claim is generic enough to still apply (NEVER preserve
        competitor brand names — rewrite to remove them, or [REMOVE])
  (d) How would the avatar's customer talk about that beat, in <=
      word_count + 1 words?
  (e) Write the target. Then count words. If over budget, compress —
      do NOT echo the source.

OUTPUT FORMAT — VALID YAML ONLY. NO PROSE. NO PLANNING NARRATIVE.

Your entire visible response MUST start with the literal line `mapping:`
and contain nothing else. The CORE/BEATS/ACTION plan from STEP 0 stays in
your internal reasoning — it does NOT appear in your output. Same for
STEP 1's per-line analysis. The parser downstream is strict — any prose
before `mapping:` will break it and the operator will see [MAPPING_FAILED]
in every row.

Visible output template (this is ALL you produce):

mapping:
  - source: "exact source text 1"
    target: "target text 1"
  - source: "exact source text 2"
    target: "target text 2"

Be exhaustive — include EVERY source text element, in the input order.
NO markdown fences, NO commentary, NO "Here's the mapping:" preamble.
Start your response with `mapping:` on the very first line."""


def _compute_source_structure(source_texts: list[str]) -> list[dict]:
    """Annotate each source line with word_count + char_count.

    Pure-Python; no LLM call. Kept as a backward-compat shim for any caller
    still passing raw strings. New code should use the structured extractor
    (`_extract_visible_text_inventory_structured`) which returns role +
    position alongside the counts."""
    out: list[dict] = []
    for t in source_texts:
        stripped = (t or "").strip()
        words = stripped.split()
        out.append({
            "text": stripped,
            "position": "",
            "role": "callout",
            "word_count": len(words),
            "char_count": len(stripped),
        })
    return out


def _format_voice_pack(avatar: "CustomerAvatar | None") -> str:
    """Render the ICP voice pack — thin wrapper around `strategy.voice.format_voice_pack`.

    Kept as a module-local alias because earlier code in this file refers to
    the underscore-prefixed name. The shared implementation lives in
    `strategy.voice` so prompt_engine.py can import the same helper without
    creating a circular dependency with this module.
    """
    from strategy.voice import format_voice_pack
    return format_voice_pack(avatar)


# Roles where [REMOVE] is not an acceptable target — the operator wants
# their copy in those slots. The mapper sometimes gets cold feet when the
# source's literal content (e.g. "Probiotic Chew for dogs") doesn't translate
# cleanly into the new brand's category, and bails to [REMOVE]; the
# validation pass below catches that and re-issues with a "must produce a
# real target" instruction.
_MUST_REPLACE_ROLES = (
    "headline",
    "subheadline",
    "callout",
    "callout-pain",
    "callout-benefit",
    "brand",
    "cta",
)


def _validate_and_retry_mapping(
    *,
    mapping: list[dict[str, str]],
    brief: "CreativeBrief | None" = None,
    avatar: "CustomerAvatar | None" = None,
    max_retries_per_line: int = 1,
) -> list[dict[str, str]]:
    """Second-pass quality gate. Catches two failure modes:

    1. Target word count is off by >1 from source — re-issue with a "compress
       to N words" instruction.
    2. Target is [REMOVE] on a must-replace role (headline / callout / brand
       / cta) — re-issue with a "produce a real replacement, never abandon
       this slot" instruction.

    Skips [PRESERVE AS-IS] targets (intentional) and decoration / fine-print /
    bodycopy rows where [REMOVE] is legitimate.

    Cheap: only fires Claude for the offending lines, not the whole map."""
    if not mapping:
        return mapping

    voice_block = _format_voice_pack(avatar) if avatar else ""

    fixed: list[dict[str, str]] = []
    for item in mapping:
        src = (item.get("source") or "").strip()
        tgt = (item.get("target") or "").strip()
        role = (item.get("role") or "").strip().lower()
        if not src:
            fixed.append(item)
            continue

        # Failure mode #2: [REMOVE] on a must-replace role.
        if tgt.upper() == "[REMOVE]" and role in _MUST_REPLACE_ROLES:
            src_words = len(src.split())
            hook = (getattr(brief, "hook", "") or "").strip() if brief else ""
            callouts = list(getattr(brief, "benefit_callouts", []) or []) if brief else []
            cta_text = (getattr(brief, "cta", "") or "").strip() if brief else ""
            persona = (getattr(brief, "persona", "") or "").strip() if brief else ""
            pain = (getattr(brief, "pain_point", "") or "").strip() if brief else ""

            slot_intent = {
                "headline": f"the brief's hook: \"{hook}\"" if hook else
                            f"the persona's primary pain: \"{pain}\"",
                "subheadline": f"a supporting variant of the hook: \"{hook}\"",
                "brand": "the new brand name (use the brand wordmark)",
                "cta": f"the brief's CTA: \"{cta_text}\"" if cta_text else "an action prompt",
                "callout": f"one of these benefit callouts: {callouts}" if callouts else
                           f"a benefit phrase the {persona} persona would say",
                "callout-pain": f"the pain state without the product (persona: {persona}, pain: \"{pain}\")",
                "callout-benefit": f"the result state with the product. Use one of: {callouts}" if callouts else
                                  f"the result state the {persona} persona wants",
            }
            intent = slot_intent.get(role, "the brief's main message")

            forced_prompt = (
                f"{voice_block}\n"
                f"You wrote [REMOVE] for a source slot whose role is '{role}'. "
                f"That role is MUST-REPLACE — the operator wants their copy in "
                f"this slot.\n\n"
                f'  source: "{src}"  ({src_words} words, role: {role})\n'
                f"  budget: {max(1, src_words - 1)} to {src_words + 1} words\n"
                f"  fill with: {intent}\n\n"
                f"Rewrite a real target IN THE CUSTOMER'S VOICE, fitting the "
                f"word budget. Output ONLY the new target text — no quotes, "
                f"no YAML, no explanation, no [REMOVE]."
            )
            forced_system = (
                "You are rewriting one advertisement copy line to fill a slot "
                "that was wrongly marked [REMOVE]. The slot's role is "
                "must-replace. Produce a real target in the customer's voice, "
                "hitting the word budget. Output is one line of text."
            )
            try:
                new_tgt = claude_complete(
                    forced_prompt, system=forced_system, max_tokens=128,
                ).strip().strip('"').strip("'")
                if new_tgt and new_tgt.upper() != "[REMOVE]":
                    tgt = new_tgt
            except Exception:
                pass
            fixed.append({
                "source": src,
                "position": item.get("position", ""),
                "role": item.get("role", "callout"),
                "target": tgt,
            })
            continue

        if tgt.upper() in ("[REMOVE]", "[PRESERVE AS-IS]"):
            fixed.append(item)
            continue

        src_words = len(src.split())
        tgt_words = len(tgt.split())
        if abs(src_words - tgt_words) <= 1:
            fixed.append(item)
            continue

        # Out of envelope — retry with explicit compression instruction.
        retry_prompt = (
            f"{voice_block}\n"
            f"You produced this mapping but the target word count is wrong.\n\n"
            f'  source: "{src}"  ({src_words} words)\n'
            f'  current target: "{tgt}"  ({tgt_words} words)\n'
            f"  required: {max(1, src_words - 1)} to {src_words + 1} words\n\n"
            f"Rewrite the target IN THE CUSTOMER\\'S VOICE (using the language "
            f"patterns + customer quotes above as register reference) to fit "
            f"the required word count. Preserve any leading marker (❌, ✅, "
            f"•, ★) from the source. Output ONLY the new target text, "
            f"nothing else — no quotes, no YAML, no explanation."
        )
        retry_system = (
            "You are rewriting one advertisement copy line to fit a strict "
            "word-count envelope. Preserve meaning, match the customer voice "
            "register, hit the word count exactly. Output is one line of text."
        )
        try:
            new_tgt = claude_complete(
                retry_prompt, system=retry_system, max_tokens=128,
            ).strip().strip('"').strip("'")
            # Sanity check: the retry might still be off if Claude ignores
            # us. Keep the best of (original, retry) measured by closeness.
            new_words = len(new_tgt.split())
            if abs(src_words - new_words) < abs(src_words - tgt_words):
                tgt = new_tgt
        except Exception:
            pass

        fixed.append({
            "source": src,
            "position": item.get("position", ""),
            "role": item.get("role", "callout"),
            "target": tgt,
        })

    return fixed


def _generate_source_to_target_mapping(
    *,
    source_items: list[dict],
    brief: CreativeBrief,
    brand: Brand,
    product: Product,
    avatar: "CustomerAvatar | None" = None,
) -> list[dict[str, str]]:
    """Claude call: map each source text element to its target equivalent,
    in the ICP's voice, fitting the source's word-count envelope and
    preserving the source's role + position.

    `source_items` is a list of dicts from the structured vision extractor:
    `{text, position, role, word_count, char_count}`. Strings-only callers
    should pre-wrap via `_compute_source_structure`.

    Returns a list of `{"source", "position", "role", "target"}` dicts in
    the same order as `source_items`. Target may be "[REMOVE]" (delete from
    image) or "[PRESERVE AS-IS]" (decorative product-label text we don't
    touch).

    Pre-processing: trims `brief.benefit_callouts` to the number of callout-
    role slots in the source. Before this trim, briefs with 5 callouts and
    sources with 2 slots forced Claude to either pack multiple ideas per
    slot (bloats target word count) or hallucinate ghost slots (NB2 then
    renders extra text). With the trim, Claude works with the right amount
    of content for the envelope.

    `avatar` is optional but strongly recommended — without it the mapper
    falls back to brief-only context and the output will sound more like
    brand-pitch than customer-voice.

    Used by the differential remix mode to build a surgical-edit prompt.
    """
    if not source_items:
        return []

    # Pre-trim brief callouts to the source's callout-slot count. Sources
    # have a fixed number of callout-shaped holes; pumping extra brief
    # callouts in only forces Claude to either compress them together
    # (over-budget text) or invent slots (NB2 then renders extra text not
    # in the swap table). Trim upstream so the mapper sees a matched count.
    callout_slots = sum(
        1 for item in source_items
        if str(item.get("role") or "").startswith("callout")
    )
    raw_callouts = brief.benefit_callouts or []
    if callout_slots > 0:
        trimmed_callouts = raw_callouts[:callout_slots]
    else:
        trimmed_callouts = []  # no slots → callouts won't be rendered anyway

    # Build the inventory block: include role + position so the mapper can
    # match content type to slot type (a headline-role brief.hook goes
    # into the headline-role source slot, not a callout).
    def _fmt_role_pos(item: dict) -> str:
        role = str(item.get("role") or "callout")
        pos = str(item.get("position") or "")
        if pos:
            return f"[role: {role}, pos: {pos}]"
        return f"[role: {role}]"

    inventory_block = "\n".join(
        f'  - "{s["text"]}"  ({s["word_count"]} word{"s" if s["word_count"] != 1 else ""}) '
        f'{_fmt_role_pos(s)}'
        for s in source_items
    )

    benefit_callouts_block = "\n".join(
        f"    - {c}" for c in trimmed_callouts
    ) or "    (none)"

    voice_pack = _format_voice_pack(avatar)
    voice_block = voice_pack + "\n" if voice_pack else (
        "(no ICP voice pack available — infer voice from the brief's persona "
        "name and lean toward short, plain, observational customer-style "
        "phrasing rather than brand-marketing language)\n\n"
    )

    # Note: benefit_callouts are pre-trimmed to N=callout_slots. Spell out
    # the count so the mapper doesn't think it can invent slots to fit
    # extras.
    callout_count_note = (
        f"  (NOTE: the source has {callout_slots} callout slot(s). The "
        f"benefit_callouts above have been pre-trimmed to fit.)"
        if callout_slots > 0 else
        f"  (NOTE: the source has 0 callout-role slots — do NOT add new "
        f"callout text to brand/headline/cta slots.)"
    )

    user_prompt = f"""SOURCE AD TEXT INVENTORY (extracted via vision, top→bottom, with word counts + role + position):

{inventory_block}

{voice_block}TARGET BRIEF — the new ad's content to map onto the source layout:

  brand: {brand.name}
  product: {product.name}
  persona: {brief.persona}
  hook: {brief.hook}
  hook_type: {brief.hook_type}
  cta: {brief.cta}
  benefit_callouts:
{benefit_callouts_block}
{callout_count_note}
  framework: {brief.framework}
  awareness_level: {getattr(brief.awareness_level, 'value', '') if brief.awareness_level else ''}
  pain_point: {brief.pain_point or '(none)'}

ROLE-MATCH the source slots:
  - headline / subheadline source slots ← brief.hook (compressed to fit)
  - callout-pain source slots         ← pain-side content (avatar pain language)
  - callout-benefit source slots      ← benefit-side content (trimmed benefit_callouts)
  - callout (generic) source slots    ← brief.benefit_callouts (trimmed)
  - brand source slots                ← brand name / product name
  - cta source slots                  ← brief.cta
  - bodycopy source slots             ← compress brief.body_copy or pain_point
  - fine-print / decoration slots     ← "[PRESERVE AS-IS]" unless the new brand needs different legalese

Map each source text element to its target equivalent now. Honor R1 (word
count within ±1) and R2 (ICP voice, not brand voice). Output YAML only."""

    raw = claude_complete(
        user_prompt,
        system=_DIFFERENTIAL_MAPPING_SYSTEM,
        max_tokens=2048,
    )
    body = _strip_code_fences(raw)

    # Defensive extraction: the system prompt tells Claude to start the
    # response with `mapping:`, but the planning pass we added makes Claude
    # occasionally emit STEP 0 / STEP 1 thinking as prose first. Find the
    # first `mapping:` line and parse from there so a leaked planning
    # preamble doesn't break the whole run.
    for line_idx, line in enumerate(body.splitlines()):
        if line.lstrip().startswith("mapping:") and not line.lstrip().startswith("mapping:s"):
            body = "\n".join(body.splitlines()[line_idx:])
            break

    # Failure-sentinel fallback used twice below. Writing the sentinel
    # surfaces the failure in the dashboard mapping editor — silent identity
    # (target=source) looks like a working run that just happens to produce
    # the reference back, which is exactly the bug we want to avoid.
    def _failed_mapping(reason: str) -> list[dict]:
        print(
            f"  [mapper] sentinel fallback ({reason}) — writing "
            f"[MAPPING_FAILED] targets for operator review.",
            flush=True,
        )
        return [
            {
                "source": item["text"],
                "position": item.get("position", ""),
                "role": item.get("role", "callout"),
                "target": f"[MAPPING_FAILED — {reason}; edit me]",
            }
            for item in source_items
        ]

    try:
        data = yaml.safe_load(body) or {}
    except Exception as e:
        return _failed_mapping(f"YAML parse failed: {type(e).__name__}")

    items = data.get("mapping") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return _failed_mapping("LLM output had no 'mapping:' list")

    # Build src→target lookup from LLM output. Index by exact source text so
    # ordering quirks in the LLM response don't shift slots. Any source the
    # LLM dropped gets "[REMOVE]" (less risky than identity-mapping an
    # English string into a Spanish slot, for example).
    llm_targets: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        src = str(item.get("source") or "").strip()
        tgt = str(item.get("target") or "").strip()
        if src:
            llm_targets[src] = tgt or "[REMOVE]"

    result: list[dict[str, str]] = []
    for src_item in source_items:
        src_text = src_item["text"]
        tgt = llm_targets.get(src_text, "[REMOVE]")
        result.append({
            "source": src_text,
            "position": src_item.get("position", ""),
            "role": src_item.get("role", "callout"),
            "target": tgt,
        })

    # Catch the case where Claude returned valid YAML but every target
    # equals its source. Claude sometimes does this when it can't translate
    # the source's category to the new brand AND doesn't want to use [REMOVE]
    # (it's a "preserve" cop-out). Treat as a failure so the operator sees it.
    must_replace_identities = [
        r for r in result
        if r["source"].strip() == r["target"].strip()
        and (r.get("role") or "").lower() in _MUST_REPLACE_ROLES
    ]
    if len(must_replace_identities) >= 3:
        return _failed_mapping(
            f"LLM returned source=target for {len(must_replace_identities)} "
            f"must-replace roles"
        )

    # Second-pass quality gate — fix any out-of-envelope target.
    result = _validate_and_retry_mapping(mapping=result, brief=brief, avatar=avatar)
    return result


def _build_differential_prompt(
    *,
    brief: CreativeBrief,
    product: Product,
    mapping: list[dict[str, str]],
    creative_direction: str,
    aspect_ratio: str,
    scene_cleanup: str = "",
) -> str:
    """Assemble a surgical-edit NB2 prompt from a source→target mapping.

    Output ~250 words. Tells NB2: edit Image 1, swap product with Image 2,
    apply text swaps from the mapping table, optionally apply a setting
    delta from creative_direction, preserve everything else.

    This is intentionally short. The verbose composition / lighting /
    photography spec from prompt_from_brief() is NOT generated for
    differential mode — the reference image carries that information."""
    lines: list[str] = []
    lines.append(
        "This is a SURGICAL EDIT of Image 1 (the reference ad). Image 2 "
        "is the replacement product. Apply ONLY the changes listed below; "
        "preserve every other visual element of Image 1 exactly — "
        "composition, layout, font family and weight, color palette, "
        "lighting register, decorative marks (❌, ✅, frosted cards, "
        "panels, badges), hand positions, and product orientation."
    )
    lines.append("")

    # Product swap (always present). Hand-pose adaptation note: if the
    # source ad shows a hand reaching INTO an open product (jar lid off,
    # pouring, scooping), but the new product is a closed bottle or sealed
    # container, naturally adjust the hand pose to fit. Otherwise we get
    # nonsense images of a hand reaching into a closed lid.
    lines.append("PRODUCT SWAP:")
    lines.append(
        f"  - Replace the product container/package shown in Image 1 with "
        f"the {product.name} from Image 2. Keep the same general hand "
        f"position in the frame and same lighting on the product.\n"
        f"  - HAND-POSE ADAPTATION: if the source ad shows a hand "
        f"reaching INTO an open product (e.g. fingers inside a jar with "
        f"the lid off, pouring, scooping out capsules) but the "
        f"{product.name} from Image 2 is CLOSED (sealed lid, no opening "
        f"visible), naturally adjust the hand to PRESENT the closed "
        f"product instead — holding it up, displaying it, fingers around "
        f"the side of the bottle. Do NOT render a hand reaching into a "
        f"closed lid; that's physically impossible and breaks the image."
    )
    lines.append("")

    # Scene cleanup — operator-supplied "remove from the scene" instructions
    # for non-text elements (animals, props, model, background). This is the
    # automated version of the manual "remove the dog" pass: when the source
    # ad is a pet-supplement remix going to a human-supplement brand, the
    # dog has to go; nothing else in the pipeline catches that.
    sc = (scene_cleanup or "").strip()
    if sc:
        lines.append("SCENE CLEANUP — remove these non-text elements:")
        for line in sc.splitlines():
            line = line.strip(" -•").strip()
            if line:
                lines.append(f"  - {line}")
        lines.append(
            "  - After removal, naturally infill the space (extend background, "
            "shift remaining elements only as needed). Do NOT introduce new "
            "scene elements to fill the gap."
        )
        lines.append("")

    # Text swaps. Position + role labels (when available) give NB2 a clearer
    # anchor than text-only swaps — "at top-center, replace headline 'X' with
    # 'Y'" beats "replace 'X' with 'Y'" because there's no ambiguity when
    # the same string appears more than once in the source.
    #
    # Decoration-role items (product-label text like "Net Contents: 4.23 oz",
    # "SALMON FLAVOR", barcodes) are filtered out of the swap table — they
    # belong on the bottle, get carried over by the product image, and
    # enumerating them in the swap table just inflates the prompt and risks
    # NB2 trying to "render" them on top of the new product label.
    text_swaps = [
        m for m in mapping
        if m.get("source")
        and (m.get("role") or "").strip().lower() != "decoration"
    ]
    if text_swaps:
        lines.append(
            "TEXT SWAPS — MANDATORY. For each line below, the source text "
            "currently appearing in Image 1 MUST be replaced with the "
            "target text. This is not optional and not a suggestion. The "
            "swap table is the contract for this edit:\n"
            "  - render target AT THE SAME POSITION as source\n"
            "  - keep the SAME font family, weight, color, alignment\n"
            "  - keep any leading marker characters (❌, ✅, •, ★)\n"
            "  - DO NOT change typography style\n"
            "  - where target is [REMOVE], delete that element entirely\n"
            "  - where target is [PRESERVE AS-IS], render source text unchanged"
        )
        for m in text_swaps:
            src = m["source"].replace('"', '\\"')
            tgt = m["target"].replace('"', '\\"')
            pos = (m.get("position") or "").strip()
            role = (m.get("role") or "").strip()
            anchor_parts = [p for p in (pos, role) if p]
            anchor = f"[{', '.join(anchor_parts)}] " if anchor_parts else ""
            if tgt.upper() == "[REMOVE]":
                lines.append(
                    f'  - {anchor}"{src}"  →  [REMOVE this element entirely]'
                )
            elif tgt.upper() == "[PRESERVE AS-IS]":
                lines.append(
                    f'  - {anchor}"{src}"  →  [PRESERVE AS-IS — render unchanged]'
                )
            else:
                lines.append(f'  - {anchor}"{src}"  →  "{tgt}"')
        lines.append("")

        # Allowlist suffix: enumerate the exact final-image text inventory.
        # NB2 obeys allowlists more reliably than denylists ("render ONLY
        # these N strings" outperforms "do not add new text"). This is the
        # differential-mode analogue of the strategic-mode density suffix.
        # Decoration-role text isn't enumerated here either — the product
        # image carries it, and NB2 doesn't need a permit to keep it.
        rendered_targets = [
            m["target"].strip() for m in text_swaps
            if m.get("target")
            and m["target"].strip().upper() not in ("[REMOVE]", "[PRESERVE AS-IS]")
        ]
        preserve_targets = [
            m["source"].strip() for m in text_swaps
            if (m.get("target") or "").strip().upper() == "[PRESERVE AS-IS]"
        ]
        final_inventory = rendered_targets + preserve_targets
        if final_inventory:
            lines.append(
                f"FINAL TEXT INVENTORY — the output image's primary overlay "
                f"text contains EXACTLY these {len(final_inventory)} element"
                f"(s), and NO others. (Product-label text printed on the "
                f"package itself carries over from Image 2 and is exempt.):"
            )
            for t in final_inventory:
                lines.append(f'  - "{t}"')
            lines.append("")

    # Operator-supplied creative-direction delta (optional)
    cd = (creative_direction or "").strip()
    if cd:
        lines.append("SETTING / STYLE CHANGE (operator-supplied delta):")
        lines.append(f"  - {cd}")
        lines.append(
            "  - Apply this change to the background / lighting environment "
            "only. The product, hands, and overall composition stay the same."
        )
        lines.append("")

    # Preserve clause
    lines.append("PRESERVE (do not modify):")
    lines.append("  - Composition, panel positions, frosted cards, decorative overlays")
    lines.append("  - Font family, weight, kerning, text size relative to elements")
    lines.append("  - X-marks (❌) and check-marks (✅) and their colors/positions")
    lines.append("  - Hand poses, product orientation, lighting direction")
    lines.append(
        "  - Total number of text elements (only the ones in the swap table "
        "above change; the rest remain visually identical)"
    )
    lines.append("")

    # Negative
    lines.append(
        "Negative: do NOT add FDA disclaimers, body copy paragraphs, "
        "extra badges, additional brand wordmarks, customer review text, "
        "ratings, or any text element not in the swap table above. Do not "
        "introduce new decorative elements, callouts, or visual zones."
    )
    lines.append("")
    lines.append(f"{aspect_ratio} aspect ratio.")

    return "\n".join(lines)


# ─── Staged differential mode (3-pass: product → text → model/character) ────
#
# Background: NB2 collapses ALL changes into a single shot in the standard
# differential prompt — product swap + text swaps + setting delta + preserve
# clause, all at once. Each instruction competes for attention. The operator's
# manual Higgsfield workflow that produced the cleanest results did three
# sequential edits, each with one job. Staged mode mirrors that:
#
#   Pass 1 (NB2): swap product. Keep text + layout pixel-identical.
#   Pass 2 (NB2): swap text. Keep product + layout pixel-identical.
#   Pass 3 (Higgsfield Soul, optional): swap the model/character.
#
# Cost: 3x NB2 calls per brief (~$0.24 vs $0.08 standard). Intermediate
# images saved to disk for inspection so the operator can spot which pass
# introduced any drift.


def _build_pass1_product_swap_prompt(
    product: Product,
    aspect_ratio: str,
    scene_cleanup: str = "",
) -> str:
    """Pass 1 prompt: replace the product (and optionally remove scene
    elements). Lock text + layout in place.

    NB2 receives [reference, product] as image_urls. The prompt is tight
    so NB2 doesn't have to triage competing edits. When scene_cleanup is
    provided (e.g. "remove the dog"), it folds into this pass — the
    operator's manual workflow handled cleanup alongside the product swap
    and we mirror that."""
    cleanup = (scene_cleanup or "").strip()
    cleanup_block = ""
    if cleanup:
        cleanup_lines = []
        for line in cleanup.splitlines():
            line = line.strip(" -•").strip()
            if line:
                cleanup_lines.append(f"  - {line}")
        cleanup_block = (
            "\nSCENE CLEANUP — also remove these non-text elements from the "
            "scene:\n"
            + "\n".join(cleanup_lines)
            + "\n  - Naturally infill the space (extend the existing "
            "background, do NOT add new scene elements to fill the gap).\n"
        )
    return (
        "This is a SURGICAL EDIT of Image 1 (the reference ad). Image 2 is "
        f"the replacement product ({product.name}).\n\n"
        "PRODUCT SWAP — replace the product:\n"
        "  - Replace the product container/package shown in Image 1 with "
        f"the {product.name} from Image 2.\n"
        "  - Keep the SAME general hand position in the frame and same "
        "lighting on the product.\n"
        "  - HAND-POSE ADAPTATION: if the source ad shows a hand reaching "
        "INTO an open product (e.g. fingers inside a jar with the lid "
        f"off, pouring, scooping out capsules) but the {product.name} "
        "from Image 2 is CLOSED (sealed lid, no opening visible), "
        "naturally adjust the hand to PRESENT the closed product "
        "instead — holding it up, displaying it, fingers around the "
        "side of the bottle. Do NOT render a hand reaching into a closed "
        "lid; that's physically impossible and breaks the image."
        f"{cleanup_block}\n"
        "PRESERVE PIXEL-IDENTICALLY — do NOT change any of the following:\n"
        "  - Every word of on-image text (headlines, callouts, brand "
        "wordmarks, CTAs, badges, fine print) — character-for-character.\n"
        "  - Every font, weight, color, size, alignment, and decorative "
        "mark (❌, ✅, •, ★, frosted cards, panels, badges).\n"
        "  - Composition, framing, color palette, lighting register, "
        "background (apart from any cleanup above), and the human figure "
        "(unless the cleanup list names it).\n\n"
        "Do NOT change any text content. Do NOT introduce new text or new "
        "scene elements. The output is Image 1 with the product swapped "
        "(hand pose adapted if needed) "
        + ("and the listed cleanup applied — nothing else." if cleanup
           else "— nothing else.")
        + f"\n\n{aspect_ratio} aspect ratio."
    )


def _build_pass2_text_swap_prompt(
    mapping: list[dict[str, str]],
    aspect_ratio: str,
) -> str:
    """Pass 2 prompt: apply text swaps to the pass-1 output. Lock product +
    layout in place.

    NB2 receives [pass1_output] as the sole image_url. The prompt enumerates
    every text swap and the FINAL TEXT INVENTORY allowlist. Decoration-role
    items (product-label text) are filtered — the product reference carries
    those, and enumerating them in the swap table only invites NB2 to
    re-render them over the new label."""
    text_swaps = [
        m for m in mapping
        if m.get("source")
        and (m.get("role") or "").strip().lower() != "decoration"
    ]

    lines: list[str] = []
    lines.append(
        "This is a SURGICAL EDIT of Image 1. The product and layout in "
        "Image 1 are CORRECT — keep them. The only thing to change is the "
        "on-image text per the swap table below."
    )
    lines.append("")

    if text_swaps:
        lines.append(
            "TEXT SWAPS — MANDATORY. For each line below, the source text "
            "currently appearing in Image 1 MUST be replaced with the "
            "target text. This is not optional and not a suggestion. The "
            "swap table is the contract for this edit:\n"
            "  - render target AT THE SAME POSITION as source\n"
            "  - keep the SAME font family, weight, color, alignment\n"
            "  - keep any leading marker characters (❌, ✅, •, ★)\n"
            "  - where target is [REMOVE], delete that element entirely\n"
            "  - where target is [PRESERVE AS-IS], render source text unchanged\n"
            "  - where target starts with [MAPPING_FAILED, that row was a "
            "Claude failure during mapping — render the source text "
            "unchanged but the operator will need to fix it before "
            "shipping the ad"
        )
        for m in text_swaps:
            src = m["source"].replace('"', '\\"')
            tgt = m["target"].replace('"', '\\"')
            pos = (m.get("position") or "").strip()
            role = (m.get("role") or "").strip()
            anchor_parts = [p for p in (pos, role) if p]
            anchor = f"[{', '.join(anchor_parts)}] " if anchor_parts else ""
            if tgt.upper() == "[REMOVE]":
                lines.append(
                    f'  - {anchor}"{src}"  →  [REMOVE this element entirely]'
                )
            elif tgt.upper() == "[PRESERVE AS-IS]":
                lines.append(
                    f'  - {anchor}"{src}"  →  [PRESERVE AS-IS — render unchanged]'
                )
            else:
                lines.append(f'  - {anchor}"{src}"  →  "{tgt}"')
        lines.append("")

        rendered_targets = [
            m["target"].strip() for m in text_swaps
            if m.get("target")
            and m["target"].strip().upper() not in ("[REMOVE]", "[PRESERVE AS-IS]")
        ]
        preserve_targets = [
            m["source"].strip() for m in text_swaps
            if (m.get("target") or "").strip().upper() == "[PRESERVE AS-IS]"
        ]
        final_inventory = rendered_targets + preserve_targets
        if final_inventory:
            lines.append(
                f"FINAL TEXT INVENTORY — the output image's primary overlay "
                f"text contains EXACTLY these {len(final_inventory)} "
                f"element(s), and NO others. (Product-label text printed on "
                f"the package itself is exempt — leave it as-is.):"
            )
            for t in final_inventory:
                lines.append(f'  - "{t}"')
            lines.append("")

    lines.append("PRESERVE PIXEL-IDENTICALLY:")
    lines.append("  - The product shown in Image 1 (already swapped — keep it)")
    lines.append("  - Composition, framing, color palette, lighting")
    lines.append("  - Decorative marks (❌, ✅, panels, frosted cards, badges)")
    lines.append("  - Hand positions, model pose, background, props")
    lines.append("")

    lines.append(
        "Do NOT change the product. Do NOT introduce new visual elements. "
        "Do NOT add text outside the FINAL TEXT INVENTORY above."
    )
    lines.append("")
    lines.append(f"{aspect_ratio} aspect ratio.")

    return "\n".join(lines)


def _build_pass3_model_swap_prompt(aspect_ratio: str) -> str:
    """Pass 3 prompt for Higgsfield Soul: identity-lock the person/model.

    Sent alongside soul_id + the pass-2 output as reference_image_url. Soul_2
    is already identity-locked by soul_id; the reference supplies layout +
    text + product. Prompt is short and instruction-only because soul_2 with
    a reference is much more directive than text-to-image."""
    return (
        "Recreate the reference image EXACTLY — same layout, same product, "
        "same on-image text, same composition, same lighting, same hand "
        "positions, same decorative marks. The ONLY change: the person/face "
        "shown in the ad is the soul character (identity-locked).\n\n"
        "PRESERVE PIXEL-IDENTICALLY:\n"
        "  - All on-image text (every word, every font, every position)\n"
        "  - Product container, hand positions, product orientation\n"
        "  - Composition, framing, color palette, lighting, background\n"
        "  - Decorative marks (❌, ✅, panels, frosted cards, badges)\n\n"
        f"{aspect_ratio} aspect ratio."
    )


def _build_pass3_model_swap_prompt_nb2(
    model_descriptor: str,
    aspect_ratio: str,
) -> str:
    """Pass 3 prompt for NB2 (text-only model swap, no Higgsfield required).

    Mirrors the operator's manual workflow: "replace the model in the picture
    with a middle-aged white woman". The descriptor is free-text prose
    (demographic / styling / vibe) supplied by the operator or pulled from
    the persona's avatar YAML. NB2 receives [stage2_output] as the sole
    image_url and edits in place — same person-pose, same hands on the
    product, just a different model.

    This is the preferred Stage 3 path because (a) it doesn't require a
    trained soul, (b) it lets the operator describe the model directly in
    the brief's persona terms, and (c) NB2 with a single-image edit is
    more directive than soul_2 with a reference."""
    desc = (model_descriptor or "").strip()
    return (
        "This is a SURGICAL EDIT of Image 1. Replace ONLY the human "
        "model/person shown in the image. Keep everything else "
        "pixel-identical.\n\n"
        "MODEL SWAP:\n"
        f"  - The person/model in Image 1 is now: {desc}\n"
        "  - Match the same pose, same hand position holding the product, "
        "same body angle, same wardrobe register (casual/professional/etc), "
        "same framing. Only the person's identity (face, age, ethnicity, "
        "hair, body type) changes to fit the description above.\n\n"
        "PRESERVE PIXEL-IDENTICALLY:\n"
        "  - All on-image text (every word, every font, every position)\n"
        "  - Product container, hand positions, product orientation\n"
        "  - Composition, framing, color palette, lighting, background, "
        "props\n"
        "  - Decorative marks (❌, ✅, panels, frosted cards, badges, pills)\n\n"
        "Do NOT change the product. Do NOT change the text. Do NOT change "
        "the layout. ONLY the person's identity changes.\n\n"
        f"{aspect_ratio} aspect ratio."
    )


def _generate_remix_images_staged(
    briefs_data: list[dict],
    *,
    remix_path: Path,
    images_dir: Path,
    num_images: int,
    aspect_ratio: str,
    thinking_level: str = "disabled",
    final_pass_soul: bool = True,
) -> list[Path]:
    """Staged 3-pass differential image generation.

    Per brief:
      1. NB2 edit: [reference, product] + product-swap-only prompt
         → <brief_id>_stage1_product.png
      2. NB2 edit: [stage1] + text-swap-only prompt
         → <brief_id>_stage2_text.png
      3. (if soul_id ready AND final_pass_soul) Higgsfield soul_2:
         reference_image_url=stage2, soul_id=<persona's trained character>
         → <brief_id>_stage3_model.png
         Otherwise stage2 is also the final.

    The final image (stage3 if soul present, else stage2) is also saved as
    `<brief_id>_1x1.png` so downstream tooling (dashboard, refinements)
    keeps finding outputs at the standard path.

    Requires:
      - mappings/<brief_id>.yaml on disk for each brief (differential mode)
      - reference.<ext> on disk (auto-uploaded once per run)

    Returns the list of FINAL image paths (one per brief × num_images)."""
    from generators.fal_client import generate_and_save, upload_image as _fal_upload
    from generators.image_generator import _get_product_image_urls

    if not briefs_data:
        return []

    # Resolve mode + reference upload — required for staged.
    first_prompt = remix_path / "prompts" / f"{briefs_data[0]['brief_id']}.txt"
    run_mode = (
        _detect_remix_mode_from_prompt(first_prompt) if first_prompt.exists() else
        "strategic"
    )
    if run_mode != "differential":
        raise ValueError(
            "Staged image generation requires a differential-mode remix run "
            "(needs the per-brief mappings/*.yaml that differential mode "
            "produces). This run was generated in '{}' mode.".format(run_mode)
        )

    reference_url = _resolve_remix_reference_url(remix_path)
    if not reference_url:
        raise ValueError(
            "Staged mode requires the archived reference image to be "
            "uploadable, but no reference was found in "
            f"{remix_path}. Re-run `adc remix --reference ...` to recreate it."
        )

    client_slug = briefs_data[0]["client"]
    product_name = briefs_data[0]["product"]
    product = _load_product_flexible(
        client_slug, product_name.lower().replace(" ", "-")
    )
    product_urls = _get_product_image_urls(product, client_slug)

    # Load operator-supplied directives that were persisted at remix time.
    # scene_cleanup fires in pass 1 alongside the product swap. model_descriptor
    # drives pass 3 (NB2 text-only model swap); empty descriptor + final_pass_soul
    # falls back to the soul_2 path; empty descriptor + no soul stops at pass 2.
    scene_cleanup = ""
    model_descriptor = ""
    sc_path = remix_path / "scene_cleanup.txt"
    if sc_path.exists():
        try:
            scene_cleanup = sc_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    md_path = remix_path / "model_descriptor.txt"
    if md_path.exists():
        try:
            model_descriptor = md_path.read_text(encoding="utf-8").strip()
        except OSError:
            pass

    print(
        f"[remix] Staged mode: {len(briefs_data)} brief(s) × 3 passes each."
        + (f" Scene cleanup: '{scene_cleanup[:60]}'." if scene_cleanup else "")
        + (f" Model descriptor: '{model_descriptor[:60]}'." if model_descriptor else "")
        + f" Final pass via Higgsfield Soul: "
        f"{'enabled' if final_pass_soul else 'disabled'}.",
        flush=True,
    )

    saved_paths: list[Path] = []
    for brief_data in briefs_data:
        brief_id = brief_data["brief_id"]
        mapping = _load_brief_mapping(remix_path, brief_id)
        if not mapping:
            print(
                f"  [skip staged] {brief_id} — no mapping at "
                f"mappings/{brief_id}.yaml. Run `adc remix --mode differential` first.",
                flush=True,
            )
            continue

        for i in range(num_images):
            suffix = f"_{i+1}" if num_images > 1 else ""
            stage1_path = images_dir / f"{brief_id}{suffix}_stage1_product.png"
            stage2_path = images_dir / f"{brief_id}{suffix}_stage2_text.png"
            stage3_path = images_dir / f"{brief_id}{suffix}_stage3_model.png"
            final_path = images_dir / f"{brief_id}{suffix}_1x1.png"

            # ── Pass 1: product swap (+ scene cleanup if provided) ───────
            try:
                p1_results = generate_and_save(
                    prompt=_build_pass1_product_swap_prompt(
                        product, aspect_ratio, scene_cleanup=scene_cleanup,
                    ),
                    product_image_urls=[reference_url] + product_urls,
                    save_dir=images_dir,
                    filename_prefix=f"{brief_id}{suffix}_stage1_product_raw",
                    aspect_ratio=aspect_ratio,
                    num_images=1,
                    thinking_level=thinking_level,
                )
            except Exception as e:
                print(f"  [fail stage1] {brief_id}: {e}", flush=True)
                continue
            if not p1_results or not p1_results[0].local_path:
                print(f"  [fail stage1] {brief_id}: NB2 returned no image", flush=True)
                continue
            p1_results[0].local_path.replace(stage1_path)

            stage1_url = _fal_upload(stage1_path)

            # ── Pass 2: text swap ────────────────────────────────────────
            try:
                p2_results = generate_and_save(
                    prompt=_build_pass2_text_swap_prompt(mapping, aspect_ratio),
                    product_image_urls=[stage1_url],
                    save_dir=images_dir,
                    filename_prefix=f"{brief_id}{suffix}_stage2_text_raw",
                    aspect_ratio=aspect_ratio,
                    num_images=1,
                    thinking_level=thinking_level,
                )
            except Exception as e:
                print(f"  [fail stage2] {brief_id}: {e}", flush=True)
                # Stage 1 is the best we have — promote it to the final slot
                # so the operator still sees output rather than an empty run.
                shutil.copy2(stage1_path, final_path)
                saved_paths.append(final_path)
                continue
            if not p2_results or not p2_results[0].local_path:
                print(f"  [fail stage2] {brief_id}: NB2 returned no image", flush=True)
                shutil.copy2(stage1_path, final_path)
                saved_paths.append(final_path)
                continue
            p2_results[0].local_path.replace(stage2_path)

            # ── Pass 3: model/character swap ─────────────────────────────
            # Three possible paths, in priority order:
            #   (a) model_descriptor provided → NB2 text-mode edit. Preferred
            #       because it mirrors the operator's manual "replace the
            #       model with X" workflow and doesn't need a trained soul.
            #   (b) final_pass_soul=True AND persona has a ready soul_id →
            #       Higgsfield soul_2 with stage2 as reference. Identity-locked.
            #   (c) Neither → stop at stage 2, copy it as final.
            soul_id = (
                _get_soul_id_for_brief(brief_data) if final_pass_soul else None
            )
            stage3_done = False

            if model_descriptor:
                # Path (a): NB2 text-mode model swap.
                try:
                    p3_results = generate_and_save(
                        prompt=_build_pass3_model_swap_prompt_nb2(
                            model_descriptor, aspect_ratio,
                        ),
                        product_image_urls=[_fal_upload(stage2_path)],
                        save_dir=images_dir,
                        filename_prefix=f"{brief_id}{suffix}_stage3_model_raw",
                        aspect_ratio=aspect_ratio,
                        num_images=1,
                        thinking_level=thinking_level,
                    )
                    if p3_results and p3_results[0].local_path:
                        p3_results[0].local_path.replace(stage3_path)
                        shutil.copy2(stage3_path, final_path)
                        stage3_done = True
                    else:
                        print(
                            f"  [fail stage3] {brief_id}: NB2 returned no image "
                            f"for model swap; falling back to stage 2.",
                            flush=True,
                        )
                except Exception as e:
                    print(
                        f"  [fail stage3] {brief_id}: {e}; falling back to "
                        f"stage 2.",
                        flush=True,
                    )

            if not stage3_done and soul_id:
                # Path (b): Higgsfield soul_2.
                from generators.higgsfield_client import (
                    HiggsfieldError,
                    soul_generate_and_save,
                )
                try:
                    stage2_url = _fal_upload(stage2_path)
                    soul_generate_and_save(
                        soul_id=soul_id,
                        prompt=_build_pass3_model_swap_prompt(aspect_ratio),
                        out_path=stage3_path,
                        reference_image_url=stage2_url,
                        aspect_ratio=aspect_ratio,
                        quality="2k",
                    )
                    shutil.copy2(stage3_path, final_path)
                    stage3_done = True
                except HiggsfieldError as e:
                    if "credit" in str(e).lower():
                        print(
                            f"  [warn stage3] {brief_id}: HF credits exhausted. "
                            f"Using stage 2 output as final.",
                            flush=True,
                        )
                    else:
                        print(f"  [fail stage3] {brief_id}: {e}", flush=True)

            if not stage3_done:
                # Path (c): stage 2 is the final.
                if final_pass_soul and not model_descriptor:
                    print(
                        f"  [info stage3] {brief_id} — persona has no Soul "
                        f"Character; using stage 2 output as final.",
                        flush=True,
                    )
                shutil.copy2(stage2_path, final_path)

            saved_paths.append(final_path)

            # Campaign-name sidecar.
            campaign_name = brief_data.get("campaign_name") or ""
            if campaign_name:
                sidecar = final_path.with_name(final_path.stem + "_campaign.txt")
                sidecar.write_text(campaign_name + "\n", encoding="utf-8")

    return saved_paths


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


def _find_latest_scene_for_brief(images_dir: Path, brief_id: str) -> Path | None:
    """Find the latest TEXT-FREE scene image for a brief.

    Higgs Field iterative refinement should use the no-text scene as its
    reference, not the PIL-overlaid final image — otherwise the rendered
    text becomes a stylistic influence on the next pass and leaks into the
    soul_2 output. Scene files are named `<brief_id>[_v<N>]_scene.png`
    (produced by the Phase 2 HF path).

    Fallback: if no `_scene.png` exists (e.g. the brief was originally
    generated with NB2), return the latest regular image. The caller can
    still iterate, but soul_2 will see the rendered text in the reference
    and may try to imitate it.
    """
    if not images_dir.exists():
        return None
    scene_candidates = sorted(images_dir.glob(f"{brief_id}*_scene.png"))
    if scene_candidates:
        # Prefer highest version. Stems look like:
        #   <brief_id>_scene.png            (v1, original)
        #   <brief_id>_v2_scene.png
        #   <brief_id>_v3_scene.png
        def _version_key(p: Path) -> tuple[int, str]:
            m = re.search(r"_v(\d+)_scene", p.stem)
            return (int(m.group(1)) if m else 1, p.name)
        return sorted(scene_candidates, key=_version_key)[-1]
    # No scene file — fall back to the regular latest-image picker.
    return _find_latest_image_for_brief(images_dir, brief_id)


def _build_hf_refine_prompt(
    brief_data: dict,
    feedback: str,
) -> str:
    """Build a soul_2 refinement prompt that combines scene context + feedback.

    soul_2 with `reference_image_url` performs guided image-to-image
    generation. The reference supplies composition, lighting, framing,
    and identity; the prompt steers what should change.

    We keep the prompt short and instruction-oriented (Claude rewriting
    isn't necessary — soul_2 with a reference is much more directive than
    NB2 text-to-image). Format:

      REFINEMENT: <user feedback>

      SCENE CONTEXT: <visual_format line from the brief, for grounding>

      <text-free trailer same as Phase 2 generate path>

    The text-free trailer is critical — without it soul_2 will try to
    render the brief's hook text inline (and produce gibberish letterforms).
    PIL re-composites the text in the next pass.
    """
    feedback = feedback.strip()
    visual_format = (brief_data.get("visual_format") or "").strip()
    persona = (brief_data.get("persona") or "").strip()

    lines: list[str] = []
    lines.append(f"REFINEMENT: {feedback}")
    lines.append("")
    if visual_format:
        lines.append(f"SCENE CONTEXT: {visual_format}")
    if persona:
        lines.append(f"SUBJECT: {persona} (identity locked via Soul Character).")
    lines.append("")
    lines.append(
        "Preserve everything from the reference image except what the "
        "REFINEMENT directive changes — same person, same overall composition, "
        "same lighting register, same wardrobe/setting unless the refinement "
        "explicitly modifies them. Photoreal, phone-camera aesthetic, no "
        "studio lighting, no AI-look."
    )
    lines.append("")
    lines.append(
        "TEXT-FREE OUTPUT: Render ONLY the scene — subject, environment, "
        "lighting, product. The lower third of the frame should be empty, "
        "uncluttered warm cream space ready for a separate text overlay. "
        "DO NOT render any letters, words, quotation marks, captions, "
        "headlines, logos, brand wordmarks, CTAs, badges, ratings, or "
        "review text anywhere in the image. The output is a photograph "
        "only; text is composited in a downstream pass."
    )
    lines.append("")
    lines.append(
        "Negative prompt: any text, any letters, any words, any captions, "
        "any quotation marks, any logos, any badges, any wordmarks, any "
        "Trustpilot, any star rating, any number ratings, any overlay text."
    )
    return "\n".join(lines)


def refine_image_higgsfield(
    *,
    remix_dir: str | Path,
    brief_id: str,
    feedback: str,
    num_images: int = 1,
    aspect_ratio: str = "1:1",
    base_image: str | Path | None = None,
) -> list[Path]:
    """Higgs Field iterative refinement: soul_2 + previous scene as reference.

    Mirrors the user's manual Higgs Field workflow (generate → use that
    image as reference → generate next → iterate). The persona's soul_id
    locks identity across passes; the previous image steers composition,
    framing, lighting; the feedback prompt drives what changes.

    Pipeline:
      1. Load brief, look up the persona's soul_id (must be 'ready').
      2. Pick the latest scene image for the brief (prefers `_scene.png`).
      3. Upload that scene via fal.ai → public URL HF can fetch.
      4. Build a refinement prompt (scene context + feedback + text-free trailer).
      5. Call soul_2 with soul_id + reference_image_url + new prompt.
      6. Save the new scene as `<brief_id>_v<N>_scene.png`.
      7. Run PIL overlay (same hook + CTA from the brief) → `<brief_id>_v<N>.png`.
      8. Append to refinement_log.yaml.

    Credit-related HiggsfieldError exceptions bubble up so the outer
    `refine_image()` dispatcher can swap engines for the run.

    Returns the list of saved final-image paths (with text overlay)."""
    from generators.fal_client import upload_image
    from generators.higgsfield_client import (
        HiggsfieldError,
        soul_generate_and_save,
    )
    from generators.text_overlay import SECONDKIND_PRESET, render_ad_overlay

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

    soul_id = _get_soul_id_for_brief(brief)
    if not soul_id:
        raise ValueError(
            f"No 'ready' Soul Character for persona "
            f"'{brief.get('persona', '?')}'. Train one first or use "
            f"--engine nb2 for refinement."
        )

    images_dir = remix_path / "images"
    if base_image is not None:
        candidate = Path(base_image)
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
        previous_image = _find_latest_scene_for_brief(images_dir, brief_id)
        if previous_image is None:
            raise FileNotFoundError(
                f"No previous output image found for brief '{brief_id}' in "
                f"{images_dir}. Generate the base image first via "
                f"`adc remix-images --engine higgsfield-soul`."
            )

    # Upload the previous scene to fal.ai so HF can fetch it. fal.ai's CDN
    # returns a public HTTPS URL; HF accepts any HTTPS image URL via its
    # `medias[{value, role: image}]` parameter.
    previous_image_url = upload_image(previous_image)

    refine_prompt = _build_hf_refine_prompt(brief, feedback.strip())
    version = _next_refinement_version(images_dir, brief_id)
    images_dir.mkdir(parents=True, exist_ok=True)

    # Pull the brief's hook + CTA for the PIL overlay step (same convention
    # as the Phase 2 generate path).
    hero_quote = (brief.get("hook") or "").strip()
    cta_text = (brief.get("cta") or "Learn more").strip().rstrip("→").strip()

    saved_paths: list[Path] = []
    for i in range(num_images):
        if num_images == 1:
            scene_filename = f"{brief_id}_v{version}_scene.png"
            final_filename = f"{brief_id}_v{version}.png"
        else:
            letter = chr(ord("a") + i)  # a, b, c, ...
            scene_filename = f"{brief_id}_v{version}_{letter}_scene.png"
            final_filename = f"{brief_id}_v{version}_{letter}.png"
        scene_path = images_dir / scene_filename
        final_path = images_dir / final_filename

        try:
            soul_generate_and_save(
                soul_id=soul_id,
                prompt=refine_prompt,
                out_path=scene_path,
                reference_image_url=previous_image_url,
                aspect_ratio=aspect_ratio,
                quality="2k",
            )
        except HiggsfieldError as e:
            # Bubble credit errors so the outer dispatcher can fall back.
            if "credit" in str(e).lower():
                raise
            print(f"  [fail soul-refine] {brief_id} v{version}: {e}")
            continue

        try:
            render_ad_overlay(
                base_image=scene_path,
                hero_quote=hero_quote,
                cta_text=cta_text,
                out_path=final_path,
                preset=SECONDKIND_PRESET,
            )
        except Exception as e:
            print(f"  [fail overlay] {brief_id} v{version}: {e}")
            continue
        saved_paths.append(final_path)

        # Campaign-name sidecar (same convention as NB2 refine path).
        campaign_name = brief.get("campaign_name") or ""
        if campaign_name:
            sidecar = final_path.with_name(final_path.stem + "_campaign.txt")
            sidecar.write_text(campaign_name + "\n", encoding="utf-8")

    # Refinement notes file alongside the prompts.
    refined_prompt_path = remix_path / "prompts" / f"{brief_id}_v{version}.txt"
    refined_prompt_path.write_text(
        _format_refinement_notes(brief, feedback, version, previous_image)
        + "\n\n"
        + refine_prompt
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


def refine_image(
    *,
    remix_dir: str | Path,
    brief_id: str,
    feedback: str,
    num_images: int = 1,
    thinking_level: str = "disabled",
    aspect_ratio: str = "1:1",
    base_image: str | Path | None = None,
    engine: str = "nb2",
    fallback_engine: str | None = None,
) -> list[Path]:
    """Refine an existing remix image with user feedback.

    Engines:
      - "nb2"              fal.ai NB2 edit endpoint, Claude rewrites the
                            prompt incorporating feedback; uses
                            [product_image, previous_output] as references.
      - "higgsfield-soul"  Higgs Field soul_2 + PIL overlay. Uses the
                            persona's trained Soul Character (identity lock)
                            + the previous scene image as composition
                            reference. Mirrors the user's manual HF
                            iterative workflow.

    `fallback_engine`: if HF fails because of missing credits, retry the
    run with this engine. Set to "nb2" from the dashboard for graceful
    degradation.

    Pipeline (NB2):
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
    # ─── Higgs Field iterative refine path ───
    if engine == "higgsfield-soul":
        try:
            return refine_image_higgsfield(
                remix_dir=remix_dir,
                brief_id=brief_id,
                feedback=feedback,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
                base_image=base_image,
            )
        except Exception as e:
            if fallback_engine and "credit" in str(e).lower():
                print(
                    f"  [fallback] Higgs Field unavailable ({e}). "
                    f"Falling back to engine={fallback_engine}."
                )
                return refine_image(
                    remix_dir=remix_dir,
                    brief_id=brief_id,
                    feedback=feedback,
                    num_images=num_images,
                    thinking_level=thinking_level,
                    aspect_ratio=aspect_ratio,
                    base_image=base_image,
                    engine=fallback_engine,
                    fallback_engine=None,
                )
            raise

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
