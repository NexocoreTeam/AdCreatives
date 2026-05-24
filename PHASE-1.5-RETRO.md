# Phase 1.5 Retro — Lessons learned during the production push

*Captured 2026-05-24, after the creative build phase landed (9 final ads × 3 aspect ratios = 27 creatives, ad copy in voice, all PIL/hf-web pipelines exercised in anger).*

This retro covers the lessons from **after** `PHASE-1-RETRO-IMPLEMENTATION.md` shipped. That retro built the hybrid UGC pipeline, brief validation, editorial design rules, and the rest of the infrastructure. This one captures what we learned **using** that infrastructure to actually produce ads.

---

## Top friction since the last retro

### 1. Ad copy was lacklustre because voice.md taught compression for every slot

**What happened:** the first pass of ad copy treated Meta primary text like a callout slot (under 30 chars). Competitor performers run 100-300 word storytelling primary texts. The voice file had no slot-specific guidance for long-form — it taught the same compression rules for every slot.

**Cost:** one full rewrite across 9 ads. No real money, but significant conversation overhead.

**Fixed in this session:** added new **META PRIMARY TEXT (long-form)** section to `library/voice.md` with the 4-beat arc structure, paragraph break rules, `✅` / `❌` emoji as bullet markers, worked example, ban on Shop Now CTAs in body copy.

### 2. Em-dash overuse — voice.md actively taught it

**What happened:** the X-gone signature pattern (`"Bloat — gone"`) and the negation-as-identity move (`"Not a crib — a way to X"`) both relied on em-dashes throughout. You banned them mid-session as not on-brand for native ad copy.

**Fixed in this session:**
- Em-dash added to forbidden-punctuation list in `library/voice.md` with a "banked from production feedback" provenance note
- X-gone pattern renamed to **X. Gone.** (period-stop form) — keeps the same rhythm without the dash
- Move 1 (negation as identity) examples updated
- Category-adaptation example banks updated (postbiotic + biohacker)

### 3. Six iterations on Earned Confidence because I built one variant at a time

**What happened:** v1 calm → v2 marigold accent → v3 full marigold bg → v4 seeds vs harvest → v5 specimen debris → v6 memento mori. Each step driven by "try something else." If I'd **proposed 5 directions upfront and built 3 in parallel**, we'd have been done in 1-2 rounds instead of 6.

**Same pattern on hook-001:** v1 dying capsule → v2 test tubes (too clever) → v3 before/after → v4 cascade → v5 open capsule split → v6 marigold serif (final ship was v5/v6).

**Cost:** ~$8-10 in unnecessary generations + ~30 minutes of conversation overhead per concept.

### 4. pain-006 v2 shipped with a headline/body mismatch that no validator caught

**What happened:** headline promised *"3 receipts the probiotic industry hides"* but body delivered *our trial results*. A bait-and-switch — you caught it on visual review. Required splitting into v3 (industry-hides) and v4 (trials-checked) — two ads instead of one.

**Why it slipped:** `validators/brief_text_validator.py` (from last retro) catches **cross-concept text leakage** (a phrase from Concept 2 appearing in Concept 7) but not **headline-vs-body premise alignment**.

### 5. Validated_assets warning fires but doesn't auto-fix

**What happened:** every hf-web call using `gut-balance-product.png` triggered the Posthiotic-typo warning. The warning is correct but actionless — the user can't easily fix the source asset (brand-level print run). We had to remember to add "fix label to read Postbiotic" to each prompt manually. Most generations shipped with the typo.

### 6. No Phase 1 launch checklist

**What happened:** by end of Phase 1 we had 9 ads × 3 aspect ratios = 27 creatives, 9 copy specs, brand voice locked, but **no document** that walks through Meta Ads Manager upload: ad set structure, audience setup, budget allocation, day-3 kill criteria, scaling triggers. Phase 1 strategy + creative is done; launch readiness is implicit.

---

## Improvements ranked by impact

### 🥇 Top tier (Tier 1)

