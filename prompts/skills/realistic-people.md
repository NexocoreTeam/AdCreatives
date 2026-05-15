# Realistic People in NB2 Prompts

Distilled patterns from a curated subset of nano-banana prompts that
consistently produce realistic AI models (synthesized from
`prompts/library/nanobana/`: `lifestyle-casual-hold`,
`ym-02-realistic-mirror-selfie`, `ym-10-photorealistic-makeup-portrait`,
`uc-15.3-flash-portrait-seasonal`, `uc-16.9-relaxed-couch-portrait`,
`ym-50-podcast-studio-portrait`, `ym-52-cinematic-festival-portrait`).

**When to apply this skill:** any NB2 prompt that includes a person — full
body, ¾, close-up, or even a partial shot (e.g. a hand holding the product).
Skip it for product-only studio shots with no human present.

The cost of vague photography direction is uncanny-valley faces, plastic
skin, "stock photo" energy, and posed-rather-than-candid framing. Every NB2
prompt featuring a person MUST specify all five blocks below.

---

## Block 1 — Camera & lens (pick the register that fits the scene)

| Scenario | Camera spec to use |
|---|---|
| Casual hand-hold over a counter, no face visible | "iPhone quality, natural overhead daylight, slightly warm, slight natural grain" |
| Mirror selfie, native UGC, full body or ¾ | "smartphone rear camera via mirror, 24-28mm equiv, chest-level reflection, sharp deep focus, 4K" |
| Direct-flash candid portrait, native | "smartphone camera, wide aperture, fast shutter (flash), high ISO, hard shadows + bright highlights" |
| Lifestyle indoor (couch, bedroom, kitchen) | "35-50mm portrait lens, low-medium ISO, sharp face with slight background DOF blur" |
| Close beauty portrait (face/skin focus) | "85mm portrait prime, f/2.0-f/2.8, shallow DOF, tack-sharp subject, creamy bokeh, subtle 35mm film grain" |
| Studio interview / podcast / authority | "50mm lens, f/1.8, soft key + fill + subtle rim, shallow DOF, professional color grading, YouTube podcast aesthetic, 8K" |
| Cinematic outdoor (festival, golden hour, evening) | "85-135mm telephoto, shallow DOF, slightly low camera angle, sharp subject with soft bokeh background, 8K" |

Always quote the spec verbatim — don't paraphrase as "a portrait lens".
NB2 responds to specific numbers (50mm, f/1.8, ISO levels).

## Block 2 — Lighting (match the register)

- **Daylight indoor**: "natural daylight from window, soft diffused mix of window light + warm [lamp / sconce / candles]"
- **Daylight outdoor**: "soft dappled natural light through tree canopy" / "golden hour rim light" / "overcast soft light"
- **Studio**: "soft key light on face, subtle rim lighting, clean high-key, soft shadows, crisp specular highlights on product"
- **Flash native**: "on-camera flash creating hard shadows and bright highlights, mixed with warm ambient [Christmas tree lights / string lights / candles / lamp]"
- **Cinematic mixed**: "soft dusk light combined with strong cool artificial ambient from [neon / screen / sodium-lamp] — neon creates glowing rim light around hair/shoulders, soft front fill on face"

Specify the QUALITY of light (soft / hard / contrasty), the DIRECTION
(front / rim / side), and the COLOR (warm / cool / neutral). Avoid the
phrase "good lighting" — NB2 doesn't know what that means.

## Block 3 — Skin, anatomy, and hands (always include)

These cues are how you fight uncanny-valley output. Include the relevant
ones in EVERY person-containing prompt:

- **Skin texture**: "visible pores", "natural dewy skin", "hyper-detailed skin textures", "real skin texture", "freckles" / "tan lines" / "natural complexion"
- **No polish**: "no airbrushing", "no plastic skin", "natural complexion not smoothed"
- **Eyes**: "natural eye catchlights" (for portrait/studio), "soft gaze toward camera" or "looking [slightly off / over shoulder]"
- **Hands**: "perfect hands, five fingers each", "natural grip on product", "[NAIL COLOR/STATE — natural / matte / matching brand]"
- **Body**: "accurate anatomy", "natural weight and fabric draping"
- **Mirror reflections** (when applicable): "correct mirror reflection geometry, no distortion"

When the model holds the product: hands must be tight, accurate, with five
fingers. Specify which fingers wrap where if it matters (e.g. "thumb and
index pinching the cap, other three fingers cradling the bottle").

## Block 4 — Composition, mood, and register

Match the brand voice. Pick ONE register per prompt — don't mix.

| Register | Key descriptors |
|---|---|
| **Native UGC** (smartphone feel) | "candid, not posed", "real moment captured", "slightly off-center framing", "subtle natural grain", "feels like a friend's Instagram post" |
| **Influencer lifestyle** | "influencer lifestyle photography aesthetic", "2000s digital camera vibe", "hyper-detailed skin textures", "real-life candid" |
| **Editorial / produced** | "high-end magazine beauty advertising look", "fashion editorial meets authentic", "professional color grading", "8K resolution" |
| **Cinematic** | "cinematic, photorealistic", "dynamic confident pose", "vibrant, youthful, energetic" |
| **Authority / studio** | "professional, confident, friendly expression", "clean cinematic studio atmosphere", "shallow DOF for cinematic depth" |

Whatever the register, the model must do something specific:
- Pose: "standing with back partially facing camera, torso twisted looking over shoulder, weight on one leg" — not "standing naturally"
- Expression: "playful expression, smiling while looking back over their shoulder directly at camera" — not "looking happy"
- Action: "mid-stride", "leaning on armrest", "one arm raised with relaxed hand"

## Block 5 — Negative cues (universal, include in EVERY person prompt)

These belong at the END of the prompt as an explicit "negative prompt" or
"avoid" list. Anthropic-style models honor these strongly:

```
Negative prompt: stiff pose, posed/staged feel, unrealistic body, plastic
skin, smoothed/airbrushed skin, stock-photo energy, uncanny valley, blur on
subject, malformed hands, extra fingers, foreign-language signage, celebrity
look-alikes, AI-generated face artifacts.
```

When the scene is a mirror selfie, add: "no mirror distortion, no reversed text."
When the model holds a product, add: "product label readable, correct text orientation, no warped label."

---

## How this skill is loaded

This file is loaded as system context in `generators/prompt_engine.py:PROMPT_WRITER_SYSTEM`.
Every call to `prompt_from_brief()`, `prompt_from_reference()`, and
`prompt_from_library()` includes these patterns. The Claude prompt-writer
treats Blocks 1-5 as a checklist for any person-containing concept.

When the brief specifies `creative_mechanic` like "UGC Static" or "Talking
Head" or "Lifestyle Hand-Hold", the writer should pick the matching
register from Block 4 and include the corresponding camera/lighting cues
from Blocks 1-2.

When the user provides a `creative_direction` at generation time (via
`--creative-direction` flag or the dashboard's creative-direction field),
that directive is the highest-priority instruction — it overrides any
generic pattern from this skill that contradicts it.
