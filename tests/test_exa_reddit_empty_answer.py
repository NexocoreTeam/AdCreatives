"""Exa now answers a reddit.com-scoped search with zero results and no error.

Before this fix, run_query only fell back to the Reddit API / Apify bridge on
Exa's SOURCE_NOT_AVAILABLE error. The empty answer was cached as if Reddit had
nothing to say, and every later run skipped the query because a cache file
existed.
"""

from __future__ import annotations

import json
from dataclasses import asdict

import pytest
import yaml
from click.testing import CliRunner

import strategy.apify_reddit as apify_reddit
import strategy.exa_research as exa_research
import strategy.reddit_research as reddit_research
import strategy.status_dashboard as sd
from strategy.apify_reddit import ApifyRedditError
from strategy.exa_queries import ExaQuery, cache_stem, cached_result_is_usable
from strategy.exa_research import (
    ExaHit,
    ExaQueryResult,
    cache_result,
    load_cached,
    run_query,
    run_research_bundle,
)
from strategy.reddit_research import RedditAuthError

POST_URL = "https://www.reddit.com/r/example/comments/abc123/thread/"


class _Doc:
    def __init__(self, url: str):
        self.url = url
        self.title = "A thread"
        self.text = "body text"
        self.published_date = None
        self.author = None
        self.score = 0.5


class _Response:
    def __init__(self, docs):
        self.results = docs


class _FakeExa:
    """Answers every search with the same docs and records each call."""

    def __init__(self, docs):
        self.docs = docs
        self.calls = []

    def search_and_contents(self, query, **kwargs):
        self.calls.append((query, kwargs))
        return _Response(list(self.docs))


def _reddit_query(label: str = "reddit-acme-honest") -> ExaQuery:
    return ExaQuery(
        label=label,
        query="Acme honest review experience worth it",
        include_domains=["reddit.com"],
        category="reddit",
        keyword_query='"Acme" review',
    )


def _web_query(label: str = "web-acme-love") -> ExaQuery:
    return ExaQuery(label=label, query="Acme best love review")


def _hit() -> ExaHit:
    return ExaHit(
        url=POST_URL, title="t", published_date=None, author=None,
        score=1.0, text="body", domain="reddit.com",
    )


def _raises(exc: Exception):
    def raiser(*args, **kwargs):
        raise exc
    return raiser


def _no_fallback(monkeypatch):
    stop = AssertionError("no fallback may run here")
    monkeypatch.setattr(reddit_research, "run_reddit_query", _raises(stop))
    monkeypatch.setattr(apify_reddit, "run_reddit_query_via_apify", _raises(stop))


# ─── run_query ───────────────────────────────────────────────────────────────


def test_empty_reddit_answer_falls_back_to_the_reddit_api(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _FakeExa([]))
    from_api = ExaQueryResult(query=_reddit_query(), fetched_at="t", results=[_hit()])
    monkeypatch.setattr(
        reddit_research, "run_reddit_query", lambda query, content_chars=3000: from_api
    )
    monkeypatch.setattr(
        apify_reddit, "run_reddit_query_via_apify",
        _raises(AssertionError("Apify must not run when the Reddit API works")),
    )

    assert run_query(_reddit_query()) is from_api


def test_empty_reddit_answer_uses_apify_when_the_api_is_unusable(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _FakeExa([]))
    monkeypatch.setattr(
        reddit_research, "run_reddit_query", _raises(RedditAuthError("creds not set"))
    )
    from_apify = ExaQueryResult(query=_reddit_query(), fetched_at="t", results=[_hit()])
    monkeypatch.setattr(
        apify_reddit, "run_reddit_query_via_apify",
        lambda query, content_chars=3000: from_apify,
    )

    assert run_query(_reddit_query()) is from_apify


def test_empty_reddit_answer_with_no_usable_fallback_raises(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _FakeExa([]))
    monkeypatch.setattr(
        reddit_research, "run_reddit_query",
        _raises(RedditAuthError("REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set.")),
    )
    monkeypatch.setattr(
        apify_reddit, "run_reddit_query_via_apify",
        _raises(ApifyRedditError("run failed: authentication token is not valid")),
    )

    with pytest.raises(RuntimeError) as exc:
        run_query(_reddit_query())
    message = str(exc.value)
    assert "no reddit.com results" in message
    assert "REDDIT_CLIENT_ID" in message
    assert "token is not valid" in message
    assert isinstance(exc.value.__cause__, ApifyRedditError)


