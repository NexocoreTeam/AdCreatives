# Recipe Production Steps, All 10 Recipes

The exact tools, prompts, and steps required to produce a piece of content for each of the 10 recipes. Open this when you need a step-by-step walkthrough.

**How the pattern works for every recipe:**

1. You ask Claude → Claude returns copy + Higgsfield prompts + workflow
2. You paste Higgsfield prompts → generate images / video
3. You add text manually in CapCut / Canva (Claude already gave you the text)
4. You post

The skill never makes the actual images. It tells you exactly what to paste where.

---

## Quick reference, all 10 at a glance

| # | Recipe | Tools required |
|---|---|---|
| 1 | `text-overlay-monologue` (Love Letter) | Claude, Higgsfield, CapCut |
| 2 | `text-overlay-pov` (POV Short) | Claude, Higgsfield, CapCut |
| 3 | `david-goliath-no-intro` (video) | Claude, founder footage, Higgsfield, ElevenLabs, CapCut |
| 3 | `david-goliath-no-intro` (carousel) | Claude, Canva |
| 4 | `pixar-ai-slop` | Claude, Higgsfield (animation), ElevenLabs, CapCut · ⚠️ VFX skill |
| 5 | `not-x-objection` | Claude, Canva (+ optional Higgsfield) |
| 6 | `ugc-cutup-voiceover` | Claude, existing UGC library, ElevenLabs, CapCut |
| 7a | `static-educational-card` (IG editorial) | Claude, Canva |
| 7b | `static-educational-card` (TikTok native) | Claude, Higgsfield, CapCut |
| 8 | `native-ai-product-shot` | Claude, Higgsfield Product Photoshoot |
| 9 | `ai-ugc-influencer` | Claude, Higgsfield Soul ID + Supercomputer, ElevenLabs, CapCut · ⚠️ VFX skill |
| 10 | `engagement-prompt` | Claude, Canva OR native IG/TikTok app |

---

## 1. text-overlay-monologue (TikTok Love Letter)

**Output:** Video · **Platforms:** TikTok + IG Reels · **Lift:** low

### Tools
- **Claude Code**, script + Higgsfield prompts
- **Higgsfield** (Create Image), silent B-roll
- **CapCut**, assemble + add text overlay

### Steps

**1. Get the script + prompts from Claude**
- Open Claude Code
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use text-overlay-monologue.`
- Claude returns: a 35-75 word, 3-beat love letter (callout + hedged fact, emoji-led "supports" lines, product + effortless close) + 3-4 Higgsfield prompts for B-roll

**2. Generate B-roll in Higgsfield**
- Go to https://higgsfield.ai → Create Image
- Paste each prompt one at a time (each starts `"Shot on iPhone, candid"`, ends with no-text clause)
- Generate 9:16 vertical, download
- Tip: generate all in one session for visual tone consistency. Avoid any prompt with faces, text is the focal point

**3. Assemble in CapCut**
- Drop B-roll clips in timeline order
- Add the monologue as text overlay, reveal one line at a time
- Text is the hero: large, readable, centered
- Add minimal ambient music (drop volume under brand-reveal line)
- Export 9:16

---

## 2. text-overlay-pov (TikTok POV Short)

**Output:** ~5-second video · **Platforms:** TikTok + IG Reels · **Lift:** very_low

### Tools
- **Claude Code**
- **Higgsfield** (Create Image, anchor + variation)
- **CapCut**

### Steps

**1. Get the POV line + prompts**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use text-overlay-pov.`
- Claude returns: a 1-2 line flex/POV (from the line bank or your own-feed harvest) + visual plan: single candid-motion clip OR 1 anchor prompt + 3-5 variation prompts

**2. Generate the ANCHOR shot in Higgsfield**
- Higgsfield → Create Image
- Paste the anchor prompt (locked camera frame, kitchen/mirror/desk setting)
- Generate 9:16, download, this is your reference image

