"""Tests for strategy/competitor_bestsellers.py — competitor sales-rank snapshots.

Network fetchers are monkeypatched in the module namespace; the card PARSING
path runs the real parse_shopify_product_cards against a synthetic grid so the
integration with researcher.py stays honest. Also covers: rendered-first with
static fallback (JS themes return fragments to httpx — observed live on
Pipsticks/Stickii 2026-07-06), per-competitor failure notes persisted instead
of vanishing, and the gap-analyzer content block.
"""

from __future__ import annotations

import json

import yaml

import strategy.competitor_bestsellers as cb
from strategy.competitor_bestsellers import (
    fetch_bestsellers,
    format_bestsellers_block,
    load_bestsellers,
    snapshot_for_client,
)

GRID_HTML = """
<div class="grid">
  <a href="/products/turt-plush"><img alt="Turt McGurt Plush"></a><span class="price">$28.00</span>
  <a href="/products/sticker-club"><img alt="Sticker Club"></a><span class="price">$10.00</span>
</div>
"""


def test_fetch_prefers_rendered_html(monkeypatch):
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: GRID_HTML)
    monkeypatch.setattr(
        cb, "fetch_shopify_bestsellers",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("static path must not run")),
    )
    cards, method, note = fetch_bestsellers("https://x.com", top_n=5)
    assert method == "firecrawl"
    assert [c.name for c in cards] == ["Turt McGurt Plush", "Sticker Club"]
    assert note == ""


def test_fetch_falls_back_to_static(monkeypatch):
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: None)
    monkeypatch.setattr(
        cb, "fetch_shopify_bestsellers",
        lambda base, page_count=1: [("https://x.com/collections/all", GRID_HTML)],
    )
    cards, method, note = fetch_bestsellers("https://x.com")
    assert method == "httpx-static"
    assert len(cards) == 2
    assert "theme-dependent" in note


def test_fetch_returns_note_when_both_paths_empty(monkeypatch):
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: None)
    monkeypatch.setattr(cb, "fetch_shopify_bestsellers", lambda *a, **k: [])
    cards, method, note = fetch_bestsellers("https://x.com")
    assert cards == []
    assert method == "none"
    assert "no cards" in note


def test_fetch_top_n_cap(monkeypatch):
    many = "".join(
        f'<a href="/products/p-{i}"><img alt="Product {i} Name"></a>' for i in range(30)
    )
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: many)
    cards, _, _ = fetch_bestsellers("https://x.com", top_n=15)
    assert len(cards) == 15


def _client_with_competitors(tmp_path):
    comp_dir = tmp_path / "clients" / "demo"
    comp_dir.mkdir(parents=True)
    (comp_dir / "competitors.yaml").write_text(
        yaml.safe_dump({
            "competitors": [
                {"name": "Alpha", "slug": "alpha", "url": "https://alpha.com"},
                {"name": "NoUrl Co", "slug": "nourl", "url": ""},
            ]
        }),
        encoding="utf-8",
    )


def test_snapshot_writes_files_and_persists_failures(tmp_path, monkeypatch):
    _client_with_competitors(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: GRID_HTML)
    results = snapshot_for_client("demo", top_n=5)

    by_slug = {r["slug"]: r for r in results}
    assert by_slug["alpha"]["method"] == "firecrawl"
    assert [p["rank"] for p in by_slug["alpha"]["top"]] == [1, 2]
    assert by_slug["nourl"]["method"] == "skipped"
    assert "no url" in by_slug["nourl"]["note"]

    out_dir = tmp_path / "clients" / "demo" / "research" / "competitor-bestsellers"
    assert (out_dir / "alpha.json").exists()
    # Failures are persisted too — an empty layer must say why
    assert (out_dir / "nourl.json").exists()
    saved = json.loads((out_dir / "nourl.json").read_text(encoding="utf-8"))
    assert saved["top"] == []


def test_load_and_format_block(tmp_path, monkeypatch):
    _client_with_competitors(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cb, "firecrawl_scrape_html", lambda url, **kw: GRID_HTML)
    snapshot_for_client("demo", top_n=5)

    payload = load_bestsellers("demo", "alpha")
    assert payload["competitor"] == "Alpha"
    block = format_bestsellers_block(payload)
    assert "BEST-SELLING PRODUCTS" in block
    assert "1. Turt McGurt Plush" in block

    assert load_bestsellers("demo", "missing") is None
    assert format_bestsellers_block(None) == ""


def test_gap_analyzer_content_includes_bestsellers():
    from strategy.gap_analyzer import _gather_brand_content

    payload = {
        "competitor": "Alpha",
        "top": [{"rank": 1, "name": "Turt McGurt Plush", "price": "$28.00", "url": "u"}],
    }
    content, meta = _gather_brand_content(
        "Alpha", exa_results=[], bestsellers=payload,
    )
    assert "BEST-SELLING PRODUCTS" in content
    assert meta["bestseller_products"] == 1
