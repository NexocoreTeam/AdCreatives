"""Judge.me widget-XHR fallback tier.

Some Judge.me stores render reviews ONLY via the widget's runtime XHR: no
review content in static or JS-rendered PDP HTML, no public token on the
page, and the classic v1 widget endpoint returns nothing — found live on a
14K+-review Shopify store whose product deep-dive reported "judgeme (0)"
for every product. The widget's own data source
(api.judge.me/reviews/reviews_for_widget) needs only the *.myshopify.com
domain + the numeric Shopify product id, both recoverable from page HTML.
"""

import json

import pytest

import strategy.competitor_research as competitor_mod
import strategy.reviews as reviews_mod
from strategy.reviews import (
    Review,
    VendorSignal,
    _extract_myshopify_domain,
    _extract_shopify_product_id,
    _parse_judgeme_widget_html,
    fetch_judgeme_widget_reviews,
    fetch_product_reviews,
)

# ── Fixtures ────────────────────────────────────────────────────────────────

# PDP of a widget-XHR-only store: Judge.me widget container is present but
# EMPTY (reviews arrive via runtime XHR), while the ShopifyAnalytics meta and
# Shopify.shop identifiers sit in inline <script> tags as on every Shopify PDP.
JUDGEME_XHR_ONLY_PDP = """<html><head>
<script src='https://cdn.judge.me/widget_preloader.js'></script>
<script>var meta = {"product":{"id":8734921155,"gid":"gid://shopify/Product/8734921155","vendor":"Example","type":"Apparel"},"page":{"pageType":"product"}};</script>
<script>Shopify.shop = "example-store.myshopify.com";</script>
</head><body>
<div class='jdgm-widget jdgm-review-widget jdgm-outside-widget'></div>
</body></html>"""

# Same store, but the HTML in hand carries no identifiers (e.g. a renderer
# that stripped inline scripts) — the fallback must re-fetch to recover them.
JUDGEME_PDP_NO_IDENTIFIERS = """<html><body>
<div class='jdgm-widget jdgm-review-widget'></div>
</body></html>"""

# The `html` field of a real reviews_for_widget response (structure verified
# live): single-quoted attributes, one `<div class='jdgm-rev ...'>` per
# review, rating as data-score on jdgm-rev__rating, timestamp in
# data-content, body as <p> paragraphs.
WIDGET_XHR_HTML_PAGE = (
    "<div class='jdgm-rev-widg' data-widget-locale='en' data-number-of-reviews='4'>"
    "<div class='jdgm-rev-widg__header'>"
    "<h2 class='jdgm-rev-widg__title'>Customer Reviews</h2></div>"
    "<div class='jdgm-rev-widg__reviews'>"
    "<div class='jdgm-rev jdgm-divider-top ' data-verified-buyer='true' data-thumb-count='2'>"
    "<div class='jdgm-rev__header'>"
    "<span class='jdgm-rev__icon jdgm-rev__icon--circle'>M</span>"
    "<span class='jdgm-rev__rating' data-score='5' role='img' aria-label='5 star review'>"
    "<span class='jdgm-star jdgm--on'></span><span class='jdgm-star jdgm--on'></span>"
    "<span class='jdgm-star jdgm--on'></span><span class='jdgm-star jdgm--on'></span>"
    "<span class='jdgm-star jdgm--on'></span></span>"
    "<span class='jdgm-rev__timestamp jdgm-spinner' data-content='2026-06-28 17:03:12 UTC'>"
    "06/28/2026</span>"
    "<span class='jdgm-rev__br'></span>"
    "<span class='jdgm-rev__author-wrapper'><span class='jdgm-rev__author'>Maya R.</span>"
    "<span class='jdgm-rev__buyer-badge-wrapper'>"
    "<span class='jdgm-rev__buyer-badge'>Verified Buyer</span></span></span>"
    "</div>"
    "<div class='jdgm-rev__content'>"
    "<b class='jdgm-rev__title'>Made my whole week</b>"
    "<div class='jdgm-rev__body'>"
    "<p>Soft, true to size &amp; the print didn&#39;t crack after washing.</p>"
    "<p>Wearing it right now.</p></div>"
    "</div></div>"
    "<div class='jdgm-rev jdgm-divider-top ' data-verified-buyer='false' data-thumb-count='0'>"
    "<div class='jdgm-rev__header'>"
    "<span class='jdgm-rev__rating' data-score='4' role='img' aria-label='4 star review'>"
    "<span class='jdgm-star jdgm--on'></span></span>"
    "<span class='jdgm-rev__timestamp jdgm-spinner' data-content='2026-05-02 09:11:45 UTC'>"
    "05/02/2026</span>"
    "<span class='jdgm-rev__author-wrapper'><span class='jdgm-rev__author'>Jon</span></span>"
    "</div>"
    "<div class='jdgm-rev__content'>"
    "<div class='jdgm-rev__body'><p>Solid quality.</p></div>"
    "</div></div>"
    "</div></div>"
)

