# Reference Emulation Workflow

Use this operating procedure when adapting an existing static ad to a client
product. It describes operator-guided production using existing tools; it does
not add automatic approval, selection, or resume behavior to the CLI.

Read [pipeline rules](pipeline-rules.md) and the
[Creative Production System](creative-production-system.md) first. Research-led
batches still use the [Phase 2 gates](phase-2-static-briefing-workflow.md).

## Source and evidence

- Source: Mitchell Thompson's [18 September 2026 walkthrough](https://vento.so/view/ebd429ad-b14b-41a7-949a-d39de4794cf6).
- Provenance: manual synthesis of the recording's transcript and representative
  visual checks, discussed and accepted by the operator on 18 September 2026.
- Demonstration: adapting a phone-product reference ad to IVI sunglasses.
- Evidence level: one observed production session, with several variables
  changing. Model preferences and explanations for failures are hypotheses,
  not controlled benchmark results or evidence of campaign performance.

| Moment | Observation | Production lesson |
|---|---|---|
| 00:21–01:45 | Product and logo sourced; product angle chosen for the scene | Prepare usable assets before prompting |
| 06:19–10:39 | Auto sizing, wording, extra tasks, and references revised | Set dimensions deliberately; diagnose the specific failure |
| 13:11–15:58 | Image roles and removal of the original product made explicit | Name inputs, replacement, preservation, and intended result |
| 17:17 | Preferred output selected; old references removed | Continue from the selected output, not the latest output by default |
| 18:27–20:35 | Logo/background edited; guessed background color was unconvincing | Add only needed assets and give concrete color direction |
| 21:49–23:44 | Copy tied to research and a concise product differentiator | Fit source-supported copy to the actual text space |
| 25:44–27:21 | Fuzziness identified and a cleanup edit proposed | Inspect sharpness and drift before accepting another pass |

## Where this fits

The four practical creative flows remain:

| Flow | Starting point | Role of this procedure |
|---|---|---|
| Research-led concepts | Avatar, desire, insight, angle, chosen format | Execute a reference-based concept after briefing approval |
| Reference emulation | Specific reference ad and client product | Primary operating procedure |
| Strategic reference translation | Borrowed mechanic and client aesthetic | Reuse edit discipline after deciding the new direction |
| Template or asset assembly | Proven template or clean visual plus copy | Use image edits for visual assets; finish exact layout/text separately |

Foreplay library batches are an emulation variant. Build the research idea pool
first, then candidate visuals and post-emulation ad cards, then fit and approve
final copy. A candidate with inherited reference text is a working intermediate,
not a finished client ad or evidence supporting the reference's claims.

## Choose the route

Start simple reference adaptations with one focused natural-language pass.
Use staged editing after a failed pass, for a fragile product/person requirement,
or when the operator chooses that route. Do not make every ad a fixed three-pass
job. Skip changes already satisfied by the selected image.

The staged route is:

```text
Prepared assets -> Product replacement -> Inspect/select
-> Branding/background -> Inspect/select -> Approved copy -> Final QA
```

Each pass has one main objective. A minor related change can share a pass when
both results can be checked. If a combined request fails, separate its tasks.
"One main objective" is a working heuristic, not proof that two changes or
three references always fail. Keep strategy analysis outside the edit prompt.

Existing production approval and paid-run cost confirmation still apply.
An already authorized run/budget does not need repeated permission requests;
visual selection is a separate decision about which result to use.

## Prepare the inputs

1. Save the reference ad and its source link. Identify the mechanic, scan path,
   lighting, product position, text zones, and identifiers to change.
2. Choose the exact product/variant from the brief. If unspecified, choose a
   suitable variant and record it. Prefer a view compatible with the target
   composition; do not use a front-on shot by habit.
3. Use a sufficiently detailed product source. Prefer the original asset;
   a clean screenshot is a fallback. Remove unrelated website chrome, not
   product detail. Keep the untouched original for identity comparisons.
4. Prepare the approved logo in the needed light/dark treatment at a usable
   size. Use a supported image export if the generation tool cannot take the
   source format. Do not rely on enlarging a tiny screenshot to recover detail.
