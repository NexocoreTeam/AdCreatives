# Realistic People in NB2 Prompts

The single biggest predictor of "this image looks real" vs. "this image
looks AI" in Nano Banana 2 output is whether the prompt names specific
camera bodies, lens models, apertures, film stocks, and lighting setups
verbatim. NB2 has a built-in fallback to plastic-skin, doll-eyed,
perfectly-lit portrait mode whenever the prompt lacks photographic
specificity. The skill below is the minimum required to override that
fallback.

Apply this skill to ANY prompt that includes a person — full body, ¾,
close-up, or even just hands/torso. Skip only for product-only studio
shots with no human present.

**Rule of thumb**: write like a creative director briefing a working
photographer. Specify the body, lens, aperture, film stock, lighting
setup, and what the subject is DOING (mid-action, not posed). Generic
descriptors like "good lighting" or "portrait lens" produce stock-photo
fallback output every time.

---

## Pattern source

Patterns distilled from the photoreal entries in
`prompts/library/nanobana/` (especially `ym-10-photorealistic-makeup-portrait`,
`ym-07-candid-mirror-selfie-beauty`, `ym-52-cinematic-festival-portrait`,
`uc-16.9-relaxed-couch-portrait`) plus the published patterns at:
- `miraflow.ai/blog/50-nano-banana-prompts-that-look-like-real-photos`
- `deepdreamgenerator.com/blog/nano-banana-2-best-prompts`
- `imagine.art/blogs/nano-banana-2-prompt-guide`

Use the verbatim phrases below — do NOT paraphrase. NB2 reacts strongly
to the exact wording, especially camera body + lens + aperture combos.

---

## Block 1 — Camera (required, verbatim — name BODY + LENS + APERTURE)

Pick the camera spec that matches the brief's register. Quote it
word-for-word in the prompt. NB2 anchors on specific numbers — a body
without an aperture or a focal length without a body produces
stock-photo fallback.

| Register | Camera spec — quote verbatim |
|---|---|
| Counter-hold UGC, daylight indoor | `Shot on Sony A7 IV with 50mm f/1.8 prime, ISO 400, natural daylight, mild grain` |
| Lifestyle indoor (couch / kitchen / desk) | `Shot on Fujifilm X-T5 with 35mm f/2 lens, ISO 800, soft window light, fine grain` |
| Native UGC / smartphone candid | `iPhone 15 Pro rear camera, 26mm equivalent, soft daylight, candid framing, slight handheld motion` |
| Mirror selfie | `iPhone 15 Pro rear camera via mirror, 24mm equivalent, chest-level reflection, sharp deep focus, no mirror distortion` |
| Direct-flash candid | `iPhone 15 Pro with on-camera flash, fast shutter, ISO 800, hard shadows behind subject, bright forehead/nose highlights` |
| Editorial portrait (close-up, face/skin focus) | `Shot on Hasselblad X2D with 135mm f/2.8, shallow DOF, tack-sharp eyes, creamy bokeh, Kodak Portra 400 film grain` |
| Authority / podcast studio | `Shot on Sony FX3 with 50mm f/1.8, three-point lighting, soft key + fill + subtle rim, shallow DOF, professional color grading` |
| Cinematic outdoor / golden hour | `Shot on Canon R5 with 85mm f/1.4 prime, ISO 200, golden-hour backlight, shallow DOF, Cinestill 800T cinematic film color` |
| Documentary editorial | `Shot on Leica Q3 with 28mm f/1.7, natural single-source light, Kodak Portra 400 emulation, candid documentary framing` |

If none fits, default to `Shot on Sony A7 IV with 50mm f/1.8 prime, ISO 400, natural daylight, fine grain`.

Body, lens, aperture, and ISO MUST all appear. Don't say "portrait lens"
or "professional camera." Name the gear.

## Block 2 — Film stock and color grading (required — pick ONE)

NB2 has learned film stock characteristics from training data. Naming a
specific stock biases the output color grade, contrast curve, and grain
pattern in a way that no abstract color descriptor can match.

