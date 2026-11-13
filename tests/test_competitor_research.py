"""Tests for strategy/competitor_research.py page fetching.

A page Firecrawl reports as blocked by the site's bot check is not fetched a
second way. A page that is merely missing still falls back to the direct fetch.
Fetchers are monkeypatched in the module namespace; no network calls.
"""

from __future__ import annotations

import strategy.competitor_research as cr
from strategy.competitor_research import Competitor, pull_competitor_reviews
from strategy.firecrawl_client import BLOCKED_PAGE

PAGE = "https://shop.example/products/a"


def _no_direct_fetch(url):
    raise AssertionError(f"blocked page fetched directly: {url}")


def test_blocked_page_is_not_fetched_directly(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    assert cr._fetch_html(PAGE) == ""


def test_missing_page_still_falls_back_to_the_direct_fetch(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: None)
    monkeypatch.setattr(cr, "_fetch_html_raw", lambda url: "<html>raw</html>")

    assert cr._fetch_html(PAGE) == "<html>raw</html>"


def test_rendered_page_is_used_as_is(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: "<html>rendered</html>")
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    assert cr._fetch_html(PAGE) == "<html>rendered</html>"


def test_review_pull_leaves_blocked_product_pages_alone(monkeypatch):
    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [
        "https://shop.example/products/a",
        "https://shop.example/products/b",
    ])
    monkeypatch.setattr(cr, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)
    monkeypatch.setattr(cr, "_fetch_html_raw", _no_direct_fetch)

    bundle = pull_competitor_reviews(
        Competitor(name="Shop", slug="shop", url="https://shop.example")
    )

    assert bundle.reviews == []
    assert bundle.scraped_pages == []
