from strategy.reviews import detect_review_vendor

YOTPO_V3_PDP = """<html><head>
<script src="https://cdn-widgetsrepository.yotpo.com/v1/loader/lh6gyFV6uKBk7WHfIcafanP1nqCbNIsFJ4DEUfAF?languageCode=en" async></script>
</head><body>
<div data-yotpo-instance-id="123" data-yotpo-product-id="6855031619666"></div>
<meta property="product" content='{"product_id": 6855031619666}'>
</body></html>"""


def test_yotpo_v3_loader_guid_detected_as_app_key():
    """Modern Yotpo installs have no staticw2 script — the app key lives in
    the widget-loader URL (found live on crazy-rumors, 0 -> 10 reviews)."""
    signal = detect_review_vendor(YOTPO_V3_PDP)
    assert signal.vendor == "yotpo"
    assert signal.identifiers.get("app_key", "").startswith("lh6gyFV6")


def test_legacy_yotpo_still_detected():
    legacy = '<script src="https://staticw2.yotpo.com/AbCdEfGhIjKlMnOpQrSt12345/widget.js"></script>'
    signal = detect_review_vendor(legacy)
    assert signal.vendor == "yotpo"
    assert signal.identifiers.get("app_key") == "AbCdEfGhIjKlMnOpQrSt12345"
