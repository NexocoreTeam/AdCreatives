# The Seven Experiments — Detailed Protocols (E1–E7)

For: Devin · Nexocore Static Ad System · companion to
[devin-7-week-plan.md](devin-7-week-plan.md)

Rules that apply to every experiment: change one variable at a time ·
grade every output against the reference card · max 2 inputs per HF
generation · `enhance_prompt: false` always (auto-enhance rewrites prompts
and makes results unattributable) · log everything (setup, output links,
winner, why) · every winner gets taught to the agent the same week
(teach → fresh-chat verify → regression check → changelog).

One principle underneath everything: **AI generates pixels; Python/PIL
composes layouts and text.** Headlines, CTAs, grids, and brand marks are
the PIL pass — plan generations to leave clean space per the card's scan
path, grade the pixels, and never blame the AI step for text it was never
supposed to render.

## How grading works everywhere

Score each output on the card checklist, 0–2 each (0 = fail, 1 = partial,
2 = clean), for a /10 total:

- **Mechanic preserved** — the persuasion move the card named still lands,
  including its proof element
- **Scan path holds** — the eye travels in the card's order
- **Product role correct** — hero/prop/reveal/absent as the card said
- **Brand-owned** — nothing copied: not their creator, exact copy, or
  visual identity
- **Clean execution** — no artifacts, halos, label damage, broken
  hands/text

**Run each variant 3 times, not once** — HF has randomness, so a single
output proves nothing. Compare the three-run average.

**The blame test, before any verdict.** When an output is bad: is the
card wrong (fix it in its Slack thread: `update AD-0XX: field = value`)?
Is the prompt unfaithful to the card (ask the agent to show the prompt it
sent)? Only then blame the chain or the model.

**The standard test set (S1–S4).** As experiments complete, freeze their
best task as a regression task: after E1, S1 = comparison-format remake
and S2 = product-static remake; after E2/E3, S3 = person-in-frame ad;
after E4, S4 = brand-vibe task on the second brand. Every teach-the-agent
loop re-runs S1–S4. Pin the exact inputs (card, assets, prompt) in the
experiment tab so reruns are identical.

---

## E1 — Remake chains: one-shot vs. two-step

Priority 1 · run first · ~3–4 hrs

**The question:** When we remake a competitor ad with our product, is it
better to ask HF for everything in one generation, or split it into two
steps?

**Why it matters:** This is the most common job the system does. Every
other experiment runs on top of whatever chain wins here — so this answer
comes first.

**Setup:** Pick 3 reference ads from the library, one per major format
type (e.g., one receipt-style/comparison, one product static, one
lifestyle scene). For each you need: the card, the reference image, and a
clean SecondKind product shot.

**Variants:**

- A (one-shot): single generation — reference ad + product image, prompt
  asks for the full remake including brand look.
- B (two-step): step 1 = remake reference with our product, neutral
  styling. Step 2 = step 1's output + brand reference, restyle only,
  structure untouched.

**Procedure:** For each of the 3 reference ads, run A three times and B
three times (18 generations total). Grade against the card. Log per
format — the answer may differ by format.

**Decision rule:** If B wins by 2+ points average for a format, two-step
becomes the rule for that format. If they tie, one-shot wins (fewer steps
= cheaper and faster). Mixed results by format are a fine outcome —
that's exactly the per-format recipe knowledge we want.

**Teach the agent:** one rule per format, e.g., "For receipt-style
remakes: two-step, never combined. For simple product statics: one-shot
is fine."

**Traps:** Label damage on the product cutout → that's the trigger to
build the clean-cutout/approved-label asset folder (woven-through task),
not a chain verdict.

---

## E6 — Prompt format: JSON vs. natural language, and how much card fits

Priority 2 · run immediately after E1 · ~3–4 hrs

**The question:** (a) When the agent converts a card into an HF prompt,
does HF respond better to structured JSON or a tight natural-language
paragraph? (b) How many card fields can go into one prompt before HF gets
confused?

