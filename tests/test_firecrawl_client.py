"""Tests for strategy/firecrawl_client.py, the research crawler's Firecrawl wrapper.

The rule behind these: never get past a site's bot check. So the wrapper asks
Firecrawl for basic proxies only, and a page that comes back as a block screen
is logged and left out, so callers treat it like any other missing page.

The SDK client is a create_autospec mock of the installed SDK's client class,
so a keyword the SDK does not accept fails the test instead of vanishing into
the wrapper's broad `except`. No network calls, no Firecrawl credits.
"""

from __future__ import annotations

import inspect
from unittest.mock import create_autospec

import pytest

import strategy.firecrawl_client as fcm

FirecrawlClient = pytest.importorskip("firecrawl.v2.client").FirecrawlClient
sdk = pytest.importorskip("firecrawl.v2.types")

SITE = "https://shop.example"
PAGE = f"{SITE}/protocols/focus/"
CAPTCHA = f"{SITE}/.well-known/sgcaptcha/?r=%2Fprotocols%2Ffocus%2F"


def _page(
    source_url: str = PAGE,
    *,
    title: str | None = "Focus Protocol",
    final_url: str | None = None,
    status: int | None = 200,
    proxy_used: str | None = "basic",
):
    """A scraped page as the SDK hands it back: content plus metadata."""
    return sdk.Document(
        markdown=f"# {title}",
        html=f"<html><head><title>{title}</title></head><body></body></html>",
        metadata=sdk.DocumentMetadata(
            title=title,
            url=final_url or source_url,
            source_url=source_url,
            status_code=status,
            proxy_used=proxy_used,
        ),
    )


def _robot_check(source_url: str = PAGE):
    """SiteGround's Anti-Bot screen, shaped like the one Firecrawl returned for
    a SiteGround-hosted page on 13 Nov 2026: status 200, this title, and a
    final URL under /.well-known/sgcaptcha/."""
    return _page(source_url, title="Robot Challenge Screen", final_url=CAPTCHA)


def _job(*pages):
    return sdk.BatchScrapeJob(
        status="completed", completed=len(pages), total=len(pages), data=list(pages)
    )


@pytest.fixture
def fc(monkeypatch):
    """Stand-in SDK client that enforces the installed SDK's call signatures."""
    client = create_autospec(FirecrawlClient, instance=True)
    monkeypatch.setattr(fcm, "get_firecrawl_client", lambda: client)
    return client


# ── Proxy mode: basic only, never Firecrawl's escalating default ─────────────


def test_single_page_scrape_asks_for_basic_proxies(fc):
    fc.scrape.return_value = _page()

    assert fcm.firecrawl_scrape_html(PAGE) is not None
    assert fc.scrape.call_args.kwargs["proxy"] == "basic"


def test_batch_scrape_asks_for_basic_proxies(fc):
    fc.batch_scrape.return_value = _job(_page())

    assert fcm.firecrawl_scrape_markdown([PAGE]) == {PAGE: "# Focus Protocol"}
    assert fc.batch_scrape.call_args.kwargs["proxy"] == "basic"


def test_map_is_called_without_a_proxy_mode(fc):
    fc.map.return_value = sdk.MapData(links=[{"url": f"{SITE}/products/a"}])

    assert fcm.firecrawl_map_urls(SITE) == [f"{SITE}/products/a"]
    assert "proxy" not in fc.map.call_args.kwargs


def test_sdk_map_still_has_no_proxy_mode():
    """Tripwire. Firecrawl's /map takes no proxy mode today, so there is nothing
    to pin to basic. If an SDK upgrade adds one, this fails on purpose."""
    assert "proxy" not in inspect.signature(FirecrawlClient.map).parameters, (
        "Firecrawl's map() now takes a proxy mode: pass the basic mode in "
        "firecrawl_map_urls too, then update this test."
    )


# ── A block screen is logged and left out, never returned as content ─────────


def test_robot_check_screen_is_not_returned_as_html(fc, capsys):
    fc.scrape.return_value = _robot_check()

    assert fcm.firecrawl_scrape_html(PAGE) is fcm.BLOCKED_PAGE
    err = capsys.readouterr().err
    assert "[firecrawl]" in err
    assert "blocked" in err
    assert PAGE in err


def test_robot_check_is_recognised_by_its_title_alone(fc):
    fc.scrape.return_value = _page(title="  robot challenge screen ")

    assert fcm.firecrawl_scrape_html(PAGE) is fcm.BLOCKED_PAGE


def test_robot_check_is_recognised_by_its_final_url_alone(fc):
    fc.scrape.return_value = _page(title="One moment", final_url=CAPTCHA)

    assert fcm.firecrawl_scrape_html(PAGE) is fcm.BLOCKED_PAGE


def test_blocked_marker_is_falsy_so_plain_callers_treat_the_page_as_missing():
    """Callers that only check `if html:` need no change. Callers with their own
    direct fetch check `html is BLOCKED_PAGE` and leave a blocked page alone."""
    assert not fcm.BLOCKED_PAGE
    assert fcm.BLOCKED_PAGE == ""
    assert isinstance(fcm.BLOCKED_PAGE, str)


