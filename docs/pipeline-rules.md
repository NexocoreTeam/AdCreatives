# Pipeline rules

Operating principles for the AdCreatives strategy + brief generation pipeline.
These rules encode hard-won lessons that should NOT be relaxed without
explicit user discussion.

---

## 1. ONE product per run when products solve different problems

**Rule:** When a brand sells multiple SKUs that target different pains
or jobs-to-be-done, run the pipeline for ONE product at a time. Each product
gets its own competitor list, gap map, personas, psychology profile, strategy
matrix, and brief set.

**Why:** Personas, gaps, and angles all collapse into mush when forced to
straddle two different value propositions. A persona for "bloating relief"
is fundamentally different from a persona for "stress and sleep support" —
both real, both important, but their pain language, current solutions,
trigger events, and psychology profiles diverge.

### When to run per-product (separate runs)

✅ **Supplements with distinct mechanisms / outcomes**
   - SecondKind: run Gut Balance separately from Mood Balance
   - Pendulum: run Glucose Control separately from Akkermansia Daily

✅ **Skincare with distinct concerns**
   - Run anti-aging serum separately from acne treatment

✅ **Food brands with distinct occasions**
   - Magic Spoon Treats (snacks) separately from Magic Spoon Cereal

### When to run per-brand (single run)

✅ **Categories where products share mechanism / function**
   - Clothing brands (Reformation, WISKII Active): full-brand run is fine
   - Footwear (HIKE Footwear): one run covers the product line
   - Single-mechanism beverage lines (Olipop Classic Root Beer + Olipop Vintage Cola — same prebiotic-soda promise)

✅ **Single-hero-product brands**
   - Magic Spoon Original Protein Cereal (one product line, several flavors)
   - Caraway non-stick pan

### How to decide quickly

Ask: "Would the personas for product A be substantially different from the
personas for product B?" If yes → run separately. If no → run once.

If you run a brand with mixed products as a single pass, expect to throw out
the result and re-run per-product.

---

## 2. Calibrate persona awareness to ACTUAL market awareness

**Rule:** A persona's `awareness_level` must reflect what the audience
actually knows about the brand's category — not the brand team's internal
vocabulary.

**Why:** Most brand teams talk about their category as if it were already
established. The audience doesn't. If the brand introduces a novel mechanism
or category name, default to `problem_aware` framing — not `solution_aware`.

`problem_aware` is correct when:
- The audience has the pain
- They've tried the LEGACY category (probiotics, retinol, greens powders) and
  it failed or underwhelmed
- They have never searched for the brand's NEW category name

`solution_aware` is correct only when:
- Consumers actively type the category name into search
- Multiple competitors share the category name in their own marketing
- The category has measurable consumer demand (Google Trends, search volume)

When in doubt, default to `problem_aware`. Honest pain framing always
out-converts sophisticated evaluation framing for a category the audience
hasn't heard of yet.

---

## 3. Gap map: PRODUCT gaps only, never operational

**Rule:** The competitive gap map must surface only PRODUCT-LEVEL gaps.
Operational gaps (customer service, subscription billing, shipping, returns,
website UX) are dropped on the floor, no matter how loud the customer voice
data is.

**Why:** Paid creative converts on what the PRODUCT does. Operational claims
("we reply fast," "easy returns") don't move people to add to cart for
supplements, skincare, or apparel — those are post-purchase concerns that
matter for retention, not acquisition.

✅ Surface gaps about: efficacy, results timing, mechanism credibility, side
effects, sensory experience, routine fit, outcome durability, category-level
skepticism.

❌ Drop gaps about: customer service quality, subscription billing horror
stories, shipping speed, return policies, refund processing.

Also drop "table-stakes proof points where we can't out-execute" — e.g.,
don't claim ingredient transparency as an edge when both we and competitors
use branded compounds the consumer can't independently verify.

---

## 4. Brief generation: NEVER name competitors

**Rule:** Competitor brand names must NEVER appear in hooks, body copy,
headlines, callouts, CTAs, or visual direction. No exceptions, no "indirect"
references that obviously point at one brand.

❌ "Stop wasting money on Seed"
❌ "Better than AG1"
❌ "Move over, Ritual"
❌ "What Pendulum doesn't tell you"

✅ "The probiotics you've tried"
✅ "Live-bacteria approaches"
✅ "Other gut supplements"
✅ "The category that hasn't worked for you"

**Why:** Direct competitor naming invites comparison battles, unauthorized
FUD, legal exposure, and the appearance of insecurity. Always abstract to
the CATEGORY (or the MECHANISM) — that's where the persuasion lives anyway.

The competitive gap map can REFERENCE competitor names internally — that's
background context for the strategist. Translate to category-level language
before it lands in any customer-facing field.

---

## 5. Don't lead with operational positioning

**Rule:** Hooks and angles must lead with PRODUCT promises, not company
promises.