def test_reddit_hits_from_exa_need_no_fallback(monkeypatch):
    monkeypatch.setattr(exa_research, "_get_client", lambda: _FakeExa([_Doc(POST_URL)]))
    _no_fallback(monkeypatch)

    result = run_query(_reddit_query())

    assert [h.url for h in result.results] == [POST_URL]
    assert result.source == "exa"


def test_an_empty_answer_outside_reddit_stays_empty(monkeypatch):
    fake = _FakeExa([])
    monkeypatch.setattr(exa_research, "_get_client", lambda: fake)
    _no_fallback(monkeypatch)

    result = run_query(_web_query())

    assert result.results == []
    assert len(fake.calls) == 1


# ─── Where a result came from ────────────────────────────────────────────────


def test_reddit_api_results_say_where_they_came_from(monkeypatch):
    monkeypatch.setattr(reddit_research, "search_posts", lambda search, limit=10: [])

    assert reddit_research.run_reddit_query(_reddit_query()).source == "reddit-api"


def _fake_apify(monkeypatch, run):
    class FakeDataset:
        def iterate_items(self):
            return iter([])

    class FakeActor:
        def call(self, run_input, timeout_secs):
            return run

    class FakeClient:
        def actor(self, actor_id):
            return FakeActor()

        def dataset(self, dataset_id):
            return FakeDataset()

    monkeypatch.setattr(apify_reddit, "_get_client", lambda: FakeClient())


def test_apify_results_say_where_they_came_from(monkeypatch):
    _fake_apify(monkeypatch, {"defaultDatasetId": "ds1", "status": "SUCCEEDED"})

    assert apify_reddit.run_reddit_query_via_apify(_reddit_query()).source == "apify"


@pytest.mark.parametrize("run", [
    {"defaultDatasetId": "ds1", "status": "FAILED"},
    {"defaultDatasetId": "ds1", "status": "TIMED-OUT"},
    {"defaultDatasetId": "ds1", "status": "ABORTED"},
    None,
])
def test_an_apify_run_that_did_not_finish_is_an_error_not_an_empty_answer(monkeypatch, run):
    _fake_apify(monkeypatch, run)

    with pytest.raises(ApifyRedditError, match="run ended"):
        apify_reddit.run_reddit_query_via_apify(_reddit_query())


def test_source_survives_the_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", tmp_path / "clients")
    result = ExaQueryResult(
        query=_reddit_query(), fetched_at="t", results=[], source="apify",
    )

    path = cache_result("acme", result)

    assert json.loads(path.read_text(encoding="utf-8"))["source"] == "apify"
    assert load_cached("acme")[0].source == "apify"


# ─── Which cached results can be reused ──────────────────────────────────────


HIT_ROWS = [asdict(_hit())]


def _cached(query: ExaQuery, rows: list[dict], source: str | None = None) -> dict:
    """A cache file's content. No source = written before this fix."""
    data = {"query": asdict(query), "fetched_at": "t", "results": rows}
    return data if source is None else {**data, "source": source}


def test_an_old_empty_reddit_cache_is_not_reused():
    assert not cached_result_is_usable(_cached(_reddit_query(), []))
    assert not cached_result_is_usable(_cached(_reddit_query(), [], source="exa"))
    assert not cached_result_is_usable({**_cached(_reddit_query(), []), "source": None})


def test_files_the_rule_cannot_read_are_left_alone():
    assert cached_result_is_usable({"query": "not a dict", "results": []})
    assert cached_result_is_usable({"query": None, "results": []})
    assert cached_result_is_usable([])
    assert cached_result_is_usable(None)


def test_other_caches_are_reused():
    assert cached_result_is_usable(_cached(_reddit_query(), [], source="apify"))
    assert cached_result_is_usable(_cached(_reddit_query(), [], source="reddit-api"))
    assert cached_result_is_usable(_cached(_reddit_query(), HIT_ROWS))
    assert cached_result_is_usable(_cached(_web_query(), []))
    assert cached_result_is_usable({"results": []})


# ─── research-web (run_research_bundle) ──────────────────────────────────────


