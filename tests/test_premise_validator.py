"""Tests for `validators.brief_text_validator.validate_headline_body_premise`.

The validator makes a single cheap Claude call to detect bait-and-switch
briefs (headline promises X, body delivers Y). All tests stub
`claude_complete` so no real API calls happen.

Pattern: import `validators.brief_text_validator as v` and
`monkeypatch.setattr(v, "claude_complete", fake)`. The module-under-test
imports `claude_complete` lazily inside the function, so we need to
inject the fake into the right namespace — see the helper below.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from validators.brief_text_validator import (
    PremiseValidationResult,
    _split_headline_and_body,
    should_warn_on_premise,
    validate_headline_body_premise,
)


# ─── Fixtures ───────────────────────────────────────────────────────────────


def _brief(
    hook: str = "x",
    body_copy: str = "",
) -> CreativeBrief:
    return CreativeBrief(
        brief_id="premise-test",
        client="secondkind-bold",
        product="Gut Balance",
        awareness_level=AwarenessLevel.PROBLEM_AWARE,
        framework=CopyFramework.PAS,
        angle="any angle",
        hook=hook,
        body_copy=body_copy,
    )


def _patch_claude(monkeypatch: pytest.MonkeyPatch, response: str) -> list[dict]:
    """Replace strategy.llm.claude_complete with a stub returning `response`.

    Returns a list that records each call's (prompt, system, max_tokens)
    so individual tests can assert on prompt content + token budget.
    """
    calls: list[dict] = []

    def _fake_complete(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        calls.append({
            "prompt": prompt, "system": system, "max_tokens": max_tokens,
        })
        return response

    # The premise validator does a local `from strategy.llm import
    # claude_complete` inside the function, so we must patch the source
    # module (strategy.llm), not the validator's namespace.
    import strategy.llm as llm_mod
    monkeypatch.setattr(llm_mod, "claude_complete", _fake_complete)
    return calls


# ─── _split_headline_and_body ───────────────────────────────────────────────


class TestSplitHeadlineAndBody:
    def test_body_copy_present_uses_hook_as_headline(self):
        b = _brief(hook="Promise", body_copy="Delivery.")
        assert _split_headline_and_body(b) == ("Promise", "Delivery.")

    def test_body_copy_empty_splits_hook_on_first_newline(self):
        b = _brief(hook="Headline line\nBody line 1\nBody line 2")
        h, body = _split_headline_and_body(b)
        assert h == "Headline line"
        assert body == "Body line 1\nBody line 2"

    def test_hook_only_no_newline_returns_empty_body(self):
        b = _brief(hook="Just a one-liner")
        assert _split_headline_and_body(b) == ("Just a one-liner", "")


# ─── validate_headline_body_premise (mocked claude) ─────────────────────────


class TestPremiseValidator:
    def test_aligned_brief_returns_aligned_true(self, monkeypatch):
        _patch_claude(monkeypatch, json.dumps({
            "aligned": True,
            "confidence": 0.9,
            "reasoning": "body delivers the promised mechanism explanation",
        }))
        b = _brief(
            hook="Why your probiotic isn't working",
            body_copy=(
                "Most live bacteria don't survive stomach acid. Here's how "
                "postbiotics solve the survival problem."
            ),
        )
        result = validate_headline_body_premise(b)
        assert result.aligned is True
        assert result.confidence == pytest.approx(0.9)
        assert not result.skipped
        assert not should_warn_on_premise(result)

    def test_pain_006_v2_historical_mismatch_triggers_warning(self, monkeypatch):
        """The motivating regression case: headline promises industry reveal,
        body delivers our trial results — bait-and-switch."""
        _patch_claude(monkeypatch, json.dumps({
            "aligned": False,
            "confidence": 0.88,
            "reasoning": (
                "headline promises 3 anti-industry facts but body delivers "
                "pro-us trial results"
            ),
        }))
        b = _brief(
            hook="3 receipts the probiotic industry hides:",
            body_copy=(
                "We ran a 6-week trial. 87% of participants reported less "
                "bloating. Average energy improved by 23%. Sleep quality "
                "up across the board."
            ),
        )
        result = validate_headline_body_premise(b)
        assert result.aligned is False
        assert result.confidence >= 0.7
        assert should_warn_on_premise(result)

    def test_low_confidence_mismatch_suppresses_warning(self, monkeypatch):
        _patch_claude(monkeypatch, json.dumps({
            "aligned": False,
            "confidence": 0.4,
            "reasoning": "headline is ambiguous; body could plausibly fit",
        }))
        b = _brief(
            hook="Try this if nothing else worked",
            body_copy="Gut Balance is built on a different mechanism.",
        )
        result = validate_headline_body_premise(b)
        assert result.aligned is False
        # Below 0.7 confidence threshold — no warning emitted
        assert not should_warn_on_premise(result)

    def test_skip_env_var_bypasses_validator(self, monkeypatch):
        # Even with a stub that would say aligned=False, the env-var
        # short-circuit must skip the call entirely.
        calls = _patch_claude(monkeypatch, json.dumps({
            "aligned": False, "confidence": 0.95, "reasoning": "bad",
        }))
        monkeypatch.setenv("ADC_SKIP_PREMISE_CHECK", "1")
        b = _brief(hook="X", body_copy="Y")
        result = validate_headline_body_premise(b)
        assert result.skipped is True
        assert result.aligned is True
        assert not should_warn_on_premise(result)
        assert calls == [], "claude_complete should not be called when skipped"

    def test_skip_env_var_off_value_does_not_skip(self, monkeypatch):
        """Set ADC_SKIP_PREMISE_CHECK=0 → still runs the check."""
        _patch_claude(monkeypatch, json.dumps({
            "aligned": True, "confidence": 0.8, "reasoning": "ok",
        }))
        monkeypatch.setenv("ADC_SKIP_PREMISE_CHECK", "0")
        b = _brief(hook="X", body_copy="Y")
        result = validate_headline_body_premise(b)
        assert not result.skipped
        assert result.aligned is True

    def test_no_separable_body_skips(self, monkeypatch):
        calls = _patch_claude(monkeypatch, "irrelevant")
        # Hook with no newline + no body_copy → no body to compare against
        b = _brief(hook="One-liner only")
        result = validate_headline_body_premise(b)
        assert result.skipped is True
        assert result.aligned is True
        assert calls == [], "should not call Claude when there's no body"

    def test_claude_error_returns_skipped(self, monkeypatch):
        def _boom(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
            raise RuntimeError("API unreachable")

        import strategy.llm as llm_mod
        monkeypatch.setattr(llm_mod, "claude_complete", _boom)
        b = _brief(hook="Promise", body_copy="Delivery")
        result = validate_headline_body_premise(b)
        assert result.skipped is True
        assert result.aligned is True
        assert "RuntimeError" in result.reasoning

    def test_malformed_response_returns_skipped(self, monkeypatch):
        _patch_claude(monkeypatch, "this is not JSON at all")
        b = _brief(hook="Promise", body_copy="Delivery")
        result = validate_headline_body_premise(b)
        assert result.skipped is True
        assert "non-JSON" in result.reasoning

    def test_response_with_markdown_fences_parses(self, monkeypatch):
        """Claude sometimes wraps JSON in ```json...``` — strip and parse."""
        _patch_claude(monkeypatch, (
            "```json\n"
            + json.dumps({"aligned": True, "confidence": 0.9, "reasoning": "ok"})
            + "\n```"
        ))
        b = _brief(hook="Promise", body_copy="Delivery")
        result = validate_headline_body_premise(b)
        assert not result.skipped
        assert result.aligned is True

    def test_prompt_stays_compact(self, monkeypatch):
        """Cost target <$0.001/save — guard against a ballooning prompt."""
        calls = _patch_claude(monkeypatch, json.dumps({
            "aligned": True, "confidence": 0.9, "reasoning": "ok",
        }))
        b = _brief(
            hook="Promise headline",
            body_copy="Short body that delivers.",
        )
        validate_headline_body_premise(b)
        assert len(calls) == 1
        # max_tokens budget should be tight — output is just a small JSON blob
        assert calls[0]["max_tokens"] <= 200, (
            f"max_tokens={calls[0]['max_tokens']} — keep it tight to "
            f"hold the per-call cost <$0.001"
        )
        assert "HEADLINE" in calls[0]["prompt"]
        assert "BODY" in calls[0]["prompt"]


# ─── should_warn_on_premise threshold logic ─────────────────────────────────


class TestShouldWarnOnPremise:
    def test_skipped_never_warns(self):
        r = PremiseValidationResult(aligned=False, confidence=0.99, reasoning="x", skipped=True)
        assert not should_warn_on_premise(r)

    def test_aligned_never_warns(self):
        r = PremiseValidationResult(aligned=True, confidence=0.99, reasoning="x")
        assert not should_warn_on_premise(r)

    def test_below_threshold_does_not_warn(self):
        r = PremiseValidationResult(aligned=False, confidence=0.69, reasoning="x")
        assert not should_warn_on_premise(r)

    def test_at_or_above_threshold_warns(self):
        for c in (0.7, 0.85, 1.0):
            r = PremiseValidationResult(aligned=False, confidence=c, reasoning="x")
            assert should_warn_on_premise(r), f"should warn at confidence={c}"


# ─── save_brief integration (verifies the wiring without real network) ─────


class TestSaveBriefHook:
    def test_save_brief_invokes_premise_validator(
        self, monkeypatch, tmp_path: Path, capsys
    ):
        """save_brief should call the premise validator and emit a warning
        when alignment fails confidently."""
        monkeypatch.chdir(tmp_path)
        # Provide a stubbed Claude response that will trip the warning
        _patch_claude(monkeypatch, json.dumps({
            "aligned": False,
            "confidence": 0.9,
            "reasoning": "mismatch",
        }))
        # Build a save-able client folder
        client_dir = tmp_path / "clients" / "demo"
        (client_dir / "briefs").mkdir(parents=True)

        from models.loader import save_brief
        b = _brief(hook="Promise", body_copy="Delivery")
        b.client = "demo"
        save_brief("demo", b)

        captured = capsys.readouterr()
        assert "premise_validator" in captured.err, (
            f"expected premise_validator warning on stderr; got: {captured.err!r}"
        )

    def test_save_brief_silent_when_premise_aligned(
        self, monkeypatch, tmp_path: Path, capsys
    ):
        monkeypatch.chdir(tmp_path)
        _patch_claude(monkeypatch, json.dumps({
            "aligned": True,
            "confidence": 0.9,
            "reasoning": "good",
        }))
        client_dir = tmp_path / "clients" / "demo"
        (client_dir / "briefs").mkdir(parents=True)

        from models.loader import save_brief
        b = _brief(hook="Promise", body_copy="Delivery")
        b.client = "demo"
        save_brief("demo", b)

        captured = capsys.readouterr()
        assert "premise_validator" not in captured.err

    def test_save_brief_silent_when_skipped_via_env(
        self, monkeypatch, tmp_path: Path, capsys
    ):
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ADC_SKIP_PREMISE_CHECK", "1")
        # This stub would warn if called — assert it's not.
        calls = _patch_claude(monkeypatch, json.dumps({
            "aligned": False, "confidence": 0.95, "reasoning": "x",
        }))
        client_dir = tmp_path / "clients" / "demo"
        (client_dir / "briefs").mkdir(parents=True)

        from models.loader import save_brief
        b = _brief(hook="Promise", body_copy="Delivery")
        b.client = "demo"
        save_brief("demo", b)

        captured = capsys.readouterr()
        assert "premise_validator" not in captured.err
        assert calls == []
