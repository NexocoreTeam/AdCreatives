# Static Educational Card

**Output:** single image OR carousel · **Platforms:** Instagram + TikTok slideshow · **Lift:** very_low · **Brand-intro:** late or none

## What this is

Single image or carousel slides. Text-on-image. Educational or mythbusting tone. No CTA.

**Default visual:** native AI phone-snap setting backgrounds per slide with text overlaid. Plain Snow White editorial is the occasional alternative (used when text density requires it).

Two variants, both now default to phone-snap:
- **IG variant**, brand typography (Caslon Condensed + Neue Montreal) overlaid on phone-snap photos
- **TikTok native variant**, system font (Helvetica) overlaid on phone-snap photos

## When to use it

- Problem-aware or unaware personas (educational entry point)
- Mythbusting matrix positions
- Science-backed brands with explicit mechanism claims
- Building Sarah's rule-8 quality (these double as static paid ads cleanly)

## When to fall back to plain Snow White editorial

- Dense educational content where text needs maximum legibility
- Brand announcements / press moments
- Anniversary / milestone posts
- ~1 in 4 of your carousels

For everything else, default to phone-snap backgrounds.

---

## IG variant, worked example (default = phone-snap backgrounds)

**Brief:** `secondkind-bold-gut-balance-0c7dc7.yaml`
**Frame:** `behind-the-science`
**Output:** 6-slide IG carousel

### THE TEXT (VA adds in Canva using brand typography)

| Slide | Headline (Caslon) | Body (Neue Montreal) |
|---|---|---|
| 1 | *Why your probiotic isn't working* | A 3-minute explanation. |
| 2 | *You swallow it.* | 10 billion live bacteria, ready to fix your gut. |
| 3 | *Then your stomach acid happens.* | pH 1.5-3.5. Most die in 5 minutes. |
| 4 | *Bile salts kill what's left.* | The small intestine is the second wall. |
| 5 | *The survivors don't colonize.* | They pass through your gut. They never stay. |
| 6 | *Postbiotics skip all three walls.* | (+ SK wordmark, no CTA) |

### THE HIGGSFIELD PROMPTS (visuals only, phone-snap backgrounds per slide)

```
Slide 1 (hook):
"Shot on iPhone, candid. A single probiotic capsule resting on a clean wooden kitchen counter, soft morning light, large negative space above the capsule, slightly imperfect framing, 1:1 aspect ratio. No text, no captions, no overlays, no graphics, no typography."

Slide 2 (swallow it):
"Shot on iPhone, candid. A hand holding a probiotic capsule near a glass of water on a wooden counter, soft morning light, negative space in the upper portion of the frame, 1:1 aspect ratio. No text, no captions, no overlays, no graphics, no typography."

Slide 3 (stomach acid):
"Shot on iPhone, candid. A clear glass beaker with amber-colored liquid on a wooden kitchen counter, soft natural light, science-experiment vibe but domestic, negative space around the beaker, 1:1 aspect ratio. No text, no captions, no labels, no overlays, no graphics, no typography."

Slide 4 (bile salts):
"Shot on iPhone, candid. Probiotic capsules dissolving in a clear liquid in a glass jar on a wooden counter, soft natural light, casual composition, negative space around the jar, 1:1 aspect ratio. No text, no captions, no overlays, no graphics, no typography."

Slide 5 (colonization):
"Shot on iPhone, candid. Top-down view of pill capsules scattered on a wooden kitchen counter, casual arrangement, soft natural light, negative space in upper portion, 1:1 aspect ratio. No text, no captions, no overlays, no graphics, no typography."

Slide 6 (mechanism reveal):
"Shot on iPhone, candid. Gut Balance amber glass jar on a wooden kitchen counter, soft morning light, single product in frame, slight negative space for wordmark, 1:1 aspect ratio. The product label is the only text in the image, no additional text, no captions, no overlays, no extra graphics."
```

### Layout pattern
- Text sits in the negative-space area of each photo
- Caslon Condensed headline (large) + Neue Montreal body (smaller)
- Optional single yellow accent (#fcb348) on mechanism words (stomach acid, bile salts, postbiotics)
- SK wordmark bottom-right on slide 6 only

### Production workflow

1. Lift the science from `competitive-gaps.md` + brief's `benefit_callouts`
2. Generate 6 phone-snap backgrounds in Higgsfield
3. Open Canva "IG Carousel Native" template, drop backgrounds per slide
4. Drop slide copy in the negative-space areas, Caslon + Neue Montreal
5. Add yellow accents on key words
6. Add SK wordmark on slide 6 only
7. Export 6 × 1080×1080 PNGs in carousel order

---

## IG variant, Snow White editorial alternative (occasional)

When you want the premium editorial feel (announcements, dense content):

- Snow White background (#fefcf6) on every slide
- Same Caslon + Neue Montreal typography
- Single yellow accent on mechanism words
- Editorial Minimalism, generous whitespace, no decorative borders
- Optional hand-drawn line illustrations if they add clarity (stomach diagram on slide 3, etc.)

Workflow: skip the Higgsfield step. Just Canva. total.

Use this maybe 1 in 4 carousels.

---

## TikTok native variant

**Output:** 6-slide TikTok slideshow OR carousel video · **Platforms:** TikTok + IG Reels slideshow · **Lift:** very_low

Same 6-slide narrative as IG variant. Different production:
- Same Higgsfield prompts (phone-snap backgrounds), just 9:16 vertical instead of 1:1
- Text overlay uses **system font (Helvetica)**, NOT brand serifs
- Text added in CapCut (or TikTok app), not Canva

### TikTok-variant Higgsfield prompts
Change `1:1 aspect ratio` to `9:16 vertical` in each prompt above. Everything else stays the same.

### Production workflow (TikTok variant)

1. Lift same 6 slide copy from IG variant (reusable across both)
2. Generate 6 phone-snap backgrounds in Higgsfield (9:16)
3. Drop into CapCut, add text overlay per slide using **Helvetica/system font**
4. Export 6 × 9:16 PNGs OR single video slideshow

### Critical
TikTok variant uses SYSTEM font, not brand serifs. Brand-typography on TikTok reads as "ad" → gets scrolled.

---

## Pitfalls (both variants)

- More than one point per slide, kills the rhythm. Strict one-thought-per-slide.
- Adding a CTA, destroys the educational frame. Brand mark on final slide is enough.
- Going too "science textbook", keep it conversational
- Skipping the build, first 5 slides must earn slide 6. Don't collapse.
- Photo backgrounds with no negative space, text gets lost. Regenerate with more clear area.
- Plain Snow White every time, too "ad"-feeling for organic. Default to phone-snap.
- **TikTok variant:** using brand typography → reads as ad. Use system font.
- **IG variant:** plain Snow White when text density doesn't require it, defaults toward "ad" feel