| Mood needed | Film stock + color grading phrase |
|---|---|
| Warm natural skin, casual lifestyle | `Kodak Portra 400 emulation, natural warm skin tones, soft pastel palette` |
| Editorial cool, modern fashion | `FUJI Pro 400H emulation, cool muted color grading, soft pastels` |
| Cinematic, neon / evening / mixed light | `Cinestill 800T emulation, cinematic teal-and-orange color grade, halation glow on highlights` |
| Documentary, journalistic | `Kodak Tri-X 400 emulation, B&W high-contrast, fine grain` (or `Kodak Portra 400 for documentary color`) |
| High-end magazine beauty | `Phase One IQ4 medium-format digital, neutral natural color grade, no aggressive grading` |

**Avoid** "vibrant colors," "saturated," "Instagram-style filter" — those
push toward AI-style oversaturation. Always pair "natural color grading"
or a named film stock with the camera spec from Block 1.

## Block 3 — Lighting (required, specify direction + quality + color)

State direction, quality, color temperature, AND name the lighting
setup. Three-point lighting is the editorial-portrait default; single-
source window light is the lifestyle default.

| Register | Verbatim lighting spec |
|---|---|
| Daylight indoor lifestyle | `Single soft window light from upper-left at ~45°, warm 4500K color temperature, gentle shadow falloff across face` |
| Editorial portrait studio | `Classic three-point lighting: soft key light at 45° creating gentle jawline shadows, subtle rim light separating subject from background, low ambient fill` |
| Documentary candid | `Single ambient light source (window / overhead pendant / lamp), no studio fill, natural shadow drop` |
| Native flash | `On-camera direct flash, hard shadows behind subject, bright forehead/nose highlights, mixed with warm ambient` |
| Golden hour outdoor | `Soft golden-hour backlight from behind subject, warm rim around hair, soft front fill from open shade` |
| Cinematic mixed | `Soft dusk fill on face combined with cool [neon / screen / sodium-lamp] rim light from behind, halation around highlights` |

Avoid "good lighting," "natural lighting," "well-lit." NB2 reads these
as no constraint and falls back to even studio flat illumination.

## Block 4 — Skin, anatomy, and hands (required, verbatim — 4 magic phrases)

These four phrases together are the most reliable anti-uncanny-valley
override in NB2. Include all four in every person-containing prompt,
quoted exactly:

1. `Visible pores, natural skin texture variation across the face, subtle under-eye detail`
2. `Hyper-detailed skin — no airbrushing, no plastic smoothness, slight natural asymmetry`
3. `Natural eye catchlights, soft realistic gaze, no doll-like glassy eyes`
4. `Five fingers per hand, anatomically correct grip, natural relaxed finger positioning`

Add ONE pose-specific cue:
- For counter-hold poses: `Forearms resting on the counter, weight settled, shoulders soft, mid-thought micro-expression`
- For seated poses: `Relaxed seated posture, slight forward lean, hands occupied with an action (not held statically)`
- For standing portraits: `Weight on one leg, soft contrapposto, hands mid-gesture not posed`
- For close-ups: `Head turned slightly off-axis, soft micro-expression, mid-blink or mid-thought, not a held stare`

Add ONE clothing cue when wardrobe is visible:
`Realistic fabric folds and shadows on the [garment], natural drape, soft texture detail`

## Block 5 — Composition register (pick ONE — never mix)

Match the brand voice. Documentary and editorial are the most likely
fits for testimonial-review and UGC briefs.

| Register | Verbatim cue |
|---|---|
| Documentary editorial | `Documentary photography style, candid moment captured incidentally, editorial wellness-magazine aesthetic, real-life imperfections preserved` |
| Native UGC | `Candid, not posed, slightly off-center framing, subtle natural grain, feels like a friend's Instagram post, iPhone capture energy` |
| Lifestyle influencer | `Hyper-detailed lifestyle photography aesthetic, real-life candid, mid-2020s creator content energy` |
| Editorial / produced | `High-end magazine portrait aesthetic, fashion editorial meets authentic, professional color grading, 8K resolution` |
| Cinematic | `Cinematic, photorealistic, dynamic confident pose, film-still composition, anamorphic feel` |
| Authority studio | `Professional, confident, friendly expression, clean cinematic studio atmosphere, shallow DOF` |