def _write_cache(clients, client, query, results, source=None):
    raw = clients / client / "research" / "exa" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / f"{cache_stem(query.label)}.json").write_text(
        json.dumps(_cached(query, results, source)), encoding="utf-8"
    )


def test_bundle_reruns_old_empty_reddit_caches_and_survives_failures(tmp_path, monkeypatch):
    clients = tmp_path / "clients"
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", clients)
    stale_reddit = _reddit_query("reddit-acme-honest")
    apify_empty = _reddit_query("reddit-acme-worth-it")
    reddit_with_hits = _reddit_query("reddit-acme-vs-rival")
    cached_web, fresh_web = _web_query("web-acme-cached"), _web_query("web-acme-fresh")
    _write_cache(clients, "acme", stale_reddit, [])
    _write_cache(clients, "acme", apify_empty, [], source="apify")
    _write_cache(clients, "acme", reddit_with_hits, HIT_ROWS)
    _write_cache(clients, "acme", cached_web, HIT_ROWS)
    monkeypatch.setattr(
        exa_research, "default_queries_for_brand",
        lambda brand, competitors=None, category_terms=None: [
            stale_reddit, apify_empty, reddit_with_hits, cached_web, fresh_web, fresh_web,
        ],
    )
    asked = []

    def fake_run_query(query):
        asked.append(query.label)
        if query.label == stale_reddit.label:
            raise RuntimeError("Exa returned no reddit.com results; fallbacks unusable")
        return ExaQueryResult(query=query, fetched_at="t", results=[_hit()])

    monkeypatch.setattr(exa_research, "run_query", fake_run_query)

    results = run_research_bundle("acme", "Acme")

    assert asked == [stale_reddit.label, fresh_web.label]
    assert [r.query.label for r in results] == [
        apify_empty.label, reddit_with_hits.label, cached_web.label, fresh_web.label,
    ]
    error = clients / "acme" / "research" / "exa" / "errors" / f"{stale_reddit.label}.json"
    assert "no reddit.com results" in json.loads(error.read_text(encoding="utf-8"))["error"]


def _research_web_client(tmp_path, monkeypatch, brand: str = "Acme Co"):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", tmp_path / "clients")
    base = tmp_path / "clients" / "acme"
    base.mkdir(parents=True)
    (base / "brand.yaml").write_text(yaml.dump({"name": brand}), encoding="utf-8")
    return tmp_path / "clients"


def test_research_web_reports_the_queries_that_failed(tmp_path, monkeypatch):
    from cli import cli

    _research_web_client(tmp_path, monkeypatch)

    def fail_reddit(query):
        if "reddit.com" in query.include_domains:
            raise RuntimeError("Exa returned no reddit.com results; fallbacks unusable")
        return ExaQueryResult(query=query, fetched_at="t", results=[_hit()])

    monkeypatch.setattr(exa_research, "run_query", fail_reddit)

    res = CliRunner().invoke(cli, ["research-web", "--client", "acme"])

    assert res.exit_code == 0, res.output
    assert "2 queries failed" in res.output
    assert "reddit-acme-co-honest" in res.output


def test_research_web_does_not_report_a_reused_cache_as_failed(tmp_path, monkeypatch):
    """research-competitors writes the same cache file under a slugged label."""
    from cli import cli

    clients = _research_web_client(tmp_path, monkeypatch)
    _write_cache(clients, "acme", _reddit_query("reddit-acme-co-honest"), HIT_ROWS)
    monkeypatch.setattr(
        exa_research, "run_query",
        lambda query: ExaQueryResult(query=query, fetched_at="t", results=[_hit()]),
    )

    res = CliRunner().invoke(cli, ["research-web", "--client", "acme"])

    assert res.exit_code == 0, res.output
    assert "failed" not in res.output


def test_research_web_runs_a_duplicated_competitor_once(tmp_path, monkeypatch):
    from cli import cli

    _research_web_client(tmp_path, monkeypatch)
    asked = []

    def record(query):
        asked.append(cache_stem(query.label))
        return ExaQueryResult(query=query, fetched_at="t", results=[_hit()])

    monkeypatch.setattr(exa_research, "run_query", record)

    res = CliRunner().invoke(
        cli, ["research-web", "--client", "acme", "--competitors", "Rival,Rival,rival"],
    )

    assert res.exit_code == 0, res.output
    assert len(asked) == len(set(asked))
    assert "failed" not in res.output


