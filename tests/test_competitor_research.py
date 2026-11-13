"""Tests for strategy/competitor_research.py page fetching.

A page Firecrawl reports as blocked by the site's bot check is not fetched a
second way, and the saved note says so. A page that is merely missing still
falls back to the direct fetch. Fetchers are monkeypatched in the module
namespace; no network calls.
"""

from __future__ import annotations

import strategy.competitor_research as cr
from strategy.competitor_research import Competitor, pull_competitor_reviews
from strategy.firecrawl_client import BLOCKED_PAGE
from strategy.reviews import VendorSignal

SITE = "https://shop.example"
PAGE_A = f"{SITE}/products/a"
PAGE_B = f"{SITE}/products/b"
SHOP = Competitor(name="Shop", slug="shop", url=SITE)


def _no_direct_fetch(url):
    raise AssertionError(f"blocked page fetched directly: {url}")


def _no_reviews(html="", product_url="", base_url="", limit=100):
    return [], VendorSignal(vendor="none")


def test_blocked_page_is_not_fetched_directly(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    html = cr._fetch_html(PAGE_A)

    assert html == ""
    assert html is BLOCKED_PAGE  # passed on, so the caller can say why it is empty


def test_missing_page_still_falls_back_to_the_direct_fetch(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: None)
    monkeypatch.setattr(cr, "_fetch_html_raw", lambda url: "<html>raw</html>")

    assert cr._fetch_html(PAGE_A) == "<html>raw</html>"


def test_rendered_page_is_used_as_is(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: "<html>rendered</html>")
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    assert cr._fetch_html(PAGE_A) == "<html>rendered</html>"


def test_review_pull_leaves_blocked_product_pages_alone_and_says_so(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [PAGE_A, PAGE_B])
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    bundle = pull_competitor_reviews(SHOP)

    assert bundle.reviews == []
    assert bundle.scraped_pages == []
    assert "2 page(s) blocked by the site's bot check" in bundle.notes
    assert "review widget is unknown" in bundle.notes
    # Nothing was read, so the note must not claim what the pages contain.
    assert "No supported widget API" not in bundle.notes


def test_blocked_homepage_is_named_in_the_note(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [])
    monkeypatch.setattr(cr, "_shopify_products_json_urls", lambda url: [])
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    bundle = pull_competitor_reviews(SHOP)

    assert bundle.scraped_pages == []
    assert "1 page(s) blocked by the site's bot check" in bundle.notes
    assert "No product pages found" in bundle.notes


def test_note_counts_blocked_pages_next_to_the_pages_that_were_read(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [PAGE_A, PAGE_B])
    monkeypatch.setattr(
        cr,
        "firecrawl_scrape_html",
        lambda url: BLOCKED_PAGE if url == PAGE_A else "<html>plain</html>",
    )
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)
    monkeypatch.setattr(cr, "fetch_product_reviews", _no_reviews)

    bundle = pull_competitor_reviews(SHOP)

    assert bundle.scraped_pages == [PAGE_B]
    assert "1 page(s) blocked by the site's bot check" in bundle.notes
    assert "No reviews extracted from 1 page(s)" in bundle.notes
    assert "No supported widget API" in bundle.notes


def test_note_is_unchanged_when_nothing_is_blocked(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [PAGE_A, PAGE_B])
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: "<html>plain</html>")
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)
    monkeypatch.setattr(cr, "fetch_product_reviews", _no_reviews)

    bundle = pull_competitor_reviews(SHOP)

    assert bundle.notes == (
        "No reviews extracted from 2 page(s). Detected vendors: none. "
        "No supported widget API and no JSON-LD review markup — for this "
        "competitor, rely on Exa/Reddit/Amazon/social sources instead."
    )
