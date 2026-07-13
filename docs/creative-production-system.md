# Creative Production System

This document captures the current ad-making workflow used by the Creative
Strategist agent. It is for agents working in this repo who need to understand
how we actually make, remix, finish, and QA ads after strategy briefs exist.

Read this alongside `AGENTS.md`, `docs/pipeline-rules.md`, and any relevant
client files under `clients/<slug>/`. For controlled one-pass vs multi-pass,
JSON vs natural language, model-route, product-locking, or text-overlay tests,
also read `docs/static-ad-production-test-plan.md`.

For research-led Phase 2 static batches, read
`docs/phase-2-static-briefing-workflow.md` before selecting formats or
templates. Phase 2 must choose the avatar and mass desire, analyze competitor
and adjacent ads, build the angle bank, and ask the operator for the visual
format before writing format-specific copy.

## Purpose

The production system is not "prompt once and use the result." The current
workflow is:

1. Pull strong references.
2. Decide what each reference controls.
3. Choose the production route.
4. Generate or build a clean base.
5. Finish text/product details deterministically.
6. QA visually before sending.
7. Put useful working versions into Canva when the team needs handoff or edits.

Use AI image tools for visual base, scene, lighting, composition, and aesthetic
translation. Use local rendering or Canva for exact text and product-label
fidelity.

## Reference Sources

Use several source types, each with a specific job.

### Foreplay

Use Foreplay for proven ad mechanics and platform-native examples:

- Brand discovery ads.
- Saved boards and swipefile ads.
- Competitor static formats.
- Hooks, scan paths, proof systems, and offer structures.

Example jobs:

- PetLab apology-note static = empathy letter mechanic.
- PetLab receipt comparison = consolidated value/receipt mechanic.
- Rheal product routine statics = organic wellness product-in-life mechanic.

### Apify

Use Apify for broader competitor ad scraping and category intelligence:

- Repeated hooks and formats.
- Competitor claims and offers.
- Platform-specific creative patterns.
- Saturated ideas and whitespace opportunities.

Treat Apify as category mapping, not a final creative source by itself.

### Pinterest

Use Pinterest for raw visual mechanics and aesthetic inspiration. Do not only
search for polished ads. Mine the first-page visual field for ordinary images
that can become ads.

Useful Pinterest outputs include:

- POV salad or food-in-hand scenes.
- Wellness routine screenshots.
- Product-on-counter scenes.
- Educational charts.
- Quote/sign/affirmation visuals.
- Typography, color, and composition cues.

Every Pinterest reference must become a concrete ad mechanic: hook, layout,
scene, product role, caption style, proof structure, or anti-example. Do not
use vague "vibe" boards.

### Brand And Product References

Use brand/product references for:

- Product truth and label fidelity.
- Packaging colors and visual cues.
- Approved claims and claim boundaries.
- Offer, price, and product mechanism.

For SecondKind, keep the postbiotic mechanism clear and avoid letting AI tools
redesign the Gut Balance jar.

## Reference Packet Rule

For any new ad idea, build a small reference packet before generation when the
visual direction is not obvious.

Use 3-7 references max for a single territory. Label each reference by:

- Source.
- Lane.
- What it controls.
- What not to copy.
- Why it fits the product/format.

Reference lanes:

- Format reference: layout, scan path, proof structure, CTA logic.
- Aesthetic reference: palette, texture, mood, typography personality.
- Platform reference: native execution, caption placement, polish level.
- Product/brand reference: product truth, colors, claims.
- Execution reference: typography, badges, callouts, receipt/chart details.
- Anti-example: what to avoid.

## Concept And Industry Research

Before making a batch of static ads, separate audience research from concept
research.

- Audience research answers who we are speaking to, what they care about, what
  they object to, what moments trigger the problem, and what exact language they
  use.
- Concept and industry research answers which ad mechanics, hooks, visual
  structures, and templates are already working in the market or adjacent
  markets.

Do not start static production from a blank brainstorm. Start from the Audience
Conversion Report, a selected persona/avatar, a selected mass desire or core
focus, and a concept source mix.

The correct order is:

1. Synthesize the research: psychographics, problems/desires, moments,
   objections, and exact customer terminology.
