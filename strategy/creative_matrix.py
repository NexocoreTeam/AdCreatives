"""Creative Matrix — tactical 4-tab synthesis bridging briefs and image-gen.

Reads the existing research outputs (competitive-gaps.yaml, VOC corpus, avatars,
brand context) and synthesizes a CreativeMatrix with four tabs:

    pain_vs_competitor   — gap-mining: competitor complaints + our advantage
    what_they_love       — emotional triggers competitors solve well
    wishes_gaps          — white-space products / fixes customers wish for
    hook_angles          — ready-to-shoot hook executions

Every row carries a bridge layer (format_fit, static_treatment, psychology_trigger)
plus a primary `trending_match` keyed against trending_formats.yaml. Cost-tiered:

    lean      — trending_match only, no trending_next (50% cost)
    standard  — trending_match + trending_next (eager, baseline cost)
    wide      — trending_match + 2 alternates (180% cost, rarely worth it)

Output (atomic write):
    clients/<slug>/strategy/creative_matrix.yaml    canonical, machine-readable
    clients/<slug>/strategy/matrix_meta.yaml        provenance (sources, dates, tier)
    clients/<slug>/strategy/creative_matrix.xlsx    human-facing (via matrix_xlsx)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from models.avatar import HEURISTIC_NAMES, CustomerAvatar
from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.loader import load_brand
from models.matrix import (
    FORMAT_FIT_VALUES,
    SOURCE_TYPES,
    CreativeMatrix,
    MatrixRow,
    MatrixTab,
    TrendingMatch,
    TrendingNext,
)
from models.product import Product
from strategy.llm import claude_complete
from strategy.trending import load_trending_formats

CLIENTS_DIR = Path("clients")


# ─── I/O ────────────────────────────────────────────────────────────────────


def matrix_paths(client_slug: str) -> dict[str, Path]:
    base = CLIENTS_DIR / client_slug / "strategy"
    return {
        "dir": base,
        "yaml": base / "creative_matrix.yaml",
        "meta": base / "matrix_meta.yaml",
        "xlsx": base / "creative_matrix.xlsx",
    }


def save_matrix(matrix: CreativeMatrix, client_slug: str) -> Path:
    paths = matrix_paths(client_slug)
    paths["dir"].mkdir(parents=True, exist_ok=True)

    data = matrix.model_dump(mode="json", exclude_none=True)
    paths["yaml"].write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    meta = {
        "client": matrix.client,
        "generated_at": matrix.generated_at,
        "matrix_version": matrix.matrix_version,
        "trending_source": matrix.trending_source,
        "research_sources_used": matrix.research_sources_used,
        "tier": matrix.tier,
        "row_counts": {
            "pain_vs_competitor": len(matrix.pain_vs_competitor),
            "what_they_love": len(matrix.what_they_love),
            "wishes_gaps": len(matrix.wishes_gaps),
            "hook_angles": len(matrix.hook_angles),
        },
    }
    paths["meta"].write_text(
        yaml.safe_dump(meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return paths["yaml"]


def load_matrix(client_slug: str) -> CreativeMatrix:
    path = matrix_paths(client_slug)["yaml"]
    if not path.exists():
        raise FileNotFoundError(
            f"No creative matrix at {path}. Run `adc matrix --client {client_slug}` first."
        )
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return CreativeMatrix(**data)


# ─── Research loaders ───────────────────────────────────────────────────────


def _load_competitive_gaps(client_slug: str) -> dict | None:
    path = CLIENTS_DIR / client_slug / "research" / "competitive-gaps.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_voc_corpus(client_slug: str) -> dict | None:
    path = CLIENTS_DIR / client_slug / "voc" / "extracted_pains.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _load_brand_context(client_slug: str) -> str:
    path = CLIENTS_DIR / client_slug / "brand-context.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")[:6000]


def _detect_sources_used(
    gaps_data: dict | None,
    voc_data: dict | None,
) -> dict[str, list[str]]:
    """Best-effort detection of which research sources the matrix is built on.

    The matrix doesn't fetch — it synthesizes from prior stages. We surface
    what those prior stages used so the operator can audit gaps in coverage.
    """
    sources: set[str] = set()
    if gaps_data:
        for analysis in gaps_data.get("per_brand", {}).get("competitors", []):
            for source in analysis.get("meta", {}).get("sources", []):
                sources.add(source)
        own = gaps_data.get("per_brand", {}).get("own", {})
        for source in own.get("meta", {}).get("sources", []):
            sources.add(source)
    if voc_data:
        sources.add("voc_corpus")

    tier_1 = {"reddit", "amazon", "trustpilot"}
    tier_3_keywords = ("tiktok", "instagram", "ig_", "youtube")

    classified: dict[str, list[str]] = {"tier_1": [], "tier_2": [], "tier_3": []}
    for s in sorted(sources):
        if s in tier_1 or any(s.startswith(t) for t in tier_1):
            classified["tier_1"].append(s)
        elif any(k in s.lower() for k in tier_3_keywords):
            classified["tier_3"].append(s)
        else:
            classified["tier_2"].append(s)
    return {k: v for k, v in classified.items() if v}


# ─── Shared system prompt ───────────────────────────────────────────────────


_MATRIX_SHARED_SYSTEM = f"""You are a direct-response creative strategist building a
tactical "creative matrix" for paid social ads. The matrix is the layer between
brand strategy and image/video generation — every row must be specific enough
to shoot, not generic enough to be filler.

