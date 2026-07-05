import pytest

import strategy.apify_reddit as apify_reddit
import strategy.exa_research as exa_research
import strategy.reddit_research as reddit_research
from strategy.apify_reddit import ApifyRedditError, _hits_from_items
from strategy.exa_queries import ExaQuery
from strategy.exa_research import ExaQueryResult, run_query
from strategy.reddit_research import RedditAuthError

POST_URL = "https://www.reddit.com/r/pourover/comments/1s3hs51/march_madness/"
# _post_base_url canonicalizes to the post-id base (slug dropped) so posts and
# comments group together regardless of URL variants; id-only URLs resolve fine.
POST_BASE = "https://www.reddit.com/r/pourover/comments/1s3hs51/"

ACTOR_ITEMS = [
    {
        "dataType": "post",
        "url": POST_URL,
        "title": "March Madness: Favorite American Roaster",
        "body": "Which roaster wins?",
        "username": "Ahoy_Pirate",
        "communityName": "r/pourover",
        "createdAt": "2026-03-25T17:45:43.000Z",
    },
    {
        "dataType": "comment",
        "url": POST_URL,
        "body": "Stumptown went downhill after the acquisition.",
        "username": "obscurej",
    },
    {
        "dataType": "comment",
        "url": POST_URL,
        "body": "[deleted]",
        "username": "gone",
    },
    {
        "dataType": "comment",
        "url": "https://www.reddit.com/r/espresso/comments/zzz9/paladino_thread/",
        "body": "Paladino is my daily driver.",
        "username": "espresso_fan",
    },
]


def test_hits_group_comments_under_posts():
    hits = _hits_from_items(ACTOR_ITEMS, content_chars=3000)
    assert len(hits) == 2

    main = hits[0]
    assert main.url == POST_BASE
    assert main.domain == "reddit.com"
    assert main.title.startswith("March Madness")
    assert "Which roaster wins?" in main.text
    assert "went downhill" in main.text
    assert "[deleted]" not in main.text

    orphan = hits[1]  # comment whose post wasn't in the stream still surfaces
    assert "daily driver" in orphan.text


def test_hits_respect_content_budget():
    items = [{
        "dataType": "post",
        "url": POST_URL,
        "title": "t",
        "body": "a" * 5000,
    }]
    hits = _hits_from_items(items, content_chars=3000)
    assert len(hits[0].text) == 3000


def test_missing_token_raises(monkeypatch):
    monkeypatch.delenv("APIFY_API_TOKEN", raising=False)
    with pytest.raises(ApifyRedditError):
        apify_reddit.run_reddit_query_via_apify(
            ExaQuery(label="reddit-x", query="x", include_domains=["reddit.com"])
        )


# ─── Chain routing through run_query ─────────────────────────────────────────

EXA_REDDIT_REFUSAL = ValueError(
    'Request failed with status code 403: {"tag":"SOURCE_NOT_AVAILABLE",'
    '"error":"The following requested domains are not available: reddit.com"}'
)


class _RefusingExa:
    def search_and_contents(self, *args, **kwargs):
        raise EXA_REDDIT_REFUSAL


def _reddit_query() -> ExaQuery:
    return ExaQuery(
        label="reddit-zoka-coffee-honest",
        query="Zoka Coffee honest review",
        include_domains=["reddit.com"],
        category="reddit",
    )


def test_apify_bridge_used_when_official_api_unusable(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _RefusingExa())

    def no_creds(query, content_chars=3000):
        raise RedditAuthError("creds pending Responsible Builder review")

    monkeypatch.setattr(reddit_research, "run_reddit_query", no_creds)

    sentinel = ExaQueryResult(query=_reddit_query(), fetched_at="t", results=[])
    monkeypatch.setattr(
        apify_reddit, "run_reddit_query_via_apify",
        lambda query, content_chars=3000: sentinel,
    )

    assert run_query(_reddit_query()) is sentinel


def test_all_three_tiers_failing_raises_combined_error(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _RefusingExa())
    monkeypatch.setattr(
        reddit_research, "run_reddit_query",
        lambda query, content_chars=3000: (_ for _ in ()).throw(
            RedditAuthError("creds pending")
        ),
    )
    monkeypatch.setattr(
        apify_reddit, "run_reddit_query_via_apify",
        lambda query, content_chars=3000: (_ for _ in ()).throw(
            ApifyRedditError("APIFY_API_TOKEN not set")
        ),
    )

    with pytest.raises(RuntimeError) as exc:
        run_query(_reddit_query())
    message = str(exc.value)
    assert "Exa no longer serves reddit.com" in message
    assert "creds pending" in message
    assert "APIFY_API_TOKEN" in message


def test_junk_results_filtered_by_brand_term(monkeypatch):
    """The actor scrapes rendered pages; Reddit pads weak searches with
    trending junk (a BG3 gaming thread showed up for a coffee query)."""
    items = [
        {"dataType": "post", "url": "https://www.reddit.com/r/BG3mods/comments/aaa1/mod/",
         "title": "New BG3 mod is great", "body": "gaming stuff"},
        {"dataType": "post", "url": "https://www.reddit.com/r/espresso/comments/bbb2/zoka/",
         "title": "Zoka Coffee Paladino thoughts?", "body": "Trying Zoka Coffee next week."},
    ]

    class FakeDataset:
        def iterate_items(self):
            return iter(items)

    class FakeActor:
        def call(self, run_input, timeout_secs):
            assert run_input["searches"] == ['"Zoka Coffee" review']
            return {"defaultDatasetId": "ds1"}

    class FakeClient:
        def actor(self, actor_id):
            return FakeActor()

        def dataset(self, dataset_id):
            return FakeDataset()

    monkeypatch.setattr(apify_reddit, "_get_client", lambda: FakeClient())

    query = ExaQuery(
        label="reddit-zoka-coffee-honest",
        query="Zoka Coffee honest review experience worth it",
        include_domains=["reddit.com"],
        keyword_query='"Zoka Coffee" review',
    )
    result = apify_reddit.run_reddit_query_via_apify(query)
    assert len(result.results) == 1
    assert "Zoka Coffee" in result.results[0].title
