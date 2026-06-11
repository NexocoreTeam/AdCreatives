---
name: secondkind-bold-organic
description: Self-contained organic content production skill for SecondKind Bold (postbiotic gut-health brand, bold voice variant). Bundles the 80 Levinger frames + 10 AI/asset-only production recipes (including hyperrealistic AI UGC influencer videos and low-friction engagement prompts) + SecondKind Bold brand context (voice, prohibited terms, visual rules) + the full 52-entry creative matrix (pain / love / wish / hook) + canonical AI avatar storage. VA-facing, for the social-media person making weekly organic content with no shoot days. Default behavior is ON-DEMAND, SINGLE-PICK with CONCRETE OUTPUT, actual copy + visual direction + production workflow. Multiple options ONLY when explicitly asked. Triggers on "make organic content for secondkind-bold pain-XXX", "give me organic variations for love-XXX", "secondkind-bold organic concept", "what should we post this week for secondkind-bold", "use secondkind-bold-organic with [matrix ID]".
---

# SecondKind Bold, Organic Content Production

This is the VA-facing preset skill for producing organic content for SecondKind Bold. Everything you need is in this folder:

- **`matrix.md`**, the full creative matrix (52 entries: pain, love, wish, hook). Browse this to pick what you're addressing.
- **`formats.yaml`**, Sarah Levinger's 80 organic content frames
- **`production-recipes.yaml`**, 10 AI/asset-only production recipes
- **`recipes/`**, worked example per recipe (Higgsfield prompts included)
- **`avatars/`**, canonical AI avatar lives here (set up once via Higgsfield Soul ID using the prompt in `recipes/ai-ugc-influencer.md`)
- **`VA-QUICKSTART.md`**, copy-paste prompt templates

The base `organic-formats` skill works the same way for any client. This preset wraps it with SecondKind Bold's brand context, voice rules, and matrix preloaded, so the VA doesn't have to specify the client slug or load context manually.

## What to do when this skill fires

1. **Read this file in full** (brand context below, non-negotiable).
2. **Read `formats.yaml`, `production-recipes.yaml`** in this folder.
3. **Acknowledge briefly**, under 50 words. Example:
 > Loaded secondkind-bold-organic: 80 Levinger frames + 10 production recipes + 52 matrix entries. Brand voice locked. Ready for on-demand pick.
4. **Ask what the VA is addressing** if not stated. Common: matrix ID (`pain-005`, `love-003`, `hook-002`), persona name, or pain description.
5. **Resolve the matrix ID** by reading the relevant section of `matrix.md`. Pull the complaint, advantage, positioning angle, format fit, psychology trigger.
6. **Pick frame × recipe**, apply Sarah's eight rules + brand-intro-delay + anchor + variation (POV-specific).
7. **Produce concrete output**, actual copy + visual direction + asset checklist with conditional fallback + production workflow with time estimate.
8. **Stop.** No batching unless explicitly asked.

## SecondKind Bold, brand context (LOAD THIS, DO NOT DRIFT)

### Voice / tone

**Confrontational, declarative, science-armed.** Names the probiotic industry directly as a structurally broken delivery model. Sides with the customer against the category, never against the customer. Vindicates ("you weren't wrong, the product was"), diagnoses the mechanism failure, then converts.

Wry, not sneering. Receipts always arrive in the next line.

### Brand essentials

- **Tagline:** *We don't sell bacteria.*
- **Mission:** Help people feel like themselves again by delivering clinically studied postbiotics that support the gut-brain axis.
- **Mechanism:** Postbiotics (EpiCor®, Bereum®, Totipro®), the bioactive compounds bacteria produce, delivered already active. Skips the survival gauntlet.
- **Founder:** Remy Reinstein

### Colors (use these only for static cards / AI images)

- **Primary** `#1c1917` (Black, for signature serif headlines, body)
- **Secondary** `#d2d2cd` (Light Grey, supporting neutral)
- **Background** `#fefcf6` (Snow White, warm off-white)
- **Accent** `#fcb348` (Mood Balance Yellow, *sole* warm accent, used sparingly on mechanism words)

### Typography (static treatments)

