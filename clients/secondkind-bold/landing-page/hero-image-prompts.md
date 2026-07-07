# SK / Inside Health Report landing hero: "brain fog at the kitchen table"

Hero image under the headline "Scientists Discover Midlife Brain Fog May Start in the Gut, Not the Brain" on insidehealthreport.com. Goal: reads as a real photo, not AI, not stock.

## Winning recipe

- Model: **Higgsfield Soul V2** (`text2image_soul_v2`), no soul-id needed
- Command: `echo "<prompt>" | higgsfield generate create text2image_soul_v2 --aspect_ratio 3:2 --quality 2k --wait --json`
- Prompt style: short plain sentences, NOT structured JSON
- Core levers: "unremarkable amateur photo" mediocrity anchor, named capture flaws (tilted framing, blown-out window, flat colors, mild noise, zero retouching), provenance anchor ("family camera roll, not an advertisement, not a stock photo"), subject unaware of camera, one off-topic prop (charging cable)
- What failed: Nano Banana Pro (any prompt) stays editorial-polished; long JSON prompts invite set-dressing; "candid/natural" adjectives alone do nothing

## Candidates (hf-output/sk-landing-hero/)

### v4-soul-flash.png (strongest emotional match)

> A candid flash photo taken on an old phone in a dim kitchen early in the morning: a tired woman in her early 50s slumped at the kitchen table, head propped on one hand with her fingers in her grey-streaked hair, eyes down toward the full mug of coffee that has gone cold in front of her, not looking at the camera. Phone face down on the table next to a stray charging cable. Harsh direct flash against the dark room, slight shadow behind her, last night's dishes by the sink. Rumpled cardigan over an old t-shirt, no makeup, real mature skin with tired lines around her eyes. Slightly awkward framing, flat colors, mild noise, zero retouching. Looks like an ordinary photo from a family camera roll, boring and real, not an advertisement, not a stock photo.

### v4-soul-daylight.png (gentler, window gaze, reads slightly older)

> An unremarkable amateur photo of a worn-out woman in her early 50s sitting alone at her kitchen table early on a grey weekday morning. She has not noticed the camera; she is turned mostly away in three-quarter view, chin propped on one hand, staring toward the window at nothing. A full mug of coffee gone cold sits in front of her next to her phone lying face down and a stray charging cable. Kitchen lights off, dim grey window light only, no flash. Last night's dishes by the sink. Rumpled cardigan, no makeup, grey-streaked hair pulled back carelessly, real skin texture, tired lines around her eyes. Framing a little off with too much empty table in the foreground, window slightly blown out, flat muted colors, mild noise, zero retouching. Boring and real, like a photo from a family camera roll, not an advertisement, not a stock photo.

### v3-soul-terse.png (baseline: real texture but too young, eye contact)

Prompt: hero-image-prompt-terse.txt as of v3 (woman read mid-30s, looked into lens).

### v3-nanobanana-json.png (right subject, too polished; editorial-stock look)

Prompt: hero-image-prompt.json on `nano_banana_2`, 3:2. Keep only if a cleaner look is wanted.

## v6: the "article editorial" register (CURRENT DIRECTION)

Operator verdict on v3/v4: real but too organic; wants "photo that runs in an article, almost stock, but not AI ad," keeping the v3 woman.

**Winning two-step recipe:**

1. Generate a real-looking base photo on Soul V2 (v3-soul-terse.png).
2. Re-shoot it on **Nano Banana 2 with the Soul photo as `--image` reference** and an editorial prompt. NB keeps the woman's identity and the scene's realism cues while lifting light and composition to editorial. Prompt opener that works: "Take the exact same woman from the reference photo: same face, same soft features, same age around 40, same shoulder-length brown hair with a little grey showing at the part, same grey knit cardigan. Re-photograph her for a newspaper health article about brain fog in women over 40..." then scene + "Keep her skin completely unretouched with real texture... Muted natural colors, gentle contrast, faint grain, documentary editorial photography like a newspaper health feature. Absolutely not glossy, not an advertisement, no beauty retouching."

Results: **v6-nb-ref-gazedown.png** (eyes lowered, safest article look) and **v6-nb-ref-eyecontact.png** (flat worn eye contact, closest to the v3 energy the operator liked).

**Failure modes learned:**

- Soul V2 + `--image` ref of its own output: copies composition literally but swaps in a default early-20s model face. Do not use for identity.
- Soul V2 text-only with heavy de-glam language: dropped the wardrobe entirely (subject rendered undressed). Always pin clothing explicitly on Soul.

## v7: commercial setting upgrade (operator approved gazedown, wanted a high-quality kitchen)

Same two-step recipe, but reference = **v6-nb-ref-gazedown.png** (the approved shot) and the prompt keeps woman + pose pinned while swapping the set: "Re-photograph her in a [bright high-end modern kitchen: white shaker cabinets, light quartz countertops... / warm upscale kitchen: cream cabinets with brass handles, marble island, eucalyptus... / airy minimal kitchen: pale wood, large bright window...]" + the same "gently commercial editorial photography for a premium health publication... still a real photograph, not glossy advertising" register block. Results: v7-kitchen-white, v7-kitchen-warm (needed a 3% crop, NB added letterbox strips), v7-kitchen-airy.

## De-AI post pass (always run before upload)

Raw model output is a pristine 2.5K PNG, which is itself an AI tell. Run:

`python scripts/deai_post.py hf-output/sk-landing-hero/<file>.png`

Writes `<file>-web.jpg`: downscale to 1600px, 0.4px softening of synthetic edges, slight desaturation and black lift, luminance-weighted grain (stronger in shadows), JPEG q85. Upload the `-web.jpg`, never the PNG.

## Tuning notes for next variants

- Age dial: "late 40s" reads about 35 on Soul; "early 50s" lands as 48 to 55. Say "early 50s" to hit the over-40 reader.
- Gaze: never "at the camera." Either eyes down at the coffee (flash version) or out the window (daylight version).
- Mobile crop: 3:2 masters keep her center-left; safe to crop 4:5 around subject plus mug.