5. Prepare a small pool of approved, source-supported copy options and brand
   palette guidance. Final wording must fit the selected layout.
6. Set the target aspect ratio and resolution explicitly. The demo used 3:4
   and 1K for iteration; those are session settings, not universal deliverables.
7. Record the actual model/route and settings. Website model availability does
   not imply that the repo's API engine supports the same model.

The broader reference packet can contain several research images. Each image
request should contain only the inputs needed for that particular edit.

## Product replacement

Assign image numbers to the actual attachment order. Name the visible object
being replaced rather than an ambiguous subcomponent. Describe the resulting
scene, including removal of the original product.

Example for a product-first attachment order in the website:

```text
Image 1 is the client sunglasses. Image 2 is the reference ad with a phone.
Replace the phone in Image 2 with the sunglasses from Image 1. Remove the phone
entirely. Preserve Image 2's composition, background gradient, and text layout
for this step. The only hero product should be the client sunglasses.

Match the scene's lighting, contact shadows, reflections, perspective, and color
temperature so the sunglasses look photographed there. Preserve their identity,
shape, proportions, color, and markings. Do not redesign the product or leave
halos, cutout edges, or a product-photo background.
```

For a one-pass visual adaptation, also name the specific brand-owned surface
changes. Preserve the mechanic while changing background color/material,
lighting warmth, supporting objects, or other identifying details. Unrelated
changes belong in a later pass.

**Acceptance check:** correct variant and geometry; original object removed;
believable scale, contact, light, and perspective; composition and text capacity
preserved; no label drift, white box, halo, or duplicated product. Compare the
output against the actual product source, not just the reference ad.

### Person and UGC references

Keep the existing model/source safeguards. When a client has an approved
model/product source, that source controls likeness, styling, and product; the
ad reference controls pose, crop, scene, and mechanic. Name the exact person
being replaced. Match lighting, shadows, contrast, perspective, and camera feel.
If only a flat lay exists but the scene needs a modeled product, first create
and approve an on-model product source through the client model pipeline.

Otherwise replace the recognizable reference creator, not just their clothing:

```text
Use a different creator, not the same model with styling changes. Keep the
same pose, crop, selfie angle, and product-in-hand mechanic, but change the
face, hair, wardrobe, accessories, and room details enough that it clearly reads
as a different person.
```

For UGC/selfie/hand-held references, retain the short ordinary-phone instruction:

```text
Make this look like a real low-effort iPhone selfie, not an AI image. Preserve
the pose and product-in-hand layout, but use a different person. The camera
should feel ordinary and slightly bad: soft front-camera focus, dirty lens haze,
flat indoor light, muted color, mild compression, no HDR, no beauty-camera
skin, no visible pore detail, no crisp hair strands, no glossy sharp edges.
Make it feel like a casual photo from someone's camera roll.
```

Adapt the identity sentence when using an approved client model. Do not apply
this realism downgrade to polished product statics, receipts, proof boards,
or screenshots. Keep products and ad text legible. Add detail only to address
a specific failure; do not expand the prompt into beauty/camera theory.

## Inspect, select, and promote

After each edit, inspect candidates against that stage's objective and the
unchanged requirements. Record a selected image or a rejection reason. Use an
existing operator selection; if the operator has not selected among candidates,
present the usable options and wait before spending on downstream edits.
Do routine QA first so the operator chooses among viable candidates.

Use the selected output as the next base. Remove old references from the active
request and add only the asset needed next, such as the logo. Keep originals
and rejected candidates on disk for traceability; removing a reference from a
request does not mean deleting source files. Do not promote the newest image
merely because a generation completed successfully.

If every candidate fails, fix the failed stage. Do not spend on copy or polish
to disguise a wrong product. Return to the last accepted base when a later pass
introduces drift. Save each attempt separately rather than overwriting it.

## Branding, background, and copy

Use the accepted product-in-scene image plus the logo when needed. Specify logo
treatment and placement. Give a concrete palette/gradient direction from the
brand and product instead of leaving a disliked color choice to another guess.
Logo and background may share a pass; split them if either fails. Confirm that
product identity, composition, and text space survived the changes.