HARD RULES:

- Use ONLY language and evidence from the provided research. Do not invent
  customer quotes. If the research doesn't support a row, do not write it.
- Every row's `what_people_say` must read like real customer speech in 7-10 words.
  Verbatim where possible; tight paraphrase when not.
- `format_fit` MUST be a non-empty subset of: {sorted(FORMAT_FIT_VALUES)}
  Pick 1-3. Lead with the strongest fit. Use "video-only" when the row cannot
  reasonably be executed as a static image.
- `static_treatment` is the image-ad direction. Write it like a shoot brief:
  composition, headline, what's in frame. 1-3 sentences. Empty string only
  when format_fit is exactly ["video-only"].
- `psychology_trigger` MUST be one of: {sorted(HEURISTIC_NAMES)}
  Pick the single dominant heuristic the row activates. Empty allowed only if
  the row genuinely activates none cleanly.
- `source_type` values MUST come from: {sorted(SOURCE_TYPES)}

PRODUCT-LEVEL GAPS ONLY. Do not surface operational complaints (shipping,
billing, support quality, website UX). Paid creative converts on what the
product DOES, not on how the company operates.

Output STRICT JSON only — no markdown fences, no commentary, no trailing
commas. Use double-quoted strings."""


# ─── Tab generators ─────────────────────────────────────────────────────────


def _gaps_research_block(gaps_data: dict | None) -> str:
    """Compact, scannable digest of competitive-gaps.yaml for tab prompts."""
    if not gaps_data:
        return "(No competitive-gaps.yaml found — operator should run `adc analyze-gaps` first.)"

    parts: list[str] = []
    syn = gaps_data.get("synthesis", {})
    if syn.get("exploitable_gaps"):
        parts.append("EXPLOITABLE GAPS (per cross-competitor synthesis):")
        for g in syn["exploitable_gaps"]:
            parts.append(
                f"  - opportunity: {g.get('opportunity', '')}\n"
                f"    competitors_failing: {g.get('competitors_failing', [])}\n"
                f"    evidence: {g.get('customer_evidence', '')!r}\n"
                f"    our_advantage: {g.get('our_advantage', '')}\n"
                f"    ad_angle: {g.get('ad_angle', '')}"
            )
    if syn.get("shared_dealbreakers"):
        parts.append("\nSHARED DEALBREAKERS (category-wide vulnerabilities):")
        for d in syn["shared_dealbreakers"]:
            parts.append(
                f"  - issue: {d.get('issue', '')}\n"
                f"    affected: {d.get('affected_competitors', [])}\n"
                f"    our_response: {d.get('our_response', '')}"
            )

    per_brand = gaps_data.get("per_brand", {})
    competitors = per_brand.get("competitors", [])
    if competitors:
        parts.append("\nPER-COMPETITOR LOVES / GAPS / DEALBREAKERS (raw):")
        for c in competitors[:6]:  # cap to avoid blowing context
            brand = c.get("brand", "?")
            parts.append(f"\n  === {brand} ===")
            for bucket_key, label in [
                ("loves", "LOVES"),
                ("gaps", "GAPS"),
                ("dealbreakers", "DEALBREAKERS"),
            ]:
                items = c.get(bucket_key, []) or []
                if not items:
                    continue
                parts.append(f"  {label}:")
                for it in items[:5]:
                    claim = it.get("claim") or it.get("gap") or it.get("issue") or ""
                    quote = it.get("money_quote", "")
                    sources = it.get("sources", [])
                    parts.append(
                        f"    - {claim} (sources: {sources})"
                        + (f"\n      quote: {quote!r}" if quote else "")
                    )

    return "\n".join(parts) if parts else "(competitive-gaps.yaml present but empty)"


def _voc_research_block(voc_data: dict | None) -> str:
    if not voc_data:
        return "(No VOC corpus extracted.)"
    digest: dict[str, Any] = {}
    for key in (
        "pain_points",
        "trigger_moments",
        "desires",
        "objections",
        "transformations",
        "money_quotes",
    ):
        items = voc_data.get(key, [])
        if items:
            digest[key] = items[:8]  # cap per bucket
    if not digest:
        return "(VOC corpus present but no signal-bearing buckets populated.)"
    return yaml.safe_dump(digest, sort_keys=False, allow_unicode=True)


def _brand_summary_block(brand: Brand) -> str:
    """Compact brand identity slice for matrix prompts."""
    data = brand.model_dump(mode="json")
    interesting = {
        k: v for k, v in data.items()
        if k in ("name", "category", "differentiators", "positioning", "tone",
                 "value_props", "ingredients", "key_claims", "guarantee")
        and v
    }
    return yaml.safe_dump(interesting, sort_keys=False, allow_unicode=True)


_TAB_1_USER_TEMPLATE = """Build TAB 1 of the creative matrix: pain_vs_competitor.

