# VA Guide, Organic Content for SecondKind Bold

Hi! This is your guide to making a week of organic content for SecondKind Bold. You won't shoot video. You won't book creators. You'll use AI tools + a Claude skill + a matrix of customer topics.

A video walkthrough exists, watch that first. Then keep this open as your reference.

---

# Part 1: How the system works

## What you have

- **Claude Code** (installed) with the `secondkind-bold-organic` skill loaded
- **`matrix.md`**, 52 customer topics (pains, loves, wishes, hooks), each with an ID
- **10 production recipes**, different ways to make a piece without shooting anything
- **AI tools**, Higgsfield, ElevenLabs, CapCut, Canva

You don't need to memorize the 10 recipes. The skill picks the right one for you.

## One-time setup (do these once, before you start)

1. **Install the skill.** Unzip `secondkind-bold-organic.zip` into `~/.claude/skills/secondkind-bold-organic/` on your machine.
2. **(Optional) Set up the canonical AI avatar in Higgsfield.** Required before your first AI UGC influencer video, but not before any other recipe. Takes, see `recipes/ai-ugc-influencer.md`.

## The weekly workflow

```
1. Open matrix.md → pick an ID (e.g. pain-005)
2. Tell Claude → Claude returns output
3. Pick the option you like (if you asked for variants)
4. Execute: Higgsfield → CapCut/Canva → post
```

That's it. Roughly 3-for a full week of content.

## Two ways to ask Claude

| What you type | What you get |
|---|---|
| *"Use secondkind-bold-organic. Pull pain-005. Use [recipe-name]."* | **One** fully-developed concept, copy, prompts, workflow. Ready to ship. |
| *"Use secondkind-bold-organic. Give me 3 variations for pain-005."* | **Three quick-card overviews**, each a different recipe. You pick one, say *"go deep on #2,"* and Claude returns the full output. |

Use **variants** when you're browsing for ideas. Use **direct** when you know what you want.

## What Claude gives you vs what you do

**Claude generates:**
- The actual copy (headlines, scripts, captions)
- The Higgsfield prompts you paste into Higgsfield
- Step-by-step production workflow with time estimates
- A rule check (no prohibited words, brand-intro point, etc.)

**You execute:**
- Paste Higgsfield prompts into Higgsfield → generate images/video
- Open CapCut (for video) or Canva (for static) → add text manually
- Post

**Claude never makes the actual images or videos.** It gives you the recipe; you cook.

## The rules (Claude enforces these, but know them)

1. **Voice:** confrontational, declarative, science-armed. Never use *miracle, life-changing, journey, ritual, transform your, holistic, cure, treats.*
2. **Brand-intro-delay:** the SK-Bold brand doesn't appear in the first 30% of any piece. Each recipe has its own intro point.
3. **Native-first visuals:** default to AI phone-snap setting backgrounds (kitchen counter, bathroom counter, nightstand). Plain Snow White editorial is the occasional alternative.
4. **Higgsfield prompts:** every prompt starts with *"Shot on iPhone, candid"* and ends with *"No text, no captions, no overlays, no graphics, no typography."* You add text manually in CapCut/Canva.
5. **No CTA.** No "shop now," no "link in bio," no hashtags in the visual.

If you ever see Claude break these, push back: *"Re-do without using [word]."*

## Posting cadence

See **`CADENCE.md`** for the full weekly schedule. The short version:

- **Daily backbone:** 1+ feed post per day (TikTok + IG Reels). Inconsistency hurts your ad CPMs. Better to post a low-effort piece daily than a perfect piece weekly.
- **Mix recipes**, same recipe every day kills recall; same recipe never used breaks the recall engine.
- **Engagement prompts:** 1× per week feed posts MAX. 2-3× per week as stories is fine.
- **Love letter:** 1× per week. Short educational charmer (35-75 words): warm callout + surprising fact + product as easy add. (Redefined 2026-06-11; no longer the long emotional monologue.)
- **Pixar AI slop:** 1× per month, special occasions only.
- **AI UGC influencer:** 1× per week once your Soul ID is set up.

A typical week: ~10-13 pieces across 6 different recipes (8 feed posts + 5 stories).

## Quick reference, all 10 recipes