**3. Generate VARIATION cuts**
- For each variation prompt:
 - Drag the anchor image into Higgsfield as a reference
 - Paste the variation prompt (each describes ONE element changing, outfit, bottle, date)
 - Generate, download
- End with 4-5 cut images that share the same frame

**4. Assemble in CapCut**
- Drop cuts in sequence, ~1 second each
- Add the POV text overlay LOCKED across all cuts (text never moves)
- Export 9:16

### Critical
Static clip + text = boring. Anchor + variation = scroll-stop. The visual change across cuts IS the format.

---

## 3. david-goliath-no-intro

Two paths, **video** if you have founder footage, **carousel** if you don't.

### 3A. Video version

**Output:** Video (60-90s) · **Lift:** medium

#### Tools
- **Claude Code**, script
- **Agency UGC library**, founder talking-head + anti-category footage
- **Higgsfield**, any missing B-roll
- **ElevenLabs**, VO if founder voice unavailable
- **CapCut**, assemble

#### Steps

**1. Get the script**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use david-goliath-no-intro, video version.`
- Claude returns: 60-90s VO script in 7-8 beats, brand intro at ~70%, list of needed B-roll

**2. Pull existing founder + category footage**
- Search the agency library
- Identify clips matching the script beats

**3. Generate missing B-roll in Higgsfield**
- Paste any Higgsfield prompts Claude provided
- Generate 9:16, download

**4. Voiceover**
- If founder voice available: record directly OR use existing founder audio
- If not: paste script into ElevenLabs, pick matching tone

**5. Assemble in CapCut**
- Drop founder talking head + B-roll cutaways in script order
- Layer VO
- The brand does NOT appear (visually OR in script) until ~70% mark
- Export 9:16

### 3B. Carousel version (no footage needed)

**Output:** 7-slide IG carousel · **Lift:** medium

#### Tools
- **Claude Code**
- **Canva**

#### Steps

**1. Get the carousel copy**
- Paste: `...Use david-goliath-no-intro, carousel version.`
- Claude returns: 7 slides of copy, brand reveal slide 7

**2. Design in Canva**
- "IG Carousel" brand template, 7 frames
- Slide 1: indictment headline (no brand)
- Slides 2-6: build the case against the category
- Slide 7: brand reveal, SK wordmark + 1-line resolution
- Caslon Condensed headlines, Neue Montreal body
- Export 7 × 1080×1080 PNGs

---

## 4. pixar-ai-slop

**Output:** Video (30-60s) OR static image set · **Lift:** medium

⚠️ **Requires AI animation skill.** Don't attempt without practice.

### Tools
- **Claude Code**, script
- **Higgsfield** (animation mode), OR Runway / Pika
- **ElevenLabs**, cartoon character voices
- **CapCut**, edit

### Steps

**ONE-TIME setup: build the character set**
- Generate recurring AI cartoon characters (e.g. "Pro" + "Biotic" + "Posty")
- Save references for reuse, these are your recurring cast (Sarah's rule 1)
- Don't generate new characters per episode

**Per episode:**

**1. Get the script from Claude**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use pixar-ai-slop.`
- Claude returns: 4-scene animated script + character actions per scene

**2. Generate animation scenes in Higgsfield**
- Use saved character references
- Paste each scene prompt with character actions
- Generate animated clips per scene, 9:16

**3. Voice the characters in ElevenLabs**
- Different cartoonish voice per character
- Generate dialogue lines per scene

**4. Assemble in CapCut**
- Cut scenes together
- Add VO + sound effects (whooshes, dings)
- Export 9:16

### Important
Reuse the SAME characters across every episode. New characters per video = no recall. Same characters across many videos = the recall engine.

---

## 5. not-x-objection ("We're not [X]")

**Output:** Static image (or short video) · **Platforms:** IG + TikTok · **Lift:** very_low

### Tools
- **Claude Code**
- **Higgsfield** (Create Image, phone-snap background)
- **Canva** (brand template + text overlay)

### Default workflow, phone-snap background

