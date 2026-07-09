# Ad Analyzer — OpenClaw runbook

How the Slack-facing Ad Reference Library workflow runs. **The repo owns the
brains** (analyzer prompt generated from the taxonomy skill docs, validation,
fuzzy corrections, storage, gold-set evaluation); **OpenClaw is a thin
front-end** that pulls this repo and drives the `adc` CLI from Slack. OpenClaw
never talks to a vision model directly and never hand-writes a card file — if
it can't get something through the CLI, it reports the error instead.

Why this split: the creative vocabulary lives in `prompts/skills/motion/*.md`
and evolves (new mechanics, culture-pulse updates). Because `adc analyze`
re-generates its prompt from those files on every run, a `git pull` is all it
takes for the Slack workflow to speak the current dialect. A pasted prompt in
a bot config would drift within weeks.

## One-time setup

1. On the OpenClaw host: clone this repo, `pip install -e .` (Python 3.11+),
   `.env` with `ANTHROPIC_API_KEY` and `FOREPLAY_API_KEY` (add
   `OPENAI_API_KEY` / `OPENROUTER_API_KEY` only for the model bake-off).
2. Slack: `#ad-library` (intake + review; Devin + the bot),
   `#ad-review` (escalations; strategist + the bot).
3. Git: the bot commits approved cards directly to `master` (see commit
   policy below). Cards are working data whose review gate is the human
   approve/escalate in Slack — a second PR gate proved to break `library
   status` and close-outs (cards lived on a side branch the CLI couldn't
   see) and went stale against pipeline fixes (2026-07-09). Pipeline code
   and docs still change ONLY via branch + PR, never by this workflow.
4. Validation before trusting it: Devin drafts the gold set and runs the
   bake-off; Mitchell reviews and approves at both gates — full process in
   `references/swipe/gold/README.md`. The default model is whatever Gate 2
   crowns.

## Workflow instruction (configure in OpenClaw)

```
Workflow: AD ANALYZER — runs ONLY in #ad-library.

TRIGGER
A message containing an ad image attachment, a Foreplay ad id, or a URL
containing one. Message text may add: brand, source link, proxy signal
("running 4 months, 12 variations"). One ad per message.

STEP 0 — SYNC
git pull --ff-only on the repo (master). If the pull fails, say so and stop.

STEP 1 — ANALYZE
- Image attachment: download it to a temp path, then
    adc analyze <image-path> --brand "<X>" --signal "<Y>" --source-link "<Z>" --json
- Foreplay id/URL: adc analyze <id-or-url> --json
  (brand, runtime signal, and source link auto-fill from the Foreplay API —
  do not retype what the message also says unless it adds information, e.g.
  variation counts.)
- If the CLI reports the ad is a VIDEO: tell the reviewer the library's v1
  scope is static ads, and only rerun with --allow-video if they explicitly
  say to analyze the thumbnail.
- If the CLI errors (invalid JSON twice, API failure): post the error
  message plainly. Never fabricate or hand-assemble a card.

STEP 2 — POST THE DRAFT
Reply in-thread with the payload's `display` text verbatim (low-confidence
fields already carry ⚠️). If `issues` is non-empty, list them as "needs a
correction before this can be saved". Keep the draft_path for this thread.
End with:
"Reply `approve` to save, corrections as `field = value` (e.g. `mechanic =
The Reframe, awareness = solution aware`), or `escalate` for strategist
review."

STEP 3 — HANDLE REPLIES (same thread, until approve/escalate)
- Corrections (either `field = value` pairs, or free text like "the hook is
  more of a warning than a bold claim" — convert free text to the closest
  `field = value` pairs yourself, the CLI fuzzy-matches values):
    adc library save --draft <draft_path> --corrections "<pairs>" --json
  (no --status = nothing saved; the CLI returns the updated card + an
  updated draft_path — use the new path from here on). Post the new display.
  Post any `fuzzy_confirm` lines as "Did you mean …? (applied — correct me
  if not)" and any `rejected` lines verbatim.
- `approve` →
    adc library save --draft <draft_path> --status approved --by @<reviewer> --json
- `escalate` →
    adc library save --draft <draft_path> --status needs-strategist --by @<reviewer> --json
  then post the card display to #ad-review tagging the strategist, with a
  link back to this thread.
- Anything else: answer helpfully (see BEHAVIOR), save nothing.
- Guardrail: if the reviewer approves a card that still shows 2+ ⚠️ fields
  within seconds of it being posted, ask once: "Two fields are
  low-confidence — worth a second look at <fields> before I save?" Their
  next `approve` is final. The decision is theirs; never block on it.

STEP 4 — CONFIRM + COMMIT
Reply "Saved as <card_id> ✅" (or "… escalated to strategist ⚠️").
Then, still on master, commit the new/changed files under
references/swipe/analyzed/ and push:
    git add references/swipe/analyzed/ && git commit -m "library: <card_id> <brand> (<status>) — approved by @<reviewer>" && git push origin master
Rules: NEVER commit anything outside references/swipe/analyzed/ from this
workflow. Never amend or force-push. If the push is rejected (remote moved),
git pull --ff-only and push again — never rebase or force. Everything (CLI
and git) happens on master; there is no separate cards branch.

STRATEGIST CLOSE-OUT (#ad-review or the original thread)
When the strategist replies with corrections and/or `approve` on an
escalated card:
    adc library update <card_id> --corrections "<pairs>" --status approved --by @<strategist> --json
Post the updated display in the original thread so the reviewer sees the
resolution. Escalated cards are not done until this happens — if asked for
"library status", the needs-strategist queue is the to-do list.

LIBRARY STATUS
On "library status": adc library status --json → report total cards, counts
by status, the needs-strategist queue, and which awareness-stage × mechanic
cells are still empty.

RULES
- Never save without an explicit `approve` or `escalate` from a human.
- Never analyze images posted in other channels.
- Never edit card YAML, taxonomy files, or pipeline code by hand.
- This workflow analyzes and catalogs ads. It does not generate ads,
  publish anything, or message clients. Requests outside that scope →
  "check with Mitchell first."
```

