"""Strategy matrix — Schwartz awareness × persona messaging map.

Reads everything we have for a client (brand context + avatar(s) + products)
and produces a strategy matrix that maps each persona × awareness stage
combination to specific messaging guidance: angles, hooks, frameworks,
mechanics, and funnel placement.

System context is layered: motion/creative-strategy-engine drives the
strategic structure; product-marketing-context ensures the underlying
messaging hierarchy is sound.

Output: brand-context.md gets a strategy-matrix.md sibling, plus a
structured strategy-matrix.yaml that the brief generator can consume.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from models.brand import Brand
from models.avatar import CustomerAvatar
from models.product import Product
from models.skills import load_skill
from strategy.competitive_context import (
    format_competitive_block,
    format_psychology_summary,
    format_voc_block,
    load_competitive_gaps,
    load_voc_pains,
)
from strategy.llm import claude_complete

# Schwartz awareness stages — fixed vocabulary used across the codebase.
AWARENESS_STAGES = [
    "unaware",
    "problem_aware",
    "solution_aware",
    "product_aware",
    "most_aware",
]


@dataclass
class StrategyMatrixResult:
    matrix_md: str
    data: dict


MATRIX_SYSTEM = """You are a senior creative strategist producing a strategy
matrix for an e-commerce DTC brand. Your job is to map each persona × Schwartz
awareness stage combination to actionable messaging guidance.

You operate under TWO layered skills:
1. motion/creative-strategy-engine — pain × persona × awareness framework
2. coreyhaines/product-marketing-context — messaging hierarchy + positioning

Apply the creative-strategy-engine framework as the structural backbone.
Use product-marketing-context principles to ground every cell in real
positioning rather than generic strategist-speak.

--- CREATIVE STRATEGY ENGINE ---

""" + load_skill("motion/creative-strategy-engine") + """

--- PRODUCT MARKETING CONTEXT ---

""" + load_skill("product-marketing-context") + """

---

Output requirements:
- Be specific to this brand. No generic strategy.
- Reference the brand's actual products, language, and proof points.
- Each cell must read like instructions a strategist could hand to a copywriter.
- Output is YAML only, no markdown fences, matching the schema in the prompt."""


def _format_personas(avatars: list[CustomerAvatar]) -> str:
    """Format avatar(s) into compact text for the LLM context."""
    if not avatars:
        return "(no personas defined)"
    lines = []
    for i, av in enumerate(avatars, 1):
        pains = "; ".join(p.pain for p in av.pain_points[:5])
        desires = "; ".join(d.desire for d in av.desires[:5])
        lines.append(
            f"PERSONA {i}: {av.name or 'Primary'}\n"
            f"  Demographic: {av.demographic}\n"
            f"  Awareness level (current): {av.awareness_level}\n"
            f"  Top pains: {pains}\n"
            f"  Top desires: {desires}\n"
            f"  Objections: {', '.join(av.objections[:5])}\n"
            f"  Triggers: {', '.join(av.trigger_events[:5])}"
        )
    return "\n\n".join(lines)


def _format_products(products: list[Product]) -> str:
    """Format products into compact text for the LLM context."""
    if not products:
        return "(no products defined)"
    return "\n".join(
        f"- {p.name}: {p.description[:200]}"
        + (f" | URL: {p.url}" if p.url else "")
        for p in products
    )


def build_strategy_matrix(
    brand: Brand,
    avatars: list[CustomerAvatar],
    products: list[Product],
    brand_context_md: str = "",
    client_slug: str | None = None,
    competitive_gaps: dict | None = None,
    voc_pains: dict | None = None,
) -> StrategyMatrixResult:
    """Generate a strategy matrix for the given client.

    Returns both a human-readable markdown matrix and a structured YAML
    document with one cell per persona × awareness stage.

    Upstream research is auto-loaded when `client_slug` is supplied (and the
    relevant files exist on disk):
      * `clients/<slug>/research/competitive-gaps.yaml` → gap map synthesis
      * `clients/<slug>/voc/extracted_pains.yaml` → VoC corpus
      * `psychology_profile` block on each avatar → per-persona psych summary

    Each upstream slice is silently no-op'd when missing — the matrix still
    builds, just with thinner grounding. Callers can also pass `competitive_gaps`
    and `voc_pains` explicitly to override the auto-load (useful for tests).
    """
    if not avatars:
        raise ValueError(
            "No personas to build a matrix for. Run `adc research` first, or "
            "wait for Stage 2 (`adc personas`) to expand to multiple personas."
        )

    personas_text = _format_personas(avatars)
    products_text = _format_products(products)

    # Auto-load upstream research artifacts when client_slug provided and the
    # caller hasn't supplied them explicitly.
    if client_slug:
        if competitive_gaps is None:
            competitive_gaps = load_competitive_gaps(client_slug)
        if voc_pains is None:
            voc_pains = load_voc_pains(client_slug)

    competitive_block = format_competitive_block(competitive_gaps)
    voc_block = format_voc_block(voc_pains)
    psychology_block = format_psychology_summary(avatars)

    visual_id = ""
    if brand.visual_identity and brand.visual_identity.aesthetic:
        visual_id = (
            f"  Aesthetic: {brand.visual_identity.aesthetic}\n"
            f"  Design language: {brand.visual_identity.design_language}\n"
            f"  Mood: {', '.join(brand.visual_identity.mood)}\n"
        )

    prompt = f"""Build a strategy matrix for {brand.name}.

