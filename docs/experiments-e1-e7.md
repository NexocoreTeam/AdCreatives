# Testing Engine — E1–E7 Experiment Protocols

Companion to [devin-7-week-plan.md](devin-7-week-plan.md). Each experiment
here is written so it can be executed by checklist — no expert judgment
required beyond "does the output honor the card?"

Two standing constraints govern every experiment:

- **Higgsfield gets max 2 inputs per generation.** Anything more complex
  becomes a chain of simple steps.
- **AI generates pixels; Python/PIL composes layouts and text** (see
  `.claude/skills/higgsfield-ad-production/SKILL.md`). Headlines, CTAs,
  grids, and brand marks are the PIL pass — never graded against the AI
  generation, and never blamed on it.

## The shared method (applies to every E)

**Card-fidelity rubric.** Score every output 0–2 on each dimension
(0 = lost, 1 = degraded, 2 = preserved), out of 10:

- Mechanic preserved — the persuasion move the card named still works
- Scan path — the eye travels in the card's order
- Product role — hero/prop/reveal/absent as the card specified
- Proof element — present and still believable
- QA clean — no halos, label damage, artifacts, broken hands/text

Experiment-specific dimensions get added per E below. Winner = higher
average across trials. Tie-break: fewer steps wins; still tied → cheaper
wins.

**Trial hygiene.**

- Change one variable at a time. Same product asset, same brand card, same
  settings across arms — only the arm differs.
- Minimum 2 trials per arm; run a 3rd when the first two disagree.
- `enhance_prompt: false` always (auto-enhance rewrites prompts and makes
  results unattributable — documented in the Higgsfield skill).
- Log every generation link the moment it exists, not at end of day.

**The log row (experiment tab).** One row per trial:
`E# | card_id | arm | step count | generation links | rubric scores | winner? | note`

**The standard test set (S1–S4).** As experiments complete, freeze their
best task as a standard regression task. After E1: S1 = comparison-format
remake, S2 = callout-format remake. After E2/E3: S3 = person-in-frame ad.
After E4: S4 = brand-vibe task on the second brand. Every teach-the-agent
loop re-runs S1–S4 to catch rules that break old wins. Keep the exact
inputs (card, assets, prompt) pinned in the experiment tab so reruns are
identical.

**Every E ends the same way:** one-sentence rule → agent shows the exact
instruction change → fresh-chat verify → S1–S4 regression → log row.
(Full loop in the 7-week plan.)

---

## E1 — Remake chains (first, ~6–8 hrs)

**Question.** Remaking a reference ad with our product: is one generation
enough, or does a two-step chain (remake with product → restyle to brand)
beat it — and does the answer differ by ad format?

**Why first.** Every later experiment builds on the winning chain shape.

**Setup.**

- Pick 3 approved cards from the library spanning distinct formats — aim
  for one comparison-structure ad (e.g. Us vs. Them), one Feature Benefit
  Callout, one casual/native-style ad (e.g. Native Text Overlay).
- Product: SecondKind clean cutout. Brand card: secondkind-bold.
- Text overlays are PIL work — plan the generation to leave clean space
  per the card's scan path, and grade the pixels, not the headline.

**Arms (per card).**

- A — One-shot: single generation, 2 inputs (reference ad image + product
  cutout), prompt carries the brand styling.
- B — Two-step: step 1 remakes the ad's structure with our product
  (inputs: reference ad + product); step 2 restyles step-1's output to the
  brand (inputs: step-1 output + brand reference), structure untouched.

**Grade.** Shared rubric + one extra dimension: *structure fidelity* — put
the output beside the card's scan_path list and walk it element by
element.

**Decision rule.** Decide PER FORMAT. A split verdict ("one-shot wins for
callouts, chain wins for comparisons") is a finding, not a failure.

**Rule template.** "For [format] remakes: [one-shot with product ref |
step 1 remake with product, step 2 restyle]. Never [the loser]."

**Traps.**

- Bad output ≠ bad chain. Run the blame test first: is the card wrong
  (fix via `update AD-0XX` in its thread)? Is the prompt unfaithful to the
  card (ask the agent to show the prompt it sent)? Only then blame the
  step count.
