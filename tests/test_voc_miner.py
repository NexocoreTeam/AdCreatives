"""Tests for strategy/voc_miner.py — YAML-wobble recovery + per-file isolation.

The LLM call itself is not exercised (that would measure Anthropic, not our
logic) — claude_complete is monkeypatched. What IS covered: the mine → repair
→ re-mine ladder in extract_voc_from_text, fence stripping, non-mapping
outputs, and mine_voc_for_client continuing past a poisoned source file
instead of losing the whole run. Both wobble fixtures mirror failures observed
live on 2026-07-06 (a misindented ANALYST_NOTE block, then an unquoted
parenthetical after a quoted scalar — each killed a 473-review mining run).
"""

from __future__ import annotations

import pytest
import yaml

import strategy.voc_miner as voc_miner
from strategy.voc_miner import (
    VocExtractionError,
    extract_voc_from_text,
    mine_voc_for_client,
)

GOOD_YAML = """\
pain_points:
  - pain: shipping is slow
    intensity: high
money_quotes:
  - quote: "over a month for stickers"
    theme: objection
"""

# `- "scalar" (junk)` inside a block sequence is the exact wobble shape from
# the second live failure; guaranteed yaml.parser.ParserError.
BAD_YAML = """\
pain_points:
  - "shipping is slow" (stated as relief, implying fear)
  - pain: second
"""

LIST_YAML = """\
- just
- a bare list
"""


class FakeClaude:
    """Sequenced stand-in for claude_complete; records every prompt."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def __call__(self, prompt, system="", max_tokens=4096, **kwargs):
        self.calls.append(prompt)
        return self.outputs.pop(0)


def _patch(monkeypatch, outputs) -> FakeClaude:
    fake = FakeClaude(outputs)
    monkeypatch.setattr(voc_miner, "claude_complete", fake)
    return fake


# ─── Fixture sanity ──────────────────────────────────────────────────────────


def test_bad_yaml_fixture_actually_fails_to_parse():
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(BAD_YAML)


# ─── extract_voc_from_text ladder ────────────────────────────────────────────


def test_clean_parse_is_single_call(monkeypatch):
    fake = _patch(monkeypatch, [GOOD_YAML])
    out = extract_voc_from_text("reviews", "category")
    assert out["pain_points"][0]["pain"] == "shipping is slow"
    assert len(fake.calls) == 1


def test_markdown_fences_stripped(monkeypatch):
    fake = _patch(monkeypatch, ["```yaml\n" + GOOD_YAML + "```"])
    out = extract_voc_from_text("reviews", "category")
    assert "pain_points" in out
    assert len(fake.calls) == 1


def test_repair_pass_recovers_without_remining(monkeypatch):
    fake = _patch(monkeypatch, [BAD_YAML, GOOD_YAML])
    out = extract_voc_from_text("reviews", "category")
    assert out["pain_points"][0]["intensity"] == "high"
    assert len(fake.calls) == 2
    # Second call must be the repair prompt (carries the broken document),
    # not a re-mine (which would carry the review corpus).
    assert "failed to parse" in fake.calls[1]
    assert "shipping is slow" in fake.calls[1]


def test_remine_after_failed_repair(monkeypatch):
    fake = _patch(monkeypatch, [BAD_YAML, BAD_YAML, GOOD_YAML])
    out = extract_voc_from_text("reviews", "category")
    assert "pain_points" in out
    assert len(fake.calls) == 3  # mine, repair, re-mine


def test_exhausted_attempts_raise(monkeypatch):
    fake = _patch(monkeypatch, [BAD_YAML] * 4)
    with pytest.raises(VocExtractionError, match="poisoned"):
        extract_voc_from_text("reviews", "category", source="poisoned")
    assert len(fake.calls) == 4  # mine, repair, re-mine, repair


def test_non_mapping_output_triggers_remine_not_repair(monkeypatch):
    # A bare list is valid YAML, so there is nothing to "repair" — the ladder
    # should go straight to a second mining attempt.
    fake = _patch(monkeypatch, [LIST_YAML, GOOD_YAML])
    out = extract_voc_from_text("reviews", "category")
    assert "pain_points" in out
    assert len(fake.calls) == 2
    assert "failed to parse" not in fake.calls[1]


# ─── mine_voc_for_client per-file isolation ──────────────────────────────────


def _make_client(tmp_path, files: dict[str, str]) -> None:
    voc = tmp_path / "clients" / "demo" / "voc"
    voc.mkdir(parents=True)
    for name, content in files.items():
        (voc / name).write_text(content, encoding="utf-8")


def test_poisoned_file_does_not_kill_run(tmp_path, monkeypatch):
    _make_client(tmp_path, {"a.txt": "review text a", "b.txt": "review text b"})
    monkeypatch.chdir(tmp_path)
    seen = []

    def fake_extract(text, category, source="reviews"):
        seen.append(source)
        if source == "a":
            raise VocExtractionError("unparseable after retries")
        return yaml.safe_load(GOOD_YAML)

    monkeypatch.setattr(voc_miner, "extract_voc_from_text", fake_extract)
    merged = mine_voc_for_client("demo", "cat")
    assert seen == ["a", "b"]
    assert merged["pain_points"]  # b's insights survived a's failure
    assert merged["extraction_failures"] == [
        {"source": "a.txt", "reason": "unparseable after retries"},
    ]


def test_clean_run_has_no_failures_key(tmp_path, monkeypatch):
    _make_client(tmp_path, {"a.txt": "review text a"})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        voc_miner, "extract_voc_from_text",
        lambda *a, **k: yaml.safe_load(GOOD_YAML),
    )
    merged = mine_voc_for_client("demo", "cat")
    assert "extraction_failures" not in merged


def test_all_files_failing_raises_with_reasons(tmp_path, monkeypatch):
    _make_client(tmp_path, {"a.txt": "x", "b.txt": "y"})
    monkeypatch.chdir(tmp_path)

    def always_fail(text, category, source="reviews"):
        raise VocExtractionError(f"bad {source}")

    monkeypatch.setattr(voc_miner, "extract_voc_from_text", always_fail)
    with pytest.raises(VocExtractionError, match="a.txt.*b.txt"):
        mine_voc_for_client("demo", "cat")
