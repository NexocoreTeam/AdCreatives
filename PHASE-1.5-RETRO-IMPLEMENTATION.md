# Phase 1.5 Retro — Implementation log

*Implemented 2026-05-24 by agent. Tracks Tier 1 items #2 and #3 from `PHASE-1.5-RETRO.md`.*

Both improvements were built, wired into the existing CLI surface, and covered by automated tests. Full suite (`pytest tests/`) is green at **420 passed**, including **20 new tests** for the premise validator and **7 new tests** for the auto-fix extension.

---

## Improvement 1 — Headline-vs-body premise validator — ✅ DONE

**Why:** `pain-006 v2` shipped with a headline promising *"3 receipts the probiotic industry hides"* but a body delivering *our trial results*. The existing cross-concept leakage validator missed it because the body text DID come from the source matrix row — the premise just didn't match the headline's claim.

### What was built

| File | Change |
|---|---|
| `validators/brief_text_validator.py` | Added `validate_headline_body_premise(brief)` → `PremiseValidationResult` (single cheap Claude call, JSON-output, ~150 input / 80 output tokens). Plus `should_warn_on_premise(result)` to centralise the 0.7-confidence threshold. |
| `models/loader.py` | `save_brief` now invokes the premise validator alongside the existing leakage validator. Both are wrapped in a wide `try` so they can never break a save. Warnings go to stderr in the same style as the leakage warnings. |
| `tests/test_premise_validator.py` | 20 new tests — all use `monkeypatch.setattr(strategy.llm, "claude_complete", fake)` so zero real API calls run during the suite. |

### Behaviour

- **Headline / body extraction:** if `brief.body_copy` is non-empty, headline = `hook`, body = `body_copy`. Otherwise hook is split on the first newline: line 0 is the headline, the rest is the body. If neither yields a body, the check is skipped.
- **Warning threshold:** only emits a warning when `aligned=False AND confidence >= 0.7 AND not skipped`. Below 0.7 the model isn't sure enough; a warning would just create noise.
- **Bypass:** set `ADC_SKIP_PREMISE_CHECK=1` (or `true`, `yes`, `on`) to skip the check entirely for intentionally provocative briefs. Stub never runs in that case (verified by `test_skip_env_var_bypasses_validator`).
- **Failure modes:** any exception from `claude_complete` (auth, network, parse) returns `skipped=True, aligned=True` so the save still succeeds. Malformed JSON responses (e.g. plain text, markdown fences) are handled — `_parse_premise_response` strips ` ```json ` fences and falls back to `skipped=True` on garbage.
- **Cost target:** `max_tokens=120` on the output, ~150 input tokens. Per-call cost is well under $0.001 on Sonnet 4.6. Locked in by `test_prompt_stays_compact` which asserts `max_tokens <= 200`.

### How to use

```bash
# Default behaviour — premise check runs on every save_brief() call
adc generate ...          # warning prints to stderr if mismatch detected

# Bypass for an intentionally provocative brief
ADC_SKIP_PREMISE_CHECK=1 adc generate ...

# Warning shape on stderr:
[premise_validator] possible headline/body mismatch for brief <id> (confidence=0.88):
  reasoning: headline promises 3 anti-industry facts but body delivers pro-us trial results
  bypass with ADC_SKIP_PREMISE_CHECK=1 if the brief is intentionally provocative.
```

### Test results

```
tests/test_premise_validator.py::TestSplitHeadlineAndBody (3 tests)         PASSED
tests/test_premise_validator.py::TestPremiseValidator (10 tests)            PASSED
  - test_aligned_brief_returns_aligned_true
  - test_pain_006_v2_historical_mismatch_triggers_warning  ← the motivating case
  - test_low_confidence_mismatch_suppresses_warning
  - test_skip_env_var_bypasses_validator
  - test_skip_env_var_off_value_does_not_skip
  - test_no_separable_body_skips
  - test_claude_error_returns_skipped
  - test_malformed_response_returns_skipped
  - test_response_with_markdown_fences_parses
  - test_prompt_stays_compact
