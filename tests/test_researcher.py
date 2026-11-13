"""Tests for strategy/researcher.py homepage fetching.

A homepage Firecrawl reports as blocked by the site's bot check is not fetched
a second way. A homepage that is merely missing still falls back to the direct
fetch. httpx.Client is replaced for each test; no network calls.
"""

from __future__ import annotations

import pytest

import strategy.researcher as researcher
from strategy.firecrawl_client import BLOCKED_PAGE

SITE = "https://shop.example"


class _Response:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    text = "<html>direct</html>"


@pytest.fixture
def direct(monkeypatch):
    """Replace httpx.Client; return the list of URLs that were fetched directly."""
    fetched: list[str] = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, **kwargs):
            fetched.append(url)
            return _Response()

    monkeypatch.setattr(researcher.httpx, "Client", Client)
    return fetched


def test_blocked_homepage_is_not_fetched_directly(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: BLOCKED_PAGE)

    assert researcher.fetch_homepage_html(SITE) == ""
    assert direct == []


def test_missing_homepage_still_falls_back_to_the_direct_fetch(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: None)

    assert researcher.fetch_homepage_html(SITE) == "<html>direct</html>"
    assert direct == [SITE]


def test_rendered_homepage_is_used_as_is(monkeypatch, direct):
    monkeypatch.setattr(researcher, "firecrawl_scrape_html", lambda url: "<html>rendered</html>")

    assert researcher.fetch_homepage_html(SITE) == "<html>rendered</html>"
    assert direct == []