This tab mines NEGATIVE competitor signal — complaints, gaps, and dealbreakers
where our brand has a credible product-level advantage.

# OUR BRAND
{brand_block}

# BRAND CONTEXT (excerpt)
{brand_context}

# COMPETITIVE RESEARCH
{gaps_block}

# VOC (own + adjacent)
{voc_block}

Produce a JSON array of 10-15 rows. Each row:

{{
  "id": "pain-NNN",                          // zero-padded sequence
  "tab": "pain_vs_competitor",
  "complaint": "...",                        // specific, product-level
  "source_type": ["..."],                    // from SOURCE_TYPES picklist
  "what_people_say": "7-10 word verbatim-flavoured summary",
  "our_advantage": "...",
  "positioning_angle": "...",                // ad-ready angle
  "format_fit": ["us-vs-them", "..."],
  "static_treatment": "shoot direction in 1-3 sentences",
  "psychology_trigger": "<one of HEURISTIC_NAMES>"
}}

Rules specific to this tab:
- Prefer complaints with verbatim customer quotes in the research over
  paraphrased synthesis claims.
- our_advantage must reference a concrete product fact (ingredient,
  formulation, format, mechanism) — not a vague "we're better".
- positioning_angle must be shoot-ready copy, not a meta-description.

Return JSON only: {{"rows": [ ... ]}}"""


_TAB_2_USER_TEMPLATE = """Build TAB 2 of the creative matrix: what_they_love.

This tab mines POSITIVE competitor signal — emotional triggers and
transformations customers rave about. We piggyback on what's working in the
category to amplify the same trigger with our product.

# OUR BRAND
{brand_block}

# BRAND CONTEXT (excerpt)
{brand_context}

# COMPETITIVE RESEARCH (focus on LOVES buckets per competitor)
{gaps_block}

# VOC TRANSFORMATIONS & DESIRES
{voc_block}

Produce a JSON array of 8-12 rows. Each row:

{{
  "id": "love-NNN",
  "tab": "what_they_love",
  "emotional_trigger": "the deep win customers describe (e.g. 'healed eczema after years')",
  "source_type": ["..."],
  "what_people_say": "7-10 word verbatim-flavoured summary",
  "hook_or_angle_to_amplify": "how OUR ad lands the same trigger",
  "format_fit": ["before-after", "..."],
  "static_treatment": "shoot direction in 1-3 sentences",
  "psychology_trigger": "<one of HEURISTIC_NAMES>"
}}

Rules specific to this tab:
- Lead with the strongest, most evidence-backed emotional wins from competitor
  research — these are validated category triggers.
- hook_or_angle_to_amplify must describe what OUR ad shows or says, not
  a generic theme.
- Strongly favor format_fit values that show transformation: before-after,
  ugc-static, screenshot-review, editorial.

Return JSON only: {{"rows": [ ... ]}}"""


_TAB_3_USER_TEMPLATE = """Build TAB 3 of the creative matrix: wishes_gaps.

This tab mines WHITE SPACE — products, fixes, or features customers wish
existed in the category. The frustration behind the wish is creative gold
because it surfaces unmet needs nobody has addressed yet.

# OUR BRAND
{brand_block}

# BRAND CONTEXT (excerpt)
{brand_context}

# COMPETITIVE RESEARCH (focus on GAPS buckets per competitor + synthesis exploitable_gaps)
{gaps_block}

# VOC OBJECTIONS & WISHES
{voc_block}

Produce a JSON array of 6-10 rows. Each row:

{{
  "id": "wish-NNN",
  "tab": "wishes_gaps",
  "wished_product": "what they wish existed (e.g. 'a tallow balm that doesn't smell beefy')",
  "source_type": ["..."],
  "real_frustration": "the underlying frustration (1 sentence)",
  "script_or_static_opportunity": "concrete creative we can build off this wish",
  "format_fit": ["...", "..."],
  "static_treatment": "shoot direction in 1-3 sentences",
  "psychology_trigger": "<one of HEURISTIC_NAMES>"
}}

Rules specific to this tab:
- Each row's wish should be one our brand can credibly satisfy or speak to —
  don't surface gaps we can't address.
- The "I wish..." / "if only..." / "would be perfect if..." pattern in the
  research is the strongest signal.

Return JSON only: {{"rows": [ ... ]}}"""


_TAB_4_USER_TEMPLATE = """Build TAB 4 of the creative matrix: hook_angles.

This tab is the EXECUTION layer — ready-to-shoot hook openings combining
tactic + setup + why-it-works. Draw on the strategic seeds in Tabs 1-3 plus
the brand context.

# OUR BRAND
{brand_block}

# BRAND CONTEXT (excerpt)
{brand_context}

# UPSTREAM TAB SEEDS (use as raw material)
{prior_tabs_block}

Produce a JSON array of 10-15 rows. Each row:

