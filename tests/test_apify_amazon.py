"""Amazon review scraping through junglee/amazon-reviews-scraper.

The actor reads the star tier from `filterByRatings` and the order from
`sort`. The code used to send `filterByStar` and `sortBy`, which the actor
ignores, so every 5/3/1 pull returned the same unfiltered reviews three
times and paid for each copy.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

import strategy.apify_amazon as apify_amazon
from strategy.amazon_tiers import (
    pull_failed,
    rarest_first,
    saved_tier_failed,
    saved_tier_unfiltered,
)
from strategy.apify_amazon import AmazonReviewBundle, scrape_amazon_reviews, star_filter_ignored
from strategy.reviews import Review

REPO_ROOT = Path(__file__).resolve().parents[1]

PRODUCT_URL = "https://www.amazon.com/dp/B000TEST01"
SECOND_URL = "https://www.amazon.com/dp/B000TEST02"
TIER_RATING = {"fiveStar": 5, "fourStar": 4, "threeStar": 3, "twoStar": 2, "oneStar": 1}


def _item(rating: int, n: int) -> dict:
    return {
        "reviewTitle": f"title {n}",
        "reviewDescription": f"body {n}",
        "ratingScore": rating,
        "userId": f"user{n}",
        "date": "2026-01-01",
        "product": {"title": "Test Product"},
    }


class FakeApify:
    """Stands in for ApifyClient: records each run's input, answers with a status and items."""

    def __init__(self, items_for=lambda run_input: [], status="SUCCEEDED"):
        self.inputs: list[dict] = []
        self.items_for = items_for
        self.status = status
        self.datasets_read = 0
        self._items: list[dict] = []

    def actor(self, actor_id):
        assert actor_id == apify_amazon.ACTOR_ID
        fake = self

        class _Actor:
            def call(self, run_input, timeout_secs):
                fake.inputs.append(run_input)
                fake._items = fake.items_for(run_input)
                return {"status": fake.status, "defaultDatasetId": "ds1"}

        return _Actor()

    def dataset(self, dataset_id):
        fake = self

        class _Dataset:
            def iterate_items(self):
                fake.datasets_read += 1
                return iter(fake._items)

        return _Dataset()


def _install(monkeypatch, fake: FakeApify) -> FakeApify:
    monkeypatch.setattr(apify_amazon, "_get_client", lambda: fake)
    return fake


def _reviews_matching_the_tier(run_input: dict) -> list[dict]:
    rating = TIER_RATING[run_input["filterByRatings"][0]]
    return [_item(rating, n) for n in range(4)]


@pytest.mark.parametrize("tier, actor_value", [
    ("five_star", "fiveStar"),
    ("four_star", "fourStar"),
    ("three_star", "threeStar"),
    ("two_star", "twoStar"),
    ("one_star", "oneStar"),
    ("all_stars", "allStars"),
    ("positive", "positive"),
    ("critical", "critical"),
])
def test_star_tier_is_sent_in_the_field_the_actor_reads(monkeypatch, tier, actor_value):
    fake = _install(monkeypatch, FakeApify())

    scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", star_filter=tier)

    assert fake.inputs[0]["filterByRatings"] == [actor_value]
    assert "filterByStar" not in fake.inputs[0]


def test_sort_is_sent_in_the_field_the_actor_reads(monkeypatch):
    fake = _install(monkeypatch, FakeApify())

    scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A")
    scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", sort="recent")

    assert [run_input["sort"] for run_input in fake.inputs] == ["helpful", "recent"]
    assert all("sortBy" not in run_input for run_input in fake.inputs)


def test_an_unknown_tier_or_sort_is_refused_before_any_paid_run(monkeypatch):
    fake = _install(monkeypatch, FakeApify())

    with pytest.raises(ValueError):
        scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", star_filter="six_star")
    with pytest.raises(ValueError):
        scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", sort="newest")

    assert fake.inputs == []