Choose copy from research after inspecting the real text capacity. Prefer a
specific, verified reason to buy over generic quality language. Preserve the
selected avatar, awareness level, desire, and claim boundaries. Origin,
materials, durability, and mechanism ideas mentioned in a brainstorming session
are questions to verify, not facts to publish. Never shrink a necessary proof
qualification away to fit a headline; shorten accurately or change the layout.

Choose finishing deliberately:

- **Editable variants, exact typography, native UI, or team handoff:** Canva
  Magic Text/native elements or local rendering. Keep the accepted visual base
  intact. Protect the product before broader Magic Layers work.
- **Single flattened creative:** a focused image-model copy edit is an option
  when editability is not required. Supply exact approved wording, inspect
  spelling and line breaks, and recheck product/background fidelity afterward.
  If it fails, use deterministic text finishing.

For Foreplay batches, retain the required post-emulation ad card and copy
approval. The card records text capacity, angle fit, source language, crop
safety, and finish route. Local working cards are not library cards; write
`references/swipe/analyzed/` only through the approved library commands.

## Diagnose failures and finish

| Failure | Next action |
|---|---|
| Wrong dimensions | Set the intended ratio explicitly; check the actual output dimensions |
| Original product remains or replacement is ignored | Check attachment order; name the visible object, explicit replacement/removal, and intended result |
| Unrelated changes or mixed identities | Reduce the task and active inputs; retry from the last accepted base |
| Correct product but pasted appearance | Fix integration: light, perspective, scale, contact shadows/reflections |
| Wrong product geometry, label, or markings | Return to the real asset; use protected product/compositing when needed |
| Bad logo or background color | Improve logo source or specify the desired treatment/palette |
| Copy overflows or becomes unreadable | Shorten without losing meaning/proof, choose another layout, or use editable text |
| Sharpness drops after edits | Compare with the accepted parent; correct source/resolution or use controlled cleanup, then recheck fidelity |

Do not cycle models indefinitely without identifying the failure. Record the
changed variable on each retry and stay within the authorized budget. Extra
generative cleanup is optional; "make sharper" can redraw product details.

Final QA includes product and logo accuracy, removal of reference-brand names
and inherited claims, exact approved copy, no em-dashes in ad copy, intended
dimensions, mobile readability, crop safety, and the existing Static Mistake
Filter. Label unfinished references/placeholders as intermediates. State whether
the deliverable is flattened or editable. Visual acceptance is not a campaign
performance verdict.

## Record and use the current tools

Keep a compact manual run note with client working data under
`clients/<slug>/ad-runs/<run-id>/`, marked `provenance: manual`. Record source
links, product/variant, ordered input paths and roles, exact prompt, model/route,
settings, output paths, selected parent, rejection reasons, selection by whom,
copy/proof sources, finishing route, actual cost if known, and final QA status.
If cost is unknown, say so; do not invent a pipeline cost-log entry. Existing
automated generation/refinement logs remain the record of what those tools ran.

| Capability | Current behavior and use |
|---|---|
| Higgsfield website | Run individual edits, compare candidates, select the next input; record the model actually used |
| `adc edit` | One edit with explicit `--image`, `--prompt`, and `--output`; current engine is `hf-web` / `nano_banana_flash`. First image is the canvas, so adapt image-role wording to that order. Use unique output paths |
| `adc remix-refine` | Existing remix iteration/version logging; use `--from-image` to choose the accepted parent rather than the default latest version. Reference inputs differ by engine |
| `adc remix-images --staged` | Automatic product/text/optional person chain, with no visual approval pause. NB2 handles the first two stages; `hf-web` takes its single-pass route even if `--staged` is supplied |

Today, operators/agents enforce these checkpoints between separate edit calls.
Persisted stage status, candidate selection, selected-parent lineage, and
resume-from-approved-stage support are automation backlog items, not implemented
features of this documentation update. Use the
[test plan](static-ad-production-test-plan.md) to evaluate routes before encoding
new model defaults or a fixed chain.
