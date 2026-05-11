"""Psychology profiling — diagnose buyer heuristics, valence/intensity, pairings.

Uses the psychology-profiling skill (prompts/skills/psychology-profiling.md) as
system context. Reads avatar + brand + (optional) VOC, produces a
PsychologyProfile written back into the avatar yaml in place.

Diagnostic only — does not generate ad concepts. Output feeds the angle
multiplier and brief generator downstream.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar, PsychologyProfile
from models.loader import load_brand
from models.skills import load_skill
from strategy.llm import claude_complete

CLIENTS_DIR = Path("clients")


PROFILER_SYSTEM = """You are an expert in buyer psychology. Your job is to diagnose
how a specific avatar makes purchase decisions so downstream strategy and creative
generation can target the right mental levers.

You produce ONE psychology_profile yaml block. You do NOT generate ad concepts.
You diagnose. Concept generation happens later, using your output as input.

Hard rules — schema enforced downstream, profiles that violate these are rejected:

- Every dominant_heuristic and weak_heuristic must use one of the 9 valid names
  (snake_case): scarcity, social_proof, authority_bias, effect_heuristic,
  processing_fluency, temporal_discounting, salience_bias, goal_gradient,
  framing_effect.
- Every recommended/avoid pairing must use one of the 14 valid pairing names
  (snake_case from the table in the skill).
- Every dominant_heuristic must have at least one item in `evidence` —
  a verbatim quote or specific field reference like `trigger_events[2]`.
- At most 3 dominant_heuristics may be at confidence: high. Force a ranking.
- At most 6 entries in recommended_prompt_pairings. Filter to the best fits.
- valence is positive | negative; intensity is high | low; confidence is
  high | medium | low.

Follow the skill below.

--- PSYCHOLOGY PROFILING SKILL ---

""" + load_skill("psychology-profiling") + """

---

Output VALID JSON ONLY — no prose, no markdown fences, no YAML.
The top-level key must be `psychology_profile`. Use JSON string escaping
(double-quoted strings, escape inner quotes with backslash). Do not include
trailing commas. Example shape:

{
  "psychology_profile": {
    "dominant_heuristics": [
      {
        "heuristic": "social_proof",
        "confidence": "high",
        "why": "...",
        "evidence": ["..."],
        "ad_implications": "..."
      }
    ],
    "weak_heuristics": [...],
    "emotional_position": {"primary": {...}, "secondary": {...}},
    "recommended_prompt_pairings": [...],
    "avoid_pairings": [...]
  }
}"""


PROFILER_PROMPT_TEMPLATE = """Diagnose the psychology profile for this avatar.

Use the avatar fields, brand context, and (if provided) VOC corpus as the
ONLY sources of evidence. Do not invent context. If a field is empty or
contradictory, prefer the most evidence-backed reading.

# AVATAR ({avatar_name})

```yaml
{avatar_yaml}
```

# BRAND CONTEXT ({brand_name})

```yaml
{brand_yaml}
```

# VOC CORPUS

{voc_block}

---

Produce the psychology_profile yaml per the skill spec. Cite evidence for every
dominant_heuristic and weak_heuristic. Pick exactly 3–6 recommended pairings and
1–3 avoid pairings. Place the avatar on the primary + secondary valence/intensity
quadrants with evidence-grounded rationale.

