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
- Output YAML only, no markdown fences."""


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "persona"


def build_personas(
    brand: Brand,
    brand_context_md: str,
    max_personas: int = 4,
) -> PersonasResult:
    """Generate structured personas from a brand context document.

    Returns a list of persona dicts (each ready to be saved as a YAML
    avatar file) and an index dict that registers each persona with its
    role and slug.
    """
    if not brand_context_md:
        raise ValueError(
            "No brand-context.md provided. Run `adc research` first."
        )

    prompt = f"""Read the brand context below and produce a structured persona set
for {brand.name}. Identify every distinct audience tier the brand context
references (primary, secondary, tertiary), and write a complete persona for each.

Up to {max_personas} personas. Skip anti-personas. Skip generic 'gift buyer'
unless the brand context explicitly emphasizes them.

BRAND CONTEXT:
{brand_context_md[:12000]}

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