| Recipe | Output | When |
|---|---|---|
| `text-overlay-monologue` (Love Letter) | Video | Surprising fact + light education, 35-75 words |
| `text-overlay-pov` (POV Short) | Video | 1-2 line flex or POV from live feed formats. Daily fill + line test bed. |
| `david-goliath-no-intro` | Video or carousel | Calling out the probiotic industry |
| `pixar-ai-slop` | Animation | Personifying bacteria / category villains. VFX skill. |
| `not-x-objection` | Static or short video | Brand positioning. "We're not probiotics." |
| `ugc-cutup-voiceover` | Video | When you have existing UGC footage |
| `static-educational-card` | Image or carousel | Mythbusting, educational |
| `native-ai-product-shot` | Image or carousel | Feed-fill product photo |
| `ai-ugc-influencer` | Video | Hyperrealistic AI avatar speaking. VFX skill. |
| `engagement-prompt` | Image / poll | Drive comments. 1×/week feed max. |

---

# Part 2: Each recipe with steps + an example

Each recipe walkthrough below shows you exactly what the steps look like and what Claude actually returns when you ask for that recipe. Pick the recipe, follow the steps, ship.

---

## Recipe 1: TikTok Love Letter (`text-overlay-monologue`)

**What it makes:** A 20-40 second TikTok / Reel: a short, warm, educational 3-beat letter (35-75 words) revealed beat-by-beat over silent AI B-roll. Callout + surprising fact, then emoji-led "supports" lines, then product named once + easy close.

**When to use it:** When a surprising fact or identity behavior carries the open. Unaware / problem-aware. (Redefined 2026-06-11; this is no longer a long emotional monologue.)

**Tools:** Claude, Higgsfield, CapCut

### Steps

1. **Ask Claude** for the script + Higgsfield prompts
2. **Generate 4-6 B-roll clips** in Higgsfield (silent, no people speaking)
3. **Assemble in CapCut**: drop clips, add text overlay line-by-line, add minimal music
4. **Export 9:16, post**

### Example: the gut-lining clock (script 2 in `clients/secondkind-bold/copy/tiktok-love-letters-v3.md`)

**You type:**
> *Use secondkind-bold-organic. Pull a fact angle. Use text-overlay-monologue.*

**Claude returns:**

**BEAT 1 (opener, first 3 sec, white text):**
> *Girls, your gut lining rebuilds itself about every week. What you feed it today actually matters.*

**BEAT 2 (emoji-led reveals, one line per screen):**
> *Postbiotics are compounds your gut uses for exactly that:*
> *😌 Lining support*
> *🚽 Regularity*
> *⚡ Steady energy*

**BEAT 3 (product + close, the final beat, ~60-75% in):**
> *Gut Balance packs three clinically studied ones into two capsules a day. Easy add.*

**HIGGSFIELD PROMPTS (3-4 silent B-roll clips, 9:16 vertical, quiet and domestic):**

```
1. "Shot on iPhone, candid. Hands stirring oatmeal in a cream stoneware
 bowl, golden morning light through a kitchen window, slightly imperfect
 framing, no faces visible, 9:16 vertical, shallow depth of field. No
 text, no captions, no overlays, no graphics, no typography."

2. "Shot on iPhone, candid. A small handful of pill capsules in an open
 palm, kitchen counter background, soft morning light, no face, 9:16
 vertical. No text, no captions, no overlays, no graphics, no typography."

3. "Shot on iPhone, candid. Glass of water being filled at a kitchen sink,
 midday natural light, slightly off-center composition, no faces, 9:16
 vertical. No text, no captions, no overlays, no graphics, no typography."

4. "Shot on iPhone, candid. Amber glass supplement jar on a tidy kitchen
 counter next to keys and a phone, evening light, no faces, 9:16 vertical.
 No text, no captions, no overlays, no graphics, no typography."
```

**WORKFLOW:**
1. Generate 4 B-roll clips in Higgsfield
2. CapCut: drop clips in order, add text overlay with line-by-line reveal
3. Minimal ambient pad music, drop volume under brand-reveal line
4. Export 9:16

---

## Recipe 2: TikTok POV Short (`text-overlay-pov`)

**What it makes:** A 5-15 second TikTok / Reel: 1-2 lines TOPS over a candid clip of a real person in a mundane moment. The line is a meme-native identity flex borrowed from live feed formats (or a POV open); it never makes a product claim. Visual: single candid-motion clip OR locked-camera anchor + variation. Fastest format to ship.

