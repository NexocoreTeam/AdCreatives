# Phase 1 — Aspect Ratio Variants

Generated 1:1 and 9:16 variants for 9 finalized Meta ad creatives. All outputs
saved alongside originals in their respective concept folders under
`clients/secondkind-bold/ai-ads/phase-1/`.

Pipeline used: `adc edit` (Higgsfield `nano_banana_flash`) for hf-web reframes
and `scripts/native_ugc_overlay.py` for PIL overlays on top of 1:1 clean bases.

## Results

| # | Concept | Engine | 1:1 file | 1:1 | 9:16 file | 9:16 |
|---|---|---|---|---|---|---|
| 1 | pain-010 editorial | hf-web | `pain-010/v2-amber__1x1.png` | OK | `pain-010/v2-amber__9x16.png` | OK |
| 2 | pain-010 native UGC | PIL | `pain-010/v5-native-pil__1x1.png` | OK | (existing 9:16 — not regenerated) | n/a |
| 3 | Social Mirror UGC | PIL | `social-mirror/v13-pil-brand-marigold__1x1.png` | OK | (existing 9:16 — not regenerated) | n/a |
| 4 | hook-001 (open capsule) | hf-web | `hook-001/v6-brand-marigold-serif__1x1.png` | OK | `hook-001/v6-brand-marigold-serif__9x16.png` | OK |
| 5 | pain-006 industry hides | hf-web | `pain-006/v5-notes-industry-hides-fixed__1x1.png` | OK (re-run) | `pain-006/v5-notes-industry-hides-fixed__9x16.png` | OK (re-run) |
| 6 | pain-006 trials checked | hf-web | `pain-006/v4-notes-trials-checked__1x1.png` | OK (re-run) | `pain-006/v4-notes-trials-checked__9x16.png` | OK (re-run) |
| 7 | Earned Confidence | hf-web | `earned-confidence/v5-specimen-debris__1x1.png` | OK | `earned-confidence/v5-specimen-debris__9x16.png` | OK |
| 8 | Native Reel woman | PIL | `native-reel/v4-pil-woman__1x1.png` | OK | (existing 9:16 — not regenerated) | n/a |
| 9 | Native Reel man | PIL | `native-reel/v5-pil-man__1x1.png` | OK | (existing 9:16 — not regenerated) | n/a |

All file paths above are relative to `clients/secondkind-bold/ai-ads/phase-1/`.
All output files are >2.5MB (well above the 500KB integrity threshold).

## Auxiliary outputs (clean-base 1:1 reframes)

The PIL pipeline ads (#2, #3, #8, #9) required a 1:1 clean-base photo first.
These intermediate outputs are also saved in the concept folders for future
re-overlay without paying the hf-web reframe cost again:

- `pain-010/clean-base-native__1x1.png` (8.7 MB)
- `social-mirror/clean-base__1x1.png` (8.8 MB)
- `native-reel/clean-base-woman__1x1.png` (8.7 MB)
- `native-reel/clean-base-man__1x1.png` (8.4 MB)

## Notes on re-runs

**Pain-006 (Ads 5 + 6)** had to be re-run because the first pass added a yellow
tint to what is actually a pure-white iPhone Notes-app background — the
original PNGs are `(255,255,255)` solid white but my initial prompt described
the background as "yellow Notes-app background," and the model dutifully tinted
the canvas yellow. Re-ran with explicit "WHITE Notes-app background (do NOT
add yellow or any color tint)" anchoring and the corrected versions match the
source. Both v5 (industry-hides) and v4 (trials-checked) were re-run at both
1:1 and 9:16.

**Pain-006 Ad 5 9:16 first attempt** failed with `status=failed` from the
Higgsfield job (no file saved). Retried with a more explicit prompt that named
every UI element to preserve — succeeded on the second attempt.

All other ads succeeded on the first hf-web call. No PIL overlay calls failed.

## Quality observations

- **hf-web reframes** preserved all text, all visual elements, and all colors
  on every output. Spot-checked each output side-by-side with the original.
  The model handled both the "shorter to wider/square" (4:5 → 1:1) and "wider
  to taller" (4:5 → 9:16) cases correctly without dropping content.
- **PIL overlays at 1:1** — text positions use `y_pct` of frame height so they
  auto-scale. At 1:1 (shorter than 9:16) the top caption stack sits a little
  closer to the photo subject, but the layouts remain legible and on-brand.
  No cramping. Marigold pill highlight and bottom CTA box both render
  correctly on the 1:1 frame.
- **Earned Confidence 9:16** — the capsule debris pattern reads slightly
  sparser in the taller frame but still feels intentional. Headline and
  wordmark unchanged.

## Cost estimate

| Type | Count | Per-call | Subtotal |
|---|---|---|---|
| hf-web ad reframes (initial) | 10 | ~$0.20 | ~$2.00 |
| hf-web ad reframes (pain-006 re-runs) | 4 | ~$0.20 | ~$0.80 |
| hf-web ad reframes (Ad 5 9:16 failed retry) | 1 | ~$0.20 | ~$0.20 |
| hf-web clean-base reframes | 4 | ~$0.20 | ~$0.80 |
| PIL overlay calls | 4 | $0 | $0 |
| **Total** | **19 paid calls** | | **~$3.80** |

Within the $1.50-$4.50 budget.

## Recommended next steps

- **No manual Figma finish-work is required** — all 14 outputs render cleanly
  with text, composition, and colors intact.
- The PIL-pipeline 1:1 outputs (Ads 2, 3, 8, 9) could optionally have their
  layout `y_pct` values tuned in `generators/ugc_overlay.py` if you want
  caption positions specifically optimized for square framing rather than
  the current "scale-by-percentage" approach. Not required — current outputs
  are production-quality.
- The four 1:1 clean-base photos can be reused for future variations (new
  copy on the same base photo) without paying the hf-web reframe cost again.
- Working tree is dirty as requested; review with `git status` / `git diff`
  before committing.

## Files changed (new files only, no edits to tracked files)

The new files are under `clients/secondkind-bold/ai-ads/phase-1/` and are not
yet tracked by git. The pre-existing `generators/ugc_overlay.py` modification
shown in the initial `git status` was not made by this run.
