# Static Ad Production Test Plan

This document defines the manual V1 testing workflow for static ad production.
Use it when the team wants to compare Higgsfield pass strategies, prompt
formats, model routes, product handling, or human/model reference sources before
encoding defaults into the repo.

The goal is not to make a few good ads. The goal is to learn which route should
become the default for each kind of static ad.

For normal copied/emulated statics, the current production default is already
simple: upload the reference ad and product image, use a short natural-language
one-pass prompt, make a few small visual changes so the output is not a direct
copy, then use Canva Magic Text to make only the ad copy editable. Use this test
plan when the operator explicitly wants to audit whether a more complex route is
better.

## Test Objective

Build a controlled testing system so Creative Strategist can answer:

1. When is one-pass Higgsfield enough?
2. When is two-pass better?
3. When does a three-step workflow help?
4. Does JSON prompting outperform natural language?
5. Which model/route works best by creative type?
6. Should humans/models come from Pinterest/source images, Higgsfield Soul, or
   both?
7. Is product best integrated by Higgsfield or composited later as a locked
   layer?
8. Which creative types should avoid Higgsfield for final output and use
   local/Canva deterministic builds instead?

## Benchmark Creative Types

Run tests across multiple creative types because each type fails differently.

### 1. Polished Product Static

Examples:

- PetLab receipt comparison.
- PetLab apology note.
- Premium product-on-stage static.

What this tests:

- Reference faithfulness.
- Gradient/background polish.
- Product-stage realism.
- Receipt/note realism.
- Product fidelity.
- Need for Canva cleanup.

Default hypothesis:

- Use actual reference image in Higgsfield.
- Let Higgsfield handle lighting, stage, background, and composition.
- Use Canva/local for final text, badges, and product-label cleanup.

### 2. UGC / Human POV Static

Examples:

- Salad POV.
- Hand holding product.
- Creator routine screenshot.

What this tests:

- Hand realism.
- iPhone/native camera feel.
- Human/model quality.
- Whether repeated edits make the image look AI-ish.
- Product-in-life integration.

Default hypothesis:

- Start with a real Pinterest/source reference for pose/composition.
- Use Higgsfield for light edits or base generation only when needed.
- Add native text overlays locally or in Canva.

### 3. Graphic / Native Screenshot Static

Examples:

- Calendar screenshot.
- Receipt.
- iPhone screenshot.
- Text-message thread.
- Chart.

What this tests:

- Exact UI detail.
- Status bar realism.
- Spacing and line breaks.
- Text accuracy.
- Native screenshot believability.

Default hypothesis:

- Use local deterministic render or Canva for final.
- Use Higgsfield only if a background/photo base is needed.

### 4. Product Scene / Lifestyle Static

Examples:

- Jar on counter.
- Bathroom/kitchen routine.
- Product beside food/drink.

What this tests:

- Scene lighting.
- Product integration.
- Product label fidelity.
- Halo/pasted look.
- Whether Higgsfield over-redesigns the product.

Default hypothesis:

- Use Higgsfield for scene and lighting.
- Protect or lock product when label fidelity matters.
- Finish final text outside Higgsfield.

## Manual Test Packet Workflow

For V1, do not build new code first. Creative Strategist should prepare a
manual test packet, then the operator/intern runs the variants in Higgsfield.

Ask Creative Strategist:

```text
We are running a manual Higgsfield static ad production test.

Use this reference ad and product to prepare a complete copy/paste test packet.

Goal: compare [test name].

Include:
1. Reference teardown.
2. Reference roles: what each reference controls and what not to copy.
3. Product/brand constraints.
4. Variant IDs.
5. Prompts for each variant.
6. Model instructions.
7. Hard negatives.
8. QA checklist.
9. Scorecard.

Do not generate yet. Make it copy/paste ready for Higgsfield.
```

Every output must be labeled with a variant ID before review.

Example variant IDs:

- `A_one_pass_natural_nb`
- `B_one_pass_json_nb`
- `C_two_pass_natural_nb`
- `D_two_pass_json_gpt`
- `E_locked_product_hybrid_nb`

