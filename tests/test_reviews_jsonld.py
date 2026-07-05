import json

from strategy.reviews import extract_jsonld_reviews, fetch_product_reviews


def _page(payload) -> str:
    return (
        "<html><head><script type=\"application/ld+json\">"
        + json.dumps(payload)
        + "</script></head><body>coffee</body></html>"
    )


PRODUCT_WITH_REVIEWS = {
    "@context": "https://schema.org",
    "@type": "Product",
    "name": "Espresso Blend",
    "review": [
        {
            "@type": "Review",
            "reviewBody": "Best espresso I've had at home.",
            "reviewRating": {"@type": "Rating", "ratingValue": "5"},
            "author": {"@type": "Person", "name": "Dana"},
            "datePublished": "2026-05-01",
        },
        {
            "@type": "Review",
            "reviewBody": "Solid but pricey.",
            "reviewRating": {"@type": "Rating", "ratingValue": 4.0},
            "author": "Sam",
        },
    ],
}


def test_extracts_reviews_from_product_node():
    reviews = extract_jsonld_reviews(_page(PRODUCT_WITH_REVIEWS))
    assert len(reviews) == 2
    assert reviews[0].body == "Best espresso I've had at home."
    assert reviews[0].rating == 5
    assert reviews[0].reviewer == "Dana"
    assert reviews[0].product_name == "Espresso Blend"
    assert reviews[1].rating == 4


def test_extracts_from_graph_wrapper():
    graph = {"@context": "https://schema.org", "@graph": [PRODUCT_WITH_REVIEWS]}
    reviews = extract_jsonld_reviews(_page(graph))
    assert len(reviews) == 2


def test_broken_jsonld_block_is_skipped():
    html = (
        "<script type=\"application/ld+json\">{not json,}</script>"
        + _page(PRODUCT_WITH_REVIEWS)
    )
    assert len(extract_jsonld_reviews(html)) == 2


def test_aggregate_only_markup_yields_nothing():
    aggregate = {
        "@type": "Product",
        "name": "Espresso Blend",
        "aggregateRating": {"@type": "AggregateRating", "ratingValue": "4.9", "reviewCount": 158},
    }
    assert extract_jsonld_reviews(_page(aggregate)) == []


def test_duplicate_reviews_deduped_across_blocks():
    html = _page(PRODUCT_WITH_REVIEWS) + _page(PRODUCT_WITH_REVIEWS)
    assert len(extract_jsonld_reviews(html)) == 2


def test_limit_respected():
    assert len(extract_jsonld_reviews(_page(PRODUCT_WITH_REVIEWS), limit=1)) == 1


def test_fetch_product_reviews_falls_back_to_jsonld():
    """vendor:none pages with server-rendered reviews must still yield data
    (Zoka issue #4 — files created with reviews: [])."""
    reviews, signal = fetch_product_reviews(html=_page(PRODUCT_WITH_REVIEWS))
    assert signal.vendor == "jsonld"
    assert len(reviews) == 2


def test_fetch_product_reviews_no_widget_no_jsonld():
    reviews, signal = fetch_product_reviews(html="<html><body>plain page</body></html>")
    assert reviews == []
    assert signal.vendor == "none"
