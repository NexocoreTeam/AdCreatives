"""Client status dashboard — pure local file inspection.

Reads the filesystem under clients/<slug>/ and ai-ads/<slug>/ and produces a
checklist view of:

    1. Strategy stages (brand research, personas, products, offers, matrix, psychology)
    2. Competitive research (Exa, on-site reviews, Amazon, gap map)
    3. Ad assets (briefs, prompts, generated images)
    4. Recency warnings (anything stale)
    5. Recommendations (what to run next)

No API calls. No LLM. Runs in under a second.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import yaml

from strategy.exa_queries import cache_stem, competitive_queries_for_brand

CLIENTS_DIR = Path("clients")
AI_ADS_DIR = Path("ai-ads")

STALE_THRESHOLD_DAYS = 14   # anything older than this triggers a "consider refresh" hint


@dataclass
class StageStatus:
    """One stage's status — shown as a row in the dashboard."""
    name: str
    done: bool = False
    summary: str = ""           # e.g., "3 personas", "12 briefs"
    last_modified: Optional[datetime] = None
    notes: list[str] = field(default_factory=list)
    counts: dict = field(default_factory=dict)  # structured numbers for the recommendation engine

    @property
    def age_days(self) -> Optional[int]:
        if not self.last_modified:
            return None
        return (datetime.now() - self.last_modified).days


def _mtime(path: Path) -> Optional[datetime]:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime)


def _newest_mtime(paths: list[Path]) -> Optional[datetime]:
    candidates = [_mtime(p) for p in paths if p.exists()]
    candidates = [c for c in candidates if c is not None]
    return max(candidates) if candidates else None


