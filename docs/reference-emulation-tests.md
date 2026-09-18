# Pass Strategy Tests for Reference Emulation

This is Test A of the [Static Ad Production Test Plan](static-ad-production-test-plan.md).
Read its controls, cost/approval rules, and scoring guidance before running.
The variants are manual test procedures, not new CLI modes.

The [reference-emulation procedure](reference-emulation-workflow.md) incorporates
the operator's 2026-09-18 walkthrough. That session motivates A4 below; it does
not establish that staged editing or a particular model always wins.

Purpose: determine how many production stages are best for each creative type.

### A1. One-Pass Higgsfield

Use when testing whether Higgsfield can handle the full visual base at once.
This is also the normal baseline for simple ad-copying/emulation jobs.

Inputs:

- Main reference ad.
- Product image.
- Full prompt.
- Brand/product constraints.

Operator steps:

1. Upload/select the reference ad.
2. Upload/select the product image.
3. Paste the one-pass prompt.
4. Select the target model/route.
5. Generate one output.
6. Save output as `A_one_pass_[prompt-format]_[model]`.

Prompt should tell Higgsfield:

- The reference controls layout, lighting, composition, and visual polish.
- The product reference controls product identity/category.
- Make small surface changes so the output is not a direct clone: background
  color/texture, wall or backsplash color, props, model hair/clothing, scenery,
  or supporting objects.
- Final text does not need to be perfect if text will be rebuilt later.
- Do not redesign the product label.

Keep constant:

- Same reference image.
- Same product image.
- Same format/aspect ratio.
- Same copy intent.

Score:

- Overall polish.
- Reference match.
- Product fidelity.
- Product integration.
- Halo/glow risk.
- Cleanup effort.

Use this if:

- Scene/product lighting needs to feel integrated.
- Reference polish is the main value.
- Product identity risk is acceptable or can be cleaned in Canva.
- The intended Canva handoff is Magic Text for copy-only layers, not Magic
  Layers over the whole image.

### A2. Two-Pass Workflow

Use when testing whether splitting the base from product/text improves control.

Pass 1 inputs:

- Reference ad.
- Prompt for scene, layout, lighting, background, or visual base.
- No final exact text requirement.
- Product may be absent or only lightly suggested depending on the test.

Pass 1 operator steps:

1. Upload/select the reference ad.
2. Paste the visual-base prompt.
3. Generate the base.
4. Save as `C_two_pass_base_[model]`.

Pass 2 inputs:

- Pass 1 base output.
- Product image or locked product layer.
- Prompt for product integration or final refinement.

Pass 2 operator steps:

1. Upload/select the base output.
2. Upload/select the product image if product integration is being tested.
3. Paste the product/final refinement prompt.
4. Generate or move to Canva/local depending on the variant.
5. Save as `C_two_pass_final_[model]`.

Variants to run:

- `hf_base_then_product`: Higgsfield creates base, then integrates product.
- `hf_base_then_locked_product`: base is created in Higgsfield, product is
  composited/protected later.
- `hf_base_then_canva_text`: base is created in Higgsfield, text is rebuilt in
  Canva/local.

Score:

- Product fidelity.
- Product pasted look.
- Scene lighting consistency.
- Cleanup difficulty.
- Final ad quality.

Use this if:

- Product label must be accurate.
- Higgsfield creates halos/glows.
- Final text must be exact.
- Product should be locked as its own layer.

### A3. Three-Step Workflow

Use when testing complex ads with both fragile scene and fragile person/product
requirements.

Steps:

1. Scene/style/base composition.
2. Product or human/model integration.
3. Canva/local text, badges, product protection, and QA cleanup.

Operator steps:

1. Run a base-scene prompt from the format/style reference.
2. Run a second step using product and/or model/hand reference.
3. Finish exact text, badges, and crop-safe copy locally or in Canva.
4. Save each stage.

Recommended variants:

- `three_step_scene_product_text`
- `three_step_scene_model_text`
- `three_step_scene_product_magic_grab_text`

Score:

- Does quality improve enough to justify the time?
- Does each pass add drift?
- Does the human/model become more AI-ish?
- Does product fidelity improve or degrade?
- Is cleanup easier or harder than one-pass?

Use this if:

- Human/model/hand is important.
- Product and person are both fragile.
- Scene needs one reference and model/pose needs another.

Risk:

- Every extra pass can introduce drift. If pass 2 makes the image more AI-ish,
  stop and switch to source-image editing or local/Canva cleanup.

### A4. Product-First Editing With Selection Between Stages

Test the walkthrough's route separately from A2's scene-first route and A3's
scene/person assembly. Start with a polished product reference where a different
object must be fully replaced.

1. Prepare the reference, compatible client product view, usable logo, explicit
   palette, target ratio/resolution, and approved copy.
2. Product pass: reference + product; define ordered input roles and explicit
   replacement/removal. Preserve the reference's scene and text zones.
3. Inspect the output. Record failures rather than carrying them forward.
   Select the accepted output and remove stale references from the next request.
4. Branding pass: accepted product output + logo if needed; apply the planned
   branding/background changes. Recheck product fidelity and select again.
5. Finish the same approved copy with the route fixed for this comparison.
   Evaluate image-model versus editable text separately, not simultaneously.
6. Save all candidates and selection decisions, including unsuccessful runs.

Before the test, define a maximum attempt count and spend per variant, the
stage acceptance checklist, and the candidate-selection rule. Apply the same
review criteria to both chains. Report acceptance rate, rejected attempts,
total paid requests, operator time, and cost per accepted final alongside
visual quality. If a stage exhausts its budget without an acceptable image,
record the run as failed; do not omit it from the comparison.

Compare three complete runs of A1 against three of A4 on each chosen reference.
Hold model, source assets, target dimensions, approved copy, finishing route,
and final brand direction constant. A1 requests product + branding together;
A4 separates those objectives. Include the same logo asset in A1 if logo
replacement is part of the comparison. Asset use follows the declared chain;
the chain is the independent variable. If comparing fixed-count generations instead of
an operator-reviewed workflow, declare that design separately and keep every
output. Never compare an uncurated one-shot sample with only the best of many
staged attempts without accounting for all attempts.

Record each stage's exact prompt, actual ordered inputs, output, selected
parent, model/settings, acceptance decision, and rejection reason. Compare
sharpness and product detail against the original product asset and accepted
parent at every stage. Score whether selection prevents downstream work on
bad bases and whether further edits introduce drift.

The extra passes are justified only if acceptable-output rate or quality
improves enough to justify the measured time, spend, and cleanup. Treat results
as specific to the tested format/task. Visual scores do not establish CTR,
CPA, ROAS, or a universal model ranking.