BRAND:
  Name: {brand.name}
  Tone: {brand.tone}
  Mission: {getattr(brand, 'mission', '') or '(not specified)'}
  Tagline: {getattr(brand, 'tagline', '') or '(not specified)'}
{visual_id}

PERSONAS:
{personas_text}

PRODUCTS IN SCOPE:
{products_text}

BRAND CONTEXT (excerpt for grounding):
{brand_context_md[:8000]}

# COMPETITIVE INTELLIGENCE

{competitive_block}

# VOICE-OF-CUSTOMER EVIDENCE

{voc_block}

# AVATAR PSYCHOLOGY

{psychology_block}

---

For EACH persona × EACH of the 5 Schwartz awareness stages
(unaware, problem_aware, solution_aware, product_aware, most_aware),
fill out a matrix cell. That's {len(avatars) * 5} total cells.

Return YAML with this exact structure:

matrix:
  - persona_name: "..."
    persona_id: "primary"  # or secondary, tertiary, etc.
    cells:
      - awareness_stage: "unaware"
        what_they_know: "What this audience currently believes/knows about their problem"
        what_they_dont_know_yet: "The gap to fill"
        primary_angle: "The strategic messaging angle for this stage (1 sentence)"
        hook_style: "Type of hook that works (e.g. 'shock-stat', 'pattern-interrupt', 'story-opener')"
        example_hook: "An actual scroll-stopping hook line written for THIS brand at THIS stage"
        framework: "pas | aida | bab | fab | four_cs | quest | pastor | slap"
        creative_mechanic: "Structural ad concept (e.g. 'Pattern Interrupt with Reveal', 'Talking Head Confession')"
        proof_to_surface: "Specific proof point from this brand to lead with"
        cta: "Call to action language for this stage"
        funnel_placement: "cold | warm | retargeting"
        notes: "Any brand-specific guidance or warnings for this cell"
      # ... 4 more cells (problem_aware, solution_aware, product_aware, most_aware)

cross_stage_observations:
  highest_leverage_stages: ["which stages are biggest opportunities for this brand"]
  weakest_stages: ["which stages are hardest given the brand's current proof points"]
  ad_distribution_recommendation: "How budget/creative volume should split across stages"
  category_specific_notes: "Anything specific to this product category"

Quality checks:
1. Every example_hook must reference the brand's actual product, language, or proof.
2. Every proof_to_surface must come from the brand's real assets (Today Show, founder story, reviews, specific numbers).
3. CTAs should match the buying-stage psychology (Learn More for unaware, Shop Now for most_aware).
4. Funnel placement should be: unaware = cold, problem_aware = cold, solution_aware = cold/warm, product_aware = warm/retargeting, most_aware = retargeting.
5. When COMPETITIVE INTELLIGENCE lists exploitable gaps, at least one cell per persona must attack a specific gap by name in its primary_angle.
6. When VOICE-OF-CUSTOMER EVIDENCE includes verbatim quotes, prefer using customer phrasing (or near-paraphrase) in example_hook over strategist-speak.
7. When AVATAR PSYCHOLOGY lists dominant heuristics for a persona, that persona's cells must lean on those heuristics in hook_style and creative_mechanic — and must avoid the avatar's weak heuristics.

