# Phase 2 Static Briefing Workflow

Use this workflow after the Audience Conversion Report is source-truthed and
before making static ads. The goal is to prevent agents from choosing creative
formats too early.

Phase 2 is not "generate static concepts". Phase 2 is:

1. Synthesize the source-backed audience research.
2. Choose one avatar.
3. Choose one mass desire or core focus.
4. Pull and analyze direct competitor plus adjacent-niche ads.
5. Build the 70 / 20 / 10 source mix.
6. Build an angle bank by awareness level.
7. Ask the operator to choose the visual format or template.
8. Generate format-specific benefits, negatives, and headlines.
9. Run the Static Mistake Filter.
10. Get approval before production or paid generation.

## Create The Workbook

Use the local/free scaffold command:

```text
adc audience-conversion phase2-static --client <slug> --product <product-id>
```

Optional:

```text
adc audience-conversion phase2-static \
  --client secondkind-v2 \
  --product gut-balance \
  --avatar "Done-Everything-Right Dana" \
  --mass-desire "finally feel consistent again"
```

This writes:

```text
clients/<slug>/research/audience-conversion/phase-2-static-briefing-workbook.md
```

The command does not scrape ads, call LLMs, or generate images. It creates the
required operator-facing workbook.

## Gate 1: Audience Research Synthesis

Before concepts, summarize:

- psychographics
- problems and desires
- behaviors and moments
- objections and misconceptions
- exact customer terminology

Use source-backed language. Add notes like:

```text
We are using "still bloated after doing everything right" because customers
described doing probiotics, diet changes, and gut routines while still feeling
bloated in reviews/social comments.
```

Do not turn vivid customer wording into generic strategy language.

## Gate 2: Pick One Avatar

Pick one avatar before concepting. If two avatars are attractive, make two
separate batches.

The selected avatar should include:

- core desire
- core pain
- core objection
- daily-life context
- language style
- source support
- angles to avoid

## Gate 3: Pick One Mass Desire Or Core Focus

Before building the angle bank, ask the operator to choose one:

- mass desire
- core objection
- misconception
- failed solution
- behavior/moment

Do not build a format-specific static before this choice.

## Gate 4: Pull And Analyze Direct + Adjacent Ads

Use Foreplay, Apify, Meta/TikTok ad sources, Pinterest mechanics, or approved
ad-library cards.

Target:

- 10 direct competitor/category ideas
- 10 adjacent niche ideas
- 3-5 internal winners when available

Quote cost and get approval before paid pulls.

## Gate 5: Ad Analysis And Opportunity Extraction

Do not only summarize pulled ads. For each ad, capture:

- mechanic
- what works
- what they did wrong
- missed opportunity
- how we can emulate it
- awareness level
- evidence level

This is how direct competitor and adjacent niche references become usable
concept material.

## Gate 6: 70 / 20 / 10 Source Mix

Label every idea:

- 70% proven outside references
- 20% internal winners
- 10% new swings

Also label source type:

- `direct_competitor`
- `adjacent_niche`
- `internal_winner`
- `new_swing`
- `cross_industry_swipe`

And evidence level:

- `high`
- `medium`
- `low`

## Gate 7: Angle Bank By Awareness Level

Build angles after choosing the mass desire/core focus.

Organize by:

- unaware
- problem-aware
- solution-aware
- product-aware
- most-aware

Awareness mapping:

- **Most aware:** urgency, proof, CTA, offer, validation.
- **Product aware:** differentiation, social proof, why this product.
- **Solution aware:** comparison, mechanism, credibility, category contrast.
- **Problem aware:** empathy, agitation, daily-life payoff.
- **Unaware:** curiosity, story, surprising moment, identity tension.

Headlines should be clear before clever. Prefer 6-10 words when possible.
Use review/comment language and explain why each headline works.

### Verbatim-First Copy Rule

When raw quotes or exact phrases exist, start from those words before writing
ad copy. The strongest static copy should often feel like the customer said it
first and the ad simply sharpened it.

For every important hook, benefit, negative/comparison bullet, objection, or
first-line copy option, capture:

- raw quote or exact phrase
- source type: review, Amazon, TikTok, Reddit/GigaBrain, competitor review,
  own review, YouTube, Instagram, etc.
- lightly edited ad line
- what changed and why

Do not replace vivid source language with generic marketing language. If the
source says "I do everything right and still feel bloated," do not flatten it
to "supports digestive comfort" unless the format specifically needs a
mechanism/proof line.