- Label damage on the product → note it; that's the trigger to build the
  clean-cutout/approved-label asset folder (woven-through task).

---

## E6 — Prompt format (second, ~4–6 hrs)

**Question.** (a) Should the agent hand Higgsfield a structured JSON
prompt or a tight natural-language paragraph? (b) How many card fields fit
in one prompt before HF starts ignoring or blending them? The bet is 3–4 —
prove or correct it.

**Why second.** Every later experiment writes prompts; settle the format
before generating hundreds of images with the wrong one.

**Setup.**

- Part (a): 2 cards (one simple, one dense) × both arms × 2 trials, using
  E1's winning chain shape.
- Part (b): one dense card, natural-language arm only. Ladder the prompt:
  version with 2 card fields (mechanic + scan path), then 4 (+ product
  role, proof element), then 6 (+ cultural note, format nuance). Same
  everything else. Find where fidelity drops.

**Arms (part a).**

- A — Structured JSON (keys mirroring card fields).
- B — Tight paragraph (max ~5 sentences), written as if the reference
  images don't exist, then "the same product as reference 2" — the
  documented identity-prompt pattern.

**Grade.** Shared rubric + *instruction adherence*: count how many of the
prompt's card fields are visibly honored in the output.

**Decision rule.** One default format for all future prompts, and a hard
field cap N. Both go into the agent's instructions.

**Rule template.** "Prompts to HF are [format]; include at most [N] card
fields ([which ones]); everything else moves to step 2 or the PIL pass."

**Traps.** `enhance_prompt` off, or the ladder measures the enhancer, not
HF. Keep the ladder's added fields cumulative — don't swap fields between
rungs.

---

## E2 — Ads with people (~4–5 hrs, needs E1 + E6)

**Question.** When the ad needs a person: does the person swap ride along
in the restyle step, or does it need a dedicated third step?

**Setup.**

- 2 cards whose scan path or format involves a person (creator-style,
  testimonial-style static).
- Person reference: one fixed face photo used across all arms.
- Model per the Higgsfield skill: `nano_banana_pro` with the face
  reference passed FIRST in medias — it's the only documented
  identity-preserving route. (`soul_2` does style transfer: right vibe,
  wrong face.)

**Arms.**

- A — Two steps: person folded into the restyle step (inputs: step-1
  output + person ref; brand styling carried by the prompt).
- B — Three steps: remake → restyle → person swap as its own generation
  (inputs: step-2 output + person ref).

**Grade.** Shared rubric + *identity hold* (same recognizable person,
intact hands/eyes) + *placement* (person sits where the scan path wants
them).

**Decision rule.** Cheapest arm that holds identity AND fidelity. If A
works only when the step needs ≤2 inputs, that IS the rule — the max-2
constraint deciding for you.

**Rule template.** "Person ads: [fold the swap into restyle | add a third
swap step] — person reference always first in inputs, never soul_2 for a
specific face."

---

## E3 — Realistic people (~5–6 hrs, after E2)

**Ground truth first.** The repo already has a VALIDATED recipe for
people who don't read as AI — `.claude/skills/realistic-person-image/`
(registers A camera-roll / B editorial / C commercial-clean; Soul V2 as
the anti-polish base; `nano_banana_2` for reference-faithful upgrades;
never feed a Soul output back into Soul as reference — it swaps the
face). E3 does NOT re-litigate that. It extends it to in-feed ad
creative and tests the arm the skill doesn't cover: real creator photos
as references.

**Question.** For people in feed ads: Pinterest creator photo as
reference vs. HF Soul generating the person vs. both combined — which
looks most real AND most native to a feed?

**Arms.**

- A — Pinterest creator photo as reference (`nano_banana_pro` + photo).
- B — Soul-generated person (register-A recipe from the skill, no
  reference).
- C — Combined: Soul base for the anti-polish person, then `nano_banana_2`
  with the Pinterest photo for styling/scene only.

**Grade.** Shared rubric + *realism checklist* (hands, skin texture, eyes,
teeth, hair edges — 0–2 each) + *feed-native blind vote*: show each output
to a teammate for 3 seconds in a mock feed; "ad or post?" Real-feeling
loses the "ad" label.