**1. Get the copy + Higgsfield prompt from Claude**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use not-x-objection.`
- Claude returns: 1 headline (the "We're not [X]" line) + 3 body lines + Higgsfield prompt for a phone-snap background

**2. Generate background in Higgsfield**
- Higgsfield → Create Image
- Paste the prompt (starts `"Shot on iPhone, candid"`, ends with no-text clause)
- Background examples Claude rotates: kitchen counter at morning, bathroom counter, nightstand, open journal on desk, all with large negative space for text
- Generate 1:1 aspect, download

**3. Design in Canva**
- Open "IG Square Native" template
- Drop the phone-snap background as the base layer
- Drop headline (Caslon Condensed, large) in the photo's negative-space area
- Drop 3 body lines (Neue Montreal, smaller) below the headline
- Single yellow (#fcb348) accent on the mechanism word
- SK wordmark bottom-right corner. **No CTA.**
- Export 1080×1080 PNG

### Occasional alternative, Snow White editorial

Use ~1 in 4 posts, for brand announcements / press moments / when text density is high.

**1. Get the copy**, same as above
**2. Skip Higgsfield**
**3. Design in Canva "IG Square Editorial"**
- Snow White (#fefcf6) background
- Same Caslon + Neue Montreal type treatment
- Single yellow accent, SK wordmark bottom-right

### TikTok slideshow alternative

- Same 3-5 lines, each as a slide
- Generate AI phone-snap background per slide in Higgsfield (9:16 vertical)
- Add text in CapCut using **system font** (NOT brand serifs)
- Export as slideshow

---

## 6. ugc-cutup-voiceover

**Output:** Video (60-90s) · **Platforms:** TikTok + IG Reels · **Lift:** low

### Tools
- **Claude Code**, script
- **Agency UGC library**, existing creator footage
- **ElevenLabs**, AI voiceover
- **CapCut**, edit

⚠️ Requires existing UGC. If none, use `text-overlay-monologue` instead.

### Steps

**1. Get the VO script + footage requirements**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use ugc-cutup-voiceover.`
- Claude returns: 60-90s VO script + list of B-roll types you need (e.g. "morning routine," "kitchen counter," "hands closing laptop")

**2. Pull matching UGC from the library**
- Search for clips matching the mood/setting
- Pick clips where the creator's FACE/MOUTH is NOT visible (use hands, body, settings)
- Mood mismatch = bad output, don't use gym footage for sleep pain
- Strip audio from each clip

**3. Generate AI voiceover in ElevenLabs**
- Voice: female 30-40, warm but tired, conversational
- Direction: *"conversational, thinking aloud, not broadcast-perfect"*
- Paste full VO script, generate
- Listen back, regenerate if too polished

**4. Assemble in CapCut**
- Drop silent UGC clips in script order
- Layer AI VO on top
- Add minimal ambient music (drop volume under brand reveal)
- Auto-generate captions, verify
- Brand intro at mid-to-late mark (~60-75%)
- Export 9:16

### Important
No Higgsfield needed, this recipe uses EXISTING UGC. The creator becomes anonymous lifestyle B-roll. Don't show their face during the emotional voice beats, visible speech mouth movement will conflict with the AI VO.

---

## 7. static-educational-card

Two variants, same script, different production. Pick based on platform.

### 7A. IG variant, default is phone-snap backgrounds per slide

**Output:** 6-slide IG carousel · **Platform:** Instagram · **Lift:** very_low

#### Tools
- **Claude Code**
- **Higgsfield** (Create Image, 6 phone-snap backgrounds)
- **Canva** (text overlay using brand typography)

#### Steps