{{
  "id": "hook-NNN",
  "tab": "hook_angles",
  "hook_angle": "the actual opening line, written as ad copy",
  "tactic": "the hook tactic name (e.g. 'edible-reveal', 'pattern-interrupt', 'identity-callout')",
  "story_setup": "the story or setup beats — what happens on screen",
  "why_it_works": "1-2 sentence rationale grounded in psychology or current platform behavior",
  "format_fit": ["...", "..."],
  "static_treatment": "image direction (empty string if format_fit is video-only)",
  "psychology_trigger": "<one of HEURISTIC_NAMES>"
}}

Rules specific to this tab:
- hook_angle must be the LINE ITSELF, in quotes if needed — not a description
  of the hook. The operator should be able to copy-paste it into a shoot.
- Mix static-friendly and video-friendly tactics across the rows.
- Reference rows from Tabs 1-3 in `why_it_works` when the hook lands on one
  of those strategic seeds.

Return JSON only: {{"rows": [ ... ]}}"""


def _generate_tab(
    tab: MatrixTab,
    *,
    brand: Brand,
    brand_context: str,
    gaps_block: str,
    voc_block: str,
    prior_tabs_block: str = "",
) -> list[MatrixRow]:
    """Single Claude call per tab. Returns parsed, validated rows."""
    template_map = {
        MatrixTab.PAIN_VS_COMPETITOR: _TAB_1_USER_TEMPLATE,
        MatrixTab.WHAT_THEY_LOVE: _TAB_2_USER_TEMPLATE,
        MatrixTab.WISHES_GAPS: _TAB_3_USER_TEMPLATE,
        MatrixTab.HOOK_ANGLES: _TAB_4_USER_TEMPLATE,
    }
    template = template_map[tab]

    user_prompt = template.format(
        brand_block=_brand_summary_block(brand),
        brand_context=brand_context or "(brand-context.md missing)",
        gaps_block=gaps_block,
        voc_block=voc_block,
        prior_tabs_block=prior_tabs_block,
    )

    raw = claude_complete(
        user_prompt,
        system=_MATRIX_SHARED_SYSTEM,
        max_tokens=8192,
    )

    parsed = _parse_json_with_rows(raw)
    if not parsed:
        raise RuntimeError(
            f"Failed to parse JSON for tab {tab.value}. First 500 chars: {raw[:500]!r}"
        )

    rows: list[MatrixRow] = []
    for i, row_data in enumerate(parsed.get("rows", [])):
        # Force the tab field (LLM occasionally drops or mangles it) and
        # re-number ids so we never accept LLM-supplied collisions across runs.
        row_data["tab"] = tab.value
        row_data["id"] = _normalize_id(tab, i + 1)
        # Normalize source_type values — the LLM sometimes emits domain-suffix
        # variants like 'trustpilot.com' or hallucinated review aggregators
        # like 'thingtesting.com' that the strict picklist rejects. Map them
        # to canonical SOURCE_TYPES so we don't lose otherwise-good rows.
        if isinstance(row_data.get("source_type"), list):
            row_data["source_type"] = _normalize_source_types(row_data["source_type"])
        try:
            rows.append(MatrixRow(**row_data))
        except Exception as e:
            # Skip individual bad rows rather than nuking the whole tab.
            # Operator can re-run --row <id> later if needed.
            print(f"  [skip {tab.value} row {i + 1}] {e}")
            continue
    return rows


# Common LLM aliases mapped to canonical SOURCE_TYPES picklist values.
# Anything not in this map AND not in SOURCE_TYPES is bucketed into
# `vertical_site` if it looks like a domain, else `other`.
_SOURCE_TYPE_ALIASES: dict[str, str] = {
    "trustpilot.com": "trustpilot",
    "amazon.com": "amazon",
    "us.amazon.com": "amazon",
    "amazon.co.uk": "amazon",
    "amazon.ca": "amazon",
    "reddit.com": "reddit",
    "old.reddit.com": "reddit",
    "tiktok.com": "tiktok_comments",
    "tiktok": "tiktok_comments",
    "instagram.com": "ig_comments",
    "instagram": "ig_comments",
    "ig": "ig_comments",
    "youtube.com": "youtube_comments",
    "youtube": "youtube_comments",
    "yt": "youtube_comments",
    "onsite": "onsite_reviews",
    "on-site": "onsite_reviews",
    "voc": "voc_corpus",
}


def _normalize_source_types(values: list[str]) -> list[str]:
    """Coerce LLM-emitted source values into the canonical SOURCE_TYPES picklist.

    Strategy:
      1. Lowercase + strip.
      2. If already canonical, keep as-is.
      3. If in alias map, swap to canonical.
      4. If contains a dot (looks like a domain), bucket as vertical_site.
      5. Else fall back to 'other'.
    Dedupes while preserving first-seen order.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for v in values:
        if not isinstance(v, str):
            continue
        v_lower = v.lower().strip().lstrip("@")
        canonical: str
        if v_lower in SOURCE_TYPES:
            canonical = v_lower
        elif v_lower in _SOURCE_TYPE_ALIASES:
            canonical = _SOURCE_TYPE_ALIASES[v_lower]
        elif "." in v_lower:
            canonical = "vertical_site"
        else:
            canonical = "other"
        if canonical not in seen:
            seen.add(canonical)
            cleaned.append(canonical)
    return cleaned


