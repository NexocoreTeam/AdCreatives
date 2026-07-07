"""Tests for strategy/gold_eval.py and strategy/ad_library.py."""

from __future__ import annotations

import pytest
import yaml

from strategy.ad_card import save_card
from strategy.ad_library import library_status, log_library_cost
from strategy.gold_eval import GOLD_ROOT, load_gold_set, run_gold_eval
from strategy.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


def make_gold(root, name="receipt-ad", expected=None, acceptable=None):
    gold = root / GOLD_ROOT
    gold.mkdir(parents=True, exist_ok=True)
    (gold / f"{name}.jpg").write_bytes(b"img")
    spec = {
        "brand": "Soft Services",
        "media_type": "static",
        "expected": expected or {
            "format": "Billboard", "hook_type": "Warning",
            "mechanic": "The Trojan Horse", "awareness_stage": "problem_aware",
            "product_role": "hero",
        },
    }
    if acceptable:
        spec["acceptable"] = acceptable
    (gold / f"{name}.expected.yaml").write_text(
        yaml.safe_dump(spec), encoding="utf-8")


def fake_analyzer(answers_by_call: list[dict]):
    """Returns an analyze() stand-in that pops pre-baked field answers."""
    calls = {"n": 0}

    def analyze(image, **kwargs):
        answers = answers_by_call[min(calls["n"], len(answers_by_call) - 1)]
        calls["n"] += 1
        card = {
            "format": "Billboard", "hook_type": "Warning",
            "mechanic": "The Trojan Horse", "awareness_stage": "problem_aware",
            "product_role": "hero", "why_it_works": "w", "steal": "s", "avoid": "a",
        } | answers
        return {"card": card, "display": "", "issues": [], "warnings": [],
                "meta": {"model": kwargs.get("model", "?")}}

    return analyze


class TestLoadGoldSet:
    def test_empty_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="No gold ads"):
            load_gold_set(tmp_path)

    def test_key_without_image_raises(self, tmp_path):
        gold = tmp_path / GOLD_ROOT
        gold.mkdir(parents=True)
        (gold / "x.expected.yaml").write_text("expected: {format: Billboard}")
        with pytest.raises(FileNotFoundError, match="no matching image"):
            load_gold_set(tmp_path)

    def test_key_without_expected_block_raises(self, tmp_path):
        gold = tmp_path / GOLD_ROOT
        gold.mkdir(parents=True)
        (gold / "x.jpg").write_bytes(b"img")
        (gold / "x.expected.yaml").write_text("brand: X")
        with pytest.raises(ValueError, match="expected"):
            load_gold_set(tmp_path)

    def test_loads_pairs(self, tmp_path):
        make_gold(tmp_path)
        items = load_gold_set(tmp_path)
        assert len(items) == 1
        assert items[0]["name"] == "receipt-ad"


class TestRunGoldEval:
    def test_perfect_model_scores_100(self, tmp_path, tax):
        make_gold(tmp_path)
        results = run_gold_eval(["model-a"], runs_per_model=2, tax=tax,
                                root=tmp_path, analyze=fake_analyzer([{}]))
        r = results["models"]["model-a"]
        assert r["overall_accuracy"] == 1.0
        assert r["self_consistency"] == 1.0
        assert r["failures"] == []

    def test_wrong_field_scores_down_and_fails_listed(self, tmp_path, tax):
        make_gold(tmp_path)
        wrong = {"mechanic": "The Reframe"}
        results = run_gold_eval(["model-b"], runs_per_model=1, tax=tax,
                                root=tmp_path, analyze=fake_analyzer([wrong]))
        r = results["models"]["model-b"]
        assert r["field_accuracy"]["mechanic"] == 0.0
        assert r["field_accuracy"]["format"] == 1.0
        assert r["overall_accuracy"] == 0.8
        assert any("receipt-ad.mechanic" in f for f in r["failures"])

    def test_acceptable_alternate_counts_correct(self, tmp_path, tax):
        make_gold(tmp_path, acceptable={"mechanic": ["The Reframe"]})
        results = run_gold_eval(["model-c"], runs_per_model=1, tax=tax,
                                root=tmp_path,
                                analyze=fake_analyzer([{"mechanic": "The Reframe"}]))
        assert results["models"]["model-c"]["field_accuracy"]["mechanic"] == 1.0

    def test_flaky_model_loses_consistency(self, tmp_path, tax):
        make_gold(tmp_path)
        flip = fake_analyzer([{"mechanic": "The Trojan Horse"},
                              {"mechanic": "The Reframe"}])
        results = run_gold_eval(["model-d"], runs_per_model=2, tax=tax,
                                root=tmp_path, analyze=flip)
        assert results["models"]["model-d"]["self_consistency"] < 1.0

    def test_results_file_written_with_prose(self, tmp_path, tax):
        make_gold(tmp_path)
        results = run_gold_eval(["model-e"], runs_per_model=1, tax=tax,
                                root=tmp_path, analyze=fake_analyzer([{}]))
        files = list((tmp_path / GOLD_ROOT).glob("results-*.yaml"))
        assert len(files) == 1
        data = yaml.safe_load(files[0].read_text(encoding="utf-8"))
        prose = data["models"]["model-e"]["prose_for_blind_rating"]
        assert prose[0]["rating"] == ""  # strategist fills blind
        assert results["taxonomy_version"] == tax.version


class TestLibraryStatus:
    def _card(self, **overrides):
        base = {
            "brand": "X", "source_link": "", "proxy_signal": "unknown",
            "media_type": "static", "format": "Billboard", "hook_type": "Warning",
            "mechanic": "The Trojan Horse", "secondary_mechanic": None,
            "scan_path": ["a", "b"], "proof_element": "p", "product_role": "hero",
            "awareness_stage": "problem_aware", "why_it_works": "w",
            "cultural_note": "none", "steal": "s", "avoid": "a",
            "field_confidence": {"format": "high", "hook_type": "high",
                                 "mechanic": "low", "awareness_stage": "high",
                                 "product_role": "high"},
            "reasoning": {"mechanic": "", "awareness_stage": ""},
        }
        return base | overrides

    def test_counts_queue_and_grid(self, tmp_path, tax):
        save_card(self._card(), status="approved", image_path=None, tax=tax,
                  provenance={}, root=tmp_path)
        save_card(self._card(awareness_stage="most_aware", mechanic="The Reframe"),
                  status="needs-strategist", image_path=None, tax=tax,
                  provenance={}, root=tmp_path)
        data = library_status(tax, root=tmp_path)
        assert data["total"] == 2
        assert data["by_status"] == {"approved": 1, "needs-strategist": 1}
        assert len(data["needs_strategist"]) == 1
        assert "mechanic" in data["needs_strategist"][0]["low_confidence"]
        assert data["grid"]["problem_aware"]["The Trojan Horse"] == 1
        assert data["grid"]["most_aware"]["The Reframe"] == 1
        assert "The Borrowed Enemy" in data["empty_mechanics"]

    def test_cost_log_appends(self, tmp_path):
        log_library_cost("adc analyze", 0.03, note="test", root=tmp_path)
        log_library_cost("adc analyze", 0.03, note="test2", root=tmp_path)
        log_path = tmp_path / "references/swipe/analyzed/.cost-log.jsonl"
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
