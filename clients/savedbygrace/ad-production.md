# Saved by Grace Co. — Ad Production Guide

*SBG-specific patterns + locked anchors + brand voice for ad work. Pair with
the universal `higgsfield-ad-production` skill for generation mechanics.*

---

## Locked character anchors (reuse, don't regenerate)

These are the highest-value assets in the project. Reuse them in every new ad
instead of generating new faces.

| Character | Type | ID / Path | Description |
|---|---|---|---|
| **Mom B** | HF image_job ID | `6a47867f-b14f-444b-9d4e-9efa1fa4b8ef` | Brunette midwest mom, 30, soft features. Pass as `medias` reference. |
| **Baby B** | HF image_job ID | `c5ce2320-8e53-4896-acb6-5d2ac96bc0d5` | ~20-month-old toddler with curly brown hair. Pass as `medias` reference. |
| **UGC mom (selfie)** | HF media_id (uploaded) | `404265ea-2711-4212-93a1-10291020b170` | Real customer UGC reference — darker skin, wavy dark hair, in red Loves Jesus + America Too tee. Bedroom backdrop. Pass as reference for new UGC variations. |
| **UGC selfie file** | local | `clients/savedbygrace/models/ugc-mirror-selfie.png` | Source UGC image; re-upload to HF if media_id expires. |
| **SBG Co. logo** | local | `clients/savedbygrace/brand/logo.png` | Hand-lettered "SBG Co." in warm dark brown, transparent BG. Use in quote cards, brand-mark tiles, footer blocks. |

Rights note: confirm UGC creator's likeness rights before training a Soul ID
off her face or generating *new* synthetic scenes of her. Reusing her as-is
in a single ad is lower risk than synthesizing derivative content.

---

## Foreplay model replacement rule

Foreplay references are never a source of model identity for Saved by Grace.
They only control the ad mechanic: pose, crop, camera angle, text capacity,
background type, product placement, and overall visual structure.

When adapting a model-led Foreplay ad, use this image-role logic:

1. **Image 1 = SBG-approved model/product image.** This controls the person,
   likeness, styling, garment/product, print, fit, and product truth.
2. **Image 2 = Foreplay/reference ad.** This controls the scene, pose,
   background type, crop, lighting mood, and ad format.
3. Prompt Higgsfield to replace the exact person/product role in image 2 with
   the model/product from image 1.

Default prompt shape:

```text
Use image 1 as the model and product we want to use. Use image 2 as the
reference ad scene and layout. Replace the person wearing [describe item/role]
in image 2 with the model from image 1. Keep the person's likeness, styling,
body feel, and product/garment from image 1.

Make the person/product from image 1 look like they belong in image 2. Match
the scene's lighting, shadows, contrast, color grade, perspective, camera
quality, and photography style. The replacement should not look pasted in,
cut out, glowing, over-sharp, or photoshoot-shocked.

Keep the ad mechanic, pose, crop, and text capacity from image 2, but do not
use the model identity from image 2. Final text will be edited later in Canva.
```

If the product only exists as a flat lay but the Foreplay reference needs a
model, run the SBG AI-modeled product-photo pipeline first. Create and curate
an approved on-model product image with Model 1 or Model 2, then use that
finished on-model result as image 1 for Foreplay emulation.

For kids products, do not use the adult SBG model references. Use flat lays,
clothesline scenes, product-only collages, or a separately approved kid-safe
route.

---

## Brand visual signature (apply to every ad)

1. **Golden hour is mandatory.** Every lifestyle shot. No harsh midday, no
   studio strobes, no blue hour. Hazy late-afternoon natural light is the
   brand.
2. **Red is the only saturated color.** Everything else is cream, denim,
   wood, grass, beige. The brand's warm red is `#B23A48` — washed, not
   stop-sign red.
3. **Props tell stories.** Coke bottles (vintage glass), cherries in white
   bowls, wooden honey dippers, patchwork quilts, vintage American flags
   (folded or draped), wicker picnic baskets, wood furniture.
4. **Real bodies, real spaces.** UGC > polish. Real bedrooms, real porches,
   real picnic quilts. Anti-overproduced.
5. **Magnolia / Joanna Gaines aesthetic.** Modern Christian farmhouse for
   the millennial family. Cream + wood + linen + soft red accents.
6. **Kodak Portra 400 35mm aesthetic in every prompt.** Slight grain,
   shallow depth of field, soft warmth. This is the consistent film-stock
   note across all generations.

---

## Brand voice for ad copy

**Do:**
- Period-stacked fragments: `Simple words. Deep meaning.` / `Soft. Comfy. Says it all.`
- Lowercase warmth: `she gets it from her mama.`
- Identity tags 3–7 words: `for the wild ones.`
- Name the product directly: `the loves jesus + america, too. tee`
- Mirror brand's existing copy: `The All-American Edit is here.`
- "Cute + comfy" pair recurs for kids items.

**Don't:**
- Em-dashes or en-dashes — **anywhere**. Period or `+` or `·` instead.
- "Hurry girls, it's a vibe 🇺🇸" energy. Reads cheesy / try-hard.
- Theological language or scripture quotes in headlines.
- Hard-sales urgency mechanics. "Stock up before sizes sell out" is the
  outer edge — never countdowns or "Only 3 left!".
- Wear-it-today / instant-gratification framing.

**Voice register cheat sheet:**
- Cheesy fail: `okay y'all this loves jesus + america tee from sbg is EVERYTHING 🥹🇺🇸`
- Grounded win: `Soft, comfy, says exactly what I mean. The Loves Jesus + America, Too. tee.`