## Reference Teardown

Before any test, create a production teardown.

Capture:

- Persuasion mechanic: why the ad works.
- Layout skeleton: headline/product/proof/CTA zones.
- Visual style: lighting, camera, background, colors, typography vibe.
- Product role: hero, hand-held, staged, on counter, in routine.
- Source context: iPhone POV, product shoot, receipt, calendar screenshot,
  note, chart, etc.
- What Higgsfield should create.
- What Canva/local should finish.
- What to preserve.
- What to change.
- What to improve from the reference.
- Hard negatives.
- Center 1:1 crop-safe text requirement.

The ad-library teardown explains why an ad works. This production teardown
explains how to recreate or translate it without breaking it.

## Test A: One Pass vs Two Passes vs Three Passes

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

## Test B: Prompt Format

Purpose: compare natural language, literal JSON, hybrid, and teardown-to-prompt
formats while keeping images/model/pass strategy constant.

Run these variants with the same reference, product, model, aspect ratio, and
pass strategy.

### B1. Natural-Language Prompt

Operator steps:

1. Use the same reference/product inputs as the control.
2. Paste a clear paragraph or bullet prompt.
3. Save as `B1_natural_[model]`.

Prompt should include:

- Task.
- What to preserve.
- What to change.
- Product constraints.
- Hard negatives.
- Output intent.

Score:

- Layout obedience.
- Reference faithfulness.
- Product fidelity.
- General aesthetic quality.

### B2. Literal JSON Prompt

Operator steps:

1. Use the same reference/product inputs as B1.
2. Paste a valid JSON-style prompt packet.
3. Save as `B2_json_[model]`.

JSON should include:

```json
{
  "mode": "exact_emulation",
  "reference_roles": {
    "format_reference": "controls layout and visual style",
    "product_reference": "controls product identity"
  },
  "preserve": [],
  "change": [],
  "hard_negatives": [],
  "output_intent": "visual base for Canva/local text cleanup"
}
```

Score:

- Does Higgsfield follow structured constraints better?
- Does it become too literal or confused?
- Are hard negatives followed better than natural language?

### B3. Hybrid Prompt

Operator steps:

1. Paste the structured packet first.
2. Add a short natural-language execution instruction after it.
3. Save as `B3_hybrid_[model]`.

Use this because it may give the model structure without sacrificing normal
prompt comprehension.

Score:

- Constraint following.
- Visual quality.
- Product fidelity.
- Cleanup effort.

### B4. Teardown-To-Prompt

Operator steps:

1. Create the production teardown separately.
2. Convert it into a concise execution prompt.
3. Do not paste the entire teardown unless needed.
4. Save as `B4_teardown_prompt_[model]`.

Score:

- Does the separate analysis improve output?
- Is the prompt cleaner than JSON?
- Does it avoid overloading Higgsfield?

Decision rule:

- Pick the prompt format that gives the best reference match with the lowest
  cleanup burden, not the one that looks most sophisticated.

## Test C: Model / Route Comparison

Purpose: choose the best model/route by creative type.

Models/routes to compare when available:

- HF Web / `nano_banana_flash`.
- Alternate Nano Banana route if available.
- GPT Image / ChatGPT image model if available.
- Higgsfield Soul for recurring person/model identity.
- fal as a baseline for older structured brief generation.

Operator steps:

1. Use the same reference/product inputs.
2. Use the same pass strategy.
3. Use the winning or current best prompt format.
4. Run one output per model/route.
5. Save as `C_[model-route]_[variant]`.

Score:

- Reference accuracy.
- Visual polish.
- Product fidelity.
- Human realism.
- Text artifact rate.
- Cost/time.
- Cleanup required.

Decision rule:

- Do not pick one global model for everything. Pick defaults by creative type.

Likely defaults to validate:

- Polished reference statics: HF Web / Nano Banana-style reference route.
- Native UI screenshots: local deterministic build.
- UGC human/hand: source-reference edit first; model route depends on hand
  realism.
