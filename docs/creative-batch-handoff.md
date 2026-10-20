# Creative batch handoff

Package selected final creatives in the client's Google Drive and create or
update a native Google Sheet for review and later ad preparation. Use this when
the operator asks to deliver a batch, put creatives in a client folder, or make
an ad handoff sheet. Do not run after every generation unless requested.

## Resolve the batch

1. Resolve the client through the shared catalog and read its client guidance.
   Identify the selected creative versions from the conversation, recipes and
   delivery manifests. A recent filename alone does not prove approval.
2. Use the destination supplied for this batch. Otherwise inspect the client's
   existing Drive structure and propose a meaningful batch folder there, such
   as a month, campaign or product launch. Reuse a clearly matching existing
   folder/sheet. Ask only when the client, destination or included versions are
   materially ambiguous. Never hardcode a previous client's folder or month.
3. Inventory final assets: creative ID/name, type, actual dimensions and ratio,
   recipe version/output role where available, review status and local source.
   Exclude raw generations, rejected revisions and QA frames unless requested.
   Mark missing provenance honestly; do not invent a recipe.
4. Use the operator's own connected Google Drive/Sheets tools and their skills.
   NetBird and the shared service do not grant Google access. On an employee
   machine, retrieve needed assets through supported shared creative download
   commands; do not assume the host's local paths exist there or share keys.

## Upload and organize

- Use readable filenames with a stable creative ID, treatment and actual ratio,
  for example `CLIENT-01_Product_Organic-Pill_9x16.mp4`. Give different creative
  treatments their own IDs; size variants of the same treatment share an ID.
- Upload copies to the resolved batch folder, preserving originals and recipes.
  A flat folder works for small batches; use per-creative or carousel subfolders
  when needed. Preserve the client's established organization where practical.
- Reconcile an existing delivery manifest and destination listing before
  uploading. Match content hashes where available, not names alone. If an upload
  has an uncertain result, inspect Drive before retrying. Do not silently replace
  a different file with the same name or duplicate a completed batch.
- Keep inherited sharing. Do not make files public, invite people or message a
  client without authorization. Creating the requested folder/sheet and uploads
  needs no additional confirmation when already authorized.

## Main sheet: Creatives

One row represents one creative/ad concept. Preserve columns A-H in this order:

| Column | Header | Contents |
|---|---|---|
| A | Creative type | Video, Image or Carousel |
| B | 1:1 version | Verified Drive link, or blank |
| C | 9:16 version | Verified Drive link, or blank |
| D | Ad copy variation 1 | Primary text |
| E | Ad copy variation 2 | Alternate primary text |
| F | Headline variation 1 | Headline |
| G | Headline variation 2 | Alternate headline |
| H | Ad destination URL | Verified product or landing page |

After H, retain Creative ID, Creative name, other actual ratios (for example a
4:5 version), and Notes. Add the tracking fields below after existing columns;
match by header, never shift or overwrite operator columns. Never put a 4:5 file
in the 1:1 column.

| Tracking field | Meaning |
|---|---|
| Meta ad name | Exact proposed launch name, then reconciled against readback |
| Review status | Draft copy, Needs creative review, Needs destination, Approved, Rejected |
| Launch status | Not launched, Created paused, Activation confirmed, Delivery observed, Paused, Unknown |
| Meta ad IDs | All verified ad IDs using this creative; blank before creation |
| First activation (UTC) | First verified activation timestamp, not upload/creation time |
| First spend date | First date with observed spend, with account timezone |
| Recipe versions | Ratio-to-version IDs and output role (normally final) |
| Retention | Keep, Review for cleanup, Archived locally; never an automatic delete flag |
| Usage checked at (UTC) | Timestamp of last actual launch/binding/usage reconciliation |

Use a stable Creative ID in filenames, manifests and the Meta ad name. A useful
default is `NX | Video | Product | Treatment | Oct 20 | CLIENT-BATCH-V01`.
Honor supplied client naming conventions. Size variants share a Creative ID;
different treatments get different IDs. Names are searchable labels, not unique
database keys: bind exact client, account, ad ID, recipe version, output role and
SHA-256. Proposed names do not prove that an ad exists. Preserve actual readback
names and rename history after launch; never rename live ads during handoff.

When extending a sheet, backfill proposed names for existing rows but leave
unverified historical usage Unknown. New outputs from the current run may be
Not launched when that history is known. Do not promote review status merely
because an operator asks to upload a preview. Keep QA concerns visible.

Keep paired sizes in one row, not separate ads. Leave missing ratios blank and
explain relevant placement limits in Notes. Do not generate or crop extra assets
just to fill cells. A clean 9:16 video can leave 1:1 blank when the operator accepts
auto-cropping and inspection confirms the important content remains visible.
Do not assume every video without captions is crop-safe. For captioned video,
check text throughout the timeline before claiming square auto-crop is safe.

