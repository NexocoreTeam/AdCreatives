# Gold Standard — the analyzer's answer key

Human-verified ads that score the analyzer: they decide (optionally) which
vision model is the default, and regression-check every prompt / taxonomy
change afterward. **Keep this set forever.** If a change makes scores drop,
roll the change back.

## How the gold set gets built: promoted, not pre-authored

The gold set is **derived from the live library**, not written from
scratch. Devin's job is reviewing and correcting AI drafts in #ad-library —
not authoring analysis cold (that was the original project brief, and
pre-authoring a gold set contradicted it). Every approved card is already a
human-verified annotation, so the answer key falls out of normal work.

**Promotion (Mitchell, ~30 min, once ~15 approved cards exist):**

1. Pick 10–15 approved cards. **Prefer cards where a human overrode the
   model** — check `provenance.model_draft_values` and the corrections
   trail in each sidecar. Corrected cards are the most informative test
   items precisely because the model got them wrong; a gold set made only
   of untouched approvals just measures the model agreeing with itself.
   Include a few clean approvals too, re-verified by you at promotion time.
2. For each card: copy its image here as `<name>.jpg` (or `.png`), and
   write `<name>.expected.yaml` from the card's APPROVED analysis (format
   below). Where the thread showed genuine ambiguity, record the
   defensible alternates under `acceptable:`.
3. Sanity-check every answer key against its image yourself — promotion is
   the strategist QA moment. Then commit the set via PR.

## Answer key format

```yaml
brand: Soft Services
media_type: static            # static | video (video = thumbnail analysis)
context:                      # optional — operator context fed to the model
  proxy_signal: "running ~4 months, 12 variations"
expected:                     # canonical taxonomy values (exact names)
  format: Us vs. Them
  hook_type: Contrast
  mechanic: The Contrast Without Comment
  awareness_stage: solution_aware
  product_role: prop
acceptable:                   # optional — defensible alternates also score
  mechanic: [The Trojan Horse]
```

Exact canonical names are in the **Creative Taxonomy — Quick Reference**
canvas in #ad-library, or `adc taxonomy` (`--markdown` for the one-pager).
Awareness stages: `unaware`, `problem_aware`, `solution_aware`,
`product_aware`, `most_aware`. Product roles: `hero`, `prop`, `reveal`,
`absent`.

`acceptable:` matters: genuinely ambiguous ads have more than one
defensible read. Without it, exact-match scoring punishes reasonable
answers and adds noise.

## Running the eval / bake-off (after promotion)

```
adc library validate --model claude-sonnet-4-6 --model gpt-4o \
    --model google/gemini-2.5-pro --runs 2
```

- The default model is `claude-sonnet-4-6` until a bake-off says otherwise —
  running one is optional now that a human reviews every card, but the
  regression use is not: **re-run this after ANY prompt, model, or taxonomy
  change** and compare against the previous `results-*.yaml`. Scores drop →
  roll back.
- Enum accuracy + self-consistency print as a table; full results (each
  model's `why_it_works` / `steal` / `avoid` prose) land in
  `results-<stamp>.yaml`. Rate the prose **blind** (1–5 in the `rating:`
  fields) before looking at which model wrote which.
- If a bake-off crowns a different model, add `--model <winner>` to the
  `adc analyze` line in the OpenClaw workflow — no code change.

## Few-shot examples

Copy 2–3 of the best gold cards into `examples.md` here (image description
+ the correct JSON per the card schema). If that file exists, `adc analyze`
appends it to the generated system prompt under "EXAMPLES OF CORRECT
ANALYSIS" — measurably improves consistency.

## Housekeeping

- `results-*.yaml` files are gitignored (regenerable). The images,
  `*.expected.yaml`, and `examples.md` are committed.
- As the library grows, promote newly-corrected cards occasionally — the
  gold set should keep covering the places the model actually fails.