**When to use it:** Daily fill + the messaging test bed. Winning lines graduate to love letters, creator briefs, and paid hooks. Line bank: `clients/secondkind-bold/copy/tiktok-pov-shorts.md`.

**Tools:** Claude, Higgsfield, CapCut

### Steps

1. **Ask Claude** for the POV line + anchor prompt + 4-5 variation prompts
2. **Generate the anchor shot** in Higgsfield
3. **Generate 4-5 variation cuts** using the anchor as reference (same scene, ONE element changes)
4. **Assemble in CapCut**: cuts in sequence, text overlay LOCKED above
5. **Export, post**

### Example: "Serving looks and a calm gut." (line 8 in the bank)

**You type:**
> *Use secondkind-bold-organic. Pull a line from the POV bank. Use text-overlay-pov.*

**Claude returns:**

**THE LINE (locked, never moves):**
> *Serving looks and a calm gut.*

**THE VISUAL, anchor + variation (two outfits = two days):**

| Cut | Variation |
|---|---|
| 1 | Same desk, same framing: structured blazer, mid-typing, relaxed |
| 2 | Same desk, same framing: colorful knit, different hair, sipping coffee |

**HIGGSFIELD PROMPTS:**

```
Anchor (generate ONCE, use as reference for all variations):
"Shot on iPhone, candid. A woman in her late 30s sitting at a desk on a
video call, laptop open, natural window light, framed at chest level,
home office setting, 9:16 vertical, slightly imperfect framing. No text,
no captions, no overlays, no graphics, no typography."

Cut 1 (day one):
"Use the anchor as reference. Same desk, same framing, same lighting. She
wears a structured blazer over a white top, mid-typing, relaxed posture.
No text, no captions, no overlays."

Cut 2 (day two):
"Use the anchor as reference. Same desk, same framing, same lighting. She
wears a colorful knit sweater, hair styled differently, holding a coffee
mug. No text, no captions, no overlays."
```

**Single-clip alternative (also sanctioned):** one candid clip with natural motion (typing, nodding on a call) carries lines like *"My safe order misses me."* with no cuts at all. Never use a frozen, motionless clip.

**WORKFLOW:**
1. Generate anchor, then variation cut(s) using anchor as reference (or animate one candid clip)
2. CapCut: cuts in sequence + locked text overlay above
3. Export 9:16

**Critical:** Static clip + text doesn't stop the scroll. The variation pattern is the format.

---

## Recipe 3: David & Goliath (`david-goliath-no-intro`)

**What it makes:** A video or 7-slide carousel that calls out the probiotic industry as the enemy, then introduces the SK-Bold brand at ~70% in. Two paths: video (needs founder footage) or carousel (just Canva).

**When to use it:** Solution-aware or product-aware personas. When the matrix entry has a clear category problem to attack.

**Tools:** Claude + (founder footage + ElevenLabs + CapCut for video) OR (Canva only for carousel)

### Steps (carousel, the easier path)

1. **Ask Claude** for the 7-slide copy
2. **Design 7 slides in Canva** with brand typography (or phone-snap backgrounds for native variant)
3. **Brand reveal on slide 7**
4. **Export, post as IG carousel**

### Example, `pain-002`: *~70% of probiotic bacteria die in gastric transit*

**You type:**
> *Use secondkind-bold-organic. Pull pain-002. Use david-goliath-no-intro, carousel version.*

**Claude returns:**

**THE 7 SLIDES:**

| Slide | Copy |
|---|---|
| 1 | **The probiotic industry is built on a lie.** |
| 2 | They sell you 10 billion live bacteria. They tell you it'll fix your gut. |
| 3 | They don't tell you that ~70% of those bacteria die in your stomach acid before they ever reach your gut. |
| 4 | The ones that survive face a colonization battle they were never built to win. |
| 5 | Which is why you can take a $50 probiotic every morning for six months and feel exactly nothing. |
| 6 | That's not a problem with one brand. That's the entire delivery model. |
| 7 | **We're postbiotics. We send the compounds bacteria make, already active. No survival gauntlet.** (SK wordmark, bottom-right) |