Reuse approved copy when supplied. Otherwise draft two copy and headline options
from the product and client guidance and label them as drafts pending review.
Use plain language, no em dashes and no invented offers, testimonials or claims.
If the product/destination is uncertain, mark it unresolved instead of guessing.
Preserve supplied URLs/tags; do not invent tracking parameters.

## Carousel cards tab

Keep one main row for the carousel's shared copy. Create a `Carousel cards` tab
with one row per card, linked through the same Creative ID:

| Column | Header |
|---|---|
| A | Creative ID |
| B | Card order (1-based) |
| C | 1:1 image |
| D | 9:16 image |
| E | Card headline |
| F | Destination URL |
| G | Notes |

Add other ratios only when available. Preserve deliberate card order in both
the table and filenames (`CLIENT-02_Card-01_1x1.png`). Use card-specific URLs
and headlines when provided. Main-sheet size cells may link to clearly labeled
ordered size folders; otherwise leave them blank and point to this tab in Notes.
Do not present one card's image as the entire carousel. An empty template tab is
fine when the batch has no carousel; never add fictional card rows.

## Build, verify and save

- Follow the installed Google Drive, Google Sheets and spreadsheet-authoring
  skills for supported creation/import tools. Create a native Google Sheet in
  the chosen batch folder. For an existing handoff sheet, inspect it first and
  edit bounded ranges matched by Creative ID, preserving operator changes.
- Use clear headers, frozen header rows, filters, readable widths and wrapped
  copy. Add a Video/Image/Carousel dropdown when supported. Keep instructions
  outside the data table. Do not hide important URLs behind unexplained labels.
- Read Drive metadata back: correct folder parent, file type, expected size and
  available checksum. Check source dimensions and confirm every sheet link maps
  to the intended creative, ratio and version. Read the native sheet back to
  verify headers, rows, copy, blank sizes and carousel order after creation.
- Save a delivery manifest in the client's working-data delivery location using
  supported host file-writing tools for remote operators. Record batch/client,
  folder and sheet IDs/URLs, tab and creative IDs, recipe/output references,
  source hashes, filenames/ratios, uploaded file IDs/URLs, copy review status,
  timestamp and verification results. Record missing fields as gaps. Never save
  credentials or expiring signed download URLs. Do not rewrite immutable recipes.
- Return the folder and native sheet links, counts of creatives/files, missing
  sizes or pending copy review, and any unresolved verification. If access is
  blocked, prepare the inventory/copy locally and state what remains; do not
  claim an upload or sharing succeeded. No Meta launch is implied by delivery.

Example request: “Package this batch for CLIENT in this Drive folder and make
our creative handoff sheet. Keep the clean video 9:16 only.”

## Launch reconciliation and disk cleanup

Maintain a `Launch log` tab when tracking launch history. One row represents
one platform ad: Creative ID, platform, account ID, ad ID, actual ad name,
recipe/output bindings, creation timestamp, activation timestamp, first spend
date/timezone, current verified status, receipt/evidence reference and checked-at
timestamp. One creative can have several ads. Keep those rows when an ad pauses.

After an approved launch action, use the execution receipt and readback to update
the log and the matching main row. Created paused, activation confirmed and first
observed spend are separate events. First spend comes from analytics; a configured
ACTIVE status alone does not prove delivery. Record per-ratio bindings for flexible
ads and per-card bindings for carousels. Never invent IDs or mark a creative used
from its filename, sheet presence or planned ad name. If this operator lacks Sheet
access, retain a pending reconciliation in the delivery manifest and report it.
This is an agent-maintained handoff workflow, not a background Sheet sync service.

For a later cleanup request, prepare a dry-run inventory with exact paths, hashes,
sizes, recipe ancestry, Drive file IDs/checksums, launch bindings and usage evidence.
Check all uses of each asset, not just one row or one account. Missing bindings,
incomplete history, unverified Drive copies or unresolved approval mean Keep.
Do not infer never-used from zero recent spend. A paused creation still references
the media and is kept until explicitly retired and reconciled. Any ever-launched
creative, source used by a retained descendant, shared input or uncertain usage
stays protected by default.

An explicitly rejected/retired, verified never-used output can be proposed for
cleanup after backup verification. Distinguish duplicate working exports from
immutable recipe-bundle assets. Deleting a working copy may save little if a recipe
contains another copy; report actual reclaimable bytes. Never remove recipe-bundle
media, parent inputs or manifests through ordinary cleanup. They are required for
hash verification and reproducibility; archival needs a separate supported restore
plan. Preserve prompts, hashes, receipts, lineage, decisions and a deletion audit.

Show the exact candidate list and reclaimable space for approval before deletion.
Confirm each resolved absolute path stays inside the intended client directory.
Prefer recoverable quarantine first; permanent removal is separately explicit.
Uploading to Drive or choosing Review for cleanup is not deletion permission.
Never delete Drive copies or alter sharing as part of local disk cleanup.