def test_batch_leaves_out_the_blocked_page_and_keeps_the_rest(fc, capsys):
    home, about = f"{SITE}/", f"{SITE}/about/"
    fc.batch_scrape.return_value = _job(
        _page(home, title="Home"),
        _robot_check(PAGE),
        _page(about, title="About"),
    )

    pages = fcm.firecrawl_scrape_markdown([home, PAGE, about])

    assert pages == {home: "# Home", about: "# About"}
    err = capsys.readouterr().err
    assert "blocked" in err
    assert PAGE in err  # the log names the page we asked for, not only the captcha


@pytest.mark.parametrize("status", [401, 403, 429])
def test_page_that_answered_with_a_block_status_is_left_out(fc, capsys, status):
    """These are the answers Firecrawl's default mode retries through stronger
    proxies. On basic they come back as they are, so they must not be read."""
    fc.scrape.return_value = _page(title="Access denied", status=status)
    fc.batch_scrape.return_value = _job(_page(title="Access denied", status=status))

    assert fcm.firecrawl_scrape_html(PAGE) is fcm.BLOCKED_PAGE
    assert fcm.firecrawl_scrape_markdown([PAGE]) == {}
    err = capsys.readouterr().err
    assert f"HTTP {status}" in err
    assert PAGE in err


@pytest.mark.parametrize("status", [200, 404, 500, None])
def test_other_statuses_are_handled_as_before(fc, status):
    """Pins the edge of this rule, not a view on 404 text: only the block
    answers above are left out."""
    fc.scrape.return_value = _page(status=status)
    fc.batch_scrape.return_value = _job(_page(status=status))

    assert fcm.firecrawl_scrape_html(PAGE) is not None
    assert fcm.firecrawl_scrape_markdown([PAGE]) == {PAGE: "# Focus Protocol"}


@pytest.mark.parametrize("title", ["Robot Challenge Screen Printing Kit", "Robot", ""])
def test_title_must_match_the_whole_phrase(fc, title):
    """A longer title that contains the phrase, or a shorter one inside it, is content."""
    fc.scrape.return_value = _page(title=title)

    assert fcm.firecrawl_scrape_html(PAGE) is not None


def test_page_without_metadata_is_returned(fc):
    fc.scrape.return_value = sdk.Document(html="<html></html>")

    assert fcm.firecrawl_scrape_html(PAGE) == "<html></html>"


def test_block_markers_match_the_fields_the_sdk_builds_from_an_api_response(fc):
    """The API answers in camelCase (statusCode, sourceURL). Feed its shape
    through the SDK's own parser so a renamed field fails here."""
    normalize = pytest.importorskip("firecrawl.v2.utils.normalize").normalize_document_input
    denied = {
        "html": "<html>denied</html>",
        "metadata": {"title": "Denied", "url": PAGE, "sourceURL": PAGE, "statusCode": 403},
    }
    robot = {
        "html": "<html>robot</html>",
        "metadata": {
            "title": "Robot Challenge Screen",
            "url": CAPTCHA,
            "sourceURL": PAGE,
            "statusCode": 200,
        },
    }

    for api_page in (denied, robot):
        fc.scrape.return_value = sdk.Document(**normalize(api_page))
        assert fcm.firecrawl_scrape_html(PAGE) is fcm.BLOCKED_PAGE


# ── Firecrawl's `proxy` setting is deprecated: notice if it stops being honoured ──


def test_stronger_proxy_than_asked_for_is_logged_and_the_page_kept(fc, capsys):
    fc.scrape.return_value = _page(proxy_used="stealth")
    fc.batch_scrape.return_value = _job(_page(proxy_used="stealth"))

    assert fcm.firecrawl_scrape_html(PAGE) is not None
    assert fcm.firecrawl_scrape_markdown([PAGE]) == {PAGE: "# Focus Protocol"}
    err = capsys.readouterr().err
    assert err.count("stealth") == 2
    assert err.count(PAGE) == 2


@pytest.mark.parametrize("proxy_used", ["basic", None])
def test_ordinary_page_logs_nothing(fc, capsys, proxy_used):
    fc.scrape.return_value = _page(proxy_used=proxy_used)
    fc.batch_scrape.return_value = _job(_page(proxy_used=proxy_used))

    fcm.firecrawl_scrape_html(PAGE)
    fcm.firecrawl_scrape_markdown([PAGE])

    assert capsys.readouterr().err == ""


# ── The fallbacks callers rely on ────────────────────────────────────────────


def test_without_a_client_every_call_returns_empty(monkeypatch):
    monkeypatch.setattr(fcm, "get_firecrawl_client", lambda: None)

    assert fcm.firecrawl_scrape_html(PAGE) is None
    assert fcm.firecrawl_scrape_markdown([PAGE]) == {}
    assert fcm.firecrawl_map_urls(SITE) == []


def test_sdk_failure_returns_empty_and_is_logged(fc, capsys):
    """A failure is not a block: it stays None, so callers may use their own fetch."""
    fc.scrape.side_effect = RuntimeError("scrape failed")
    fc.batch_scrape.side_effect = RuntimeError("batch failed")

    assert fcm.firecrawl_scrape_html(PAGE) is None
    assert fcm.firecrawl_scrape_markdown([PAGE]) == {}
    err = capsys.readouterr().err
    assert "scrape failed" in err
    assert "batch failed" in err