def test_research_web_fails_when_no_query_succeeds(tmp_path, monkeypatch):
    from cli import cli

    _research_web_client(tmp_path, monkeypatch)
    monkeypatch.setattr(
        exa_research, "run_query", _raises(EnvironmentError("EXA_API_KEY not set.")),
    )

    res = CliRunner().invoke(cli, ["research-web", "--client", "acme"])

    assert res.exit_code == 1
    assert "No query succeeded" in res.output
    assert "EXA_API_KEY not set" in res.output


# ─── research-competitors ────────────────────────────────────────────────────


def test_research_competitors_reruns_only_old_empty_reddit_caches(tmp_path, monkeypatch):
    from cli import cli
    from strategy.exa_queries import competitive_queries_for_brand

    monkeypatch.chdir(tmp_path)
    clients = tmp_path / "clients"
    base = clients / "acme"
    base.mkdir(parents=True)
    (base / "brand.yaml").write_text(yaml.dump({"name": "Acme"}), encoding="utf-8")
    (base / "competitors.yaml").write_text(yaml.dump({"competitors": [
        {"name": "Rival Co", "slug": "rival-co", "url": "https://rival.example"},
        {"name": "Other Co", "slug": "other-co", "url": "https://other.example"},
    ]}), encoding="utf-8")
    planned = competitive_queries_for_brand("Acme", ["Rival Co", "Other Co"])
    reddit_kind = {
        "reddit-acme-honest": ("stale", [], None),
        "reddit-rival-co-honest": ("apify said nothing", [], "apify"),
        "reddit-other-co-honest": ("has hits", HIT_ROWS, None),
    }
    for q in planned:
        _kind, rows, source = reddit_kind.get(q.label, ("web", HIT_ROWS, None))
        _write_cache(clients, "acme", q, rows, source)
    asked = []

    def fake_run_query(query):
        asked.append(query.label)
        return ExaQueryResult(query=query, fetched_at="t", results=[_hit()], source="apify")

    monkeypatch.setattr(exa_research, "run_query", fake_run_query)

    res = CliRunner().invoke(cli, ["research-competitors", "--client", "acme", "--skip-onsite"])

    assert res.exit_code == 0, res.output
    assert set(reddit_kind) <= {q.label for q in planned}
    assert asked == ["reddit-acme-honest"]


# ─── adc status ──────────────────────────────────────────────────────────────


def test_status_counts_old_empty_reddit_caches_as_missing(tmp_path, monkeypatch):
    clients = tmp_path / "clients"
    base = clients / "acme"
    base.mkdir(parents=True)
    (base / "brand.yaml").write_text(yaml.dump({"name": "Acme"}), encoding="utf-8")
    (base / "competitors.yaml").write_text(yaml.dump({"competitors": [
        {"name": "Rival Co", "slug": "rival-co", "url": "https://rival.example"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)
    from strategy.exa_queries import competitive_queries_for_brand

    for q in competitive_queries_for_brand("Acme", ["Rival Co"]):
        reddit = "reddit.com" in q.include_domains
        _write_cache(clients, "acme", q, [] if reddit else [{"url": "https://x.example"}])

    stage = next(
        s for s in sd.competitive_research_status("acme") if s.name == "Exa web sentiment"
    )

    assert stage.summary.startswith("8/10")
    assert any("Reddit" in n and "empty" in n for n in stage.notes)


def test_status_tolerates_a_cache_file_with_an_odd_query_field(tmp_path, monkeypatch):
    clients = tmp_path / "clients"
    base = clients / "acme"
    base.mkdir(parents=True)
    (base / "brand.yaml").write_text(yaml.dump({"name": "Acme"}), encoding="utf-8")
    (base / "competitors.yaml").write_text(yaml.dump({"competitors": [
        {"name": "Rival Co", "slug": "rival-co", "url": "https://rival.example"},
    ]}), encoding="utf-8")
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)
    raw = base / "research" / "exa" / "raw"
    raw.mkdir(parents=True)
    (raw / "reddit-acme-honest.json").write_text(
        json.dumps({"query": "hand-written", "results": []}), encoding="utf-8"
    )

    stage = next(
        s for s in sd.competitive_research_status("acme") if s.name == "Exa web sentiment"
    )

    assert stage.summary.startswith("1/10")