- Generic brief-to-image: fal may remain a baseline path.

## Test D: Human / Model Source

Purpose: learn whether one-off human/hand/static UGC should use Pinterest,
Higgsfield Soul, both, or source-image editing.

### D1. Pinterest/Source Reference

Inputs:

- Real Pinterest/source image controlling pose, hand, camera feel, or POV.
- Product reference if product is present.

Operator steps:

1. Select one source reference that clearly shows the desired hand/person/POV.
2. Tell Higgsfield that the source reference controls pose and camera feel.
3. Generate or lightly edit.
4. Save as `D1_pinterest_source_[model]`.

Score:

- Hand realism.
- iPhone/native feel.
- Product integration.
- AI artifact level.

### D2. Higgsfield Soul

Inputs:

- Soul/model identity.
- Pose/composition reference if available.
- Product reference if product is present.

Operator steps:

1. Use Soul when identity consistency matters across multiple ads.
2. Keep prompt close to pose/reference.
3. Save as `D2_soul_[model]`.

Score:

- Identity consistency.
- Human realism.
- Pose obedience.
- Platform-native feel.

### D3. Combined Pinterest + Soul

Operator steps:

1. Use Pinterest/source reference for pose/framing.
2. Use Soul for identity.
3. Save as `D3_pinterest_soul_[model]`.

Score:

- Does combining references improve or confuse the output?
- Does the person still look native?

### D4. Real Source Edit

Operator steps:

1. Use a real source/base image.
2. Make minimal edits only.
3. Add text locally/Canva.
4. Save as `D4_source_edit_[model]`.

Use this when regeneration starts making people or hands look AI-ish.

Decision rule:

- For one-off UGC, prefer real source/Pinterest references or source edits.
- Use Soul when recurring identity is more important than one-off realism.

## Test E: Product Integrated vs Locked Product Layer

Purpose: decide whether product should be created inside the Higgsfield image or
protected/composited later.

### E1. Higgsfield-Integrated Product

Operator steps:

1. Provide reference ad and product image.
2. Ask Higgsfield to integrate product naturally into the scene.
3. Save as `E1_hf_integrated_product`.

Score:

- Lighting match.
- Product contact/shadow.
- Label accuracy.
- Product redesign risk.
- Halo/glow.

Use this when:

- Product realism inside scene is more important than exact label fidelity.
- The product is simple or can survive mild reinterpretation.

### E2. Locked Product Layer

Operator steps:

1. Generate scene/base without asking Higgsfield to redraw product details.
2. Composite the real product later in Canva/local.
3. Tune scale, shadow, warmth, and contact.
4. Save as `E2_locked_product_layer`.

Score:

- Label fidelity.
- Pasted look.
- Shadow/contact realism.
- Final believability.

Use this when:

- Product label must be exact.
- Higgsfield keeps changing packaging.
- Compliance/product identity matters more than perfect scene integration.

### E3. Higgsfield Product + Magic Grab Protection

Operator steps:

1. Use Higgsfield output if product is already integrated and mostly correct.
2. In Canva, Magic Grab the product first.
3. Protect product layer.
4. Magic Layers the rest for text edits.
5. Save as `E3_hf_product_magic_grab`.

Score:

- Does Magic Grab preserve label?
- Does the product layer stay clean?
- Does text cleanup avoid product-label damage?

Use this when:

- Higgsfield product looks integrated.
- Product is good enough to preserve, but text needs editing.

### E4. Scene-Only Base + Real Product

Operator steps:

1. Generate a clean scene/background with no product or placeholder product.
2. Add real product later.
3. Save as `E4_scene_only_real_product`.

Score:

- Does the final look pasted?
- How hard is lighting/shadow matching?
- Does product fidelity justify the extra work?

Decision rule:

- HF-integrated product often looks more photographed into the scene.
- Locked product preserves identity but can look pasted.
- If HF starts redesigning the product, stop regenerating and move to locked
  product or Magic Grab protection.