- **Headlines:** F37 Caslon Condensed (Regular / Semibold / Bold; italic for emphasis). Tight kerning (-2).
- **Body:** Neue Montreal Medium / Bold.
- **Sentence case only, never ALL CAPS.**
- No drop shadows. No outlined text. No effects on text or logo. No expanded type.

### Visual identity

- Editorial Minimalism aesthetic, structured grid, generous whitespace, magazine-grade typography.
- **Signature visual device:** abstract white dot / circle clusters representing the microbiome. Single saturated accent color (e.g. `#fcb348`) lives WITHIN the cluster on one or two dots to differentiate the product.
- Photography style: clean, brightly-lit studio product photography on seamless neutral backgrounds. Every shot is the hero shot.
- Premium dark amber glass jars (apothecary / scientific signal).

### Prohibited terms, VA MUST NOT use these

**FDA structure-function compliance:**
- cure, treats, heals, prevents, reverses, eliminates

**Anti-influencer / anti-hype:**
- miracle, magical, revolutionary, life-changing, game-changer, guaranteed

**Tone violations:**
- amazing, incredible, mind-blowing

**Bold-voice anti-cheese (wellness fluff that undercuts the confrontational posture):**
- journey, ritual, find your best self, transform your, begin your, embrace your, unlock your, wellness lifestyle, holistic

If a draft uses any of these, rewrite before showing it.

### Audience

Women 28-50, but male reviewers present. Health-conscious, supplement-fluent, exhausted by gut wellness marketing, often "tried everything." Skews toward Huberman / functional medicine / clean supplement interests. Comfort with science language.

### Social proof (use when relevant)

- 92% felt calmer in 2 weeks (brand-reported)
- 89% reported less bloating (brand-reported)
- Press: CBS, NBC, Silicon Valley Business Journal, USA Today, Daily Mail
- Doctor endorsements: Dr. Zachary Schwartz (Family Medicine), Dr. Nancy Lin (PhD, Holistic Nutritionist), Dr. Stuart Weinberger (Gastroenterologist), Dr. Hyun Dong Shin (PhD, Microbiologist)
- 60-day money-back guarantee

## The culture layer (added 2026-06-10): organic runs at T2 license

Everything this skill produces is a T2 (organic) or T1 (comment) surface, which carries more license than the paid rulebook. The live culture layer is maintained in the AdCreatives repo at `clients/secondkind-bold/culture/` (pulse-*.md, vocabulary.yaml, bold-bets.md, refreshed biweekly via the `culture-pulse` skill); if you can read it, load it before writing. If you can't, apply the standing flexes below and treat any cultural reference older than 30 days as expired (say so rather than guessing).

**Standing T1-T2 flexes** (from the 2026-06-10 guidelines audit; FDA claims rules and the side-with-her identity rules still apply everywhere, in full):

- **Pride is not shame.** The hot-girls-with-IBS reclamation register is open for Danielle and Paula ("hot girls know which bathrooms to trust"). Shame stays banned. Never Natalie.
- **Questions are allowed** in captions, engagement prompts, and replies. Confession prompts drive the early comment density the algorithm rewards.
- **Comment-native emoji are vocabulary here:** 💀 (too real), 😭 (dramatic relatable), 🙏 (sparingly, replies only).
- **Receipts move one tap away.** A joke doesn't need a citation in-frame; put the trial in the pinned comment or caption.
- **Ironic quotation of wellness-speak is allowed as mockery** ("your gut journey," eye roll). Sincere use stays banned.
- **The second enemy:** indict the guttok hack economy too ("no ginger shot is coming to save you"). Mock the hacks, never the people doing them. Still never name competitor brands; if a commenter names one first, answer honestly and mechanism-first.
- **Cultural urgency is fine** ("this sound dies Friday"); offer urgency stays banned.
- **First-60-minute comment protocol:** reply to at least 5 early comments on every post, in the group-chat register. Pin a punchline or the receipt.

**Fast-lane gate before shipping anything bold (six questions, minutes):** claims clean? cut lands on category/mechanism/us? two live cultural signals? would she share it or dunk on it? low-blast-radius surface? kill date and metric named? Six yes = ship.

