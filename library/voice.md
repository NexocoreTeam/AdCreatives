# Copywriting Voice Profile

This file is the **single source of truth** for the voice/tone/cleverness
patterns the AdCreatives system should use when writing ad copy. It is
loaded by `strategy/ad_remixer.py` at runtime and injected into both the
angle-generation prompt and the source→target mapping prompt.

The voice profile is extracted from a reference brand (babybay) whose
copywriting demonstrates the patterns we want: clever, concrete, customer-
voice, and confident without being preachy or product-spec heavy.

To override for a specific client, create `clients/<slug>/voice.md` —
the loader prefers per-client over this global default.

---

## CORE VOICE PRINCIPLES (apply to every line you write)

1. **Customer voice, never brand voice.** Customers say "Bloat gone."
   Brands say "Supports digestive comfort." Always pick the first.

2. **Concrete over abstract.** Replace internal feelings with observable
   states. ❌ "Confidence shaken" → ✓ "Three brands later, still tired."

3. **Short. Period.** Most strong lines are 1–4 words. Periods between
   short fragments create rhythm. "Safe. Stylish. Sleep."

4. **Wink, don't hedge.** Self-aware playfulness is fine ("A total
   snoozefest" used as a compliment). Apologetic hedges are not
   ("actually", "finally" — strip them).

5. **Define by negation.** The brand is what others aren't. "Not a crib."
   "Never plastic." "No bars between you." This is one of the brand's
   strongest moves.

6. **Be specific. Be the believable.** Vague claims slide past the brain
   without sticking. Specific numbers, durations, doses, and named
   thresholds get processed deeply AND signal that you've done the work
   to back the claim. Use specificity wherever the brief gives you the
   raw material. (Full rules in the SPECIFICITY section below.)

---

## PERSUASION vs SPECIFICITY (two different layers — use both)

These are easy to confuse. They aren't the same lever.

- **Persuasion** is the EMOTIONAL angle. The hook, the rhythm, the wink,
  the negation move, the customer-truth headline. It makes the reader
  FEEL something fast enough to stop scrolling. The signature moves
  below cover this.

- **Specificity** is the PROOF layer. A number, a duration, an exact
  threshold, a named ingredient, a percent. It gives the reader the
  REASON TO BELIEVE the angle. The specificity section below covers
  this.

A great ad has both. "Eating clean. Still bloated by dinner." (persuasion)
+ "84-day RCT data" (specificity). Without persuasion, specificity reads
as a spec sheet. Without specificity, persuasion reads as a hot take.

---

## SPECIFICITY RULES (apply whenever the brief has the raw material)

The research underlying these rules:

1. **Vagueness gets shallow processing.** The brain doesn't deeply
   evaluate vague claims — they don't stick. Specific claims do.
