# Audience Conversion Report Workflow

Use this workflow during new-client research, ICP refreshes, and pre-brief
research when we need customer-language depth before writing ad concepts.

The goal is to turn raw customer and category conversations into a clean
research document that directly feeds hooks, briefs, scripts, statics, UGC
concepts, and objection-handling ads.

This is an automation-first workflow with manual fallback. It sits on top of
the repo's structured research layers and should collect/source as much as
possible through repo commands, APIs, Apify actors, Firecrawl, Reddit/YouTube
integrations, Foreplay, and OpenClaw browser automation before asking a human
to copy/paste. Do not treat it as a replacement for `adc research-*`,
`adc mine-voc`, `adc analyze-gaps`, personas, or briefs. Use it to improve the
source quality and copy usefulness of those outputs.

## When To Use

Use this when:

- Starting a new client or product.
- Existing repo research feels too thin or too abstract.
- Competitor reviews, Reddit, TikTok, or social comments are underfed.
- The team needs exact customer phrasing for ads.
- The client has useful reviews, emails, surveys, sales calls, or comments.
- We need objection-led or behavior/moment-led ad angles.

Use it especially when `adc status` shows weak source layers:

- 0 competitor reviews.
- 0 social comments.
- Missing Reddit data.
- Missing Amazon/product review URLs.
- Broad sentiment exists, but true VOC is thin.

## Automation-First Standard

Do not default to manual Google Doc collection when the same source can be
collected by the repo or the OpenClaw desktop/browser runtime.

Preferred collection order:

1. Repo-native commands:
   - `adc research-competitors --client <slug>`
   - `adc research-social --client <slug>`
   - `adc research-amazon --client <slug>`
   - `adc mine-voc --client <slug> --category <category>`
2. Source-specific APIs or configured bridges:
   - Reddit API or Apify Reddit bridge.
   - Apify TikTok/Instagram/Amazon actors.
   - YouTube comments API when configured.
   - Firecrawl for known pages and rendered review/comment pages.
   - Exa for broad sentiment and discovery.
3. OpenClaw browser automation on the designated PC:
   - GigaBrain / Reddit Answers searches.
   - Login-gated source review where the user is already authenticated.
   - TikTok/Google/Pinterest-style first-page source collection when APIs are
     too thin.
4. Human copy/paste only when automation is blocked, paid access is not
   approved, or the source explicitly requires human judgment.

When using OpenClaw/browser automation for GigaBrain or Reddit Answers, the
agent should search, expand, capture visible summaries/comments/source links,
and write them directly into repo artifacts with source labels. The operator
should not have to maintain a raw Google Doc unless they explicitly prefer
that route.

Every collected item should keep provenance:

- Source type: own review, competitor review, TikTok comment, Reddit/GigaBrain,
  Reddit Answers, YouTube comment, support email, sales call, survey, etc.
- Source URL or source label when available.
- Competitor/client/product association.
- Raw text.
- Date collected.
- Automation method: repo command, API, Apify, Firecrawl, Exa, OpenClaw browser,
  or manual.

## Output Files

For repo-backed client work, save the generated raw dump and final report under:

```text
clients/<slug>/research/audience-conversion/
  raw-data.md
  raw-data.jsonl
  source-manifest.yaml
  research-document.md
  source-truth-check.md
```

Use:

- `raw-data.md` for a human-readable dump grouped by source.
- `raw-data.jsonl` for source-preserved records that downstream tooling can
  parse.
- `source-manifest.yaml` for search terms, URLs, tools used, source counts, and
  missing/blocked lanes.
- `research-document.md` for the synthesized Audience Conversion Report.
- `source-truth-check.md` for the audit.

If the work is happening manually in Google Docs, mirror the names:

- `Raw Data - [Product Name]`
- `Research Document - [Product Name]`

If a PDF or TXT export is used for an LLM, keep it as an attachment or local
working artifact, but the repo-readable final should be Markdown.

## Step 1: Generate The Raw Data Dump

Create or update the repo raw dump:

```text
clients/<slug>/research/audience-conversion/raw-data.md
clients/<slug>/research/audience-conversion/raw-data.jsonl
clients/<slug>/research/audience-conversion/source-manifest.yaml
```

