"""Competitive gap analysis.

Reads cached competitive research (Exa + on-site reviews) and produces
a structured "gap map" per the framework:
    5-star equivalent -> what customers love (table stakes)
    3-star equivalent -> what falls short (GAPS - creative gold)
    1-star equivalent -> dealbreakers (switching opportunities)

Then a cross-competitor synthesis surfaces white space for our brand to occupy.

Output:
    clients/<slug>/research/competitive-gaps.yaml    (machine-readable)
    clients/<slug>/research/competitive-gaps.md      (human-readable summary)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.skills import load_skill
from strategy.apify_amazon import AmazonReviewBundle, load_cached_amazon_bundles
from strategy.competitor_research import (
    Competitor,
    CompetitorReviewBundle,
    load_cached_competitor_bundles,
    load_competitors,
)
from strategy.exa_research import ExaQueryResult, load_cached
from strategy.llm import claude_complete

CLIENTS_DIR = Path("clients")
MAX_EXA_CHARS_PER_BRAND = 80_000        # token budget per per-brand Claude call
MAX_REVIEWS_PER_BRAND = 80              # cap on-site reviews to avoid blowing context


GAP_ANALYST_SYSTEM = """You are a competitive strategist for direct-response advertising.

Your job is to read raw customer voice (reviews, Reddit threads, news, third-party
discussions) about ONE brand and stratify it into three buckets matching the
5-star / 3-star / 1-star review framework:

    LOVES (5-star equivalent):
      What customers consistently rave about. Table stakes — our brand must match
      or beat this to compete. Note: these are widely positive and emotionally
      charged.

    GAPS (3-star equivalent):
      What customers WISH was different. The "I almost loved it but..." tier.
      Look for: "I wish...", "would be perfect if...", "the only downside...",
      "if only it had...". These are CREATIVE GOLD because they're unmet needs
      our brand can address head-on.

    DEALBREAKERS (1-star equivalent):
      What made customers quit, refund, never buy again. Hard objections,
      side effects, broken trust. These are SWITCHING OPPORTUNITIES — when
      a customer leaves Brand X over issue Y, we want to be the answer.

For each insight extracted, you MUST include:
- A specific money quote (verbatim, with surrounding context)
- A confidence level (high/medium/low) based on how many independent sources mention it
- The source domain or type (reddit / brand-onsite / news / trustpilot)

CONFIDENCE SCORING:
  high   - mentioned by 3+ independent sources, consistent language
  medium - mentioned by 2 sources, or strong but single-source
  low    - single mention, could be outlier

SAMPLE BIAS: online reviewers skew toward strong opinions. Note when a "gap" might
be a vocal-minority issue vs a category-defining one.

Output valid YAML only, no markdown fences.

--- CUSTOMER RESEARCH SKILL ---

""" + load_skill("customer-research") + """
"""


SYNTHESIS_SYSTEM = """You are a competitive strategist synthesizing gap analyses
across multiple competitors to find white-space opportunities for OUR brand.

You will be given:
    1. Per-competitor gap maps (loves / gaps / dealbreakers)
    2. Our brand's positioning and differentiators