EMPTY_WIDGET_HTML = "<div class='jdgm-rev-widg'><div class='jdgm-rev-widg__reviews'></div></div>"


# ── Identifier extraction ───────────────────────────────────────────────────


def test_extract_myshopify_domain():
    assert _extract_myshopify_domain(JUDGEME_XHR_ONLY_PDP) == "example-store.myshopify.com"
    assert _extract_myshopify_domain("<html></html>") == ""


def test_extract_shopify_product_id():
    # ShopifyAnalytics meta is the reliable source: /products/<handle>.js and
    # /products.json can 404/500 on rate-limited stores.
    assert _extract_shopify_product_id(JUDGEME_XHR_ONLY_PDP) == "8734921155"
    assert _extract_shopify_product_id("<html><body>no meta</body></html>") == ""


# ── Widget HTML parsing ─────────────────────────────────────────────────────


def test_parse_judgeme_widget_html():
    reviews = _parse_judgeme_widget_html(WIDGET_XHR_HTML_PAGE)
    assert len(reviews) == 2

    first = reviews[0]
    assert first.rating == 5
    assert first.reviewer == "Maya R."
    assert first.title == "Made my whole week"
    # Tags stripped, entities unescaped, paragraphs joined with whitespace
    assert "true to size & the print didn't crack" in first.body
    assert "Wearing it right now." in first.body
    assert "<p>" not in first.body
    assert first.date == "2026-06-28 17:03:12 UTC"
    assert first.verified is True

    second = reviews[1]
    assert second.rating == 4
    assert second.reviewer == "Jon"
    assert second.title == ""  # review without a title
    assert second.body == "Solid quality."
    assert second.verified is False


def test_parse_judgeme_widget_html_empty():
    assert _parse_judgeme_widget_html(EMPTY_WIDGET_HTML) == []
    assert _parse_judgeme_widget_html("") == []


# ── Widget-XHR fetching + pagination ────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _FakeHttpxClient:
    """Routes on URL substring; each route holds an in-order response queue
    (pagination). Records every (url, params) call for assertions."""

    def __init__(self, route_responses: dict[str, list[_FakeResponse]]):
        self._routes = route_responses
        self.calls: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def get(self, url, params=None, **_):
        self.calls.append((url, dict(params or {})))
        for key, queue in self._routes.items():
            if key in url and queue:
                return queue.pop(0)
        return _FakeResponse(404, {"error": f"no fake for {url}"})


def _patch_httpx(
    monkeypatch: pytest.MonkeyPatch, routes: dict[str, list[_FakeResponse]]
) -> _FakeHttpxClient:
    fake = _FakeHttpxClient(routes)
    monkeypatch.setattr(reviews_mod.httpx, "Client", lambda **kwargs: fake)
    return fake


def test_widget_xhr_hits_api_host_and_paginates(monkeypatch):
    """Two pages of 2 reviews with total_count=4 → both pages fetched, then
    stop. The route key pins the api.judge.me host — the same path on
    judge.me returns 404, so a host regression must fail this test."""
    page_1 = _FakeResponse(200, {"html": WIDGET_XHR_HTML_PAGE, "total_count": 4, "page": 1})
    page_2 = _FakeResponse(200, {"html": WIDGET_XHR_HTML_PAGE, "total_count": 4, "page": 2})
    fake = _patch_httpx(monkeypatch, {"api.judge.me/reviews/reviews_for_widget": [page_1, page_2]})

    reviews = fetch_judgeme_widget_reviews(
        "example-store.myshopify.com", "8734921155", limit=100, product_name="soft-tee"
    )

    assert len(reviews) == 4
    assert all(r.product_id == "8734921155" for r in reviews)
    assert all(r.product_name == "soft-tee" for r in reviews)
    assert len(fake.calls) == 2

    first_params = fake.calls[0][1]
    assert first_params["url"] == "example-store.myshopify.com"
    assert first_params["shop_domain"] == "example-store.myshopify.com"
    assert first_params["platform"] == "shopify"
    assert first_params["product_id"] == "8734921155"
    assert first_params["page"] == 1
    assert first_params["per_page"] == 10
    assert fake.calls[1][1]["page"] == 2


