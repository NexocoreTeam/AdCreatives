"""Generate canonical headshot portraits for each persona.

The idea: stop relying on text-only persona descriptions to coax NB2
into rendering a realistic face. Instead, generate ONE canonical
headshot per persona on a neutral background, save it to disk, and
pass it as an identity reference whenever the remix pipeline needs that
persona in a scene.

Pipeline:
  1. extract_visual_cues  -> LLM call that distills the CustomerAvatar
                              YAML into structured visual fields.
  2. build_portrait_prompt -> assembles a Nano Banana 2 text-to-image
                              prompt using the realistic-people skill
                              + the extracted visual cues.
  3. generate_portraits    -> fires NB2 N times, saves candidate PNGs
                              under clients/<slug>/avatars/<persona>/.

Cost: ~$0.25 per persona for 3 candidates (1 Sonnet call + 3 NB2 calls).
One-time per persona — the chosen canonical photo is reused for every
ad targeting that persona.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from generators.fal_client import download_image, generate_text_only
from models.avatar import CustomerAvatar
from models.brand import Brand
from strategy.llm import claude_complete

CLIENTS_DIR = Path("clients")


# ─── Visual cue extraction ──────────────────────────────────────────────────


VISUAL_CUES_SYSTEM = """You translate a CustomerAvatar's strategic profile
into structured visual cues that a photographer would use to cast a
model for an ad. The output drives a Nano Banana 2 headshot generator.

Rules:
- Be specific. "40s" beats "middle-aged". "Fitted dark charcoal crewneck"
  beats "casual clothing". "Tracker watch on left wrist" beats "wearable
  technology".
- Default to broad ethnicity_register ("any" or "diverse") unless the
  avatar's demographic explicitly names an ethnic group. We're aiming for
  realistic ad models, not stereotypes.
- The persona's NAME often disambiguates gender (e.g. "Brandon" → male,
  "Paula" → female) even when the demographic field hedges with "man or
  woman". Use the name unless the demographic explicitly overrides.
- Wardrobe should match the persona's lifestyle, NOT the brand. A
  biohacker wears technical-casual, not athleisure. A clinical
  practitioner wears understated professional. A new mom wears
  comfortable lived-in pieces.
- Expression and body_language should match the persona's emotional
  state (frustrated probiotic-burned buyer vs. authority-confident
  practitioner). Mid-thought micro-expressions beat held smiles.

Output STRICT JSON, no markdown fences, no commentary."""


VISUAL_CUE_FIELDS = [
    "age",
    "gender",
    "ethnicity_register",
    "build",
    "skin_register",
    "hair",
    "wardrobe",
    "accessories",
    "expression",
    "body_language",
    "register",
]


@dataclass
class VisualCues:
    """Structured visual fields extracted from a CustomerAvatar."""

    age: str
    gender: str
    ethnicity_register: str
    build: str
    skin_register: str
    hair: str
    wardrobe: str
    accessories: str
    expression: str
    body_language: str
    register: str

    @classmethod
    def from_dict(cls, d: dict) -> "VisualCues":
        return cls(**{k: str(d.get(k, "") or "") for k in VISUAL_CUE_FIELDS})

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in VISUAL_CUE_FIELDS}


def extract_visual_cues(avatar: CustomerAvatar, brand: Brand) -> VisualCues:
    """LLM-driven translation from CustomerAvatar → VisualCues.

    Reads the avatar's name, demographic, psychographic, and language
    patterns. Outputs structured cues consumed by `build_portrait_prompt`.
    Idempotent given identical inputs (the LLM produces stable output
    when re-run on the same persona within a session).
    """
    pains = []
    for p in (avatar.pain_points or [])[:3]:
        if hasattr(p, "pain"):
            pains.append(p.pain)
    pains_str = " / ".join(pains) if pains else "—"

    lang = ", ".join((avatar.language_patterns or [])[:5]) or "—"

    prompt = f"""Translate this CustomerAvatar into structured visual cues for
a headshot photographer.

PERSONA NAME: {avatar.name}
DEMOGRAPHIC: {avatar.demographic}
PSYCHOGRAPHIC: {avatar.psychographic}
TOP PAINS: {pains_str}
LANGUAGE PATTERNS: {lang}
BRAND CONTEXT: {brand.name} — {brand.tone or 'no tone specified'}

Output a JSON object with exactly these keys (all strings, no markdown):

