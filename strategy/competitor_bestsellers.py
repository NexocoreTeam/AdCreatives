"""Competitor best-seller snapshots — what the category actually BUYS.

`/collections/all?sort_by=best-selling` is public on every Shopify store and
returns the catalog in descending sales order. The gap map already hears what
competitor customers COMPLAIN about (reviews, comments, Exa sentiment); this
layer adds what they buy most, so contrasts like "their #1 seller is a
licensed collab, ours is an original character" become available as angles.

Fetch strategy: Firecrawl-rendered first — many themes paint the product grid
with JavaScript, so the static path returns fragments (observed live: chubble
157 cards static, Pipsticks 2, Stickii 1). Static httpx is the fallback when
Firecrawl is unavailable. Every outcome, including failures, is persisted to
research/competitor-bestsellers/<slug>.json — an empty layer must say why.

Free: no LLM calls, one page fetch per competitor.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from strategy.competitor_research import load_competitors
from strategy.firecrawl_client import firecrawl_scrape_html
from strategy.researcher import (
    ProductCard,
    fetch_shopify_bestsellers,
    normalize_url,
    parse_shopify_product_cards,
)

CLIENTS_DIR = Path("clients")
BESTSELLER_SUFFIX = "collections/all?sort_by=best-selling"
DEFAULT_TOP_N = 15


def fetch_bestsellers(url: str, top_n: int = DEFAULT_TOP_N) -> tuple[list[ProductCard], str, str]:
    """Fetch a store's best-selling grid. Returns (cards, method, note)."""
    base = normalize_url(url)
    sorted_url = f"{base}/{BESTSELLER_SUFFIX}"

    html = firecrawl_scrape_html(sorted_url)
    if html:
        cards = parse_shopify_product_cards(html, base)
        if cards:
            return cards[:top_n], "firecrawl", ""

    pages = fetch_shopify_bestsellers(base, page_count=1)
    if pages:
        cards = parse_shopify_product_cards(pages[0][1], base)
        if cards:
            return (
                cards[:top_n],
                "httpx-static",
                "firecrawl empty; static grid parse (theme-dependent, may be partial)",
            )

    return [], "none", "no cards parsed from rendered or static fetch"


def snapshot_for_client(client_slug: str, top_n: int = DEFAULT_TOP_N) -> list[dict]:
    """Snapshot every configured competitor's best-sellers to disk."""
    competitors = load_competitors(client_slug)
    out_dir = CLIENTS_DIR / client_slug / "research" / "competitor-bestsellers"
    out_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    for comp in competitors:
        if not (comp.url or "").strip():
            payload = _payload(comp, "", [], "skipped", "no url configured in competitors.yaml")
        else:
            cards, method, note = fetch_bestsellers(comp.url, top_n=top_n)
            payload = _payload(comp, comp.url, cards, method, note)

        out_path = out_dir / f"{comp.slug}.json"
        out_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        results.append(payload)
    return results


def _payload(comp, url: str, cards: list[ProductCard], method: str, note: str) -> dict:
    return {
        "competitor": comp.name,
        "slug": comp.slug,
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "note": note,
        "top": [
            {"rank": i, "name": c.name, "price": c.price, "url": c.url}
            for i, c in enumerate(cards, 1)
        ],
    }


def load_bestsellers(client_slug: str, competitor_slug: str) -> dict | None:
    """Return a saved snapshot, or None when missing/empty."""
    path = (
        CLIENTS_DIR / client_slug / "research" / "competitor-bestsellers"
        / f"{competitor_slug}.json"
    )
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) and data.get("top") else None


def format_bestsellers_block(payload: dict | None) -> str:
    """Prompt-ready block for the gap analyzer's per-brand content."""
    if not payload or not payload.get("top"):
        return ""
    lines = [
        f"{p['rank']}. {p['name']}" + (f" ({p['price']})" if p.get("price") else "")
        for p in payload["top"]
    ]
    return (
        "--- BEST-SELLING PRODUCTS (store-reported sales order, top of "
        "/collections/all?sort_by=best-selling) ---\n" + "\n".join(lines) + "\n"
    )
