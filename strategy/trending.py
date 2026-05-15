"""Trending ad format recommender.

Given a CreativeBrief, pick the top 3 currently-trending ad formats that best
fit the brief's audience and angle. Outputs go into the brief's
`trending_format_recommendations` field as inspiration for alternative
video/static executions the operator can produce in parallel.

Pipeline:
  1. Load trending_formats.yaml from the repo root.
  2. Pre-filter by rule-based signal matching (awareness level, persona
     descriptors, product category tags) — narrows to ~3-5 candidates.
  3. Single Claude call ranks the top 3 with 1-2 sentence rationales each.
  4. Returns list of dicts ready to attach to the brief.

The recommendation is purely informational — it does NOT change the
underlying image generation. Operators see it in the brief notes header
and dashboard as "here's a trending alternative you could also try".
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from strategy.llm import claude_complete

if TYPE_CHECKING:
    from models.avatar import CustomerAvatar
    from models.brand import Brand
    from models.brief import CreativeBrief

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRENDING_PATH = REPO_ROOT / "trending_formats.yaml"


# ─── Library loader ─────────────────────────────────────────────────────────


def load_trending_formats(path: Path | None = None) -> list[dict]:
    """Load trending_formats.yaml. Returns only `Active` entries."""
    target = path or DEFAULT_TRENDING_PATH
    if not target.exists():
        return []
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except Exception:
        return []
    formats = data.get("trending_formats") if isinstance(data, dict) else []
    if not isinstance(formats, list):
        return []
    return [
        f for f in formats
        if isinstance(f, dict)
        and f.get("id")
        and (f.get("status") or "Active") == "Active"
    ]


# ─── Rule-based prefilter ───────────────────────────────────────────────────


def _awareness_score(brief: "CreativeBrief", fmt: dict) -> int:
    """+2 if brief's awareness_level is in best_when.awareness_levels."""
    levels = (fmt.get("best_when") or {}).get("awareness_levels") or []
    brief_level = brief.awareness_level.value if brief.awareness_level else ""
    return 2 if brief_level in levels else 0


def _persona_score(brief: "CreativeBrief", fmt: dict) -> int:
    """+1 per shared persona descriptor (tokens in brief.persona ∩ best_when.persona_types)."""
    persona_tags = (fmt.get("best_when") or {}).get("persona_types") or []
    if not persona_tags:
        return 0
    persona_text = (brief.persona or "").lower()
    score = 0
    for tag in persona_tags:
        # tag is a hyphenated label like 'gen-z' — match substring against persona text
        token = re.sub(r"[\-_]+", " ", tag.lower()).strip()
        if token and token in persona_text:
            score += 1
    return score


def _category_score(brief: "CreativeBrief", fmt: dict) -> int:
    """+1 if 'any' is allowed, or if product name maps to a category tag."""
    cats = (fmt.get("best_when") or {}).get("product_categories") or []
    if "any" in [c.lower() for c in cats]:
        return 1
    # Heuristic: rough mapping from brief.product (e.g. 'Gut Balance') to category.
    # This is a soft signal — the LLM ranker will refine.
    return 0


def prefilter_formats(
    brief: "CreativeBrief",
    formats: list[dict],
    top_n: int = 5,
) -> list[dict]:
    """Rule-based prefilter: score each format, return top N by score.

    Scores are intentionally cheap — they narrow the candidate pool before
    the LLM rank step writes rationales. Tiebreakers preserve YAML order
    (i.e. the canonical list order in trending_formats.yaml)."""
    if not formats:
        return []
    scored: list[tuple[int, int, dict]] = []
    for idx, fmt in enumerate(formats):
        score = (
            _awareness_score(brief, fmt)
            + _persona_score(brief, fmt)
            + _category_score(brief, fmt)
        )
        scored.append((score, idx, fmt))
    # Sort by (-score, idx) — higher score first, then preserve original order
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in scored[:top_n]]


# ─── LLM-backed rank-and-rationale ──────────────────────────────────────────


_RANKER_SYSTEM = """You are a performance-marketing strategist who recommends
which trending ad formats best fit a creative brief.

You receive:
  - A creative brief (persona, hook, framework, angle, awareness level)
  - A list of trending ad format candidates with id, name, summary, and
    best_when signals

Your job: rank the top 3 formats for this brief and write a 1-2 sentence
rationale for each. The rationale must explain WHY this format fits THIS
brief — referencing specific persona traits or angle.

Output STRICT JSON only (no markdown fences, no commentary):

{
  "recommendations": [
    {
      "format_id": "<id from candidates>",
      "rank": 1,
      "rationale": "<1-2 sentence explanation>",
      "production_notes": "<1 sentence on what to be careful about when producing this>"
    },
    {"format_id": "...", "rank": 2, "rationale": "...", "production_notes": "..."},
    {"format_id": "...", "rank": 3, "rationale": "...", "production_notes": "..."}
  ]
}

Use double-quoted strings. Escape inner quotes with backslash. No trailing
commas. format_id MUST be one of the candidate ids."""


