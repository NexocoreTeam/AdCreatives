"""Tests for strategy/catalog.py — full-catalog census + problem clustering.

The crawl itself is not exercised (it reuses researcher.py's tested Shopify
fetchers); what IS covered: card dedupe across pages, cluster-prompt assembly
(products listed, hard cap honored), the LLM parse → repair → retry ladder
(via an injected complete_fn, no monkeypatching), catalog.yaml shape, the
rule-1 verdict line, and the competitive_context loader/formatter pair.
"""

from __future__ import annotations

import pytest
import yaml

from strategy.catalog import (
    CatalogError,
    MAX_PRODUCTS_IN_PROMPT,
    build_cluster_prompt,
    cluster_catalog,
    dedupe_cards,
    rule1_verdict,
    write_catalog,
)
from strategy.competitive_context import format_catalog_block, load_catalog
from strategy.researcher import ProductCard


def _card(name: str, slug: str, price: str = "$10.00", rank: int = 0) -> ProductCard:
    return ProductCard(
        name=name, url=f"https://x.com/products/{slug}", price=price, rank=rank
    )


CLUSTER_YAML = """\
clusters:
  - name: emotional-support merch
    problem: affordable daily mood relief
    persona_fit: primary
products:
  - handle: sticker-club
    cluster: emotional-support merch
    promise: five new characters monthly
    ad_priority: high
  - handle: plush-luci
    cluster: emotional-support merch
    promise: a plush that gets it
    ad_priority: medium
"""

TWO_CLUSTER_YAML = """\
clusters:
  - name: gut support
    problem: bloating relief
    persona_fit: primary
  - name: mood support
    problem: stress and sleep
    persona_fit: secondary
products:
  - handle: sticker-club
    cluster: gut support
    promise: p1
    ad_priority: high
  - handle: plush-luci
    cluster: mood support
    promise: p2
    ad_priority: low
"""

BAD_YAML = """\
clusters:
  - "emotional-support merch" (the main one)
"""


class FakeClaude:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, prompt, system="", max_tokens=4096, **kwargs):
        self.calls.append(prompt)
        return self.outputs.pop(0)


# ─── Card assembly ───────────────────────────────────────────────────────────


def test_dedupe_cards_keeps_first_occurrence():
    page1 = [_card("A", "a", rank=1), _card("B", "b", rank=2)]
    page2 = [_card("B duplicate", "b", rank=3), _card("C", "c", rank=4)]
    cards = dedupe_cards([page1, page2])
    assert [c.name for c in cards] == ["A", "B", "C"]


def test_cluster_prompt_lists_products_and_caps():
    cards = [_card(f"Product {i}", f"p-{i}") for i in range(MAX_PRODUCTS_IN_PROMPT + 50)]
    prompt = build_cluster_prompt(cards, brand_snippet="Chaotic merch brand")
    assert "Product 0" in prompt
    assert "Chaotic merch brand" in prompt
    # Products past the cap are summarized, not listed
    assert f"p-{MAX_PRODUCTS_IN_PROMPT + 10}" not in prompt
    assert "more products not listed" in prompt


# ─── Clustering ladder ───────────────────────────────────────────────────────


def test_cluster_catalog_clean_parse_single_call():
    fake = FakeClaude([CLUSTER_YAML])
    out = cluster_catalog([_card("Sticker Club", "sticker-club")], "", complete_fn=fake)
    assert out["clusters"][0]["name"] == "emotional-support merch"
    assert len(fake.calls) == 1


def test_cluster_catalog_repairs_bad_yaml():
    fake = FakeClaude([BAD_YAML, CLUSTER_YAML])
    out = cluster_catalog([_card("Sticker Club", "sticker-club")], "", complete_fn=fake)
    assert "products" in out
    assert len(fake.calls) == 2
    assert "failed to parse" in fake.calls[1]


def test_cluster_catalog_raises_when_exhausted():
    fake = FakeClaude([BAD_YAML] * 4)
    with pytest.raises(CatalogError):
        cluster_catalog([_card("A", "a")], "", complete_fn=fake)
    assert len(fake.calls) == 4  # extract, repair, re-extract, repair


# ─── Artifact shape + rule-1 verdict ─────────────────────────────────────────


def test_write_catalog_merges_cards_with_clustering(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cards = [
        _card("Sticker Club", "sticker-club", price="$10.00", rank=1),
        _card("Luci-purr Plush", "plush-luci", price="$28.00", rank=2),
    ]
    clustering = yaml.safe_load(CLUSTER_YAML)
    path = write_catalog("demo", "https://x.com", cards, clustering)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data["total_products"] == 2
    assert data["clusters"][0]["product_count"] == 2
    by_handle = {p["handle"]: p for p in data["products"]}
    assert by_handle["sticker-club"]["price"] == "$10.00"
    assert by_handle["sticker-club"]["promise"] == "five new characters monthly"
    assert "single pipeline scope" in data["rule1_verdict"]


def test_rule1_verdict_multi_cluster():
    clusters = yaml.safe_load(TWO_CLUSTER_YAML)["clusters"]
    verdict = rule1_verdict(clusters)
    assert "separate" in verdict
    assert "gut support" in verdict and "mood support" in verdict


# ─── Loader + prompt block (competitive_context) ─────────────────────────────


def test_load_catalog_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_catalog("nope") is None


def test_format_catalog_block_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cards = [_card("Sticker Club", "sticker-club", rank=1),
             _card("Luci-purr Plush", "plush-luci", rank=2)]
    write_catalog("demo", "https://x.com", cards, yaml.safe_load(CLUSTER_YAML))
    block = format_catalog_block(load_catalog("demo"))
    assert "FULL CATALOG" in block
    assert "emotional-support merch" in block
    assert "2 product(s)" in block
    assert "Sticker Club" in block


def test_format_catalog_block_empty_and_capped(tmp_path, monkeypatch):
    assert format_catalog_block(None) == ""
    monkeypatch.chdir(tmp_path)
    cards = [_card(f"Product {i}", f"p-{i}") for i in range(200)]
    clustering = {
        "clusters": [{"name": "c1", "problem": "x", "persona_fit": "primary"}],
        "products": [
            {"handle": f"p-{i}", "cluster": "c1", "promise": "y", "ad_priority": "low"}
            for i in range(200)
        ],
    }
    write_catalog("demo", "https://x.com", cards, clustering)
    block = format_catalog_block(load_catalog("demo"), max_chars=1500)
    assert len(block) <= 1500
