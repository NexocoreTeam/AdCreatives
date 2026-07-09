# Devin — Your 7-Week Plan

Role: Static Ad System & Competitor Research Intern · Nexocore
Cohort: July 6 – August 21, 2026 · ~60 hours total (~8–9 hrs/week)
Mentor: Mitchell · Works with: Creative Strategist (weekly), Wasif (video intern)

> **v2 (updated Jul 9).** The AI ad analyzer was built and battle-tested
> during Week 1, before your start in the system. You arrive to a working
> tool — which means you start the real job (reviewing ads) on day one,
> and the testing engine gets almost a full extra week of runway.

## The mission in one paragraph

Nexocore makes ads with AI (Higgsfield) driven by an agent (OpenClaw) in
Slack. The system's weakness: when we pull a competitor ad as a reference,
it doesn't understand *why* that ad is good — so the outputs are
hit-or-miss. Your job is to fix that in three moves: (1) **build out the
Ad Reference Library** — the AI analyzer drafts an expert breakdown of
every competitor ad, and you review, correct, and approve each card until
the library is deep and trustworthy, (2) spend most of your internship
**testing** — finding the exact step-by-step methods that make Higgsfield
produce great ads reliably, and (3) **teach every proven method to our
strategist agent** the moment you prove it, so the whole system keeps
working after you leave.

Two rules that govern everything you do:

- We never copy competitor ads. We extract the mechanic (the idea that
  makes it work) and rebuild it as brand-owned. Never reuse their creator,
  exact copy, or visual identity.
- Higgsfield gets max 2 inputs per generation. Anything more complex
  becomes a chain of simple steps. Finding the best chains is your job.

And one habit: log your hours in the tracker the same day you work them.
You submit hours to VFC weekly, and your stipend depends on the final
total being right.

## Week 1 (Jul 6–10) — Learn the system, first cards in

Goal by Friday: you can explain how our creative system works, in your own
words, to Mitchell — and your first ~10 reviewed cards are in the library.

- Get your access working: Slack (+ the #ad-library channel), Higgsfield,
  your Nexocore Gmail, Canva, Foreplay, Apify. You never handle API keys —
  those live on the server. If any tool asks you for one, ask Mitchell.
- In #ad-library, read the two canvases at the top of the channel:
  **How to Add an Ad** (your daily loop, step by step) and **Creative
  Taxonomy — Quick Reference** (every allowed value for every card field).
  You are NOT expected to know this vocabulary — the AI drafts the expert
  analysis; you review and correct it. You're the editor, not the author.
  Ask the bot "what's The Trojan Horse mechanic?" anytime — teaching you
  is part of its job.
- Watch the Loom SOPs (system overview, OpenClaw in Slack, Higgsfield
  statics, what a good ad looks like, QA rules).
- Read the Creative System Overview doc — the bible for how we make ads
  today.
- Shadow the Creative Strategist on 2–3 live ads. Watch how they pick
  references, what they reject, and why.
- **Start the loop with real ads from Foreplay**: post the ad id in
  #ad-library → the AI drafts a card → you read every field (especially
  any marked ⚠️) → correct what's wrong (`mechanic = The Reframe`), then
  `approve` — or `escalate` when genuinely unsure (that's the correct
  move, never a failure). Prioritize proven ads: long-running, many
  variations, and use Foreplay's Display Format → Image filter — video
  ads are out of scope for now and the bot will decline them.
- Mitchell reviews each of your first ~10 approved cards and gives you
  feedback — the system records exactly what the AI said versus what you
  corrected, so this calibration is fast and specific.
- Checkpoint: explain the system back to Mitchell. If you can't yet,
  that's fine — Week 2 waits until you can.

## Week 2 (Jul 13–17) — Build out the library

Goal: 15–20 approved cards, an honest steal/avoid line on every one, and
an empty escalation queue.

- Keep the daily loop going. Every card gets an honest steal/avoid line:
  what we can reuse (the mechanic, the structure, the proof logic) and
  what we must never copy (the person, the exact words, their brand look).
- Ask "library status" in #ad-library anytime: total cards, the
  escalation queue, and the coverage grid (awareness stage × mechanic)
  showing which combinations the library still lacks. Use the gaps to
  steer which ads you pull next.
- Around ~15 cards, Mitchell promotes a subset of your reviewed cards
  into the gold set (his job, ~30 minutes, not yours) — from then on,
  every future change to the analyzer gets automatically scored against
  human-verified answers. Your careful reviewing this week is literally
  what makes that possible.
- The library doesn't need to be "finished" — it keeps growing all
  internship. It needs enough approved cards (10–15) that testing can
  start. Target ~30 total by mid-internship.
- Pacing well? Start E1 (below) late this week. The analyzer was built
  early, so the testing engine inherits the saved time.

## Weeks 3–7 (Jul 20 – Aug 21) — The testing engine

This is the core of your internship: five straight weeks of experiment →
winner → teach the agent → verify → next experiment.

> Full step-by-step protocols for every experiment — setup, arms, grading
> rubric, decision rules, time budgets, traps — live in
> `docs/experiments-e1-e7.md`. This section is the overview.

