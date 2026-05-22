# Text-only ad generation — A vs B drift experiment

A parallel generation track inspired by PYNK Creative Ecosystem. Sends ONLY
the product image to fal.ai (`nano-banana-2/edit`) plus a fully-filled
template prompt — **no reference ad image.** Existing reference-based
`adc generate` is untouched.

This is the **B-variant** in an A-vs-B test isolating whether text-only
generation produces less layout drift than the current reference-based
path on the same Cooper templates.

---

## What it isolates

| | A (reference-based) | B (text-only) |
|---|---|---|
| Command | `adc generate --reference <id>` | `adc generate-text --template <id>` |
| Template source | `clients/<slug>/templates/*.yaml` + a reference PNG in `reference_ads/raw/` | `prompts/library/cooper/*.yaml` |
| Image inputs to FAL | `[reference, product]` — **reference is canvas, product is inserted into it** (new default) | `[product]` only — no reference |
| Prompt source | `generators/prompt_engine.py` + tightened OVERRIDE directive prepended | `generators/pynk_text_filler.py` (template text + slot fill + Product Anchor) |
| Aspect ratio | Inferred from brief or `--aspect` flag | Locked from the template's `aspect_ratios[0]` (or `--aspect` override) |
| Output folder | `ai-ads/<client>/images/` | `ai-ads/<client>/text-only/<brief_id>_<ts>/<NN>-<slug>/` |
| Cost log | `adc generate` | `adc generate-text` |
| Best for | Cloning a specific reference ad with the brand's brief content | Predictable template-driven output, no reference needed |

The variable being tested is the **engine itself** — same template text, same
product, same brand DNA. If B beats A on layout fidelity, text-only is the
better default for these templates. If A is better, the reference-based
pipeline holds.

---

## Running the test

Pick a brief + product + template. Run both engines back-to-back on identical
inputs.

```bash
# 1. Browse Cooper templates
adc generate-text --client secondkind --list-templates

# 2. A — reference-based (existing)
adc generate --client secondkind --pick 3 --reference cooper-11-pull-quote-review

# 3. B — text-only (new)
adc generate-text --client secondkind \
  --brief brf_abc123 \
  --template cooper-11-pull-quote-review \
  --num-images 1
```

Outputs:

- A: `ai-ads/secondkind/images/<brief_id>.png` (+ `prompts/<brief_id>.txt`)
- B: `ai-ads/secondkind/text-only/<brief_id>_<YYYYMMDD-HHMMSS>/11-pull-quote-review/secondkind_pull-quote-review_v1.png` (+ `ad-spec.json`)

Each B output folder includes a full `ad-spec.json` capturing the prompt,
slot map, model, aspect ratio, seed, and any ⚠️ flagged invented slots.
The spec is replay-ready: rerun the same script directly on the folder to
regenerate with new seeds.

---

## What to compare

Side-by-side visual comparison. Score each pair on:

1. **Layout fidelity** — does the output match the template's spatial directives?
   Stat radial: is the product centered with stats orbiting? Pull-quote review
   card: is the review card in the bottom-left overlapping the color block?
2. **Product fidelity** — does the product look like the real product (shape,
   label text, color, packaging)?
3. **On-image text quality** — are headlines readable, correctly placed,
   contrasted against the background?
4. **Composition drift between runs** — generate 2-3 variations per side and
   look at how much variance there is.

Tag winners per template type. Some templates may favor A (where the reference
image is genuinely helpful — e.g. dense layouts the model can't reconstruct
from text alone). Others may favor B (where the reference image is
contaminating output or competing with the product image for the canvas).

---

## Recommended templates for the first round

Pick 3-5 templates spanning different complexity tiers:

| Template | Why test it |
|---|---|
| `cooper-01-headline` | Simplest layout. Tests baseline text rendering. If B fails here, the engine has a fundamental issue. |
| `cooper-07-us-vs-them` | Side-by-side composition. Layout drift is highly visible — checkmarks on right, X marks on left, brand color split. |
| `cooper-11-pull-quote-review` | Most complex of the curated 22. Review card + color block + product overlap. Stress test for text-only layout reconstruction. |
| `cooper-13-stat-surround` | Radial composition with stats orbiting product. Spatial fidelity matters a lot. |
| `cooper-33-faux-press` | Mimics a news article. Lots of small text + structured layout. |

