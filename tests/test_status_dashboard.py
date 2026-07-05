import json

import yaml

import strategy.status_dashboard as sd
from strategy.exa_queries import cache_stem, competitive_queries_for_brand


def _make_client(tmp_path, *, amazon_urls=False):
    clients = tmp_path / "clients"
    base = clients / "zoka-coffee"
    base.mkdir(parents=True)
    (base / "brand.yaml").write_text(
        yaml.dump({"name": "Zoka Coffee"}), encoding="utf-8"
    )
    (base / "brand-context.md").write_text("# Zoka", encoding="utf-8")
    competitor = {
        "name": "Stumptown Coffee Roasters",
        "slug": "stumptown",
        "url": "https://www.stumptowncoffee.com",
    }
    if amazon_urls:
        competitor["amazon_urls"] = ["https://www.amazon.com/dp/B000TEST"]
    (base / "competitors.yaml").write_text(
        yaml.dump({"competitors": [competitor]}), encoding="utf-8"
    )
    return clients, base


def _write_products(base, count, enriched):
    products = base / "products"
    products.mkdir(exist_ok=True)
    for i in range(count):
        payload = {"name": f"Blend {i}", "description": "x"}
        if i < enriched:
            payload["benefits"] = ["tastes great"]
        (products / f"blend-{i}.yaml").write_text(yaml.dump(payload), encoding="utf-8")


def _stage(stages, name):
    return next(s for s in stages if s.name == name)


def test_expected_exa_stems_match_planning_module(tmp_path, monkeypatch):
    clients, _ = _make_client(tmp_path)
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)

    stems = sd._expected_competitive_exa_stems("zoka-coffee")
    queries = competitive_queries_for_brand(
        own_brand="Zoka Coffee",
        competitor_names=["Stumptown Coffee Roasters"],
    )
    assert stems == [cache_stem(q.label) for q in queries]
    assert len(stems) == 10


def test_exa_stage_flags_missing_reddit_caches(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)

    raw = base / "research" / "exa" / "raw"
    raw.mkdir(parents=True)
    for stem in sd._expected_competitive_exa_stems("zoka-coffee"):
        if stem.startswith("reddit-"):
            continue  # simulate the Zoka run: Reddit queries never persisted
        (raw / f"{stem}.json").write_text(
            json.dumps({"results": [{"url": "https://x.com"}]}), encoding="utf-8"
        )

    stage = _stage(sd.competitive_research_status("zoka-coffee"), "Exa web sentiment")
    assert stage.summary.startswith("8/10")
    assert any("Reddit" in n for n in stage.notes)


def test_exa_stage_surfaces_error_records(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)

    errors = base / "research" / "exa" / "errors"
    errors.mkdir(parents=True)
    (errors / "reddit-zoka-coffee-honest.json").write_text(
        json.dumps({"error_type": "ValueError", "error": "boom"}), encoding="utf-8"
    )

    stage = _stage(sd.competitive_research_status("zoka-coffee"), "Exa web sentiment")
    assert stage.counts["queries_failed"] == 1
    assert any("failed query record" in n for n in stage.notes)


def test_onsite_reviews_with_zero_reviews_is_not_done(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)

    onsite = base / "research" / "competitor-reviews"
    onsite.mkdir(parents=True)
    (onsite / "stumptown.json").write_text(
        json.dumps({"vendor": "none", "reviews": []}), encoding="utf-8"
    )

    stage = _stage(
        sd.competitive_research_status("zoka-coffee"), "On-site competitor reviews"
    )
    assert stage.done is False
    assert stage.notes


def test_social_stage_reads_diagnostics(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)

    diag = base / "research" / "youtube-diagnostics"
    diag.mkdir(parents=True)
    (diag / "stumptown.json").write_text(
        json.dumps({
            "platform": "youtube",
            "competitor_slug": "stumptown",
            "status": "ok",
            "comments": 0,
        }),
        encoding="utf-8",
    )

    stage = _stage(sd.competitive_research_status("zoka-coffee"), "Social comments")
    assert stage.done is False
    assert stage.counts["diagnostics"] == 1
    assert any("per-source diagnostics" in n for n in stage.notes)


def _recommendations(tmp_path, monkeypatch, clients):
    monkeypatch.setattr(sd, "CLIENTS_DIR", clients)
    monkeypatch.setattr(sd, "AI_ADS_DIR", tmp_path / "ai-ads")
    strategy = sd.strategy_status("zoka-coffee")
    competitive = sd.competitive_research_status("zoka-coffee")
    assets = sd.ad_assets_status("zoka-coffee")
    return sd.build_recommendations("zoka-coffee", strategy, competitive, assets)


def test_fully_enriched_products_do_not_trigger_enrich_rec(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    _write_products(base, count=10, enriched=10)
    recs = _recommendations(tmp_path, monkeypatch, clients)
    # Old substring check ("0 enriched" in "10 product(s), 10 enriched") misfired here.
    assert not any("Enrich product files" in r for r in recs)


def test_unenriched_products_trigger_enrich_rec(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    _write_products(base, count=3, enriched=0)
    recs = _recommendations(tmp_path, monkeypatch, clients)
    assert any("Enrich product files" in r for r in recs)


def test_amazon_rec_fires_when_urls_configured(tmp_path, monkeypatch):
    clients, _ = _make_client(tmp_path, amazon_urls=True)
    recs = _recommendations(tmp_path, monkeypatch, clients)
    # Old check looked for the literal "amazon_urls" in a summary that says
    # "(with Amazon URLs)" — it could never fire.
    assert any("Pull Amazon reviews" in r for r in recs)


def test_amazon_rec_explains_no_autodiscovery_without_urls(tmp_path, monkeypatch):
    clients, _ = _make_client(tmp_path, amazon_urls=False)
    recs = _recommendations(tmp_path, monkeypatch, clients)
    assert any("auto-discover" in r for r in recs)


def test_social_first_run_recommended(tmp_path, monkeypatch):
    clients, _ = _make_client(tmp_path)
    recs = _recommendations(tmp_path, monkeypatch, clients)
    assert any("adc research-social" in r for r in recs)


def test_social_zero_comment_run_gets_force_refresh_rec(tmp_path, monkeypatch):
    clients, base = _make_client(tmp_path)
    (base / ".cost-log.jsonl").write_text(
        json.dumps({
            "timestamp": "2026-07-05T10:00:00",
            "command": "adc research-social",
            "cost": 0.0,
            "note": "4 pulls, 0 comment(s)",
        }) + "\n",
        encoding="utf-8",
    )
    recs = _recommendations(tmp_path, monkeypatch, clients)
    assert any("--force-refresh" in r and "research-social" in r for r in recs)