Preferred CLI:

```text
adc audience-conversion collect --client <slug> --product <product-slug> --category <category>
```

This command is free/local. It does not run paid research or LLM synthesis. It
consolidates existing repo artifacts into the Audience Conversion folder:

- `brand-context.md`
- `brand.yaml` brand information
- product YAML context
- existing avatar/persona YAML context
- own VOC files under `clients/<slug>/voc/`
- competitor review files under `research/competitor-reviews/`
- Amazon review files under `research/amazon-reviews/`
- social comment files under `research/*-comments/`
- cached Exa results under `research/exa/raw/`
- optional raw TXT/MD files passed with `--manual-source`

Use `--skip-exa` if Exa snippets are too broad for the current synthesis.

Examples:

```text
adc audience-conversion collect --client secondkind --product gut-balance --category postbiotics
adc audience-conversion collect --client zoka-coffee --product espresso-paladino --category specialty-coffee
adc audience-conversion collect --client expand-furniture --manual-source clients/expand-furniture/raw/client-notes.md
```

The agent should generate these files automatically from collected sources.
Do not summarize while collecting.

Recommended sections:

- Product/category conversation mining.
- Own product reviews.
- Competitor reviews.
- TikTok comments.
- Reddit/forum comments.
- Sales calls, support emails, surveys, or client notes.
- Product USPs and claims.

Raw is fine. Messy is fine. The point is to preserve the voice of the market
before the model cleans it up.

If a source is collected manually, label it clearly as manual in the source
manifest. Manual collection should be the exception, not the default.

## Step 2: Gather Product/Category Conversations

Primary automated routes:

- Reddit API / Apify Reddit bridge from configured search queries.
- Exa broad sentiment for discovery.
- OpenClaw browser automation for GigaBrain or Reddit Answers when the
  designated PC has access.

Useful browser-automation source:

```text
https://www.reddit.com/answers/
```

GigaBrain may also be used when available, especially for Reddit/forum-style
conversation mining. Treat it as a browser-automated source unless the user
explicitly chooses manual copy/paste.

Search:

- Product category.
- Core problem.
- Competitor names.
- Category + complaints.
- Category + side effects.
- Category + alternatives.
- Category + "does it work".
- Category + "worth it".
- Category + "review".

Examples:

- `collagen powder`
- `collagen powder side effects`
- `collagen powder bloating`
- `best collagen powder reddit`
- `postbiotics vs probiotics`
- `probiotics not working`

Automated collector steps:

1. Search the product category.
2. Open relevant threads.
3. Expand comments.
4. Capture full visible conversations into `raw-data.md` and `raw-data.jsonl`.
5. Use follow-up questions to go deeper.
6. Capture summaries, source-thread references, and raw comments.
7. Record source labels and search terms in `source-manifest.yaml`.

Useful follow-up questions:

- What do people dislike about this category?
- What side effects do people report?
- What alternatives have they tried?
- What makes them skeptical?
- What do they compare this product to?
- What words do they use when describing the problem?
- What moments trigger the problem in daily life?
- What do they wish existed instead?

Prioritize width and depth. Capture different subtopics, not only the first
obvious pain point.

## Step 3: Collect Reviews And Comments

Collect at least:

- 10-30 own product reviews, if available.
- 10-30 competitor reviews.
- 10-30 TikTok comments from own videos, if available.
- 10-30 TikTok comments from competitor/category videos.

Also use:

- Amazon reviews where the exact product/category is relevant.
- Review sites.
- Reddit threads.
- YouTube comments on review/comparison videos.
- Instagram comments.
- Sales-call notes.
- Support emails.
- Surveys.

Important TikTok/comment signals:

- Questions.
- Skepticism.
- Comparison comments.
- "How is this different from X?"
- Timing objections.
- Taste/aftertaste concerns.
- Side-effect concerns.
- "I tried this and nothing happened."
- "Does it work for [specific use case]?"

If the client's owned social comments are weak, use competitor/category content.
Do not stop just because the client has low comment volume.

Automation notes:

- Own reviews should come from vendor APIs, exports, or Firecrawl-rendered
  review pages when possible.
