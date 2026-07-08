# Gold Standard — the analyzer's answer key

Hand-annotated ads that decide which vision model the analyzer uses, and
regression-check every prompt / taxonomy change afterward. **Keep this set
forever.** If a change makes scores drop, roll the change back.

**Who does what:** Devin drafts (Parts A–E below). Mitchell reviews and
approves at two gates. Nothing here counts until Mitchell has approved it.

## The one hard rule

**Never run `adc analyze` on a gold ad before its answer key is approved.**
The answer key must come from humans. If the model helps write the key, the
test measures whether the model agrees with itself — it can no longer catch
the model's mistakes. Classify every gold ad with your own eyes and the
skill docs only. (After Gate 1 approval, analyzer runs on these ads are
fine — that's the whole point.)

---

## Part A — Pick the ads (Devin, in Foreplay)

Pick **12–15 static image ads** (no videos), different brands:

- Prefer long-running ads (longevity = the ad is working).
- Spread the set out: across all 15, aim for at least 5 different
  mechanics, 8 different formats, and 4 of the 5 awareness stages.
- Deliberately include **2–3 ads you find genuinely hard to classify** —
  those teach us where the model needs a human.
- Note each ad's brand and Foreplay ad id as you go.

## Part B — Annotate (Devin — this is the learning part)

First, read the three vocabulary docs start to finish (budget an hour):

- `prompts/skills/motion/creative-mechanics.md`
- `prompts/skills/motion/hook-tactics.md`
- `prompts/skills/motion/visual-formats.md`

Then for each ad, put two files in this folder:

1. `<name>.jpg` — the ad image. Name it kebab-case, e.g.
   `soft-services-receipt.jpg`.
2. `<name>.expected.yaml` — your answer key:

```yaml
brand: Soft Services
media_type: static
context:                      # optional — only if Foreplay shows a signal
  proxy_signal: "running ~4 months, 12 variations"
expected:                     # exact names from the skill docs
  format: Receipt
  hook_type: Contrast
  mechanic: The Trojan Horse
  awareness_stage: problem_aware
  product_role: prop
acceptable:                   # optional — see below
  mechanic: [The Contrast Without Comment]
```

Rules of thumb:

- Values must be the **exact names** from the skill docs (`###` headings).
  Awareness stages are: `unaware`, `problem_aware`, `solution_aware`,
  `product_aware`, `most_aware`. Product roles: `hero`, `prop`, `reveal`,
  `absent`.
- Torn between two defensible values? Put your pick under `expected:` and
  the runner-up under `acceptable:` — and flag it in your Gate 1 report.
  Don't agonize alone; that's what the review is for.
- Don't look up "what would the AI say." Your read + the docs only.

## Part C — Gate 1: report to Mitchell (Devin)

Send Mitchell a short report:

1. Where the files are (branch name, or the folder if you're not on git yet).
2. A table: `name | brand | format | mechanic | awareness stage | unsure?`
3. Coverage check: which mechanics / stages the set covers, and which it
   doesn't.
4. Your questions — every ad you flagged `unsure`, and why.
5. The sentence: "I did not run the analyzer on any of these."

**Mitchell's review (Gate 1):** open each image next to its yaml; check
mechanic and awareness_stage hardest (they're the most misread); confirm
the flagged-ambiguous ads carry `acceptable:` alternates; correct or
discuss anything off; then commit the approved set to master via PR.
The gold set is now frozen.

## Part D — Run the bake-off (Devin, only AFTER Gate 1 approval)

On the machine with the repo + `.env` set up (if a model's API key is
missing, ask Mitchell — don't create accounts or handle keys):

```
adc library validate --model claude-sonnet-4-6 --model gpt-4o \
    --model google/gemini-2.5-pro --runs 2
```

- ~90 API calls; it runs sequentially, so expect 15–30 minutes. Let it
  finish. Total cost ≈ $3.
- It prints an accuracy table and writes `results-<stamp>.yaml` here with
  every model's `why_it_works` / `steal` / `avoid` prose.
- **Prepare the blind prose sheet:** for each gold ad, paste the three
  models' prose into a doc in shuffled order labeled Option 1/2/3. Keep
  the option→model mapping in a separate private note. Mitchell rates
  without knowing which model wrote which.

## Part E — Gate 2: report to Mitchell (Devin)

Send:

1. The accuracy table (paste or screenshot) + the results file path.
2. The blind prose sheet (not the mapping).
3. The `failures:` list from the results file — which fields each model
   gets wrong.
4. Your recommendation and one paragraph of reasoning. (Mitchell decides;
   your reasoning is the exercise.)

**Mitchell's review (Gate 2):** rate the prose blind (1–5 per entry), then
unblind with Devin; weigh enum accuracy + self-consistency (< ~90%
consistency = flaky enums, be wary) + prose ratings; crown the default
model. If the winner isn't `claude-sonnet-4-6`, add `--model <winner>` to
the `adc analyze` line in the OpenClaw workflow instruction — no code
change. Post the decision and the winning scores in #ad-library so the
choice is on record (results files themselves stay gitignored).

## After the decision — few-shot examples

Devin assembles `examples.md` in this folder from the 2–3 gold cards
Mitchell picks (image description + the correct JSON per the schema).
Mitchell approves, it gets committed, and `adc analyze` automatically
appends it to the prompt under "EXAMPLES OF CORRECT ANALYSIS" —
measurably improves consistency.

## Housekeeping

- `results-*.yaml` files are gitignored (regenerable). The images,
  `*.expected.yaml`, and `examples.md` are committed.
- Any future prompt/model/taxonomy change: re-run Part D's command and
  compare against the previous results before shipping.