2. Ask the operator to pick or approve one avatar.
3. Ask the operator to pick or approve one mass desire, objection,
   misconception, failed solution, or behavior/moment.
4. Pull/analyze direct competitor and adjacent-niche ads.
5. Build the 70 / 20 / 10 source mix.
6. Build the angle bank by awareness level.
7. Ask the operator to choose the visual format/template.
8. Generate format-specific benefits, negatives, and headlines.
9. Run the Static Mistake Filter.
10. Get approval before production.

Use the local scaffold when the batch needs a working document:

```text
adc audience-conversion phase2-static --client <slug> --product <product-id>
```

### 70 / 20 / 10 Concept Source Mix

For performance-oriented static batches, use this default sourcing mix:

- **70% proven outside references:** direct competitors, category leaders,
  adjacent niches, Foreplay boards, Apify/Meta/TikTok ad scrape, Pinterest
  mechanics, and ad-library teardowns.
- **20% internal winners:** hooks, formats, templates, overlays, offers, and
  mechanics that have already worked for this client or across agency accounts.
- **10% new swings:** fresh hypotheses, new visual ideas, odd hooks, trend
  plays, or strategist intuition.

Label each concept by source:

- `direct_competitor`
- `adjacent_niche`
- `internal_winner`
- `new_swing`
- `cross_industry_swipe`

Also label the evidence level:

- `high`: performance/spend/traffic signal or known internal winner.
- `medium`: long-running active ad, repeated category pattern, strong Foreplay
  or ad-library signal.
- `low`: visually interesting or strategically plausible, but not proven.

### Adjacent Niche Mining

Do not only look at direct competitors. Adjacent niches often provide fresher
mechanics than the same product category.

Ask:

- What categories solve a similar desire?
- What categories sell to the same persona/avatar?
- What categories address the same objection or failed solution?
- What categories have better visual/copy mechanics than this niche?

Examples:

- Clear protein: protein bars, electrolyte drinks, protein gummies, low-calorie
  snacks, functional beverages, sports nutrition.
- Gut health/postbiotics: probiotics, prebiotics, greens powders, digestive
  enzymes, bloating teas, women's wellness supplements, functional beverages,
  GLP-1 support, healthy-girl routine content.
- Premium coffee: specialty coffee subscriptions, espresso gear, boutique
  chocolate, craft alcohol, luxury pantry goods, morning routine products.

Fast operating target:

- Pull 10 direct/category examples.
- Pull 10 adjacent niche examples.
- Pull 3-5 internal winners when available.
- Stop the research pass around one hour unless the category lacks usable
  references.

### Angle Bank Before Template Selection

Before selecting templates or asking for images, generate an angle bank from
the Audience Conversion Report.

Inputs:

- selected persona/avatar
- one mass desire or core objection
- behavior/moment triggers
- failed solutions
- exact customer terminology
- product USP and proof
- awareness level

Organize angles by awareness level:

- unaware
- problem-aware
- solution-aware
- product-aware
- most-aware

Each static concept should state:

- Which persona it speaks to.
- Which source-backed pain, desire, objection, misconception, moment, failed
  solution, or golden nugget it uses.
- Which awareness level it targets.
- Which reference/template/mechanic it uses.
- What copy must be changed per awareness level.

The agent should ask the operator to choose the mass desire or core focus before
building the bank. Do not assume this choice when several desires are plausible.

When ad examples have been pulled, analyze them for:

- what the ad did well
- what the ad did wrong
- the missed opportunity
- the transferable mechanic
- how we can emulate it without cloning surface details

For headings and hook lines, prefer clear 6-10 word options when possible. Rank
headline options by scroll-stopping power and relevance, and explain which
source language or insight supports each option.

Every angle bank should also include benefit-depth options. Do not stop at the
first functional benefit.

- Level 1: functional benefit, e.g. "more energy".
- Level 2: daily-life outcome, e.g. "no 2 PM crash".
- Level 3: emotional payoff, e.g. "feel in control of your routine again".
- Level 4: identity or social payoff, e.g. "show up as the person you used to
  be".
- Level 5: specific lived moment, e.g. "wear the dress that has been sitting in
  the closet" or "finish the gym session and still have energy after".

Prefer level 3-5 language for hooks and first-line copy when it is supported by
the Audience Conversion Report. Use level 1 only when the format is explicitly
mechanism, proof, or comparison led.

