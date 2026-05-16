# Realistic People in NB2 Prompts

The single biggest predictor of "this image looks real" vs. "this image
looks AI" in Nano Banana 2 output is whether the prompt names specific
camera and skin-texture details verbatim. NB2 has a built-in fallback to
plastic-skin, doll-eyed, perfectly-lit portrait mode whenever the prompt
lacks photographic specificity. The skill below is the minimum required
to override that fallback.

Apply this skill to ANY prompt that includes a person — full body, ¾,
close-up, or even just hands/torso. Skip only for product-only studio
shots with no human present.

---

## Pattern source

Distilled from the consistently-photoreal entries in
`prompts/library/nanobana/`:
- `lifestyle-casual-hold` (counter-hold register)
- `ym-02-realistic-mirror-selfie` (smartphone-native register)
- `ym-10-photorealistic-makeup-portrait` (lifestyle portrait)
- `uc-15.3-flash-portrait-seasonal` (flash-candid)
- `uc-16.9-relaxed-couch-portrait` (lifestyle indoor)
- `ym-50-podcast-studio-portrait` (authority studio)
- `ym-52-cinematic-festival-portrait` (cinematic outdoor)

The patterns below are what those prompts have in common. Use them
verbatim — do not paraphrase. NB2 reacts strongly to the exact phrasing.

---

## Block 1 — Camera (required, verbatim)

Pick the spec that matches the brief's register. Quote it word-for-word
in the prompt. NB2 anchors itself on specific numbers (focal length,
aperture, ISO) — paraphrasing as "a portrait lens" produces stock-photo
fallback output.

| Register | Camera spec — quote verbatim |
|---|---|
| Counter-hold UGC, daylight indoor | `Shot on a Sony A7 IV with 50mm f/1.8 prime, ISO 400, natural overhead daylight, subtle film grain` |
| Lifestyle indoor (couch / kitchen / desk) | `Shot on a Fujifilm X-T5 with 35mm f/2 lens, ISO 800, soft window light, mild grain` |
| Native UGC / smartphone candid | `Shot on iPhone 15 Pro rear camera, 26mm equivalent, soft daylight, slight motion blur, candid framing` |
| Mirror selfie | `Smartphone rear camera via mirror, 24mm equivalent, chest-level reflection, sharp deep focus, no mirror distortion` |
| Direct-flash candid | `Smartphone camera with on-camera flash, wide aperture, fast shutter, high ISO, hard shadows and bright highlights, native iPhone night look` |
| Close beauty portrait | `Shot on Hasselblad H6D with 100mm f/2.2 macro, shallow DOF, tack-sharp eyes, creamy bokeh, fine 35mm film grain` |
| Authority / podcast studio | `Shot on Sony FX3 with 50mm f/1.8, soft key + fill + subtle rim, shallow DOF, professional color grading, 8K resolution` |
| Cinematic outdoor (golden hour / dusk) | `Shot on a Canon R5 with 85mm f/1.4 prime, ISO 200, golden hour backlight, shallow DOF, cinematic film color` |

If none fits, default to `Shot on a Sony A7 IV with 50mm f/1.8 prime, ISO 400`.

## Block 2 — Skin and anatomy magic phrases (required, verbatim)

These four phrases together are the most reliable anti-uncanny-valley
override in NB2. Include all four in every person-containing prompt,
quoted exactly:

1. `visible pores, natural skin texture variation across the face`
2. `hyper-detailed skin, no airbrushing, no plastic smoothness`
3. `natural eye catchlights, soft realistic gaze, no doll-like glassy eyes`
4. `five fingers per hand, anatomically correct grip, natural finger positioning`

Add ONE pose-specific cue from this list:
- For counter-hold poses: `forearms resting on the counter, weight settled, shoulders soft`
- For seated poses: `relaxed seated posture, slight forward lean, hands occupied`
- For standing portraits: `weight on one leg, soft contrapposto, hands purposeful not posed`
- For close-ups: `head turned slightly off-axis, soft micro-expression, not a held stare`

## Block 3 — Lighting (required, specific)

State direction, quality, and color temperature. Never just "good
lighting" or "natural lighting."

- **Daylight indoor**: `soft directional window light from upper-left, warm color temperature, gentle shadow falloff across face`
- **Daylight outdoor**: `soft dappled natural light through trees` / `overcast soft light, no harsh shadows` / `golden hour rim light from behind`
- **Studio**: `soft key light at 45°, subtle rim light separating subject from background, clean specular highlights on skin`
- **Native flash**: `on-camera flash, hard shadows behind subject, bright forehead/nose highlights, mixed with warm ambient`
- **Cinematic mixed**: `soft dusk fill on face combined with cool [neon / screen / sodium-lamp] rim light from behind`

## Block 4 — Mood register (pick ONE — never mix)

| Register | Verbatim cue |
|---|---|
| Native UGC | `candid, not posed, slightly off-center framing, subtle natural grain, feels like a friend's Instagram post` |
| Lifestyle influencer | `hyper-detailed lifestyle photography aesthetic, real-life candid, 2000s digital camera vibe` |
| Editorial / produced | `high-end magazine portrait aesthetic, fashion editorial meets authentic, professional color grading` |
| Cinematic | `cinematic, photorealistic, dynamic confident pose, film-still composition` |
| Authority studio | `professional, confident, friendly expression, clean cinematic studio atmosphere, shallow DOF` |

The model must do something specific — name a pose, expression, AND
action. Generic descriptions like "looking happy" or "standing
naturally" produce posed-mannequin output.

## Block 5 — Negative cues (required, at end of prompt)

Always append this exact block as the last line of the prompt:

```
Negative prompt: stiff pose, posed/staged feel, plastic skin, smoothed
airbrushed skin, stock-photo energy, uncanny valley, malformed hands,
extra fingers, glassy doll eyes, AI-generated face artifacts, foreign-
language signage, celebrity look-alikes, blurry subject when subject
should be sharp.
```

When the scene is a mirror selfie add: `no mirror distortion, no reversed text`.
When the model holds a product add: `product label readable, correct text orientation, no warped label`.

---

## Anti-italic default

The default NB2 output for any quote-overlay ad tends toward an
italicized, ornate serif with decorative quotation marks. This is rarely
what the brief wants. Unless the brief's `visual_direction` block
explicitly requests italic serif treatment, default to:

- `clean modern sans-serif, medium weight, tight kerning, no italic`
- For quote overlays: render quote marks as small, neutral, non-decorative
- Avoid the phrases "italic serif", "decorative serif", "elegant script"

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

## How this skill is loaded

This file is loaded as system context in
`generators/prompt_engine.py:PROMPT_WRITER_SYSTEM`. Every call to
`prompt_from_brief()`, `prompt_from_reference()`, and
`prompt_from_library()` includes these patterns. The prompt-writer
treats Blocks 1-5 plus the anti-italic and one-brand-mark rules as a
checklist for any person-containing concept.

When the brief specifies `creative_mechanic` like "UGC Static" or
"Talking Head" or "Lifestyle Hand-Hold", the writer should pick the
matching register from Block 4 and include the corresponding camera
spec from Block 1.

When the user provides a `creative_direction` at generation time (via
`--creative-direction` flag or the dashboard's creative-direction
field), that directive is the highest-priority instruction — it
overrides any generic pattern from this skill that contradicts it.
