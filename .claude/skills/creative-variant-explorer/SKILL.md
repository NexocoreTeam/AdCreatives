---
name: creative-variant-explorer
description: Propose 3-5 directional creative variants BEFORE building any of them, instead of building one variant at a time and iterating serially. Use when the user asks for variations, alternatives, different angles, more options, "what else could we try," "try another way," or any request that implies divergent exploration rather than incremental refinement. Triggers on phrases like "try another," "give me variations," "different angle," "what else," "more options," "any other ideas," "try something else," "more variations." Does NOT trigger for micro-iterations (color swaps, font tweaks, single-element fixes) — those proceed directly.
metadata:
  version: 1.0.0
---

# Creative Variant Explorer

This skill prevents the **iterate-serially-on-a-single-variant trap** that wasted ~$10 and 90 minutes on the SecondKind Bold Phase 1 push (6 iterations each on Earned Confidence and hook-001, when 1 round of 5 parallel options would have done it).

When the user asks for divergent exploration ("try another," "give me variations"), the default Claude behavior is to build ONE variant, wait for feedback, build the NEXT one, repeat. This skill replaces that pattern with **propose-then-build-in-parallel**.

---

## When this skill fires

The skill activates on user phrases that imply **divergent variant exploration**:

- "try another"
- "give me variations"
- "different angle"
- "what else could we try"
- "more options"
- "any other ideas"
- "try something else"
- "more variations"
- "let's try another way"
- "open to other directions"
- "what other concepts"
- "are there other ways"

The skill does NOT fire on **micro-iteration refinement** — those proceed directly without proposal:

- "make the text smaller"
- "change the headline to X"
- "use marigold instead of green"
- "fix the typo"
- "shift the layout"
- "more vertical padding"

The test: if the user is asking for **another concept / direction / angle**, fire. If they're asking for **a small fix to the current direction**, don't fire.

---

## What to do when fired

### 1. STOP. Do not generate anything yet.

The default impulse is to immediately produce a variant. Resist it. This skill exists because that impulse leads to 6-iteration serial cycles. Pause.

### 2. Propose 3-5 DISTINCT directional options in chat

Each option is a SHORT pitch (3-5 lines max). Each option must be:

- **Conceptually distinct** from the others — not a micro-variation
- **Specific enough to picture** — not "more colorful" but "use brand marigold as the primary background color"
- **Honest about trade-offs** — what the option gains, what it risks

**Format:**

```markdown
### Option A — [short name describing the direction]
- **Concept:** [1-2 sentences on the visual/creative move]
- **Mechanism it targets:** [the psychological lever — recognition, reframe, social proof, etc.]
- **Why it works:** [why this would land for this audience]
- **Risk:** [honest trade-off]

### Option B — [different direction]
...
```

Aim for 3-5 options. More than 5 becomes paralysis-by-choice; fewer than 3 isn't real divergence.

### 3. Recommend a top pick (without being pushy)

After listing options, say which 1-2 you'd lean toward and why. **One short paragraph max.** Don't lobby — just give an honest signal so the user has a starting point if they have no preference.

### 4. Wait for the user to pick

Possible responses:
- **"Build option B"** → build only B
- **"Build options A and C"** → build both in parallel
- **"Build them all"** → build all in parallel (warn about cost if 4+)
- **"None of these — try X instead"** → user is giving you a new direction; build X
- **"Pick the best one"** → build your top pick

Do NOT proceed until the user gives a clear pick (or you offer a default and the user implicitly accepts via silence/agreement).

### 5. Build the picked option(s) in PARALLEL

If multiple options were picked, build them **simultaneously** using parallel tool calls (multiple `adc edit` calls in a single message, or a background agent if the lift is heavy). Do NOT build them sequentially — the whole point of this skill is to amortize the cost of divergence into one parallel pass.

Note on `hf-web` rate limits: 2-3 concurrent jobs is safe. If 4+ options were picked, use a background agent to handle queuing.

### 6. After the user reviews, ALLOW serial iteration

Once a winner emerges from the parallel pass, switch back to normal iteration mode. Micro-tweaks on the chosen direction (color shift, font swap, copy edit) proceed serially as normal — this skill only governs the divergent step.

---

## Worked examples — what this would have changed on the SecondKind Bold push

### Earned Confidence (6 iterations → would have been 1 round of 5)

**Actual session:**
1. v1 — calm cream + black serif
2. v2 — cream + marigold "sell" + dot cluster (user: "try with marigold")
3. v3 — full marigold background (user: "try a marigold option")
4. v4 — seeds vs harvest metaphor (user: "scroll-stopping")
5. v5 — specimen debris (user: "try all 3")
6. v6 — memento mori (built in same round as v5)