**HIGGSFIELD PROMPTS (7 phone-snap backgrounds, 1 per slide):**

```
Slide 1: "Shot on iPhone, candid. A large probiotic bottle close-up on a
counter, soft morning light, large clear area in upper portion for text,
1:1 aspect ratio. No text, no captions, no overlays."

Slide 2: "Shot on iPhone, candid. Multiple probiotic capsules in an open
palm, kitchen counter background, soft natural light, negative space
around, 1:1 aspect ratio. No text, no captions, no overlays."

[Slides 3-6 follow similar pattern, Claude provides all 7]

Slide 7: "Shot on iPhone, candid. Gut Balance amber glass jar on a wooden
counter, soft morning light, single product in frame, negative space for
wordmark, 1:1 aspect ratio. Product label is the only text."
```

**WORKFLOW:**
1. Generate 7 phone-snap backgrounds in Higgsfield
2. Canva: "IG Carousel Native" template, drop backgrounds + Caslon Condensed copy in clear areas
3. Yellow accent on mechanism words (*postbiotics, compounds*), SK wordmark slide 7 only
4. Export 7 PNGs

**Important:** Never name competitors by brand (no "Seed," "Ritual," etc.). Always attack the CATEGORY ("probiotics") or the broken belief.

---

## Recipe 4: Pixar AI Slop (`pixar-ai-slop`)

**What it makes:** Outrageous AI cartoon characters acting out the brand's narrative. Visibly AI, never trying to look real. Best for personifying things, the gut, the bacteria, the bloat.

**When to use it:** When humor unlocks an objection earnest copy can't reach. When VA has AI animation skills.

**Tools:** Claude, Higgsfield (animation), ElevenLabs (character voices), CapCut

### Steps

1. **(One-time)** Build your recurring character set in Higgsfield, "Pro," "Biotic," "Posty"
2. **Ask Claude** for the 4-scene script + character actions
3. **Generate animated scenes** in Higgsfield using saved character references
4. **Voice characters in ElevenLabs**, different cartoon voice per character
5. **Assemble in CapCut**, add SFX, export

### Example, `wish-002`: *"a probiotic-category product that actually survives the trip to the gut"*

**You type:**
> *Use secondkind-bold-organic. Pull wish-002. Use pixar-ai-slop.*

**Claude returns:**

**THE 4-SCENE SCRIPT:**

**Scene 1**, Two Pixar-style bacteria characters (Pro and Biotic) inside a capsule, nervously holding tiny backpacks.
> *PRO: "Okay so we just have to survive the stomach, then the small intestine, then convince an entire ecosystem to let us in. Easy."*
> *BIOTIC: "How many of us are in this bottle?"*
> *PRO: "Ten billion."*
> *BIOTIC: "And how many usually make it?"*
> *PRO: "...don't worry about it."*

**Scene 2**, Wave of (clearly AI-rendered) stomach acid washes over them. Most disappear in puffs of pixel dust.

**Scene 3**, Two survivors emerge into the intestine. See an established city of resident bacteria looking at them like strangers.
> *PRO: "...nobody's expecting us, are they."*

**Scene 4**, Cut to Posty (the postbiotic, clearly different character, glowing). Just walking around the gut city. Nobody's mad. She's just delivering.
> *VO: "Postbiotics skip the survival part. You send the compounds, not the messengers."*

**HIGGSFIELD ANIMATION PROMPTS (use saved character refs):**

```
Scene 1: "Two Pixar-style bacteria characters Pro and Biotic, anthropomorphized
with tiny backpacks, inside a transparent pill capsule, nervous expressions,
9:16 vertical animated style. No text, no captions, no overlays."

Scene 2: "Same characters, wave of orange-amber acid liquid washes through the
capsule, characters scream cartoon screams, most disappear in puffs of dust,
9:16 vertical animated style."

[Scenes 3 and 4 follow similar pattern]
```

**WORKFLOW:**
1. (One-time) Generate character refs (Pro + Biotic + Posty) in Higgsfield Soul ID, ONCE, reused forever
2. Generate 4 scene animations using character refs
3. Voice each character in ElevenLabs (different cartoonish voice per character)
4. Edit in CapCut: scenes + VO + sound effects
5. Export 9:16

**Critical:** Same characters across every Pixar AI episode. New characters per video = no recall.

