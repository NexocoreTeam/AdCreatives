"""Tests for strategy/offers.py page fetching.

An offer page Firecrawl reports as blocked by the site's bot check is not
fetched a second way. When Firecrawl returned nothing at all, every page still
falls back to the direct fetch. The `direct` fixture replaces httpx.Client; no
network calls.
"""

from __future__ import annotations

from urllib.parse import urljoin

import strategy.offers as offers
from strategy.firecrawl_client import ScrapedPages

SITE = "https://shop.example"
CANDIDATES = [urljoin(SITE + "/", path.lstrip("/")) for path in offers.OFFER_CANDIDATE_PATHS]


def _batch_returns(monkeypatch, scraped):
    monkeypatch.setattr(offers, "firecrawl_scrape_markdown", lambda urls, **kw: scraped)


def test_blocked_offer_pages_are_not_fetched_directly(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=CANDIDATES))

    assert offers.fetch_offer_pages(SITE) == {}
    assert direct == []


def test_offer_pages_that_were_not_blocked_are_still_fetched(monkeypatch, direct):
    _batch_returns(monkeypatch, ScrapedPages({}, blocked=CANDIDATES[1:]))

    assert offers.fetch_offer_pages(SITE) == {CANDIDATES[0]: "<html>direct</html>"}
    assert direct == [CANDIDATES[0]]


def test_every_offer_page_falls_back_when_firecrawl_returned_nothing(monkeypatch, direct):
    _batch_returns(monkeypatch, {})

    offers.fetch_offer_pages(SITE)

    assert direct == CANDIDATES


def test_backup_fetch_of_offer_pages_sends_no_browser_name(monkeypatch, direct):
    _batch_returns(monkeypatch, {})

    offers.fetch_offer_pages(SITE)

    assert direct.user_agents == [direct.library_default] * len(CANDIDATES)
