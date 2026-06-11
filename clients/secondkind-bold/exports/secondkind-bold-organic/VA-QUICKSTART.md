# VA Quickstart, SecondKind Bold Organic

You are making organic content for **SecondKind Bold** (postbiotic gut-health brand). No shoot days, no human talent, AI tools + existing UGC + matrix briefs only.

This is a 1-page primer. Read it once, then bookmark.

## What you have

| File | What it is |
|---|---|
| `matrix.md` | The creative matrix, 52 entries you pick from. Scan it like a menu. Each entry has an ID (`pain-005`, `love-003`, `hook-002`, `wish-004`). |
| `formats.yaml` | 80 organic content frames from Sarah Levinger (game show, mystery, comedy, etc.) |
| `production-recipes.yaml` | 9 ways to actually produce content without a human shoot |
| `recipes/` | Worked example per recipe with copy + visuals + Higgsfield prompts + workflow |
| `avatars/` | Where your canonical AI avatar lives (generate once before making AI UGC videos, see `recipes/ai-ugc-influencer.md`) |
| `SKILL.md` | The orchestrator, Claude reads this when you invoke the skill |

## The workflow

### 1. Open `matrix.md` and pick a matrix ID

Scan the matrix. Pick one entry you want to address. Note its ID, `pain-005`, `love-003`, `hook-002`, etc.

Tip: most pain entries land hardest. Start there.

### 2. Paste a prompt template

**🟢 Most common, 3 variations to choose from:**
```
Use secondkind-bold-organic. Give me 3 variations of organic content addressing pain-XXX.
```

**🟢 Single concrete piece (when you know what you want):**
```
Use secondkind-bold-organic. Pull pain-XXX. Give me one concrete organic piece using the [recipe-name] recipe.
```

**🟢 By pain description (when no ID in mind):**
```
Use secondkind-bold-organic. We need organic content addressing [the pain in plain English]. Give me 2-3 options.
```

**🟢 Recipe constraint (you know what production type you want):**
```
Use secondkind-bold-organic. Pull pain-XXX. Use the not-x-objection recipe.
```

Recipe names (paste-able):
- `text-overlay-monologue`, short TikTok love letter (35-75 words, callout + fact + easy close)
- `text-overlay-pov`, 1-2 line flex/POV short (candid-motion clip or locked-camera variation)
- `david-goliath-no-intro`, calling out the probiotic industry
- `pixar-ai-slop`, AI animation (needs VFX skill)
- `not-x-objection`, *"We're not probiotics. We don't want to be."*
- `ugc-cutup-voiceover`, existing UGC + AI voiceover
- `static-educational-card`, IG carousel + TikTok native variant
- `native-ai-product-shot`, phone-snap product photos
- `ai-ugc-influencer`, hyperrealistic AI avatar speaking (uses canonical SK-Bold avatar from `avatars/`)
- `engagement-prompt`, comments/poll-driving prompts (1×/week feed, 2-3×/week stories)

### 3. Read Claude's output

You'll get something like:

> **Matrix entry:** pain-001, probiotic efficacy plateaus
> **Recipe:** TikTok Love Letter
> **Opener:** *"Girls, your gut lining rebuilds itself about every week."*
> **Body:** [35-75 word, 3-beat letter: callout + fact → emoji-led "supports" lines → product + easy close]
> **Visual:** [specific scene description] · **Fallback:** [stock alternative]
> **Brand-intro point:** final beat (~60-75% in)
> **Production workflow:** 1. … 2. … (total )
> **Rule check:** all pass ✓

The output is **ready to ship**. The headline, body copy, and visual direction are all final. You produce it with your AI tools (Higgsfield, fal.ai, ChatGPT, ElevenLabs, CapCut, Canva, etc.) and post.

### 4. Iterate or go deep

After variations, you can:
```
Go deep on #2. I need full copy and visuals.
```

Or if a piece needs adjustment:
```
Same recipe, but make the opener punchier, more like the "still bloated by 7pm" energy.
```

## The five rules you can't break

1. **No prohibited terms.** SKILL.md has the full list. Most important: never use *miracle, life-changing, journey, ritual, transform your, holistic*. If Claude includes one, push back.
2. **Brand-intro-delay.** The SecondKind brand does NOT appear in the first 30% of any piece. Check the brand-intro-point in the output.
3. **Voice:** confrontational, declarative, science-armed. Not cheerful. Not influencer-y.
4. **POV shorts MUST use anchor + variation pattern.** Locked camera, one element changes across cuts. Never static clip + text.
5. **No CTA.** No "shop now," no "link in bio," no hashtags. Brand mark in corner is enough.

## What this skill does NOT do for you

- Generate the actual images/videos, you do that with your AI tools
- Schedule the post, you decide when to ship
- Track performance, separate analytics workflow
- Make paid ads, that's a different pipeline

## When you're stuck

- Try a different recipe for the same matrix entry, *"same pain-XXX but try static-educational-card instead"*
- Ask Claude to explain a recipe, *"how does anchor + variation work for text-overlay-pov?"*
- Look at the worked example in `recipes/<recipe-name>.md`, every recipe has a concrete example you can adapt

## One-time setup before AI UGC

Before you make any `ai-ugc-influencer` videos, you need to set up the canonical SK-Bold avatar in **Higgsfield Soul ID**. Do this ONCE.

1. Open `recipes/ai-ugc-influencer.md`
2. Follow the "Avatar generation (one-time setup)" section
3. Save the Soul ID in Higgsfield as "SK-Bold Canonical Avatar"
4. Also download the reference image to `avatars/sk-bold-canonical-avatar.png`

From then on, every AI UGC video uses this same Soul ID. Higgsfield maintains character consistency automatically, same face, hair, cardigan, lighting tone across every scene.

## What good looks like

A week of organic posts that all address different matrix entries, use 2-3 different recipes, never break the brand voice rules, and never introduce the brand in the first 30%. You should be able to produce 5 pieces a week
