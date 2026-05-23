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

---

## SIGNATURE MOVES (use these patterns — they work)

### Move 1: Negation as identity
The brand identifies itself by what it ISN'T, then redirects to what it IS.

- "Not a crib. A way to [USP]"
- "All wood, never plastic"
- "100% beechwood (never plastic or mesh)"
- "Toxic chemicals are out ❌ All-natural is in ✅"
- "No bars to reach over / No getting out of bed"

Apply to any category: "Not a probiotic. Postbiotics that actually arrive."
"Never live bacteria. Always 1 trillion bioactives."

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

### Move 8: Emoji + 2–3 word benefit
Emoji functions as the icon (the "feature visual"). The phrase is 2–4
words MAX. Never use full sentences here.

- 😴 Better sleep
- 🤱 Closer sleep
- ❤️ Safer sleep
- 🌍 More natural sleep
- 🌱 Naturally non-toxic
- ⭐ 4.9 stars

Apply: 🌱 1T bioactives / 😌 Bloat gone / 💪 Steady energy

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

**Benefit callouts (the "X — gone" pattern is gold):**
- "Bloat clears"
- "Bloat clears by noon"
- "Bloat — gone"
- "Brain fog — gone"
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
- "2pm wall — gone"
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
- "17% fewer sick days — RCT" (if you have the data)

---

## THE "X — GONE" PATTERN (signature move worth its own section)

A move that emerged organically in production: pair a pain word with
an em-dash and "gone". Three beats. Reads as victory. Translates to
nearly any consumer-wellness category.

**Examples:**
- "Brain fog — gone"
- "2pm wall — gone"
- "Bloat — gone"
- "Headaches — gone"
- "Energy crashes — gone"

Use sparingly (one per ad, max two) — overused, the rhythm flattens.

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
