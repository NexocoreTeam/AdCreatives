# Video finishing and research-based variants

Use after reference analysis or when refining an existing video. This is an
operator workflow, not a new CLI or an unattended generation endpoint. Follow
`video-reference-remakes.md`, `video-element-edits.md` and
`creative-feedback-loop.md` for their existing contracts and approvals.

## Start from the selected version

Read the client's `creative-preferences.md`, when present, and
`video-finishing/approval-history.json`. Resolve the selected recipe, output
role and file hash before editing. Newest file does not mean approved version.
Record approval separately for footage, voice, script, hook wording, hook style
and subtitles. A style approval does not finalize copy or authorize launch.
Use client preferences as defaults, not as instructions overriding today's request.

## Analyze the reference as an edit

Review the full available timeline. Alongside the existing analysis schema, keep
a shot-plan sidecar with source time range, shot purpose, action, framing (wide,
medium, close), approximate duration, audio/caption beat and adaptation decision.
Do not add unsupported fields to CLI payloads. Distinguish observed details from
inferred prompts. A transcript and translation are different artifacts; preserve
the source language and uncertainty when the wording matters.

List continuity state at each cut: actor, wardrobe, room, product geometry and
finish, prop location, and whether an action has already happened. Identify the
opening, setup, detail inserts and ending. Match useful pacing and sequence,
not merely the subject or room aesthetic. Do not copy unrelated claims.

## Repair only the affected shots

Map the user's criticism to exact ranges. Keep the approved footage and audio
outside those ranges unless another change is requested. Do not shorten a full
ad to conceal a defect. Record any runtime adaptation explicitly.

For repeated physical-action failures, propose a simpler action that preserves
the storytelling purpose: smoothing an already-fitted sheet instead of pulling
fabric around rails, for example. Do not silently substitute a different action
or prop destination. Before generation, specify framing, hand trajectory, object
contact, start/end state and what stays fixed. Use the product photo for geometry
and the selected video for actor/room continuity; neither is permission to copy
known defects. Respect the operator's selected provider and existing cost gates.

After generation inspect hands, limbs, contact, slat/edge thickness, colours,
product shape and actions across time. Check the adjoining shots too: props must
not vanish, earlier states must not reappear, and a finishing action should not
be followed by an earlier preparation step. Sampled frames establish only sampled
visual checks, not continuous-motion or lip-sync verification. Save raw output,
selected ranges and QA limitations, even for rejected takes. Reconcile an
uncertain submission instead of resubmitting it.

## Voice auditions before full variants

Use a short representative script excerpt containing both the opening and a
normal conversational sentence. Audition the selected stock voices before
generating complete scripts or muxing every voice into video. Record provider,
model/variant, exact voice ID (not only its display name), prompt, supported
delivery settings, raw output and any pitch-preserving speed adjustment.

Write for speech: contractions, connected thoughts, plausible emphasis and
uneven but readable sentence lengths. Avoid theatrical opening pauses or adding
filler everywhere to simulate spontaneity. Use only settings the provider
actually exposes; do not invent an organicness control. Compare the opening,
breaths, emphasis, product pronunciation and pacing. Change one delivery factor
at a time. A preference for one voice or speed belongs to that client/session.

Preserve a verified testimonial's meaning and distinguish adaptations from
verbatim quotes. Product material statements must be scoped to supported parts;
marketing source copy alone is not evidence for new medical or safety claims.

## Reusable subtitles and written hooks

Maintain separate editable copy and presentation settings. Reuse the clean
master instead of drawing new text over a previously captioned export.
Generate timestamps from the actual selected audio, account for any audio lead
or speed change, compare all words to the approved script and correct brand
spellings. Save SRT/ASS (or equivalent) and timing provenance. Do not reuse old
timings when changing the narration.

For centered square-crop compatibility, the square in a W x H portrait video is
`x=0..W, y=(H-W)/2..(H+W)/2`. At 1080 x 1920 this is y=420..1500.
Keep all glyphs, shadows and boxes inside with margins; check the actual center
crop and the vertical export. This is crop safety, not a guarantee against all
placement-specific app controls. Keep faces, product details and key actions
readable. If a crop cannot preserve the content, make a separate reviewed version.

An opening hook should be visible from frame one for its selected duration.
A five-second hook and a full-duration static caption are different choices.
For the stacked-box treatment, use a smaller uppercase label above a larger
benefit line, compact rounded rectangles, measured padding and optional inverted
brand/white colours. This is a caption treatment, not native app UI. Exact font,
copy, colours and timing are client-specific. Compare the supplied visual
reference's type hierarchy and geometry, not just its background shape.

## Script and angle variations

Lock an approved visual master first, then create a small hypothesis table:
variant ID, ICP/awareness, pain point or desire, source file and exact excerpt or
section, hook, script, claim evidence, expected response and review status.
Read `audience-conversion-report.md` for source-quality requirements. Do not
label an angle research-backed solely because an avatar file exists; mark
unsupported ideas as hypotheses and incomplete research as incomplete.

Change the script/hook for the selected angle while retaining approved footage,
voice and finish when appropriate. Check that the pictures still support the
new words. Measure generated narration before assembly; never silently cut
speech, add long frozen endings, or change pace to force an ill-fitting script.
New audio needs new subtitle timing. New paid attempts and launches retain their
existing approval requirements.

## Save decisions and reusable client settings

Keep `clients/<folder>/video-finishing/preset.json`, a short usage note and an
append-only `approval-history.json` containing dated decisions, actual user
evidence, affected component, recipe/output references, known limitations and
supersession relationships. Use `unknown` when the exact date/version is missing.
Do not rewrite immutable recipes or treat supersession as deletion permission.

Record each generated or assembled version with `adc creative record`, validate
it with `adc creative inspect`, and use the existing registry import/service
route. Preserve exact prompts, inputs, models, IDs, settings, command lines,
cost evidence, approval and final hashes. Postgres stores recipe metadata; media
remain in private host bundles. Do not promise employee access to an unmerged
skill, undeployed doc, private provider login or unexposed host command.