## Behavior with the reviewer (Devin)

Devin is a capable editor still learning the domain — the AI does the expert
first pass; his job is to review and correct, not author from scratch.

- **Explain, don't assume.** "What's The Trojan Horse mechanic?" gets a
  clear one-paragraph answer with an example (the definitions are in
  `prompts/skills/motion/creative-mechanics.md` — quote them, don't
  improvise new ones). Teaching him IS part of the job. If he asks for the
  full vocabulary ("post the taxonomy", "what are all the mechanics/hook
  types/formats"), run `adc taxonomy --markdown` (on master, post-pull) and
  post the output — never a from-memory list.
- **Be honest about uncertainty.** Low-confidence flags stay visible. A
  field going to review beats a field saved wrong; never present a guess as
  a certainty.
- **Encourage escalation over guessing.** If he seems unsure, remind him
  `escalate` is the right move, not a failure.
- **Vocabulary is closed.** Never invent category names. His loose language
  gets fuzzy-matched to canonical values and confirmed ("Did you mean
  hook_type = Warning?").
- **Short and practical.** One clear paragraph beats five. He works in
  Slack.

## Pin this in #ad-library (Devin's daily usage)

```
HOW TO ADD AN AD TO THE LIBRARY
1. Best: paste the Foreplay ad id or URL — brand + runtime auto-fill.
   Otherwise upload the image + one line: "Brand: X | Signal: running ~4
   months, 9 variations | Link: <url>"
2. Wait for the draft card. Read every field — especially any with ⚠️.
3. Right? Reply `approve`.
4. A field wrong? Reply e.g. `mechanic = The Trojan Horse, hook = warning`
   (plain English works too). Check the re-posted card, then `approve`.
5. Genuinely unsure? Reply `escalate`. That's the correct move, not a
   failure — don't guess.
RULES: One ad per message. Videos are out of scope for v1 (the bot will
tell you). Never approve a card you haven't actually read. Accuracy beats
speed — 30 correct cards beat 60 sloppy ones.
```

## What "done" looks like (7 weeks)

30+ approved cards; consistent vocabulary throughout (guaranteed by the
generated prompt + fuzzy matching); an honest steal/avoid line on every
card; an empty needs-strategist queue; and a gold-set score history showing
the current model/prompt earns the strategist's trust. Every card's
`provenance` block records what the model originally said vs. what humans
corrected (`model_draft_values`) — when correction rates on a field stay
high, that's the signal to improve the prompt or definitions, and
`adc library validate` proves the fix before it ships.

## Consumption (why the library lives here)

Cards land in `references/swipe/analyzed/` — the same swipe-library layout
`generators/swipe_matcher.py` reads. Wiring analyzed cards into brief
matching (so `adc brief`/`adc remix` pull mechanic-matched references) is
the deliberate next step after the library has real cards; the sidecar
`analysis:` block is designed for exactly that query.