## Production Routes

### Exact Reference Emulation

Use when Mitch wants an ad to look close to a specific reference.

Rules:

- Use the actual reference image in Higgsfield when polish, product lighting,
  stage, gradient, or composition matter.
- Do not rebuild polished references from memory or local approximations.
- Use local rendering or Canva for exact copy cleanup after generation.
- Preserve the mechanic and polish, but translate competitor names/products
  into category or client-owned language.

Example: PetLab apology note and PetLab receipt comparison both improved
materially only after the actual PetLab reference was used in Higgsfield.

### Reference Translation

Use when the goal is to keep a winning mechanic but make it feel brand-owned.

Process:

1. Extract the skeleton: hook, layout, product role, proof structure, CTA,
   badges, reading order.
2. Decide what is borrowed vs brand-owned.
3. Choose an aesthetic territory.
4. Build/generate inside that territory.
5. QA that the final still preserves the winning mechanic.

Example territories:

- Premium product shoot.
- iPhone desk / real receipt POV.
- Clean wellness editorial.
- Founder note.
- Native creator explainer.
- Soft clinical proof board.

### Organic UGC / Platform-Native Static

Use when the ad should feel like a creator screenshot, not a designed static.

Rules:

- Start with a real visual reference that shows the source context.
- If the mechanic is "iPhone POV holding product," the hand/product framing is
  non-negotiable.
- If AI iterations make people/hands/products look fake, use a real Pinterest
  image base and lightly edit it instead.
- Add final text locally or in Canva; avoid baked-in generative text.

### Graphic / Screenshot Style

Use for calendar, receipt, text message, note, app, chart, or UI-native ads.

Rules:

- Build locally when UI/text precision matters.
- Make the chrome match the platform details: status bar, battery, time, date,
  spacing, native colors.
- Casual copy often matters more than perfect design polish.
- QA small UI realism details before sending.

### Proven Template Remix

Use when we already have a proven static format and need to adapt it quickly to
a product, persona, or angle.

This route is different from asking an image model to create a whole ad from
scratch. The template controls the structure; research controls the copy; AI
only helps with asset replacement or visual base work when needed.

Examples:

- us vs them
- receipt comparison
- apology note
- calendar screenshot
- testimonial/story overlay
- TikTok pill stack
- IG Story square text box
- founder note
- product comparison grid

Process:

1. Choose a proven template from the client or agency library.
2. Identify what the template controls: layout, scan path, proof structure,
   image slots, text hierarchy, badges, and product placement.
3. Identify what must change: product, copy, claims, avatar, offer, awareness
   level, brand colors, and unsupported competitor language.
4. Use the angle bank and selected visual format to determine the benefits,
   negatives, objections, proof, and headlines before editing the template.
5. Use HF/ChatGPT/Canva AI only for asset replacement or visual slots when
   needed, such as replacing a can with the client product or generating a
   secondary comparison object.
6. Use the angle bank to write awareness-specific template copy.
7. Finish in Canva/local so headlines, bullets, badges, and spacing can be
   tested without regenerating the image.

For each template, generate:

- five headline options
- first-line copy
- benefit bullets
- negative/comparison bullets where relevant
- objection handled
- proof needed
- one copy set per relevant awareness level

Hard rule: do not bake final exact copy into generated image pixels when the
goal is fast testing. Use editable Canva/local text for copy iteration.

### HF Base + Canva Cleanup

Use when Higgsfield gives the best scene/lighting/polish, but exact text or
product-label fidelity still needs control.

Rules:

- Higgsfield creates the base.
- Canva cleans text and product layers.
- Use Magic Grab on product first when labels matter.
- Use Magic Layers only after protecting the product layer.
- Rebuild final text/badges as editable Canva elements when the team needs
  future edits.

### Local Overlay Production

Use local rendering when exact native text treatment matters more than Canva
editability.

Current best use cases:

- TikTok pill captions.
- IG Story square text box.
- Organic caption with shadows.

Canva MCP is useful for storage, review, and broad cleanup, but does not
reliably expose all native text-background controls. Local rendering currently
gives better control over pill padding, radius, baseline alignment, emoji
rendering, and shadow balance.