---

## Recipe 5: "We're not [X]" (`not-x-objection`)

**What it makes:** A static image (or short video) with a bold brand-positioning headline. The canonical SK-Bold execution: *"We're not probiotics. We don't want to be."*

**When to use it:** Brand-positioning posts. When the differentiator IS the entire pitch.

**Tools:** Claude, Higgsfield (phone-snap background), Canva

### Steps

1. **Ask Claude** for the headline + 3 body lines + Higgsfield prompt
2. **Generate phone-snap background** in Higgsfield
3. **Design in Canva**: drop background, add headline + body in clear area
4. **Export, post**

### Example, `pain-001`: *probiotic efficacy plateaus after 1-2 months*

**You type:**
> *Use secondkind-bold-organic. Pull pain-001. Use not-x-objection.*

**Claude returns:**

**THE HEADLINE (Caslon Condensed, large):**
> *We're not probiotics.*
> *We don't want to be.*

**THE BODY (Neue Montreal, smaller, 3 lines):**
> Most probiotics don't survive your stomach acid.
> The ones that do don't colonize.
> We send the compounds your gut actually uses, already active.

**HIGGSFIELD PROMPT (phone-snap background):**

```
"Shot on iPhone, candid. A clean wooden kitchen counter at morning, soft
natural light from a window off-frame, mostly empty counter with a single
ceramic mug in the bottom-right corner, large clear/negative space in the
upper portion of the frame, lived-in domestic feel, 1:1 aspect ratio,
slightly imperfect framing. No text, no captions, no overlays, no graphics,
no typography."
```

**WORKFLOW:**
1. Generate background in Higgsfield
2. Canva "IG Square Native" template: drop background, drop headline + body in upper-left clear area (Caslon + Neue Montreal)
3. Yellow accent on the word *compounds*, SK wordmark bottom-right
4. Export 1080×1080 PNG

**Occasional alternative:** Skip Higgsfield, use plain Snow White background, total. Use about 1 in 4 posts.

---

## Recipe 6: UGC Cut-up + AI Voiceover (`ugc-cutup-voiceover`)

**What it makes:** A video using existing UGC footage from past campaigns, with the audio stripped and a new AI voiceover layered on top. The creator becomes anonymous lifestyle B-roll.

**When to use it:** When you have a backlog of licensed UGC and want to repurpose it for a new pain point. No Higgsfield needed.

**Tools:** Claude, existing UGC library, ElevenLabs, CapCut

### Steps

1. **Ask Claude** for the VO script + the type of B-roll you need
2. **Pull matching UGC** from your library (clips where the creator's mouth isn't visible)
3. **Strip audio** from the clips
4. **Generate AI voiceover** in ElevenLabs
5. **Assemble in CapCut**: silent UGC + AI VO + captions + minimal music

### Example, `love-001`: *"Bloating visibly gone, fast, noticeable, socially liberating relief"*

**You type:**
> *Use secondkind-bold-organic. Pull love-001. Use ugc-cutup-voiceover.*

**Claude returns:**

**THE VO SCRIPT:**

> *"There's a version of you that disappeared sometime in your late twenties."*
> *"The one who didn't think about her stomach. Who could eat dinner and not regret it. Who looked the same at 7pm as she did at noon."*
> *"You assumed she was gone forever."*
> *"You tried probiotics. Cleanses. Cutting things out. None of it brought her back."*
> *"Then one day you noticed you could button your jeans after dinner."*
> *"And then a week of that. And then a month."*
>
> *[BRAND INTRO ~55s mark]*
> *"Turns out the version of you you missed wasn't gone. She was waiting for your gut to actually work."*
> *"Postbiotics don't send live bacteria. They send what your gut uses, already active. No survival gauntlet."*

**B-ROLL TYPES NEEDED (Claude tells you what to search the library for):**

1. Woman's hands buttoning jeans, no face visible
2. Hands chopping vegetables in a kitchen
3. Hands closing a laptop at evening
4. Hands holding a coffee mug at morning
5. A woman walking (filmed from behind or side, no face)
6. Hand reaching for the Gut Balance bottle on a counter

