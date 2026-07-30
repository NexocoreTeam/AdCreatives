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

Mechanical test: `adc catalog --client <slug>` crawls the FULL catalog and
clusters it by customer problem. The cluster count IS the number of pipeline
scopes (1 cluster = single run; N clusters = N runs sharing the brand +
competitor layers), and the printed rule-1 verdict makes the call explicit.
The census also feeds the strategy matrix and brief prompts, so angles are
written knowing the whole range instead of only the enriched heroes.

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

**Provider default:** Use Firecrawl as the default managed crawler/page fetcher
for AdCreatives research. Do not block this repo's workflows on a Brave Search
API key. Firecrawl handles known-page crawling/rendered extraction; Exa handles
broad web sentiment and Amazon candidate discovery; Apify/official APIs handle
platform-specific comment/review sources.

Per-source expectations:

- **On-site reviews** — fallback chain: vendor APIs (Okendo / Yotpo /
  Judge.me — deep, hundreds of reviews) → JSON-LD markup → schema.org
  microdata in the rendered page (with FIRECRAWL_API_KEY set, competitor
  pages are fetched JS-rendered, so widget output without a public API is
  still visible — expect the visible 5-10 reviews, not the archive). Some
  premium brands publish no on-site reviews at all; the bundle `notes` and
  `adc status` will say so. That's a finding, not a failure — lean on the
  other layers.
  - **Judge.me has a second tier:** some stores render reviews only via the
    widget's runtime XHR — nothing in static or JS-rendered PDP HTML, no
    public token on the page, and the classic widget endpoint returns 0
    (found live on a 14K+-review store). The pipeline falls back to the
    widget's own data source (`api.judge.me/reviews/reviews_for_widget` —
    the same path on judge.me 404s) using the `*.myshopify.com` domain +
    numeric Shopify product id recovered from the PDP HTML (ShopifyAnalytics
    meta; `/products/<handle>.js` and `/products.json` can 404/500 on
    rate-limited stores). When the tier can't run or still gets 0, the
    reason lands in the diagnostics (`notes` / product-dive output).
- **The CLIENT's own reviews** — when the client's store shows a review
  count but the pipeline pulls 0 (e.g. Judge.me with `disable_web_reviews`
  set: token-locked API, nothing rendered in the DOM — found live on
  Expand Furniture), do NOT scrape harder. The client owns that data: have
  them export reviews from the vendor dashboard (Judge.me/Okendo/Yotpo all
  export CSV) and drop it into `clients/<slug>/voc/` as
  `[{"rating": N, "body": "..."}]` JSON. First-party export beats any
  scrape in completeness and is zero-risk.
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

When automated VOC is thin, run the automation-first Audience Conversion Report
workflow in `docs/audience-conversion-report.md` before calling research
complete. It adds a generated raw-data dump, OpenClaw/browser-assisted
GigaBrain/Reddit/forum mining when APIs are thin, own and competitor reviews,
TikTok/comment questions, product-USP context, behavior/moment extraction,
exact customer terminology, and a source-truthed research document that can
feed personas, gaps, scripts, and briefs. Manual copy/paste is the fallback,
not the default.

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

---

## 8. Copied statics default to simple one-pass emulation plus Magic Text

**Rule:** When the operator asks to copy, emulate, or lightly remix an existing
static ad, start with a simple natural-language one-pass Higgsfield prompt using
the reference ad and client product image. Do not default to JSON prompts,
multi-pass workflows, or complex planning unless the first output fails or the
operator explicitly requests a controlled test.

The prompt should preserve the winning ad mechanic and visual polish while
changing small surface identifiers so the output is not a clone:

- background color, material, or texture
- lighting warmth or surface treatment
- kitchen backsplash, wall, cabinet, or countertop colors
- small background objects, e.g. coffee maker instead of plant
- model reference, hair color, clothing, scenery, or supporting props
- product replacement and brand-owned color accents