Your job is to find:

    CATEGORY TABLE STAKES — what every successful competitor delivers; our brand
    must match to be considered. Don't waste creative on these as differentiators.

    EXPLOITABLE GAPS — places where one or more competitors FALL SHORT in ways
    our brand can solve. Each opportunity must include:
      - Which competitor(s) fail at this
      - Specific customer language showing the failure
      - Our brand's advantage / proof point
      - An ad angle direction (1-2 sentence creative direction)

    SHARED DEALBREAKERS — issues that hit MULTIPLE competitors. These are
    category-wide vulnerabilities. If our brand avoids them, lead with it.

    DEFENSIVE PRIORITIES — issues hitting OUR brand that also hit competitors
    (so customers won't see us as worse, but we should pre-empt the objection).

Be specific. Quote real customer language. Don't make up advantages.

Output VALID JSON only, no markdown fences, no commentary before or after.
Use double-quoted strings. Escape any internal quotes with backslash."""


def _gather_brand_content(
    brand_name: str,
    exa_results: list[ExaQueryResult],
    on_site_bundle: CompetitorReviewBundle | None = None,
    amazon_bundles: list[AmazonReviewBundle] | None = None,
    is_own_brand: bool = False,
) -> tuple[str, dict]:
    """Concatenate every piece of customer voice we have about one brand into a
    single context string, plus a metadata dict. Returns (content, meta)."""
    parts: list[str] = []
    meta = {
        "exa_hits": 0,
        "reddit_hits": 0,
        "news_hits": 0,
        "trustpilot_hits": 0,
        "on_site_reviews": 0,
        "amazon_reviews": 0,
        "total_chars": 0,
        "sources": set(),
    }

    brand_slug = re.sub(r"[^a-zA-Z0-9]+", "-", brand_name.lower()).strip("-")

    # Pull Exa results that match this brand (by label prefix)
    for r in exa_results:
        label = r.query.label.lower()
        if brand_slug not in label:
            continue
        for hit in r.results:
            if not hit.text or len(hit.text.strip()) < 100:
                continue
            parts.append(
                f"--- {r.query.category.upper()} | {hit.domain} | {hit.title} ---\n"
                f"URL: {hit.url}\n"
                f"{hit.text.strip()}\n"
            )
            meta["exa_hits"] += 1
            if "reddit" in hit.domain:
                meta["reddit_hits"] += 1
            elif "trustpilot" in hit.domain:
                meta["trustpilot_hits"] += 1
            else:
                meta["news_hits"] += 1
            meta["sources"].add(hit.domain)

    # Add on-site reviews if available
    if on_site_bundle and on_site_bundle.reviews:
        reviews_text = [
            f"--- ON-SITE REVIEW | rating={rv.rating} | {rv.product_name or 'unknown'} ---\n"
            f"Title: {rv.title}\n"
            f"Body: {rv.body}\n"
            for rv in on_site_bundle.reviews[:MAX_REVIEWS_PER_BRAND]
        ]
        parts.append("\n".join(reviews_text))
        meta["on_site_reviews"] = min(len(on_site_bundle.reviews), MAX_REVIEWS_PER_BRAND)
        meta["sources"].add(f"{on_site_bundle.vendor}-onsite")

    # Add Amazon reviews if available — these are typically the highest-volume
    # AND star-stratified source. Sample evenly across ratings so 5/3/1 are
    # all represented even when totals are uneven.
    if amazon_bundles:
        all_amazon_reviews: list = []
        for bundle in amazon_bundles:
            all_amazon_reviews.extend(bundle.reviews)
        if all_amazon_reviews:
            # Stratified sample: prioritize 1, 3, 5 stars (the user's framework)
            by_rating: dict[int, list] = {1: [], 2: [], 3: [], 4: [], 5: [], 0: []}
            for rv in all_amazon_reviews:
                by_rating.setdefault(rv.rating, []).append(rv)
            # Take up to N from each priority tier
            tier_budget = MAX_REVIEWS_PER_BRAND // 3
            sampled = (
                by_rating[5][:tier_budget]
                + by_rating[3][:tier_budget]
                + by_rating[1][:tier_budget]
            )
            # Fill remaining budget with 4s and 2s if we have room
            remaining = MAX_REVIEWS_PER_BRAND - len(sampled)
            if remaining > 0:
                sampled += by_rating[4][:remaining // 2] + by_rating[2][:remaining // 2]
            reviews_text = [
                f"--- AMAZON REVIEW | rating={rv.rating}/5 | {rv.product_name[:80]} | "
                f"reviewer={rv.reviewer or 'anon'} ---\n"
                f"Title: {rv.title}\n"
                f"Body: {rv.body}\n"
                for rv in sampled
            ]
            parts.append("\n".join(reviews_text))
            meta["amazon_reviews"] = len(sampled)
            meta["sources"].add("amazon")

    content = "\n\n".join(parts)

    # Truncate hard if too long (rare, but defensive)
    if len(content) > MAX_EXA_CHARS_PER_BRAND:
        content = content[:MAX_EXA_CHARS_PER_BRAND] + "\n\n[TRUNCATED]"

    meta["total_chars"] = len(content)
    meta["sources"] = sorted(meta["sources"])
    return content, meta


def analyze_one_brand(
    brand_name: str,
    is_own_brand: bool,
    exa_results: list[ExaQueryResult],
    on_site_bundle: CompetitorReviewBundle | None,
    amazon_bundles: list[AmazonReviewBundle] | None = None,
) -> dict:
    """One Claude call: produce a gap map for one brand."""
    content, meta = _gather_brand_content(
        brand_name, exa_results, on_site_bundle, amazon_bundles, is_own_brand
    )

    if not content.strip():
        return {
            "brand": brand_name,
            "is_own_brand": is_own_brand,
            "error": "No usable content collected",
            "meta": meta,
        }

    role = "OUR brand" if is_own_brand else "a competitor brand"
    prompt = (
        f"Analyze the following customer voice content about {role} named '{brand_name}'.\n\n"
        f"Stratify findings into LOVES (5-star equivalent), GAPS (3-star), DEALBREAKERS (1-star).\n\n"
        f"Return YAML matching this exact schema:\n\n"
        f"brand: \"{brand_name}\"\n"
        f"loves:\n"
        f"  - claim: \"what they love (short, specific)\"\n"
        f"    confidence: \"high/medium/low\"\n"
        f"    money_quote: \"verbatim customer quote\"\n"
        f"    sources: [\"domain or source\"]\n"
        f"gaps:\n"
        f"  - gap: \"what falls short / what's missing / what they wish was different\"\n"
        f"    confidence: \"high/medium/low\"\n"
        f"    money_quote: \"verbatim quote showing the gap\"\n"
        f"    sources: [\"domain or source\"]\n"
        f"dealbreakers:\n"
        f"  - issue: \"hard objection / why they quit\"\n"
        f"    confidence: \"high/medium/low\"\n"
        f"    money_quote: \"verbatim quote\"\n"
        f"    sources: [\"domain or source\"]\n"
        f"summary: \"2-3 sentences capturing the brand's customer perception\"\n\n"
        f"--- CUSTOMER VOICE CONTENT ---\n\n{content}\n"
    )

    raw = claude_complete(
        prompt=prompt,
        system=GAP_ANALYST_SYSTEM,
        max_tokens=4096,
    )

    parsed = _parse_yaml_response(raw)
    if not isinstance(parsed, dict):
        parsed = {"brand": brand_name, "error": "Parse failure", "raw": raw[:1000]}

    parsed["is_own_brand"] = is_own_brand
    parsed["meta"] = meta
    return parsed


def synthesize_gaps(
    own_brand: str,
    own_brand_analysis: dict,
    competitor_analyses: list[dict],
    brand_context: str = "",
) -> dict:
    """Cross-competitor synthesis: identify white space for our brand."""
    competitor_section = "\n\n".join(
        f"=== {a.get('brand', 'unknown')} ===\n{yaml.safe_dump(a, sort_keys=False)}"
        for a in competitor_analyses
    )
    own_section = yaml.safe_dump(own_brand_analysis, sort_keys=False)

    prompt = (
        f"Synthesize the following per-brand gap maps into a competitive opportunity map for {own_brand}.\n\n"
        f"=== OUR BRAND ({own_brand}) ===\n{own_section}\n\n"
        f"=== COMPETITORS ===\n{competitor_section}\n\n"
        + (f"=== OUR BRAND CONTEXT ===\n{brand_context}\n\n" if brand_context else "")
        + "Return JSON matching this exact shape (no markdown, no commentary):\n\n"
        "{\n"
        '  "category_table_stakes": [\n'
        '    {"feature": "what every competitor delivers", "why_critical": "..."}\n'
        "  ],\n"
        '  "exploitable_gaps": [\n'
        "    {\n"
        '      "opportunity": "the gap we can fill",\n'
        '      "competitors_failing": ["poppi", "culture-pop"],\n'
        '      "customer_evidence": "verbatim quote showing the gap",\n'
        f'      "our_advantage": "what {own_brand} has that solves this",\n'
        '      "ad_angle": "1-2 sentence creative direction"\n'
        "    }\n"
        "  ],\n"
        '  "shared_dealbreakers": [\n'
        "    {\n"
        '      "issue": "category-wide vulnerability",\n'
        '      "affected_competitors": ["poppi", "health-ade"],\n'
        '      "our_response": "how we avoid or counter this"\n'
        "    }\n"
        "  ],\n"
        '  "defensive_priorities": [\n'
        "    {\n"
        '      "objection": "objection hitting us too",\n'
        '      "also_hits": ["competitor1"],\n'
        '      "pre_empt": "how to address before they bring it up"\n'
        "    }\n"
        "  ],\n"
        f'  "summary": "2-3 sentence read of where {own_brand} can win"\n'
        "}\n\n"
        "Include 4-7 exploitable_gaps, 2-4 shared_dealbreakers, 2-4 defensive_priorities."
    )

    raw = claude_complete(
        prompt=prompt,
        system=SYNTHESIS_SYSTEM,
        max_tokens=8192,
    )

    parsed = _parse_json_response(raw)
    if not isinstance(parsed, dict):
        # Fall back to YAML parser in case Claude ignored the JSON instruction
        parsed = _parse_yaml_response(raw)
    if not isinstance(parsed, dict):
        parsed = {"error": "Parse failure", "raw": raw}
    return parsed


def _parse_json_response(raw: str) -> dict | list | None:
    """Pull JSON out of a Claude response. Handles fenced code blocks and
    leading/trailing commentary."""
    if not raw:
        return None
    text = raw.strip()
    # Strip markdown fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    # Locate the first `{` and last `}` — anything outside is commentary
    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = text[first:last + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        # Try removing trailing commas (common LLM mistake)
        cleaned = re.sub(r",(\s*[}\]])", r"\1", candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return None


def analyze_competitive_gaps(
    client_slug: str,
    brand_name: str,
    synthesis_only: bool = False,
) -> dict:
    """End-to-end gap analysis: per-brand passes + cross-competitor synthesis.

    If synthesis_only=True, loads existing per-brand analyses from the cached
    YAML and re-runs only the synthesis pass. Useful for recovering from a
    parse failure without re-paying for per-brand work.

    Returns a dict with `per_brand`, `synthesis`, and `meta`.
    Also writes:
      clients/<slug>/research/competitive-gaps.yaml
      clients/<slug>/research/competitive-gaps.md
    """
    exa_results = load_cached(client_slug)
    on_site_bundles = load_cached_competitor_bundles(client_slug)
    on_site_by_slug = {b.competitor.slug: b for b in on_site_bundles}
    amazon_bundles = load_cached_amazon_bundles(client_slug)
    amazon_by_slug: dict[str, list[AmazonReviewBundle]] = {}
    for ab in amazon_bundles:
        amazon_by_slug.setdefault(ab.competitor_slug, []).append(ab)
    competitors = load_competitors(client_slug)

    if not exa_results and not on_site_bundles and not amazon_bundles:
        raise RuntimeError(
            f"No cached research found for {client_slug}. "
            f"Run `adc research-competitors --client {client_slug}` first."
        )

    if synthesis_only:
        existing_path = CLIENTS_DIR / client_slug / "research" / "competitive-gaps.yaml"
        if not existing_path.exists():
            raise RuntimeError(
                "No existing competitive-gaps.yaml to re-synthesize from. "
                "Run without --synthesis-only first."
            )
        existing = yaml.safe_load(existing_path.read_text(encoding="utf-8")) or {}
        own_analysis = existing.get("per_brand", {}).get("own", {})
        competitor_analyses = existing.get("per_brand", {}).get("competitors", [])
        if not own_analysis or not competitor_analyses:
            raise RuntimeError(
                "Existing competitive-gaps.yaml is missing per-brand analyses. "
                "Run a full analyze-gaps first."
            )
    else:
        # Per-brand passes
        own_analysis = analyze_one_brand(
            brand_name=brand_name,
            is_own_brand=True,
            exa_results=exa_results,
            on_site_bundle=None,
            amazon_bundles=amazon_by_slug.get(_slugify_for_match(brand_name)),
        )

        competitor_analyses = []
        for c in competitors:
            analysis = analyze_one_brand(
                brand_name=c.name,
                is_own_brand=False,
                exa_results=exa_results,
                on_site_bundle=on_site_by_slug.get(c.slug),
                amazon_bundles=amazon_by_slug.get(c.slug),
            )
            competitor_analyses.append(analysis)

    # Load brand context for synthesis
    brand_ctx_path = CLIENTS_DIR / client_slug / "brand-context.md"
    brand_context = brand_ctx_path.read_text(encoding="utf-8") if brand_ctx_path.exists() else ""
    # Cap brand context to first 6000 chars so synthesis prompt isn't blown out
    brand_context = brand_context[:6000]

    synthesis = synthesize_gaps(
        own_brand=brand_name,
        own_brand_analysis=own_analysis,
        competitor_analyses=competitor_analyses,
        brand_context=brand_context,
    )

    output = {
        "own_brand": brand_name,
        "per_brand": {
            "own": own_analysis,
            "competitors": competitor_analyses,
        },
        "synthesis": synthesis,
    }

    # Persist
    research_dir = CLIENTS_DIR / client_slug / "research"
    research_dir.mkdir(parents=True, exist_ok=True)
    yaml_path = research_dir / "competitive-gaps.yaml"
    md_path = research_dir / "competitive-gaps.md"
    yaml_path.write_text(yaml.safe_dump(output, sort_keys=False, allow_unicode=True), encoding="utf-8")
    md_path.write_text(_render_markdown(output), encoding="utf-8")

    return output


def _slugify_for_match(text: str) -> str:
    """Slugify a brand name for matching to competitor slugs (own-brand Amazon lookup)."""
    return re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")


def _parse_yaml_response(raw: str) -> dict | list | None:
    """Strip fences and try to parse YAML safely.

    Falls back: if full parse fails, walk back from the end one line at a time
    until we find a parseable prefix. This recovers from mid-stream Claude
    output issues (e.g., a quote that didn't close in the final section).
    """
    if not raw:
        return None
    text = raw.strip()
    # Strip any markdown fence
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    # Strip any "Here is the YAML:" or similar preamble — find first top-level key
    m = re.search(r"(?m)^([a-z_][a-z0-9_]*:)", text)
    if m and m.start() > 0:
        text = text[m.start():]

    try:
        return yaml.safe_load(text)
    except Exception:
        pass

    # Fallback: progressively truncate from the end, line by line
    lines = text.split("\n")
    for cutoff in range(len(lines) - 1, 0, -1):
        candidate = "\n".join(lines[:cutoff])
        try:
            parsed = yaml.safe_load(candidate)
            if isinstance(parsed, dict) and parsed:
                return parsed
        except Exception:
            continue
    return None


def _render_markdown(output: dict) -> str:
    """Human-readable summary for quick browsing."""
    lines: list[str] = []
    own = output.get("own_brand", "")
    lines.append(f"# Competitive Gap Map — {own}\n")
    syn = output.get("synthesis", {})

    if syn.get("summary"):
        lines.append(f"**TL;DR:** {syn['summary']}\n")

    if syn.get("exploitable_gaps"):
        lines.append("## Exploitable Gaps\n")
        for g in syn["exploitable_gaps"]:
            lines.append(f"### {g.get('opportunity', '')}")
            comps = ", ".join(g.get("competitors_failing", []))
            lines.append(f"- **Competitors failing:** {comps}")
            ev = g.get("customer_evidence", "")
            if ev:
                lines.append(f"- **Evidence:** \"{ev}\"")
            lines.append(f"- **Our advantage:** {g.get('our_advantage', '')}")
            lines.append(f"- **Ad angle:** {g.get('ad_angle', '')}\n")

    if syn.get("shared_dealbreakers"):
        lines.append("## Shared Dealbreakers (Category Vulnerabilities)\n")
        for d in syn["shared_dealbreakers"]:
            lines.append(f"- **{d.get('issue', '')}** — affects: {', '.join(d.get('affected_competitors', []))}")
            lines.append(f"  - Our response: {d.get('our_response', '')}\n")

    if syn.get("defensive_priorities"):
        lines.append("## Defensive Priorities (Objections That Hit Us Too)\n")
        for p in syn["defensive_priorities"]:
            lines.append(f"- **{p.get('objection', '')}** — pre-empt: {p.get('pre_empt', '')}\n")

    if syn.get("category_table_stakes"):
        lines.append("## Category Table Stakes\n")
        for t in syn["category_table_stakes"]:
            lines.append(f"- **{t.get('feature', '')}** — {t.get('why_critical', '')}\n")

    # Per-brand summaries
    lines.append("\n---\n\n## Per-Brand Analyses\n")
    own_analysis = output.get("per_brand", {}).get("own", {})
    competitor_analyses = output.get("per_brand", {}).get("competitors", [])
    for analysis in [own_analysis] + competitor_analyses:
        brand = analysis.get("brand", "?")
        is_own = analysis.get("is_own_brand", False)
        tag = " (OUR BRAND)" if is_own else ""
        lines.append(f"\n### {brand}{tag}\n")
        if analysis.get("summary"):
            lines.append(f"_{analysis['summary']}_\n")

        for bucket_name, key in [("Loves", "loves"), ("Gaps", "gaps"), ("Dealbreakers", "dealbreakers")]:
            items = analysis.get(key, []) or []
            if not items:
                continue
            lines.append(f"**{bucket_name}:**")
            for item in items[:5]:
                claim = item.get("claim") or item.get("gap") or item.get("issue") or ""
                conf = item.get("confidence", "")
                quote = item.get("money_quote", "")
                lines.append(f"- {claim} _({conf})_")
                if quote:
                    lines.append(f"  > \"{quote}\"")
            lines.append("")

    return "\n".join(lines)
