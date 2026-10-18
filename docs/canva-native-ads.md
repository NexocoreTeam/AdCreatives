# Canva native ad automation

For requests using the iOS/Ella collection or that exact Apple-organic look,
use editable Canva page copies. This route takes precedence over the local
renderer for that reference. The reference is
[Copy of IOS Collection | @ella_contentclub](https://www.canva.com/design/DAHXWe9cEqM/hY2GQBZJlwYV8QjuVoeyfA/edit),
design `DAHXWe9cEqM`, 128 pages as observed on 2026-10-08.

The reusable Codex skill is `canva-native-ads`, maintained in Nexocore-AgentOps
at `adapters/codex/skills/canva-native-ads/`. Install that folder in each
operator's Codex skills directory. Each operator needs their own connected
Canva access to the agency template and client assets; the skill carries no keys.
This is an agent-operated workflow with preview approval, not an unattended
Canva API job. It does not add a new `adc` rendering command.

## Operator request

For example: "Make a Saved by Grace ad using the iOS reminder component and
this approved photo/copy. Save its recipe." For a variation: "Use this recipe,
keep the reminder and copy, and change the model/setting." Reuse approved
inputs and ask only for missing choices, evidence, or required approvals.

## Execution

1. Resolve client/product, approved angle/copy, source evidence, clean photo,
   size and optional parent recipe. Existing strategy and paid-generation gates
   apply. Generate only photographic assets; never bake UI into AI output.
2. Inspect the current source page. Candidate pages: Notes 3/5, reminders
   5/7/22, selection menus 2/18/21, AirDrop 12/34, question sticker 33,
   incoming call 39. Confirm the treatment and dimensions before copying.
3. Copy the selected page into its own working design; preserve the library.
   Persist the copy ID immediately for resumability. Open an editing transaction
   and resolve current text/media elements. Do not guess IDs.
4. Replace approved photo slots and text while preserving the template's fonts,
   colours, shapes, spacing and emphasis. Keep copy within the original visual
   capacity. Real conversations require source and permission; brand copy
   must not pretend to be a customer testimonial.
5. Inspect and show the edited preview, check product/copy/crop safety, and
   obtain approval. The Canva connector explicitly requires preview approval
   before committing edits. Keep pending draft state in the private run record.
6. Commit, read back, export and inspect each actual output size. Discover the
   available export route: the connector inspected on 2026-10-08 exposes editing
   but no export tool, and the repo CLI has no export command. Use Canva's
   authenticated browser Download flow when available; otherwise report export
   pending and provide the editable design. Thumbnails are not final exports.
7. Snapshot the actual prompts, inputs, operations, source/working design and
   page IDs, approval evidence and final assets with `adc creative record`;
   verify with `adc creative inspect`. See `docs/creative-feedback-loop.md`.
   Set `--clients-dir` to the established client workspace when using a worktree.

Save run records under `clients/<slug>/ad-runs/<unique-run>/`, outside tracked
code. Mark manually assembled run records `provenance: manual`; recipe
provenance uses its own `recorded` / `reconstructed` schema. Preserve missing
history as limitations. Copying a template alone is not a completed creative.

Use the source's actual dimensions. Find and verify a matching Story source
for 9:16 rather than stretching a feed page or guessing a page-number offset.
Variants get new working copies, output folders and immutable recipe versions
with `parent` and `changes`. Save the testing hypothesis in the run record.

## Scope

The skill automates tool orchestration during a Codex request. Canva editing,
export availability and final visual QA remain runtime checks. It does not
publish ads, schedule work, bypass preview approval or register unverified
Meta bindings. `adc native-ad` remains available for its four supported local
components and explicit local/batch requests. Do not silently replace a
requested exact Canva reference with a local approximation.
