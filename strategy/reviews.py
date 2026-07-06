"""Review-widget detection + real review fetching.

Most Shopify stores load reviews via JavaScript widgets (Okendo, Yotpo,
Judge.me, Loox, Stamped). Static HTML scraping misses the actual review
content. This module detects which vendor a brand uses, extracts the
identifiers from the page HTML, and hits the vendor's public JSON API
to pull the real review text.

Output is normalized across vendors so downstream extraction (motion/
review-audit) gets a consistent shape regardless of where the reviews
came from.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

import httpx

from strategy.researcher import USER_AGENT, fetch_product_pages_with_raw


@dataclass
class Review:
    title: str = ""
    body: str = ""
    rating: int = 0
    reviewer: str = ""
    date: str = ""
    product_name: str = ""
    product_id: str = ""
    verified: bool = False
    helpful_count: int = 0


@dataclass
class VendorSignal:
    vendor: str   # okendo|yotpo|judgeme|loox|stamped|junip|reviewsio|shopify-native|fera|none
    identifiers: dict = field(default_factory=dict)
    confidence: str = "high"  # high | medium | low
    # Why a vendor path came up empty (or which fallback tier recovered it).
    # Callers persist this into research diagnostics — pipeline-rules rule 6:
    # 0-review outcomes must carry their reason, not vanish.
    notes: str = ""


def detect_review_vendor(html: str) -> VendorSignal:
    """Sniff the HTML for review-widget vendor signals + extract identifiers.

    Detection prefers strong widget signatures (staticw2.yotpo, jdgm-rev,
    junip-product-summary) over generic name mentions (which can be cookie
    banners, blog posts, or unrelated text).
    """

    # --- Okendo ---
    if re.search(r"oke-reviews|okendoSubscriberId|cdn\.okendo\.io", html, re.IGNORECASE):
        ids: dict = {}
        for pat in [
            r'okendoSubscriberId["\']?\s*[:=]\s*["\']([^"\']+)["\']',
            r'data-oke-store-id=["\']([^"\']+)["\']',
            r'subscriberId["\']?\s*:\s*["\']([0-9a-f-]{30,})["\']',
        ]:
            m = re.search(pat, html)
            if m:
                ids["subscriber_id"] = m.group(1)
                break
        return VendorSignal(
            vendor="okendo",
            identifiers=ids,
            confidence="high" if ids.get("subscriber_id") else "low",
        )

    # --- Yotpo ---  (require an actual widget signature, not just the word "yotpo")
    if re.search(
        r"staticw2\.yotpo\.com|yotpo-widget-instance|yotpo-main-widget"
        r"|cdn-widgetsrepository\.yotpo\.com",
        html, re.IGNORECASE,
    ):
        ids = {}
        for pat in [
            r'data-yotpo-app-key=["\']([^"\']+)["\']',
            r'yotpo[_-]app[_-]key["\']?\s*[:=]\s*["\']([A-Za-z0-9]+)["\']',
            r'staticw2\.yotpo\.com/[^"\']*?/([A-Za-z0-9]{20,})',
            # Yotpo v3 embeds carry the app key as the widget-loader GUID
            # (found live on crazy-rumors: no legacy staticw2 script, key
            # only present in the loader URL).
            r'cdn-widgetsrepository\.yotpo\.com/v1/loader/([A-Za-z0-9_-]{20,})',
        ]:
            m = re.search(pat, html)
            if m:
                ids["app_key"] = m.group(1)
                break
        # Yotpo uses Shopify product ID (the big number). Try several locations.
        for pat in [
            r'data-product-id=["\'](\d{10,})["\']',
            r'yotpo-product-id=["\'](\d{10,})["\']',
            r'"product_id"\s*:\s*["\']?(\d{10,})',
            r'"id"\s*:\s*(\d{12,})',
        ]:
            m = re.search(pat, html)
            if m:
                ids["product_id"] = m.group(1)
                break
        return VendorSignal(
            vendor="yotpo",
            identifiers=ids,
            confidence="high" if ids.get("app_key") else "low",
        )

    # --- Judge.me --- (require actual widget classes, not just "judge.me" mentions)
    if re.search(r"jdgm-rev|jdgm-widget|judge\.me/api|judge\.me/widget", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-shop-domain=["\']([^"\']+)["\']', html)
        if m:
            ids["shop_domain"] = m.group(1)
        return VendorSignal(vendor="judgeme", identifiers=ids, confidence="medium")

    # --- Loox --- (require widget script, not blog mentions)
    if re.search(r"loox\.io/widget|loox\.app/widget|loox-rating", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-loox-shop=["\']([^"\']+)["\']', html)
        if m:
            ids["shop_id"] = m.group(1)
        return VendorSignal(vendor="loox", identifiers=ids, confidence="low")

    # --- Stamped.io ---
    if re.search(r"stamped-product-reviews|stamped\.io/widget", html, re.IGNORECASE):
        return VendorSignal(vendor="stamped", confidence="low")

    # --- Junip ---
    if re.search(r"junip-product-summary|junip-product-review|junip\.co", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-junip-store-key=["\']([^"\']+)["\']', html)
        if m:
            ids["store_key"] = m.group(1)
        m = re.search(r'data-junip-product-id=["\']([^"\']+)["\']', html)
        if m:
            ids["product_id"] = m.group(1)
        return VendorSignal(
            vendor="junip",
            identifiers=ids,
            confidence="high" if ids.get("store_key") else "low",
        )

    # --- Reviews.io ---
    if re.search(r"widget\.reviews\.io|ruk-reviews-summary|reviewsio-(rating|product)", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-store=["\']([^"\']+)["\']', html)
        if m:
            ids["store_id"] = m.group(1)
        return VendorSignal(
            vendor="reviewsio",
            identifiers=ids,
            confidence="high" if ids.get("store_id") else "low",
        )

    # --- Native Shopify Product Reviews ---
    if re.search(r'spr-container|"shopify-product-reviews"|spr-reviews|spr-summary', html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-product-id=["\'](\d+)["\']', html)
        if m:
            ids["product_id"] = m.group(1)
        return VendorSignal(vendor="shopify-native", identifiers=ids, confidence="medium")

    # --- Fera.ai ---
    if re.search(r"fera\.ai/v3|app\.fera\.ai|fera-rating", html, re.IGNORECASE):
        return VendorSignal(vendor="fera", confidence="low")

    return VendorSignal(vendor="none", confidence="high")


OKENDO_API_BASE = "https://api.okendo.io/v1"


def _resolve_okendo_next_url(next_url: str | None) -> str | None:
    """Okendo's nextUrl is host-relative ('/stores/...') — without resolving
    it, pagination silently stops after page 1 (why Zoka's store feed only
    ever surfaced 20 reviews)."""
    if not next_url:
        return None
    if next_url.startswith("http"):
        return next_url
    return OKENDO_API_BASE + next_url


def _extract_okendo_product_id(html: str) -> str:
    """Pull the Shopify product ID Okendo's widget markup carries on a PDP."""
    for pat in (
        r'data-oke-reviews-product-id=["\']shopify-(\d+)',
        r'"productId"\s*:\s*"shopify-(\d+)',
        r'oke-reviews-product-id="shopify-(\d+)',
    ):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return ""


