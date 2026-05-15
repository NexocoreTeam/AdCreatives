"""Stage 2 — multi-persona expansion.

Reads the brand-context.md (which already identifies audience tiers)
and generates a full structured avatar YAML per persona under
clients/<slug>/avatars/. This lets later stages (strategy matrix,
brief generator) target specific personas rather than collapsing
everything into a single avatar.

System context layers:
- motion/creative-strategy-engine — pain × persona structure
- coreyhaines/customer-research — JTBD + confidence scoring
- coreyhaines/product-marketing-context — persona-as-positioning
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar, Desire, PainPoint
from models.brand import Brand
from models.skills import load_skill
from strategy.competitive_context import (
    format_competitive_block,
    format_voc_block,
    load_competitive_gaps,
    load_voc_pains,
)
from strategy.llm import claude_complete


@dataclass
class PersonasResult:
    personas: list[dict]
    index: dict


PERSONAS_SYSTEM = """You are a creative strategist building a structured
persona set for an e-commerce DTC brand. The brand already has a brand-context
document that identifies multiple audience tiers — your job is to expand each
into a complete, structured persona that downstream tools (strategy matrix,
brief generator) can target individually.

Apply three layered skills:
- motion/creative-strategy-engine — persona × pain mapping
- coreyhaines/customer-research — JTBD framework + confidence scoring
- coreyhaines/product-marketing-context — persona as positioning input

--- CREATIVE STRATEGY ENGINE ---

""" + load_skill("motion/creative-strategy-engine") + """

--- CUSTOMER RESEARCH ---

""" + load_skill("customer-research") + """

--- PRODUCT MARKETING CONTEXT ---

""" + load_skill("product-marketing-context") + """

---

Output rules:
- Each persona must be genuinely distinct — different pains, triggers, language,
  awareness level. If two personas would generate the same ad, they're the same
  persona.
- Use brand-specific language and product knowledge in every field.
- Pain points and desires must reference real things the brand observed,
  not generic strategist phrasing.
- Awareness level may differ by persona (e.g., primary may be solution_aware
  while a secondary persona is problem_aware).
- Output YAML only, no markdown fences.

CATEGORY AWARENESS CALIBRATION (read before assigning awareness_level):

Calibrate awareness levels to the brand's ACTUAL market position, not the brand
team's internal vocabulary. If the brand introduces a genuinely new or
emerging category — novel mechanism, no established consumer search demand,
the audience has never seen the category named on social media or in
podcasts — personas must skew **problem_aware**, NOT solution_aware.

`problem_aware` is the correct default when:
- The audience has the pain and has tried the legacy category (e.g., probiotics,
  greens powders, retinol) but those approaches failed or underwhelmed.
- The brand's NEW category (e.g., postbiotics) has no consumer recognition yet.
- Personas would not type the brand's category name into a search bar.
- The honest persona thought is "I'm tired of bloating and nothing has worked,"
  NOT "I'm comparing postbiotic brands."

`solution_aware` is reserved for established categories where consumers
actively compare brands within that category (probiotics, kombucha, electrolyte
powders, greens powders, multivitamins). If you assign solution_aware to a
persona for a brand-new category, you are FORCING a fiction that erases the
brand's positioning challenge and produces personas that don't exist in the
real market.

When in doubt, default to problem_aware. Honest pain framing > sophisticated
evaluation framing for a category nobody has heard of yet."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "persona"