**Why it matters:** Every generation in every later experiment uses a
prompt the agent wrote. If the prompt style is wrong, every later result
is polluted — a "Soul vs. Pinterest" loss might really be a bad-prompt
loss in disguise. Settle this before E2–E7.

**Setup:** 2 reference ads (use E1 winners' chain). Same card, same
chain, same references — ONLY the prompt changes. Write prompts as if the
reference images don't exist, then anchor with "the same product as
reference 2" — the documented identity-prompt pattern.

**Variants (part a):**

- A (JSON): the card fields rendered as a structured JSON prompt.
- B (natural language): the same fields as one tight paragraph.

**Variants (part b, run with the part-a winner):**

- C (minimal): 3 fields — mechanic, scan path, product role.
- D (medium): 5–6 fields — add proof element, format, brand palette line.
- E (maximal): everything on the card.

**Procedure:** 3 runs per variant per reference ad. For part b, watch for
the confusion signature: outputs that ignore instructions, mash elements
together, or drift off-mechanic as field count rises.

**Decision rule:** Part-a winner becomes the agent's default prompt
style. Part b: the highest field count that doesn't degrade scores
becomes the cap (bet: 3–4 — prove or disprove it).

**Teach the agent:** "Build HF prompts as [winner style]. Include at most
[N] card fields per prompt: always mechanic and scan path; add others
only if directly relevant to the step."

---

## E2 — Ads with people: 2-step vs. 3-step

Priority 3 · ~3 hrs

**The question:** When the reference ad includes a person, does the
person-swap need its own step, or can it ride along in an existing step?

**Why it matters:** Person ads are where HF breaks first — faces and
hands fall apart when the model juggles too much. And person-swaps are
mandatory: we can never keep the competitor's creator.

**Setup:** 2 creator-style reference ads from the library + a Pinterest
creator reference (the person we're swapping in) + product shot. Use the
E1-winning chain and E6-winning prompt style.

**Model rules (documented, don't rediscover):** person swaps use
`nano_banana_pro` with the face reference passed FIRST in the inputs —
it's the only validated identity-preserving route. `soul_2` does style
transfer: right vibe, wrong face. Never use it for a specific person.

**Variants:**

- A (2-step): step 1 = remake with our product. Step 2 = restyle + swap
  person in one generation (output + creator photo = 2 inputs, brand look
  carried by the prompt).
- B (3-step): remake → restyle → swap person (step-2 output + creator
  photo).
- C (swap-first, optional if A and B both disappoint): swap the person in
  the reference first, then remake with product, then restyle.

**Procedure:** 3 runs per variant per ad. Grade on the standard checklist
PLUS the E3 realism check (hands, eyes) — a perfect mechanic with a
melted face is a fail.

**Decision rule:** Fewest steps that consistently produces a clean,
realistic person wins. If B wins, that confirms the hypothesis: person
work needs isolation.

**Teach the agent:** "For ads containing a person: use [N]-step chain,
person-swap happens at step [X], always with only [output + creator
reference] as inputs, always nano_banana_pro, never soul_2."

---

## E3 — Realistic people: Pinterest reference vs. HF Soul vs. combined

Priority 4 · ~3–4 hrs

**Ground truth first.** The repo already has a VALIDATED recipe for
people who don't read as AI — `.claude/skills/realistic-person-image/`
(registers: camera-roll / editorial / commercial-clean; Soul V2 as the
anti-polish base; `nano_banana_2` for reference-faithful upgrades). Two
documented bugs to respect: never feed a Soul output back into Soul as a
reference (it swaps the face), and nano-banana from text alone stays
editorial-polished no matter the prompt — don't fight it for camera-roll
looks. E3 does not re-litigate any of that; it extends the recipe to
in-feed ad creative and tests the arm the skill doesn't cover: real
creator photos as references.

**The question:** What's the best source for a believable human in our
ads — a real Pinterest creator photo as reference, HF Soul generating the
person from scratch, or Soul first then refined with a Pinterest
reference for pose/styling?

**Why it matters:** "Obviously AI" people kill ad performance. The winner
becomes the standard input for every creator-style ad we make.

**Setup:** One brief, held constant: "late-20s woman, morning kitchen,
holding SecondKind Gut Balance, natural light, iPhone-photo energy." Use
the E2-winning chain.

**Variants:**

- A (Pinterest ref): real creator photo as the person reference
  (`nano_banana_pro`).
- B (Soul): Soul V2 generates the person from the text brief, no person
  reference (the skill's register-A recipe).
- C (combined): Soul generates the person → that output + Pinterest
  reference for pose/styling refinement in a second step
  (`nano_banana_2`).

**Procedure:** 3 runs each. Grade on the realism checklist: hands
(finger count, natural grip), eyes (focus, catchlights), skin (texture
vs. plastic), hair edges, background coherence — and the feed test: drop
the output next to 3 real UGC posts and ask a teammate "which one is the
ad?" If they can't tell, that's a pass.

**Also log: consistency.** If we need the same "person" across 3 ad
variations, which source keeps them recognizable? Run one variation set
for the top scorer.

**Decision rule:** May split by use case — close-up creator statics might
need one answer, background lifestyle people another. Log separately and
allow two rules.

**Teach the agent:** "For close-up creator ads, source the person via
[winner]. For background/lifestyle people, use [winner]. Pinterest
creator references are for people, poses, and moods only — never ad
mechanics (those come from Foreplay/Apify)."

---

## E4 — Unique brand vibe: same mechanic, unmistakably different brands

Priority 5 · ~3 hrs

**The question:** Can the system take ONE mechanic and produce genuinely
distinct looks for two different brands — or does everything drift toward
the same generic "AI aesthetic"?

**Why it matters:** This is the "make it uniquely ours" problem. If two
clients' ads look like siblings, we don't have a system, we have a
template.

**Setup:** One mechanic from the library (e.g., receipt comparison). Two
brand style cards with real force behind them — palette, fonts, product
truth, mood words, no-go's. Use SecondKind + magic-spoon (both live in
`clients/` and contrast hard: clinical supplement vs. playful cereal).
Winning chain + prompt style from E1/E6.

**Variants:**

- A: generation guided by the brand card alone (injected into the restyle
  step).
- B (diverge/converge): HF freestyles 4–6 style options for the brand
  with no reference constraint → Mitchell/strategist picks one → final
  build uses reference card + chosen style + brand card.

**Procedure:** Run both variants for both brands (3 runs each = 12
outputs). Strip or blur logos and product labels before judging — the
test is vibe, not reading the label. Then the blind test: a teammate
sorts the unlabeled outputs by brand.

**Decision rule:** Pass = 100% correct sorting AND both sets score clean
on the card checklist. If A passes, great — cheapest path. If only B
passes, the diverge/converge loop becomes standard for new-look requests.
If neither passes, the brand cards are too weak — rewrite them with more
specific, forceful language (palette hexes, lighting character, casting,
texture words) and rerun. That finding is itself valuable: it defines
what a brand card must contain.

**Teach the agent:** "When a brand look is needed: [A or B flow]. Brand
cards must include [the elements that proved necessary]. If the requester
can't articulate the look, run the diverge step and present options."

---

## E7 — HF's internal models: pick a default per job category

Priority 6 · ~2–3 hrs · scope-controlled

**Ground truth first.** The Higgsfield skill already has a
model-selection table (`nano_banana_pro` = identity + reliable in-image
text; `text2image_soul_v2` = anti-polish people; `soul_cast` = 16:9
one-offs; Soul-ID training rarely worth it under 20 shots). E7 verifies
that table per job category and catches anything new — it is not a
from-scratch bake-off.

**The question:** Which HF image model is the default for each category
of job?

**Setup:** Three job categories, one representative task each (from
S1–S4), all using proven chains/prompts:

- Photoreal person (use the E3-winning source)
- Product static (clean product-hero shot)
- Stylized/graphic (receipt, notes-app, or graphic-native format)

**Procedure:** Per category, run the same task through the table's
recommended model + challenger models available (3 runs per model). Grade
against the card + category-specific criteria (realism for people, label
fidelity for product, native accuracy for graphic).

**Decision rule:** Highest average per category = default model for that
category. Do NOT expand into sub-sub-categories. If a default overturns
the skill's table, the table gets updated via Mitchell (repo docs change
by PR) in the same teach loop. Revisit only when HF ships a new model —
re-run this same protocol; it's now a permanent benchmark.

**Teach the agent:** "Default models: photoreal person → [X]; product
statics → [Y]; stylized/graphic → [Z]. Override only on explicit
instruction."

---

## E5 — No-reference generation (STRETCH — only if time allows)

Priority 7 · ~2–3 hrs · drop first if behind

**The question:** Can the system make a good ad from just a card + copy —
no example image at all?

**Why it matters:** The library's coverage grid (`library status` shows
awareness stage × mechanic; format whitespace shows up as formats with no
cards) reveals ad types nobody in the category is running. There are no
references for those, by definition. If knowledge alone can drive
generation, whitespace becomes a competitive weapon.

**Setup:** Pick one whitespace combo (a format × mechanic pairing with
zero cards). Write the concept as if it were a card: mechanic definition
(from the taxonomy), intended scan path, product role, copy lines, brand
card.

**Variants:**

- A (pure prompt): generate from the written concept alone.
- B (build-the-reference-first): mock up a rough reference in Canva (even
  ugly — just the structure), then run the normal remake chain on it.

**Procedure:** 3 runs each. Grade against the written concept the same
way you'd grade against a card.

**Decision rule:** If A works → huge: whitespace ads are makeable on
demand; teach it. If only B works → the finding is "references are
load-bearing; whitespace requires a Canva mockup step first" — also worth
teaching. If neither works → log it honestly as an open problem with this
protocol attached; that's a legitimate handoff item, not a failure.

**Teach the agent:** whichever pathway proved out, as the standard flow
for "make me a [format] ad we have no reference for."

---

## Sequencing and time budget

1. E1 — remake chains · 3–4 hrs · needs: library seeded (10–15 cards)
2. E6 — prompt format · 3–4 hrs · needs: E1 winner
3. E2 — person chains · 3 hrs · needs: E1 + E6 winners
4. E3 — realistic people · 3–4 hrs · needs: E2 winner
5. E4 — brand vibe · 3 hrs · needs: E1 + E6 winners, brand cards written
6. E7 — HF model bake-off · 2–3 hrs · needs: all proven chains
7. E5 — no-reference (stretch) · 2–3 hrs · needs: library grid populated

Total: ~20–24 hours of experiment work across Weeks 3–7, leaving room for
the teach-the-agent loops (~30–60 min per lesson), library growth, and
the woven-in cleanup items. If behind at the Week 4 midpoint: drop E5,
scope E7 to two categories, protect E1–E4 at full quality.

## The log format (one row per experiment run set)

- Experiment / variant — e.g. `E1-B (two-step)`
- Reference card — e.g. `AD-014 (receipt comparison)`
- Setup — e.g. `Step 1: ref + product. Step 2: output + brand restyle`
- Output links — the 3 generation links
- Card score — avg of 3, e.g. `8.3 / 10`
- Winner? — e.g. `Yes — beat E1-A (5.7) by 2.6`
- Why — e.g. `One-shot kept losing the itemized-receipt structure`
- Taught to agent — `✅ Jul 24 · verified fresh-chat ✅ · regression ✅`
