"""Tests for parse_shopify_product_cards href coverage.

Themes emit product links in three shapes; the parser must catch all of them
and dedupe to one card per slug. The collection-scoped form was a live gap:
Pipsticks and Self-Care Is For Everyone grids emit almost exclusively
/collections/<x>/products/<slug> hrefs and parsed to 1-2 cards before the
2026-07-07 regex extension.
"""

from __future__ import annotations

from strategy.researcher import parse_shopify_product_cards

BASE = "https://x.com"


def test_bare_relative_href():
    html = '<a href="/products/turt-plush"><img alt="Turt McGurt Plush"></a>'
    cards = parse_shopify_product_cards(html, BASE)
    assert [c.name for c in cards] == ["Turt McGurt Plush"]
    assert cards[0].url == f"{BASE}/products/turt-plush"


def test_collection_scoped_href():
    html = (
        '<a href="/collections/all/products/sticker-club">'
        '<img alt="Sticker Club Monthly"></a>'
    )
    cards = parse_shopify_product_cards(html, BASE)
    assert len(cards) == 1
    # Canonical PDP URL: the /collections prefix is dropped
    assert cards[0].url == f"{BASE}/products/sticker-club"


def test_absolute_href():
    html = '<a href="https://x.com/products/plush-luci"><img alt="Luci Plush"></a>'
    cards = parse_shopify_product_cards(html, BASE)
    assert len(cards) == 1
    assert cards[0].url == f"{BASE}/products/plush-luci"


def test_scoped_and_bare_dedupe_to_one_card():
    html = (
        '<a href="/collections/best-sellers/products/turt-plush"><img alt="Turt Plush"></a>'
        '<a href="/products/turt-plush"><img alt="Turt Plush"></a>'
    )
    cards = parse_shopify_product_cards(html, BASE)
    assert len(cards) == 1