def fetch_okendo_product_reviews(
    subscriber_id: str,
    shopify_product_id: str,
    limit: int = 200,
) -> list[Review]:
    """Fetch reviews scoped to ONE product from Okendo's public API.

    The store-level feed only returns the most recent reviews across every
    SKU, which starves popular products (Zoka's Espresso Paladino has 158
    reviews; the store feed surfaced 5 of them). Product scoping fixes that.
    """
    if not subscriber_id or not shopify_product_id:
        return []
    start = (
        f"https://api.okendo.io/v1/stores/{subscriber_id}"
        f"/products/shopify-{shopify_product_id}/reviews?limit=20"
    )
    return _paginate_okendo_reviews(start, limit)


def fetch_okendo_store_reviews(subscriber_id: str, limit: int = 100) -> list[Review]:
    """Fetch reviews from Okendo's public store-level endpoint.

    Endpoint: https://api.okendo.io/v1/stores/{subscriberId}/reviews?limit=20
    Paginates via nextUrl up to `limit` reviews total. Returns most-recent first.
    """
    if not subscriber_id:
        return []
    url = f"https://api.okendo.io/v1/stores/{subscriber_id}/reviews?limit=20"
    return _paginate_okendo_reviews(url, limit)


def _paginate_okendo_reviews(url: str, limit: int) -> list[Review]:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    reviews: list[Review] = []
    pages = 0

    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        while url and len(reviews) < limit and pages < 10:
            try:
                resp = client.get(url)
            except (httpx.RequestError, httpx.TimeoutException):
                break
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except json.JSONDecodeError:
                break

            for r in data.get("reviews", []) or []:
                if r.get("status") and r.get("status") != "approved" and r.get("status") != "published":
                    # Some Okendo stores moderate reviews; skip non-approved
                    continue
                reviewer_data = r.get("reviewer", {}) or {}
                reviewer = (
                    reviewer_data.get("displayName")
                    if isinstance(reviewer_data, dict)
                    else str(reviewer_data)
                ) or ""
                reviews.append(
                    Review(
                        title=r.get("title", "") or "",
                        body=r.get("body", "") or "",
                        rating=int(r.get("rating") or 0),
                        reviewer=reviewer,
                        date=r.get("dateCreated", "") or "",
                        product_name=r.get("productName", "") or "",
                        product_id=str(r.get("productId", "") or ""),
                        verified=bool(r.get("isIncentivized") is False and r.get("status") == "published"),
                        helpful_count=int(r.get("helpfulCount") or 0),
                    )
                )

            url = _resolve_okendo_next_url(data.get("nextUrl"))
            pages += 1

    return reviews[:limit]


