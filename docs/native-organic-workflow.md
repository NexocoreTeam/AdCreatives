# Native / Organic Static Ad Workflow

Use this branch of the existing production workflow when an ad should look
like an organic post: a casual photo with a platform caption, question sticker,
message thread, Notes card, or reminder. Keep the existing audience, angle,
source, approval, and product-fidelity gates. The format changes execution,
not the research standard.

## Choose The Treatment At Gate 8

For the iOS/Ella Canva board or a request for its exact Apple-organic look,
use [canva-native-ads.md](canva-native-ads.md) and the `canva-native-ads` skill.
That supplied reference takes precedence over the local component rows below.
The skill prepares editable drafts, obtains Canva's required preview approval,
and records actual production steps and exports for future variations.

If the operator already names a format or supplies a reference to reproduce,
record that choice; do not ask them to choose it again. If they only say
"make it organic," recommend the closest supported treatments for the angle
and get their format choice before final copy.

| Requested look | Production route | What controls the look |
|---|---|---|
| Casual photo with caption boxes or highlight pills | `adc ugc-ad --brief` using `text_layout` | Approved caption reference and client `ugc_voice`; this renderer uses brand styling |
| Exact TikTok per-line pills, square IG Story box, or white shadowed caption | Local overlay or Canva using the existing Text Overlay Presets in `creative-production-system.md` | Platform reference and measured caption preset; these are not named `adc native-ad` components |
| Instagram question sticker | `adc native-ad`, `native_ui.component: question_box` | Fixed native UI styling; brand question or real shared response |
| iMessage thread | `adc native-ad`, `native_ui.component: imessage` | Fixed native UI styling; real conversation with permission evidence |
| iOS Notes list/checklist/review roundup | `adc native-ad`, `native_ui.component: notes` | Fixed native UI styling; sourced copy and attributed reviews |
| iOS reminder pop-up | `adc native-ad`, `native_ui.component: reminder` | Fixed native UI styling; a short source-backed line or real product name |
| Exact Ella template or an unbuilt UI component | Single-page Canva template copy, when available | Keep the template's fonts and geometry; edit words and permitted image slots |

An IG Story caption box is different from an IG question sticker. A generic
caption/pill layout is not an exact platform preset: `adc ugc-ad` can fall back
to SecondKind styling when client settings are missing. Check the client
`ugc_voice` and preview before using it for another brand. Use the preset or
template route when exact platform fidelity is required.

DM/comment replies, the separate Q&A answer card, Copy/Select menu, and lock
screen are not implemented in `adc native-ad`. Do not substitute iMessage for
an Instagram DM or claim an unavailable component exists. Use an available
approved template or surface the missing component.

## Prepare Once, Reuse For Copy Variants

1. Record the selected format, visual reference, angle, and awareness level in
   the Phase 2 workbook. Keep a supplied reference as the styling authority.
2. Verify the actual words and their source. Brand-authored questions, notes,
   and reminders must be identified as brand-authored; they must not imply a
   customer's experience. Attribute real reviews. Keep the original source
   and permission evidence for conversations and shared responses. Competitor
   VOC can inform angles, but cannot become a claimed client conversation.
3. Select an approved clean photo with room for the element. If a new photo
   is needed, quote the cost and obtain approval before paid generation. Use
   the existing product/model reference rules and phone-camera treatment.
4. Generate only the photo: no captions, stickers, message bubbles, Notes
   cards, reminders, or added UI. Preserve real product/garment text. For a
   native reference, this overrides the general one-pass text/Magic Text route.
5. Put approved copy in the existing brief: `text_layout` for UGC boxes/pills,
   or `native_ui` for a supported app component. The workbook handoff records
   source, permission, base image, reference, route, sizes, and output location.
   A manually assembled brief must include `provenance: manual`; it is not an
   `adc brief` output. Keep `source_insight`/`hook_source` truthful as well.
6. Render after production approval. Reuse the clean base for copy changes.
   Use a separate output folder or filename for each concept/variant so a
   new render does not overwrite a previous candidate.
7. Inspect each exported size against the reference at phone size. Keep the
   source brief and metadata with the asset; record QA and approval in the
   workbook. A successful render does not mean the ad is approved to ship.

### Existing Commands

Run from the checkout containing PR #28 or later. Paths below are placeholders
for approved assets/briefs, not new research or production output.

```text
adc audience-conversion phase2-static --client <slug> --product <product-id>
adc native-ad --brief clients/<slug>/briefs/<brief>.yaml -o ai-ads/<slug>/native/<variant>
adc ugc-ad --base <clean.png> --brief clients/<slug>/briefs/<brief>.yaml --brand <slug> -o ai-ads/<slug>/ugc/<variant>.png
```

`native-ad` renders 4x5 and 9x16 by default; `--size` can select 1x1 or override
the brief's sizes. `ugc-ad` keeps the base image dimensions. Prepare the base
for each desired crop rather than assuming the same text placement fits all.
Native component fields and copy-flag examples are in
[native-ui-components.md](native-ui-components.md).

These are agent/operator routing instructions. `adc generate` and `adc prompts`
do not automatically dispatch a `native_ui` brief to the local renderer; call
`adc native-ad` explicitly. The Phase 2 command scaffolds a workbook, not a
finished brief. Merge decisions back into an existing workbook by hand instead
of using `--force` to erase research or approvals.

## Native / Organic QA

- Compare font, shape, spacing, colours, padding, emoji, and line breaks to
  the selected platform reference/preset. Keep app UI free of brand styling.
- Confirm attribution, exact customer wording where quoted, and permission
  evidence. A `content_source` string is a record, not verification of consent.
- Keep one clear thought in the element. Shorten copy rather than shrinking
  it until it is unreadable. No em-dashes in ad copy.
- Check the product, face, and core hook remain visible in every output. For
  4x5/9x16, inspect the center square; if it fails, reposition in the brief or
  supply a separate feed-safe version and label the other Story/Reels-only.
  Default component placement does not guarantee crop safety.
- Retain `.meta.yaml` for native renders. Confirm it exists and records the
  content source. PNGs are flattened; keep the clean base and brief for local
  edits, or use the optional Canva template route for editable handoff.

For a new request, the operator can simply say: "Use our native/organic
workflow for [client/product], with [caption or element/reference]." Continue
from existing approved strategy and assets; ask only for missing choices,
source evidence, or required production approval.