## Text Overlay Presets

### TikTok Pill Style

Default specs:

- Font: Proxima Nova Semi Bold.
- Fallback: TikTok Sans SemiBold when Proxima is not available.
- Font size: 50.
- Box size / padding: 21.
- Corner radius: 15.
- Fill mode: per-line with radius 15.
- Alignment: left aligned by default.
- Emojis: allowed at the beginning of each point when they support native feel.

QA:

- Emoji and text must be vertically centered inside the pill.
- All pills in a stack should usually use the same fill color.
- Pill color must contrast with the exact placement area. Do not use green
  pills on green salad/shirt areas unless contrast is strong.
- Avoid odd staggered alignment unless the reference clearly uses it.
- For 9:16 assets, keep the main hook/pill stack inside the center 1:1 crop
  unless the ad is explicitly Story/Reels-only.

### IG Story Square Text Box

Default specs:

- Font: Palatino Linotype Bold.
- Font size: 40-50.
- Font color: black `#000000`.
- Background: white `#FFFFFF`.
- Box size / padding: 20.
- Corner radius: 0.
- Fill mode: all-lines.

QA:

- Balance line breaks so lines are roughly similar length.
- Avoid orphan lines with only one or two words.
- Reword or lengthen copy if needed to make the block feel intentionally
  typeset.
- Emojis are encouraged when they make the testimonial feel native, but render
  them in color and use them sparingly.
- Check baseline alignment so no word sits off-line.

### Organic Caption Style

Default specs:

- Font: Proxima-style semibold.
- Font size: 50-60.
- Color: white.
- Two-shadow system, tuned subtle.

Starting shadow settings:

- Tight shadow: low-opacity black, angle 135 degrees, short distance, light
  blur.
- Wide shadow: very low-opacity black, angle 135 degrees, larger distance and
  blur, just enough to support readability.

The wide shadow should read as a readability cushion, not a visible glow.

## Product Handling Rules

- Product images must be cut out or naturally integrated into the scene.
- No white product-photo box, mismatched rectangle, halo, glow, or pasted edge.
- Do not ask Higgsfield to "fix" or redraw product identity if label fidelity
  matters. It can change the label, cap, shape, or packaging.
- If Higgsfield generates a believable product-in-scene treatment and the label
  is close enough, preserve that integrated lighting/shadow/plinth contact.
- If the issue is only a bright rim or cap highlight, prefer local/Canva tonal
  correction.
- If exact product replacement is needed, do it as a compositing/Canva task and
  tune scale, shadow, warmth, perspective, and contact with the stage.

## Canva Handoff Rules

- Clarify whether a Canva design is a flattened PNG or editable native text.
- Flattened Canva imports are acceptable for review/storage, but not final
  editable handoff.
- For product/package ads, use Magic Grab on the product first.
- Keep the product layer separate and protected.
- Then run Magic Layers on the remaining image/background layer.
- Delete bad OCR layers, especially product-label OCR.
- Rebuild ad text, receipts, totals, badges, and proof rows as clean Canva
  text/shapes when future editing matters.
- Do text changes in Canva/editable layers. Do not blur-patch polished ads.

Known failure modes:

- Magic Layers can damage or duplicate label text if run on the whole product
  image.
- Local blur patches create visible bands, ghost text, footer smears, and
  texture mismatch.
- Canva MCP may move/resize elements but cannot reliably recreate native text
  background effects.

## 1:1 Feed-Crop Safety

For 9:16 and 4:5 creatives, the main hook/core text must remain visible and
understandable inside the center 1:1 crop.

Rules:

- Primary hook and core text stay inside the square feed crop.
- Secondary/footer text can sit outside the square.
- If text is intentionally outside the center square, label the asset
  Story/Reels-only or create a separate feed-safe version.
- Check this before sending any 9:16 preview.

## Static Mistake Filter

Use this before generation and again before sending. A static ad should be
rejected or rewritten if it fails these checks.

### One-Second Readability

The ad must be understandable while someone is half-scrolling.

Fail if:

- Main copy is tiny.
- White text sits on yellow, pale, busy, or low-contrast backgrounds.
- Decorative graphics sit behind key copy.
- Too many elements compete with the hook.
- The core message is not readable inside the center 1:1 crop.

