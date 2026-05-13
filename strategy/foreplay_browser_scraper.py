"""Playwright-based scraper for Foreplay UI's per-ad Content Style classifications.

Foreplay's public API returns empty `content_filter` for most ads, but the
web UI shows a real "Content Style" classification (Features and Benefits,
Us vs Them, etc.) on every IMAGE ad's detail panel — produced by Foreplay's
own classifier and stored in Firestore. This scraper uses Playwright with a
persistent Chrome profile to reuse the user's logged-in Foreplay session,
walks each brand's ad feed, and saves a {ad_id: content_style} cache.

First run: a visible Chrome window opens — log in to Foreplay manually, then
press Enter in the terminal to continue. The login is saved in a dedicated
profile dir so subsequent runs auto-authenticate.

Setup:
    pip install -e ".[scraping]"
    playwright install chromium

Usage:
    adc scrape-classifications --library standard [--max-per-brand 30]

Output:
    references/swipe/<library>/_classifications-cache.json
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    # Avoid importing playwright at module load — it's an optional dep
    from playwright.sync_api import BrowserContext, Page  # noqa: F401


SWIPE_ROOT = Path("references/swipe")
PROFILE_DIR = Path.home() / ".foreplay-scraper-profile"
CACHE_FILENAME = "_classifications-cache.json"

# Long timeouts because Foreplay's UI is heavy (Vue + Firestore subscriptions)
PAGE_LOAD_TIMEOUT = 30_000
PANEL_OPEN_TIMEOUT = 15_000
AD_CHANGE_TIMEOUT = 6_000

# The scraping JS — same logic we validated via Claude in Chrome. Self-iterating
# Next-button walker that reads Content Style from the open detail panel.
SCRAPE_JS = r"""
async (maxAds) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function readField(label) {
    for (const el of document.querySelectorAll('div, span')) {
      if ((el.textContent || '').trim() !== label) continue;
      const parent = el.parentElement;
      if (!parent) continue;
      const sibs = Array.from(parent.children);
      const idx = sibs.indexOf(el);
      if (idx >= 0 && idx + 1 < sibs.length) {
        return (sibs[idx + 1].textContent || '').trim().replace(/\s+/g, ' ');
      }
    }
    return null;
  }

  function readAdId() {
    for (const el of document.querySelectorAll('div, span')) {
      const m = (el.textContent || '').trim().match(/^ID:\s*(\d{10,})$/);
      if (m) return m[1];
    }
    return null;
  }

  function findNext() {
    for (const b of document.querySelectorAll('button')) {
      if ((b.textContent || '').trim().toLowerCase() === 'next') return b;
    }
    return null;
  }

  async function waitForChange(prev, timeout = 5000) {
    const t0 = Date.now();
    while (Date.now() - t0 < timeout) {
      await sleep(150);
      const cur = readAdId();
      if (cur && cur !== prev) return cur;
    }
    return null;
  }

  const out = [];
  let lastId = null;
  for (let i = 0; i < maxAds; i++) {
    await sleep(700);
    const adId = readAdId();
    if (!adId) break;
    if (adId === lastId) {
      // Stuck — maybe we hit the end of the feed
      break;
    }
    out.push({
      ad_id: adId,
      format: readField('Format'),
      content_style: readField('Content Style'),
      niche: readField('Niche'),
      product_category: readField('Product Category'),
      target_market: readField('Target Market'),
    });
    lastId = adId;
    if (i < maxAds - 1) {
      const btn = findNext();
      if (!btn) break;
      btn.click();
      const newId = await waitForChange(adId);
      if (!newId) break;
    }
  }
  return out;
}
"""


def _import_playwright():
    """Import playwright lazily and give a helpful error if missing."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "playwright not installed. Run:\n"
            "    pip install -e \".[scraping]\"\n"
            "    playwright install chromium"
        ) from exc
    from playwright.sync_api import sync_playwright

    return sync_playwright


def _load_brands_from_meta(library: str) -> list[dict]:
    meta_path = SWIPE_ROOT / library / "_meta.yaml"
    if not meta_path.exists():
        raise FileNotFoundError(f"No _meta.yaml at {meta_path}")
    with meta_path.open(encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}
    return meta.get("brands") or []