def test_widget_xhr_stops_on_empty_page(monkeypatch):
    """A page that parses to no reviews ends pagination even when
    total_count claims more (defends against infinite loops on parse
    misses or servers that overreport)."""
    empty = _FakeResponse(200, {"html": EMPTY_WIDGET_HTML, "total_count": 100, "page": 1})
    fake = _patch_httpx(monkeypatch, {"api.judge.me": [empty]})

    reviews = fetch_judgeme_widget_reviews("example-store.myshopify.com", "8734921155")
    assert reviews == []
    assert len(fake.calls) == 1


def test_widget_xhr_stops_on_http_error(monkeypatch):
    page_1 = _FakeResponse(200, {"html": WIDGET_XHR_HTML_PAGE, "total_count": 40, "page": 1})
    err = _FakeResponse(429, {"error": "rate limited"})
    fake = _patch_httpx(monkeypatch, {"api.judge.me": [page_1, err]})

    reviews = fetch_judgeme_widget_reviews("example-store.myshopify.com", "8734921155", limit=100)
    assert len(reviews) == 2  # keeps what it got before the error
    assert len(fake.calls) == 2


def test_widget_xhr_respects_limit(monkeypatch):
    page_1 = _FakeResponse(200, {"html": WIDGET_XHR_HTML_PAGE, "total_count": 40, "page": 1})
    fake = _patch_httpx(monkeypatch, {"api.judge.me": [page_1]})

    reviews = fetch_judgeme_widget_reviews("example-store.myshopify.com", "8734921155", limit=1)
    assert len(reviews) == 1
    assert len(fake.calls) == 1


def test_widget_xhr_requires_identifiers():
    assert fetch_judgeme_widget_reviews("", "8734921155") == []
    assert fetch_judgeme_widget_reviews("example-store.myshopify.com", "") == []


# ── Fallback orchestration in fetch_product_reviews ─────────────────────────


def _forbid_bridged_fetch(monkeypatch):
    def _fail(url):
        raise AssertionError(f"bridged fetch must not run (identifiers are in the PDP HTML): {url}")
    monkeypatch.setattr(reviews_mod, "_fetch_raw_html_bridged", _fail)


def test_judgeme_primary_endpoint_still_first(monkeypatch):
    """When the classic v1 widget endpoint delivers, the XHR tier must not run."""
    monkeypatch.setattr(
        reviews_mod, "fetch_judgeme_reviews",
        lambda shop_domain, handle, limit=100: [Review(body="great tee", rating=5)],
    )

    def fail_xhr(*args, **kwargs):
        raise AssertionError("widget-XHR tier must not be used when the v1 endpoint works")

    monkeypatch.setattr(reviews_mod, "fetch_judgeme_widget_reviews", fail_xhr)
    _forbid_bridged_fetch(monkeypatch)

    reviews, signal = fetch_product_reviews(
        html=JUDGEME_XHR_ONLY_PDP,
        product_url="https://example-store.com/products/soft-tee",
        base_url="https://example-store.com",
    )
    assert signal.vendor == "judgeme"
    assert len(reviews) == 1
    assert signal.notes == ""


def test_judgeme_falls_back_to_widget_xhr(monkeypatch):
    """v1 endpoint empty → widget-XHR runs with the myshopify domain and
    numeric product id extracted from the PDP HTML already in hand (no
    extra fetches against a possibly rate-limited store)."""
    monkeypatch.setattr(reviews_mod, "fetch_judgeme_reviews", lambda *a, **k: [])
    _forbid_bridged_fetch(monkeypatch)

    calls = {}

    def fake_xhr(myshopify_domain, product_id, limit=100, product_name=""):
        calls["args"] = (myshopify_domain, product_id)
        return [Review(body="soft", rating=5)]

    monkeypatch.setattr(reviews_mod, "fetch_judgeme_widget_reviews", fake_xhr)

    reviews, signal = fetch_product_reviews(
        html=JUDGEME_XHR_ONLY_PDP,
        product_url="https://example-store.com/products/soft-tee",
        base_url="https://example-store.com",
    )
    assert signal.vendor == "judgeme"
    assert calls["args"] == ("example-store.myshopify.com", "8734921155")
    assert len(reviews) == 1
    assert "widget-XHR" in signal.notes


