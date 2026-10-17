# Change a person or setting in an existing video

Use this for “same table movement, different kitchen” or “change the actor.”
It extends `video-reference` with Genjutsu `hf_mult_replace_object`. Product
replacement remains in the existing reference-remake workflow. Alex uses the
shared `pipeline_ops.py` commands plus his own authorized Higgsfield connection;
NetBird does not share provider sessions. No new keys or dependencies are needed.

## Scene and brief

Inspect the actual video and client context. Identify what changes, what stays,
and the exact time range. A short scene is useful for a requested test; do not
silently shorten a whole-ad request. A prompt is not a pixel mask. Use a supplied
authorized actor reference or describe a fictional adult.

```powershell
adc video-reference --client expand-furniture excerpt --source video-inputs/ad.mp4 --start 0 --end 3 --reason "Approved opening-scene kitchen test"
```

This saves the original snapshot/hash, range, FFmpeg command, inspected clip and
reference frames. It pads the ending with a still to at least four whole seconds,
maximum 30 seconds. Review/select `reference.png`; the first-frame default is
only an option. Whole 4–30 second videos can use `inspect` directly when their
duration matches the request. Use `excerpt` for fractional durations.

Write the timeline analysis from `video-reference-remakes.md`, bound to the
prepared clip's hash/duration including the hold, and an element-edit brief:

```json
{
  "product": "junior-giant-table",
  "product_truth": "White extending table; preserve rails, panels, legs and stools",
  "purpose": "Change the actor in the approved kitchen",
  "change": "person",
  "direction": "Different fictional adult woman, auburn ponytail, blue blouse",
  "preserve": "Wood kitchen, table geometry, hand contact, movement and cuts",
  "reference_role": "preservation",
  "text_policy": "preserve",
  "duration": 4,
  "resolution": "720p",
  "billing": "credits"
}
```

`change` accepts `person`, `setting`, or `person_and_setting`. `reference_role`
is `preservation` for unchanged room/product authority, or `replacement` for a
supplied target actor/room. Do not accidentally use the old actor as the new
identity. `text_policy` preserves or removes existing overlays; it never
authorizes new offers. Honor explicit operator instructions about sale text.
`billing` is credits or free; free requires explicit choice and current provider
eligibility at 480p/720p, with no automatic fallback to credits.

```powershell
adc video-reference --client expand-furniture prepare-edit --reference video-remakes/SOURCE_RUN --analysis video-inputs/analysis.json --brief video-inputs/edit.json --product-image video-remakes/SOURCE_RUN/reference.png --parent creative-recipes/PARENT_VERSION/recipe.json
```

For a follow-up edit use the previous approved result as source and its recipe
as parent. Omit parent only when no saved recipe exists. This preserves a changed
kitchen when subsequently changing the person. The historical `product_image`
option holds the labeled preservation/replacement image for this route.

## Approval and generation

Upload the exact packet image and clip, verify hashes, then quote `packet.params`
with both image and video roles. Save a sanitized quote with params, credits,
quoted_at and media_bindings under `video-inputs/`, as in the remake workflow.
Backend media aliases are normalized at approval. The Expand test's 28-credit
quote is historical; verify current pricing every time.

Use `approve`, `claim`, `receipt`, `finish`. The packet pins model, prompt, billing,
runtime, resolution and assets. Free requests require a real zero-credit quote
and explicit free approval; never relabel a paid quote as zero. Existing explicit
authorization for this exact operation/cost is sufficient. Local transport
steps do not require repeated confirmation. Every retry must be covered by
actual authorization. Reconcile timeouts instead of blindly resubmitting.

Shared approval uses `cost_unit: credits`, `estimated_cost` equal to
`options.credits`, and nonempty `cost_basis`, including for free requests. The
service supplies the authenticated operator and verifies approval text. The host
does not submit provider jobs.

## Review and full-ad assembly

Review motion, actor consistency, room, mechanism, hands, text and runtime.
State which checks happened: sampled frames cannot establish continuous motion
or lip sync. Finish saves raw output with actual QA, including defects.

```powershell
adc video-reference --client expand-furniture assemble --run video-remakes/COMPLETED_EDIT_RUN --source video-inputs/ad.mp4 --qa "Actual findings and remaining limitations"
```

Assembly verifies the original source hash and completed recipe, aligns small
provider runtime differences (maximum 0.3 seconds), removes the ending hold and
replaces only the selected range. Remaining footage and source audio are retained;
audio is re-encoded as AAC when present. Output uses generated dimensions and
30 fps. It creates a preview child recipe with command, hashes and QA. Raw output
and originals remain saved. The same run cannot be assembled twice; reconcile
interruptions rather than removing locks.

The shared service registers finish/assemble recipes and ancestry in Postgres.
Verify `registry_verified` and the version ID. Media remain in private host
bundles; ClickHouse is not the media archive. Saving is not launch approval.

Recorded Expand examples: kitchen raw `6c2eff8b-b02f-46f4-92e9-5791fd5bb89a`,
kitchen preview `a030aedd-09e2-4f0b-bc63-007cdfeb2ff1`, new-person raw
`bfde620b-c1d0-4c22-a4bd-a4b1353c7428`, new-person preview
`783b17ae-a7b9-41a9-8b6e-1590f237db5c`. These are client-specific retrieval
examples from host-assisted tests before these commands existed; only their
opening three seconds changed. Do not attribute those records retroactively to
the new implementation or use them as default inputs for another client.