❌ "30-day money-back guarantee" (lead)
❌ "Free shipping over $60" (lead)
❌ "Easy cancellation, no trap subscription" (lead)
❌ "Our founder reads every email" (lead)

✅ "92% felt less bloated in 2 weeks"
✅ "Postbiotics deliver what probiotics promise"
✅ "Calm gut, clear head"

Operational angles can SUPPORT a product-led hook (the guarantee as a
risk-reversal kicker AFTER the promise lands), but they never lead.

---

## Putting it together

These rules compound. The pipeline's job is to produce briefs that:
1. Are scoped to ONE product (rule 1)
2. Speak to personas at their actual awareness level (rule 2)
3. Exploit real product gaps, not noise (rule 3)
4. Never name competitors (rule 4)
5. Lead with what the product does (rule 5)

When a brief violates any of these, treat it as a bug — fix the upstream
prompt, don't band-aid the output.

---

## 6. Match research sources to where the category's VOC actually lives

**Rule:** Before running the research layers, decide per category which
sources will carry the VOC load — and configure competitors.yaml
accordingly. Do not treat an empty layer as "research done".

**Why:** The Zoka Coffee run produced 0 competitor reviews, 0 social
comments, and no Amazon data — not because commands crashed, but because
the sources were mismatched to the category (specialty coffee VOC lives on
Reddit, YouTube reviews, and brand-owned review widgets, not Amazon or
Trustpilot).

Per-source expectations:

- **On-site reviews** — vendor APIs (Okendo / Yotpo / Judge.me) plus a
  JSON-LD fallback. Some premium brands publish no on-site reviews at all;
  the bundle `notes` and `adc status` will say so. That's a finding, not a
  failure — lean on the other layers.
- **Amazon** — `amazon_urls` must be explicit; the pipeline does NOT
  auto-discover Amazon listings. Only add URLs when the exact competitor
  product is genuinely sold (and reviewed) on Amazon; otherwise skip the
  layer.
- **YouTube** — prefer `youtube_search_queries` ("<brand> review",
  "<brand> vs <competitor>") or explicit `youtube_video_ids` over
  brand-owned handles. Brand uploads are weak VOC: low comment volume,
  disabled comments, or fan noise.
- **TikTok / Instagram** — same logic: `tiktok_search_queries` or explicit
  post URLs beat brand handles.
- **Trustpilot** — the `trustpilot-*` Exa queries return page-level search
  snippets (sentiment), NOT parsed review objects with star ratings. Treat
  them as directional, and don't count them as structured review mining.
- **Reddit** — Exa no longer serves reddit.com (403 SOURCE_NOT_AVAILABLE);
  the pipeline falls back automatically, in order: official Reddit API
  (needs valid `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET`; new apps go
  through Reddit's Responsible Builder review) → Apify actor bridge
  (`trudax/reddit-scraper-lite`, needs `APIFY_API_TOKEN`, pay-per-result).
  Prefer landing the official creds — that path is sanctioned and free; the
  Apify bridge is public-page scraping, same posture as the TikTok/IG
  layers. If both are unusable the reddit-* layer stays empty and the
  failure records under `research/exa/errors/` say exactly why.

After any research command reports 0 items, check the diagnostics before
moving on: `research/exa/errors/`, `research/<platform>-diagnostics/`, and
the `notes` field in `research/competitor-reviews/*.json`.

---

## 7. Static ad copy should sound like a person, not a strategy doc

**Rule:** For cold social statics, UGC-style ads, and competitor-inspired
formats, the top line must use plain customer language before any mechanism
or proof point appears.

**Why:** People do not stop scrolling for category education. They stop when
the ad sounds like a thought they already had, a question they would actually
ask, or a problem they can recognize without learning brand vocabulary first.

The default formula:

1. Top line = lived problem, simple curiosity, or human realization.
2. Support line = plain mechanism or product explanation.
3. One ad = one point.

Good cold-static patterns:

- "Still bloated after taking probiotics?"
- "Are your probiotics actually doing anything?"
- "I thought probiotics were supposed to help."
- "Maybe probiotics weren't the answer."
- "Postbiotics made gut support simple."
- "Gut support that doesn't need live bacteria to survive digestion."

Avoid using internal strategy language as the main hook:

- "Mechanism failure"
- "84-day RCT" unless the format is explicitly science/proof-led
- "Bioactive compounds. Already active."
- "Colonization"
- "Viability"
- "Gut lining"
- "Stack got shorter"
- "Why you should swap probiotics for postbiotics" as the top-line hook

Science, statistics, and mechanism still matter, but they must earn their way
into the second line or body copy. If the viewer needs category knowledge to
understand the hook, rewrite it.

When adapting competitor or reference ads, use the structure and persuasion
logic without cloning the surface. Change obvious visual identifiers: color,
font treatment, layout rhythm, marker color, product placement, and copy
cadence. In comparison ads, use a generic category product on the competitor
side and the client product only on the client/postbiotic side.