---

## Product knowledge (who wears what + graphics)

| Product | Audience | Graphic | Adult? | Kid? | Notes |
|---|---|---|---|---|---|
| **Loves Jesus + America, Too.** | Both | Small red sans-serif "LOVES JESUS + AMERICA, TOO." centered chest | Yes ($32+) | Yes ($22, baby sizes 3/6M → Youth XL) | Most versatile — works for matching mom+baby. Colorways: cream, red, blue, white. |
| **Loves Her Babies + America, Too.** | Mom only | Small red sans-serif "LOVES HER BABIES + AMERICA, TOO." centered chest | Yes ($28) | No conceptual fit (baby can't "love her babies") | Mom-coded only. Use for mom-solo ads. |
| **All American Mama's Club** | Mom only | NAVY "ALL AMERICAN" arched + RED bow center + NAVY "MAMA'S CLUB" arched + tiny red "MADE IN THE USA" | Yes ($32) | No | The iconic mom best-seller. Strongest visual ID. Cream or white tee. |
| **FERAL Tee** | Kid | Tan/caramel bold arched college-style "FERAL" centered chest | Adult version exists separate ($28) | Yes ($22). Colors: black, pepper, forest green. | Kid-coded. "Wild mama" energy. |
| **Wild Like My Curls** | Kid (and adult) | Dark distressed two-line "WILD LIKE / MY CURLS" stacked centered | Yes | Yes (3/6M → Youth XL) | Curl-identity. Strongest fit for curly-haired kids. |

**Common mistake to avoid:** when generating multiple tees in one image,
don't pass multiple product references at once — the model will mix the
text. Generate each tee with only its own reference + a strong prompt.

---

## SAVEDBYGRACE_PRESET (brand text overlay)

Defined in [`generators/text_overlay.py`](../../generators/text_overlay.py):

```python
SAVEDBYGRACE_PRESET = BrandPreset(
    name="savedbygrace",
    accent_color=(178, 58, 72),        # #B23A48 warm brand red — CTA pill fill
    text_color=(50, 35, 22),           # #322316 warm dark brown — quote text
    wash_color=(245, 240, 230),        # #F5F0E6 cream linen — bottom wash / pill bg
    wash_alpha=235,
)
```

**Available overlay functions:** (all use the preset by default)
- `render_ad_overlay()` — brand-standard: bottom cream wash + quote + CTA pill
- `render_centered_pill_overlay()` — Oddbird-style: floating cream pill at vertical center
- `render_tiktok_caption_overlay(lines=[...])` — one auto-width pill per line, flat (no shadow), bold sans
- `render_mixed_caption_overlay(items=[...])` — mix of pill + handwritten lines, per-item color overrides

Use `Caveat-Variable.ttf` for handwritten lines (download from Google Fonts —
see `clients/savedbygrace/fonts/`).

---

## Reusable ad templates built this session

| Format | Script | Notes |
|---|---|---|
| **Americana 4-tile collage** | `collage/compose_collage.py` | 2×2 lifestyle + flat lay, cursive headline + brand-voice sub-headline. Brand red accent. |
| **Beek-style review ad** | `review-ad/compose_review_ad.py` | Top hero flat lay + UGC selfie + cream quote card with logo + thin white frame. |
| **iMessage v8 (RTR-style)** | `imessage/compose_imessage_v5.py` | 9:16 full-bleed photo, centered chat bubbles with iOS tails + timestamps, product tag pill + brand mark at bottom. |
| **UGC 4-tile (Oddbird-style)** | `ugc-grid/compose_ugc_grid.py` | 2×2 mirror-selfie grid + mixed pill/handwritten caption. Reuses UGC model. |
| **3-column masonry (Pinterest-style)** | `masonry/compose_masonry.py` | True 3-col independent stacks, rounded cards, 2×2 CTA cell, mix of lifestyle + product-on-white. |

**Pattern**: every script keeps source frames in a `source/` subfolder and
the final composed output in the parent folder. Iterate the script, not the
source frames.

---

## Common pitfalls (specific to SBG)

1. **Don't put mom in FERAL or Wild Like My Curls** — those are kid-coded.
   Mom wears LJA, LHB, or AAMC.
2. **Don't put adult-version products on a baby** — Wild Like My Curls
   *does* come in baby sizes (3/6M+), but verify the product page first.
   Loves Her Babies has no kid version (conceptual mismatch).
3. **Cream tee + cream linen flat lay** = product text gets lost. Either
   use a contrasting tee colorway, or ensure the text is rendered at
   high resolution.
4. **Don't mix multiple "LOVES X" tees in the same generation** — the model
   confuses the text. Generate each tee separately.
5. **Americana = vintage warm, not loud fireworks.** Folded flags, glass
   Coke bottles, patchwork quilts. Not flag overlays, not bright primary
   reds.

---

## Cost-efficient workflow for SBG

1. **Generate the source images ONCE per face/character anchor.** Reuse
   forever.
2. **Iterate composition + copy in Python.** Free, instant, deterministic.
3. **One scene = one base shot** that can be re-composed into multiple ad
   formats (e.g., the mom+baby picnic shot powers Americana collage AND
   iMessage AND masonry hero).
4. **For variant tests**, change only the text/CTA in the composition
   script. Don't regenerate images.

Typical ad cost: 5–25 credits (one fresh face anchor + 2–4 variation shots).
Most iterations after that are ~$0.