2. **Specific numbers create perceived credibility through legal
   exposure.** "Best in the world" is legally protected puffery (anyone
   can say it; nobody's expected to take it literally). "30% reduction"
   creates legal liability — so readers assume you must have done the
   work to back it up, and they believe you more.
3. **The more vague the claim, the more the reader thinks
   "I'm being marketed to."** Skepticism rises in lockstep with
   vagueness.
4. **Audience awareness calibrates.** For high-awareness categories
   (everyone knows what protein powder is) you can be a bit broad.
   For LOW-awareness categories — novel mechanisms, new ingredients,
   first-of-kind products — specificity is REQUIRED or the reader
   reads it as untrustworthy. Postbiotics are low-awareness. RCT-backed
   formulations are low-awareness. Treat them accordingly.

### Specificity moves (use these in order of preference)

**(a) Name the threshold.**
- ❌ "Bloat clears soon" / "Bloat clears" → ✓ "Bloat clears by noon"
- ❌ "Energy steady" → ✓ "Steady through 3pm" / "No 2pm wall"
- ❌ "Feel better" → ✓ "Feel it by week 2"

**(b) Name the duration / study window.**
- ❌ "Clinically studied" → ✓ "84-day RCT" / "14-day trial"
- ❌ "Published research" → ✓ "Peer-reviewed in JAMA"
- ❌ "Long-term effects" → ✓ "12-month follow-up"

**(c) Name the dose / quantity.**
- ❌ "Trillions of bioactives" → ✓ "1T bioactives"
- ❌ "Multiple strains" → ✓ "4 strains"
- ❌ "High-potency" → ✓ "500mg per serving"

**(d) Name the percent.**
- ❌ "Fewer sick days" → ✓ "17% fewer sick days"
- ❌ "Better absorption" → ✓ "3x absorption"
- ❌ "Reduced bloating" → ✓ "72% report less bloating"

**(e) Name the ingredient (without ®/™ in callouts).**
- ❌ "Patented BiomeBalance™ complex" → ✓ "EpiCor-backed" or "Totipro + EpiCor"
- The ®/™ marks belong on the product label, not in 2–4 word callouts.

### The Rolls-Royce move (signature move worth its own callout)

In 1958, the most-famous Rolls-Royce ad ever ran with the headline:

> "At 60 mph, the loudest noise in this new Rolls-Royce comes from the
> electric clock."

One hyper-specific concrete detail (an electric clock at 60 mph) that
IMPLIES all the rest of the quality (suspension, engineering, build).
50% sales increase. $25K ad spend.

The move: instead of listing 5 features, pick ONE concrete observable
moment that, if you saw it, would tell you everything else is also great.

**Apply:**
- ❌ "Better digestion, sharper focus, steady energy"
- ✓ "By week 2, the only thing your gut does is digest."
- ✓ "Three probiotic brands later, still bloated. One bottle of this,
  done."
- ✓ "At noon, the bloat is already gone."

One specific moment. Implies the rest.

### Numbers are protected during compression

When fitting a target to a source's word envelope, NUMBERS are protected.
Drop adjectives, descriptors, modifiers — keep the number, the duration,
the percent, the dose. The number IS the credibility.

- Source slot: 2 words. Brief: "84-day GI trial data" (4 words).
  - ❌ "Trial data" (dropped the number)
  - ❌ "GI study" (dropped the number)
  - ✓ "84-day RCT" (kept the number, dropped the GI/data wrappers)

---

## SIGNATURE MOVES (use these patterns — they work)

### Move 1: Negation as identity
The brand identifies itself by what it ISN'T, then redirects to what it IS.

- "Not a crib. A way to [USP]"
- "All wood, never plastic"
- "100% beechwood (never plastic or mesh)"
- "Toxic chemicals are out ❌ All-natural is in ✅"
- "No bars to reach over. No getting out of bed."

Apply to any category: "Not a probiotic. Postbiotics that arrive."
"Never live bacteria. Always 1 trillion bioactives."

Construction rule: use periods, colons, or line breaks between the
negation half and the affirmation half. **Never use em-dashes** (see
the forbidden-punctuation rule below). Period stops carry the same
rhythm without the dash.

### Move 2: Three-beat rhythm (period stops)
Three short fragments separated by periods. The rhythm IS the persuasion.

- "Sleep close. Sleep safe. Sleep happy."
- "Safer sleep. Better sleep. More peace of mind."
- "Safe. Stylish. Sleep."
- "Better sleep. Naturally."
- "best. purchase. ever."
- "Sweet dreams start here."

Apply: "Bloat gone. Energy steady. Sleep deep."

### Move 3: [Adjective] + [Noun] template
Pick one noun, vary the adjective across three callouts.

- Better sleep / Closer sleep / Safer sleep / More natural sleep
- More peace of mind / More quality rest

Apply: "Better gut. Calmer gut. Quieter gut."

### Move 4: Rhyme, alliteration, internal music
Sound-pattern lifts a line out of generic-marketing range.

- "Sleep close, roll far"
- "Say hey to babybay"
- "Sweet dreams start here"
- "Easier feedings, quicker comfort"
- "Give love, go back to sleep"

Apply: "Wake clear, not foggy." "Less bloat. More you."

### Move 5: Customer quote as headline
A short, specific, real-customer line carries more weight than any brand
claim. Always credited with first name + last initial.

- "Hooray for no plastics" – Alivia F.
- "Couldn't love it more" – Lila H.
- "Hands down, best bedside sleeper" – Chloe S.
- "New moms: buy this" – Anne V.
- "I wish we found this for our first born" – Tiffany S.

These are 2–6 word reviews — extreme compression. Apply: pick a real
customer's punchiest 4-word verdict and use it verbatim as the headline.

### Move 6: Cross-out hook (negation + replacement)
Strike through what's wrong, replace with what's right.

- "Better sleep with a newborn is ~~impossible~~"
- "Natural bedside sleepers ~~don't~~ exist"
- "Peace of mind is ~~hard~~ easy to find"

Apply: "Probiotics ~~work~~ arrive dead at the gut."

### Move 7: Reframe — "Not just X. It's Y"
Expand the value beyond the obvious category.

- "babybay is not just for sleeping. It's for peace of mind, all the time"
- "babybay is not just for sleeping. It's for easy nighttime feeding"

Apply: "Gut Balance isn't just bloating. It's energy, sleep, clarity."

### Move 8: Emoji — two specific use cases
Emoji has exactly two legitimate uses in this voice. Anything else is
decoration and gets stripped.

**Use 1 — Callout / feature icon (short slot, 2–4 words max):**
- 😴 Better sleep
- 🤱 Closer sleep
- ❤️ Safer sleep
- 🌍 More natural sleep
- 🌱 Naturally non-toxic
- ⭐ 4.9 stars

Apply: 🌱 1T bioactives / 😌 Bloat gone / 💪 Steady energy

**Use 2 — Bullet markers in long-form (Meta primary text):**

Meta's ad text field does not render real bullet points. Emoji are
the only way to create visual list structure inside long-form primary
text. Use a single consistent marker per list — never mix.

Approved markers:
- ✅ — what we do / our advantages / wins (most common in long-form)
- ❌ — what they (competitors/category) don't do / failure modes
- 🚫 — banned / not for sale / what we refuse
- 🧪 — clinical trial / scientific evidence
- ↓ — soft CTA arrow at end of UGC primary text ("trust me on this ↓")

Banned markers (too cute, too hype, or generic-marketing-coded):
- 💪 🔥 ⚡ 🎉 ✨ 🌟 — hype emoji
- 🙏 🥰 😍 — over-emotional
- 💯 🚀 — bro-voice / growth-hacker
- 👇 — too pushy in CTA position (use ↓ instead — cleaner)

Use sparingly. A long-form ad should have one bullet-list section
max. If two lists in one ad, use different markers (e.g. ❌ for the
failure list, ✅ for the advantage list). Never emoji-decorate mid-
sentence prose — emoji are bullet/icon punctuation, not adjectives.

### Move 9: Concrete sensory verb
Always physical, observable, immediate.

- "Soothe with a touch"
- "Give love, go back to sleep"
- "Mid-night hugs (without bars between you)"
- "Quick diaper changes"
- "Within arm's reach"
- "Reach over"

Apply: "Bloat clears by noon." "Gut settles by week 2."

### Move 10: Self-aware wink
The brand acknowledges its own cleverness; the reader is in on the joke.

- "The only time calling something 'a total snoozefest' is a total compliment 😉"
- "'Out of sight, out of mind' isn't a thing in parenthood 👀"
- "Hooray for no plastics"

This is a tone, not a formula. Don't force it — but when a line writes
itself with a wink, take it.

---

## FORBIDDEN VOCABULARY (kill list — never use these words)

These are marketing-speak. The customer doesn't say them. Strip them
from every target you write.

**Verbs (marketing → kill):**
- ease, eases, easing → use: gone, clears, stops, lifts
- support, supports, supporting → use: works, arrives, kicks in, lands
- help with, helps with → use: fixes, kills, ends
- assist, assists → use: handles, takes care of
- improve, improves, optimize, optimizes → use: works, kicks in, lifts
- enhance, enhances → use: lifts, sharpens
- address, addresses → use: stops, kills, fixes
- maintain, maintains → use: keeps, holds, locks in
- reduces, lessens → use: gone, off, away
- promote, promotes → (just remove the word; rewrite around it)
- facilitate, facilitates → use: makes, gets

**Adjectives (banned):**
- premium, luxury, elite, world-class
- advanced, cutting-edge, next-generation, innovative, revolutionary
- proprietary (in customer-facing copy), patented (acceptable IF needed
  for credibility but not in callouts — "Patented BiomeBalance complex"
  is too marketing-y for a callout slot)
- holistic, synergistic, optimal, ideal
- experience, journey (as nouns)

**Puffery — legally-protected phrases that signal weakness (banned):**
These are legally protected BECAUSE nobody's expected to take them
literally (under US ad law, "puffery" can't get you sued because no
reasonable person would believe a literal "best in the world" claim).
That's exactly why they carry no information — and exactly why
specific claims with numbers beat them.
- "best in the world", "world's best", "best ever"
- "industry-leading", "category-defining", "market-leading"
- "the gold standard", "the only X you'll ever need"
- "unmatched", "unparalleled", "second to none"
- "trusted by millions" (vague — use "Loved by 1M+ families" if you
  have the count; otherwise drop it)
- "world-class", "best-in-class"
Rewrite any of these as a specific claim with a number, a duration, a
named threshold, or a customer quote.

**Hedges (banned — these signal weakness):**
- actually, finally, really, just, honestly, literally
- These four hedges leak constantly. STRIP THEM. They never improve a line:
    - ❌ "Bloating actually calms down" → ✓ "Bloat clears"
    - ❌ "Finally felt the difference" → ✓ "Felt the difference"
      (or better: "Felt it by week 2")
    - ❌ "It really works" → ✓ "It works" (or rewrite around it)
    - ❌ "Honestly, the best" → ✓ "Best, hands down"
- Exception, single allowed pattern: a hedge inside a customer-quoted
  testimonial WITH proper attribution is fine ("Three brands later —
  actually works." – Bailey K.) because the customer can talk this
  way. Brand-voice cannot.

**Patent/ingredient name-drops in callouts (banned):**
- "Patented BiomeBalance™ complex"
- "Features patented [ingredient] technology"
- "Powered by [TM]"
These belong on the product label, not in a 3-word callout slot.
If you need to reference the ingredient: "1T bioactives" or just the
ingredient name without the wordmark ("EpiCor-backed").

**Forbidden CONSTRUCTIONS (not single words):**
- "Supports X" — the worst offender. Rewrite as the resulting state.
- "Helps with X" — same. Rewrite as the outcome.
- "Designed to X" / "Built to X" — passive-marketing. Rewrite active.
  (Exception: "Built to last" is a brand-recognized phrase; OK.)
- Long compound sentences with subordinate clauses
- Anything starting with "Our [adjective] formula..."
- Disclaimers in callout slots ("These statements have not been
  evaluated by the FDA" — never include unless explicitly required.)

**Forbidden PUNCTUATION:**
- **Em-dash (—) is banned in all copy.** Banked from production
  feedback (2026-05-24): the X-gone pattern and the negation-as-identity
  move both relied on em-dashes; they were rewritten to period-stop
  and colon forms. Use one of these instead:
    - Period stop: "Bloat. Gone." (preferred — period-stop rhythm)
    - Colon: "Bloat: gone." (alt for variety)
    - Comma: "Bloat, gone." (softest — use rarely)
    - Line break: when the break is visual / multi-line
  En-dash (–) inside a customer-quote attribution credit
  ("Hooray for no plastics" – Alivia F.) is the one acceptable
  dash form — that's standard typography for a citation, not body
  copy. Hyphens (-) inside compound words (12-week, 84-day) are
  fine.

---

## RAW EXAMPLES BY SLOT TYPE

When you write a target, look at the matching slot here for reference.

### Headlines (1–8 words; punchy, often with rhythm)

- "Say hey to babybay"
- "Better sleep. Naturally."
- "Sleep close. Sleep safe. Sleep happy."
- "Safe. Stylish. Sleep."
- "Sweet dreams start here"
- "Safe sleep: delivered in style"
- "Loved by 1,000,000+ families"
- "Get all-natural sleep"
- "Closer, better sleep"
- "All wood, never plastic"
- "Get closer, better sleep"
- "What babybay is about"
- "4 reasons babybay always sells out"
- "4 reasons parents say 'best. purchase. ever.'"

### Subheadlines / sub-pitches (one short line)

- "Of its bestselling bedside sleepers"
- "Easier feedings, quicker comfort"
- "Built to last"
- "Naturally non-toxic"
- "Always within reach"

### Callouts (2–5 words; emoji-eligible)

- "Within arm's reach"
- "Close but safe"
- "Hooray for no plastics"
- "Easy nighttime feedings"
- "High-quality beechwood"
- "Made in Germany"
- "Close at night"
- "Safe in own bed"
- "Soothe with a touch"
- "Quick diaper changes"
- "More peace of mind"
- "More quality rest"
- "Mid-night hugs"
- "Without bars between you"

### Pain-side callouts (what they're stuck with WITHOUT the product)

- "Flimsy plastic"
- "Cheap mesh"
- "Toxic solvents & dyes"
- "VOCs"
- "Better sleep is impossible"
- "Bars between you"
- "Reaching over"
- "Getting out of bed"
- "Out of sight, out of mind"

### Benefit-side callouts (the relief / new state)

- "High-quality beechwood"
- "Non-toxic"
- "Naturally hypoallergenic"
- "Water-based finishes"
- "Within arm's reach"
- "Easy nighttime feeds"
- "Soothe with a touch"
- "No bars between you"
- "Always in sight"

### CTAs (2–5 words; verb-first)

- "Shop now"
- "Shop sleepers & more"
- "Shop parent-loved sleepers"
- "Shop all-natural sleepers"
- "Shop babybay sleepers"
- "Bedside sleepers & more"
- "Get all-natural sleep"
- "Get closer, better sleep"
- "Join the 1,000,000+"

CTA verbs that work in this voice: Shop, Get, Join, See, Meet, Say hey to.
CTA verbs to avoid: Discover, Explore, Learn more, Find out, Unlock.

### Customer quotes (real, short, specific)

- "A perfect baby crib." – Dhamma W.
- "Hooray for no plastics." – Alivia F.
- "Couldn't love it more." – Lila H.
- "Hands down, best bedside sleeper." – Chloe S.
- "New moms: buy this" – Anne V.
- "My newborn loves sleeping on it." – Bailey B.
- "Beyond beautiful and well made!" – Haley B.
- "Easy to move around our home." – Elizabeth A.
- "I wish we found this for our first born." – Tiffany S.
- "Fits our decor perfectly while also being completely functional." – Melanie B.

Use 4–8 word quotes. Always credit. Always real.

### Question hooks

- "Sick of plastic everything?"
- "Want to give your baby clean, natural sleep?"
- "Want a natural wood crib?"

Apply: "Sick of probiotics that don't arrive?" "Want a gut that just works?"

### Social-proof lines

- "1,000,000+ families worldwide"
- "Loved by 1,000,000+ families"
- "4.9 stars, 355+ reviews"
- "415+ ⭐⭐⭐⭐⭐ reviews"
- "babybay all-natural sleepers get ⭐⭐⭐⭐⭐ for a reason"

---

## CATEGORY ADAPTATIONS — translating babybay moves to other categories

The reference brand (babybay) sells baby sleepers. The same voice moves
work on wellness, supplement, biohacker, and practitioner-targeted ads
when adapted. Below are example banks captured from real production
runs where the voice translated well. Use these when working in the
matching category.

### Postbiotic / gut-health (consumer)

**Headlines (period-stop rhythm + customer truth):**
- "Eating clean. Still bloated by dinner. | Probiotics die before they reach your gut."
- "Took them every day. | The bioactives never arrived."
- "Optimizing the bacteria. Not the bioactives. | Skip the bacteria. Get the bioactives."
- "Three probiotic brands later"
- "Bottles of probiotics, still bloated"

**Pain callouts (concrete body-feeling):**
- "Still bloated"
- "Brain fog"
- "Brain fog stays"
- "Puffy"
- "Unpredictable gut"
- "Bars between you" (← good analog from babybay if barrier-shaped)
- "No change"
- "Still off"

**Benefit callouts (the "X. Gone." pattern is gold):**
- "Bloat clears"
- "Bloat clears by noon"
- "Bloat. Gone."
- "Brain fog. Gone."
- "Gut cooperates"
- "Gut feels mine"
- "Gut feels like mine again"
- "Sharp by noon"
- "Less puffy by week 2"
- "Energy back"
- "Felt the difference"

### Practitioner / clinical-evidence persona

This is where the babybay playfulness gets dialed down and the rhythm
gets crisper. Period-stops still work. Wink moves don't.

**Headlines (evidence-credibility):**
- "What your patients tried. | What the RCTs actually showed."
- "Without RCT backing"
- "Sick. Again. Scheduled." (← dark humor wink, used carefully)

**Pain callouts (clinical observations, NOT internal feelings):**
- "Patients report nothing"
- "No study cited"
- "No published data"
- "Survivability unproven"
- "Trust erodes" (borderline — abstract; prefer "Patients leave")
- "Recommendations falling flat"

**Benefit callouts (evidence cues — verifiable, specific):**
- "84-day trial data"
- "14-day RCT"
- "Named, verifiable ingredients"
- "Replicated in RCTs"
- "Cited mechanism"
- "Peer-reviewed"
- "Clinician-reviewed"

**Forbidden in this register:**
- Customer-feeling language ("still bloated", "energy back") — wrong audience
- Product-spec ("Patented BiomeBalance complex", "Supports X")
- Patent-name-drops in callouts (use the ingredient unbranded: "EpiCor-backed")

### Biohacker / optimizer persona

**Headlines (efficiency framing):**
- "Optimizing the bacteria. Not the bioactives."
- "Stack of 12. Bloat at 12."

**Pain callouts (system-failure observations):**
- "2pm wall"
- "Stack keeps growing"
- "Bloat compounds"
- "Numbers tell a story"

**Benefit callouts (system-improvement observations):**
- "Stack gets shorter"
- "2pm wall. Gone."
- "Energy steady"
- "Gut cooperates"
- "Numbers improve"

### Immune / anxiety persona

**Headlines (predictable-pattern framing):**
- "Sick every quarter. Right on schedule."
- "Sick. Again. Scheduled."

**Pain callouts (recurrence observations):**
- "Sick quarterly"
- "Runs down at crunch"
- "Energy crashes"

**Benefit callouts (immunity-as-state):**
- "Fewer sick days"
- "Energy holds through"
- "Gut stays steady"
- "17% fewer sick days. RCT-backed." (if you have the data)

---

## META PRIMARY TEXT (long-form ad body copy)

**Critical distinction:** every other slot in this voice (headlines,
callouts, CTAs, customer quotes) is SHORT-FORM compression. Meta
**primary text** is the opposite — it is the **body copy of the ad**,
not a callout. It's the multi-paragraph caption that sits ABOVE the
image in a Meta feed placement.

Banked from production feedback (2026-05-24): when the voice's
compression rules get applied to primary text, the output reads
lacklustre — single sentences where competitors are running 100–300
word narratives. The compression rules apply to every other slot,
NOT to primary text.

### Length and shape

- **100–300 words is normal.** Competitor performers run anywhere
  from 80 to 400 words in primary text.
- **Multiple paragraphs encouraged.** Break with double line breaks
  every 2–3 sentences. Each paragraph should land one beat.
- **Truncation point on Meta is ~125 chars in the feed preview** —
  the FIRST 125 chars must hook hard enough to earn the "See More"
  expand. Everything after that is for the readers who already
  clicked to expand.
- **No headlines or callouts inside primary text** — it's prose, not
  a stack of fragments. Save the punchy short forms for the headline
  slot under the image.

### Structure — the 4-beat arc

Every primary text should walk through:

1. **Name the suspicion.** Lead with the felt failure or the recognized
   moment. "You took the probiotic. Every morning. For months." —
   the reader has done this; they recognize themselves.
2. **Diagnose the mechanism.** Explain *why* the failure happens in
   structural terms. "Roughly 70% of live bacteria die in stomach acid
   before reaching your gut." Receipt-grade specificity required here.
3. **Vindicate.** Lift the blame off the customer. "You weren't lazy.
   The delivery model was broken." This is where the bold-voice
   indictment lands on the category, not on her.
4. **Convert.** Introduce the alternative with a short ingredient/
   trial proof. Soft CTA OR end on a brand statement; never "Shop now."

### Permitted formatting moves inside primary text

- **Period-stop fragments** still work — they punch the rhythm even
  in long-form. "You weren't lazy. Your probiotic was dead. Now you know."
- **Emoji bullet markers** for any list of 3+ items: use ✅ for
  advantages, ❌ for failure modes, 🧪 for trial citations. ONE list
  max per ad (or one ❌ list and one ✅ list). See Move 8.
- **Customer-voice opener** is gold — first-person testimonial register
  with lowercase friend-text tone for UGC concepts.
- **Soft CTA in UGC primary text:** `trust me on this ↓` at the bottom.
  Editorial primary text ends on the brand statement, no CTA.

### Forbidden inside primary text

- **No "Shop now" / "Buy now" / "Learn more" / "Click here" CTAs.**
  Those are platform button slots. Primary text closes on a brand
  truth or a soft `trust me on this ↓`, not a sales imperative.
- **No mid-sentence emoji decoration.** Emoji are bullet markers or
  feature icons (per Move 8) — not adjectives. "Bloat clears 💪" is
  wrong; "✅ Bloat clears" is right.
- **No em-dashes.** See forbidden-punctuation rule.
- **No long subordinate clauses.** Short declarative sentences win
  even in long-form. The rhythm is what carries the body.

### Worked example — bold-variant primary text in voice

For a SecondKind Bold vindication ad ("You weren't lazy. Your probiotic
was dead."):

> You took the probiotic. Every morning. For months.
>
> You did everything right. Picked the brand with the highest CFU
> count, stuck to the routine, checked the labels. And still: bloated
> by 7pm. Brain fog by 3pm. Energy crashes. Nothing changed.
>
> Here's what nobody puts on the bottle. Roughly 70% of the live
> bacteria in commercial probiotics die in stomach acid before
> reaching your gut. You weren't paying for what works. You were
> paying for what dissolves in transit.
>
> Postbiotics are the bioactive compounds bacteria are supposed to
> produce inside your gut. SecondKind Gut Balance skips the delivery
> problem entirely.
>
> ✅ Three patented postbiotic ingredients
> ✅ Three published clinical trials
> ✅ Already active. Already absorbable.
>
> You weren't lazy. Your probiotic was dead. Now you know.

Note: 175 words. 6 paragraphs (with the bullet block counting as one).
Opens with customer-truth recognition. Mechanism diagnosis with the
70% receipt. Vindication ("you weren't paying for what works"). Brand
intro with trial proof. Closes on the period-stop signature without
any sales imperative. Zero em-dashes. One ✅ list, no other emoji.

This is the shape. Apply per concept.

---

## THE "X. GONE." PATTERN (signature move worth its own section)

A move that emerged organically in production: pair a pain word with
a period-stop and "Gone." Two beats. Reads as victory. Translates to
nearly any consumer-wellness category.

This pattern originally used em-dashes ("X — gone") but em-dashes are
now banned across this voice (see forbidden-punctuation rule below).
Period-stop carries the same rhythm. Colon is the alt form.

**Examples (period-stop, primary form):**
- "Brain fog. Gone."
- "2pm wall. Gone."
- "Bloat. Gone."
- "Headaches. Gone."
- "Energy crashes. Gone."

**Examples (colon, alt form for variety):**
- "Brain fog: gone."
- "Bloat: gone by week 2."

Use sparingly (one per ad, max two). Overused, the rhythm flattens.

---

## TONE CALIBRATION

When in doubt, ask: "Would a friend who's used this product text me
this line?" If yes — keep it. If it sounds like a billboard, rewrite.

The reference brand's voice can be characterized as:
- **Warm but not saccharine** — friendly, never preachy
- **Confident but not arrogant** — "best. purchase. ever." (claimed by
  customers, not the brand)
- **Playful but not silly** — winks and rhymes, but always anchored
  in a real benefit
- **Clean but not sterile** — concrete sensory language ("Mid-night hugs")
  not abstract "wellness journey" language
- **Brand name lowercase** — `babybay` not `Babybay`. (If your brand
  has a stylized cap pattern, respect it but lean toward the lowercase
  warmth where applicable.)
