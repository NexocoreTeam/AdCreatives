from strategy.reviews import extract_microdata_reviews, fetch_product_reviews

MICRODATA_PAGE = """
<html><body>
<div itemprop="review" itemscope itemtype="https://schema.org/Review">
  <meta itemprop="ratingValue" content="5">
  <meta itemprop="datePublished" content="2026-05-01">
  <span itemprop="author" itemscope itemtype="https://schema.org/Person">
    <span itemprop="name">Dana</span>
  </span>
  <p itemprop="reviewBody">Best espresso I've made at home.</p>
</div>
<div itemprop="review" itemscope>
  <span itemprop="ratingValue">4</span>
  <p itemprop="description">Solid but pricey.</p>
</div>
<div itemprop="review" itemscope>
  <p itemprop="reviewBody"></p>
</div>
</body></html>
"""


def test_extracts_microdata_reviews():
    reviews = extract_microdata_reviews(MICRODATA_PAGE)
    assert len(reviews) == 2
    assert reviews[0].body == "Best espresso I've made at home."
    assert reviews[0].rating == 5
    assert reviews[0].reviewer == "Dana"
    assert reviews[0].date == "2026-05-01"
    assert reviews[1].rating == 4
    assert reviews[1].body == "Solid but pricey."


def test_duplicates_and_empty_bodies_skipped():
    assert len(extract_microdata_reviews(MICRODATA_PAGE + MICRODATA_PAGE)) == 2


def test_no_itemprop_short_circuits():
    assert extract_microdata_reviews("<html><body>plain</body></html>") == []


def test_fetch_product_reviews_falls_back_to_microdata():
    reviews, signal = fetch_product_reviews(html=MICRODATA_PAGE)
    assert signal.vendor == "microdata"
    assert len(reviews) == 2


def test_sloppy_html_tolerated():
    sloppy = "<div itemprop='review' itemscope><p itemprop='reviewBody'>ok<br>fine</div>"
    reviews = extract_microdata_reviews(sloppy)
    assert len(reviews) == 1
    assert "ok" in reviews[0].body