def _normalize_id(tab: MatrixTab, n: int) -> str:
    prefix_map = {
        MatrixTab.PAIN_VS_COMPETITOR: "pain",
        MatrixTab.WHAT_THEY_LOVE: "love",
        MatrixTab.WISHES_GAPS: "wish",
        MatrixTab.HOOK_ANGLES: "hook",
    }
    return f"{prefix_map[tab]}-{n:03d}"


def _summarize_tab_for_hook_seed(rows: list[MatrixRow], tab_label: str) -> str:
    """One-line digests of rows from a prior tab, fed into Tab 4."""
    if not rows:
        return f"({tab_label}: empty)"
    lines = [f"=== {tab_label} ==="]
    for r in rows[:12]:
        anchor = (
            r.complaint
            or r.emotional_trigger
            or r.wished_product
            or r.hook_angle
            or "(unspecified)"
        )
        lines.append(
            f"  {r.id}: {anchor[:120]} | psych: {r.psychology_trigger or '—'}"
        )
    return "\n".join(lines)


# ─── Trending match ─────────────────────────────────────────────────────────


_TRENDING_SYSTEM = """You are a performance-marketing strategist matching one
creative-matrix row to ONE specific trending ad mechanic from a curated library
plus, optionally, ONE alternate idea built on the same psychological principle.

Output STRICT JSON only — no markdown fences, no commentary."""


def _format_trending_candidates(candidates: list[dict]) -> str:
    lines: list[str] = []
    for c in candidates:
        bw = c.get("best_when") or {}
        lines.append(
            f"  id: {c.get('id')}\n"
            f"    name: {c.get('name')}\n"
            f"    summary: {(c.get('summary') or '').strip()[:300]}\n"
            f"    format_type: {c.get('format_type', 'both')}\n"
            f"    best_for: awareness={bw.get('awareness_levels', [])}, "
            f"persona_types={bw.get('persona_types', [])}"
        )
    return "\n".join(lines)


def _row_summary_for_trending(row: MatrixRow) -> str:
    anchor = (
        row.complaint
        or row.emotional_trigger
        or row.wished_product
        or row.hook_angle
        or "(unspecified)"
    )
    return (
        f"id: {row.id}\n"
        f"  tab: {row.tab.value}\n"
        f"  anchor: {anchor}\n"
        f"  what_people_say: {row.what_people_say or '—'}\n"
        f"  psychology_trigger: {row.psychology_trigger or '—'}\n"
        f"  format_fit: {row.format_fit}\n"
        f"  static_treatment: {row.static_treatment or '—'}"
    )


def _prefilter_for_row(
    row: MatrixRow,
    formats: list[dict],
    top_n: int = 6,
) -> list[dict]:
    """Cheap pre-filter: score each format by row-feature overlap.

    Reuses the same scoring intent as strategy/trending.py but on row fields
    rather than CreativeBrief fields.
    """
    if not formats:
        return []
    scored: list[tuple[int, int, dict]] = []
    static_friendly_fits = {
        "us-vs-them", "headline", "before-after", "ingredient-callout",
        "screenshot-review", "quote-pull", "meme", "carousel", "editorial",
        "features-benefits", "facts-stats", "media-press", "promotion-discount",
        "ugc-static",
    }
    row_wants_static = bool(row.format_fit) and any(
        f in static_friendly_fits for f in row.format_fit
    )
    row_wants_video = "video-only" in row.format_fit

    for idx, fmt in enumerate(formats):
        score = 0
        ftype = (fmt.get("format_type") or "both").lower()
        if row_wants_video and ftype == "video":
            score += 2
        if row_wants_static and ftype in ("static", "both"):
            score += 2
        # category-level tag overlap (cheap substring match)
        cats = [c.lower() for c in (fmt.get("best_when") or {}).get("product_categories") or []]
        if "any" in cats:
            score += 1
        scored.append((score, idx, fmt))
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [t[2] for t in scored[:top_n]]


def _generate_trending(
    row: MatrixRow,
    formats: list[dict],
    *,
    include_next: bool,
) -> tuple[TrendingMatch | None, TrendingNext | None]:
    candidates = _prefilter_for_row(row, formats, top_n=6)
    if not candidates:
        return None, None

    next_shape = (
        ',\n  "trending_next": {\n'
        '    "idea": "...",\n'
        '    "principle": "ties back to the row\'s psychology_trigger because ...",\n'
        '    "execution": "concrete shoot/render direction"\n'
        "  }"
    ) if include_next else ""

    next_task = (
        "ALSO produce a `trending_next`: a DIFFERENT mechanic built on the "
        "same psychology_trigger."
        if include_next
        else "Do NOT produce trending_next."
    )

    user_prompt = f"""ROW SUMMARY
{_row_summary_for_trending(row)}

CANDIDATE TRENDING FORMATS (pick ONE for trending_match):
{_format_trending_candidates(candidates)}

Tasks:
1. Pick the single best-fit trending format. Set format_id to the candidate's id.
2. Write a concrete `execution` (1-4 sentences) describing what to actually
   shoot or render for THIS row using that mechanic.
3. {next_task}

Output JSON:
{{
  "trending_match": {{
    "concept": "short name of the mechanic",
    "execution": "concrete shoot/render direction",
    "format_id": "<id from candidates>"
  }}{next_shape}
}}"""

    raw = claude_complete(user_prompt, system=_TRENDING_SYSTEM, max_tokens=1024)
    parsed = _parse_json_obj(raw)
    if not parsed:
        return None, None

    match_data = parsed.get("trending_match") or {}
    next_data = parsed.get("trending_next") if include_next else None

    match = None
    if match_data and match_data.get("concept"):
        try:
            match = TrendingMatch(**match_data)
        except Exception:
            match = None

    next_obj = None
    if next_data and next_data.get("idea"):
        try:
            next_obj = TrendingNext(**next_data, generated="eager")
        except Exception:
            next_obj = None

    return match, next_obj


