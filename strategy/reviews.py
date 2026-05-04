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
from pathlib import Path

import httpx

from strategy.researcher import USER_AGENT


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
    vendor: str   # "okendo" | "yotpo" | "judgeme" | "loox" | "stamped" | "none"
    identifiers: dict = field(default_factory=dict)
    confidence: str = "high"  # high | medium | low


def detect_review_vendor(html: str) -> VendorSignal:
    """Sniff the HTML for review-widget vendor signals + extract identifiers."""

    # --- Okendo ---
    if re.search(r"okendo\.io|oke-reviews|okendoSubscriberId", html, re.IGNORECASE):
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

    # --- Yotpo ---
    if re.search(r"yotpo\.com|yotpo-widget|staticw2\.yotpo\.com", html, re.IGNORECASE):
        ids = {}
        for pat in [
            r'data-yotpo-app-key=["\']([^"\']+)["\']',
            r'yotpo[_-]app[_-]key["\']?\s*[:=]\s*["\']([A-Za-z0-9]+)["\']',
            r'staticw2\.yotpo\.com/[^"\']*?/([A-Za-z0-9]{20,})',
        ]:
            m = re.search(pat, html)
            if m:
                ids["app_key"] = m.group(1)
                break
        # Yotpo uses Shopify product ID (the big number)
        m = re.search(r'"id"\s*:\s*(\d{12,})', html)
        if m:
            ids["product_id"] = m.group(1)
        return VendorSignal(
            vendor="yotpo",
            identifiers=ids,
            confidence="high" if ids.get("app_key") else "low",
        )

    # --- Judge.me ---
    if re.search(r"judge\.me|jdgm-|judgeme-", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-shop-domain=["\']([^"\']+)["\']', html)
        if m:
            ids["shop_domain"] = m.group(1)
        # Product handle is in URL
        return VendorSignal(vendor="judgeme", identifiers=ids, confidence="medium")

    # --- Loox ---
    if re.search(r"loox\.io|loox-rating", html, re.IGNORECASE):
        ids = {}
        m = re.search(r'data-loox-shop=["\']([^"\']+)["\']', html)
        if m:
            ids["shop_id"] = m.group(1)
        return VendorSignal(vendor="loox", identifiers=ids, confidence="low")

    # --- Stamped.io ---
    if re.search(r"stamped\.io|stamped-product-reviews", html, re.IGNORECASE):
        return VendorSignal(vendor="stamped", confidence="low")

    return VendorSignal(vendor="none", confidence="high")


def fetch_okendo_store_reviews(subscriber_id: str, limit: int = 100) -> list[Review]:
    """Fetch reviews from Okendo's public store-level endpoint.

    Endpoint: https://api.okendo.io/v1/stores/{subscriberId}/reviews?limit=20
    Paginates via nextUrl up to `limit` reviews total. Returns most-recent first.
    """
    if not subscriber_id:
        return []

    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    url = f"https://api.okendo.io/v1/stores/{subscriber_id}/reviews?limit=20"
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

            url = data.get("nextUrl") or None
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


def fetch_product_reviews(
    html: str,
    product_url: str = "",
    base_url: str = "",
    limit: int = 100,
) -> tuple[list[Review], VendorSignal]:
    """Detect vendor and fetch reviews. Returns (reviews, vendor_signal)."""
    signal = detect_review_vendor(html)

    if signal.vendor == "okendo" and signal.identifiers.get("subscriber_id"):
        return fetch_okendo_store_reviews(signal.identifiers["subscriber_id"], limit=limit), signal

    if signal.vendor == "yotpo":
        app_key = signal.identifiers.get("app_key")
        product_id = signal.identifiers.get("product_id")
        if app_key and product_id:
            return fetch_yotpo_product_reviews(app_key, product_id, limit=limit), signal

    if signal.vendor == "judgeme":
        shop_domain = signal.identifiers.get("shop_domain")
        if not shop_domain and base_url:
            from urllib.parse import urlparse
            shop_domain = urlparse(base_url).netloc
        handle = ""
        if product_url:
            m = re.search(r"/products/([^/?#]+)", product_url)
            if m:
                handle = m.group(1)
        if shop_domain and handle:
            return fetch_judgeme_reviews(shop_domain, handle, limit=limit), signal

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
