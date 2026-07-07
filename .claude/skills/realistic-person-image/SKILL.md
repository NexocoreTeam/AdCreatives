---
name: realistic-person-image
description: >
  Generate AI images of people that do not read as AI-generated. Use whenever a
  generated image will contain a person, model, or human face: ad creatives,
  landing page heroes, advertorial/article images, website imagery, UGC-style
  photos, testimonial portraits. Trigger on "not look AI", "looks too AI",
  "realistic person", "like a real photo", "stock-like but real", or any
  human-in-frame image generation for any client. Validated end-to-end
  2026-07-07 on the SecondKind landing hero (10+ generation iterations).
---

# Realistic Person Image

People images fail as "AI" for two reasons: the model's beauty/polish prior, and
the pristine-file fingerprint. This skill beats both. It is the default process
for ANY generated image containing a person, for ads and website imagery alike.

## Step 1: pick the register with the operator

| Register | Looks like | When |
|---|---|---|
| A. Camera-roll | unedited phone photo, family album | UGC-style, maximum authenticity |
| B. Editorial | photo beside a newspaper health article | advertorials, blog/article pages |
| C. Commercial-clean | premium publication, styled set, real human | landing heroes, brand pages |

Operators often ask for A, then walk it back to B or C once they see results.
Generate the current register plus one neighbor when in doubt.

## Step 2: model routing (Higgsfield CLI, validated)

- **Base human (register A, and the seed for B/C):** `text2image_soul_v2`,
  no soul-id needed. Soul V2 is the anti-polish model.
- **Register upgrades and set swaps that keep the same person:**
  `nano_banana_2` with the approved photo as `--image` reference. NB is the
  only validated reference-faithful model.
- **NEVER** feed a Soul output back into Soul as `--image` reference: it copies
  the composition but swaps in a default early-20s model face.
- NB text-only stays editorial-polished no matter the prompt; do not fight it
  for register A.

```bash
echo "<prompt>" | higgsfield generate create text2image_soul_v2 --aspect_ratio 3:2 --quality 2k --wait --json
echo "<prompt>" | higgsfield generate create nano_banana_2 --image <approved.png> --aspect_ratio 3:2 --wait --json
```

Auth: `higgsfield auth login` is a browser device login. Run it in background
Bash, hand the operator the printed device URL, continue when it completes.

## Step 3: prompt levers (all registers)

- **Terse plain sentences, not JSON.** Long structured prompts read as
  set-dressing; the model arranges props like a stylist.
- **Describe an existing photo; never instruct.** No negative-list walls, no
  "absolutely no X" stacks. Write it like a caption.
- **Banned words:** photorealistic, 8K, HDR, masterpiece, hyper-detailed.
- **Mediocrity anchor (A, soften for B):** "an unremarkable amateur photo...
  boring and real, not an advertisement, not a stock photo."
- **Provenance anchor:** camera roll (A), "photograph accompanying a serious
  health article / for a premium health publication" (B/C).
- **Capture flaws (A; keep only grain + "no retouching" for B/C):** slightly
  tilted framing, too much empty foreground, window blown out, mixed white
  balance, mild noise, flat muted colors, zero retouching.
- **Action, not pose** ("too foggy to start the day" beats "sitting sadly").
- **Subject unaware of camera** unless eye contact is an explicit choice.
- **One off-topic prop** (stray charging cable) sells realism; three themed
  props read as staging.
- **Age dial skews young:** say "early 50s" to render a late-40s face.
- **Always pin wardrobe explicitly.** Soul V2 with de-glam language and no
  outfit stated can render the subject undressed.
- Real skin line that works: "natural unretouched skin with visible texture
  and tiredness under her eyes, minimal makeup."

## Step 4: identity-preserving re-shoots (the two-step)

To upgrade register or swap the set while keeping the approved person, prompt
NB2 with the approved image as reference, opener verbatim:

> "Take the exact same woman from the reference photo: same face, same soft
> features, same age around 40, same [hair], same [wardrobe], same pose with
> [pose]. Re-photograph her in [new setting / register]..."

Close with: "Still a real photograph, not glossy advertising, no beauty
retouching."

## Step 5: de-AI post pass (mandatory, every image)

```bash
python scripts/deai_post.py <image.png> [...]
```

Downscales to 1600px, softens synthetic micro-sharpness, flattens contrast,
adds luminance-weighted grain, re-encodes JPEG q85. **Ship the `-web.jpg`,
never the raw PNG.** A pristine 2.5K PNG is itself an AI tell.

## Known failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Young model-pretty face | Soul+ref, or age stated literally | NB for refs; age +8 years |
| Subject undressed | Soul de-glam without wardrobe pin | always state the outfit |
| Black letterbox strips | NB with reference sometimes adds them | 3-4% inset crop, re-run post pass |
| Perfectly arranged props | too many themed props listed | max 2-3 objects, one off-topic |
| Still glossy on NB | fighting NB's prior for register A | switch to Soul V2 |

## Generality

The Step 3 levers and Step 5 post pass are model-agnostic (they work on GPT
Image, Gemini/Nano Banana anywhere, etc.). The Step 2 routing is
Higgsfield-validated as of 2026-07-07; re-validate routing before assuming it
for other providers.

Worked example with full prompt history and operator decisions:
`clients/secondkind-bold/landing-page/hero-image-prompts.md`
