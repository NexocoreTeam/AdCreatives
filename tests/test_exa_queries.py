from strategy.exa_queries import (
    cache_stem,
    competitive_queries_for_brand,
    slugify,
)


def test_slugify_basic():
    assert slugify("Zoka Coffee") == "zoka-coffee"
    assert slugify("Stumptown Coffee Roasters!") == "stumptown-coffee-roasters"
    assert slugify("  ") == ""


def test_competitive_queries_five_per_brand():
    queries = competitive_queries_for_brand(
        own_brand="Zoka Coffee",
        competitor_names=["Stumptown Coffee Roasters"],
    )
    assert len(queries) == 10

    labels = [q.label for q in queries]
    for expected in (
        "web-zoka-coffee-love",
        "web-zoka-coffee-mixed",
        "web-zoka-coffee-complaints",
        "reddit-zoka-coffee-honest",
        "trustpilot-zoka-coffee",
        "web-stumptown-coffee-roasters-love",
        "reddit-stumptown-coffee-roasters-honest",
    ):
        assert expected in labels


def test_reddit_and_trustpilot_domain_scoping():
    queries = competitive_queries_for_brand("Zoka Coffee", [])
    by_label = {q.label: q for q in queries}
    assert by_label["reddit-zoka-coffee-honest"].include_domains == ["reddit.com"]
    assert by_label["trustpilot-zoka-coffee"].include_domains == ["trustpilot.com"]


def test_cache_stem_matches_label_slug():
    queries = competitive_queries_for_brand("Zoka Coffee", ["Onyx Coffee Lab"])
    for q in queries:
        stem = cache_stem(q.label)
        assert stem  # never empty
        assert stem == slugify(q.label)