The product reference controls product identity, packaging, proportions, and
label accuracy. Higgsfield should re-light and re-integrate that product into
the reference scene so it matches lighting direction, shadow softness, color
temperature, contrast, perspective, and depth of field. Explicitly ask it to
remove halos, cutout edges, pasted-on looks, mismatched lighting, and
source-image artifacts from the product reference. Do not let it redesign,
warp, or hallucinate the product label.

After the image is approved, upload it into Canva and use **Magic Text** first.
Only the ad copy should become editable. Keep the rest of the generated image
intact unless broader product/model cleanup is required.

Use Magic Layers only when Magic Text is insufficient, and protect product
labels first with Magic Grab if the product/package matters.

---

## 9. Static concepts need a source mix, not a blank brainstorm

**Rule:** Static ad batches should start from the Audience Conversion Report,
a selected persona/avatar, a selected mass desire or core focus, and a labeled
concept source mix. Do not move from generic research straight into image
generation.

Use `docs/phase-2-static-briefing-workflow.md` and, when useful, scaffold the
working file with:

```text
adc audience-conversion phase2-static --client <slug> --product <product-id>
```

The static briefing workbook is required before production when the request is
broad, research-led, or concept-batch oriented.

Phase 2 gate order:

1. Audience research synthesis: psychographics, problems/desires,
   behaviors/moments, objections, exact terminology.
2. Avatar selection.
3. Mass desire or core-focus selection.
4. Direct competitor and adjacent-niche ad pull/analysis.
5. 70 / 20 / 10 source mix.
6. Angle bank by awareness level.
7. Operator-selected visual format/template.
8. Template-specific benefits, negatives, and headlines.
9. Static Mistake Filter.
10. Approval before production.

Default concept mix:

1. **70% proven outside references** â€” direct competitors, category leaders,
   adjacent niches, Foreplay, Apify/Meta/TikTok ad scrape, Pinterest mechanics,
   and approved ad-library teardowns.
2. **20% internal winners** â€” client or agency hooks, templates, formats,
   offers, overlays, or visual mechanics that have worked before.
3. **10% new swings** â€” fresh hypotheses, trend plays, unusual hooks, or
   strategist intuition.

Every concept should identify:

- the persona/avatar
- the source-backed insight from Phase 1
- the awareness level
- the source type (`direct_competitor`, `adjacent_niche`, `internal_winner`,
  `new_swing`, etc.)
- the evidence level (`high`, `medium`, `low`)
- the template/reference/mechanic being used

Adjacent niche mining is required for concept diversity. Pull roughly 10 direct
or category examples and 10 adjacent niche examples before selecting concepts,
unless the category is already saturated with high-quality references.

For template-based statics, generate an angle bank before editing the template.
The angle bank should include awareness-level copy options, benefits,
negatives/comparison bullets, objections handled, proof needed, and exact
customer phrasing. Image tools can help replace visual assets; final text
belongs in Canva/local layers when iteration matters.

Copy must be verbatim-first when raw customer language exists. For important
hooks, first lines, benefits, negatives/comparison bullets, and objection
callouts, capture the raw quote or exact phrase, source type, ad-ready version,
and what changed. The goal is to say the customer's own words back in ad form,
not translate them into generic marketing language.

When analyzing pulled competitor or adjacent ads, do not only summarize. Extract
the ad mechanic, what works, what they did wrong, missed opportunities, and how
the mechanic can be emulated for the selected avatar and mass desire.

---

## 10. Static ads must pass the mistake filter before production or export

**Rule:** Do not generate, export, or send a static ad that is hard to read,
generic, merely promotional, or built from clever copy instead of source-truthed
customer language.

Every static must pass these six checks:

1. **One-second readability.** The main hook must be legible while the viewer
   is half-scrolling. Tiny text, low contrast, busy backgrounds behind copy,
   and white-on-yellow style combinations fail.