def test_judgeme_refetches_pdp_when_meta_missing(monkeypatch):
    """HTML in hand lacks the ShopifyAnalytics meta (e.g. renderer stripped
    inline scripts) → recover the product id via ONE bridged PDP re-fetch
    that rides the same-domain rate-limit backoff (commit d2ecde3)."""
    monkeypatch.setattr(reviews_mod, "fetch_judgeme_reviews", lambda *a, **k: [])

    html_without_meta = JUDGEME_PDP_NO_IDENTIFIERS.replace(
        "<body>", "<body><script>Shopify.shop = 'example-store.myshopify.com';</script>"
    )
    bridged_urls = []

    def fake_bridged(url):
        bridged_urls.append(url)
        return JUDGEME_XHR_ONLY_PDP

    monkeypatch.setattr(reviews_mod, "_fetch_raw_html_bridged", fake_bridged)

    calls = {}

    def fake_xhr(myshopify_domain, product_id, limit=100, product_name=""):
        calls["args"] = (myshopify_domain, product_id)
        return [Review(body="soft", rating=5)]

    monkeypatch.setattr(reviews_mod, "fetch_judgeme_widget_reviews", fake_xhr)

    reviews, signal = fetch_product_reviews(
        html=html_without_meta,
        product_url="https://example-store.com/products/soft-tee",
        base_url="https://example-store.com",
    )
    assert bridged_urls == ["https://example-store.com/products/soft-tee"]
    assert calls["args"] == ("example-store.myshopify.com", "8734921155")
    assert len(reviews) == 1


def test_judgeme_fallback_records_reason_when_unavailable(monkeypatch):
    """No myshopify domain anywhere (page + homepage) → the tier is skipped
    and the reason lands in signal.notes so diagnostics stay honest."""
    monkeypatch.setattr(reviews_mod, "fetch_judgeme_reviews", lambda *a, **k: [])

    bridged_urls = []

    def fake_bridged(url):
        bridged_urls.append(url)
        return "<html>still no identifiers</html>"

    monkeypatch.setattr(reviews_mod, "_fetch_raw_html_bridged", fake_bridged)

    def fail_xhr(*args, **kwargs):
        raise AssertionError("widget-XHR must not run without a myshopify domain")

    monkeypatch.setattr(reviews_mod, "fetch_judgeme_widget_reviews", fail_xhr)

    reviews, signal = fetch_product_reviews(
        html=JUDGEME_PDP_NO_IDENTIFIERS,
        product_url="https://plainstore.example.com/products/soft-tee",
        base_url="https://plainstore.example.com",
    )
    assert reviews == []
    assert signal.vendor == "judgeme"
    assert "myshopify" in signal.notes
    # Homepage was consulted (via the bridged fetch) before giving up
    assert "https://plainstore.example.com" in bridged_urls


def test_judgeme_notes_when_both_tiers_empty(monkeypatch):
    monkeypatch.setattr(reviews_mod, "fetch_judgeme_reviews", lambda *a, **k: [])
    monkeypatch.setattr(reviews_mod, "fetch_judgeme_widget_reviews", lambda *a, **k: [])
    _forbid_bridged_fetch(monkeypatch)

    reviews, signal = fetch_product_reviews(
        html=JUDGEME_XHR_ONLY_PDP,
        product_url="https://example-store.com/products/soft-tee",
        base_url="https://example-store.com",
    )
    assert reviews == []
    assert "0" in signal.notes  # honest count, with the export escape hatch documented


# ── Diagnostics persistence (competitor bundle notes) ───────────────────────


def test_competitor_bundle_carries_judgeme_diagnostics(monkeypatch):
    """0-review bundles must persist the vendor-tier failure reason in
    `notes` (research/competitor-reviews/*.json), per pipeline-rules rule 6."""
    monkeypatch.setattr(
        competitor_mod, "firecrawl_map_urls",
        lambda url, limit=80: [f"{url.rstrip('/')}/products/thing"],
    )
    monkeypatch.setattr(
        competitor_mod, "_fetch_html", lambda url: "<div class='jdgm-widget'></div>"
    )

    diagnostic = (
        "judgeme: v1 widget endpoint empty; widget-XHR skipped — no "
        "*.myshopify.com domain in page or homepage HTML"
    )

    def fake_fetch(html, product_url="", base_url="", limit=100):
        return [], VendorSignal(vendor="judgeme", confidence="medium", notes=diagnostic)

    monkeypatch.setattr(competitor_mod, "fetch_product_reviews", fake_fetch)

    bundle = competitor_mod.pull_competitor_reviews(
        competitor_mod.Competitor(name="RivalCo", slug="rivalco", url="https://rival.example.com")
    )
    assert bundle.reviews == []
    assert bundle.vendor == "judgeme"
    assert diagnostic in bundle.notes
