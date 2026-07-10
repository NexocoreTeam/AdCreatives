# Creative Production System

This document captures the current ad-making workflow used by the Creative
Strategist agent. It is for agents working in this repo who need to understand
how we actually make, remix, finish, and QA ads after strategy briefs exist.

Read this alongside `AGENTS.md`, `docs/pipeline-rules.md`, and any relevant
client files under `clients/<slug>/`.

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

## Pre-Send QA

Before showing Mitch or a client a preview, inspect the image for human-eye
flaws.

Check:

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