You take real ad tasks, try them 2–3 different ways, compare outputs side
by side, and record which way won. Your grading rubric is always the card:
does the output preserve what the card said mattered (the mechanic, the
scan path, the product role)? That's a checklist judgment, not an expert
one — you can do it from day one.

### The seven experiments, in priority order (findings stack, so order matters):

- E1 — Remake chains: one-shot generation vs. two-step (remake with our
  product → then restyle). Test per ad format.
- E6 — Prompt format: agent writes the prompt as structured JSON vs. a
  tight natural-language paragraph. Also: how many card fields can go in
  a prompt before HF gets confused? (Bet: 3–4. Prove it.)
- E2 — Ads with people: does adding a person mean a third step (remake →
  restyle → swap person), or can the swap ride along in step 2?
- E3 — Realistic people: Pinterest creator photo as reference vs. HF Soul
  generating the person vs. both combined. Grade on realism (hands, skin,
  eyes) and how native it feels in a feed.
- E4 — Unique brand vibe: run the SAME mechanic for two different brand
  style cards. Pass condition: a teammate can tell which brand each
  output belongs to without being told. If they look like siblings, the
  brand card needs more force.
- E7 — HF's internal models: same prompt + references across HF's image
  models, one bake-off per job category (photoreal people / product
  statics / stylized). Pick a default per category, done.
- E5 — No-reference generation (stretch): can the system make a
  whitespace-format ad from just a card + copy, with zero example image?
  If yes, the library's gap grid becomes a goldmine.

### How every experiment ends: the teach-the-agent loop

An experiment is not finished when you know the winner — it's finished
when the agent knows it. Same week, every time:

- Turn the result into a one-sentence rule: "For receipt-style remakes:
  step 1 remake with product, step 2 restyle. Never combine."
- Tell the agent to update its instructions with that rule. The agent
  must reply with exactly what it changed — if it just says "got it," ask
  it to show the updated instruction. No shown change = nothing learned.
- Verify in a fresh chat: new conversation, fresh task, no hints. Does
  the agent do it the winning way on its own? If not, reword and go again.
- Regression check: re-run your 3–4 standard test tasks to make sure the
  new rule didn't break an old one. If it did, narrow the wording ("for
  receipt-style..." not "always...").
- Every change posts automatically to the changelog channel for
  Mitchell/strategist to glance at.
- One row in your log: lesson, evidence link, verified ✅, regression ✅.

There is never a backlog of untaught findings — the agent gets smarter one
verified rule at a time, all internship long.

### Rules for all experiments

- Change one variable at a time.
- Log everything in the experiment tab: question, setup, output links,
  winner, why.
- When an output is bad, run the blame test — is the card wrong (fix it
  in the card's Slack thread: `update AD-0XX: field = value`)? Is the
  prompt unfaithful to the card (ask the agent to show the prompt it
  sent, compare to the card)? Or is HF just incapable in one step (split
  the chain)?
- Keep adding cards to the library as you go — every new reference you
  test with gets analyzed and approved like any other.

### Also woven through these weeks (teach as you hit them, same method):

- Sourcing rules: Pinterest is for moods, organic scenes, and creator
  looks ONLY — never for ad mechanics. Mechanics come from Foreplay/Apify.
- Product asset discipline: build the clean cutout/approved-label folder
  for SecondKind the first time pasted-product or label-damage problems
  show up in your tests.
- QA gate: the pre-send checklist (spacing, alignment, halos, label
  damage, artifacts, emoji issues) taught to the agent as a formal final
  step.

Midpoint check (Week 4): you should be at ~30 logged hours. Review pacing
and experiment priorities with Mitchell. If time runs short later, E5
drops first, then E7 gets scoped down — E1–E4 must get done properly.

## Week 7 (Aug 17–21) — Finish, prove it, hand it off

Goal: the system runs without you.

Week 7 is still a testing week — but the last few days shift to closing
out:

- Final sweep: any cleanup items not yet taught (sourcing rules, asset
  folder, QA gate) get finished and taught now. Confirm everything proven
  is saved into GBrain / the client brains.
- Final report: mostly written already — it's your experiment log and
  teaching log, organized. Outcomes, evidence, what's proven, what's
  untested (with the protocol for finishing it).
- The demo: in front of the Nexocore team, someone who is NOT you drops a
  competitor ad into Slack. The agent analyzes it, runs the right chain,
  passes QA, and delivers an on-brand ad. If that works, your internship
  worked.
- Handoff: files organized, access notes, open items list.
- Log your final hours. (Post-cohort: VFC confirms your hours Aug 23 –
  Sep 4 — your tracker being complete and accurate is what makes that
  painless.)

## Your weekly rhythm (every week)

- Weekly check-in with Mitchell: progress vs. this plan, blockers, next
  week.
- Log hours same-day; submit to VFC weekly.
- Post anything you learn about what works in HF to the shared findings
  log — Wasif and the production team feed the same log from their side.
- When stuck for more than ~30 minutes: ask. In Slack, out loud. The
  agent can teach you our vocabulary; Mitchell and the strategist can
  unblock everything else. Escalating is a skill here, not a weakness.

## How you'll be judged (in a good way)

Not on volume — on proof. Thirty correct cards beat sixty sloppy ones. One
verified lesson taught to the agent beats five unverified claims. The
final demo is the whole game: a system that works when you're not driving
it.