2. **Moves the sale forward.** The ad must do more than announce a sale or
   offer. It should clarify the mechanism, handle an objection, dramatize a
   moment, explain the difference, or make the viewer feel understood.
3. **Not generic.** If any competitor could say the same thing, rewrite with
   proof, specificity, mechanism, exact customer language, or a concrete use
   case.
4. **Benefit depth.** Push beyond level-one benefits. Translate "more energy"
   into the daily-life, emotional, identity, or lived-moment payoff when the
   research supports it.
5. **Research before cleverness.** Do not ship cringey wordplay or
   copywriter-clever hooks unless the line is grounded in a real pain, moment,
   objection, failed solution, or customer phrase.
6. **Authenticity match.** Match the visual polish to the claim. Use polished
   product statics for proof/mechanism/comparison and native UGC statics for
   relatability, routine, skepticism, and lived moments.

Treat failures as upstream bugs in the concept, copy, reference choice, or
layout. Fix the concept before spending on image generation or sending the
asset for review.

---

## 11. Foreplay emulation batches require post-emulation ad cards

**Rule:** When the operator provides a large Foreplay library for copied or
emulated statics, do not force the Phase 2 angle/copy onto the references before
seeing the emulated visual containers. First create the candidate visuals, then
make an ad card for each one.

Default sequence:

1. Build the idea pool from the Audience Conversion Report.
2. Pull/import the Foreplay library.
3. Tag each ad by mechanic.
4. Run Simple Natural-Language Emulation with reference ad + product image.
5. Make small surface changes so the result is not a clone.
6. Upload to Canva and use Magic Text for editable copy only.
7. Create a post-emulation ad card.
8. Match the angle/copy to the ad card.
9. Get approval before finalizing.

For UGC, selfie, model, hand-held, or creator-style Foreplay references, the
simple Higgsfield prompt must include short imperfect phone-photo realism
language. Use blunt wording such as: "Make this look like a real low-effort
iPhone selfie, not an AI image. Preserve the pose and product-in-hand layout,
but use a different person. The camera should feel ordinary and slightly bad:
soft front-camera focus, dirty lens haze, flat indoor light, muted color, mild
compression, no HDR, no beauty-camera skin, no visible pore detail, no crisp
hair strands, no glossy sharp edges. Make it feel like a casual photo from
someone's camera roll." Do not paste long beauty/skin/camera explanations by
default.

When a Foreplay/reference ad contains a recognizable person, the prompt must
replace the model identity, not just recolor hair or clothing. Preserve the
winning pose, crop, camera source, lighting direction, and hand/product
placement, but keep the instruction short: use a different creator, not the
same model with styling changes. Change face, hair, wardrobe, accessories, and
room details enough that the output clearly reads as a different person. If
available, use a separate person/model reference for the new creator's look.

For clients with approved reusable models, especially Saved by Grace, the
approved model/product source is the identity reference and the Foreplay ad is
only the scene/mechanic reference. Treat image roles this way:

1. Image 1 = approved client model/product image.
2. Image 2 = Foreplay/reference ad.
3. Replace the specific person/product role in image 2 with the person/product
   from image 1.
4. Preserve image 1's likeness/product truth while matching image 2's lighting,
   shadows, contrast, perspective, and camera style.

If the client only has a flat lay for the product but the reference needs a
model, make an approved on-model product asset first, then use that on-model
asset as image 1. Do not ask Higgsfield to borrow or keep the reference ad's
model identity.

The ad card must capture scene, mechanic, persuasion mechanism, product role,
existing text zones, approximate text capacity, awareness fit, best/bad angles,
exact VOC phrases that can fit, Canva edit notes, 1:1 crop safety, and Static
Mistake Filter risks.

If the selected angle needs more text than the visual can carry, choose a
different angle or a different candidate ad. Do not cram dense mechanism copy
into a lifestyle/UGC visual or force a long note into a one-headline layout.