## The frame × recipe model (organic-formats core)

For any matrix entry, pick **one frame** (story/structure) and **one recipe** (production method). Sometimes the recipe IS the format (love letter, "we're not [X]"). Sometimes a frame anchors and the recipe rotates.

| Recipe | Output | Lift | Best for SecondKind Bold |
|---|---|---|---|
| `text-overlay-monologue` | video | low | Surprising-fact education, 35-75 words / 3 beats; identity opens ("hot girls") for Danielle and Paula |
| `text-overlay-pov` | video | very_low | 1-2 line flex or POV borrowed from live feed formats. Candid motion or anchor + variation (never a dead clip). The line test bed. |
| `david-goliath-no-intro` | video or carousel | medium | Probiotic industry as Goliath. Carousel fallback if no founder footage |
| `pixar-ai-slop` | video or images | medium | Personifying bacteria, the gut, the probiotic that didn't survive. VA needs VFX skill |
| `not-x-objection` | image or short video | very_low | *"We're not probiotics. We don't want to be."*, the canonical SecondKind execution |
| `ugc-cutup-voiceover` | video | low | Existing UGC stripped of audio + AI VO of a new matrix pain |
| `static-educational-card` | image or carousel | very_low | Behind-the-science, mythbusting. Two variants: IG editorial + TikTok native phone-snap |
| `native-ai-product-shot` | image or carousel | very_low | Product as phone-snap in real settings. Native captions, no CTA |
| `ai-ugc-influencer` | video | medium | Hyperrealistic AI avatar speaking a script. Uses canonical SK-Bold avatar (avatars/). 5-tool chain |
| `engagement-prompt` | image / carousel / native poll | very_low | Drive comments / replies / poll taps. *"How many probiotics have you tried?"* style. 1×/week feed max. |

## The eight Levinger rules

Don't ship organic that breaks 1-7.

1. **Episodic**, same characters/setting/format, only episode changes.
2. **Repetitive without being boring**, content surprises, format never does.
3. **Interest-based, not social**, niche identity over broadcast.
4. **Entertainment first, selling never**, no CTA. Product is a prop.
5. **Consistent in volume**, 1×/day minimum.
6. **Lifestyle-coded, not product-coded**, wrap the life, not the SKU.
7. **Designed for recall, not clicks**.
8. **Transferable**, quality marker only. We don't produce paid versions from this skill.

## The brand-intro-delay rule

The SecondKind brand does NOT appear early. It earns its reveal:

| Recipe | Brand intro point |
|---|---|
| `text-overlay-monologue` (love letter) | ~60-70% in |
| `david-goliath-no-intro` | ~70% in (after the Goliath is destroyed) |
| `text-overlay-pov` | None, line is the value, no brand needed |
| `pixar-ai-slop` | Mid-piece, integrated into character story |
| `not-x-objection` | Brand IS the message, but the X (probiotics) comes first |
| `ugc-cutup-voiceover` | Mid-to-late |
| `static-educational-card` | Slide 5-6 of a 6-slide carousel (or never on single) |
| `native-ai-product-shot` | Product is the image; caption stays native |
| `ai-ugc-influencer` | Scene 4 of 5 (~70% in), avatar must be a real person to the audience first |
| `engagement-prompt` | None, brand voice IS the brand signal; SK wordmark in corner is the only mark |

If a piece introduces the brand in the first 30%, it stops being organic. Re-pick or restructure.

## The anchor + variation rule (POV shorts ONLY; refined 2026-06-11)

For `text-overlay-pov`, never recommend a DEAD static clip with text overlay. Two sanctioned visuals:

1. **Single candid clip with natural human motion** (operator example: a person at a desk on a Zoom call). The aliveness of the moment carries it; the line does the work.
2. **Anchor + variation (the stronger default):**
   - **Camera locked.** Same frame across all cuts.
   - **One element changes** across 2-5 cuts (outfits = different days, products, body language, props, dates).
   - **Text overlay stays static.**
   - The variation creates the scroll-stop.