- Competitor reviews should use supported review widgets/APIs first, then
  Firecrawl-rendered pages, then source-specific fallback.
- TikTok/Instagram comments should use Apify/source bridges or explicit post
  URLs/search queries before manual capture.
- If a lane returns 0 items, write the failure or source mismatch to the source
  manifest instead of silently treating the lane as complete.

## Step 4: Add Brand Information And Product USPs Before Synthesis

Before synthesizing the report or generating personas, add brand and
product-specific context. This is a required gate, not an optional note. The
audience data is the source of truth for the market, but the brand information
keeps personas and concepts tied to the actual offer.

Add a **Brand Information** section with:

- Brand name.
- Unique differentiator: what makes the brand stand out.
- Best-selling or core product/service.
- Three things we wish every prospect knew about the product or brand.
- Desired brand perception: tone, values, trust signals, and how the brand
  should feel.
- Seasonal patterns: busy periods, holiday/seasonal use cases, gifting windows,
  seasonal objections, or recurring offers.
- FAQs and common customer questions.
- Approved claims.
- Claims to avoid or claims that need proof.
- Price, offer, guarantee, bundles, subscription details, or other buying
  context.

Then add product-specific context:

- What the product does.
- Core mechanism.
- Primary USPs.
- Approved claims.
- Claims to avoid.
- Price/offer.
- Target customer.
- Known proof points.
- Known objections.
- Competitors or categories to avoid naming in customer-facing copy.

The research report should compare real audience language against the product's
actual strengths. Otherwise the report becomes generic category research.

If any required brand field is missing, record it in `source-manifest.yaml` or
the research document as a missing input instead of inventing it.

## Step 5: Generate The Research Document And Personas

Export the raw document as TXT, PDF, or copy the raw Markdown into the LLM.

Use this prompt:

```text
You are an expert audience researcher and copy strategist.

You are given audience data that includes the following fields:
- pain_points
- failed_solutions
- desired_outcomes
- objections
- misconceptions
- golden_nuggets
- language_notes

Objective:
Analyze and synthesize this data into a clean, structured format using the
following exact sections.

## Brand Information

Summarize the brand context that was provided:

- Brand Name
- Unique Differentiator
- Best-Selling Product/Service
- Three Things Prospects Should Know
- Desired Brand Perception
- Seasonal Patterns
- FAQs And Common Claims
- Claims To Avoid Or Verify

If a field is missing from the source data, write `Missing from provided data`.
Do not invent brand details.

## Categorized Insights

### Top Pain Points

Format as a table:

Pain Point | Description
---|---

Pain Point:
Short, clear title capturing the core frustration.

Description:
1-2 lines summarizing the emotional reality behind it.

Group similar issues where appropriate.
Only include pain points relevant to the brand's ICP, product, and offer.
Ignore off-topic or irrelevant entries.

### Failed Solutions

Format as a table:

Attempt | Why It Failed
---|---

Attempt:
What users tried.

Why It Failed:
Why it did not solve the problem.

Group similar failed attempts if needed.
Only include attempts tied to the brand's core offer or target problem.

### Desired Outcomes

Format as a table:

Outcome | Explanation
---|---

Outcome:
Desired state the user wants.

Explanation:
Why that matters emotionally or practically.

### Objections

Format as a table:

Objection | Real Quote/Paraphrase
---|---

Objection:
User hesitation captured in simple, natural phrasing.

Real Quote/Paraphrase:
Write it like a real customer or Redditor would speak, using natural skepticism
and casual tone.

### Misconceptions

Format as a table:

Misconception | Clarification
---|---

Misconception:
Wrong belief the audience holds.

Clarification:
Correct understanding written simply.

### Behaviors And Moments

Format as a table:

Moment | Trigger | Behavior | Exact Language | What It Reveals | Ad Angle
---|---|---|---|---|---

Moment:
The real-life behavior, situation, or trigger.

Trigger:
What sets the moment off: time of day, meal, commute, workout, event, social
situation, purchase moment, product failure, comparison point, etc.

Behavior:
What the person does next, avoids, repeats, googles, asks, buys, complains
about, or changes in their routine.

Exact Language:
The raw phrase or close paraphrase that proves the moment. Preserve customer
wording whenever possible.

What It Reveals:
What this says about the audience's pain, desire, or skepticism.

Ad Angle:
How this could become a hook, scene, or static ad idea.

Do not bury behavior/moment triggers inside pain points. They are first-class
creative inputs because they become scenes, hooks, POV ads, calendar moments,
TikTok overlays, and UGC scripts.

### Exact Customer Terminology

Format as a table:

Phrase | Source/Context | Plain Meaning | How To Use In Ads | Avoid
---|---|---|---|---

Phrase:
The exact customer wording or very close paraphrase.

Source/Context:
Where it came from and what the person was talking about.

Plain Meaning:
What the phrase means strategically.

How To Use In Ads:
Hook, caption, script line, objection line, proof setup, or scene idea.

Avoid:
Any wording that would make the phrase feel too polished, too clinical, or
invented.

Prioritize phrases that sound like real people:

- specific metaphors
- casual complaints
- skeptical questions
- timing language
- comparison words
- routine phrases
- humor or sarcasm
- "I tried X and Y happened" structures

Do not replace vivid customer wording with generic strategy language.

### Golden Nuggets

Use the golden_nuggets entries.

If a quote already sounds like a natural Reddit/customer comment, keep it
verbatim.

If the quote sounds too formal or clunky, rewrite it using the style in
language_notes: casual tone, slang, contractions, emotional phrasing, humor,
skepticism, frustration, or DIY struggle.

Maintain honesty. Do not invent quotes.

Focus on quotes expressing:
- Frustration.
- Skepticism.
- Humor or sarcasm.
- Hopelessness.
- DIY struggle.
- A real moment or behavior.

Only include nuggets directly tied to the brand's ICP, product, or offer.
Ignore irrelevant ones.

### Strategy Implications For [Brand Name]

Format as a table:

Opportunity | How [Brand] Can Win
---|---

Summarize practical marketing opportunities from the audience's real
experiences.

### Objection-To-Ad Mapping

Format as a table:

Objection | Ad Concept | Proof Or Explanation Needed
---|---|---

Turn each major objection into at least one ad concept.

### Product-USP Angle Mapping

Format as a table:

Audience Problem | Product USP | Angle | Claim Risk
---|---|---|---

Use only real product USPs and approved claims. If an angle needs proof, say so.

### ICP Language Analysis

Based on language_notes, summarize:

- Natural tone: formal vs informal.
- Emotional style: skeptical, stressed, proud, fed up, hopeful, etc.
- Vocabulary: exact terms, category language, slang, comparison words.
- Copywriting tips: how to speak exactly like the ICP.

Use real examples where possible.

Include:

- words they repeat
- phrases they would actually type in a comment
- phrases that should become hooks
- phrases that should never be polished away
- language differences by awareness level or persona when visible

### Key Personas

Generate exactly three buyer personas/avatar profiles from the source-truthed
research and brand information. Each persona should represent a distinct
conversion-relevant audience segment, not a demographic stereotype.

Personas must be grounded in the raw data. If a persona detail is inferred
rather than directly supported, mark it as an inference.

For each persona:

- Persona Name ("Nickname")
- Age Range
- Quick Summary: 1-2 lines of their situation and emotional needs.
- Desire:
- Pain point:
- Objection:
- Lifestyle:
- How they perceive risk:
- What activities they do:
- Their opinions:
- Their interests:
- Their values:
- How they speak:
- Source Support: raw quote/comment/review/paraphrase that supports the persona.
- Best First Ad Angle:
- Angles To Avoid:

### Concepts

Leave this section ready for Phase 2 concept brainstorming.

If the team has not approved concept directions yet, write:

`Concept section intentionally left open for next-phase concept brainstorming.`

If the report strongly suggests concept seeds, include them as source-backed
seeds only:

Concept Seed | Source Insight | Persona | Why It Might Work | Proof Needed
---|---|---|---|---

Do not turn this into a full brief-generation step yet. The goal is to prepare
the document for concepts, not skip the concept review.

## Important Rules

- Stay 100% true to the raw audience data.
- Use language from the raw threads and reviews to guide rewrites.
- Ignore and exclude data irrelevant to the brand's target audience, product,
  offer, or service.
- Group and synthesize carefully without inventing new ideas.
- Keep the final output clean, readable, and marketing-useful.
- Flag any claim, insight, or persona detail that is not directly supported by
  the raw data.
- Generate personas only after Brand Information and the Audience Conversion
  Report are present.
- Do not create personas from brand assumptions alone.
```