**1. voice.md updates — DONE this session** ✅
- Em-dash banned in copy (preserved in prose documentation)
- Emoji rules formalized: `✅` / `❌` / `🚫` / `🧪` / `↓` only, sparing use, bullet-markers for long-form
- META PRIMARY TEXT (long-form) section added with 4-beat arc + worked example
- X-gone pattern rewritten to X. Gone. (period-stop)
- All changes persist in Python `adc remix` pipeline runs going forward.

**2. Headline-vs-body premise validator** *(this session — agent task #2)*
Extends `validators/brief_text_validator.py`. New check: does the body deliver on what the headline promises? Implementation: cheap Claude call per brief save with a small prompt that returns alignment score + reasoning. Warns on mismatch (≤0.5 alignment); blocks if explicitly contradictory.

**3. `auto_fix_prompt_addition` field on `validated_assets.yaml`** *(this session — agent task #3)*
```yaml
known_issues:
  - file: "_refs/gut-balance-product.png"
    issue: "label reads 'Posthiotic' instead of 'Postbiotic'"
    severity: warning
    auto_fix_prompt_addition: |
      IMPORTANT: change the label text on the product to read 'Postbiotic'
      (not 'Posthiotic').
```
`adc edit` and `adc ugc-ad` auto-append this to the prompt when the asset is used. Warning becomes self-healing instead of a dead-end.

### 🥈 Mid tier (Tier 2)

**4. "Propose variants upfront" workflow guidance**
When user asks "try something different," default to **proposing 3-5 sharp directions in chat first** before building any single variant. Build in parallel only after user picks. Could be a Claude Code skill `creative-variant-explorer.md` or just a documented pattern. Would have saved $8-10 + significant time on hook-001 and Earned Confidence.

**5. "Lessons banked" workflow for voice.md evolution**
When patterns break in production (like em-dash overuse this session), bank the learning in `voice.md` with a structured `### Banked YYYY-MM-DD` block: what broke, why, what changed, replacement pattern. Already informally done in this session's forbidden-punctuation block — could formalize as a discipline.

**6. Phase 1 launch checklist template**
`docs/phase-1-launch-checklist.md` template that gets copied to `clients/<slug>/phase-1-launch-checklist.md` per client. Walks through ad set creation, audience targeting, budget allocation, naming convention, copy-field-to-asset mapping, day-3 / day-7 kill criteria, escalation triggers. Closes the "creative ready → campaign live" gap.

### 🥉 Bottom tier (Tier 3)

**7. Parallel hf-web orchestration**
The aspect-ratio agent took ~32 min for 14 generations sequentially. With parallel workers (respecting hf-web's actual rate limits — likely 2-3 concurrent), it'd be ~10-15 min. Defer until volume justifies.

**8. Visual concept library per brand**
For "scroll-stop visual ideas" we keep brainstorming from scratch. A `clients/<slug>/visual_concepts.yaml` cataloguing proven scroll-stop visuals (seeds-vs-harvest, specimen-debris, memento-mori, capsule-cascade, etc.) with notes on what they signify and which mechanism they activate. Builds over time. Editorial design rules already capture this for backgrounds — extending to scroll-stop visual concepts is the next layer.

---

## What landed this session

- `library/voice.md` updates (Tier 1 #1) ✅
- `PHASE-1.5-RETRO.md` (this doc) ✅
- Agent dispatched to implement Tier 1 #2 + #3

## What's deferred

- Tier 2 #4-6 (workflow + checklist work) — quick wins, do in next session
- Tier 3 #7-8 (parallel hf-web, visual concept library) — wait for justifying volume

---

## Provenance

| Item | Source |
|---|---|
| Voice rule changes | Banked from your in-session feedback 2026-05-24 |
| Iteration count on Earned Confidence + hook-001 | Counted from this session's transcript |
| Cost estimates | Tracked from `adc edit` calls during session |
| Mismatch on pain-006 v2 | Caught by you on visual review of the iPhone Notes screenshot |
| Validated_assets dead-end pattern | Observed across ~10+ `adc edit` calls this session that all fired the Posthiotic warning |