**Decision rule.** A default people-recipe per register/use case, appended
to (not replacing) the existing skill's routing.

**Rule template.** "In-feed people: [recipe]. Pinterest sources creator
LOOKS and moods only — mechanics always come from Foreplay/Apify."

**Traps.** The two documented model bugs: Soul→Soul reference swaps faces;
nano-banana text-only output stays editorial-polished no matter the
prompt — don't fight it for the camera-roll register.

---

## E4 — Unique brand vibe (~4–5 hrs)

**Question.** Does our brand card exert enough force that the SAME
mechanic produces visibly different ads for two brands?

**Setup.**

- One mechanic-strong card. Run the full winning chain twice: once with
  the secondkind-bold brand card, once with magic-spoon (both live in
  `clients/` and contrast hard — clinical supplement vs. playful cereal).
  2 outputs per brand.
- Strip/blur logos and product labels before judging — the test is vibe,
  not reading the label.

**The blind test (pass condition).** Shuffle the 4 outputs. Two teammates
(strategist, Wasif) independently assign each output to a brand, told only
the two brand names. PASS = every output correctly attributed by both.
Anything less = the brand cards need more force.

**On failure.** Add concrete, generative slots to the weaker brand card —
palette hexes, texture words, lighting character, casting notes, set
dressing — then re-run the same card. Iterate until the blind test passes.

**Rule template.** "The restyle step must carry [the elements proven to
move the needle: palette, lighting, casting, texture] from the brand card
— adjectives alone do not transfer identity."

---

## E7 — HF's internal models (~3–4 hrs, deliberately scoped)

**Ground truth first.** The Higgsfield skill already has a model-selection
table (`nano_banana_pro` = identity + reliable in-image text;
`text2image_soul_v2` = anti-polish people; `soul_cast` = 16:9 one-offs;
skip Soul-ID training under 20 shots). E7 VERIFIES that table per job
category and catches anything new — it is not a from-scratch bake-off.

**Setup.** Three job categories: photoreal people / product statics /
stylized. Per category: the standard task (from S1–S4) run through the
table's recommended model + one challenger model, 2 trials each.

**Decision rule.** Confirm or overturn the default per category. If a
default changes, the skill table gets updated — via Mitchell (repo docs
change by PR, not by intern edit), and the agent's instruction updates in
the same teach loop.

**Scope guard.** This is the first experiment to shrink if time runs
short (after E5 drops entirely): one category, one challenger, done.

---

## E5 — No-reference generation (stretch, ~4 hrs, last)

**Question.** Can the system produce an acceptable ad for a whitespace
format — a card + copy, zero example image?

**Why it matters.** `library status` shows the coverage grid (awareness
stage × mechanic). Empty cells are formats nobody's ad library covers —
if card-only generation works, those gaps become a first-mover goldmine
instead of a blind spot.

**Setup.**

- Pick 2 empty cells from the coverage grid. For each, write the target
  as a card would describe it (mechanic, scan path, product role, proof).
- Agent composes the prompt purely from those fields (E6's winning format
  and field cap) + the brand card. 3 trials per cell. No reference image
  anywhere in the chain.

**Grade.** Shared rubric scored against the intended card + the full QA
gate.

**Decision rule.** If outputs average ≥7/10 on the rubric: whitespace
generation is real — the gap grid becomes a generation queue. If not:
record the failure modes and the minimum-reference rule ("needs the
nearest-neighbor card's image from the library as a structural
reference").

**Rule template.** "Whitespace formats: [card-only generation works for
(cases) | always pull the nearest library card as structural reference]."

---

## Budget reality check

E1 ~7h + E6 ~5h + E2 ~4.5h + E3 ~5.5h + E4 ~4.5h + E7 ~3.5h + E5 ~4h ≈
34 hrs of the ~42 available in weeks 3–7 — the remainder is the teach
loops, weekly check-ins, and continued card reviews. The plan's midpoint
rule stands: E5 drops first, then E7 shrinks; E1–E4 must finish properly.