def _format_brief_summary(brief: "CreativeBrief") -> str:
    """Compact, scannable summary of the brief for the LLM ranker."""
    parts = [
        f"persona: {brief.persona or '—'}",
        f"awareness: {brief.awareness_level.value if brief.awareness_level else '—'}",
        f"framework: {brief.framework.value if brief.framework else '—'}",
        f"angle: {brief.angle or '—'}",
        f"hook_type: {brief.hook_type or '—'}",
        f"hook: {(brief.hook or '')[:140]}",
        f"pain_point: {(brief.pain_point or '')[:140]}",
        f"product: {brief.product or '—'}",
    ]
    return "\n  ".join(parts)


def _format_candidate_summary(fmt: dict) -> str:
    """Compact candidate summary for the ranker prompt."""
    bw = fmt.get("best_when") or {}
    return (
        f"  id: {fmt.get('id')}\n"
        f"    name: {fmt.get('name')}\n"
        f"    summary: {(fmt.get('summary') or '').strip()[:240]}\n"
        f"    format_type: {fmt.get('format_type', 'both')}\n"
        f"    complexity: {fmt.get('production_complexity', 'medium')}\n"
        f"    best_for: awareness={bw.get('awareness_levels', [])}, "
        f"persona_types={bw.get('persona_types', [])}\n"
    )


def _parse_ranker_response(text: str) -> list[dict]:
    """Parse the JSON from the ranker. Returns [] on any parse failure."""
    body = text.strip()
    # Strip markdown fences if the model ignored instructions
    if body.startswith("```"):
        first = body.find("\n")
        if first != -1:
            body = body[first + 1:]
    if body.endswith("```"):
        body = body.rsplit("```", 1)[0].rstrip()
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    recs = data.get("recommendations") or []
    if not isinstance(recs, list):
        return []
    cleaned: list[dict] = []
    for r in recs:
        if not isinstance(r, dict) or not r.get("format_id"):
            continue
        cleaned.append({
            "format_id": str(r["format_id"]).strip(),
            "rank": int(r.get("rank") or len(cleaned) + 1),
            "rationale": str(r.get("rationale") or "").strip(),
            "production_notes": str(r.get("production_notes") or "").strip(),
        })
    return cleaned


def rank_top_3(
    brief: "CreativeBrief",
    candidates: list[dict],
) -> list[dict]:
    """Single Claude call. Returns top 3 ranked recommendations with rationales.

    Each entry has: format_id, rank, rationale, production_notes. The
    format_id is also enriched with the source format's name / summary /
    format_type for convenience (looked up from `candidates`)."""
    if not candidates:
        return []

    candidate_block = "\n".join(_format_candidate_summary(c) for c in candidates)
    brief_block = _format_brief_summary(brief)
    user_prompt = f"""CREATIVE BRIEF:
  {brief_block}

CANDIDATE TRENDING FORMATS (pick top 3 from these):
{candidate_block}

Rank the top 3 for THIS brief. Return JSON per the system instructions."""

    raw = claude_complete(user_prompt, system=_RANKER_SYSTEM, max_tokens=1024)
    recs = _parse_ranker_response(raw)
    if not recs:
        return []

    # Enrich each rec with the source format's metadata for downstream display
    by_id = {c.get("id"): c for c in candidates}
    enriched: list[dict] = []
    for r in recs[:3]:
        src = by_id.get(r["format_id"])
        if src is None:
            continue
        enriched.append({
            "format_id": r["format_id"],
            "name": src.get("name", ""),
            "summary": src.get("summary", ""),
            "format_type": src.get("format_type", "both"),
            "production_complexity": src.get("production_complexity", "medium"),
            "rank": r["rank"],
            "rationale": r["rationale"],
            "production_notes": r["production_notes"],
        })
    return enriched


# ─── Top-level recommender ──────────────────────────────────────────────────


def recommend_trending_formats(
    brief: "CreativeBrief",
    *,
    library_path: Path | None = None,
    prefilter_top_n: int = 5,
) -> list[dict]:
    """Recommend the top 3 trending formats for a brief.

    Returns a list of up to 3 dicts (empty if the library is empty or the
    ranker fails). Each dict has: format_id, name, summary, format_type,
    production_complexity, rank, rationale, production_notes."""
    formats = load_trending_formats(library_path)
    if not formats:
        return []
    candidates = prefilter_formats(brief, formats, top_n=prefilter_top_n)
    if not candidates:
        return []
    return rank_top_3(brief, candidates)


def recommend_trending_formats_for_briefs(
    briefs: list["CreativeBrief"],
    *,
    library_path: Path | None = None,
) -> dict[str, list[dict]]:
    """Run the recommender for many briefs. Returns a {brief_id → recs} map.

    Currently calls the per-brief recommender N times — Claude prompt
    caching on the system prompt keeps marginal cost low. Future
    optimization: batch into one Claude call with all briefs summarized."""
    out: dict[str, list[dict]] = {}
    for b in briefs:
        try:
            out[b.brief_id] = recommend_trending_formats(b, library_path=library_path)
        except Exception:
            out[b.brief_id] = []
    return out
