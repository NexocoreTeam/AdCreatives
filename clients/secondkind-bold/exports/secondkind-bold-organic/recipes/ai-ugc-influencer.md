# AI UGC Influencer

**Output:** video · **Platforms:** TikTok + IG Reels · **Brand-intro:** ~70-80% in · **Skill:** special_vfx

## What this is

Hyperrealistic AI-generated UGC video. One canonical AI avatar (your recurring "character") speaks a short script that **sounds like a real person processing something out loud, not a brand delivering a message.** Same avatar every video = brand recall over time.

The recipe is a 4-tool chain: **Higgsfield (Soul ID + Create Image + Supercomputer) → Claude → ElevenLabs → CapCut**.

## The voice rule (CRITICAL, this is what makes it organic vs. ad-y)

Scripts for this recipe **must avoid the classic UGC ad arc** (problem → diagnosis → solution → result). That structure reads as "ad" instantly and gets scrolled. Real people don't post their health journeys with that arc on their personal feeds.

### Required pattern

- **Drop into mid-thought, no headline hook.** Open with *"Okay this is going to sound stupid but..."*, *"I don't know if I'm allowed to say this but..."*, *"So I went to my doctor on Tuesday and..."*, never a polished opening line.
- **Use casual filler language.** *Like, just, kind of, anyway, okay so, honestly, I don't know.* These are what makes speech sound unwritten.
- **Self-deprecation works.** *"This is going to sound dumb,"* *"I don't even know,"* *"this might be nothing."*
- **Brand/product mentioned ONCE, incidentally.** Not as a climax. Just as a thing that happens to be in her life, *"bottle's in my cabinet now"*, not *"so I switched to [brand]"*.
- **End on uncertainty, never on results.** *"I'll see what happens,"* *"that's the update,"* *"anyway, idk."*, never *"two weeks in, my bloating is gone"*.

### Forbidden patterns

- Three-act ad structure (problem → diagnosis → solution → result)
- Testimonial closer (*"X weeks in, I felt amazing"*, *"my life changed"*)
- Brand named more than once in a script
- Polished thesis statements (*"Here's what nobody tells you..."*)
- Direct address to camera audience (*"Listen, ladies..."*, *"You're going to want to hear this..."*)
- A clean opening hook (the first line should feel mid-conversation)

The goal: **someone scrolling shouldn't be sure if this is content or just a friend venting.** That ambiguity is the whole point.

## When to use it

- Personas where UGC voice/style is the right register but existing UGC doesn't fit the new pain
- Replacing hiring UGC creators when the matrix has many pain variants
- Building brand recall through a consistent recurring "character"

⚠️ **VA must have the 4-tool chain working.** If any tool is missing, fall back to `text-overlay-monologue` (same script, no AI face).

## The canonical avatar, set up ONCE per brand

Before producing ANY video with this recipe, set up a canonical AI avatar that lives in the preset folder. Use the same avatar across ALL episodes for built-in recall.

**Do NOT generate a new avatar per video.** That kills the recall mechanism.

### Avatar generation (one-time setup)

We use **Higgsfield Soul ID**, Higgsfield's reusable AI-character feature. Soul ID creates a persistent character that maintains identity across every generation.