## Step 6: Review And Refine Personas

Before using personas for concepts, review the three generated avatars.

Check:

- Does each persona represent a real pattern in the raw data?
- Is the persona too broad or too demographic?
- Does the persona have one clear desire, pain, objection, and daily-life
  context?
- Does the persona speak in the same language as the source data?
- Are unsupported details marked as inference or removed?
- Are there three distinct conversion-relevant audiences?

Refine any persona that does not match the real customer data. In client Slack
channels, ask the team to correct or approve personas before moving into
concepts when the client context is important.

Manual fallback:

If the team wants to use an external Avatar GPT, export the research document
as a PDF, upload it, generate three personas, then paste the finalized personas
back into the **Key Personas** section. The repo-first path should generate and
store personas directly in the research document when possible.

## Step 7: Source-Truth The Report

Before using the report for briefs or ad copy, audit it.

Ask:

- Where did this claim come from?
- Is this actually in the raw data?
- Is this a quote, paraphrase, or model inference?
- Is it relevant to the ICP and offer?
- Is it product-level, not operational noise?
- Are persona details supported by the raw data or clearly marked as inference?
- Are concepts empty or source-backed rather than invented?

If the report includes unsupported ideas, revise with:

```text
Revise this report using only the raw data provided. Remove unsupported claims,
overgeneralizations, and anything not directly tied to the audience evidence.
Where possible, preserve or cite the raw quote/paraphrase that supports each
major insight.
```

Create a short source-truth note:

```text
clients/<slug>/research/audience-conversion/source-truth-check.md
```

Include:

- Unsupported claims removed.
- Strongest raw quotes.
- Insights with direct source support.
- Insights that need more data.
- Claims that need client approval or proof.
- Persona details revised or removed.
- Concept seeds that are source-backed vs deferred.

## Step 8: Use The Report For Creative

The finished report should feed:

- ICP/persona refinement.
- Competitive gap analysis.
- Strategy matrix.
- Hooks.
- Scripts.
- Static ad concepts.
- UGC concepts.
- Brief generation.
- Objection-handling ads.
- Reference/ad-library angle tags.

Strong ad concepts should come from:

- A real pain.
- A failed solution.
- A desired outcome.
- A behavior or daily moment.
- An objection.
- A misconception.
- Exact language from the audience.

Do not turn the report into generic strategy language. The value is customer
phrasing.

## Step 9: Phase 2 Concept And Industry Research Handoff

After the Audience Conversion Report, Brand Information, and Key Personas are
source-truthed, move into concept research. Do not jump straight from broad
research into ad production.

The Phase 2 handoff should include:

- One selected persona/avatar for the concept batch.
- One primary mass desire, objection, misconception, failed solution, or
  behavior/moment to build around.
- Direct competitor/category examples.
- Adjacent niche examples.
- Internal winners, if the client or agency has prior winning ads.
- An angle bank organized by awareness level.
- A short list of concepts/templates to build.

### One Avatar Per Concept Batch

Static ads should usually speak to one person, not the whole market.

Before concepting, choose one avatar and capture:

- core desire
- core pain
- core objection
- daily-life context
- exact language style
- best first ad angle
- angles to avoid

If a concept tries to speak to multiple personas with different motives, split
it into separate concepts.

### 70 / 20 / 10 Concept Mix

For performance-focused concept batches, use this default allocation:

- **70% proven outside references:** direct competitor ads, adjacent niche ads,
  Foreplay boards, Apify/Meta/TikTok ad scrape, Pinterest mechanics, and
  ad-library teardowns.
- **20% internal winners:** client or agency hooks, formats, templates, offers,
  and visual mechanics that have worked before.
