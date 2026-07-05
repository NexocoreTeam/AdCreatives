import strategy.reviews as reviews_mod
from strategy.reviews import Review, _extract_okendo_product_id, fetch_product_reviews

OKENDO_PDP = """<html><head>
<script src="https://cdn.okendo.io/widget.js"></script>
<script>okendoSubscriberId = "a0f283eb-1234-5678-9abc-def012345678";</script>
</head><body>
<div data-oke-reviews-product-id="shopify-461043241"></div>
</body></html>"""


def test_extract_okendo_product_id():
    assert _extract_okendo_product_id(OKENDO_PDP) == "461043241"
    assert _extract_okendo_product_id("<html></html>") == ""


def test_okendo_prefers_product_scoped_endpoint(monkeypatch):
    """The store-level feed starves popular products (Zoka: 5 of 158 reviews
    surfaced) — a PDP with a product ID must use the product-scoped endpoint."""
    calls = {}

    def fake_product(subscriber_id, product_id, limit=200):
        calls["args"] = (subscriber_id, product_id)
        return [Review(body="great", rating=5)]

    def fail_store(*args, **kwargs):
        raise AssertionError("store-level endpoint must not be used when product-scoped works")

    monkeypatch.setattr(reviews_mod, "fetch_okendo_product_reviews", fake_product)
    monkeypatch.setattr(reviews_mod, "fetch_okendo_store_reviews", fail_store)

    reviews, signal = fetch_product_reviews(html=OKENDO_PDP)
    assert signal.vendor == "okendo"
    assert calls["args"][1] == "461043241"
    assert len(reviews) == 1


def test_okendo_next_url_resolution():
    from strategy.reviews import _resolve_okendo_next_url

    assert _resolve_okendo_next_url(None) is None
    assert _resolve_okendo_next_url("") is None
    assert (
        _resolve_okendo_next_url("/stores/abc/reviews?limit=20")
        == "https://api.okendo.io/v1/stores/abc/reviews?limit=20"
    )
    assert (
        _resolve_okendo_next_url("https://api.okendo.io/v1/stores/abc/reviews")
        == "https://api.okendo.io/v1/stores/abc/reviews"
    )


def test_okendo_falls_back_to_store_level(monkeypatch):
    monkeypatch.setattr(reviews_mod, "fetch_okendo_product_reviews", lambda *a, **k: [])
    monkeypatch.setattr(
        reviews_mod, "fetch_okendo_store_reviews",
        lambda subscriber_id, limit=100: [Review(body="ok", rating=4)],
    )
    reviews, signal = fetch_product_reviews(html=OKENDO_PDP)
    assert signal.vendor == "okendo"
    assert len(reviews) == 1
