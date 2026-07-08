# Generation log: advertorial remake batch (overnight 2026-07-07)

Pipeline per ad: background plate (Higgsfield, 2:3, no text in image) → `scripts/deai_post.py`
(grain, de-gloss, downscale) → `scripts/ad_text_overlay.py` + `specs/adN.json` (PIL typesetting,
Georgia Bold serif / Segoe UI Bold sans / Consolas mono, gold-on-dark quote style) → final
1080x1620 JPEG in `final/`.

Copy rationale: see copy-deck.md. Register: unbranded advertorial curiosity, zero product clues.

| Ad | Model | Plate prompt (abridged) | Rerolls |
|---|---|---|---|
| 1 | nano_banana_2 | warm kitchen, open palm with two amber capsules upper-middle, water glass, lower third empty table | 1 (v1 hand collided with headline zone) |
| 2 | text2image_soul_v2 | woman early 50s, folded hands + wedding band on dark table, face out of frame, dim window light | 0 |
| 3 | nano_banana_2 | oxblood-to-black ember velvet abstract texture | 1 (first job returned empty result_url) |
| 4 | nano_banana_2 | glassy blue brain, luminous vagus cable, red rupture spark midpoint, teal intestines below | 0 |
| 5 | nano_banana_2 | intact dim brain dissolving into fog, one faint blue glimmer, navy black; battery HUD drawn in post | 0 |
| 6 | nano_banana_2 | translucent x-ray woman, amber glowing gut, particle stream rising to brain | 0 |
| 7 | text2image_soul_v2 | candid bathroom mirror selfie, early 50s, flat expression, frosted window | 1 (v1 looked at phone, not her reflection) |

Composite fixes during QC: ad3 headline size 0.049→0.036 (right-edge clip), ad4 vagus label
leader strike-through + headline bottom margin, ad6 headline 0.049→0.041 (clip), ad7 headline
reflow to shorter first line + 0.040 (clip).

Total Higgsfield jobs this batch: 10 (1 dud). Roughly 20-25 credits.

## 1:1 versions (2026-07-08)

No regeneration: each 2:3 plate cropped to a square window (per-ad top offset chosen to keep
the subject; see scratch script logic reproduced in specs) and re-typeset with `specs/adN-sq.json`
at square proportions. Notable square adaptations: ad4 moved the vagus label above the spark and
runs the headline over the scrimmed gut; ad6 clips at the hips and dims the lower gut glow under
the scrim; ad5 re-places the drawn battery HUD. Finals: `final/adN-remake-1x1.jpg` (1080x1080).

Assets:
- `final/ad1-remake.jpg` ... `final/ad7-remake.jpg` (upload-ready, 1080x1620)
- `final/contact-sheet.jpg` (review grid)
- `specs/` (re-editable text layouts; tweak JSON + re-run overlay, no regeneration needed)
- Background plates: `hf-output/sk-advertorial-remakes/` (untracked, keep for re-composites)