## Gate 8: Operator Chooses Visual Format

Stop and ask for the visual format/template:

- us vs them
- receipt comparison
- apology note
- calendar screenshot
- testimonial/story overlay
- comparison grid
- TikTok pill stack
- IG Story square box
- organic caption
- founder note

If the operator has not chosen or approved a format, do not produce final
format-specific copy.

If the operator chooses to copy/emulate a specific ad, use the default simple
emulation route from `docs/creative-production-system.md`: one natural-language
Higgsfield pass with the reference ad and product image, small surface changes
so it is not a clone, then Canva Magic Text for editable copy only. Do not
switch to JSON, multi-pass generation, or Magic Layers unless the operator asks
for a test or the first pass fails. The prompt must also include the generic
product-integration instruction: the product reference controls identity and
label fidelity, but Higgsfield should match the scene's lighting, shadows,
perspective, color temperature, and depth of field while removing halos,
cutout edges, pasted-on looks, and source-image artifacts.

If the reference is UGC, selfie, model-led, hand-held, or creator-style, include
the imperfect phone-photo block as well: lower clarity/sharpness, reduce
micro-contrast, soften fine detail, lower contrast/saturation when needed, add
subtle dirty-lens haze, preserve realistic skin texture, and avoid crisp studio
edges or a clean AI render. Keep it realistic and usable, not blurry.

If the reference contains a recognizable person, do not merely change hair or
clothing. Add the model replacement block: replace the original person with a
different believable creator, preserve the source mechanics only (pose, crop,
camera height, hand/product placement, lighting direction, selfie/product-in-hand
composition), and change identity cues such as face structure, hair, wardrobe,
accessories, grooming/makeup, and small environment details. If a separate
person/model reference is available, use it to control the new creator's look
while the Foreplay ad controls pose and layout.

If the operator provides a large Foreplay library, do not assign final copy
before seeing the emulated visual containers. Use this branch:

```text
Foreplay Library -> Simple HF Emulation -> Canva Magic Text -> Ad Card ->
Angle Fit -> Copy Set -> Approval -> Finalize
```

Each post-emulation ad card must document:

- scene / visual context
- ad mechanic
- persuasion mechanism
- product role
- existing text zones
- approximate text capacity
- awareness level fit
- best angles this format can carry
- bad angles for this format
- exact VOC phrases that can fit
- Canva edit notes
- 1:1 crop-safe text notes
- Static Mistake Filter risks

Use the ad card to decide which angle belongs on the visual. If the chosen
angle needs more text than the layout can carry, choose a different angle or a
different emulated ad instead of forcing the copy.

## Gate 9: Format-Specific Copy Set

After the visual format is chosen, write:

- benefits to list
- negatives or comparison bullets to list
- one set for each relevant awareness level
- five headline options
- source-language notes
- proof needed

For comparison formats like `us vs them`, benefits and negatives are the core
copy. For story or UGC formats, use moments and exact terminology instead.

Add a quote-to-copy translation table before finalizing copy:

| Raw customer line | Source | Ad-ready line | Use case | Keep / change note |
|---|---|---|---|---|
|  |  |  | headline / bullet / objection / CTA |  |

## Gate 10: Static Mistake Filter

Before production, the concept must pass:

- one-second readability
- center 1:1 crop safety
- moves the sale forward
- not generic
- benefit depth beyond level one when supported
- research before cleverness
- authenticity match

If it fails, fix the concept before spending money or generating images.

## Approval Rule

Production starts only after approval of:

- selected avatar
- selected mass desire/core focus
- source mix/references
- angle bank
- selected visual format/template
- template-specific benefits, negatives, and headlines
- Static Mistake Filter pass

## Manual Prompt For Slack Agents

Use this when starting a Phase 2 static batch:

```text
Start Phase 2 static briefing for this client. Do not generate ads yet.

Use the latest Audience Conversion Report and source-truth check. Create or
fill the Phase 2 static workbook.

First synthesize psychographics, problems/desires, behaviors/moments,
objections, and exact customer terminology. Then ask me to choose the avatar
and mass desire before concepting.

After that, pull/analyze direct competitor and adjacent niche ads, produce 10
competitor ideas and 10 adjacent niche ideas, label the 70/20/10 source mix,
build an angle bank by awareness level, and ask me which visual format/template
to use.

Only after I choose the format should you generate benefits, negatives, and
five headline options for that format. Do not make the ads until I approve.
```