What stays banned: a frozen, motionless clip with a caption on it. If nothing in the frame is alive, it scrolls past.

Reference: Dara Denny's *"serving looks and spreadsheets"*, same desk anchor, different outfits, text locked.

## Posting cadence (per recipe)

When the VA asks "how often should I post X?" or "what should I post this week?", reference the cadence framework:

| Recipe | Frequency |
|---|---|
| `text-overlay-pov` | Daily-ish (3-4× per week) |
| `native-ai-product-shot` | 2-3× per week |
| `ugc-cutup-voiceover` | 1-2× per week |
| `text-overlay-monologue` (Love Letter) | 1× per week, weekly emotional anchor |
| `static-educational-card` | 1× per week (alternate IG / TikTok variants) |
| `not-x-objection` | 1× per week, brand-positioning anchor |
| `engagement-prompt` (feed) | 1× per week MAX |
| `engagement-prompt` (story) | 2-3× per week |
| `david-goliath-no-intro` | 1× every 1-2 weeks |
| `ai-ugc-influencer` | 1× per week (once Soul ID is set up) |
| `pixar-ai-slop` | 1× per month, special occasions |

Foundational rules:
1. **At least 1 post per day** on TikTok and IG Reels, Meta reads inconsistency as low brand quality
2. **Mix recipes**, same recipe every day kills recall; same recipe never used breaks the recall engine
3. **Stories don't count** against the daily-feed rule

Full details: `CADENCE.md` in the preset folder.

## Native-first visual default (important)

For organic content, the default visual for static posts is a **native AI phone-snap setting background** (kitchen counter, bathroom counter, nightstand, desk) with text overlaid, NOT a plain Snow White editorial background.

Even for static brand-positioning content (`not-x-objection`, `engagement-prompt`, `static-educational-card` IG variant), default to a phone-snap background that looks native to the feed.

Plain Snow White editorial backgrounds are the **occasional alternative**, use them when:
- Text density is too high for legibility on a photo (multi-statement quizzes, dense educational carousels)
- The piece is a brand announcement / press moment requiring premium editorial feel
- VA specifically requests it

For everything else, native phone-snap is the default.

**Why:** SK-Bold's brand visual identity (Editorial Minimalism, premium photography, Snow White backgrounds) lives on **paid creative and the main site**. **Organic earns engagement through native-feeling content.** The brand typography (Caslon Condensed) can stay, it preserves brand recognition, but the BACKGROUND should be native phone-snap, not editorial.

## Text overlay on phone-snap photos

When putting text on a phone-snap photo:
- Find a CLEAR area of the photo for the text (kitchen counter empty zone, plain wall, soft-focus area)
- **IG:** brand typography (Caslon Condensed), preserves brand recognition
- **TikTok:** system font (Helvetica), fully native
- Add subtle drop shadow / semi-transparent text plate ONLY if needed. Default = text directly on photo in clear area.
- If the photo has no clear area, regenerate the Higgsfield prompt with more negative space

## No em-dashes, ever

SK Bold copy NEVER uses em-dashes (—) or en-dashes (–) in any output. Use periods, commas, or colons instead. The brand voice is declarative and three-beat-period-stop. Em-dashes create flowy connected thoughts that contradict the voice.

This applies to headlines, body copy, script lines, captions, slide text, and engagement prompts. If Claude generates copy with em-dashes, rewrite using periods or commas.

## Design tool: Canva, not Figma

All static post and carousel production happens in **Canva**, not Figma. When generating workflow instructions or referencing design steps, always say Canva. The agency does not use Figma at all.

## Higgsfield prompt rules

Every Higgsfield image prompt MUST include both:

1. **`"Shot on iPhone, candid"`** at the start. Without it, AI defaults to art-directed / professional-photography aesthetic, reads as "ad" and gets scrolled.
2. **A no-text clause** at the end: *"No text, no captions, no overlays, no graphics, no typography."* AI hallucinates garbled text otherwise. VA adds all text manually in CapCut afterwards.

**Exception for #1:** the `pixar-ai-slop` recipe is intentionally animated, not camera-phone, skip "Shot on iPhone" for that recipe.