The model must do something specific — name a pose, expression, AND
action. Generic phrasing like "looking happy" or "standing naturally"
produces posed-mannequin output. Mid-action beats held-pose every time.

## Block 6 — Negative cues (required, at end of prompt — verbatim)

Always append this exact block as the last line of the prompt:

```
Negative prompt: stiff pose, posed/staged feel, plastic skin, smoothed
airbrushed skin, waxy face, stock-photo energy, uncanny valley,
malformed hands, extra fingers, glassy doll eyes, AI-generated face
artifacts, oversaturated colors, Instagram filter look, vibrant
HDR, foreign-language signage, celebrity look-alikes, blurry subject
when subject should be sharp.
```

When the scene is a mirror selfie add: `no mirror distortion, no reversed text`.
When the model holds a product add: `product label readable, correct text orientation, no warped label`.
When the brief specifies a hook about a symptom (bloating, brain fog, fatigue): match the body language. See PERSONA EMBODIMENT in PROMPT_WRITER_SYSTEM.

---

## Anti-italic typography default

The default NB2 output for any quote-overlay ad tends toward an
italicized, ornate serif with decorative quotation marks. This is rarely
what the brief wants. Unless the brief's `visual_direction` block
explicitly requests italic-serif treatment, default to:

- `Clean modern sans-serif, medium weight, tight kerning, NOT italic`
- For quote overlays: small, neutral, non-decorative quote marks (or omit entirely)
- Avoid the phrases "italic serif", "decorative serif", "elegant script", "classic serif", "high-contrast serif"

If the brief lists a quote as part of TEXT INVENTORY, render it in
standard sans-serif unless the inventory explicitly says otherwise.

## One brand mark rule

The default NB2 output for any branded ad tends to add Trustpilot, B
Corp, CO2-neutral, "as seen in", and a brand wordmark — all on the same
image. This is rarely what the brief wants. Unless the brief explicitly
requests multiple badges:

- Render AT MOST ONE brand element beyond the product label itself
- The product label on the bottle/package counts as the primary brand mark
- A small Trustpilot icon (if the reference has one) counts as the
  optional second element
- DO NOT render a separate wordmark + a Trustpilot badge + a B Corp icon
  on the same image — pick one or none

If the brief doesn't list a brand mark in TEXT INVENTORY, do not add one.
The product label alone is enough.

---

## Quick checklist — every person-containing prompt must include

Before returning the prompt, verify it contains all six:

1. **Camera spec** — body + focal length + aperture + ISO (Block 1)
2. **Film stock or color grading** — named film stock or "natural color grading" (Block 2)
3. **Lighting** — direction + quality + color temperature (Block 3)
4. **Four skin/anatomy magic phrases** verbatim (Block 4)
5. **Composition register** — pick one, name a mid-action moment (Block 5)
6. **Negative prompt** appended at the end (Block 6)

Missing any one of these reliably produces AI-stock-photo output.
Including all six puts NB2 in real-photograph mode.

---

## How this skill is loaded

This file is loaded as system context in
`generators/prompt_engine.py:PROMPT_WRITER_SYSTEM`. Every call to
`prompt_from_brief()`, `prompt_from_reference()`, and
`prompt_from_library()` includes these patterns. The prompt-writer
treats Blocks 1-6 plus the anti-italic and one-brand-mark rules as a
hard checklist for any person-containing concept.

When the brief specifies `creative_mechanic` like "UGC Static" or
"Talking Head" or "Lifestyle Hand-Hold", the writer should pick the
matching register from Block 5 and include the corresponding camera
spec from Block 1.

When the user provides a `creative_direction` at generation time (via
`--creative-direction` flag or the dashboard's creative-direction
field), that directive is the highest-priority instruction — it
overrides any generic pattern from this skill that contradicts it.