{{
  "age": "short age descriptor like 'early-to-mid 40s'",
  "gender": "male | female | non-binary",
  "ethnicity_register": "any | diverse | <specific cue if avatar names one>",
  "build": "short build descriptor — 'lean athletic', 'soft natural', etc.",
  "skin_register": "skin texture cues — 'natural pores, slight tan, fine laugh lines'",
  "hair": "specific hair description — length, style, color",
  "wardrobe": "specific clothing matching lifestyle — 'fitted dark charcoal crewneck'",
  "accessories": "minimal — what they'd actually wear, e.g. 'Whoop band, no jewelry'",
  "expression": "mid-action micro-expression — 'calm, slightly knowing, mid-thought half-smile'",
  "body_language": "posture and energy — 'weight settled, shoulders relaxed, hands purposeful'",
  "register": "overall energy — 'intellectual peer authority', 'frustrated researcher', etc."
}}"""

    raw = claude_complete(prompt, system=VISUAL_CUES_SYSTEM, max_tokens=1000)
    raw = raw.strip()
    # Strip optional markdown fences in case the LLM ignored the rule.
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    try:
        data = json.loads(raw.strip())
    except json.JSONDecodeError as e:
        # Soft-fail: return generic cues so the downstream caller still
        # gets a portrait, just less persona-tailored. Logged so we can
        # spot pattern issues if this keeps happening.
        raise ValueError(f"Could not parse visual cues JSON: {e}\nRaw: {raw[:400]}") from e

    return VisualCues.from_dict(data)


# ─── Prompt construction ─────────────────────────────────────────────────────


def build_portrait_prompt(cues: VisualCues) -> str:
    """Assemble the Nano Banana 2 text-to-image headshot prompt.

    Uses the realistic-people skill's verbatim camera, film stock, and
    skin-anatomy phrases that the prompt-engine rules require. Output
    is a single ready-to-send prompt string. No text overlay, no
    product, no scene context — just the headshot on a neutral
    studio background.
    """
    return (
        "Headshot portrait, 1:1 aspect ratio, chest-up framing on a "
        "light-grey seamless studio background. No clutter, no props, "
        "no text overlay, no logos.\n\n"
        "SUBJECT:\n"
        f"{cues.build} {cues.gender}, {cues.age}. Ethnicity register: "
        f"{cues.ethnicity_register}. {cues.hair}. "
        f"{cues.skin_register} — visible pores, natural skin texture "
        "variation across the face, subtle under-eye detail. "
        "Hyper-detailed skin — no airbrushing, no plastic smoothness, "
        "slight natural asymmetry. Natural eye catchlights, soft "
        "realistic gaze slightly off-axis, no doll-like glassy eyes.\n\n"
        f"WARDROBE: {cues.wardrobe}. {cues.accessories}. Realistic "
        "fabric folds and shadows on the garment, natural drape, soft "
        "texture detail.\n\n"
        f"EXPRESSION & BODY LANGUAGE: {cues.expression}. "
        f"{cues.body_language}. Framed chest-up, shoulders relaxed. "
        f"Overall register: {cues.register}.\n\n"
        "CAMERA:\n"
        "Shot on Hasselblad X2D with 85mm f/2.0, shallow DOF, tack-sharp "
        "eyes, creamy bokeh, Kodak Portra 400 emulation, natural warm "
        "skin tones, soft pastel palette.\n\n"
        "LIGHTING:\n"
        "Single soft window light from upper-left at approximately 45°, "
        "warm 4500K color temperature, gentle shadow falloff across "
        "face, no studio fill, no ring-light catchlights, no even "
        "all-around illumination.\n\n"
        "REGISTER:\n"
        "Documentary editorial portrait — candid moment, real-life "
        "imperfections preserved, no Instagram filter look, natural "
        "color grading. Reads as a real photograph of a real person, "
        "not an AI render.\n\n"
        "Negative prompt: plastic skin, smoothed airbrushed skin, waxy "
        "face, stock-photo energy, uncanny valley, doll-like glassy "
        "eyes, AI-generated face artifacts, oversaturated colors, "
        "Instagram filter look, posed/staged feel, celebrity look-"
        "alike, gym-model proportions, suit or formal wear (unless "
        "specified), text or watermark, hands visible (chest-up "
        "framing).\n\n"
        "1:1 aspect ratio."
    )


# ─── Generation orchestration ───────────────────────────────────────────────


def _slug_to_avatar_dir(client_slug: str, avatar_slug: str) -> Path:
    return CLIENTS_DIR / client_slug / "avatars" / avatar_slug


def generate_portraits(
    avatar: CustomerAvatar,
    brand: Brand,
    *,
    client_slug: str,
    avatar_slug: str,
    num_candidates: int = 3,
    force: bool = False,
) -> dict:
    """Generate N candidate headshots for one persona and save them to disk.

    Returns a dict with:
      - cues:           the VisualCues that drove the prompt (for debugging)
      - prompt:         the NB2 prompt string used
      - candidate_paths: list of Paths to the saved candidate images

    If `force=False` and an existing candidate directory with files
    already exists, raises FileExistsError instead of overwriting.
    """
    candidates_dir = _slug_to_avatar_dir(client_slug, avatar_slug)
    if candidates_dir.exists() and any(candidates_dir.glob("candidate_*.png")) and not force:
        raise FileExistsError(
            f"Candidates already exist at {candidates_dir}. "
            f"Pass force=True to regenerate."
        )

    cues = extract_visual_cues(avatar, brand)
    prompt = build_portrait_prompt(cues)

    results = generate_text_only(
        prompt=prompt,
        aspect_ratio="1:1",
        resolution="1K",
        num_images=num_candidates,
    )

    candidates_dir.mkdir(parents=True, exist_ok=True)
    # Also save the cues + prompt as a sidecar for inspection/debugging.
    (candidates_dir / "_cues.json").write_text(
        json.dumps(cues.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (candidates_dir / "_prompt.txt").write_text(prompt, encoding="utf-8")

    candidate_paths: list[Path] = []
    for i, result in enumerate(results, 1):
        out_path = candidates_dir / f"candidate_{i}.png"
        download_image(result.image_url, out_path)
        candidate_paths.append(out_path)

    return {
        "cues": cues,
        "prompt": prompt,
        "candidate_paths": candidate_paths,
    }


def promote_candidate_to_canonical(
    client_slug: str,
    avatar_slug: str,
    candidate_index: int,
) -> Path:
    """Copy the chosen candidate up to `<avatar_slug>.png` (canonical).

    Used after the user picks their favorite from the candidate set.
    The candidates folder is left in place so the user can swap later.
    """
    import shutil

    candidates_dir = _slug_to_avatar_dir(client_slug, avatar_slug)
    src = candidates_dir / f"candidate_{candidate_index}.png"
    if not src.exists():
        raise FileNotFoundError(f"Candidate not found: {src}")

    canonical = CLIENTS_DIR / client_slug / "avatars" / f"{avatar_slug}.png"
    shutil.copy2(src, canonical)
    return canonical