**WORKFLOW:**
1. Search agency UGC library for the 6 b-roll types, pull clips
2. Strip audio from all clips
3. Generate AI VO in ElevenLabs (voice: female 30-40, conversational, "thinking aloud")
4. CapCut: drop clips in script order, layer VO, add minimal ambient music, auto-generate captions
5. Brand intro at ~70% mark
6. Export 9:16

**Critical:** Use clips where the creator's mouth ISN'T visible during the emotional VO beats. Hands, body, settings only, visible mouth movement will conflict with the AI voice.

---

## Recipe 7: Static Educational Card (`static-educational-card`)

**What it makes:** A single image or 6-slide carousel that educates / mythbusts. No CTA. The format itself can't sell.

**Two variants:**
- **IG variant**, Caslon Condensed + Neue Montreal on phone-snap backgrounds
- **TikTok native variant**, system font (Helvetica) on phone-snap backgrounds

**When to use it:** Problem-aware audiences. Mythbusting. Behind-the-science content.

**Tools:** Claude, Higgsfield, CapCut (TikTok) or Canva (IG)

### Steps (IG variant, default phone-snap)

1. **Ask Claude** for the 6-slide copy + 6 Higgsfield prompts
2. **Generate 6 phone-snap backgrounds** in Higgsfield
3. **Canva**: drop backgrounds + Caslon/Neue Montreal text overlay in negative space per slide
4. **Slide 6** = brand reveal (SK wordmark, no CTA)
5. **Export 6 PNGs**, upload as carousel

### Example, `pain-003`: *Live-culture probiotics cause severe adverse GI reactions*

**You type:**
> *Use secondkind-bold-organic. Pull pain-003. Use static-educational-card, IG variant.*

**Claude returns:**

**THE 6-SLIDE COPY:**

| Slide | Headline (Caslon) | Body (Neue Montreal) |
|---|---|---|
| 1 | *Why your gut hates your probiotic.* | A 3-minute explanation. |
| 2 | *Probiotics are LIVE bacteria.* | You're introducing strangers into an established ecosystem. |
| 3 | *Your gut already has its own.* | They compete. They release byproducts. They fight. |
| 4 | *That fight feels like a problem.* | Cramping. Bloating. Constipation. Sometimes worse. |
| 5 | *Most people quit at the "worse before better" stage.* | They were never told there was an alternative. |
| 6 | *Postbiotics skip the war entirely.* | (+ SK wordmark, no CTA) |

**HIGGSFIELD PROMPTS (6 phone-snap backgrounds, 1:1):**

```
Slide 1: "Shot on iPhone, candid. A hand holding a probiotic capsule
between thumb and forefinger, kitchen counter background blurred, soft
natural light, large clear area for text, 1:1 aspect ratio. No text, no
captions, no overlays."

Slide 2: "Shot on iPhone, candid. A close-up of an open probiotic
capsule with powder spilling out onto a wooden counter, soft natural
light, negative space around, 1:1 aspect ratio. No text, no captions,
no overlays."

[Slides 3-5 follow similar pattern, Claude provides all 6]

Slide 6: "Shot on iPhone, candid. Gut Balance amber glass jar on a
wooden counter, soft morning light, single product in frame, 1:1 aspect
ratio. Product label is the only text in the image."
```

**WORKFLOW:**
1. Generate 6 phone-snap backgrounds in Higgsfield
2. Canva "IG Carousel Native" template, drop backgrounds + Caslon Condensed headlines + Neue Montreal body in clear photo areas per slide
3. Yellow accent on key mechanism words, SK wordmark slide 6 only
4. Export 6 × 1080×1080 PNGs in carousel order

**TikTok native variant:** Same copy, change Higgsfield prompts to 9:16 vertical, add text in CapCut using Helvetica/system font (NOT brand serifs). total.

---

## Recipe 8: Native AI Product Shot (`native-ai-product-shot`)

**What it makes:** An AI-generated photo of the Gut Balance bottle in a real setting (kitchen counter, gym bag, nightstand). Single image or carousel. Looks like a friend's phone snap.

**When to use it:** Feed-fill content. Building brand recall through visual repetition. Product-aware audience.

**Tools:** Claude, Higgsfield Product Photoshoot, IG/TikTok app for native caption

### Steps

