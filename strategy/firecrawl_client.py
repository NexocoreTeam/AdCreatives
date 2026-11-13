"""Firecrawl wrapper for brand-site scraping.

Replaces httpx-based HTML fetching with Firecrawl's clean-markdown extraction
(only_main_content=True strips nav/footer/menus, JS rendering captures hydrated
content, no aggressive per-page truncation).

All functions return gracefully if FIRECRAWL_API_KEY is unset or the SDK call
fails — callers should fall back to httpx in that case so the pipeline never
hard-fails on a missing key or a transient API hiccup.

Bot checks: scrapes ask for basic proxies only, so Firecrawl never retries a
blocked page through stronger ones. A page that comes back as a block screen
is logged and left out of the results, so callers treat it like any other
missing page.
"""

from __future__ import annotations

import os
import sys

# Firecrawl's default proxy mode ("auto") retries a page that answered 401, 403
# or 429 through "enhanced" proxies, which is getting past the site's bot
# check. Its /map endpoint takes no proxy mode.
# https://docs.firecrawl.dev/features/enhanced-mode
_PROXY_MODE = "basic"

# On basic proxies a blocked page comes back as an ordinary document, so it is
# recognised here instead of being read as content.
_BOT_CHECK_TITLES = ("robot challenge screen",)  # SiteGround Anti-Bot
_BOT_CHECK_URL_MARKERS = ("/.well-known/sgcaptcha/",)  # SiteGround Anti-Bot
_BLOCK_STATUS_CODES = (401, 403, 429)  # the answers "auto" would have retried


def _log(msg: str) -> None:
    """Best-effort stderr logging so failures don't get silently swallowed."""
    try:
        print(f"[firecrawl] {msg}", file=sys.stderr)
    except Exception:
        pass


def get_firecrawl_client():
    """Return a Firecrawl client if FIRECRAWL_API_KEY is set, else None.

    Caller treats None as "fall back to httpx".
    """
    key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not key:
        return None
    try:
        from firecrawl import Firecrawl
        return Firecrawl(api_key=key)
    except ImportError:
        _log("firecrawl-py SDK not installed; run `pip install firecrawl-py`")
        return None
    except Exception as e:
        _log(f"client init failed: {type(e).__name__}: {e}")
        return None


def _doc_url(doc) -> str | None:
    """Pull the canonical URL off a Firecrawl Document (varies by SDK version)."""
    md = getattr(doc, "metadata", None)
    if md is None:
        return None
    for attr in ("url", "source_url", "sourceURL"):
        v = getattr(md, attr, None)
        if v:
            return v
    return None


def _meta(doc, field: str):
    return getattr(getattr(doc, "metadata", None), field, None)


def _block_reason(doc) -> str | None:
    """Say why a returned page is a block screen, or None when it is content."""
    title = _meta(doc, "title")
    if isinstance(title, str) and title.strip().lower() in _BOT_CHECK_TITLES:
        return f"bot check: title {title.strip()!r}"
    final_url = _doc_url(doc)
    if isinstance(final_url, str):
        for marker in _BOT_CHECK_URL_MARKERS:
            if marker in final_url:
                return f"bot check: sent to {marker}"
    status = _meta(doc, "status_code")
    if status in _BLOCK_STATUS_CODES:
        return f"HTTP {status}"
    return None


def _may_use(doc, requested_url: str | None) -> bool:
    """False, and logged, when a returned page is a block screen.

    Also logs a page that came through a stronger proxy than we asked for:
    Firecrawl has deprecated the `proxy` setting, and this is how a run would
    show that it stopped being honoured.
    """
    reason = _block_reason(doc)
    if reason:
        _log(f"blocked page left out: {requested_url} ({reason})")
        return False
    proxy_used = _meta(doc, "proxy_used")
    if proxy_used and proxy_used != _PROXY_MODE:
        _log(f"asked for {_PROXY_MODE} proxies but Firecrawl used {proxy_used!r}: {requested_url}")
    return True


def firecrawl_map_urls(base_url: str, limit: int = 100) -> list[str]:
    """Discover URLs on a site via Firecrawl /map. Returns [] on failure."""
    fc = get_firecrawl_client()
    if not fc:
        return []
    try:
        result = fc.map(base_url, limit=limit)
        urls: list[str] = []
        for link in (result.links or []):
            u = link.url if hasattr(link, "url") else (link if isinstance(link, str) else None)
            if u:
                urls.append(u)
        return urls
    except Exception as e:
        _log(f"map({base_url}) failed: {type(e).__name__}: {e}")
        return []


def firecrawl_scrape_markdown(
    urls: list[str],
    timeout_ms: int = 30000,
    only_main_content: bool = True,
) -> dict[str, str]:
    """Batch-scrape URLs, return {url: markdown}. Empty dict on failure.

    Uses only_main_content=True by default — strips nav, footer, mega-menus
    automatically. Pass only_main_content=False when callers need the head
    or scripts (e.g. og:image meta tags). A blocked page is logged and left out.
    """
    fc = get_firecrawl_client()
    if not fc or not urls:
        return {}
    # Dedupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            deduped.append(u)
    try:
        job = fc.batch_scrape(
            urls=deduped,
            formats=["markdown"],
            only_main_content=only_main_content,
            timeout=timeout_ms,
            proxy=_PROXY_MODE,
        )
    except Exception as e:
        _log(f"batch_scrape({len(deduped)} urls) failed: {type(e).__name__}: {e}")
        return {}

    # batch_scrape returns an object whose `.data` is the list of Documents.
    docs = getattr(job, "data", None) or job
    output: dict[str, str] = {}
    try:
        for doc in docs:
            url = _doc_url(doc)
            if not _may_use(doc, _meta(doc, "source_url") or url):
                continue
            md = getattr(doc, "markdown", None)
            if url and md:
                output[url] = md
    except TypeError:
        _log("batch_scrape return shape unexpected; got non-iterable")
        return {}
    return output


def firecrawl_scrape_html(url: str, timeout_ms: int = 30000) -> str | None:
    """Scrape a single URL and return its full rendered HTML (no main-content
    stripping). Used when callers need <head>, <meta>, or <script> tags —
    e.g. og:image extraction, Shopify detection. Returns None on failure or
    when the page is blocked.
    """
    fc = get_firecrawl_client()
    if not fc:
        return None
    try:
        doc = fc.scrape(
            url,
            formats=["html"],
            only_main_content=False,
            timeout=timeout_ms,
            proxy=_PROXY_MODE,
        )
    except Exception as e:
        _log(f"scrape({url}) failed: {type(e).__name__}: {e}")
        return None
    if not _may_use(doc, url):
        return None
    return getattr(doc, "html", None)
