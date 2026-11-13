"""Tests for strategy/researcher.py direct-fetch fallbacks.

A page Firecrawl reports as blocked by the site's bot check is not fetched a
second way: not the homepage, and not the pages of a batch. A page that is
merely missing still falls back to the direct fetch. The `direct` fixture
replaces httpx.Client; no network calls.
"""

from __future__ import annotations

from unittest.mock import create_autospec

import pytest

import strategy.firecrawl_client as firecrawl_client
import strategy.researcher as researcher
from strategy.firecrawl_client import BLOCKED_PAGE, ScrapedPages

SITE = "https://shop.example"
HOME = f"{SITE}/"
ABOUT = f"{SITE}/about"
PRODUCT_A = f"{SITE}/product/a/"
PRODUCT_B = f"{SITE}/product/b/"
DIRECT_PAGE = "<html>direct</html>"


def _batch_returns(monkeypatch, scraped):
    monkeypatch.setattr(researcher, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)


# ── The homepage ─────────────────────────────────────────────────────────────


def test_blocked_homepage_is_not_fetched_directly(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)

    assert researcher.fetch_homepage_html(SITE) == ""
    assert direct == []


def test_missing_homepage_still_falls_back_to_the_direct_fetch(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: None)

    assert researcher.fetch_homepage_html(SITE) == DIRECT_PAGE
    assert direct == [SITE]


def test_rendered_homepage_is_used_as_is(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: "<html>rendered</html>")

    assert researcher.fetch_homepage_html(SITE) == "<html>rendered</html>"
    assert direct == []


# ── A batch of brand pages ───────────────────────────────────────────────────


def test_fetch_pages_does_not_fetch_blocked_pages_directly(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=[HOME, ABOUT]))

    assert researcher.fetch_pages(SITE, paths=["/", "/about"]) == {}
    assert direct == []


def test_fetch_pages_still_fetches_the_pages_that_were_not_blocked(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=[ABOUT]))

    assert researcher.fetch_pages(SITE, paths=["/", "/about"]) == {HOME: DIRECT_PAGE}
    assert direct == [HOME]


def test_fetch_pages_knows_a_blocked_page_across_www_and_a_trailing_slash(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=["https://www.shop.example/about/"]))

    researcher.fetch_pages(SITE, paths=["/", "/about"])

    assert direct == [HOME]


def test_fetch_pages_falls_back_for_every_page_when_firecrawl_returned_nothing(monkeypatch, direct):
    _batch_returns(monkeypatch, {})

    researcher.fetch_pages(SITE, paths=["/", "/about"])

    assert direct == [HOME, ABOUT]


# ── A batch of product pages ─────────────────────────────────────────────────


def test_fetch_product_pages_does_not_fetch_blocked_pages_directly(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=[PRODUCT_A, PRODUCT_B]))

    assert researcher.fetch_product_pages([PRODUCT_A, PRODUCT_B]) == {}
    assert direct == []


def test_fetch_product_pages_still_fetches_the_pages_that_were_not_blocked(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=[PRODUCT_A]))

    assert researcher.fetch_product_pages([PRODUCT_A, PRODUCT_B]) == {PRODUCT_B: DIRECT_PAGE}
    assert direct == [PRODUCT_B]


def test_fetch_product_pages_falls_back_for_every_page_when_firecrawl_returned_nothing(
    monkeypatch, direct
):
    _batch_returns(monkeypatch, {})

    researcher.fetch_product_pages([PRODUCT_A, PRODUCT_B])

    assert direct == [PRODUCT_A, PRODUCT_B]


# ── Which pages a direct fetch may still try ─────────────────────────────────


def test_unblocked_urls_keeps_the_order_and_drops_only_blocked_pages():
    scraped = ScrapedPages({}, blocked=[ABOUT])

    assert researcher.unblocked_urls([HOME, ABOUT, PRODUCT_A], scraped) == [HOME, PRODUCT_A]


def test_unblocked_urls_treats_a_plain_dict_as_nothing_blocked():
    assert researcher.unblocked_urls([HOME, ABOUT], {}) == [HOME, ABOUT]


def test_unblocked_urls_ignores_addresses_it_cannot_parse():
    scraped = ScrapedPages({}, blocked=["https://[broken/about/", ABOUT])

    assert researcher.unblocked_urls([HOME, ABOUT, "https://[broken"], scraped) == [
        HOME,
        "https://[broken",
    ]


# ── The real batch function and a real caller together ───────────────────────


def test_a_fully_blocked_batch_makes_no_direct_fetch_end_to_end(monkeypatch, direct):
    """Only the SDK client is mocked: one page shows the robot check, the other
    answers 403, and nothing is fetched another way."""
    client_class = pytest.importorskip("firecrawl.v2.client").FirecrawlClient
    sdk = pytest.importorskip("firecrawl.v2.types")
    fc = create_autospec(client_class, instance=True)
    monkeypatch.setattr(firecrawl_client, "get_firecrawl_client", lambda: fc)

    def page(url, title, final_url=None, status=200):
        return sdk.Document(
            markdown=f"# {title}",
            metadata=sdk.DocumentMetadata(
                title=title,
                url=final_url or url,
                source_url=url,
                status_code=status,
                proxy_used="basic",
            ),
        )

    fc.batch_scrape.return_value = sdk.BatchScrapeJob(
        status="completed",
        completed=2,
        total=2,
        data=[
            page(HOME, "Robot Challenge Screen", final_url=f"{SITE}/.well-known/sgcaptcha/?r=%2F"),
            page(ABOUT, "Access denied", status=403),
        ],
    )

    assert researcher.fetch_pages(SITE, paths=["/", "/about"]) == {}
    assert direct == []