1. **Ask Claude** for the Higgsfield prompt + native caption
2. **Generate product photo** in Higgsfield (Product Photoshoot mode)
3. **Generate 3-4 variations**, pick the most "found"-looking one
4. **Post directly to IG / TikTok** with the native caption

### Example, generic feed-fill (no specific matrix entry needed)

**You type:**
> *Use secondkind-bold-organic. Use native-ai-product-shot. Kitchen counter setting.*

**Claude returns:**

**HIGGSFIELD PROMPT (Product Photoshoot, 1:1):**

```
"Shot on iPhone, candid. Gut Balance amber glass jar on a wooden kitchen
counter, alongside a stoneware coffee mug with visible steam, a slice of
sourdough toast with one bite taken, a folded linen napkin slightly out
of focus. Warm morning light from a window off-frame. Slightly off-center
framing, shallow depth of field, found-photo aesthetic, 1:1 aspect ratio.
No text overlays, no captions, product label is the only text."
```

**THE NATIVE CAPTION:**

> *the only thing I added this month*

(No emoji, no hashtags, no CTA.)

**ROTATE THESE CAPTIONS across posts:**
- *forgot what 7pm felt like without bloat. this is why.*
- *day 30. unbothered.*
- *the morning ritual nobody asked about but here we are*
- *if you know you know*

**WORKFLOW:**
1. Drag your Gut Balance reference photo into Higgsfield Product Photoshoot
2. Paste the prompt, generate 3-4 variations
3. Pick the most "found"-looking one
4. Post to IG with the caption

**Critical:** Reject anything that looks art-directed. The image must read as a casual phone snap, not a campaign photo.

---

## Recipe 9: AI UGC Influencer (`ai-ugc-influencer`)

**What it makes:** A hyperrealistic AI-generated UGC video. One canonical AI avatar speaks a 30-60 sec script across multiple scenes with character consistency. Replaces hiring UGC creators.

**When to use it:** When the matrix entry calls for a personal, confessional voice but you don't have a real creator to film.

**Tools:** Higgsfield (Soul ID + Create Image + Supercomputer), Claude, ElevenLabs, CapCut

### One-time setup (do this ONCE, )

1. Higgsfield → Soul ID → create new character
2. Paste the canonical SK-Bold avatar prompt (from `recipes/ai-ugc-influencer.md`)
3. Generate, iterate 2-3 times, pick the most Danielle-archetype version
4. Save as "SK-Bold Canonical Avatar"
5. Every future AI UGC video uses this Soul ID

### Steps (per video)

1. **Ask Claude** for the 4-6 scene script + Higgsfield scene prompts
2. **Generate scene images** in Higgsfield Create Image (using your Soul ID)
3. **Generate video with mouth-sync** in Higgsfield Supercomputer
4. **Voice in ElevenLabs**
5. **Assemble in CapCut**: video + voice + captions + ambient music

### Example, `pain-004`: *Users with complex gut conditions (SIBO, IBS) find live-probiotic products deliver mixed results*

**You type:**
> *Use secondkind-bold-organic. Pull pain-004. Use ai-ugc-influencer.*

**Claude returns:**

**THE 5-SCENE SCRIPT:**

**Scene 1 (0-10s), Hook:**
> *"I have SIBO. Which means every probiotic anyone recommended to me did the opposite of what it was supposed to do."*

**Scene 2 (10-25s), Setup:**
> *"Bloating got worse. Cramping got worse. I'd take it for two weeks, get destroyed, quit, try a new brand, get destroyed again. Three years of this."*

**Scene 3 (25-40s), Diagnosis:**
> *"My doctor finally explained it. Live bacteria don't behave when your gut is already dysregulated. You're sending invaders into a battlefield. They make everything worse before they make anything better. If they make anything better at all."*

**Scene 4 (40-52s), BRAND INTRO (~67% mark):**
> *"So I switched to postbiotics. The compounds bacteria make, no live organisms. Nothing to fight. Nothing to colonize."*

**Scene 5 (52-60s), The beat:**
> *"Three weeks in. Cramping gone. I don't dread eating anymore."*

**HIGGSFIELD SCENE PROMPTS (each uses your saved Soul ID):**