def fetch_yotpo_product_reviews(app_key: str, product_id: str, limit: int = 100) -> list[Review]:
    """Fetch reviews from Yotpo's public widget endpoint."""
    if not app_key or not product_id:
        return []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    url = (
        f"https://api.yotpo.com/v1/widget/{app_key}/products/{product_id}/reviews.json"
        f"?per_page={min(limit, 50)}&page=1"
    )
    reviews: list[Review] = []

    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
    except (httpx.RequestError, httpx.TimeoutException, json.JSONDecodeError):
        return []

    response = data.get("response") or {}
    raw_reviews = response.get("reviews") or []
    for r in raw_reviews:
        reviews.append(
            Review(
                title=r.get("title", "") or "",
                body=r.get("content", "") or "",
                rating=int(r.get("score") or 0),
                reviewer=r.get("user", {}).get("display_name", "") if isinstance(r.get("user"), dict) else "",
                date=r.get("created_at", "") or "",
                product_name="",  # not in this endpoint
                product_id=str(product_id),
                verified=bool(r.get("verified_buyer")),
                helpful_count=int(r.get("votes_up") or 0),
            )
        )
    return reviews


def fetch_judgeme_reviews(shop_domain: str, product_handle: str, limit: int = 100) -> list[Review]:
    """Fetch reviews from Judge.me's public widget endpoint.

    Returns HTML widget content; we strip + parse it.
    """
    if not shop_domain or not product_handle:
        return []

    headers = {"User-Agent": USER_AGENT}
    url = (
        f"https://judge.me/api/v1/widgets/product_review"
        f"?shop_domain={shop_domain}&handle={product_handle}&per_page={min(limit, 50)}&page=1"
    )
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
            resp = client.get(url)
            if resp.status_code != 200:
                return []
            data = resp.json()
    except (httpx.RequestError, httpx.TimeoutException, json.JSONDecodeError):
        return []

    widget_html = data.get("widget", "") or ""
    # Parse reviews from the widget HTML — Judge.me formats them in jdgm-rev divs
    review_blocks = re.findall(
        r"<div[^>]+jdgm-rev[^>]+>(.*?)</div>\s*</div>",
        widget_html,
        re.DOTALL,
    )

    reviews: list[Review] = []
    for block in review_blocks[:limit]:
        rating_m = re.search(r'data-score=["\'](\d)["\']', block)
        title_m = re.search(r"jdgm-rev__title[^>]*>([^<]+)<", block)
        body_m = re.search(r"jdgm-rev__body[^>]*>(.*?)<", block, re.DOTALL)
        reviewer_m = re.search(r"jdgm-rev__author[^>]*>([^<]+)<", block)
        reviews.append(
            Review(
                title=(title_m.group(1) if title_m else "").strip(),
                body=(body_m.group(1) if body_m else "").strip(),
                rating=int(rating_m.group(1)) if rating_m else 0,
                reviewer=(reviewer_m.group(1) if reviewer_m else "").strip(),
                date="",
                product_name=product_handle,
                product_id="",
            )
        )
    return reviews