def _load_cache(library: str) -> dict:
    path = SWIPE_ROOT / library / CACHE_FILENAME
    if not path.exists():
        return {"brands": {}}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save_cache(library: str, cache: dict) -> None:
    path = SWIPE_ROOT / library / CACHE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def _click_first_ad_expand(page) -> bool:
    """Click the 'expand to detail' folder icon on the first ad card.

    Strategy: each card has the date badge (`• 1D`/`• 2D`) followed by 2 small
    icons in its top-right — Save and Expand. The Expand icon is the rightmost
    of the two and is a button with no text. We target it via JS that
    inspects the visible card grid order.
    """
    # Wait for ad grid to render
    page.wait_for_selector("img", timeout=PAGE_LOAD_TIMEOUT)

    # JS to find the first ad card's expand button. Heuristic: find the first
    # element matching a card header (`PetLab Co.` or any brand badge), then
    # locate the LAST button in its parent's button row (Save is first, Expand
    # is second/last).
    clicked = page.evaluate(
        r"""
        () => {
            // Find first button that looks like an ad-card-header action button:
            // small (svg-only), no text. Inside a row with a 'Save to Swipe File' button.
            const allButtons = Array.from(document.querySelectorAll('button'));
            // Group adjacent siblings — for each save-button, take its later sibling buttons.
            const saveButtons = allButtons.filter(b => {
                const t = (b.textContent || '').trim().toLowerCase();
                // Card-header save button is a tiny SVG-only button (no text).
                // Save to Swipe File big button at bottom HAS text.
                return false;  // we go a different route below
            });
            // Better strategy: find the first card-header (brand badge), then
            // the buttons in that header's row.
            const cards = document.querySelectorAll('[class*="ad-card"], [data-test*="ad"], article, .card');
            // Fallback: find the first element whose direct text is short and
            // contains 'PetLab' or other brand name — its parent row has buttons.
            // Universal: just walk and click the FIRST button that has only an SVG
            // child and is near the top of the page.
            const allBtns = allButtons.filter(b => {
                const rect = b.getBoundingClientRect();
                if (rect.top > 600) return false;  // only top of viewport
                if (rect.width > 40 || rect.height > 40) return false;  // tiny icon buttons only
                if ((b.textContent || '').trim().length > 0) return false;  // no text
                // Must have an SVG child
                return !!b.querySelector('svg');
            });
            // Sort by visual order: top, then left-to-right
            allBtns.sort((a, b) => {
                const ra = a.getBoundingClientRect();
                const rb = b.getBoundingClientRect();
                if (Math.abs(ra.top - rb.top) > 5) return ra.top - rb.top;
                return ra.left - rb.left;
            });
            // The icons in card headers are arranged horizontally: save, then expand.
            // We want the EXPAND button = the SECOND tiny icon button in the first card.
            // Find first card's bounding rect by looking at first such button row.
            if (allBtns.length === 0) return { error: 'no_icon_buttons' };
            const first = allBtns[0];
            const firstRect = first.getBoundingClientRect();
            // Find buttons in same row (similar top coord)
            const sameRow = allBtns.filter(b => {
                const r = b.getBoundingClientRect();
                return Math.abs(r.top - firstRect.top) < 10;
            });
            if (sameRow.length < 2) {
                // Only one button — click it
                first.click();
                return { ok: true, btns_in_row: sameRow.length, fallback: true };
            }
            // Click the LAST one in the row — that's the expand
            sameRow[sameRow.length - 1].click();
            return { ok: true, btns_in_row: sameRow.length };
        }
        """
    )
    if not isinstance(clicked, dict) or not clicked.get("ok"):
        return False
    # Wait for detail panel to open by polling for ID: pattern
    try:
        page.wait_for_function(
            r"""() => {
                for (const el of document.querySelectorAll('div, span')) {
                    if (/^ID:\s*\d{10,}$/.test((el.textContent||'').trim())) return true;
                }
                return false;
            }""",
            timeout=PANEL_OPEN_TIMEOUT,
        )
        return True
    except Exception:
        return False


def scrape_brand(page, brand_id: str, max_ads: int = 30) -> list[dict]:
    """Scrape one brand: open detail on first ad, iterate Next, return records."""
    url = f"https://app.foreplay.co/discovery/brands/{brand_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
    page.wait_for_timeout(3000)  # let Vue + Firestore subscriptions settle

    if not _click_first_ad_expand(page):
        return []

    # Run the iteration scraper. Playwright's evaluate handles async fine.
    records = page.evaluate(SCRAPE_JS, max_ads)
    return records if isinstance(records, list) else []