def build_personas(
    brand: Brand,
    brand_context_md: str,
    max_personas: int = 4,
    client_slug: str | None = None,
    competitive_gaps: dict | None = None,
    voc_pains: dict | None = None,
) -> PersonasResult:
    """Generate structured personas from a brand context document.

    Returns a list of persona dicts (each ready to be saved as a YAML
    avatar file) and an index dict that registers each persona with its
    role and slug.

    Upstream research is auto-loaded when `client_slug` is supplied (and the
    relevant files exist on disk):
      * `clients/<slug>/research/competitive-gaps.yaml` → gap map synthesis
      * `clients/<slug>/voc/extracted_pains.yaml` → VoC corpus

    When either is present, personas are differentiated by which competitor
    weakness they care about most and grounded in verbatim customer language
    from the VoC corpus rather than inferred from brand copy alone. Both
    sections silently no-op when missing — the prompt still works on brand
    context alone (the original behavior).
    """
    if not brand_context_md:
        raise ValueError(
            "No brand-context.md provided. Run `adc research` first."
        )

    # Auto-load upstream research when client_slug is supplied and the caller
    # hasn't passed values explicitly.
    if client_slug:
        if competitive_gaps is None:
            competitive_gaps = load_competitive_gaps(client_slug)
        if voc_pains is None:
            voc_pains = load_voc_pains(client_slug)

    competitive_block = format_competitive_block(competitive_gaps)
    voc_block = format_voc_block(voc_pains)

    prompt = f"""Read the brand context below and produce a structured persona set
for {brand.name}. Identify every distinct audience tier the brand context
references (primary, secondary, tertiary), and write a complete persona for each.

Up to {max_personas} personas. Skip anti-personas. Skip generic 'gift buyer'
unless the brand context explicitly emphasizes them.

BRAND CONTEXT:
{brand_context_md[:12000]}

# COMPETITIVE INTELLIGENCE

{competitive_block}

# VOICE-OF-CUSTOMER EVIDENCE

{voc_block}

---

For each persona, return YAML with this exact structure:

personas:
  - id: "primary"   # slug: primary | secondary | tertiary | quaternary
    role: "primary" # primary | secondary | tertiary
    name: "A specific persona name with a memorable hook (e.g. 'Faithful Boy Mom Brittany', 'Macro-Tracking Marcus')"
    demographic: "Multi-clause demographic description with age, gender, location, household, income"
    psychographic: "1-3 sentence psychographic — values, lifestyle, what they care about, who they aspire to be"
    awareness_level: "unaware | problem_aware | solution_aware | product_aware | most_aware"
    why_this_persona: "1-2 sentences explaining why this persona is distinct from the others and why the brand serves them well"
    distinct_jobs_to_be_done:
      - job: "Functional/emotional/social outcome they hire the brand to deliver"
        type: "functional | emotional | social"
    pain_points:
      - pain: "Specific pain — use customer language where possible"
        intensity: "high | medium | low"
        customer_language:
          - "Verbatim or close-to-verbatim quote a real customer might say"
        source: "auto_from_brand_context"
    desires:
      - desire: "Specific desire — what they ultimately want"
        customer_language:
          - "How they would phrase the desire"
    objections:
      - "Specific objection — what makes them hesitate to buy"
    trigger_events:
      - "Specific event that pushes them to actively look for a solution"
    current_solutions:
      - "What they're using or doing now instead of the brand"
    language_patterns:
      - "How they talk — formal/casual, jargon, emotional register, common phrasings"
    confidence: "high | medium | low — how confident you are this persona is real for this brand"

Quality checks before returning:
1. Each persona's pain_points must differ meaningfully from every other persona's.
2. Names must be memorable and persona-specific, not generic ('Sarah the Customer').
3. Trigger events must be specific moments, not vague life stages.
4. customer_language entries must read like things real people would say.
5. If two personas would respond to the same hook, merge them — they are one persona.
6. When VOICE-OF-CUSTOMER EVIDENCE includes verbatim quotes, every customer_language
   entry must come from (or closely paraphrase) that corpus — not invented phrasing.
   Set `source: "voc_corpus"` for those entries.
7. When COMPETITIVE INTELLIGENCE lists exploitable gaps, differentiate the personas
   by which gap most resonates with each. Reference the specific gap in
   `why_this_persona` so downstream stages know the strategic edge per persona.

Output YAML only. No markdown fences."""

    raw = claude_complete(prompt, system=PERSONAS_SYSTEM, max_tokens=10000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    parsed = yaml.safe_load(raw) or {}
    personas = parsed.get("personas", []) or []

    index = {
        "personas": [
            {
                "id": p.get("id", _slugify(p.get("name", f"persona-{i}"))),
                "name": p.get("name", ""),
                "role": p.get("role", "secondary"),
                "awareness_level": p.get("awareness_level", "problem_aware"),
                "confidence": p.get("confidence", "medium"),
            }
            for i, p in enumerate(personas)
        ]
    }
    return PersonasResult(personas=personas, index=index)


MAX_PERSONAS = 6


def build_one_persona(
    brand: Brand,
    brand_context_md: str,
    existing_avatars: list[CustomerAvatar],
    client_slug: str | None = None,
    competitive_gaps: dict | None = None,
    voc_pains: dict | None = None,
) -> dict:
    """Generate exactly ONE new persona that's distinct from the existing set.

    Same upstream-research auto-loading as `build_personas` (competitive gaps +
    VoC). Returns a single persona dict in the same shape that `build_personas`
    produces, ready to hand to `persona_to_avatar` and save under
    `clients/<slug>/avatars/`.

    The prompt includes a short summary of every existing avatar so the LLM
    cannot duplicate one of them. Raises ValueError if the LLM returns
    nothing usable.
    """
    if not brand_context_md:
        raise ValueError(
            "No brand-context.md provided. Run `adc research` first."
        )

    if client_slug:
        if competitive_gaps is None:
            competitive_gaps = load_competitive_gaps(client_slug)
        if voc_pains is None:
            voc_pains = load_voc_pains(client_slug)

    competitive_block = format_competitive_block(competitive_gaps)
    voc_block = format_voc_block(voc_pains)

    # Compact "who already exists" block — name + demographic one-liner +
    # top 2 pain points. Keeps the prompt cheap while still letting the
    # LLM see what's covered so it can stake out fresh ground.
    if existing_avatars:
        lines = ["EXISTING PERSONAS — your new one must NOT overlap with any of these:"]
        for av in existing_avatars:
            top_pains = ", ".join(
                (p.pain or "").strip() for p in (av.pain_points or [])[:2]
            )
            lines.append(f"- {av.name}: {av.demographic[:160]}")
            if top_pains:
                lines.append(f"    Top pains: {top_pains}")
        existing_block = "\n".join(lines)
    else:
        existing_block = "(no existing personas — generate the first one)"

    prompt = f"""Read the brand context below and produce ONE additional persona
for {brand.name} that fills a gap in the existing persona set. The new persona
must be genuinely distinct from each of the existing ones — different pains,
triggers, language, or awareness level. If the only way you can differentiate
the new persona is by changing demographics while keeping the same pain set,
do not return that persona; it's not distinct enough.

{existing_block}

BRAND CONTEXT:
{brand_context_md[:12000]}

# COMPETITIVE INTELLIGENCE

{competitive_block}

# VOICE-OF-CUSTOMER EVIDENCE

{voc_block}

---

Return YAML with exactly ONE persona under a `personas:` list, in this shape:

personas:
  - id: "slug-style-id"   # short slug derived from the persona name
    role: "primary | secondary | tertiary"
    name: "A specific persona name with a memorable hook"
    demographic: "Multi-clause demographic description"
    psychographic: "1-3 sentence psychographic"
    awareness_level: "unaware | problem_aware | solution_aware | product_aware | most_aware"
    why_this_persona: "1-2 sentences explaining the gap this persona fills relative to the existing set"
    distinct_jobs_to_be_done:
      - job: "Functional/emotional/social outcome"
        type: "functional | emotional | social"
    pain_points:
      - pain: "Specific pain — use customer language where possible"
        intensity: "high | medium | low"
        customer_language:
          - "Verbatim or close-to-verbatim quote"
        source: "auto_from_brand_context"
    desires:
      - desire: "Specific desire"
        customer_language:
          - "How they would phrase the desire"
    objections:
      - "Specific objection"
    trigger_events:
      - "Specific event that pushes them to look for a solution"
    current_solutions:
      - "What they're using now instead of the brand"
    language_patterns:
      - "How they talk — register, jargon, common phrasings"
    confidence: "high | medium | low"

Output YAML only. No markdown fences."""

    raw = claude_complete(prompt, system=PERSONAS_SYSTEM, max_tokens=4000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    parsed = yaml.safe_load(raw) or {}
    personas = parsed.get("personas", []) or []
    if not personas:
        raise ValueError("LLM returned no personas — check brand-context.md content.")
    persona = personas[0]
    if "id" not in persona or not persona["id"]:
        persona["id"] = _slugify(persona.get("name", "persona"))
    return persona


def persona_to_avatar(persona: dict) -> CustomerAvatar:
    """Convert a persona dict from the LLM output into a CustomerAvatar."""
    pain_points = []
    for p in persona.get("pain_points", []) or []:
        if isinstance(p, dict):
            pain_points.append(
                PainPoint(
                    pain=p.get("pain", ""),
                    intensity=p.get("intensity", "medium"),
                    customer_language=p.get("customer_language", []) or [],
                    source=p.get("source", "personas_stage"),
                )
            )

    desires = []
    for d in persona.get("desires", []) or []:
        if isinstance(d, dict):
            desires.append(
                Desire(
                    desire=d.get("desire", ""),
                    customer_language=d.get("customer_language", []) or [],
                )
            )

    return CustomerAvatar(
        name=persona.get("name", ""),
        demographic=persona.get("demographic", ""),
        psychographic=persona.get("psychographic", "") or "",
        pain_points=pain_points,
        desires=desires,
        objections=persona.get("objections", []) or [],
        current_solutions=persona.get("current_solutions", []) or [],
        trigger_events=persona.get("trigger_events", []) or [],
        awareness_level=persona.get("awareness_level", "problem_aware"),
        language_patterns=persona.get("language_patterns", []) or [],
    )


def _load_index(client_slug: str) -> dict:
    """Load `clients/<slug>/avatars/_index.yaml`, or return an empty stub."""
    path = Path("clients") / client_slug / "avatars" / "_index.yaml"
    if not path.exists():
        return {"personas": []}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"personas": []}
    if "personas" not in data or not isinstance(data["personas"], list):
        data["personas"] = []
    return data


def _write_index(client_slug: str, index: dict) -> Path:
    path = Path("clients") / client_slug / "avatars" / "_index.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(index, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path


def add_persona(client_slug: str, persona: dict) -> tuple[Path, Path]:
    """Save ONE new persona avatar YAML and append it to `_index.yaml`.

    If the persona's id slug collides with an existing avatar file, a
    numeric suffix is appended (`-2`, `-3`, …) so we never silently
    overwrite. Returns (avatar_path, index_path).
    """
    avatars_dir = Path("clients") / client_slug / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)

    base_slug = persona.get("id") or _slugify(persona.get("name", "persona"))
    slug = base_slug
    n = 2
    while (avatars_dir / f"{slug}.yaml").exists():
        slug = f"{base_slug}-{n}"
        n += 1
    persona["id"] = slug

    avatar = persona_to_avatar(persona)
    avatar_path = avatars_dir / f"{slug}.yaml"
    with open(avatar_path, "w", encoding="utf-8") as f:
        yaml.dump(
            avatar.model_dump(mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    index = _load_index(client_slug)
    index["personas"].append({
        "id": slug,
        "name": persona.get("name", ""),
        "role": persona.get("role", "secondary"),
        "awareness_level": persona.get("awareness_level", "problem_aware"),
        "confidence": persona.get("confidence", "medium"),
    })
    index_path = _write_index(client_slug, index)
    return avatar_path, index_path


def delete_persona(client_slug: str, slug: str) -> tuple[bool, Path | None]:
    """Remove the avatar YAML for `slug` and drop it from `_index.yaml`.

    Returns (deleted, path_removed). If the avatar file doesn't exist,
    returns (False, None). The index file is rewritten regardless of
    whether the slug was present in it.
    """
    avatars_dir = Path("clients") / client_slug / "avatars"
    avatar_path = avatars_dir / f"{slug}.yaml"
    if not avatar_path.exists():
        return False, None

    avatar_path.unlink()
    # Also drop the legacy `.bak` if a previous save left one behind.
    bak = avatar_path.with_suffix(".yaml.bak")
    if bak.exists():
        bak.unlink()

    index = _load_index(client_slug)
    index["personas"] = [p for p in index["personas"] if p.get("id") != slug]
    _write_index(client_slug, index)

    return True, avatar_path


def save_personas(client_slug: str, result: PersonasResult) -> tuple[Path, list[Path]]:
    """Persist personas as individual avatar YAMLs + an index file.

    Layout:
      clients/<slug>/avatars/<persona-id>.yaml  # one per persona, CustomerAvatar shape
      clients/<slug>/avatars/_index.yaml        # roster with role + confidence
    """
    avatars_dir = Path("clients") / client_slug / "avatars"
    avatars_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for persona in result.personas:
        pid = persona.get("id") or _slugify(persona.get("name", "persona"))
        avatar = persona_to_avatar(persona)
        path = avatars_dir / f"{pid}.yaml"
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(
                avatar.model_dump(mode="json"),
                f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
        written.append(path)

    index_path = avatars_dir / "_index.yaml"
    with open(index_path, "w", encoding="utf-8") as f:
        yaml.dump(result.index, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return index_path, written