tests/test_premise_validator.py::TestShouldWarnOnPremise (4 tests)          PASSED
tests/test_premise_validator.py::TestSaveBriefHook (3 tests)                PASSED
  - test_save_brief_invokes_premise_validator
  - test_save_brief_silent_when_premise_aligned
  - test_save_brief_silent_when_skipped_via_env

20 passed in 2.22s
```

---

## Improvement 2 — `auto_fix_prompt_addition` on validated_assets — ✅ DONE

**Why:** every `adc edit` call referencing `_refs/gut-balance-product.png` fired the Posthiotic-typo warning, but the warning was actionless — the operator had to remember to manually append "fix the label to read Postbiotic" to every prompt. Most generations this session shipped with the typo.

### What was built

| File | Change |
|---|---|
| `validators/validated_assets.py` | `AssetIssue` dataclass gained an optional `auto_fix_prompt_addition: str` field (defaults to `""`). New public helper `get_auto_fix_additions(asset_paths, client_slug) -> list[str]` returns de-duped, order-preserving fix strings for the given assets. Empty string fields and unknown client slugs return `[]`. |
| `cli.py` (`adc edit`) | Pre-generation hook now (a) prints the legacy warning, (b) calls `get_auto_fix_additions`, (c) appends additions to the prompt with an `[AUTO-FIX FROM VALIDATED ASSETS]:\n` header before `submit_and_wait`, (d) prints a stderr note showing how many fixes were appended. The `prompt_or_layout` field on the sidecar metadata is now the effective prompt, so the trace records what was actually sent. The warning block moved from after-download to before-submit to make the injection possible. |
| `cli.py` (`adc ugc-ad`) | Same pre-flight check but the additions are surfaced as an **advisory** to stderr — `ugc-ad` is the PIL-overlay pipeline and never sends a prompt to an image-edit engine, so the operator gets told to re-run the base via `adc edit` first if auto-fix is registered. (The alternative was to silently swallow it; explicit advisory is friendlier.) |
| `clients/secondkind-bold/validated_assets.yaml` | Added the `auto_fix_prompt_addition` block to the existing Posthiotic-typo entry. Schema comment block at top of file expanded to document the new optional field. |
| `tests/test_ugc_overlay.py` | 7 new tests appended alongside the existing `validated_assets` tests. |

### Behaviour

- **Schema:** new field is optional. Briefs / configs without it continue to load (verified by `test_validated_assets_auto_fix_defaults_to_empty`).
- **Client-slug inference (adc edit):** the existing logic that infers the slug from a `clients/<slug>/...` output path is preserved. If no slug can be inferred, both the warning and the auto-fix are silently skipped — there's no `--client` flag because the existing code already doesn't take one.
- **Client-slug source (adc ugc-ad):** uses `effective_brand_slug` (from `--brand` flag, or brief's `client`, or fallback `secondkind-bold`), same as the existing warning lookup.
- **Dedup:** if the same asset path appears twice in a single call, its auto-fix appears only once (verified by `test_get_auto_fix_additions_dedupes_repeated_asset`).
- **Failure modes:** wrapped in a wide `try` — any registry parse error or import problem silently degrades to the legacy behaviour (no auto-fix, original prompt sent unchanged).

### How to use

```bash
# Before:
adc edit --image clients/secondkind-bold/_refs/gut-balance-product.png \
         --prompt "place the product on a marble counter"
# → ships with 'Posthiotic' typo visible

# After (no command change — auto-injection is implicit):
adc edit --image clients/secondkind-bold/_refs/gut-balance-product.png \
         --prompt "place the product on a marble counter" \
         --output clients/secondkind-bold/ai-ads/v1.png
# → stderr: "[validated_assets] Auto-appended 1 fix(es) from validated_assets.yaml."
# → effective prompt sent to hf-web:
#   "place the product on a marble counter
#
#   [AUTO-FIX FROM VALIDATED ASSETS]:
#   IMPORTANT: change the label text on the SecondKind product jar to
#   read 'Postbiotic' (with a 'b', not 'h'). The source image has a
#   typo — render the corrected label in the output."
# → ad metadata sidecar records the effective prompt (auditable trace)
```

For a new client / new asset, the operator extends `clients/<slug>/validated_assets.yaml` once:

```yaml
known_issues:
  - file: "_refs/some-asset.png"
    issue: "<plain-English description>"
    severity: warning
    workaround: "<long-form fix path>"
    auto_fix_prompt_addition: |
      <text to append to any hf-web edit prompt using this asset>