def fill_trending_next_for_row(
    row: MatrixRow,
    formats: list[dict] | None = None,
) -> TrendingNext | None:
    """Lazily generate trending_next for a row that doesn't have one.

    Used by `adc matrix --row <id> --next` to fill the column on demand at
    lean tier (or any time a fresh next-idea is wanted).
    """
    formats = formats or load_trending_formats()
    candidates = _prefilter_for_row(row, formats, top_n=6)
    if not candidates:
        return None

    user_prompt = f"""ROW SUMMARY
{_row_summary_for_trending(row)}

ROW'S PRIMARY TRENDING MATCH (already used — produce something DIFFERENT):
{yaml.safe_dump(row.trending_match.model_dump() if row.trending_match else {}, sort_keys=False)}

CANDIDATE TRENDING FORMATS (the alternate may pick from these or propose
a different mechanic not in the list):
{_format_trending_candidates(candidates)}

Produce a `trending_next`: an idea using a DIFFERENT mechanic than the primary
match, but built on the SAME psychology_trigger ({row.psychology_trigger or "unspecified"}).

Output JSON:
{{
  "trending_next": {{
    "idea": "short name of the alternate mechanic",
    "principle": "why this ties back to the same psychology_trigger",
    "execution": "concrete shoot/render direction"
  }}
}}"""

    raw = claude_complete(user_prompt, system=_TRENDING_SYSTEM, max_tokens=512)
    parsed = _parse_json_obj(raw)
    if not parsed:
        return None
    next_data = parsed.get("trending_next") or {}
    if not next_data.get("idea"):
        return None
    try:
        return TrendingNext(**next_data, generated="lazy")
    except Exception:
        return None


# ─── Top-level builders ─────────────────────────────────────────────────────


def generate_matrix(
    client_slug: str,
    *,
    tier: str = "standard",
    include_trending: bool = True,
) -> CreativeMatrix:
    """Full-build: synthesize all 4 tabs + attach trending matches.

    tier:
      lean      — trending_match only (no trending_next)
      standard  — trending_match + trending_next (eager)
      wide      — same as standard for now; reserved for future 2-alternate mode
    """
    if tier not in ("lean", "standard", "wide"):
        raise ValueError(f"tier must be lean|standard|wide, got '{tier}'")

    brand = load_brand(client_slug)
    brand_context = _load_brand_context(client_slug)
    gaps_data = _load_competitive_gaps(client_slug)
    voc_data = _load_voc_corpus(client_slug)

    if gaps_data is None and voc_data is None:
        raise RuntimeError(
            f"No research found for '{client_slug}'. Run `adc analyze-gaps` "
            f"and/or `adc mine-voc` before building the matrix."
        )

    gaps_block = _gaps_research_block(gaps_data)
    voc_block = _voc_research_block(voc_data)

    pain_rows = _generate_tab(
        MatrixTab.PAIN_VS_COMPETITOR,
        brand=brand,
        brand_context=brand_context,
        gaps_block=gaps_block,
        voc_block=voc_block,
    )
    love_rows = _generate_tab(
        MatrixTab.WHAT_THEY_LOVE,
        brand=brand,
        brand_context=brand_context,
        gaps_block=gaps_block,
        voc_block=voc_block,
    )
    wish_rows = _generate_tab(
        MatrixTab.WISHES_GAPS,
        brand=brand,
        brand_context=brand_context,
        gaps_block=gaps_block,
        voc_block=voc_block,
    )

    prior_block = "\n\n".join([
        _summarize_tab_for_hook_seed(pain_rows, "Tab 1 pain_vs_competitor"),
        _summarize_tab_for_hook_seed(love_rows, "Tab 2 what_they_love"),
        _summarize_tab_for_hook_seed(wish_rows, "Tab 3 wishes_gaps"),
    ])
    hook_rows = _generate_tab(
        MatrixTab.HOOK_ANGLES,
        brand=brand,
        brand_context=brand_context,
        gaps_block=gaps_block,
        voc_block=voc_block,
        prior_tabs_block=prior_block,
    )

    matrix = CreativeMatrix(
        client=client_slug,
        generated_at=datetime.now().isoformat(timespec="seconds"),
        tier=tier,
        research_sources_used=_detect_sources_used(gaps_data, voc_data),
        pain_vs_competitor=pain_rows,
        what_they_love=love_rows,
        wishes_gaps=wish_rows,
        hook_angles=hook_rows,
    )

    if include_trending:
        formats = load_trending_formats()
        include_next = tier in ("standard", "wide")
        for row in matrix.all_rows():
            match, next_obj = _generate_trending(row, formats, include_next=include_next)
            row.trending_match = match
            row.trending_next = next_obj

    return matrix