```
Scene 1: "SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16:
she's standing at a kitchen counter, hand on her stomach, tired
expression, soft morning light. No text overlays."

Scene 2: "SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16:
she's opening a kitchen drawer, multiple probiotic bottles visible,
resigned expression, soft natural light. No text overlays, product
labels are the only text."

Scene 3: "SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16:
she's holding a single probiotic capsule between thumb and forefinger,
holding it up to soft kitchen light, thoughtful expression. No text
overlays."

Scene 4: "SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16:
she's holding a Gut Balance amber glass jar at chest level, looking down
at it considering, soft kitchen light, calm. No text overlays, the Gut
Balance label is the only text."

Scene 5: "SK-Bold Canonical Avatar Soul ID, shot on iPhone, candid, 9:16:
she's sitting at a kitchen counter at evening, relaxed posture, looking
slightly off camera, soft warm evening light. No text overlays."
```

**WORKFLOW:**
1. Generate 5 scene images in Higgsfield Create Image with Soul ID
2. Higgsfield Supercomputer: drop scene images + script per scene, generate video with mouth-sync
3. ElevenLabs: voice the script (female 30-40, "conversational, thinking aloud")
4. CapCut: assemble clips, replace Higgsfield voice with ElevenLabs voice, add captions, minimal ambient music
5. Export 9:16

**Critical:** Same canonical avatar across EVERY SK-Bold AI UGC video. New avatar per video = no recall.

---

## Recipe 10: Engagement Prompt (`engagement-prompt`)

**What it makes:** A low-friction question designed to drive comments, replies, or poll taps. Answerable in 3 seconds with a number, word, or tap. 7 variants.

**When to use it:** Weekly engagement break. Building social-proof momentum before a campaign. Surfacing voice-of-customer in the comments.

**Tools:** Claude + (Higgsfield + Canva for static feed posts) OR (just IG/TikTok app for story polls)

**Cadence:** 1× per week feed posts MAX. 2-3× per week stories.

### Steps (Variant 1: number question, default phone-snap)

1. **Ask Claude** for the question + Higgsfield prompt
2. **Generate phone-snap background** in Higgsfield (matching the question's mood, supplement drawer, medicine cabinet)
3. **Canva**: drop background + question in clear area (Caslon Condensed, large)
4. **Export, post**

### Example, Weekly engagement post (no matrix entry needed)

**You type:**
> *Use secondkind-bold-organic. Use engagement-prompt, variant 1.*

**Claude returns:**

**FIVE QUESTION OPTIONS (pick one, rotate across weeks):**
1. *How many probiotics have you tried?*
2. *How many days into a probiotic before you give up?*
3. *How many supplements are in your bathroom right now?*
4. *How many times have you Googled "why am I bloated" this month?*
5. *What time does the bloat hit?*

**HIGGSFIELD PROMPT (phone-snap background, matches the question):**

```
"Shot on iPhone, candid. A medicine cabinet open, lined with multiple
supplement bottles, casual arrangement, soft bathroom light, large clear
area in the upper portion of the frame for text overlay, slightly
imperfect framing, 1:1 aspect ratio. No text, no captions, no overlays,
no graphics, no typography."
```

**WORKFLOW:**
1. Generate background in Higgsfield
2. Canva "Engagement Prompt Native" template, drop background, drop the question in upper clear area (Caslon Condensed, large)
3. SK wordmark bottom-right, no CTA
4. Export, post to IG feed

**Post-it rule:** Reply to comments in SK-Bold voice with The comments thread is part of the content. Track recurring answers, they're future copy material.

**Other variants (see `recipes/engagement-prompt.md` for full details):**
- Variant 2: "Anyone else..." (phone-snap, )
- Variant 3: This-or-that
- Variant 4: Native poll (story sticker, )
- Variant 5: Two-truths-and-a-lie (plain background, text-dense, )
- Variant 6: Tier list (phone-snap, )
- Variant 7: Carousel quiz (mixed or plain, )

---

# Wrap-up

The system is: matrix → ask Claude → execute. Claude does the thinking. You execute through Higgsfield, CapCut/Canva, and posting.

If you ever feel stuck:
- Try a different recipe for the same matrix entry
- Ask Claude to explain a recipe
- Open the deep-dive in `recipes/<recipe-name>.md`
- Ask Claude *"I'm stuck. What should I make this week?"*

A good week = 5-6 pieces of content using 3-4 different recipes, no broken rules, under 4 hours of work.

Welcome to the team.