```

### Test results

```
tests/test_ugc_overlay.py — validated_assets section (10 tests, 7 new)      PASSED
  Existing:
  - test_validated_assets_loads_known_issues
  - test_validated_assets_finds_suffix_match
  - test_secondkind_bold_validated_assets_has_postbiotic_issue
  New:
  - test_validated_assets_loads_auto_fix_prompt_addition
  - test_validated_assets_auto_fix_defaults_to_empty
  - test_secondkind_bold_postbiotic_has_auto_fix
  - test_get_auto_fix_additions_returns_for_known_asset
  - test_get_auto_fix_additions_dedupes_repeated_asset
  - test_get_auto_fix_additions_empty_for_unknown_asset
  - test_get_auto_fix_additions_skips_issues_without_addition
  - test_get_auto_fix_additions_empty_for_no_client_slug

tests/test_ugc_overlay.py total: 34 passed
```

---

## Full suite

```
$ python -m pytest tests/
collected 420 items

tests/test_ad_remixer.py ...............................................  [ 11%]
........................................................                  [ 24%]
tests/test_angle_multiplier.py ......................                     [ 29%]
tests/test_awareness_mapper.py ......................                     [ 35%]
tests/test_competitive_context.py ..................                      [ 39%]
tests/test_copy_checker.py ....................                           [ 44%]
tests/test_creative_matrix.py ...................                         [ 48%]
tests/test_drive_ingestion.py ........................................    [ 58%]
tests/test_gap_analyzer.py .......                                        [ 59%]
tests/test_naming.py ...................................................  [ 71%]
                                                                          [ 71%]
tests/test_premise_validator.py ....................                      [ 76%]
tests/test_psychology_profiler.py ..........................              [ 82%]
tests/test_tier3_scrapers.py .....................                        [ 87%]
tests/test_trending.py .................                                  [ 91%]
tests/test_ugc_overlay.py ..................................              [100%]

420 passed in 7.36s
```

---

## Files touched

```
modified:
  cli.py                                     +52 / -16    (adc edit auto-fix; adc ugc-ad advisory; effective-prompt metadata)
  clients/secondkind-bold/validated_assets.yaml   +9 / -1   (Postbiotic auto-fix string + schema comment)
  models/loader.py                           +26 / -0    (premise validator hook in save_brief)
  tests/test_ugc_overlay.py                  +118 / -1   (7 new validated_assets tests; import update)
  validators/brief_text_validator.py         +183 / -3   (premise validator + helpers + docstring update)
  validators/validated_assets.py             +51 / -3    (auto_fix field + get_auto_fix_additions helper)

new:
  tests/test_premise_validator.py            +267        (20 tests; all mocked, no real API calls)
  PHASE-1.5-RETRO-IMPLEMENTATION.md          (this file)
```

Working tree is left dirty per task instructions — nothing is committed. Run `git diff` to review before staging.

---

## Notes / non-goals

- **Did not** modify the existing cross-concept leakage validator's behaviour. The premise validator is a separate, additive check.
- **Did not** add a `--skip-premise-check` CLI flag. The task offered "a flag OR env var" — the env var (`ADC_SKIP_PREMISE_CHECK`) is the cleaner choice because (a) it scopes to a whole session, (b) the brief save path lives deep inside generate/remix flows where threading a click flag down would require touching ~6 other commands, (c) it's discoverable via the warning's own bypass-hint footer.
- **Did not** add new third-party deps. Premise validator uses the existing `strategy.llm.claude_complete` wrapper.
- **Did not** run any cost-incurring commands. All Claude calls in tests are stubbed via `monkeypatch.setattr(strategy.llm, "claude_complete", fake)`.