- **10% new swings:** new hypotheses, unusual hooks, trend plays, or creative
  ideas with lower evidence but meaningful upside.

Every concept should be labeled with its source type and evidence level. This
prevents random brainstorming from masquerading as proven concept strategy.

### Adjacent Niche Mining

Do not only study brands selling the same product. Pull mechanics from adjacent
niches that sell a similar desire, speak to the same avatar, or handle similar
objections.

Examples:

- Functional snacks and electrolyte drinks for protein or health routines.
- Digestive enzymes, bloating teas, greens powders, and healthy-girl routine
  content for gut health.
- Espresso gear, craft chocolate, premium pantry goods, and morning routines
  for specialty coffee.

Fast operating target:

- 10 direct/category examples.
- 10 adjacent niche examples.
- 3-5 internal winners if available.
- About one hour of concept/industry research before moving into angle
  selection, unless the category is under-sourced.

### Angle Bank By Awareness Level

Create an angle bank before choosing templates or producing images.

Use the Audience Conversion Report to generate angles from:

- mass desires
- objections
- misconceptions
- failed solutions
- behavior/moment triggers
- exact customer phrases
- golden nuggets
- product USPs
- proof points

Organize angles by awareness level:

- unaware
- problem-aware
- solution-aware
- product-aware
- most-aware

For every selected template or concept, generate:

- headline options
- first-line copy
- benefit bullets
- comparison/negative bullets where relevant
- objection handled
- proof needed
- awareness level
- source insight

### Proven Template Remix Handoff

When using a proven Canva/static template, the template controls the structure,
not the strategy.

Template controls:

- layout
- scan path
- proof structure
- product/image slots
- text hierarchy
- badges and CTA placement

Research controls:

- persona
- awareness level
- headline
- first-line copy
- benefits
- objections
- proof
- exact customer language

AI/image tools may help replace product or image slots, but final text should
stay editable in Canva/local whenever copy iteration matters.

## Relationship To Existing Repo Pipeline

This workflow does not replace the repo pipeline. It improves it.

Use alongside:

```text
adc research-competitors --client <slug>
adc research-social --client <slug>
adc research-amazon --client <slug>
adc mine-voc --client <slug>
adc analyze-gaps --client <slug>
adc brief --client <slug> --product <id> --angles 6
```

If automated research is strong, the Audience Conversion Report organizes the
best findings into an operator-friendly document.

If automated research is weak, the raw-data workflow fills gaps with
OpenClaw/browser-automated GigaBrain, Reddit Answers, TikTok, review, and
sales/support inputs first. Use manual copy/paste only when automation is
blocked.

## Minimum Research Quality Bar

Do not call an Audience Conversion Report complete unless it includes:

- Own product reviews or direct customer feedback, if available.
- Competitor/category review data.
- Reddit/forum/GigaBrain-style conversations or equivalent social VOC.
- TikTok/social questions or objections when category-relevant.
- Product USPs and approved claims.
- Brand information: differentiator, best seller/core product, desired
  perception, seasonal patterns, FAQs, and approved/common claims.
- Exact customer phrases.
- Exact customer terminology table with ad-use notes.
- Behavior/moment triggers.
- Behavior/moment table with trigger, behavior, exact language, and ad angle.
- Objections.
- Failed solutions.
- Source-truth review.

If one lane is unavailable, state that clearly in the report and explain the
fallback source used.

## Operator Notes

- Raw first, synthesis second.
- Automate collection first; manual copy/paste is fallback.
- Do not clean up too early.
- Do not let the model invent customer language.
- Questions in TikTok comments are often ad angles.
- Competitor comments are useful even when our client has low volume.
- Behaviors and moments are as important as pains and desires.
- Behaviors and moments should become scenes, hooks, and UGC/script beats.
- Exact customer terminology should be preserved, not translated into generic
  marketing wording.
- Objections should map directly to creative angles.
- Brand information and product USPs must be injected before final synthesis.
- Personas must be generated from the source-truthed report, not from brand
  assumptions alone.
- The Concepts section should exist before handoff, even if intentionally left
  open for the next phase.
- Final copy should sound like the ICP, not like a research report.