## Test F: UI / Screenshot Deterministic Build

Purpose: confirm when local/Canva beats Higgsfield for exact UI ads.

Creative types:

- Calendar.
- Receipt.
- iPhone screenshot.
- Text thread.
- Chart.

Operator steps:

1. Rebuild the UI locally or in Canva with exact components.
2. Compare against a Higgsfield attempt if useful.
3. QA status bar, time, battery, Wi-Fi, reception, header data, spacing, line
   breaks, native colors, and copy tone.
4. Save as `F_local_ui_build` and optional `F_hf_ui_attempt`.

Score:

- Native realism.
- Text accuracy.
- UI detail accuracy.
- Time to revise.
- Whether it still reads inside the center 1:1 crop.

Decision rule:

- If exact text/UI is the ad, use local/Canva deterministic build.
- Do not rely on Higgsfield for final UI details.

## Test G: Text Overlay Route

Purpose: decide whether final copy should be rendered locally or in Canva.

Overlay styles:

- TikTok pill text.
- IG Story square box.
- Organic caption shadow.

Operator steps:

1. Render local overlay using the approved preset.
2. Try Canva/native text only if editability is needed.
3. Compare visual quality and editability.
4. Save as `G_local_overlay` and `G_canva_overlay`.

Score:

- Padding/radius accuracy.
- Emoji rendering.
- Baseline alignment.
- Shadow quality.
- Line-break balance.
- 1:1 crop-safe text.
- Editability.

Decision rule:

- Use local overlay when visual precision matters.
- Use Canva when future team editing matters and native controls can reproduce
  the style cleanly.

## Required Artifacts

Every test variant should save:

```text
outputs/static-tests/<test-id>/<variant-id>/
  output.png
  prompt.txt
  plan.json
  references.json
  model.json
  scorecard.yaml
  notes.md
```

If running manually outside the repo, keep the same naming in a shared folder or
Canva project.

## Scorecard

Score each output 1-5:

- Reference faithfulness.
- Aesthetic quality.
- Product fidelity.
- Product integration.
- Human/hand realism if relevant.
- Text accuracy.
- Native/platform feel.
- Center 1:1 crop safety.
- Cleanup difficulty.
- Time/cost efficiency.
- Final shippability.

Tag failures:

- `prompt_miss`
- `reference_miss`
- `product_fidelity_miss`
- `product_integration_miss`
- `human_hand_miss`
- `text_ui_miss`
- `crop_safety_miss`
- `cleanup_workflow_miss`
- `model_limitation`

## Test Report Template

After running variants, summarize:

```markdown
# Static Test Report: <test id>

## Setup
- Client:
- Product:
- Creative type:
- Reference:
- Goal:

## Variants
| Variant | Pass Strategy | Prompt Format | Model | Product Strategy | Score | Notes |
|---|---|---|---|---|---|---|

## Winner
- Winning variant:
- Why it won:
- Cleanup needed:

## Failure Patterns
- 

## Default Rule Recommendation
- 

## Next Test
- 
```

## Code Implementation Later

Once manual tests identify winners, implement code support:

1. Add production modes:
   - `exact_emulation`
   - `reference_translation`
   - `ugc_native_static`
   - `graphic_screenshot`
   - `product_lifestyle_scene`
   - `local_overlay_only`
2. Add named execution strategies:
   - `one_pass_hf_reference`
   - `hf_base_then_locked_product`
   - `hf_scene_then_canva_text`
   - `local_deterministic_render`
   - `source_image_edit_then_overlay`
   - `magic_grab_then_magic_layers`
3. Add `adc static-plan` to output a plan without generating.
4. Add `adc static-test run` to execute multiple variants from a manifest.
5. Add benchmark YAML manifests.
6. Add scorecard artifacts.
7. Encode default routing rules by creative type.

Do not hard-code one pass or two pass globally. The strategy should be selected
by creative type, product fidelity risk, text accuracy needs, and human/model
risk.

