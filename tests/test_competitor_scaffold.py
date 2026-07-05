import pytest

import strategy.competitor_scaffold as scaffold_mod
from strategy.competitor_scaffold import enrich_competitors, scaffold_competitors


def test_scaffold_creates_file_with_search_queries(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold_mod, "CLIENTS_DIR", tmp_path / "clients")
    path = scaffold_competitors(
        "zoka-coffee", "Zoka Coffee",
        ["Stumptown Coffee Roasters", "Onyx Coffee Lab"],
    )
    text = path.read_text(encoding="utf-8")
    assert "slug: stumptown-coffee-roasters" in text
    assert "Stumptown Coffee Roasters review" in text
    assert "Stumptown Coffee Roasters vs Zoka Coffee" in text
    assert "tiktok_search_queries" in text
    assert "amazon_urls: []" in text


def test_scaffold_refuses_to_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold_mod, "CLIENTS_DIR", tmp_path / "clients")
    scaffold_competitors("c", "Brand", ["A"])
    with pytest.raises(FileExistsError):
        scaffold_competitors("c", "Brand", ["B"])


EXISTING_YAML = """# operator notes up top — must survive enrichment
competitors:
  - name: Stumptown Coffee Roasters
    slug: stumptown
    url: https://www.stumptowncoffee.com
    notes: PNW heritage roaster  # inline comment survives too
    youtube_handle: "@stumptowncoffee"

  - name: Onyx Coffee Lab
    slug: onyx
    url: https://onyxcoffeelab.com
    youtube_search_queries:
      - "onyx coffee lab review"
"""


def _write_existing(tmp_path, monkeypatch):
    clients = tmp_path / "clients"
    base = clients / "zoka-coffee"
    base.mkdir(parents=True)
    (base / "competitors.yaml").write_text(EXISTING_YAML, encoding="utf-8")
    monkeypatch.setattr(scaffold_mod, "CLIENTS_DIR", clients)
    return base / "competitors.yaml"


def test_enrich_adds_only_missing_queries(tmp_path, monkeypatch):
    path = _write_existing(tmp_path, monkeypatch)
    changes = enrich_competitors("zoka-coffee", "Zoka Coffee", apply=True)

    # Stumptown gets both; Onyx already has youtube queries so only tiktok.
    assert any("Stumptown" in c and "youtube_search_queries" in c for c in changes)
    assert any("Onyx" in c and "tiktok_search_queries" in c for c in changes)
    assert not any("Onyx" in c and "youtube_search_queries" in c for c in changes)

    text = path.read_text(encoding="utf-8")
    assert "operator notes up top" in text            # header comment preserved
    assert "inline comment survives too" in text      # inline comment preserved
    assert '"onyx coffee lab review"' in text         # existing value untouched
    assert "Stumptown Coffee Roasters vs Zoka Coffee" in text


def test_enrich_dry_run_writes_nothing(tmp_path, monkeypatch):
    path = _write_existing(tmp_path, monkeypatch)
    before = path.read_text(encoding="utf-8")
    changes = enrich_competitors("zoka-coffee", "Zoka Coffee", apply=False)
    assert changes
    assert path.read_text(encoding="utf-8") == before


def test_enrich_missing_file_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(scaffold_mod, "CLIENTS_DIR", tmp_path / "clients")
    with pytest.raises(FileNotFoundError):
        enrich_competitors("ghost", "Brand")
