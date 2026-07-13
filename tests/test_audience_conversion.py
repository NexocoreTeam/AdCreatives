import json

import yaml

from strategy.audience_conversion import collect_audience_conversion_raw


def test_collect_audience_conversion_raw_writes_expected_artifacts(tmp_path):
    clients = tmp_path / "clients"
    base = clients / "acme"
    (base / "products").mkdir(parents=True)
    (base / "voc").mkdir()
    (base / "research" / "competitor-reviews").mkdir(parents=True)
    (base / "research" / "tiktok-comments").mkdir(parents=True)
    (base / "research" / "exa" / "raw").mkdir(parents=True)

    (base / "brand-context.md").write_text("# Acme\nGut support brand.", encoding="utf-8")
    (base / "products" / "gut-balance.yaml").write_text(
        yaml.safe_dump({"name": "Gut Balance", "benefits": ["less bloating"]}),
        encoding="utf-8",
    )
    (base / "voc" / "reviews.json").write_text(
        json.dumps([
            {
                "rating": 5,
                "title": "Finally consistent",
                "text": "I feel regular for the first time in years.",
                "product": "Gut Balance",
                "source": "okendo",
            }
        ]),
        encoding="utf-8",
    )
    (base / "research" / "competitor-reviews" / "competitor.json").write_text(
        json.dumps(
            {
                "competitor": {"name": "Other Gut Brand"},
                "vendor": "none",
                "reviews": [],
                "notes": "No supported review widget.",
            }
        ),
        encoding="utf-8",
    )
    (base / "research" / "tiktok-comments" / "post.json").write_text(
        json.dumps(
            {
                "competitor_name": "Other Gut Brand",
                "post_url": "https://tiktok.example/post",
                "comments": [{"text": "Does this work better than probiotics?", "likes": 3}],
            }
        ),
        encoding="utf-8",
    )
    (base / "research" / "exa" / "raw" / "reddit-acme.json").write_text(
        json.dumps(
            {
                "query": {"label": "reddit-acme", "category": "reddit"},
                "results": [
                    {
                        "title": "Probiotics did nothing",
                        "url": "https://reddit.example/thread",
                        "text": "I tried probiotics and still felt bloated.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = collect_audience_conversion_raw(
        "acme",
        product="gut-balance",
        category="postbiotic",
        clients_dir=clients,
    )

    assert result.record_count == 5
    assert result.source_counts["own_review"] == 1
    assert result.source_counts["tiktok_comment"] == 1
    assert result.source_counts["exa_reddit"] == 1
    assert any(lane["lane"] == "competitor_reviews" for lane in result.empty_lanes)
    assert any(lane["lane"] == "brand_information" for lane in result.empty_lanes)
    assert any(lane["lane"] == "existing_personas" for lane in result.empty_lanes)
    assert result.raw_md_path.exists()
    assert result.raw_jsonl_path.exists()
    assert result.manifest_path.exists()
    assert result.research_document_path.exists()
    assert result.source_truth_path.exists()

    rows = [
        json.loads(line)
        for line in result.raw_jsonl_path.read_text(encoding="utf-8").splitlines()
    ]
    assert any("Does this work better than probiotics?" in row["text"] for row in rows)

    manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["client"] == "acme"
    assert manifest["product"] == "gut-balance"
    assert manifest["category"] == "postbiotic"


def test_collect_audience_conversion_includes_brand_info_and_personas(tmp_path):
    clients = tmp_path / "clients"
    base = clients / "acme"
    (base / "products").mkdir(parents=True)
    (base / "avatars").mkdir()

    (base / "brand-context.md").write_text("# Acme\nGut support brand.", encoding="utf-8")
    (base / "brand.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Acme",
                "unique_differentiator": "Postbiotic routine for busy adults",
                "desired_perception": "warm, credible, routine-friendly",
            }
        ),
        encoding="utf-8",
    )
    (base / "products" / "gut-balance.yaml").write_text(
        yaml.safe_dump({"name": "Gut Balance", "benefits": ["less bloating"]}),
        encoding="utf-8",
    )
    (base / "avatars" / "primary.yaml").write_text(
        yaml.safe_dump(
            {
                "name": "Routine Rebuilder",
                "pain_point": "inconsistent mornings",
                "how_they_speak": "casual and skeptical",
            }
        ),
        encoding="utf-8",
    )

    result = collect_audience_conversion_raw(
        "acme",
        product="gut-balance",
        category="postbiotic",
        clients_dir=clients,
    )

    assert result.source_counts["brand_information"] == 1
    assert result.source_counts["existing_persona"] == 1

    raw_md = result.raw_md_path.read_text(encoding="utf-8")
    assert "Unique_Differentiator" in raw_md or "unique_differentiator" in raw_md
    assert "Routine Rebuilder" in raw_md

    report_stub = result.research_document_path.read_text(encoding="utf-8")
    assert "## Brand Information" in report_stub
    assert "## Key Personas" in report_stub
    assert "## Concepts" in report_stub