@pytest.mark.parametrize("status", ["FAILED", "TIMED-OUT", "ABORTED", None])
def test_a_run_that_did_not_succeed_is_a_failure_not_an_empty_tier(monkeypatch, status):
    fake = _install(monkeypatch, FakeApify(items_for=lambda _: [_item(1, 1)], status=status))

    bundle = scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", star_filter="one_star")

    assert bundle.reviews == []
    assert bundle.notes.startswith("Apify call failed")
    # research-amazon shows the first 40 characters of a note: the status must be in them.
    assert (status or "no run record") in bundle.notes[:40]
    assert fake.datasets_read == 0


def test_a_tier_that_matches_its_filter_keeps_every_review_without_a_warning(monkeypatch):
    _install(monkeypatch, FakeApify(items_for=lambda _: [_item(1, n) for n in range(5)]))

    bundle = scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", star_filter="one_star")

    assert [review.rating for review in bundle.reviews] == [1] * 5
    assert bundle.notes == ""
    assert not star_filter_ignored(bundle)


def test_an_answer_that_ignores_the_filter_is_flagged(monkeypatch):
    unfiltered = [_item(5, n) for n in range(8)] + [_item(1, 8), _item(3, 9)]
    _install(monkeypatch, FakeApify(items_for=lambda _: unfiltered))

    bundle = scrape_amazon_reviews(PRODUCT_URL, "brand-a", "Brand A", star_filter="one_star")

    assert star_filter_ignored(bundle)
    assert bundle.notes.startswith("STAR FILTER IGNORED")


def _bundle(tier: str, ratings: list[int]) -> AmazonReviewBundle:
    return AmazonReviewBundle(
        product_url=PRODUCT_URL,
        competitor_slug="brand-a",
        competitor_name="Brand A",
        star_filter=tier,
        reviews=[Review(title="t", body="b", rating=rating) for rating in ratings],
    )


def test_one_odd_rating_is_not_an_ignored_filter():
    assert not star_filter_ignored(_bundle("one_star", [1] * 9 + [2]))


def test_unreadable_ratings_and_wide_tiers_are_not_an_ignored_filter():
    assert not star_filter_ignored(_bundle("one_star", [0] * 6))
    assert not star_filter_ignored(_bundle("all_stars", [1, 2, 3, 4, 5]))
    assert not star_filter_ignored(_bundle("critical", [1, 2, 3, 3]))
    assert not star_filter_ignored(_bundle("positive", [4, 5, 5]))
    assert star_filter_ignored(_bundle("critical", [1, 5, 4]))


def test_a_saved_file_from_before_the_fix_is_recognised():
    old_one_star_file = {
        "star_filter": "one_star",
        "reviews": [{"rating": 5}, {"rating": "4.0"}, {"rating": 1}, {"rating": None}, "junk"],
    }
    assert saved_tier_unfiltered(old_one_star_file)
    assert not saved_tier_unfiltered({"star_filter": "one_star", "reviews": [{"rating": 1}] * 5})
    assert not saved_tier_unfiltered({"reviews": [{"rating": 1}, {"rating": 5}, {"rating": 3}]})
    assert not saved_tier_unfiltered(["not", "a", "bundle"])


def test_a_saved_failed_pull_is_recognised():
    failed = {"reviews": [], "notes": "Apify call failed: ApifyApiError: usage limit exceeded"}
    assert saved_tier_failed(failed)
    assert not saved_tier_failed({"reviews": [], "notes": "Run completed but yielded 0 reviews"})
    assert not saved_tier_failed({"reviews": [{"rating": 1}], "notes": "Apify call failed: x"})
    assert not saved_tier_failed("not a bundle")
    assert pull_failed(0, "Failed to read Apify dataset")
    assert not pull_failed(0, "")


def test_tiers_are_called_rarest_first_without_repeats():
    assert rarest_first(["five_star", "three_star", "one_star"]) == [
        "one_star", "three_star", "five_star",
    ]
    assert rarest_first(["five_star", "five_star", "all_stars", "two_star"]) == [
        "two_star", "five_star", "all_stars",
    ]
    tiers = ["critical", "five_star"]
    assert rarest_first(tiers) == ["five_star", "critical"]
    assert tiers == ["critical", "five_star"]


