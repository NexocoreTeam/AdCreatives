# Tier 3 Social Sourcing — UGC Workflow

How to feed the creative matrix with social-comment signal that actually
moves the needle. Documents the manual + automated paths and when to use
which.

> TL;DR: For most consumer categories, **UGC review videos** (users reviewing
> the brand) carry far richer product-experience signal than **brand-owned
> posts** (logistics noise). Always source UGC first.

---

## The verdict that drove this design

Tested on `secondkind` with 165 IG comments from brand-owned posts vs 46
TikTok comments from UGC review videos:

| Source | Comments | Product-level pain points extracted |
|---|---|---|
| Brand-owned IG (Seed/Arrae/Ritual feeds) | 165 | 3 of 10 (~30%) |
| UGC TikTok reviews | 46 | 10 of 10 net new (~100%) |

Brand-owned comment sections skew toward operational questions
("Can I buy without subscription?", "When does this ship to Canada?") which
the gap analyzer's system prompt correctly filters out as non-creative.
UGC reviewers discuss product experience, side effects, mechanism doubts,
competitor comparisons — exactly what the matrix needs.

---

## Tier 1, 2, 3 — the layered model

```
clients/<slug>/competitors.yaml
  └── per competitor:
      ├── amazon_urls           → Tier 1 (Apify amazon scraper, paid)
      ├── tiktok_post_urls      → Tier 3 manual (most control, free if URLs known)
      ├── tiktok_search_queries → Tier 3 automated (paid search actor)
      ├── tiktok_handle         → Tier 3 brand-owned (free actor, lower signal)
      ├── instagram_post_urls   → Tier 3 manual
      ├── instagram_handle      → Tier 3 brand-owned
      └── youtube_video_ids / channel_id / handle → YouTube Data API (free)
```

The scraper picks the highest-priority field that's set, per platform.

---

## Two sourcing paths for TikTok UGC

### Path A — manual (Google search → URL list)

**When to use:** First time onboarding a new client. Most reliable. $0 discovery cost.

1. Open Google. Search `site:tiktok.com <brand> review`.
   - Example: `site:tiktok.com arrae review`
2. Skim results. Pick 3-8 videos that look like real UGC reviews:
   - 30K+ views (engagement signal — comments will be substantive)
   - Titled "honest review", "tried for 30 days", "is X worth it"
   - **NOT** the brand's own account
   - Diverse sentiment (positive + critical) for richer gap data
3. Copy each video URL.
4. Paste into `competitors.yaml`:
   ```yaml
   - name: Arrae
     slug: arrae
     url: https://www.arrae.com/
     tiktok_post_urls:
       - https://www.tiktok.com/@abbeyskitchen/video/7554098065859218696
       - https://www.tiktok.com/@hannahaaronbrown/video/7496136958825991454
       - https://www.tiktok.com/@foodiesushiqueen/video/7437232619487726894
   ```
5. Run:
   ```bash
   adc research-social --client <slug> --max-comments 100
   ```

### Path B — automated (search-based discovery)

**When to use:** Recurring research (weekly/monthly refresh), multi-brand
sweeps, or when the manual workflow becomes too time-expensive.

1. Add search queries to `competitors.yaml` (5-8 chars cheaper per query
   than picking URLs manually):
   ```yaml
   - name: Arrae
     tiktok_search_queries:
       - "arrae review"
       - "arrae honest review"
       - "tried arrae for 30 days"
   ```
2. Run the same command — the scraper will auto-discover videos via Apify's
   search actor (`clockworks/tiktok-scraper`, paid).

**Cost:** ~$2 per 1000 results from search actor + ~$0.30 per 1000 comments.
For a typical pull (3 competitors × 3 queries × 5 videos × 100 comments) that's
roughly **$1.50-$3.00 per client per run**.

**Tradeoffs vs Path A:**
- ✅ No manual URL hunting
- ✅ Discovers new review videos as they appear
- ⚠️ Lower URL quality — may surface brand-owned content tagged "review"
- ⚠️ Paid Apify actor ($2/1K results vs $0 for `free-tiktok-scraper`)
- ❌ Can't audit URLs before scraping — runs blind on whatever search returns

**My recommendation:** Path A for the first pull on a new client. Path B for
recurring refreshes once you've validated the category responds to UGC signal.

---

## Validation criteria when picking URLs (Path A)

A good UGC review video for our purposes:

- **30K+ views** — guarantees enough comments to extract meaningful pain
  points. Below 5K views you'll often get 0-3 comments.
- **Length 60s+** — shorter videos rarely surface substantive product
  experience; viewers comment with emoji reactions instead.
- **Posted within 12 months** — older reviews may reference discontinued
  formulas or pricing.
- **NOT the brand's own account** — `@arrae.co` posts are marketing, not
  reviews. Comments will be sycophancy.
- **Diverse sentiment** — include 1 critical, 1 positive, 1 neutral. The
  critical review will surface dealbreakers, the positive surfaces
  transformations, the neutral surfaces objections.
- **Variation across creators** — same person reviewing across all your
  picks gives a single-perspective bias.

---

## What's left after a successful pull

Once `research-social` has cached bundles, the downstream pipeline runs:

```bash
adc mine-voc --client <slug> --category "<category>"
adc analyze-gaps --client <slug>
adc creative-matrix --client <slug>
```

Each stage now reads the social comments natively:
- `mine-voc` picks up `clients/<slug>/voc/*-comments.json` automatically
- `analyze-gaps` (since the session 2026-05-22 update) pulls
  `research/{tiktok,instagram,youtube}-comments/` bundles per competitor
- `creative-matrix` consumes both via its tab prompts

The matrix's `research_sources_used.tier_3` field will list which platforms
fed in.

---

## Known limitations

1. **TikTok profile listing is login-walled.** The `clockworks/free-tiktok-scraper`
   actor can't see videos from a brand's own profile (`tiktok_handle` field)
   because TikTok requires login to view profile videos. You can still use
   `tiktok_post_urls` (manual URLs) — those bypass the listing step.

2. **Instagram hashtag search needs the paid IG hashtag actor.** Not currently
   automated — for IG UGC, use manual `instagram_post_urls` from Google
   search (`site:instagram.com <brand> review`).

3. **YouTube engagement is sparse for most consumer brands.** Most use YouTube
   for brand-film content with comments disabled. Set `youtube_handle` only
   when the brand actually has discussion-oriented videos.

4. **TikTok search-actor URL quality varies.** ~20-30% of returned videos may
   be tangentially related or brand-owned content tagged "review". Manual
   path beats automated for the first pull on a category.
