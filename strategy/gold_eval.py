"""Gold-standard evaluation harness for the ad analyzer.

The strategist hand-annotates 10-15 ads (the answer key); this harness runs
each through the analyzer N times per candidate model and scores the five
enum fields. It exists so model/prompt choices are measured, not vibes —
and so every future prompt or taxonomy change can be regression-checked
against the same answer key before it ships (score drops → roll back).

Gold layout (see references/swipe/gold/README.md):
    references/swipe/gold/<name>.jpg            the ad image
    references/swipe/gold/<name>.expected.yaml  the strategist's answer key

Answer keys may list `acceptable:` alternates per field — genuinely
ambiguous ads have more than one defensible read, and exact-match-only
scoring would punish defensible answers and add noise to model selection.

Scoring counts exact/acceptable matches per enum field, plus per-model
self-consistency (does the model give the same answer across repeat runs —
flaky enums are a real failure mode). Prose fields (why_it_works, steal,
avoid) are collected into the results file for the strategist to rate
blind; text quality is a human call.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from strategy.ad_analyzer import analyze_image
from strategy.taxonomy import Taxonomy, load_taxonomy

GOLD_ROOT = Path("references/swipe/gold")
SCORED_FIELDS = ("format", "hook_type", "mechanic", "awareness_stage", "product_role")


def load_gold_set(root: Path | None = None) -> list[dict[str, Any]]:
    """Load (image, answer key) pairs. Raises when empty — an empty gold
    run would report 100% of nothing."""
    gold = (root / GOLD_ROOT) if root else GOLD_ROOT
    items: list[dict[str, Any]] = []
    for expected_path in sorted(gold.glob("*.expected.yaml")):
        name = expected_path.name.removesuffix(".expected.yaml")
        image = next((p for p in (gold / f"{name}{ext}" for ext in (".jpg", ".jpeg", ".png"))
                      if p.exists()), None)
        if image is None:
            raise FileNotFoundError(f"Gold key {expected_path.name} has no matching image")
        with expected_path.open(encoding="utf-8") as f:
            spec = yaml.safe_load(f) or {}
        if not spec.get("expected"):
            raise ValueError(f"{expected_path.name} has no `expected:` block")
        items.append({"name": name, "image": image, **spec})
    if not items:
        raise FileNotFoundError(
            f"No gold ads found in {gold} — see references/swipe/gold/README.md")
    return items


def _is_correct(field_name: str, got: Any, spec: dict[str, Any]) -> bool:
    expected = (spec.get("expected") or {}).get(field_name)
    acceptable = (spec.get("acceptable") or {}).get(field_name) or []
    return got is not None and (got == expected or got in acceptable)


def run_gold_eval(
    models: list[str],
    *,
    runs_per_model: int = 2,
    tax: Taxonomy | None = None,
    root: Path | None = None,
    analyze=analyze_image,
) -> dict[str, Any]:
    """Run the bake-off. `analyze` is injectable for tests.

    Returns (and writes to gold/results-<stamp>.yaml) per-model:
    field accuracy, overall accuracy, self-consistency, failure list, and
    the prose outputs for blind rating.
    """
    tax = tax or load_taxonomy()
    gold = load_gold_set(root)
    results: dict[str, Any] = {
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "taxonomy_version": tax.version,
        "runs_per_model": runs_per_model,
        "gold_ads": len(gold),
        "models": {},
    }

    for model in models:
        correct: Counter[str] = Counter()
        attempts: Counter[str] = Counter()
        consistent = 0
        consistency_checks = 0
        failures: list[str] = []
        prose: list[dict[str, str]] = []

        for item in gold:
            context = item.get("context") or {}
            answers_by_run: list[dict[str, Any]] = []
            for run in range(runs_per_model):
                payload = analyze(
                    item["image"],
                    tax=tax,
                    media_type=item.get("media_type", "static"),
                    model=model,
                    brand=item.get("brand", ""),
                    proxy_signal=str(context.get("proxy_signal", "")),
                )
                card = payload["card"]
                answers_by_run.append({f: card.get(f) for f in SCORED_FIELDS})
                for f in SCORED_FIELDS:
                    attempts[f] += 1
                    if _is_correct(f, card.get(f), item):
                        correct[f] += 1
                    elif run == 0:
                        expected = (item.get("expected") or {}).get(f)
                        failures.append(
                            f"{item['name']}.{f}: got '{card.get(f)}', "
                            f"expected '{expected}'")
                if run == 0:
                    prose.append({
                        "ad": item["name"],
                        "why_it_works": card.get("why_it_works", ""),
                        "steal": card.get("steal", ""),
                        "avoid": card.get("avoid", ""),
                        "rating": "",  # strategist fills in, 1-5, blind
                    })
            for f in SCORED_FIELDS:
                consistency_checks += 1
                if len({str(run_ans[f]) for run_ans in answers_by_run}) == 1:
                    consistent += 1

        total_attempts = sum(attempts.values())
        results["models"][model] = {
            "field_accuracy": {
                f: round(correct[f] / attempts[f], 3) if attempts[f] else 0.0
                for f in SCORED_FIELDS
            },
            "overall_accuracy": round(
                sum(correct.values()) / total_attempts, 3) if total_attempts else 0.0,
            "self_consistency": round(
                consistent / consistency_checks, 3) if consistency_checks else 0.0,
            "failures": failures,
            "prose_for_blind_rating": prose,
        }

    gold_dir = (root / GOLD_ROOT) if root else GOLD_ROOT
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out = gold_dir / f"results-{stamp}.yaml"
    with out.open("w", encoding="utf-8") as f:
        yaml.safe_dump(results, f, sort_keys=False, allow_unicode=True, width=100)
    results["results_path"] = str(out)
    return results