def scrape_all(library: str, max_per_brand: int = 30, resume: bool = True,
               start_at: str | None = None,
               connect_url: str | None = None) -> dict:
    """Scrape Content Style for all brands in a library, writing cache as we go.

    Args:
        connect_url: If set (e.g. 'http://localhost:9222'), connect to an
            existing Chrome instance running with --remote-debugging-port=9222.
            Reuses your logged-in session — no separate login needed.
            If None, launches your installed Chrome with a dedicated profile
            (channel='chrome'). First run requires manual Foreplay login;
            credentials persist after that.

    Resumes from cache by default — brands already scraped are skipped.
    """
    sync_playwright = _import_playwright()
    brands = _load_brands_from_meta(library)
    if not brands:
        raise ValueError(f"No brands in {library}/_meta.yaml")

    cache = _load_cache(library) if resume else {"brands": {}}
    cache_brands: dict = cache.setdefault("brands", {})

    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    seen_start = start_at is None  # if None, scrape from the beginning

    with sync_playwright() as p:
        if connect_url:
            # Connect to a running Chrome with --remote-debugging-port=9222
            print(f"Connecting to Chrome at {connect_url}...", file=sys.stderr)
            browser = p.chromium.connect_over_cdp(connect_url)
            ctx = browser.contexts[0] if browser.contexts else browser.new_context()
            page = ctx.new_page()
        else:
            # Launch user's installed Chrome (not Playwright's Chromium) for
            # better SSO / login compatibility. Persistent profile so login
            # is saved across runs.
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(PROFILE_DIR),
                channel="chrome",   # use installed Chrome.exe
                headless=False,
                viewport={"width": 1400, "height": 900},
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # Login check — skipped when using CDP (the connected Chrome is
        # assumed to already be logged in)
        if not connect_url:
            page.goto("https://app.foreplay.co/dashboard", wait_until="domcontentloaded",
                      timeout=PAGE_LOAD_TIMEOUT)
            page.wait_for_timeout(2000)
            if "/login" in page.url or "/sign-in" in page.url.lower():
                print(
                    "\nNot logged in to Foreplay. A Chrome window has opened — "
                    "please log in manually, then press Enter here to continue.\n",
                    file=sys.stderr,
                )
                input("Press Enter once logged in...")
        else:
            # CDP mode: quick sanity check that the session is logged in
            page.goto("https://app.foreplay.co/dashboard",
                      wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT)
            page.wait_for_timeout(1500)
            if "/login" in page.url or "/sign-in" in page.url.lower():
                raise RuntimeError(
                    "Connected via CDP but Foreplay session is NOT logged in. "
                    "In your Chrome (the one launched with --remote-debugging-port), "
                    "log into Foreplay first, then re-run."
                )

        for entry in brands:
            brand_id = entry.get("brand_id")
            name = entry.get("name", "?")
            if not brand_id:
                continue
            if not seen_start:
                if brand_id == start_at:
                    seen_start = True
                else:
                    continue
            if resume and brand_id in cache_brands:
                # Treat empty/error caches as "needs retry" — only skip when
                # we actually got records last time.
                prev_records = cache_brands[brand_id].get("records") or []
                if prev_records:
                    print(f"[skip cached] {name} ({len(prev_records)} records)",
                          file=sys.stderr)
                    continue
                else:
                    print(f"[retrying empty cache] {name}", file=sys.stderr)

            print(f"[scraping] {name} ({brand_id})", file=sys.stderr)
            t0 = time.time()
            try:
                records = scrape_brand(page, brand_id, max_per_brand)
            except Exception as exc:
                print(f"  ! error: {exc}", file=sys.stderr)
                records = []

            elapsed = time.time() - t0
            useful = sum(1 for r in records if r.get("content_style"))
            print(f"  -> {len(records)} ads, {useful} with content_style, {elapsed:.1f}s",
                  file=sys.stderr)

            cache_brands[brand_id] = {
                "name": name,
                "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "records": records,
            }
            _save_cache(library, cache)  # checkpoint after each brand

        if connect_url:
            # Don't close the user's running Chrome
            page.close()
        else:
            ctx.close()

    return cache