def regenerate_tab(
    matrix: CreativeMatrix,
    tab: MatrixTab,
    client_slug: str,
    *,
    include_trending: bool = True,
) -> CreativeMatrix:
    """Regenerate one tab in place, preserving the other three."""
    brand = load_brand(client_slug)
    brand_context = _load_brand_context(client_slug)
    gaps_data = _load_competitive_gaps(client_slug)
    voc_data = _load_voc_corpus(client_slug)
    gaps_block = _gaps_research_block(gaps_data)
    voc_block = _voc_research_block(voc_data)

    prior_block = ""
    if tab == MatrixTab.HOOK_ANGLES:
        prior_block = "\n\n".join([
            _summarize_tab_for_hook_seed(matrix.pain_vs_competitor, "Tab 1 pain_vs_competitor"),
            _summarize_tab_for_hook_seed(matrix.what_they_love, "Tab 2 what_they_love"),
            _summarize_tab_for_hook_seed(matrix.wishes_gaps, "Tab 3 wishes_gaps"),
        ])

    new_rows = _generate_tab(
        tab,
        brand=brand,
        brand_context=brand_context,
        gaps_block=gaps_block,
        voc_block=voc_block,
        prior_tabs_block=prior_block,
    )

    if include_trending:
        formats = load_trending_formats()
        include_next = matrix.tier in ("standard", "wide")
        for row in new_rows:
            match, next_obj = _generate_trending(row, formats, include_next=include_next)
            row.trending_match = match
            row.trending_next = next_obj

    setattr(matrix, tab.value, new_rows)
    return matrix


def refresh_all_trending(matrix: CreativeMatrix) -> CreativeMatrix:
    """Re-pull trending matches for every row, keep strategic columns intact."""
    formats = load_trending_formats()
    include_next = matrix.tier in ("standard", "wide")
    for row in matrix.all_rows():
        match, next_obj = _generate_trending(row, formats, include_next=include_next)
        row.trending_match = match
        # Preserve a manually-set trending_next if it exists and we're in lean mode
        if include_next or next_obj is not None:
            row.trending_next = next_obj
    return matrix


# ─── JSON parsing helpers ───────────────────────────────────────────────────


def _strip_fences(text: str) -> str:
    body = text.strip()
    if body.startswith("```"):
        first = body.find("\n")
        if first != -1:
            body = body[first + 1:]
    if body.endswith("```"):
        body = body.rsplit("```", 1)[0].rstrip()
    return body


