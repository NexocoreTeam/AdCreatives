# Creative recipes and performance feedback

The first slice connects a saved creative version to a single-image Meta ad,
then imports an analytics winner packet into a review queue. It never launches
ads or starts paid generation. Saved by Grace is the pilot client.

## What is implemented

- `adc native-ad` and `adc ugc-ad` capture their effective render settings and
  copy assets into a new recipe when client and product are known. Provide
  them through the brief, or `--client`/`--product` for native and
  `--brand`/`--product` for UGC. Missing identity prints a capture warning.
- `adc creative record` snapshots an ordered step manifest from any production
  route. Preserve actual prompts and settings; do not invent missing history.
- `adc creative inspect` validates the manifest and hashes of every saved asset.
- `adc creative import-winners` verifies the exact local version, product,
  output role and asset hash, then writes a review queue without generating.
- Analytics stores manifests and exact ad bindings in private Postgres tables,
  and exports explicit-period, threshold-based candidate packets.

This is not yet automatic capture for every Higgsfield/fal/Canva workflow.
Use `creative record` for those routes. Automatic native/UGC capture records
the rendering stage, not the undocumented history of its base photo. Fonts
remain environment dependencies. Recipes document these limitations, and an
AI model rerun is not guaranteed to reproduce identical pixels.

## Version and asset rules

Each version has its own UUID and immutable bundle:

```text
clients/<slug>/creative-recipes/<version-id>/recipe.json
clients/<slug>/creative-recipes/<version-id>/assets/...
```

The manifest contains a concept ID, version ID, optional parent, intended
changes, ordered steps, prompts/settings, brief snapshot, runtime versions,
source paths and SHA-256 hashes. File copies inside the bundle preserve the
inputs and outputs even if working files change. Render metadata links back
to this version. Steps refer to asset roles, not filenames guessed later.

These bundles and feedback queues are private working data, gitignored even
for test clients. Include them in the agency's asset backup/sync. Postgres
stores the manifest and bundle location, not the image bytes. Both machines
must receive the same bundles through private storage; a local absolute path
does not automatically work on another machine. Never rely on expiring Meta
CDN links as the asset archive.

## Capture a native variation

After the existing strategy, source and production approval gates:

```text
adc native-ad --brief clients/<slug>/briefs/<brief>.yaml -o ai-ads/<slug>/native/<variant>
adc native-ad --brief clients/<slug>/briefs/<variant-brief>.yaml --parent-recipe <parent/recipe.json> --change setting=porch -o ai-ads/<slug>/native/<new-variant>
adc creative inspect --recipe <new-version/recipe.json>
```

The operator must actually change the inputs/spec to make the variant.
`--change` documents that change; it does not instruct an image generator.
Use a new output folder per variant. Keep one major change at a time when the
purpose is a controlled test. Product swaps require product-specific copy and
proof review. Cross-client parents are rejected.

## Record existing or multi-step production

Create a JSON step manifest. Paths are relative to the manifest or absolute.
Use `provenance: reconstructed` and explicit limitations for recovered history;
`recorded` is for steps captured at production time. The following is an
illustrative intake template, not evidence of a completed generation:

```json
{
  "client": "savedbygrace",
  "product": "wild-like-my-curls",
  "provenance": "reconstructed",
  "limitations": ["Earlier photo creation is missing; final edit only."],
  "assets": {"base": "base.png", "final": "final.png"},
  "steps": [{
    "tool": "hf-web",
    "prompt": "<exact saved prompt, not a newly invented one>",
    "settings": {"aspect_ratio": "4:5", "resolution": "2k"},
    "inputs": ["base"],
    "outputs": ["final"]
  }]
}
```

```text
adc creative record --manifest <intake.json>
```

Add intermediate images as assets and additional steps in execution order.
Include manual edits, source/permission evidence and exports where available.
Reconstruction does not confer approval or winner status. For variants, add
`parent` (path to its recipe) and `changes` (component-to-change descriptions).

## Analytics handoff

The companion analytics repo's `measurement-platform/docs/creative-exchange.md`
describes schema setup, manifest registration, exact platform-ad binding and
winner export. Register parents before children. Bind the exact exported asset
role, not just the concept or a name-based group. Confirm the platform ad is a
single image, not a flexible, catalog, carousel or video execution.

```text
adc creative import-winners --packet <analytics-winners.json> --client savedbygrace
```

The queue is written under `clients/<slug>/creative-feedback/`. Reimporting an
unchanged packet preserves the existing queue and review decisions even if
its export timestamp changed. A blocked data status or missing/tampered local
recipe fails instead of silently making a new creative.

Review each candidate's current and baseline metrics, source recipe and
limitations. Select changes, record the hypothesis, and get production
approval before paid work. Preserve the control. Rendered variants then get
new version IDs and new platform ad bindings when launched.

## Pilot activation still needed

- Match a real SBG single-image ad to its exact archived output by inspection.
- Confirm currency, account reporting timezone, attribution context, minimum
  spend/purchases, CPA or ROAS target, and conversion-delay policy.
- Review/apply the analytics migration once, then import and bind recipes.
- Run the first export and review queue manually before scheduling weekly.

No migration, recurring schedule or paid generation is activated by installing
these commands. Existing performance logs and reports are unchanged.
