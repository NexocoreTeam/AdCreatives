import strategy.amazon_suggest as suggest_mod
from strategy.amazon_suggest import candidates_from_hits, suggest_amazon_candidates
from strategy.exa_research import ExaHit, ExaQueryResult


def _hit(url="", text="", title=""):
    return ExaHit(
        url=url, title=title, published_date=None, author=None,
        score=None, text=text, domain="",
    )


def test_candidates_extracted_from_urls_and_text():
    hits = [
        _hit(url="https://www.amazon.com/Stumptown-Hair-Bender/dp/B00AR0W5VE", title="Hair Bender"),
        _hit(
            url="https://roundup-blog.com/best-coffee",
            text="Buy it at https://www.amazon.com/gp/product/B01N5UPTZS today",
            title="Best coffee roundup",
        ),
    ]
    candidates = candidates_from_hits(hits)
    assert [c["asin"] for c in candidates] == ["B00AR0W5VE", "B01N5UPTZS"]
    assert candidates[0]["url"] == "https://www.amazon.com/dp/B00AR0W5VE"


def test_candidates_deduped_by_asin():
    hits = [
        _hit(url="https://www.amazon.com/x/dp/B00AR0W5VE"),
        _hit(text="see https://amazon.com/dp/B00AR0W5VE?th=1"),
    ]
    assert len(candidates_from_hits(hits)) == 1


def test_scoped_search_refusal_falls_back_to_unfiltered(monkeypatch):
    calls = []

    def fake_run_query(query):
        calls.append(query.label)
        if query.include_domains:
            raise ValueError("SOURCE_NOT_AVAILABLE")
        return ExaQueryResult(
            query=query, fetched_at="t",
            results=[_hit(url="https://www.amazon.com/Stumptown-Coffee/dp/B00AR0W5VE", title="Stumptown Coffee Roasters Hair Bender")],
        )

    monkeypatch.setattr(suggest_mod, "run_query", fake_run_query)
    candidates = suggest_amazon_candidates("Stumptown Coffee Roasters")
    assert len(calls) == 2
    assert candidates[0]["asin"] == "B00AR0W5VE"


def test_scoped_search_success_skips_fallback(monkeypatch):
    calls = []

    def fake_run_query(query):
        calls.append(query.label)
        return ExaQueryResult(
            query=query, fetched_at="t",
            results=[_hit(url="https://www.amazon.com/Stumptown-Coffee/dp/B00AR0W5VE", title="Stumptown Coffee Roasters Hair Bender")],
        )

    monkeypatch.setattr(suggest_mod, "run_query", fake_run_query)
    suggest_amazon_candidates("Stumptown Coffee Roasters")
    assert len(calls) == 1


def test_brand_token_filter_drops_noise_candidates():
    """Found live on expand-furniture: 8 of 12 candidates were books, watches
    and generic hardware the operator had to hand-reject."""
    hits = [
        _hit(url="https://www.amazon.com/Apple-Watch-Series/dp/B0CBVX91KR",
             title="Apple Watch Series 9"),
        _hit(url="https://www.amazon.com/dp/B0D5BWRDSP",
             title="Transformer Table - Solid Wood Extendable Dining Table"),
    ]
    kept = candidates_from_hits(hits, brand_name="Transformer Table")
    assert [c["asin"] for c in kept] == ["B0D5BWRDSP"]


def test_no_brand_name_keeps_everything():
    hits = [_hit(url="https://www.amazon.com/dp/B0CBVX91KR", title="Anything")]
    assert len(candidates_from_hits(hits)) == 1


def test_short_brand_falls_back_to_full_name():
    hits = [
        _hit(url="https://www.amazon.com/dp/B07H476RHB", title="Random publisher book"),
        _hit(url="https://www.amazon.com/dp/B07H476AAA", title="Clei wall bed system"),
    ]
    kept = candidates_from_hits(hits, brand_name="Clei")
    assert [c["asin"] for c in kept] == ["B07H476AAA"]
