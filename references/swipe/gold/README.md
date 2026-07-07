# Gold Standard — the analyzer's answer key

Hand-annotated ads the Creative Strategist has scored personally. This set
decides which vision model the analyzer uses, and regression-checks every
prompt / taxonomy change afterward. **Keep it forever.** If a change makes
scores drop, roll the change back.

## Adding a gold ad (strategist)

1. Drop the ad image here: `<name>.jpg` (or `.png`).
2. Write `<name>.expected.yaml` next to it:

```yaml
brand: Soft Services
media_type: static            # static | video (video = thumbnail analysis)
context:                      # optional — operator context fed to the model
  proxy_signal: "running ~4 months, 12 variations"
expected:                     # canonical taxonomy values (exact names)
  format: Receipt
  hook_type: Contrast
  mechanic: The Trojan Horse
  awareness_stage: problem_aware
  product_role: prop
acceptable:                   # optional — defensible alternates also score
  mechanic: [The Contrast Without Comment]
```

`acceptable:` matters: genuinely ambiguous ads have more than one defensible
read. Without it, exact-match scoring punishes reasonable answers and adds
noise to model selection.

Aim for 10–15 ads covering different formats, mechanics, and awareness
stages — including 2–3 deliberately ambiguous ones (those are the cards that
teach us where the model needs a human).

## Running the bake-off

```
adc library validate --model claude-sonnet-4-6 --model gpt-4o \
    --model google/gemini-2.5-pro --runs 2
```

- Enum accuracy + self-consistency print as a table; full results (including
  each model's `why_it_works` / `steal` / `avoid` prose) land in
  `results-<stamp>.yaml`.
- Rate the prose **blind** (1–5 in the `rating:` fields) before looking at
  which model wrote which.
- Highest enum accuracy + best-rated prose becomes the default model.

## Few-shot examples

After the answer key exists, copy 2–3 of the best strategist-annotated cards
into `examples.md` here (image description + the correct JSON). If that file
exists, `adc analyze` appends it to the generated system prompt under
"EXAMPLES OF CORRECT ANALYSIS" — measurably improves consistency.

`results-*.yaml` files are gitignored (regenerable); the images, expected
files, and `examples.md` are committed.