1. Go to **Higgsfield** (https://higgsfield.ai)
2. Open **Soul ID** (the "Characters" feature)
3. Create a new Soul ID with this prompt:

> "A woman, late 30s/early 40s, brown hair pulled back loosely, no makeup, in a natural-lit kitchen or bedroom, wearing a cream cardigan over a simple top. She should look health-conscious but slightly exhausted, like someone who's tried everything for her gut health. Photographed on iPhone, natural soft light from a window, candid composition like a real moment not a posed photoshoot. Don't make her look glamorous or like a model, she's the kind of person who lurks in supplement subreddits at 11pm. 9:16 vertical."

4. Generate, iterate 2-3 times until the result feels like a real Danielle-archetype (not a model, not glamorous, slightly tired)
5. **Save the Soul ID as "SK-Bold Canonical Avatar"**, reusable across all future generations
6. Also download the reference image as `sk-bold-canonical-avatar.png` and save to `avatars/` in this preset folder
7. **From now on, every AI UGC video uses this exact Soul ID.**

## The 4-step production workflow (per video)

### Step 1: Pick the matrix entry + write the script

1. Open `matrix.md`, pick a pain/love/wish/hook entry
2. Open Claude and paste:

> "I have this matrix entry: [paste relevant section from matrix.md]
>
> Brand: SecondKind Bold (postbiotic gut-health). Tagline: 'We don't sell bacteria.'
>
> Write me 3 unique UGC script options for an AI influencer video (40-60 seconds each). My avatar: women who've tried multiple probiotics with no results. Each script MUST:
> - Open mid-thought with a self-deprecating or vulnerable line (never a polished headline hook)
> - Use casual filler language (like, just, kind of, anyway, okay so)
> - Sound like she's processing something out loud, not delivering a brand message
> - Mention the brand/product ONCE, incidentally, not as a climax
> - End on uncertainty (*'I'll see what happens'*, *'anyway, that's the update'*), NEVER on a results testimonial
> - No 3-act ad structure. No thesis statements. No 'Here's what nobody tells you'.
> - Format the output as Scene 1, Scene 2, etc. with a visual description per scene"

3. Pick the strongest script

### Step 2: Generate the scenes in Higgsfield

For each scene in the script:

1. Go to **Higgsfield → Create Image**
2. Select your **SK-Bold Canonical Avatar Soul ID**
3. Paste the scene description, prefixed with: *"Generate a 9:16 image of [Soul ID character] where she's [scene description]. Same lighting tone as the canonical reference."*
4. Generate. Repeat for each scene (typically 4-6 scenes per script).

Tips:
- Soul ID handles character consistency automatically
- Keep ONE casual setting across the whole video if possible (car, bedroom, kitchen), not a transformation arc across multiple locations
- Variations in expression are fine; the Soul ID locks the face/hair/outfit
- If a scene drifts off-tone, regenerate that scene only

### Step 3: Generate the video in Higgsfield Supercomputer

1. Go to **Higgsfield → Supercomputer**
2. Drop in all your generated scene images
3. For each scene, paste the corresponding script line + select the scene image
4. At the top, prompt: *"Create a 9:16 UGC video. Use the full script. Pace it conversationally, like she's just talking, with natural pauses."*
5. Generate

### Step 4: Voice + edit

1. **ElevenLabs:** female 30-40, conversational, *"thinking aloud, slightly tired, not broadcasting"*. Re-generate if it sounds polished or like a radio host.
2. **CapCut:** assemble clips in script order, replace any Higgsfield-generated voice with ElevenLabs, add auto-captions, light ambient music (or no music, silence reads as more organic), export 9:16

## Worked example, Danielle bloating brief (organic voice)

**Matrix entry:** `pain-001`, probiotic efficacy plateaus
**Canonical avatar:** `avatars/sk-bold-canonical-avatar.png`

### The script (~45 seconds, 5 scenes, organic register)

**Scene 1 (0-10s):**
> *"Okay this is going to sound stupid but I went to my gut doctor on Tuesday and he said something I can't stop thinking about."*

**Scene 2 (10-20s):**
> *"I've been on probiotics for like three years. Different brands. The expensive ones. The ones every gut influencer swears by."*

**Scene 3 (20-32s):**
> *"And he just casually goes, 'you know most of that bacteria is dead before it ever reaches your gut, right?' And I'm sitting there like, what."*

**Scene 4 (32-42s), BRAND INTRO (~78% in, incidental):**
> *"He said the whole live-bacteria thing kind of misses the point. There's another category called postbiotics. Bottle's in my cabinet now."*

**Scene 5 (42-48s):**
> *"I don't know. I'll see what happens. Anyway. That's the update."*

### Why this is the organic voice (compared to the ad-y version)

- **No headline hook.** *"Okay this is going to sound stupid but..."* drops into mid-thought.
- **Filler language.** *Like, kind of, just, anyway, I don't know*, these signal unscripted.
- **The brand barely registers.** *"Bottle's in my cabinet now"*, no name, no pitch, no climax. Just a casual mention. SK Bold's label appears in the visual; that's enough.
- **Self-deprecation throughout.** *"This is going to sound stupid"*, *"I don't know"*. Real posters do this constantly.
- **Ends on uncertainty.** *"I'll see what happens"*, not *"two weeks in I felt amazing"*. No results claim.

### Higgsfield prompts per scene (using SK-Bold Soul ID)

Pick ONE setting and stay there across all 5 scenes. Suggested: bedroom floor, late afternoon, soft window light.

```
Scene 1:
"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16: she's sitting
on her bedroom floor against a bed, hair up, slightly tired expression, soft
afternoon light. No text overlays, no captions."

Scene 2:
"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16: same setting,
same outfit, she's gesturing with one hand explaining, soft afternoon light.
No text overlays, no captions."

Scene 3:
"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16: same setting,
she's looking off-camera mid-thought, hand to face, slightly incredulous
expression. No text overlays, no captions."

Scene 4:
"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16: same setting,
she's holding a Gut Balance amber glass jar in one hand at chest level, looking
at it briefly while talking, soft afternoon light. No text overlays, no
captions. The Gut Balance label is the only text in the image."

Scene 5:
"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16: same setting,
she's shrugging slightly, casual relaxed posture, looking back at the camera,
soft afternoon light. No text overlays, no captions."
```

### Rule check

- **Voice:** organic, processing out loud ✓
- **No 3-act ad structure** ✓ (no problem-solution-result arc)
- **Brand mentioned once, incidentally** ✓ (Scene 4 only, no brand name spoken)
- **Ends on uncertainty** ✓ (*"I'll see what happens. Anyway."*)
- **Casual fillers throughout** ✓
- **No prohibited words** (no *miracle, journey, transform, holistic*) ✓
- **Brand-intro at ~78%** ✓ (Scene 4 of 5)
- **No CTA** ✓
- **Same canonical avatar** ✓
- **One setting throughout** ✓ (bedroom floor, not a transformation arc)

### Pitfalls, read these before scripting

- **Avatar drifts across scenes**, use higher Soul ID match weight, or regenerate the off-scene only
- **Voice sounds polished/broadcast**, direct ElevenLabs to "thinking aloud, slightly tired" and regenerate if it sounds clean
- **Script slips into ad arc**, if you find yourself writing "so I switched to..." or "[X] weeks in..." stop and rewrite. Those phrases are signals you've drifted into ad-mode.
- **Transformation visuals**, pick ONE setting. Don't have her go from "kitchen tired" to "kitchen calm", that's the testimonial visual cliché. Same posture, same light, same place.
- **Brand named more than once**, if "SecondKind" or "Gut Balance" appears more than once in the script, cut. The product label in the visual carries the brand.

## Why this recipe matters

This is the only recipe in the catalog that produces a hyperrealistic "person speaking" video. Other recipes use text overlays, animations, or existing UGC. AI UGC influencer is what you reach for when:

- The matrix entry needs a personal emotional register (someone processing, someone confessing, someone musing)
- Existing UGC library doesn't have footage that fits
- You want to scale UGC-style content without hiring creators every time

When deployed across a series with one consistent canonical avatar AND the organic voice rules, this builds the strongest brand recall in the catalog. The same face. Different musings. Never an ad.