Output YAML only. No markdown fences."""

    # 16000 tokens — generous headroom for 3 personas × 5 stages × ~10 fields each
    # plus the cross-stage observations block. The pre-patch budget of 10000 was
    # snug for 1 persona; 3 personas need ~3x the body.
    raw = claude_complete(prompt, system=MATRIX_SYSTEM, max_tokens=16000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        # Surface the raw output to a debug file so the operator can inspect
        # what the LLM emitted rather than chasing a stack trace into yaml internals.
        dump_path = Path("clients") / (client_slug or "_unknown") / "strategy-matrix.raw.txt"
        dump_path.parent.mkdir(parents=True, exist_ok=True)
        dump_path.write_text(raw, encoding="utf-8")
        raise ValueError(
            f"Strategy matrix LLM output failed to parse as YAML: {e}. "
            f"Raw output saved to {dump_path} for inspection."
        ) from e

    matrix_md = _render_markdown(brand, avatars, data)

    return StrategyMatrixResult(matrix_md=matrix_md, data=data)


def _render_markdown(brand: Brand, avatars: list[CustomerAvatar], data: dict) -> str:
    """Render the structured matrix as a human-readable markdown report."""
    lines: list[str] = []
    lines.append(f"# Strategy Matrix: {brand.name}")
    lines.append("")
    lines.append(
        f"*{len(avatars)} persona(s) × 5 Schwartz awareness stages = "
        f"{len(avatars) * 5} messaging cells*"
    )
    lines.append("")
    lines.append("---")
    lines.append("")

    matrix = data.get("matrix", []) or []
    for persona_block in matrix:
        name = persona_block.get("persona_name", "Persona")
        pid = persona_block.get("persona_id", "")
        lines.append(f"## {name}" + (f" *({pid})*" if pid else ""))
        lines.append("")

        cells = persona_block.get("cells", []) or []
        for cell in cells:
            stage = cell.get("awareness_stage", "?")
            lines.append(f"### {stage.replace('_', ' ').title()}")
            lines.append("")
            lines.append(f"**Angle:** {cell.get('primary_angle', '')}")
            lines.append("")
            lines.append(f"**What they know:** {cell.get('what_they_know', '')}")
            lines.append("")
            lines.append(f"**Gap to fill:** {cell.get('what_they_dont_know_yet', '')}")
            lines.append("")
            lines.append(f"**Hook style:** {cell.get('hook_style', '')}")
            lines.append("")
            example = cell.get("example_hook", "")
            if example:
                lines.append(f"**Example hook:** *\"{example}\"*")
                lines.append("")
            lines.append(
                f"**Framework:** `{cell.get('framework', '')}` | "
                f"**Mechanic:** {cell.get('creative_mechanic', '')}"
            )
            lines.append("")
            lines.append(f"**Proof to surface:** {cell.get('proof_to_surface', '')}")
            lines.append("")
            lines.append(
                f"**CTA:** {cell.get('cta', '')} | "
                f"**Funnel:** {cell.get('funnel_placement', '')}"
            )
            lines.append("")
            notes = cell.get("notes", "")
            if notes:
                lines.append(f"*Notes: {notes}*")
                lines.append("")
            lines.append("---")
            lines.append("")

    obs = data.get("cross_stage_observations") or {}
    if obs:
        lines.append("## Cross-stage observations")
        lines.append("")
        if obs.get("highest_leverage_stages"):
            lines.append(
                f"**Highest leverage stages:** "
                f"{', '.join(obs['highest_leverage_stages'])}"
            )
            lines.append("")
        if obs.get("weakest_stages"):
            lines.append(
                f"**Weakest stages:** {', '.join(obs['weakest_stages'])}"
            )
            lines.append("")
        if obs.get("ad_distribution_recommendation"):
            lines.append(
                f"**Budget/creative distribution:** "
                f"{obs['ad_distribution_recommendation']}"
            )
            lines.append("")
        if obs.get("category_specific_notes"):
            lines.append(
                f"**Category notes:** {obs['category_specific_notes']}"
            )
            lines.append("")

    return "\n".join(lines)


def save_matrix(client_slug: str, result: StrategyMatrixResult) -> tuple[Path, Path]:
    """Persist the matrix as both markdown and YAML next to the brand context."""
    client_dir = Path("clients") / client_slug
    md_path = client_dir / "strategy-matrix.md"
    yaml_path = client_dir / "strategy-matrix.yaml"

    md_path.write_text(result.matrix_md, encoding="utf-8")
    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(result.data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    return md_path, yaml_path