def _safe_yaml_load(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_json_load(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _is_unmodified_template_copy(path: Path) -> bool:
    """True when a client file is byte-identical to its _template original."""
    template = CLIENTS_DIR / "_template" / path.name
    try:
        return template.exists() and path.read_bytes() == template.read_bytes()
    except OSError:
        return False


def _cost_log_entries(client: str) -> list[dict]:
    path = CLIENTS_DIR / client / ".cost-log.jsonl"
    if not path.exists():
        return []
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


def _last_cost_log_entry(client: str, command: str) -> Optional[dict]:
    matches = [e for e in _cost_log_entries(client) if e.get("command") == command]
    return matches[-1] if matches else None


def _expected_competitive_exa_stems(client: str) -> list[str]:
    """Expected cache-file stems for `adc research-competitors`.

    Computed from the SAME planning code the research command runs
    (strategy.exa_queries — pure, no SDK import), so the plan and the
    dashboard can never drift.
    """
    brand_path = CLIENTS_DIR / client / "brand.yaml"
    competitors_path = CLIENTS_DIR / client / "competitors.yaml"
    brand_data = _safe_yaml_load(brand_path) or {}
    competitor_data = _safe_yaml_load(competitors_path) or {}
    brand_name = brand_data.get("name") or brand_data.get("brand_name") or client
    competitor_names = [
        c.get("name", "")
        for c in (competitor_data.get("competitors") or [])
        if c.get("name")
    ]
    queries = competitive_queries_for_brand(
        own_brand=brand_name, competitor_names=competitor_names
    )
    return [cache_stem(q.label) for q in queries]


# ─── Section 1: Strategy stages ──────────────────────────────────────────────


def strategy_status(client: str) -> list[StageStatus]:
    """Status of the strategy layer: research, personas, products, offers, matrix, psychology."""
    base = CLIENTS_DIR / client
    stages: list[StageStatus] = []

    # Brand research
    brand_path = base / "brand.yaml"
    context_path = base / "brand-context.md"
    stages.append(StageStatus(
        name="Brand research",
        done=brand_path.exists() and context_path.exists(),
        summary="brand.yaml + brand-context.md" if brand_path.exists() else "",
        last_modified=_newest_mtime([brand_path, context_path]),
    ))

    # Personas
    personas_dir = base / "avatars"
    persona_files = sorted(p for p in personas_dir.glob("*.yaml")) if personas_dir.exists() else []
    persona_files = [p for p in persona_files if p.name != "_index.yaml"]
    legacy_avatar = base / "avatar.yaml"
    persona_count = len(persona_files)
    # init-client copies the template wholesale, so a byte-identical
    # avatar.yaml is the shipped EXAMPLE, not a persona — counting it made a
    # freshly-initialized client show "Personas OK" (found live on the
    # expand-furniture kickoff).
    has_legacy = (
        legacy_avatar.exists()
        and persona_count == 0
        and not _is_unmodified_template_copy(legacy_avatar)
    )
    stages.append(StageStatus(
        name="Personas",
        done=persona_count > 0 or has_legacy,
        summary=f"{persona_count} persona(s)" if persona_count else ("legacy avatar.yaml" if has_legacy else ""),
        last_modified=_newest_mtime(persona_files + [legacy_avatar]),
    ))

    # Products
    products_dir = base / "products"
    product_files = sorted(products_dir.glob("*.yaml")) if products_dir.exists() else []
    # Exclude template product if present
    product_files = [p for p in product_files if p.name != "example-product.yaml"]
    enriched_count = 0
    for p in product_files:
        data = _safe_yaml_load(p)
        enrichment_fields = (
            "product_characteristics",
            "on_page_reviews",
            "unique_mechanism",
            "benefits",
            "objections",
            "social_proof",
            "claims",
            "offers",
            "use_cases",
        )
        if data and any(data.get(field) for field in enrichment_fields):
            enriched_count += 1
    pcount = len(product_files)
    stages.append(StageStatus(
        name="Products",
        done=pcount > 0,
        summary=(
            f"{pcount} product(s)"
            + (f", {enriched_count} enriched" if pcount else "")
        ),
        last_modified=_newest_mtime(product_files),
        counts={"products": pcount, "enriched": enriched_count},
    ))

    # Catalog census — full-SKU crawl + problem clusters (optional layer)
    catalog_path = base / "products" / "catalog.yaml"
    catalog_data = _safe_yaml_load(catalog_path) if catalog_path.exists() else None
    stages.append(StageStatus(
        name="Catalog census",
        done=bool(catalog_data),
        summary=(
            f"{len(catalog_data.get('products') or [])} product(s), "
            f"{len(catalog_data.get('clusters') or [])} cluster(s)"
            if catalog_data else ""
        ),
        last_modified=_mtime(catalog_path),
    ))

    # Offers
    offers_path = base / "offers.yaml"
    stages.append(StageStatus(
        name="Offers",
        done=offers_path.exists(),
        summary="offers.yaml" if offers_path.exists() else "",
        last_modified=_mtime(offers_path),
    ))

    # Strategy matrix
    matrix_yaml = base / "strategy-matrix.yaml"
    matrix_md = base / "strategy-matrix.md"
    stages.append(StageStatus(
        name="Strategy matrix",
        done=matrix_yaml.exists() or matrix_md.exists(),
        summary="strategy-matrix.yaml" if matrix_yaml.exists() else "",
        last_modified=_newest_mtime([matrix_yaml, matrix_md]),
    ))

    # Psychology profiles — count how many avatars have psychology_profile set
    profiled = 0
    for p in persona_files:
        data = _safe_yaml_load(p)
        if data and data.get("psychology_profile"):
            profiled += 1
    if has_legacy:
        # legacy avatar — check it too
        data = _safe_yaml_load(legacy_avatar)
        if data and data.get("psychology_profile"):
            profiled = 1
    total_avatars = persona_count if persona_count else (1 if has_legacy else 0)
    stages.append(StageStatus(
        name="Psychology profiles",
        done=profiled > 0,
        summary=(
            f"{profiled}/{total_avatars} avatar(s) profiled" if total_avatars else "no avatars"
        ),
        last_modified=_newest_mtime(persona_files + [legacy_avatar]),
    ))

    return stages


# ─── Section 2: Competitive research ─────────────────────────────────────────


def competitive_research_status(client: str) -> list[StageStatus]:
    """Status of competitive research: competitors list, Exa, on-site, Amazon, gap map."""
    base = CLIENTS_DIR / client / "research"
    stages: list[StageStatus] = []

    # Competitors list
    competitors_path = CLIENTS_DIR / client / "competitors.yaml"
    comp_count = 0
    has_amazon_urls = False
    if competitors_path.exists():
        data = _safe_yaml_load(competitors_path)
        if data and isinstance(data.get("competitors"), list):
            comp_count = len(data["competitors"])
            has_amazon_urls = any(c.get("amazon_urls") for c in data["competitors"])
    stages.append(StageStatus(
        name="Competitors list",
        done=comp_count > 0,
        summary=(
            f"{comp_count} competitor(s)"
            + (" (with Amazon URLs)" if has_amazon_urls else " (no Amazon URLs)")
        ) if comp_count else "",
        last_modified=_mtime(competitors_path),
        counts={"competitors": comp_count, "with_amazon_urls": int(has_amazon_urls)},
    ))

    # Exa research
    exa_dir = base / "exa" / "raw"
    exa_files = sorted(exa_dir.glob("*.json")) if exa_dir.exists() else []
    total_hits = 0
    for f in exa_files:
        data = _safe_json_load(f)
        if data:
            total_hits += len(data.get("results", []) or [])
    expected_exa_stems = _expected_competitive_exa_stems(client)
    existing_exa_stems = {p.stem for p in exa_files}
    missing_exa_stems = [
        stem for stem in expected_exa_stems
        if stem not in existing_exa_stems
    ]
    error_dir = base / "exa" / "errors"
    error_files = sorted(error_dir.glob("*.json")) if error_dir.exists() else []
    exa_notes: list[str] = []
    # Only flag missing caches for PARTIAL runs — a never-run stage is already
    # communicated by done=False, and "missing 30 caches" there is just noise.
    if exa_files and expected_exa_stems and missing_exa_stems:
        missing_reddit = [m for m in missing_exa_stems if m.startswith("reddit-")]
        if len(missing_reddit) == len(missing_exa_stems):
            exa_notes.append(
                "Reddit Exa query caches are missing; the web sentiment run is partial"
            )
        else:
            preview = ", ".join(missing_exa_stems[:3])
            more = f" (+{len(missing_exa_stems) - 3} more)" if len(missing_exa_stems) > 3 else ""
            exa_notes.append(f"missing expected Exa cache(s): {preview}{more}")
    if error_files:
        exa_notes.append(
            f"{len(error_files)} failed query record(s) under research/exa/errors/"
        )
    stages.append(StageStatus(
        name="Exa web sentiment",
        done=len(exa_files) > 0,
        summary=(
            f"{len(exa_files)}/{len(expected_exa_stems)} queries, {total_hits} hits"
            if exa_files and expected_exa_stems
            else (f"{len(exa_files)} queries, {total_hits} hits" if exa_files else "")
        ),
        last_modified=_newest_mtime(exa_files),
        notes=exa_notes,
        counts={
            "queries_cached": len(exa_files),
            "queries_expected": len(expected_exa_stems),
            "queries_failed": len(error_files),
            "hits": total_hits,
        },
    ))

    # On-site competitor reviews
    onsite_dir = base / "competitor-reviews"
    onsite_files = sorted(onsite_dir.glob("*.json")) if onsite_dir.exists() else []
    onsite_review_count = 0
    for f in onsite_files:
        data = _safe_json_load(f)
        if data:
            onsite_review_count += len(data.get("reviews", []) or [])
    stages.append(StageStatus(
        name="On-site competitor reviews",
        done=onsite_review_count > 0,
        summary=(
            f"{len(onsite_files)} competitor(s), {onsite_review_count} review(s)"
            if onsite_files else ""
        ),
        last_modified=_newest_mtime(onsite_files),
        notes=(
            ["review scrape produced files but no reviews; add better review sources or use Exa/Amazon/social"]
            if onsite_files and onsite_review_count == 0 else []
        ),
    ))

    # Amazon reviews — stratified
    amazon_dir = base / "amazon-reviews"
    amazon_files = sorted(amazon_dir.glob("*.json")) if amazon_dir.exists() else []
    amazon_review_count = 0
    by_star: dict[str, int] = {"5s": 0, "4s": 0, "3s": 0, "2s": 0, "1s": 0, "all": 0}
    for f in amazon_files:
        data = _safe_json_load(f)
        if data:
            n = len(data.get("reviews", []) or [])
            amazon_review_count += n
            star = data.get("star_filter", "all_stars")
            short_map = {
                "five_star": "5s", "four_star": "4s", "three_star": "3s",
                "two_star": "2s", "one_star": "1s", "all_stars": "all",
            }
            by_star[short_map.get(star, "all")] += n
    stratified = sum(by_star[k] for k in ("5s", "3s", "1s")) > 0
    stages.append(StageStatus(
        name="Amazon reviews (stratified)",
        done=amazon_review_count > 0,
        summary=(
            f"{amazon_review_count} review(s) "
            f"(5s:{by_star['5s']} / 3s:{by_star['3s']} / 1s:{by_star['1s']})"
            if amazon_review_count else ""
        ),
        last_modified=_newest_mtime(amazon_files),
        notes=([] if stratified or not amazon_review_count
               else ["only non-stratified data; re-run with default stars for 5/3/1 split"]),
    ))

    # Social comments
    social_files: list[Path] = []
    social_comment_count = 0
    social_platform_counts: dict[str, int] = {}
    diagnostic_lines: list[str] = []
    for platform in ("tiktok", "instagram", "youtube"):
        social_dir = base / f"{platform}-comments"
        files = sorted(social_dir.glob("*.json")) if social_dir.exists() else []
        social_files.extend(files)
        platform_count = 0
        for f in files:
            data = _safe_json_load(f)
            if data:
                comments = data.get("comments", []) or []
                platform_count += len(comments)
        if platform_count:
            social_platform_counts[platform] = platform_count
        social_comment_count += platform_count

        diag_dir = base / f"{platform}-diagnostics"
        diag_files = sorted(diag_dir.glob("*.json")) if diag_dir.exists() else []
        for f in diag_files:
            d = _safe_json_load(f) or {}
            status_txt = d.get("status") or "0 comments"
            diagnostic_lines.append(
                f"{platform}/{d.get('competitor_slug', f.stem)}: {status_txt}"
            )

    last_social = _last_cost_log_entry(client, "adc research-social")
    social_notes: list[str] = []
    if social_comment_count == 0 and (last_social or diagnostic_lines):
        social_notes.append(
            "last social run produced 0 comments; use explicit high-signal post/video URLs or search queries"
        )
        if diagnostic_lines:
            shown = "; ".join(diagnostic_lines[:3])
            more = f" (+{len(diagnostic_lines) - 3} more)" if len(diagnostic_lines) > 3 else ""
            social_notes.append(f"per-source diagnostics: {shown}{more}")
    social_summary = ""
    if social_comment_count:
        platform_summary = " / ".join(f"{k}:{v}" for k, v in social_platform_counts.items())
        social_summary = f"{social_comment_count} comment(s) ({platform_summary})"
    elif last_social:
        social_summary = f"0 comment(s) ({last_social.get('note', 'last run')})"
    stages.append(StageStatus(
        name="Social comments",
        done=social_comment_count > 0,
        summary=social_summary,
        last_modified=_newest_mtime(social_files) or _mtime(CLIENTS_DIR / client / ".cost-log.jsonl"),
        notes=social_notes,
        counts={"comments": social_comment_count, "diagnostics": len(diagnostic_lines)},
    ))

    # Competitor best-sellers — free sales-rank snapshots (what they BUY)
    bs_dir = base / "competitor-bestsellers"
    bs_files = sorted(bs_dir.glob("*.json")) if bs_dir.exists() else []
    bs_with_data = 0
    bs_product_count = 0
    for f in bs_files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        top = data.get("top") or []
        if top:
            bs_with_data += 1
            bs_product_count += len(top)
    stages.append(StageStatus(
        name="Competitor bestsellers",
        done=bs_with_data > 0,
        summary=(
            f"{bs_with_data}/{len(bs_files)} competitor(s), {bs_product_count} ranked product(s)"
            if bs_files else ""
        ),
        last_modified=_newest_mtime(bs_files),
    ))

    # Gap map
    gap_yaml = base / "competitive-gaps.yaml"
    gap_md = base / "competitive-gaps.md"
    gap_data = _safe_yaml_load(gap_yaml)
    gap_count = 0
    if gap_data and isinstance(gap_data.get("synthesis"), dict):
        gap_count = len(gap_data["synthesis"].get("exploitable_gaps") or [])
    stages.append(StageStatus(
        name="Competitive gap map",
        done=gap_yaml.exists(),
        summary=f"{gap_count} exploitable gap(s)" if gap_count else "",
        last_modified=_newest_mtime([gap_yaml, gap_md]),
    ))

    return stages


# ─── Section 3: Ad assets ────────────────────────────────────────────────────


def ad_assets_status(client: str) -> list[StageStatus]:
    """Status of ad production output: briefs, prompts, generated images."""
    stages: list[StageStatus] = []

    briefs_dir = CLIENTS_DIR / client / "briefs"
    brief_files = sorted(briefs_dir.glob("*.yaml")) if briefs_dir.exists() else []
    stages.append(StageStatus(
        name="Briefs",
        done=len(brief_files) > 0,
        summary=f"{len(brief_files)} brief(s)",
        last_modified=_newest_mtime(brief_files),
    ))

    prompts_dir = AI_ADS_DIR / client / "prompts"
    prompt_files = sorted(prompts_dir.glob("*.txt")) if prompts_dir.exists() else []
    stages.append(StageStatus(
        name="Fal.ai prompts",
        done=len(prompt_files) > 0,
        summary=f"{len(prompt_files)} prompt(s)",
        last_modified=_newest_mtime(prompt_files),
    ))

    images_dir = AI_ADS_DIR / client / "images"
    image_files = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
    stages.append(StageStatus(
        name="Generated ad images",
        done=len(image_files) > 0,
        summary=f"{len(image_files)} image(s)",
        last_modified=_newest_mtime(image_files),
    ))

    return stages


# ─── Section 4: Recommendations engine ───────────────────────────────────────


def build_recommendations(
    client: str,
    strategy: list[StageStatus],
    competitive: list[StageStatus],
    assets: list[StageStatus],
) -> list[str]:
    """Simple rule-based suggestions for what to run next."""
    recs: list[str] = []
    by_name = {s.name: s for s in (strategy + competitive + assets)}

    # Strategy layer gaps
    if not by_name["Brand research"].done:
        recs.append(f"Run brand research first: adc research --client {client} --url <homepage>")
        return recs   # nothing else makes sense without brand data

    if not by_name["Personas"].done:
        recs.append(f"Generate personas: adc personas --client {client}")
    products_stage = by_name["Products"]
    if not products_stage.done:
        recs.append(f"No products yet; re-run research or create products manually")
    elif products_stage.counts.get("products") and not products_stage.counts.get("enriched"):
        recs.append(
            f"Enrich product files before briefs: "
            f"adc product-deep-dive --client {client} --product <id>"
        )
    if not by_name["Offers"].done:
        recs.append(f"Extract offers: adc offers --client {client} --url <homepage>")
    if not by_name["Strategy matrix"].done:
        recs.append(f"Build strategy matrix: adc strategy-matrix --client {client}")
    if not by_name["Psychology profiles"].done and by_name["Personas"].done:
        recs.append(
            f"Profile avatar psychology (gives sharper briefs): "
            f"adc profile-psychology --client {client}"
        )
    if not by_name["Catalog census"].done and by_name["Brand research"].done:
        recs.append(
            f"Census the full catalog (rule-1 scope + catalog-aware briefs): "
            f"adc catalog --client {client}"
        )

    # Competitive layer
    competitors = by_name["Competitors list"]
    if not competitors.done:
        recs.append(
            f"Create clients/{client}/competitors.yaml with 3-5 competitors to unlock "
            f"competitive research"
        )
    else:
        if not by_name["Exa web sentiment"].done:
            recs.append(
                f"Pull web sentiment: adc research-competitors --client {client}"
            )
        elif by_name["Exa web sentiment"].notes:
            recs.append(
                f"Exa web sentiment is partial: {'; '.join(by_name['Exa web sentiment'].notes)}. "
                f"Consider rerunning failed queries with: adc research-competitors --client {client} --force-refresh"
            )
        if not by_name["On-site competitor reviews"].done:
            recs.append(
                f"Competitor on-site review scrape has no usable reviews. Add review-source URLs "
                f"or run Amazon/social review pulls before relying on the gap map."
            )
        if not by_name["Amazon reviews (stratified)"].done:
            if competitors.counts.get("with_amazon_urls"):
                recs.append(
                    f"Pull Amazon reviews: adc research-amazon --client {client}"
                )
            else:
                recs.append(
                    f"Add amazon_urls to clients/{client}/competitors.yaml if marketplace "
                    f"review mining matters for this client (the pipeline does NOT "
                    f"auto-discover Amazon product URLs)."
                )
        social_stage = by_name.get("Social comments")
        if social_stage and not social_stage.done:
            if social_stage.summary or social_stage.counts.get("diagnostics"):
                recs.append(
                    f"Social research has no usable comments. Add explicit YouTube video IDs "
                    f"(or youtube_search_queries), TikTok/Instagram post URLs, or TikTok search "
                    f"queries before rerunning: adc research-social --client {client} --force-refresh"
                )
            else:
                recs.append(
                    f"Pull social comments: adc research-social --client {client} "
                    f"(configure handles / post URLs / search queries in competitors.yaml first)"
                )
        if not by_name["Competitive gap map"].done and by_name["Exa web sentiment"].done:
            recs.append(
                f"Synthesize gap map: adc analyze-gaps --client {client}"
            )

    # Gap map should be fresh vs briefs
    gap_map = by_name["Competitive gap map"]
    briefs = by_name["Briefs"]
    if gap_map.done and briefs.done and gap_map.last_modified and briefs.last_modified:
        if gap_map.last_modified > briefs.last_modified + timedelta(minutes=10):
            recs.append(
                f"Gap map is newer than briefs — consider regenerating: "
                f"adc brief --client {client} --product <id> --angles 6"
            )

    # Assets layer
    if (
        by_name["Strategy matrix"].done
        and by_name["Psychology profiles"].done
        and not by_name["Briefs"].done
    ):
        recs.append(
            f"Generate first creative briefs: "
            f"adc brief --client {client} --product <id> --angles 6"
        )
    if by_name["Briefs"].done and not by_name["Fal.ai prompts"].done:
        recs.append(
            f"Pick briefs and write prompts: adc menu --client {client} "
            f"then adc prompts --client {client} --pick 1,2,3"
        )
    if by_name["Fal.ai prompts"].done and not by_name["Generated ad images"].done:
        recs.append(
            f"Generate finished images: adc generate --client {client} --pick 1,2,3"
        )

    # Recency warnings
    for stage in strategy + competitive:
        if stage.done and stage.age_days and stage.age_days > STALE_THRESHOLD_DAYS:
            recs.append(
                f"'{stage.name}' is {stage.age_days} days old — consider refreshing"
            )

    if not recs:
        recs.append("All stages look healthy. Ready to ship!")
    return recs
