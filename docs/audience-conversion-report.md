# Audience Conversion Report Workflow

Use this workflow during new-client research, ICP refreshes, and pre-brief
research when we need customer-language depth before writing ad concepts.

The goal is to turn raw customer and category conversations into a clean
research document that directly feeds hooks, briefs, scripts, statics, UGC
concepts, and objection-handling ads.

This is a manual-first workflow. It can sit on top of the repo's structured
research layers. Do not treat it as a replacement for `adc research-*`,
`adc mine-voc`, `adc analyze-gaps`, personas, or briefs. Use it to improve
the source quality and copy usefulness of those outputs.

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

## Output Files

For repo-backed client work, save the manual raw dump and final report under:

```text
clients/<slug>/research/audience-conversion/
  raw-data.md
  research-document.md
  source-truth-check.md
```

If the work is happening manually in Google Docs, mirror the names:

- `Raw Data - [Product Name]`
- `Research Document - [Product Name]`

If a PDF or TXT export is used for an LLM, keep it as an attachment or local
working artifact, but the repo-readable final should be Markdown.

## Step 1: Set Up The Raw Data Document

Create a Google Doc or Markdown file:

```text
Raw Data - [Product Name]
```

Paste everything raw, with minimal formatting. Do not summarize while collecting.

Recommended sections:

- Product/category conversation mining.
- Own product reviews.
- Competitor reviews.
- TikTok comments.
- Reddit/forum comments.
- Sales calls, support emails, surveys, or client notes.
- Product USPs and claims.

Paste without formatting when possible. Raw is fine. Messy is fine. The point is
to preserve the voice of the market before the model cleans it up.

## Step 2: Gather Product/Category Conversations

Primary manual source:

```text
https://www.reddit.com/answers/
```

GigaBrain may also be used when available, especially for Reddit/forum-style
conversation mining.

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

Operator steps:

1. Search the product category.
2. Open relevant threads.
3. Expand comments.
4. Copy full conversations into the raw document.
5. Use follow-up questions to go deeper.
6. Copy summaries, source-thread references, and raw comments.

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

## Step 4: Add Product USPs Before Synthesis

Before giving the raw data to an LLM, add product-specific context:

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

## Step 5: Generate The Research Document

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

Moment | What It Reveals | Ad Angle
---|---|---

Moment:
The real-life behavior, situation, or trigger.

What It Reveals:
What this says about the audience's pain, desire, or skepticism.

Ad Angle:
How this could become a hook, scene, or static ad idea.

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

### Key Personas

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

## Important Rules

- Stay 100% true to the raw audience data.
- Use language from the raw threads and reviews to guide rewrites.
- Ignore and exclude data irrelevant to the brand's target audience, product,
  offer, or service.
- Group and synthesize carefully without inventing new ideas.
- Keep the final output clean, readable, and marketing-useful.
- Flag any claim, insight, or persona detail that is not directly supported by
  the raw data.
```

## Step 6: Source-Truth The Report

Before using the report for briefs or ad copy, audit it.

Ask:

- Where did this claim come from?
- Is this actually in the raw data?
- Is this a quote, paraphrase, or model inference?
- Is it relevant to the ICP and offer?
- Is it product-level, not operational noise?

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

## Step 7: Use The Report For Creative

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

If automated research is weak, the raw-data workflow fills gaps with manual
GigaBrain, Reddit, TikTok, review, and sales/support inputs.

## Minimum Research Quality Bar

Do not call an Audience Conversion Report complete unless it includes:

- Own product reviews or direct customer feedback, if available.
- Competitor/category review data.
- Reddit/forum/GigaBrain-style conversations or equivalent social VOC.
- TikTok/social questions or objections when category-relevant.
- Product USPs and approved claims.
- Exact customer phrases.
- Behavior/moment triggers.
- Objections.
- Failed solutions.
- Source-truth review.

If one lane is unavailable, state that clearly in the report and explain the
fallback source used.

## Operator Notes

- Raw first, synthesis second.
- Do not clean up too early.
- Do not let the model invent customer language.
- Questions in TikTok comments are often ad angles.
- Competitor comments are useful even when our client has low volume.
- Behaviors and moments are as important as pains and desires.
- Objections should map directly to creative angles.
- Product USPs must be injected before final synthesis.
- Final copy should sound like the ICP, not like a research report.
