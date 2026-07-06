import strategy.competitor_research as cr
from strategy.competitor_research import Competitor, pull_competitor_reviews
from strategy.reviews import Review, VendorSignal


def test_raw_retry_recovers_identifiers_dropped_by_rendering(monkeypatch):
    """Firecrawl-rendered DOM can drop script-embedded vendor identifiers
    (found live on Elevated Faith: Okendo subscriberId in raw source only)."""
    rendered = "<html><div class='oke-reviews-widget'>stars only</div></html>"
    raw = '<html><script>subscriberId:"71f162e4-7fa0-4a3d-8c2b-2c8a6568a1a7"</script><div class="oke-reviews"></div></html>'

    monkeypatch.setattr(cr, "firecrawl_map_urls", lambda url, limit=80: [
        "https://example.com/products/a",
    ])
    monkeypatch.setattr(cr, "_fetch_html", lambda url: rendered)
    monkeypatch.setattr(cr, "_fetch_html_raw", lambda url: raw)

    calls = []

    def fake_fetch(html="", product_url="", base_url="", limit=100):
        if "subscriberId" in html:
            calls.append("raw")
            return (
                [Review(body="love it", rating=5)],
                VendorSignal(vendor="okendo",
                             identifiers={"subscriber_id": "71f162e4"},
                             confidence="high"),
            )
        calls.append("rendered")
        return [], VendorSignal(vendor="okendo", identifiers={}, confidence="low")

    monkeypatch.setattr(cr, "fetch_product_reviews", fake_fetch)

    bundle = pull_competitor_reviews(Competitor(
        name="Elevated Faith", slug="elevated-faith", url="https://example.com",
    ))
    assert calls == ["rendered", "raw"]
    assert bundle.vendor == "okendo"
    assert len(bundle.reviews) == 1
