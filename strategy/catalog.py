"""Full-catalog census — crawl every SKU, cluster by problem, answer rule 1.

The strategy layers (personas, matrix, gaps) are brand-level, but until this
stage the pipeline only *persisted* the few hero products picked during
research — the rest of the catalog was parsed for bestseller ranking and then
discarded. The census writes the whole picture to products/catalog.yaml:

- every product with price + one-line promise + persona fit,
- problem-cluster grouping, which mechanically answers pipeline rule 1
  ("one product per run when products solve different problems"): 1 cluster =
  a single pipeline scope; N clusters = N runs sharing brand/competitor layers,
- ad_priority per product so "what do we advertise next" is a menu, not a
  guess.

Downstream, competitive_context.format_catalog_block() injects a compact
summary into the strategy-matrix and brief prompts so every angle is written
knowing the full range.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

from strategy.llm import claude_complete
from strategy.llm_yaml import strip_fences, try_repair_yaml
from strategy.researcher import (
    ProductCard,
    fetch_shopify_bestsellers,
    is_shopify_site,
    normalize_url,
    parse_shopify_product_cards,
)

MAX_PRODUCTS_IN_PROMPT = 150  # listing cap; the rest is summarized honestly
MAX_CRAWL_PAGES = 12          # /collections/all pages (Shopify caps ~50/page)


class CatalogError(RuntimeError):
    """Catalog clustering produced unusable output after extract + repair."""


CLUSTER_SYSTEM = """You are a DTC catalog strategist. You group products by the
CUSTOMER PROBLEM they solve (jobs-to-be-done), not by product type or material.
Two products belong to the same cluster when the same persona would buy either
for the same underlying reason. Output valid YAML only, no markdown fences."""

CLUSTER_PROMPT = """Below is the full product catalog for a brand.

BRAND CONTEXT:
{brand_snippet}

CATALOG ({listed} of {total} products listed{truncation_note}):
{product_lines}

Group the catalog into 1-4 problem clusters. Fewer is better — split ONLY when
personas for one group would be substantially different from personas for
another (different pain language, different current solutions, different
trigger events). Format variants, sizes, and flavors of the same promise are
ONE cluster.

Return YAML with exactly this structure:

clusters:
  - name: "short cluster name"
    problem: "the customer problem this cluster solves, one line"
    persona_fit: "which persona role(s) this maps to: primary/secondary/tertiary or 'new persona needed'"
products:
  - handle: "product-url-slug"
    cluster: "cluster name from above"
    promise: "one-line customer-facing promise for this product"
    ad_priority: "high/medium/low — high = distinct story worth its own ad, low = catalog filler"

Every listed product handle must appear exactly once under products."""


def crawl_full_catalog(url: str, max_pages: int = MAX_CRAWL_PAGES) -> list[ProductCard]:
    """Crawl the whole /collections/all listing (not just the bestseller top).

    Reuses the tested Shopify fetch/parse pair from researcher.py; pages stop
    contributing once pagination runs past the catalog end (no new cards)."""
    url = normalize_url(url)
    pages = fetch_shopify_bestsellers(url, page_count=max_pages)
    per_page_cards = [parse_shopify_product_cards(html, url) for _, html in pages]
    return dedupe_cards(per_page_cards)


def dedupe_cards(per_page_cards: list[list[ProductCard]]) -> list[ProductCard]:
    """Merge page-wise card lists, keeping the first occurrence per slug."""
    seen: set[str] = set()
    merged: list[ProductCard] = []
    for cards in per_page_cards:
        for card in cards:
            slug = card.url.rstrip("/").split("/")[-1]
            if slug in seen:
                continue
            seen.add(slug)
            card.rank = len(merged) + 1
            merged.append(card)
    return merged


def _slug(card: ProductCard) -> str:
    return card.url.rstrip("/").split("/")[-1]


def build_cluster_prompt(cards: list[ProductCard], brand_snippet: str) -> str:
    listed = cards[:MAX_PRODUCTS_IN_PROMPT]
    lines = [
        f"- {_slug(c)} | {c.name} | {c.price or 'price unknown'} | bestseller rank {c.rank}"
        for c in listed
    ]
    overflow = len(cards) - len(listed)
    truncation_note = (
        f"; {overflow} more products not listed (long-tail variants)" if overflow > 0 else ""
    )
    return CLUSTER_PROMPT.format(
        brand_snippet=brand_snippet.strip() or "(no brand context provided)",
        listed=len(listed),
        total=len(cards),
        truncation_note=truncation_note,
        product_lines="\n".join(lines),
    )


def cluster_catalog(
    cards: list[ProductCard],
    brand_snippet: str,
    complete_fn: Callable[..., str] = claude_complete,
) -> dict:
    """Extract → repair → re-extract → repair, then raise CatalogError."""
    prompt = build_cluster_prompt(cards, brand_snippet)
    last_error: object = None
    for _ in range(2):
        result = strip_fences(
            complete_fn(prompt, system=CLUSTER_SYSTEM, max_tokens=8192)
        )
        try:
            parsed = yaml.safe_load(result)
        except yaml.YAMLError as err:
            last_error = err
            repaired = try_repair_yaml(result, err, complete_fn)
            if repaired is not None:
                return repaired
            continue
        if isinstance(parsed, dict) and parsed.get("clusters"):
            return parsed
        last_error = "output missing 'clusters' mapping"
    raise CatalogError(
        f"catalog clustering produced unusable YAML after 2 extraction attempts "
        f"with repair passes. Last error: {last_error}"
    )


def rule1_verdict(clusters: list[dict]) -> str:
    names = [c.get("name", "?") for c in clusters]
    if len(names) <= 1:
        return (
            "1 problem cluster -> single pipeline scope: brand-level personas/"
            "matrix/gaps cover the whole catalog; briefs stay per-product."
        )
    listed = ", ".join(f"'{n}'" for n in names)
    return (
        f"{len(names)} problem clusters ({listed}) -> per rule 1, run a separate "
        f"pipeline pass per cluster (personas/matrix/briefs), sharing the "
        f"brand + competitor research layers."
    )


def write_catalog(
    client_slug: str,
    url: str,
    cards: list[ProductCard],
    clustering: dict,
) -> Path:
    clusters = list(clustering.get("clusters", []))
    assignments = {
        p.get("handle", ""): p for p in clustering.get("products", []) if isinstance(p, dict)
    }

    products = []
    counts: dict[str, int] = {}
    for card in cards:
        handle = _slug(card)
        assigned = assignments.get(handle, {})
        cluster_name = assigned.get("cluster", "unclustered")
        counts[cluster_name] = counts.get(cluster_name, 0) + 1
        products.append({
            "name": card.name,
            "handle": handle,
            "url": card.url,
            "price": card.price,
            "rank": card.rank,
            "cluster": cluster_name,
            "promise": assigned.get("promise", ""),
            "ad_priority": assigned.get("ad_priority", ""),
        })

    for cluster in clusters:
        cluster["product_count"] = counts.get(cluster.get("name", ""), 0)

    data = {
        "url": url,
        "crawled_at": datetime.now(timezone.utc).isoformat(),
        "total_products": len(cards),
        "listed_in_clustering": min(len(cards), MAX_PRODUCTS_IN_PROMPT),
        "rule1_verdict": rule1_verdict(clusters),
        "clusters": clusters,
        "products": products,
    }

    out_dir = Path("clients") / client_slug / "products"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "catalog.yaml"
    with open(out_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    return out_path