# ── Judge.me widget-XHR fallback tier ───────────────────────────────────────
#
# Some Judge.me stores render reviews ONLY via the widget's runtime XHR:
# no review content in static or even JS-rendered PDP HTML, no public token
# on the page, and the classic v1 widget endpoint above returns nothing —
# found live on a 14K+-review Shopify store whose deep-dive reported 0 for
# every product. reviews_for_widget is the widget's own data source and
# needs only the *.myshopify.com domain + the numeric Shopify product id.

JUDGEME_WIDGET_API = "https://api.judge.me/reviews/reviews_for_widget"
_JUDGEME_WIDGET_PER_PAGE = 10


def _extract_myshopify_domain(html: str) -> str:
    """First *.myshopify.com domain in page HTML (Shopify.shop, CDN URLs,
    analytics payloads all carry it on any storefront page)."""
    m = re.search(r"([\w-]+\.myshopify\.com)", html or "")
    return m.group(1) if m else ""


def _extract_shopify_product_id(html: str) -> str:
    """Numeric Shopify product id from the ShopifyAnalytics meta on a PDP.

    This is the reliable source: /products/<handle>.js and /products.json
    can 404/500 on rate-limited stores while the PDP itself renders fine.
    """
    m = re.search(r'"product"\s*:\s*\{\s*"id"\s*:\s*(\d+)', html or "")
    return m.group(1) if m else ""


def _fetch_raw_html_bridged(url: str) -> str:
    """One-URL raw fetch riding the same-domain rate-limit bridging of
    researcher.fetch_product_pages_with_raw (4s/12s backoff): inside onboard
    the store just absorbed a burst of requests, so a plain one-shot GET here
    would fail exactly when this fallback is needed most."""
    if not url:
        return ""
    pages = fetch_product_pages_with_raw([url])
    return (pages.get(url) or {}).get("raw", "")


def _parse_judgeme_widget_html(
    fragment: str,
    product_name: str = "",
    product_id: str = "",
) -> list[Review]:
    """Parse reviews out of the `html` field of a reviews_for_widget response.

    Judge.me renders the widget server-side with single-quoted attributes:
    one `<div class='jdgm-rev ...'>` per review, rating as data-score on
    jdgm-rev__rating, ISO-ish timestamp in jdgm-rev__timestamp's
    data-content, body as <p> paragraphs inside jdgm-rev__body.
    """
    if not fragment:
        return []
    reviews: list[Review] = []
    # The trailing space in the split token keeps the widget shell
    # (jdgm-rev-widg) and inner elements (jdgm-rev__*) out of the blocks.
    for block in fragment.split("<div class='jdgm-rev ")[1:]:
        # Rest of the review div's opening tag — carries data-verified-buyer.
        head = block.split(">", 1)[0]
        rating_m = re.search(
            r"jdgm-rev__rating[^>]*?data-score=['\"](\d)['\"]", block
        ) or re.search(r"data-score=['\"](\d)['\"]", block)
        # ['\"\s] after the class name keeps jdgm-rev__author-wrapper from
        # matching before the actual author span.
        author_m = re.search(r"jdgm-rev__author['\"\s][^>]*?>([^<]*)<", block)
        title_m = re.search(r"jdgm-rev__title[^>]*?>([^<]*)<", block)
        date_m = re.search(
            r"jdgm-rev__timestamp[^>]*?data-content=['\"]([^'\"]+)['\"]", block
        )
        body = ""
        body_m = re.search(r"jdgm-rev__body[^>]*?>(.*?)</div>", block, re.DOTALL)
        if body_m:
            body = unescape(re.sub(r"<[^>]+>", " ", body_m.group(1)))
            body = re.sub(r"\s+", " ", body).strip()
        reviews.append(
            Review(
                title=unescape(title_m.group(1)).strip() if title_m else "",
                body=body,
                rating=int(rating_m.group(1)) if rating_m else 0,
                reviewer=unescape(author_m.group(1)).strip() if author_m else "",
                date=(date_m.group(1) if date_m else "")[:25],
                product_name=product_name,
                product_id=product_id,
                verified="data-verified-buyer='true'" in head
                or 'data-verified-buyer="true"' in head,
            )
        )
    return reviews


