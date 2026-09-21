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
- Operator follow-up on 18 September 2026: for references with a human model,
  perform the distinct-person edit last, after product, branding and copy are
  accepted. Preserve the rest of the creative and verify that it survived.
- Operator follow-up on 21 September 2026: preserve the reference model's level
  of attractiveness and aspirational casting appeal while changing identity.
  The first IVI model replacement needs refinement on this criterion.
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
-> Branding/background -> Inspect/select -> Approved copy
-> Final person replacement when needed -> Final QA
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

Otherwise replace the recognizable reference creator, not just their clothing.
For the operator's staged model-led route, do this in the final image-edit pass
described below. A one-pass adaptation can include it earlier. If a private
intermediate still contains the reference person, label it unfinished and do
not promote it as a completed client creative.

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

### Final person replacement

For the operator-selected staged route, finish product integration, select the
usable base, and accept branding and copy before this pass. Change the person
last, then inspect the complete result. This is an operator preference to test,
not evidence that late replacement always produces better images.

Use only the latest accepted creative as the edit canvas. Keep the original
Foreplay ad and product photographs as QA references on disk; do not reattach
the original ad as a likeness reference. Add another input only when a specific
product or approved-model fidelity problem requires it, and state its role.

Create a clearly different adult person through visible facial structure,
face shape, a modest natural complexion change, a different haircut, and a
different outfit. Change background details while retaining the scene's depth,
light direction and composition. Specify concrete changes after inspecting the
reference. A haircut or wardrobe change alone is not sufficient.

Treat casting appeal as a separate acceptance requirement. Before the edit,
describe what should carry over from the reference: comparable attractiveness,
expression, presence, grooming, styling and fit with the intended audience.
Choose the identity changes within that casting brief. A different face alone
does not establish that the replacement works for the ad.

Use the operator-selected reference as the visual benchmark. Attractiveness is
a subjective casting judgment, so record the operator's side-by-side decision
separately from identity difference and technical QA. Facial proportions, hair,
complexion and wardrobe can vary while meeting the same appeal requirement;
do not equate one specific feature or complexion with attractiveness. Preserve
natural skin texture, anatomy and the reference's photographic character.
An ordinary-phone UGC reference still needs its original level of relatability.

Height is conditional: change apparent stature only when a full-body or wide
view provides enough context to assess it. In a portrait or torso crop, omit
height and record it as not applicable; do not zoom out or invent unseen body
proportions to satisfy the instruction. Keep the pose and camera framing.

Prompt template, adapted to the actual person and scene:

```text
Edit the selected creative. Replace the featured model with a clearly different
adult person, not the same person with a new hairstyle. Change facial bone
structure and face shape, shift the complexion slightly and naturally, give
the person a different haircut and outfit, and change the background details.
Use the concrete appearance and background changes specified for this image.
Change apparent height only if the existing full-body view makes it visible;
otherwise leave height out and preserve the existing crop.

Maintain the reference's level of attractiveness and aspirational appeal with
the distinct new identity. Follow the casting brief for expression, presence,
grooming and styling. Keep the result naturally believable, with realistic
skin texture and anatomy, within the original photographic style.

Leave everything else exactly the same: the ad layout, camera angle, framing,
pose, expression, gaze, lighting direction, approved logo, exact copy, font,
line breaks, text positions, and crop-safe margins. Preserve the client's
sunglasses, including frame geometry, lens colour, material finish, bridge,
temple details and markings. Allow only the minimal contact/occlusion changes
needed to fit the unchanged sunglasses naturally to the new face. Do not
replace, enlarge, crop, restyle or redraw the product. Keep the reference's
photographic character, including ordinary-phone softness when appropriate.
No additional text, objects or people.
```

"Everything else" excludes only the declared person, outfit and background
changes; enumerate the protected elements so the instruction is not ambiguous.
The wording is a constraint to check, not a guarantee of pixel preservation.
Use masks/protected layers when supported. If the face change requires a
product redesign or breaks fit, reject it and return to the accepted parent.

Review the result beside both the source ad and selected parent. Check that the
person reads as different through several visible features, with natural anatomy,
and that the scene/wardrobe have changed. Separately check whether the new model
matches the reference's attractiveness, presence and styling for this creative.
Record operator acceptance or `needs-casting-refinement`; a technically sound
image can still fail this casting check. For eyewear, inspect bridge and nose
contact, temple-to-ear placement, hair occlusion, lens perspective and all product
markings. Recheck exact copy, logo, sharpness, dimensions and center-square safety.
Record each changed attribute, height applicability, preserved elements and any
drift. Do not infer identity verification or campaign performance from this check.

If the pass changes typography or product details, do not call it finished.
Return to the accepted base and use a narrower edit or protected-layer finishing
within the approved scope. Do not spend on an unapproved retry. The operator
selects the accepted final; no later generative pass is required by this route.

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
| Distinct person but weaker casting appeal | Revise the casting brief against the reference; protect accepted product, layout and scene; seek operator selection within an authorized retry budget |
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