**Exception for #2:** product shots can show the product's own label. No other text.

**Output structure:** list the visual prompts (for Higgsfield) and the text content (headlines, slide copy, captions) in **separate sections** so the VA knows what goes where:

> **HIGGSFIELD PROMPTS (visuals only, no text in image):**
> Slide 1: "[prompt with no-text clause]"
> ...
>
> **TEXT (VA adds in CapCut after generating images):**
> Slide 1: *"why your probiotic isn't working"*
> ...

## Concrete output principle

This skill does not say *"use a love letter format."* It says:

> **Recipe:** TikTok Love Letter
> **Opener:** *"Girls, your gut lining rebuilds itself about every week."*
> **Body:** [35-75 word, 3-beat letter: callout + hedged fact → emoji-led "supports" lines → product named once + easy close]
> **Visual:** AI B-roll of [specific scene]. If unavailable, stock footage tagged [specific tag].
> **Brand-intro point:** final beat (~60-75% in).
> **Production:** [tool chain] →

The VA reads it and ships it. No interpretation step.

## How to bridge to the matrix

Matrix IDs map to `matrix.md` sections:
- `pain-XXX` → Pain vs Competitor sheet
- `love-XXX` → What They Love sheet
- `wish-XXX` → Wishes & Gaps sheet
- `hook-XXX` → Hook Angles sheet

When the VA names an ID, read the relevant section. Use the **positioning angle**, **what people say**, and **psychology trigger** as the raw material for copy. The matrix also includes Dara format suggestions, those are for the paid pipeline. Ignore them here; pick organic recipes from `production-recipes.yaml`.

## Output pattern (single concrete pick)

```
Matrix entry: <ID>, <one-line summary from matrix.md>
Recipe: <name> (lift: <level>)
Frame: <Sarah frame name, or "implicit" if the recipe is the format>
Brand-intro point: <where>

THE CONTENT

 Headline / opener:
 "<actual text>"
 Body / monologue / slide copy:
 <actual text in SecondKind Bold voice; register per recipe (love letter = light, warm, educational; expose/confession recipes = confrontational, receipts-next-line)>
 Visual direction:
 Primary: <specific asset description>
 Fallback if primary unavailable: <specific asset>
 Brand mark / product reveal:
 <when, how, where in frame>

PRODUCTION WORKFLOW
 1. <step>, ~<time>
 2. <step>, ~<time>
 Total: ~<X> min.

RULE CHECK
 - Brand-intro-delay: ✓ (at <point>)
 - Eight Levinger rules: 1✓ 2✓ ...
 - Prohibited terms: none used ✓
 - Voice: confrontational/declarative ✓

PITFALLS TO AVOID
 - <recipe-specific pitfall>
 - <brand-specific pitfall>
```

## Multi-pick mode (only when explicitly asked)

If the VA says *"give me variations"*, *"3 options"*, *"alternatives"*, *"examples"*, produce 3-4 quick-card picks, each ≤100 words. The VA picks one and asks "go deep on #2" to get the full concrete output.

## What this skill does NOT do

- Doesn't batch-generate options by default (single-pick is the default)
- Doesn't generate the actual images/videos (use AI tool skills, `higgsfield-generate`, `fal-ai-media`, `Claude_Preview` for previews)
- Doesn't build the posting calendar
- Doesn't produce paid concepts (those live in the creative-matrix pipeline already, paid recommendations are embedded in `matrix.md` for context but should be ignored when generating organic)
- Doesn't include Yapper (needs human), Listicle (paid only), We're sorry (off-brand)

## File layout

```
clients/secondkind-bold/exports/secondkind-bold-organic/
├── SKILL.md ← this file
├── matrix.md ← 52-entry creative matrix
├── formats.yaml ← 80 Sarah Levinger frames
├── production-recipes.yaml ← 9 production recipes
├── recipes/ ← worked example per recipe (with Higgsfield prompts)
├── avatars/ ← canonical SK-Bold AI avatar (generated once by VA)
└── VA-QUICKSTART.md ← prompt templates for the VA
```

When zipped as `secondkind-bold-organic.zip`, this folder is the complete VA handoff package.