def _parse_json_obj(text: str) -> dict | None:
    body = _strip_fences(text)
    first = body.find("{")
    last = body.rfind("}")
    if first == -1 or last <= first:
        return None
    candidate = body[first:last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def _parse_json_with_rows(text: str) -> dict | None:
    """Tolerant parse — accepts either {rows: [...]} or a bare [...]."""
    body = _strip_fences(text)
    obj = _parse_json_obj(body)
    if obj is not None and "rows" in obj:
        return obj
    # Maybe the model returned a bare array
    first = body.find("[")
    last = body.rfind("]")
    if first == -1 or last <= first:
        return obj  # fall back to whatever we got
    try:
        arr = json.loads(body[first:last + 1])
        if isinstance(arr, list):
            return {"rows": arr}
    except json.JSONDecodeError:
        pass
    return obj


# ─── Matrix row → CreativeBrief synthesis ───────────────────────────────────
#
# The matrix's job is strategy; image generation is downstream. To bridge the
# two, we synthesize a CreativeBrief from any matrix row so the existing
# `generate_from_brief` pipeline can produce an actual ad without learning
# anything new about matrices.


# Map the 9 canonical heuristics to plausible Schwartz awareness levels. This
# is a heuristic itself — operators can override via `--awareness` at build
# time. Defaults to `problem_aware` for any heuristic not in this table.
_HEURISTIC_TO_AWARENESS: dict[str, AwarenessLevel] = {
    "scarcity": AwarenessLevel.MOST_AWARE,
    "social_proof": AwarenessLevel.SOLUTION_AWARE,
    "authority_bias": AwarenessLevel.SOLUTION_AWARE,
    "effect_heuristic": AwarenessLevel.PROBLEM_AWARE,
    "processing_fluency": AwarenessLevel.PROBLEM_AWARE,
    "temporal_discounting": AwarenessLevel.SOLUTION_AWARE,
    "salience_bias": AwarenessLevel.PROBLEM_AWARE,
    "goal_gradient": AwarenessLevel.PRODUCT_AWARE,
    "framing_effect": AwarenessLevel.SOLUTION_AWARE,
}


# Per-tab framework picks. The matrix's tab dictates the copy structure:
#   pain_vs_competitor → PAS (problem-agitation-solution)
#   what_they_love     → BAB (before-after-bridge)
#   wishes_gaps        → BAB (still showing transformation, but starting from white space)
#   hook_angles        → AIDA (the row IS the hook, so attention-led structure fits)
_TAB_TO_FRAMEWORK: dict[MatrixTab, CopyFramework] = {
    MatrixTab.PAIN_VS_COMPETITOR: CopyFramework.PAS,
    MatrixTab.WHAT_THEY_LOVE: CopyFramework.BAB,
    MatrixTab.WISHES_GAPS: CopyFramework.BAB,
    MatrixTab.HOOK_ANGLES: CopyFramework.AIDA,
}


def _row_angle(row: MatrixRow) -> str:
    """Pick the canonical 'messaging angle' for a row based on its tab."""
    return (
        row.positioning_angle           # Tab 1
        or row.hook_or_angle_to_amplify  # Tab 2
        or row.script_or_static_opportunity  # Tab 3
        or row.hook_angle               # Tab 4
        or "(no angle specified)"
    )


def _row_hook(row: MatrixRow) -> str:
    """Pick the canonical 'scroll-stopping hook' for a row.

    For Tab 4 (hook_angles), the row's `hook_angle` IS the hook. For other
    tabs, fall back to whatever ad-ready short line the row provides.
    """
    candidates = [
        row.hook_angle,                  # Tab 4 — directly a hook line
        row.positioning_angle,           # Tab 1 — ad-ready angle
        row.hook_or_angle_to_amplify,    # Tab 2
        row.script_or_static_opportunity,  # Tab 3
    ]
    for c in candidates:
        if c and c.strip():
            return c.strip()[:240]  # CreativeBrief hooks are short
    return "Stop scrolling."


def _row_pain_point(row: MatrixRow) -> str:
    """Pick the underlying pain/desire that this row addresses."""
    return (
        row.complaint                # Tab 1
        or row.real_frustration      # Tab 3
        or row.emotional_trigger     # Tab 2
        or row.wished_product        # Tab 3 (different angle)
        or ""
    )


def row_to_brief(
    row: MatrixRow,
    client_slug: str,
    product: Product,
    avatar: CustomerAvatar | None = None,
    *,
    brief_id_prefix: str = "matrix",
) -> CreativeBrief:
    """Synthesize a CreativeBrief from a single matrix row.

    The resulting brief is shaped so the existing `generators.image_generator`
    pipeline (specifically `generate_from_brief`) can consume it without any
    matrix awareness. Field mapping:

      row.positioning_angle / hook_or_angle / etc. → brief.angle
      row.hook_angle (Tab 4) or fallback           → brief.hook
      row.tactic (Tab 4)                            → brief.hook_tactic
      row.format_fit[0]                             → brief.visual_format
      row.format_fit[1:]                            → brief.visual_format_alternatives
      row.static_treatment                          → brief.visual_direction
      row.complaint / real_frustration / etc.       → brief.pain_point
      row.our_advantage                             → brief.body_copy
      row.psychology_trigger → awareness            (via _HEURISTIC_TO_AWARENESS)
      row.tab → copy framework                      (via _TAB_TO_FRAMEWORK)

    The `source_insight` field is set to `creative_matrix:<tab>:<row.id>` so
    every downstream artifact (naming, logs, the brief YAML itself) traces
    back to the originating matrix row.
    """
    awareness = _HEURISTIC_TO_AWARENESS.get(
        row.psychology_trigger or "", AwarenessLevel.PROBLEM_AWARE
    )
    framework = _TAB_TO_FRAMEWORK.get(row.tab, CopyFramework.PAS)

    visual_format = row.format_fit[0] if row.format_fit else ""
    visual_format_alts = list(row.format_fit[1:]) if len(row.format_fit) > 1 else []

    benefit_callouts: list[str] = []
    if row.our_advantage:
        # Split our_advantage on full stops to surface up to 3 benefit beats.
        chunks = [c.strip() for c in re.split(r"\.\s+", row.our_advantage) if c.strip()]
        benefit_callouts = chunks[:3]

    return CreativeBrief(
        brief_id=f"{brief_id_prefix}-{row.id}",
        client=client_slug,
        product=product.name,
        awareness_level=awareness,
        framework=framework,
        angle=_row_angle(row),
        hook=_row_hook(row),
        hook_type=row.tactic if row.tab == MatrixTab.HOOK_ANGLES else "",
        hook_tactic=row.tactic or "",
        hook_source=f"matrix:{row.tab.value}:{row.id}",
        persona=avatar.name if avatar else "",
        persona_traits=(avatar.demographic if avatar else "") or "",
        pain_point=_row_pain_point(row),
        benefit_callouts=benefit_callouts,
        body_copy=row.our_advantage or row.hook_or_angle_to_amplify or "",
        visual_format=visual_format,
        visual_format_alternatives=visual_format_alts,
        visual_direction=row.static_treatment or "",
        source_insight=f"creative_matrix:{row.tab.value}:{row.id}",
    )