def fetch_judgeme_widget_reviews(
    myshopify_domain: str,
    shopify_product_id: str,
    limit: int = 100,
    product_name: str = "",
) -> list[Review]:
    """Fetch product-scoped reviews from Judge.me's widget runtime XHR.

    NOTE the api.judge.me host is required — the same path on judge.me
    returns 404. Response JSON: {html, total_count, page}; paginates until
    total_count is reached, an empty page, or `limit`.
    """
    if not myshopify_domain or not shopify_product_id:
        return []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    reviews: list[Review] = []
    page = 1
    max_pages = max(1, -(-limit // _JUDGEME_WIDGET_PER_PAGE))  # ceil

    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        while len(reviews) < limit and page <= max_pages:
            try:
                resp = client.get(
                    JUDGEME_WIDGET_API,
                    params={
                        "url": myshopify_domain,
                        "shop_domain": myshopify_domain,
                        "platform": "shopify",
                        "product_id": shopify_product_id,
                        "page": page,
                        "per_page": _JUDGEME_WIDGET_PER_PAGE,
                    },
                )
            except (httpx.RequestError, httpx.TimeoutException):
                break
            if resp.status_code != 200:
                break
            try:
                data = resp.json()
            except json.JSONDecodeError:
                break

            parsed = _parse_judgeme_widget_html(
                data.get("html") or "",
                product_name=product_name,
                product_id=str(shopify_product_id),
            )
            if not parsed:
                break  # empty page ends pagination even if total_count claims more
            reviews.extend(parsed)

            try:
                total_count = int(data.get("total_count") or 0)
            except (TypeError, ValueError):
                total_count = 0
            if total_count and len(reviews) >= total_count:
                break
            page += 1

    return reviews[:limit]


def _fetch_judgeme_with_fallback(
    signal: VendorSignal,
    html: str,
    product_url: str,
    base_url: str,
    limit: int,
) -> list[Review]:
    """Judge.me in two tiers: classic v1 widget endpoint first, then the
    widget's runtime XHR when the primary yields 0 (mirrors the Okendo
    product-scoped → store-level fallback shape).

    Identifiers already in the HTML in hand are preferred; bridged re-fetches
    (homepage for the myshopify domain, PDP for the product id) only run when
    they're missing. Every 0-review outcome writes its reason to signal.notes.
    """
    from urllib.parse import urlparse

    shop_domain = signal.identifiers.get("shop_domain") or ""
    if not shop_domain and base_url:
        shop_domain = urlparse(base_url).netloc
    handle = ""
    if product_url:
        m = re.search(r"/products/([^/?#]+)", product_url)
        if m:
            handle = m.group(1)

    reviews: list[Review] = []
    primary_note = "v1 widget endpoint skipped (no product handle in URL)"
    if shop_domain and handle:
        reviews = fetch_judgeme_reviews(shop_domain, handle, limit=limit)
        primary_note = "v1 widget endpoint empty"
    if reviews:
        return reviews

    myshopify = _extract_myshopify_domain(html)
    if not myshopify and shop_domain.endswith(".myshopify.com"):
        myshopify = shop_domain
    if not myshopify and base_url:
        myshopify = _extract_myshopify_domain(_fetch_raw_html_bridged(base_url))
    if not myshopify:
        signal.notes = (
            f"judgeme: {primary_note}; widget-XHR skipped — no "
            f"*.myshopify.com domain in page or homepage HTML"
        )
        return []

    product_id = _extract_shopify_product_id(html)
    if not product_id and product_url and "/products/" in product_url:
        product_id = _extract_shopify_product_id(_fetch_raw_html_bridged(product_url))
    if not product_id:
        signal.notes = (
            f"judgeme: {primary_note}; widget-XHR skipped — no Shopify numeric "
            f"product id in PDP HTML (ShopifyAnalytics meta missing)"
        )
        return []

    reviews = fetch_judgeme_widget_reviews(
        myshopify, product_id, limit=limit, product_name=handle
    )
    signal.identifiers.setdefault("shop_domain", myshopify)
    signal.identifiers["product_id"] = product_id
    if reviews:
        signal.confidence = "high"
        signal.notes = (
            f"judgeme: {primary_note}; recovered {len(reviews)} review(s) via "
            f"widget-XHR (api.judge.me reviews_for_widget)"
        )
    else:
        signal.notes = (
            f"judgeme: {primary_note}; widget-XHR also returned 0 — store may "
            f"have no reviews for this product, or reviews are token-locked; "
            f"for a client-owned store, export from the Judge.me dashboard "
            f"into voc/ instead (pipeline-rules rule 6)"
        )
    return reviews


def _iter_jsonld_nodes(data):
    """Yield dict nodes from a JSON-LD document (handles lists and @graph)."""
    stack = [data]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            yield node
            graph = node.get("@graph")
            if isinstance(graph, list):
                stack.extend(graph)


def _jsonld_reviews_of(node: dict) -> list[dict]:
    """Review dicts carried by one JSON-LD node (itself, or its review field)."""
    node_type = node.get("@type", "")
    types = node_type if isinstance(node_type, list) else [node_type]
    if "Review" in types:
        return [node]
    reviews = node.get("review") or node.get("reviews") or []
    if isinstance(reviews, dict):
        reviews = [reviews]
    return [r for r in reviews if isinstance(r, dict)]


def _review_from_jsonld(raw: dict, product_name: str = "") -> Review:
    body = str(raw.get("reviewBody") or raw.get("description") or "").strip()
    rating_node = raw.get("reviewRating") or {}
    rating_raw = rating_node.get("ratingValue") if isinstance(rating_node, dict) else rating_node
    try:
        rating = int(round(float(rating_raw))) if rating_raw is not None else 0
    except (TypeError, ValueError):
        rating = 0
    author = raw.get("author")
    if isinstance(author, list):
        author = author[0] if author else ""
    if isinstance(author, dict):
        author = author.get("name", "")
    item = raw.get("itemReviewed")
    if isinstance(item, dict) and item.get("name"):
        product_name = str(item["name"])
    return Review(
        title=str(raw.get("name") or raw.get("headline") or "").strip(),
        body=body,
        rating=rating,
        reviewer=str(author or "").strip(),
        date=str(raw.get("datePublished") or "")[:25],
        product_name=product_name,
    )


def extract_jsonld_reviews(html: str, limit: int = 100) -> list[Review]:
    """Vendor-independent fallback: parse schema.org Review objects from
    JSON-LD blocks in the page HTML.

    Many review apps (Junip, Stamped, Loox, Reviews.io) and custom
    storefronts render reviews server-side for SEO even when their widget
    API isn't public — this recovers those with zero extra network calls.
    Aggregate-only markup (AggregateRating without review bodies) yields
    nothing, by design.
    """
    if not html:
        return []
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    reviews: list[Review] = []
    seen: set[tuple[str, str]] = set()
    for raw_block in blocks:
        try:
            data = json.loads(raw_block.strip())
        except json.JSONDecodeError:
            continue  # some themes emit broken JSON-LD; skip that block
        for node in _iter_jsonld_nodes(data):
            node_name = str(node.get("name", "") or "")
            for raw_review in _jsonld_reviews_of(node):
                review = _review_from_jsonld(raw_review, product_name=node_name)
                if not review.body:
                    continue
                key = (review.body[:80], review.reviewer)
                if key in seen:
                    continue
                seen.add(key)
                reviews.append(review)
                if len(reviews) >= limit:
                    return reviews
    return reviews


class _MicrodataReviewParser(HTMLParser):
    """Collect schema.org microdata reviews (itemprop markup) from HTML.

    Complements the JSON-LD extractor: some themes and widgets annotate the
    rendered DOM (`itemprop="review"` / `reviewBody` / `ratingValue`)
    without emitting a JSON-LD block. Especially relevant now that
    competitor pages are fetched JS-rendered via Firecrawl — widget output
    exists in the DOM even when the vendor has no public API.
    """

    VOID_TAGS = frozenset(
        {"meta", "br", "img", "input", "hr", "link", "source", "wbr", "area", "col", "embed", "track"}
    )

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.reviews: list[dict] = []
        self._depth = 0
        self._review_depth: int | None = None
        self._current: dict | None = None
        self._capture_key: str | None = None
        self._capture_depth: int | None = None
        self._author_depth: int | None = None

    def handle_startendtag(self, tag, attrs):
        # Self-closing tags carry attrs but no scope — treat like voids.
        self._handle_void(dict(attrs))

    def _handle_void(self, attrs_dict: dict) -> None:
        if self._current is None:
            return
        itemprop = attrs_dict.get("itemprop", "")
        content = attrs_dict.get("content", "")
        if not itemprop or not content:
            return
        if itemprop == "ratingValue":
            self._current.setdefault("ratingValue", content)
        elif itemprop == "datePublished":
            self._current.setdefault("datePublished", content)
        elif itemprop == "author":
            self._current.setdefault("reviewer", content)
        elif itemprop == "name" and self._author_depth is not None:
            self._current.setdefault("reviewer", content)

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag in self.VOID_TAGS:
            self._handle_void(attrs_dict)
            return
        self._depth += 1
        itemprop = attrs_dict.get("itemprop", "")

        if self._current is None:
            if itemprop == "review":
                self._review_depth = self._depth
                self._current = {}
            return

        if itemprop == "author":
            self._author_depth = self._depth
        elif itemprop in ("reviewBody", "description"):
            self._capture_key = "body"
            self._capture_depth = self._depth
            self._current.setdefault("body", "")
        elif itemprop == "name":
            self._capture_key = (
                "reviewer" if self._author_depth is not None else "title"
            )
            self._capture_depth = self._depth
            self._current.setdefault(self._capture_key, "")
        elif itemprop == "ratingValue":
            self._capture_key = "ratingValue"
            self._capture_depth = self._depth
            self._current.setdefault("ratingValue", "")

    def handle_data(self, data):
        if self._current is not None and self._capture_key:
            self._current[self._capture_key] = (
                self._current.get(self._capture_key, "") + data
            )

    def handle_endtag(self, tag):
        if tag in self.VOID_TAGS:
            return
        if self._capture_depth is not None and self._depth == self._capture_depth:
            self._capture_key = None
            self._capture_depth = None
        if self._author_depth is not None and self._depth == self._author_depth:
            self._author_depth = None
        if self._review_depth is not None and self._depth == self._review_depth:
            if self._current is not None:
                self.reviews.append(self._current)
            self._current = None
            self._review_depth = None
        self._depth -= 1

    def close(self):
        super().close()
        # Sloppy HTML (unclosed tags) can leave the last review dangling.
        if self._current is not None:
            self.reviews.append(self._current)
            self._current = None


def extract_microdata_reviews(html: str, limit: int = 100) -> list[Review]:
    """Parse schema.org microdata (itemprop) reviews out of page HTML."""
    if not html or "itemprop" not in html:
        return []
    parser = _MicrodataReviewParser()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return []

    reviews: list[Review] = []
    seen: set[tuple[str, str]] = set()
    for raw in parser.reviews:
        body = (raw.get("body") or "").strip()
        if not body:
            continue
        try:
            rating = int(round(float(raw.get("ratingValue", "") or 0)))
        except (TypeError, ValueError):
            rating = 0
        reviewer = (raw.get("reviewer") or "").strip()
        key = (body[:80], reviewer)
        if key in seen:
            continue
        seen.add(key)
        reviews.append(Review(
            title=(raw.get("title") or "").strip(),
            body=body,
            rating=rating,
            reviewer=reviewer,
            date=(raw.get("datePublished") or "").strip()[:25],
        ))
        if len(reviews) >= limit:
            break
    return reviews


def fetch_product_reviews(
    html: str,
    product_url: str = "",
    base_url: str = "",
    limit: int = 100,
) -> tuple[list[Review], VendorSignal]:
    """Detect vendor and fetch reviews. Returns (reviews, vendor_signal).

    Vendor API first (Okendo / Yotpo / Judge.me), then JSON-LD markup as a
    vendor-independent fallback — covers widgets without a public fetcher
    (Stamped, Junip, Loox, Reviews.io, ...) and custom review systems. When
    JSON-LD supplies the reviews on a page with no detected widget, the
    returned signal has vendor="jsonld".
    """
    signal = detect_review_vendor(html)
    reviews: list[Review] = []

    if signal.vendor == "okendo" and signal.identifiers.get("subscriber_id"):
        subscriber_id = signal.identifiers["subscriber_id"]
        okendo_product_id = _extract_okendo_product_id(html)
        if okendo_product_id:
            reviews = fetch_okendo_product_reviews(
                subscriber_id, okendo_product_id, limit=limit
            )
        if not reviews:
            reviews = fetch_okendo_store_reviews(subscriber_id, limit=limit)

    elif signal.vendor == "yotpo":
        app_key = signal.identifiers.get("app_key")
        product_id = signal.identifiers.get("product_id")
        if app_key and product_id:
            reviews = fetch_yotpo_product_reviews(app_key, product_id, limit=limit)

    elif signal.vendor == "judgeme":
        reviews = _fetch_judgeme_with_fallback(
            signal, html, product_url, base_url, limit
        )

    if reviews:
        return reviews, signal

    jsonld_reviews = extract_jsonld_reviews(html, limit=limit)
    if jsonld_reviews:
        if signal.vendor == "none":
            signal = VendorSignal(vendor="jsonld", identifiers={}, confidence="medium")
        return jsonld_reviews, signal

    microdata_reviews = extract_microdata_reviews(html, limit=limit)
    if microdata_reviews:
        if signal.vendor == "none":
            signal = VendorSignal(vendor="microdata", identifiers={}, confidence="medium")
        return microdata_reviews, signal

    return [], signal


def filter_reviews_by_product(reviews: list[Review], product_name: str) -> list[Review]:
    """Loose match against product name to filter store-level review lists.

    Uses substring matching in both directions (review.product_name in product.name
    or vice versa) since vendor product names don't always match brand product names
    exactly.
    """
    if not product_name:
        return reviews
    target = re.sub(r"[^\w\s]", "", product_name.lower())
    target_words = set(target.split())
    matched: list[Review] = []
    for r in reviews:
        if not r.product_name:
            continue
        rp = re.sub(r"[^\w\s]", "", r.product_name.lower())
        rp_words = set(rp.split())
        # Match if review product name shares ≥40% of target words OR target product name
        # is a substring of review product name (or vice versa)
        if (
            target in rp
            or rp in target
            or (target_words and len(target_words & rp_words) >= max(2, len(target_words) // 2))
        ):
            matched.append(r)
    return matched or reviews  # if no match, return all (better than nothing)


def save_reviews_as_voc(client_slug: str, vendor: str, reviews: list[Review]) -> Path:
    """Save reviews as a JSON file in the voc/ folder so mine-voc can use them later."""
    voc_dir = Path("clients") / client_slug / "voc"
    voc_dir.mkdir(parents=True, exist_ok=True)
    path = voc_dir / f"{vendor}-reviews.json"

    payload = [
        {
            "rating": r.rating,
            "reviewer": r.reviewer,
            "title": r.title,
            "text": r.body,
            "product": r.product_name,
            "date": r.date,
            "verified": r.verified,
            "source": vendor,
        }
        for r in reviews
        if r.body  # skip text-less reviews (review-audit will discard them anyway)
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return path