Start with `01-headline` to confirm B works at all, then move to the harder
ones.

---

## Reference-first image_urls ordering — now the default

Tested and shipped. The art-directed path (`adc generate --reference ...`)
now constructs `image_urls = [reference, product]` by default. NB2's `/edit`
endpoint treats image 1 as the canvas to edit, so the reference ad becomes
the canvas and the product is inserted into it — which is what you want when
you supplied a reference to clone.

### Background

The old default was `image_urls = [product, reference]`. NB2 treated the
product image as the canvas and the reference ad as supplemental — which
caused the reference's layout to be loosely interpreted rather than faithfully
replicated. Major contributor to the layout drift problem this experiment
set out to investigate.

### What changed

| Behavior | Before | After |
|---|---|---|
| `image_urls` order | `[product, reference]` | `[reference, product]` |
| What NB2 treats as canvas | product (its own framing/background dominates) | reference ad (its composition dominates) |
| Layout fidelity to reference | loose | strong |
| Default OVERRIDE directive | none | injected — "image 1 = layout wireframe only, image 2 = actual product, all text from prompt not from image 1" |

### Escape hatch

If you need the old behavior (rare — e.g. to reproduce historic outputs):

```bash
adc generate --client X --pick 1 --reference my-template --legacy-product-first
```

Or globally via env var: `ADC_LEGACY_PRODUCT_FIRST=1 adc generate ...`

### The OVERRIDE directive (v2)

When reference-first is active, a directive is prepended to the prompt that
tells the model explicitly:
- Image 1 is a layout wireframe — replicate composition, panel positions,
  background color, color scheme, typography style, but NO text
- Image 2 is the actual product
- All copy comes from the prompt below, never from image 1

This was tightened in v2 after the v1 directive left a leak — references with
strong on-image text (e.g. "Probiotic Chews" from a PetLabCo us-vs-them ad)
were bleeding into the output even when the brand's product was different
(SecondKind capsules). v2 says "mentally blur all text in image 1 and only
replicate its shapes/regions."

### When NOT to use the new default

The reference-first default assumes you actually want to clone the reference
ad's layout. If your `--reference` is being used as loose tone inspiration
rather than as a structural template, the old `[product, reference]` ordering
may produce more brand-tone-consistent (but layout-loose) output. Use
`--legacy-product-first` for that workflow.

---

## Engine internals (for debugging)

- **Bracket-fill:** `generators/pynk_text_filler.py:fill_template()`. Deterministic mapping for `[BRAND]`, `[BRAND COLOR]`, `[YOUR PRODUCT]`, `[BACKGROUND]`, `[BENEFIT N]`, `[YOUR HEADLINE]`, etc. Anything else gets batched into a single Claude Sonnet 4.6 call. Stats / names / member counts with no source data are filled with plausible placeholders + a ⚠️ marker; the marker is stripped from the rendered prompt but the flagged list is preserved in `ad-spec.json` for human review.
- **Product Anchor:** prepended to every prompt. Replaces everything before the first `Create:` in the cooper template with a fixed "do not invent, modify, or substitute this product" preamble.
- **Aspect lock:** taken from the template YAML's `aspect_ratios[0]`. Overridable via `--aspect`.
- **Contrast rule:** background luminance > 0.5 → dark text; else white text. Text color descriptor is included in the prompt explicitly.
- **FAL call:** `generators/pynk_text_client.py:generate_text_only_ad()` → `fal_client.generate(image_urls=[product_url], aspect_ratio=...)`.
- **Output spec:** `ad-spec.json` adjacent to each PNG. Contains full prompt, slot map, flagged invented list, chosen text color, brand/product/brief refs, seed, FAL model id. Replay-ready.

---

## Smoke test (no FAL spend)

To verify the engine works without burning credits:

```bash
py scripts/smoke_test_pynk_text.py --client secondkind --template cooper-11-pull-quote-review
```

Exercises load → fill → preamble → bracket check. Requires `ANTHROPIC_API_KEY`
in `.env` (Claude is called for batch slot fill + color naming). Does NOT
call FAL.