def _amazon_client(tmp_path, monkeypatch, urls=(PRODUCT_URL,)):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "clients" / "acme"
    base.mkdir(parents=True)
    competitors = {"competitors": [{
        "name": "Brand A",
        "slug": "brand-a",
        "url": "https://brand-a.example",
        "amazon_urls": list(urls),
    }]}
    (base / "competitors.yaml").write_text(yaml.dump(competitors), encoding="utf-8")
    return base / "research" / "amazon-reviews"


def _cached(cache_dir) -> list:
    return sorted(cache_dir.glob("*.json")) if cache_dir.exists() else []


def _cost_log(tmp_path) -> list[dict]:
    path = tmp_path / "clients" / "acme" / ".cost-log.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_research_amazon_saves_each_tier_with_only_that_tiers_reviews(tmp_path, monkeypatch):
    from cli import cli

    cache_dir = _amazon_client(tmp_path, monkeypatch)
    fake = _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--max-reviews", "25"])

    assert res.exit_code == 0, res.output
    assert [run_input["filterByRatings"] for run_input in fake.inputs] == [
        ["oneStar"], ["threeStar"], ["fiveStar"],
    ]
    assert all(run_input["maxReviews"] == 25 for run_input in fake.inputs)
    for short, rating in (("5s", 5), ("3s", 3), ("1s", 1)):
        path = cache_dir / f"brand-a-B000TEST01-{short}.json"
        saved = json.loads(path.read_text(encoding="utf-8"))
        assert {review["rating"] for review in saved["reviews"]} == {rating}


def test_research_amazon_logs_the_reviews_it_paid_for(tmp_path, monkeypatch):
    from cli import cli

    _amazon_client(tmp_path, monkeypatch)
    _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier))

    first = CliRunner().invoke(cli, ["research-amazon", "--client", "acme"])
    second = CliRunner().invoke(cli, ["research-amazon", "--client", "acme"])

    assert first.exit_code == 0 and second.exit_code == 0, first.output + second.output
    paid, cached = _cost_log(tmp_path)
    assert paid["cost"] == pytest.approx(12 * 0.006)
    assert paid["note"] == "3 call(s) made, 12 review(s) fetched"
    assert cached["cost"] == 0
    assert cached["note"] == "0 call(s) made, 0 review(s) fetched"


def test_research_amazon_logs_the_cost_when_a_run_breaks_off(tmp_path, monkeypatch):
    from cli import cli

    _amazon_client(tmp_path, monkeypatch)
    fake = FakeApify(items_for=_reviews_matching_the_tier)
    clients_handed_out = []

    def client_then_failure():
        if clients_handed_out:
            raise EnvironmentError("APIFY_API_TOKEN not set")
        clients_handed_out.append(fake)
        return fake

    monkeypatch.setattr(apify_amazon, "_get_client", client_then_failure)

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme"])

    assert isinstance(res.exception, EnvironmentError)
    [entry] = _cost_log(tmp_path)
    assert entry["cost"] == pytest.approx(4 * 0.006)
    assert entry["note"] == "1 call(s) made, 4 review(s) fetched"


@pytest.mark.parametrize("value", ["0", "-5"])
def test_research_amazon_refuses_a_review_count_below_one(tmp_path, monkeypatch, value):
    from cli import cli

    _amazon_client(tmp_path, monkeypatch)
    fake = _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--max-reviews", value])

    assert res.exit_code == 2
    assert fake.inputs == []