**With this skill, after the user said "give me a marigold variation":**

> I'll fire `creative-variant-explorer` here since this is a divergent request. Five distinct marigold-forward directions:
>
> ### Option A — Subtle marigold accent on the italic word
> Cream bg, headline mostly black, only "sell" rendered in marigold. Lowest risk, highest brand restraint.
>
> ### Option B — Full marigold background
> Bold brand-color-forward. Loud scroll-stop, less editorial calm.
>
> ### Option C — Marigold seeds-vs-harvest metaphor
> Two open capsules: raw seeds vs ground powder. Brand-positioning visual story.
>
> ### Option D — Marigold "specimen debris" still life
> Cracked transparent capsules scattered around the intact jar. Double-take scroll-stop.
>
> ### Option E — Marigold "memento mori"
> Tasteful funeral-symbolic still life. Maximum pattern-interrupt, riskiest tone.
>
> My pick: B and D in parallel — they test the brand's load-bearing question (does marigold-forward stop the scroll cold without going too far?).

User picks 3 of the 5, builds in one parallel pass. **Saved:** 4 serial generation rounds, ~$2-3, ~30 minutes.

### hook-001 (6 iterations → would have been 1 round of 4)

**Actual session:**
1. v1 — single dying capsule in amber acid
2. v2 — test tube US-vs-THEM (user: "lackluster, try another")
3. v3 — before/after split (user: "try another, hard to grasp")
4. v4 — bottle cascading pills into acid (built parallel with v3)
5. v5 — open capsule split with arrows (user: showed Seed ref)
6. v6 — same as v5 but marigold + serif (user: "change colors")

**With this skill, after "this looks lackluster, try another":**

> Firing the variant explorer. Five distinct visual concepts for the "70% transit-mortality" mechanism:
>
> ### Option A — Test tube US-vs-THEM
> Two tubes side by side, scientific specimen aesthetic.
> Risk: "probiotic vs postbiotic" requires viewer to already know the distinction.
>
> ### Option B — Before/After vertical split
> One capsule top (intact), same capsule bottom (cracked). Diagram-as-story.
> Strength: zero interpretation cost.
>
> ### Option C — Cinematic bottle cascade
> Bottle tipping, pills falling into beaker, mid-action dissolution.
> Strength: drama. Risk: requires the viewer to read "acid below."
>
> ### Option D — Open capsule with powder split
> Single capsule open, 70/30 powder pile visualization with hand-drawn arrows.
> Strength: tells the whole story in one frame.
>
> My pick: B and D in parallel — both have low interpretation cost.

User picks 2, builds in one pass. **Saved:** 4 serial rounds, ~$2-3, ~40 minutes.

---

## Edge cases

### When the user is exploring AND asking for an iteration in the same message

Example: "Try a marigold variation, but make it more atmospheric this time."

Treat the **first half** as the variant exploration trigger, but inform the variant proposal: every option you propose should honor the "more atmospheric" constraint. Don't propose options that fail that constraint.

### When the user explicitly waives the skill

Example: "Just build one. No need to brainstorm."

Skip the proposal step. Build directly. The skill is sticky-on by default but the user can opt out per-turn.

### When you have <3 reasonable directions

If the request is so constrained that only 1-2 distinct directions are reasonable (e.g. very narrow brand rules + tight creative spec), say so explicitly: "Honestly, only 2 directions make sense here given [constraint]. Both: [A], [B]. Want me to build both?"

Don't pad to 5 options for the sake of the skill. 2 honest options beats 5 options where 3 are filler.

### When parallel building isn't feasible

If `hf-web` rate limits are tight, the work is heavy (10+ generations), or the user wants to be very budget-conscious, switch the parallel-build step to serial — but **keep the proposal-first pattern**. The proposal is the load-bearing move; parallel building is the efficiency multiplier.

---

## Why this exists

Captured from the SecondKind Bold Phase 1 production push (2026-05-24). Of the 9 final ads shipped, 2 (Earned Confidence + hook-001) took 6 iterations each to find the winner — and every iteration was a discrete creative direction that could have been proposed upfront. Net cost: ~$8-10 in unnecessary generations + ~90 minutes of conversation overhead.

The lesson: **when a user wants divergence, propose; when they want refinement, build.** This skill enforces that distinction.

## Important: what this skill does NOT do

- It does NOT replace iteration. Refinement within a chosen direction still proceeds serially as normal.
- It does NOT force a 5-option proposal when fewer make sense.
- It does NOT change how the underlying generation pipelines work (`adc edit`, `adc ugc-ad`, PIL overlay). It only changes WHEN they're called and in WHAT order.
- It is NOT a substitute for understanding the user's actual intent. If you're not sure whether a request is divergent or refinement, ask before firing.