**1. Get the slide copy + 6 Higgsfield prompts**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use static-educational-card, IG variant.`
- Claude returns: 6 slide texts + 6 Higgsfield prompts for phone-snap backgrounds per slide

**2. Generate 6 phone-snap backgrounds in Higgsfield**
- Each prompt starts `"Shot on iPhone, candid"`, ends with no-text clause
- Generate 1:1 aspect (or whatever Claude specifies), download
- Each has negative-space area for text overlay

**3. Design in Canva**
- "IG Carousel Native" template, 6 frames
- Drop each phone-snap background as base layer per slide
- Drop slide copy (Caslon Condensed headline + Neue Montreal body) in the negative-space area of each photo
- Single yellow accent on key mechanism words (stomach acid, bile salts, postbiotics)
- Slide 6: brand reveal (SK wordmark in clear corner area, no CTA)
- Export 6 × 1080×1080 PNGs

**4. Upload as carousel**

#### IG editorial alternative (Snow White, occasional)

Use ~1 in 4 carousels, when text density is too high for legible photo overlay or for premium-feel moments.

- Skip Higgsfield
- Canva "IG Carousel Editorial" template
- Snow White (#fefcf6) backgrounds
- Same Caslon + Neue Montreal + yellow accent

### 7B. TikTok native variant (phone-snap feel)

**Output:** 6-slide TikTok slideshow OR video · **Platforms:** TikTok + IG Reels slideshow · **Lift:** very_low

#### Tools
- **Claude Code**
- **Higgsfield** (Create Image, phone-snap backgrounds)
- **CapCut** (or TikTok app) for text overlays

#### Steps

**1. Get the slide copy + Higgsfield prompts**
- Paste: `...Use static-educational-card, TikTok native variant.`
- Claude returns: 6 slide texts + 6 Higgsfield prompts for backgrounds

**2. Generate 6 phone-snap backgrounds in Higgsfield**
- Paste each prompt (starts `"Shot on iPhone, candid"`, ends with no-text clause)
- Generate 9:16 vertical, download

**3. Add text in CapCut**
- Drop 6 background images in order
- Add slide text using **system font** (Helvetica or similar), **NOT** brand Caslon
- White text on dark, black on light
- Export as slideshow OR carousel video

### Critical
TikTok variant uses SYSTEM font, not brand serifs. Brand-typography on TikTok reads as "ad" → gets scrolled.

---

## 8. native-ai-product-shot

**Output:** Single image OR carousel · **Platforms:** IG + TikTok slideshow · **Lift:** very_low

### Tools
- **Claude Code**
- **Higgsfield Product Photoshoot**
- **IG / TikTok app** for native captions

### Steps

**1. Get prompts + captions**
- Paste: `Use secondkind-bold-organic. Use native-ai-product-shot.`
- Claude returns: 1-5 Higgsfield prompts (depending on single or carousel) + 1-line native captions

**2. Generate product photos in Higgsfield Product Photoshoot**
- Use Higgsfield's dedicated Product Photoshoot mode (if available)
- Drop in your reference photo of the Gut Balance bottle
- Paste each prompt (`"Shot on iPhone, candid"` + setting + no-text clause)
- Generate 1:1 (IG single) or 9:16 (TikTok slideshow)
- Generate 3-4 variations per scene, pick the most "found"-looking one
- Reject anything that looks art-directed

**3. Post with native caption**
- Upload to IG or TikTok directly
- Caption: 1-line, casual, no emojis, no hashtags
- Post

### No design tool needed
The caption goes in the post directly. The image IS the design.

**Sample captions Claude provides:**
- *the only thing I added this month*
- *forgot what 7pm felt like without bloat. this is why.*
- *day 30. unbothered.*

---

## 9. ai-ugc-influencer

**Output:** Video (30-60s) · **Platforms:** TikTok + IG Reels · **Lift:** medium

⚠️ Requires the 4-tool chain working. If any tool unavailable, fall back to `text-overlay-monologue`.

### Tools
- **Higgsfield** (Soul ID + Create Image + Supercomputer)
- **Claude Code**, script
- **ElevenLabs**, voice
- **CapCut**, edit

### ONE-TIME SETUP, Create the SK-Bold Canonical Avatar Soul ID

1. Go to **Higgsfield** → **Soul ID** (Higgsfield's reusable AI-character feature)
2. Open `recipes/ai-ugc-influencer.md` and copy the canonical avatar prompt
3. Paste into Soul ID, generate
4. Iterate 2-3 times until she feels right (late-30s woman, no makeup, kitchen-y, slightly exhausted, **NOT** glamorous)
5. **Save as "SK-Bold Canonical Avatar"**, this Soul ID is reusable for every future AI UGC video
6. Also download the reference image to `avatars/sk-bold-canonical-avatar.png`

From now on, every AI UGC video uses this same Soul ID. Higgsfield maintains character consistency across scenes automatically.

### Per-video workflow

**1. Get the script from Claude**
- Paste: `Use secondkind-bold-organic. Pull pain-XXX. Use ai-ugc-influencer.`
- Claude returns: 4-6 scene script with timestamps + Higgsfield prompts per scene + brand-intro position

**2. Generate 4-6 scene images in Higgsfield Create Image**
- Select your saved **SK-Bold Canonical Avatar Soul ID**
- For each scene, paste the prompt (starts `"SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid..."`)
- Generate 9:16 vertical
- Soul ID handles character consistency automatically, face/hair/cardigan stay the same

**3. Generate video with mouth-sync in Higgsfield Supercomputer**
- Go to **Higgsfield → Supercomputer**
- Drop all 4-6 scene images
- For each scene, paste the corresponding script line + select the scene image
- At top: *"Create a 9:16 UGC video. Use the full script. Pace it naturally, not rushed."*
- Generate (runs in background)

**4. Voice in ElevenLabs**
- Voice: female 30-40, conversational, "thinking aloud"
- Paste full script, generate
- Listen back, re-generate if too polished

**5. Assemble in CapCut**
- Drop video clips in script order
- Replace Higgsfield's generated voice with your ElevenLabs voice
- Auto-generate captions, verify
- Minimal ambient pad music, drop volume under brand-reveal scene
- Export 9:16

### Important
- Same Soul ID across every SK-Bold AI UGC video = brand recall
- New avatar per video = recall destroyed
- If a scene drifts, regenerate that scene with higher Soul ID match weight

---

## 10. engagement-prompt

**Output:** Image / carousel / native poll · **Platforms:** IG (post, story) + TikTok (post, story) · **Lift:** very_low

### Tools
- **Claude Code**
- **Canva**, for static feed posts
- **IG / TikTok app**, for stories with native polls

### Cadence (enforce strictly)
- **Feed posts: 1× per week max**
- **Stories: 2-3× per week**

### Workflow by variant

#### Variant 1: Number / quick-answer question
1. Paste: `Use secondkind-bold-organic. Use engagement-prompt, variant 1.`
2. Claude returns: ~5 number-question options + Higgsfield prompt for phone-snap background (medicine cabinet, drawer of bottles, etc.)
3. Generate phone-snap background in Higgsfield
4. Open Canva "Engagement Prompt Native" template, drop background
5. Pick a question, drop it in the photo's negative-space area (Caslon Condensed)
6. SK wordmark bottom-right
7. Export, post to IG feed

#### Variant 2: "Anyone else" commiserating
1. Paste: `...Use engagement-prompt, variant 2.`
2. Claude returns: ~5 "anyone else" prompts + matching Higgsfield prompt (couch corner, denim on bed, etc.)
3. Generate background in Higgsfield
4. Drop in Canva with brand typography on photo's clear area
5. Export, post

#### Variant 3: This-or-that binary
**Story poll path:**
1. Paste: `...variant 3.`
2. Open IG/TikTok app, add poll sticker, type question + options, post

**Static post path:**
1. Paste: `...variant 3, static.`
2. Claude returns: binary options + Higgsfield prompt
3. Generate phone-snap background
4. Drop in Canva with text on photo's clear area
5. Export, post

#### Variant 4: Native poll
1. Paste: `...variant 4.`
2. Claude returns: poll question + 2-4 answer options
3. Open IG Story or TikTok Story
4. Add native poll sticker, type question + options, post

#### Variant 5: Two-truths-and-a-lie
1. Paste: `...variant 5.`
2. Claude returns: 3 statements + which is the lie
3. **Skip Higgsfield**, text density is too high for photo overlay
4. Design single IG square in Canva "Editorial" template with Snow White background
5. Caslon + Neue Montreal, 3 statements clearly numbered
6. Export, post
7. Reveal the lie in the comments after engagement plateaus

#### Variant 6: Tier-list
1. Paste: `...variant 6.`
2. Claude returns: 5-7 items to rank + Higgsfield prompt (shelf of supplements, bathroom shelf, etc.)
3. Generate phone-snap background
4. Drop in Canva, layer the tier-list text on the photo's clear area
5. Export, post
6. Reply to top comments with your own take

#### Variant 7: Carousel quiz / diagnostic
1. Paste: `...variant 7.`
2. Claude returns: 5-slide quiz copy
3. Slides 1 + 5 (hook + reveal) can use phone-snap backgrounds; slides 2-4 (answer options) work best on plain backgrounds for legibility
4. OR: keep all 5 slides plain Snow White for consistency
5. Design in Canva carousel template
6. Export 5 PNGs, upload as IG carousel

### Post-it rule
Reply to comments in **SK-Bold voice** with The comments thread is part of the content. Note recurring answers, they're VOC for future copy.

---

## Tools cheat sheet (where do I go for what?)

| Tool | URL | What you do there |
|---|---|---|
| **Claude Code** | (your local app) | Invoke the skill, get content recommendations |
| **Higgsfield** | https://higgsfield.ai | Create Image (B-roll), Soul ID (avatar), Product Photoshoot, Supercomputer (video w/ mouth sync) |
| **ElevenLabs** | https://elevenlabs.io | AI voiceovers (female 30-40, conversational tone) |
| **CapCut** | https://capcut.com | Video editing, text overlays, captions |
| **Canva** | https://canva.com | IG editorial static cards using brand typography |
| **IG / TikTok apps** | mobile | Native polls, story stickers, posting |

---

## Common patterns across all recipes

### Native-first visual default
For organic content, DEFAULT visual is a phone-snap setting background with text overlaid in a clear area. Plain Snow White editorial is the OCCASIONAL alternative, use it when text density is too high for legible photo overlay (e.g. variant 5 two-truths, dense carousels) or for brand-announcement moments.

Roughly: 75% phone-snap, 25% Snow White editorial.

The brand visual identity (Editorial Minimalism, premium photography, Snow White) lives on paid creative + the main site. Organic earns engagement through native-feeling content.

### Higgsfield prompt rules (universal)
Every Higgsfield prompt for organic content:
- Starts with `"Shot on iPhone, candid"` (camera-phone aesthetic)
- Ends with `"No text, no captions, no overlays, no graphics, no typography."` (prevents hallucinated text)

**Exception:** `pixar-ai-slop` is intentionally animated, no "Shot on iPhone."

### Text-on-photo design pattern
When putting text on a phone-snap photo:
- Find a CLEAR area of the photo for the text (negative space)
- IG variant: use brand typography (Caslon Condensed), preserves brand recognition on a native background
- TikTok variant: use system font (Helvetica), fully native
- Subtle drop shadow / semi-transparent text plate only if readability requires it
- If the photo has no clear area, regenerate with more negative space

### Text-on-image rule
Higgsfield generates clean visuals. **YOU add the text manually** in CapCut (TikTok-native) or Canva (IG). Never trust Higgsfield to write text into images.

### Brand-intro-delay
The SK-Bold brand should NOT appear in the first 30% of any piece. Each recipe has its own brand-intro point, Claude tells you where in the output.

### Cadence
- TikTok: 1+ post per day minimum (Levinger's rule, inconsistency hurts CPMs)
- IG feed: same
- Mix recipes across the week, don't post 5 love letters in a row
- Engagement prompts: 1× per week feed posts max

---

That's all 10 recipes, every tool, every step. Bookmark this doc, when you start a new piece, pick the recipe, scroll to its section here, follow the steps.