def test_research_amazon_stops_when_the_scraper_ignores_the_star_filter(tmp_path, monkeypatch):
    from cli import cli

    cache_dir = _amazon_client(tmp_path, monkeypatch, urls=(PRODUCT_URL, SECOND_URL))
    unfiltered = [_item(5, n) for n in range(6)] + [_item(1, 6), _item(3, 7)]
    fake = _install(monkeypatch, FakeApify(items_for=lambda _: unfiltered))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme"])

    assert res.exit_code == 1
    assert len(fake.inputs) == 1
    assert _cached(cache_dir) == []
    assert "ignored the star filter" in res.output
    [entry] = _cost_log(tmp_path)
    assert entry["cost"] == pytest.approx(8 * 0.006)
    assert entry["note"] == "1 call(s) made, 8 review(s) fetched"


def test_an_unfiltered_answer_is_caught_before_any_file_is_saved(tmp_path, monkeypatch):
    """Mostly 5-star, as an unfiltered "Top reviews" list is: a 5-star call alone would pass."""
    from cli import cli

    unfiltered = [_item(5, n) for n in range(63)] + [_item(4, 63), _item(3, 64), _item(2, 65)]
    assert not star_filter_ignored(_bundle("five_star", [5] * 63 + [4, 3, 2]))
    cache_dir = _amazon_client(tmp_path, monkeypatch)
    fake = _install(monkeypatch, FakeApify(items_for=lambda _: unfiltered))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--stars", "5,3,1"])

    assert res.exit_code == 1
    assert [run_input["filterByRatings"] for run_input in fake.inputs] == [["oneStar"]]
    assert _cached(cache_dir) == []


def test_research_amazon_flags_saved_files_from_before_the_fix(tmp_path, monkeypatch):
    from cli import cli

    cache_dir = _amazon_client(tmp_path, monkeypatch)
    cache_dir.mkdir(parents=True)
    old_file = {
        "product_url": PRODUCT_URL,
        "competitor_slug": "brand-a",
        "competitor_name": "Brand A",
        "asin": "B000TEST01",
        "star_filter": "one_star",
        "reviews": [{"title": "t", "body": "b", "rating": rating} for rating in (5, 5, 4, 1)],
    }
    (cache_dir / "brand-a-B000TEST01-1s.json").write_text(json.dumps(old_file), encoding="utf-8")
    fake = _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--stars", "1"])

    assert res.exit_code == 0, res.output
    assert fake.inputs == []
    assert "1 saved tier file(s) are unfiltered" in res.output


def test_research_amazon_flags_saved_failed_pulls(tmp_path, monkeypatch):
    from cli import cli

    cache_dir = _amazon_client(tmp_path, monkeypatch)
    cache_dir.mkdir(parents=True)
    old_failure = {
        "product_url": PRODUCT_URL,
        "competitor_slug": "brand-a",
        "competitor_name": "Brand A",
        "asin": "B000TEST01",
        "star_filter": "one_star",
        "reviews": [],
        "notes": "Apify call failed: ApifyApiError: Monthly usage hard limit exceeded",
    }
    (cache_dir / "brand-a-B000TEST01-1s.json").write_text(json.dumps(old_failure), encoding="utf-8")
    fake = _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--stars", "1"])

    assert res.exit_code == 0, res.output
    assert fake.inputs == []
    assert "1 saved tier file(s) hold no reviews" in res.output


def test_adc_status_does_not_load_the_apify_client():
    """`adc status` is meant to be fast: the saved-file checks must not pull in API clients."""
    probe = (
        "import sys; import strategy.status_dashboard; "
        "print(sorted(m for m in ('apify_client', 'anthropic', 'openai') if m in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    )
    assert result.stdout.strip() == "[]"


def test_research_amazon_does_not_save_a_failed_run(tmp_path, monkeypatch):
    from cli import cli

    cache_dir = _amazon_client(tmp_path, monkeypatch)
    fake = _install(monkeypatch, FakeApify(items_for=_reviews_matching_the_tier, status="FAILED"))

    res = CliRunner().invoke(cli, ["research-amazon", "--client", "acme", "--stars", "1"])

    assert res.exit_code == 0, res.output
    assert len(fake.inputs) == 1
    assert _cached(cache_dir) == []