### Move The Sale Forward

A static should not only announce an offer, sale, or generic claim. It should
make the viewer more ready to buy before they click.

The ad should do at least one:

- Clarify the mechanism.
- Handle a real objection.
- Dramatize a source-backed moment.
- Create urgency around a real desire.
- Explain why this product is different.
- Make the viewer feel understood.

If the ad only says "sale", "50% off", or "everyone loves this", rewrite it.

### Generic Claim Filter

If any competitor could say the same line, the line is not strong enough.

Rewrite generic claims with:

- proof
- specificity
- unique mechanism
- exact customer language
- category contrast
- concrete use case
- authority or earned credibility

Bad:

- "Everyone is going crazy for this."
- "Boost energy."
- "Supports immunity."
- "Feel better."

Better:

- "No longer crashing at 2 PM."
- "Postbiotic support that does not need live bacteria to survive digestion."
- "The routine that finally stayed consistent after probiotics did not."

### Benefit Depth

Hooks and first-line copy should usually go deeper than level-one benefits.

Ask:

- What does this benefit change in their day?
- What emotion does that create?
- What identity or social moment does it unlock?
- What exact lived scene would make the viewer say "that is me"?

Do not write "enhanced energy" if the real angle is "I stopped cancelling my
evening plans after work."

### Research Before Cleverness

Do not reward clever lines that are detached from source data. A witty headline
is weaker than a plain line pulled from a real objection, failed solution,
moment, or customer phrase.

Fail if the concept sounds like the copywriter trying to be clever instead of
the customer recognizing their own thought.

### Authenticity Match

Choose the visual polish level for the claim.

- Polished product statics fit proof, mechanism, comparison, receipts, charts,
  and premium product-stage formats.
- Organic UGC/native statics fit lived moments, routine claims, creator POV,
  skepticism, and testimonial-style angles.

Do not use a glossy template model for a claim that needs relatability or lived
messiness. Do not use a messy UGC scene for a claim that needs proof clarity.

## Pre-Send QA

Before showing Mitch or a client a preview, inspect the image for human-eye
flaws.

Check:

- Passes the Static Mistake Filter above.
- Text visible in the intended crop and, for 9:16/4:5, the center 1:1 crop.
- Text baseline centered inside pills/boxes.
- Consistent spacing between similar elements.
- Balanced line breaks and no orphan words.
- Color emoji rendered correctly if used.
- Product label is not damaged, doubled, blurry, or hallucinated.
- No white product halos or pasted product edges.
- No blur bands, patch rectangles, ghost text, or footer smears.
- Highlights are clean rectangles and do not collide with following text.
- Rows sit with their intended divider lines.
- The design still matches the reference mechanic.
- The ad feels like the intended platform/source context, not a PDF, deck slide,
  or AI demo.

Fix obvious issues before sending. Do not rely on Mitch to catch routine
spacing, alignment, emoji, product, or crop problems.

## Output Locations

- Generated ad images usually live under `ai-ads/<client>/images/`; this folder
  is gitignored.
- Client strategy and source data live under `clients/<slug>/`.
- Canva work should be stored in the client/month folder, e.g.
  `OpenClaw > SecondKind > July 2026`.
- Repo docs and reusable rules live under `docs/`.

## Current Tool Roles

- Foreplay: proven ad mechanics and brand/ad examples.
- Apify: competitor ad/category scraping and platform-specific source bridge.
- Pinterest: visual mechanics and aesthetic territories.
- Higgsfield: reference-based visual base, scene, lighting, product shoot, and
  aesthetic translation.
- Canva: Magic Grab, Magic Layers, cleanup, handoff, final editable polish.
- Local scripts/rendering: precise native text overlays and deterministic UI or
  graphic statics.

## Improvement Backlog

- Add reusable local overlay commands for TikTok pill, IG Story box, and organic
  caption presets.
- Add a feed-crop preview/checker for 9:16 and 4:5 images.
- Build clearer Canva handoff tooling that distinguishes flattened vs editable
  designs.
- Build a clean product asset library per client with cutout, no-shadow, and
  scene-ready variants.
- Improve reference-packet storage so every ad has sources and assigned roles.
- Improve Apify/Foreplay/Pinterest ingestion into client-specific creative
  research packets.
