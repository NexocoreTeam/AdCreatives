import json

import strategy.exa_research as exa_research
from strategy.exa_research import (
    ExaHit,
    ExaQuery,
    ExaQueryResult,
    cache_error,
    cache_result,
    load_cached,
)


def test_cache_error_persists_failure(tmp_path, monkeypatch):
    """A failed Exa query must leave a readable error record — before this
    existed, failures vanished after the run (Zoka issue #8)."""
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", tmp_path / "clients")

    query = ExaQuery(label="reddit-zoka-coffee-honest", query="zoka honest review")
    path = cache_error("zoka-coffee", query, ValueError("boom"))

    assert path.exists()
    assert path.parent.name == "errors"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["error_type"] == "ValueError"
    assert payload["error"] == "boom"
    assert payload["query"]["label"] == "reddit-zoka-coffee-honest"


def test_cache_result_clears_stale_error_record(tmp_path, monkeypatch):
    """A query that failed once and later succeeded must not keep reporting
    a failure ghost in status."""
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", tmp_path / "clients")

    query = ExaQuery(label="reddit-zoka-coffee-honest", query="zoka honest review")
    error_path = cache_error("zoka-coffee", query, ValueError("boom"))
    assert error_path.exists()

    cache_result("zoka-coffee", ExaQueryResult(
        query=query, fetched_at="2026-07-05T00:00:00Z", results=[],
    ))
    assert not error_path.exists()


def test_cache_result_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(exa_research, "CLIENTS_DIR", tmp_path / "clients")

    result = ExaQueryResult(
        query=ExaQuery(label="web-zoka-coffee-love", query="zoka love"),
        fetched_at="2026-07-05T00:00:00Z",
        results=[ExaHit(
            url="https://example.com/a",
            title="A",
            published_date=None,
            author=None,
            score=0.5,
            text="great coffee",
            domain="example.com",
        )],
    )
    path = cache_result("zoka-coffee", result)
    assert path.stem == "web-zoka-coffee-love"

    loaded = load_cached("zoka-coffee")
    assert len(loaded) == 1
    assert loaded[0].query.label == "web-zoka-coffee-love"
    assert loaded[0].results[0].domain == "example.com"