Output JSON only — no prose, no markdown fences:"""


def parse_profile_yaml(text: str) -> PsychologyProfile:
    """Parse LLM output into a validated PsychologyProfile.

    Tries JSON first (preferred — strict escaping, no ambiguity), falls back
    to YAML for tolerance of older test fixtures and any future format drift.
    Tolerates wrapped (`psychology_profile:` top-level key) and unwrapped
    output, strips markdown code fences, and raises ValidationError if the
    structure violates the schema (unknown heuristic, missing evidence, >3
    high-confidence entries, etc.).
    """
    text = text.strip()
    # Strip ```json/```yaml/``` ... ``` fences if the LLM ignored instructions
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0].rstrip()

    if not text:
        raise ValueError("LLM returned empty response for psychology profile")

    data = None
    parse_errors: list[str] = []

    # JSON first — preferred output format
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        parse_errors.append(f"json: {e}")

    # YAML fallback for backwards compatibility
    if data is None:
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            parse_errors.append(f"yaml: {e}")

    if data is None:
        raise ValueError(
            "Could not parse psychology profile response as JSON or YAML. "
            f"Errors: {'; '.join(parse_errors)}. "
            f"First 500 chars of response: {text[:500]!r}"
        )

    if isinstance(data, dict) and "psychology_profile" in data:
        data = data["psychology_profile"]
    return PsychologyProfile(**data)


def write_profile_into_avatar(
    avatar_path: Path,
    profile: PsychologyProfile,
    backup: bool = True,
) -> Path:
    """Write the psychology_profile block into an existing avatar yaml in place.

    Preserves every other top-level field in the file. Creates a `.yaml.bak`
    sibling before writing when `backup=True`.
    """
    if not avatar_path.exists():
        raise FileNotFoundError(f"Avatar not found: {avatar_path}")

    existing = yaml.safe_load(avatar_path.read_text(encoding="utf-8")) or {}
    if not isinstance(existing, dict):
        raise ValueError(f"Avatar yaml at {avatar_path} is not a mapping")

    if backup:
        shutil.copy2(avatar_path, avatar_path.with_suffix(".yaml.bak"))

    existing["psychology_profile"] = profile.model_dump(mode="json")

    with open(avatar_path, "w", encoding="utf-8") as f:
        yaml.dump(
            existing,
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return avatar_path


def profile_avatar_file(
    client_slug: str,
    avatar_path: Path,
    backup: bool = True,
) -> PsychologyProfile:
    """Run the LLM diagnosis on one avatar file and write the profile back.

    Reads the avatar yaml, brand context, and (if present) extracted VOC, then
    calls Claude with the psychology-profiling skill as system context, parses
    the response, validates it against the schema, and writes the profile into
    the avatar yaml under `psychology_profile`.
    """
    if not avatar_path.exists():
        raise FileNotFoundError(f"Avatar not found: {avatar_path}")

    avatar_data = yaml.safe_load(avatar_path.read_text(encoding="utf-8"))
    if not isinstance(avatar_data, dict):
        raise ValueError(f"Avatar yaml at {avatar_path} is not a mapping")

    # Validate avatar before profiling — we won't profile a broken avatar.
    avatar = CustomerAvatar(**avatar_data)
    if not avatar.pain_points and not avatar.trigger_events:
        raise ValueError(
            f"Avatar at {avatar_path} has no pain_points or trigger_events. "
            "Run `adc research` or `adc mine-voc` first — psychology profiling "
            "requires evidence to diagnose against."
        )

    brand = load_brand(client_slug)
    brand_yaml = yaml.safe_dump(
        brand.model_dump(mode="json"),
        sort_keys=False,
        allow_unicode=True,
    )

    voc_block = _load_voc_block(client_slug)

    prompt = PROFILER_PROMPT_TEMPLATE.format(
        avatar_name=avatar.name or avatar_path.stem,
        avatar_yaml=yaml.safe_dump(avatar_data, sort_keys=False, allow_unicode=True),
        brand_name=brand.name,
        brand_yaml=brand_yaml,
        voc_block=voc_block,
    )

    response = claude_complete(prompt, system=PROFILER_SYSTEM, max_tokens=4096)
    profile = parse_profile_yaml(response)
    write_profile_into_avatar(avatar_path, profile, backup=backup)
    return profile


def profile_all_avatars(
    client_slug: str,
    backup: bool = True,
) -> dict[str, PsychologyProfile]:
    """Profile every avatar under clients/<slug>/avatars/.

    Falls back to the legacy single `avatar.yaml` if no `avatars/` directory
    exists. Skips files prefixed with `_` (e.g. `_index.yaml`).
    """
    avatars_dir = CLIENTS_DIR / client_slug / "avatars"
    if avatars_dir.exists():
        results: dict[str, PsychologyProfile] = {}
        for path in sorted(avatars_dir.glob("*.yaml")):
            if path.name.startswith("_") or path.name.endswith(".bak"):
                continue
            results[path.stem] = profile_avatar_file(client_slug, path, backup=backup)
        if not results:
            raise FileNotFoundError(
                f"No avatar yaml files found in {avatars_dir}"
            )
        return results

    # Legacy fallback — single avatar.yaml at client root
    single = CLIENTS_DIR / client_slug / "avatar.yaml"
    if single.exists():
        return {"avatar": profile_avatar_file(client_slug, single, backup=backup)}

    raise FileNotFoundError(
        f"No avatars found for '{client_slug}'. "
        f"Expected {avatars_dir}/*.yaml or {single}."
    )


def _load_voc_block(client_slug: str) -> str:
    """Format the extracted VOC corpus as a yaml block for the prompt.

    Returns a friendly placeholder string if no VOC has been mined yet — the
    profiler will work from the avatar alone but with lower-confidence output.
    """
    voc_path = CLIENTS_DIR / client_slug / "voc" / "extracted_pains.yaml"
    if not voc_path.exists():
        return "(No VOC corpus available — diagnose from avatar + brand alone.)"

    voc_data = yaml.safe_load(voc_path.read_text(encoding="utf-8")) or {}
    # Surface only the high-signal sections; pass-through can blow the token budget.
    relevant = {
        key: voc_data.get(key, [])
        for key in (
            "pain_points",
            "desires",
            "objections",
            "trigger_events",
            "trigger_moments",
            "transformations",
            "language_patterns",
            "money_quotes",
        )
        if voc_data.get(key)
    }
    body = yaml.safe_dump(relevant, sort_keys=False, allow_unicode=True)
    return f"```yaml\n{body}\n```"
