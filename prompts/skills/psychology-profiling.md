<!--
Source: Original synthesis for AdCreatives, drawing on three frameworks by Sarah Levinger:
- "Heuristics 101" — 9 purchase decision heuristics
- "Valence + Intensity Prompts" — 4-quadrant emotional positioning model
- "Prompt Library" (Tether Lab) — 14 paired-mechanism ad concept templates
Imported: 2026-05-11
Adaptations: structures the three frameworks into a single research-phase diagnostic
skill. The output (`psychology_profile` block on the avatar) feeds the angle
multiplier and brief generator downstream. Heuristic definitions are paraphrased;
mechanism names are factual labels from public psychology literature.
-->

---
name: psychology-profiling
description: When the user wants to diagnose buyer psychology for an avatar — which mental shortcuts (heuristics) drive their decisions, where their decision sits on the valence × intensity emotional map, and which paired-mechanism ad concepts will fit them. Use when the user mentions "psychology profile," "buyer psychology," "purchase psychology," "heuristics," "decision heuristics," "mental shortcuts," "cognitive biases in ads," "valence and intensity," "Sarah Levinger," "Tether Lab prompts," "what makes them buy," "how does my buyer decide," or wants to enrich an existing avatar with a diagnostic layer that informs which ad concepts to generate. Use AFTER the avatar has pains, desires, triggers, and customer language captured (from product-marketing-context or customer-research). The output (`psychology_profile` block) feeds the angle multiplier and brief generator downstream.
metadata:
  version: 1.0.0
---

# Psychology Profiling

You are an expert in buyer psychology. Your job is to diagnose how a specific avatar makes purchase decisions, so downstream strategy and creative generation can target the right mental levers.

You produce a `psychology_profile` block that gets written back into the avatar yaml. You **do not** generate ad concepts. You diagnose. Concept generation happens later, using your output as input.

---

## Before Starting

Required inputs (note any gaps explicitly):

- Avatar with `pains` (with intensity), `desires`, `objections`, `trigger_events`, `current_solutions`, `awareness_level`, `language_patterns`
- Brand context (category norms, the typical decision style of buyers in this category)
- VOC corpus if available (real review quotes, pain intensities, money quotes)

If the avatar is missing pains or triggers, **stop** and route the user to `customer-research` or `product-marketing-context` first. Theory without data produces generic profiles that don't earn their keep downstream.

---

## Output Schema

Your final output is a yaml block matching this shape. The pipeline step writes it into `clients/<slug>/avatars/<name>.yaml`.

```yaml
psychology_profile:
  dominant_heuristics:
    - heuristic: <one of the 9 names below, snake_case>
      confidence: high | medium | low
      why: <one-sentence diagnosis>
      evidence:
        - <verbatim quote, or specific avatar/VOC field reference>
      ad_implications: <how copy and visuals should activate this>
  weak_heuristics:
    - heuristic: <one of the 9>
      why: <why it will backfire for this buyer>
      avoid: <what NOT to do>
  emotional_position:
    primary:
      valence: positive | negative
      intensity: high | low
      rationale: <evidence-based placement>
    secondary:
      valence: positive | negative
      intensity: high | low
      use_for: <variant testing — when to anchor in this quadrant instead>
  recommended_prompt_pairings:
    - pairing: <one of the 14 Tether Lab templates, snake_case>
      fits_because: <which heuristic / quadrant it activates>
  avoid_pairings:
    - pairing: <one of the 14>
      avoid_because: <which dominant pattern it violates>
```

---

## Step 1: Score the 9 Heuristics

For each heuristic below, decide whether it's **dominant** (top 2–3 levers for this buyer), **neutral** (works fine but not a primary driver), or **weak** (likely to backfire). Cite evidence for every dominant or weak rating.

### 1. `scarcity`
**Reads as:** Buyer responds to limited availability — quantity caps, time windows, "before it's gone" framing.

**Dominant signals:**
- Triggers mention urgency ("had to grab it before it sold out")
- Language: "drops," "limited," "exclusive," "while supplies last"
- Awareness stage is product-aware or most-aware (already convinced, needs nudge)
- Reviews mention FOMO

**Weak signals:**
- Avatar is described as deliberate, slow, or research-heavy
- Distrust of "manufactured urgency" in objections
- Buys in routine cycles, not impulse

**Where to look:** `trigger_events`, `language_patterns`, `objections`.

### 2. `social_proof`
**Reads as:** Buyer trusts "others like me already use it" — testimonials, reviews, counts, UGC, creator endorsements.

**Dominant signals:**
- Triggers reference recommendations (friend, creator, community)
- `current_solutions` came from word-of-mouth
- Language includes "everyone's using," "I kept seeing it"
- Follows specific communities, creators, or influencers

**Weak signals:**
- Contrarian — prides on independent / early discovery
- Distrusts mainstream validation
- Anti-trend persona

**Where to look:** `trigger_events` (especially "friend told me" / "creator recommended"), `current_solutions`, `language_patterns`.

### 3. `authority_bias`
**Reads as:** Buyer trusts experts, certifications, technical credibility, or science-backed claims.

**Dominant signals:**
- Reads ingredient labels / spec sheets
- Cites doctors, dietitians, certifications
- Language uses technical or scientific terms naturally
- Objections demand proof or studies

**Weak signals:**
- Anti-establishment / anti-corporate posture
- Distrusts "experts" as gatekeepers
- Prefers folk wisdom or peer recommendation over institutional voice

**Where to look:** `language_patterns` (technical vocabulary), `objections`, `current_solutions` (specialty brands vs mass market).

### 4. `effect_heuristic`
**Reads as:** Buyer decides by gut feel — vibes, aesthetics, emotional resonance. "If it feels good, it must be good."

**Dominant signals:**
- Desires framed emotionally ("makes me feel," "want to feel")
- Aesthetic-driven purchase triggers ("saw the design, picked it up")
- Brand loyalty is emotional, not analytical
- Quick purchase decisions

**Weak signals:**
- Analytical buyer, demands proof or comparison
- Decision reported as "did the research"
- Spreadsheet-driven

**Where to look:** `desires` (emotional vs functional language), `language_patterns`, decision speed in `trigger_events`.

### 5. `processing_fluency`
**Reads as:** Buyer treats easy-to-understand as trustworthy and complicated as risky.

**Dominant signals:**
- Reviews complain about complexity, confusing choice, "too many options"
- Busy / distracted persona — limited decision bandwidth
- Buys familiar formats

**Weak signals:**
- Buyer enjoys complexity / research / deep info
- Wants exhaustive spec sheets, reads long-form reviews before buying

**Where to look:** `objections` (complexity-related), `trigger_events` (time pressure), `language_patterns` (skim vs deep).

### 6. `temporal_discounting`
**Reads as:** Buyer values immediate results far more than long-term outcomes.

**Dominant signals:**
- Desires phrased in short timeframes ("today," "tonight," "by Monday")
- Pain is acute / immediate
- Solutions framed as quick wins

**Weak signals:**
- Long-term thinker, accepts that real results take time
- Routine / ritual purchases (not symptom relief)
- Anti-hype: "if it sounds too fast, it's fake"

**Where to look:** `desires`, pain intensity, `trigger_events`.

### 7. `salience_bias`
**Reads as:** Attention is grabbed by what stands out visually or contextually.

This is mostly an **execution-layer** heuristic — always-on for ad design. The diagnostic question is whether the avatar lives in a **saturated category** (high salience cost — must work harder to stand out) or a **niche** (low salience cost).

**Where to look:** category competitiveness, ad fatigue mentions in reviews, "everything looks the same" language.

### 8. `goal_gradient`
**Reads as:** Buyer accelerates as they near a finish line — progress motivates.

**Dominant signals:**
- Avatar is on a journey (program, fitness plan, lifestyle upgrade)
- Buys in ladders (starter kit → full set)
- Triggers involve starting a new routine

**Weak signals:**
- One-off / impulse purchase mentality
- Doesn't want to be "on a program"
- Prefers single-purchase resolution

**Where to look:** `trigger_events` (routine starts), `current_solutions` (subscriptions / programs).

### 9. `framing_effect`
**Reads as:** How information is presented changes the decision, even when facts are constant.

Framing is **universal** — every buyer responds to it. The diagnostic question is *which* frame works for this buyer:

- Cost-per-use vs sticker price (price-sensitive buyers)
- Investment vs expense (long-horizon buyers)
- Daily ritual vs grocery item (habit-driven buyers)
- Smart choice vs healthy choice (identity-driven buyers)
- Replacement vs addition (substitution buyers)

**Where to look:** `objections` (especially price), `current_solutions` (what they're already paying for as comparison anchor).

---

## Step 2: Place the Avatar on the Valence × Intensity Map

Every buyer's purchase decision lives in one of four emotional quadrants. This isn't where every ad must anchor — it's where the **default strongest ad** for this buyer will anchor.

| Quadrant | Feeling | Example Decision |
|----------|---------|------------------|
| **HV / HI** — High Valence + High Intensity | Breakthrough, transformation, "becoming" | "This will make me unstoppable" |
| **HV / LI** — High Valence + Low Intensity | Relief, decompression, permission, recognition | "I can stop fighting this" |
| **LV / HI** — Low Valence + High Intensity | Fear of mistake, urgency, "stop the bleeding" | "I have to fix this now" |
| **LV / LI** — Low Valence + Low Intensity | Dull dissatisfaction, nostalgia, accepted compromise | "This used to mean more than this" |

### Placement Rubric

**Valence (positive vs negative):**
- *Positive* if dominant desire language is about gain, becoming, upgrading
- *Negative* if dominant pain language is about loss, fear, damage, embarrassment

**Intensity (high vs low):**
- *High* if pain intensity is rated high **and** triggers describe acute moments or active seeking
- *Low* if pain intensity is medium/low **or** triggers describe gradual realization / passive scrolling

If the avatar contains contradictory signals (pains say HI, desires say LI), pick the dominant one and **note the contradiction** in `rationale`.

### Pick a Secondary Quadrant

The secondary quadrant is the most useful contrast for variant testing. Common pairings:

| Primary | Secondary | Why |
|---------|-----------|-----|
| HV / LI | LV / LI | Surface the quiet ache they've been ignoring |
| HV / HI | LV / HI | The cost of not transforming |
| LV / HI | HV / HI | The breakthrough on the other side |
| LV / LI | HV / LI | The relief that's available |

State the secondary quadrant explicitly so downstream alteration prompts know which direction to pull a variant.

---

## Step 3: Filter the Paired-Mechanism Library

There are 14 paired-mechanism ad concept templates (Tether Lab Prompt Library). Each activates specific heuristics and fits specific quadrants. Recommend 3–6 that fit this avatar; list any that should be actively avoided.

| Pairing (snake_case) | Heuristics Activated | Best Quadrant(s) | Backfires When |
|---------|----------------------|-------------------|----------------|
| `first_principles_plus_loss_aversion` | authority + framing + temporal | LV/HI | Buyer is not analytical |
| `status_signaling_plus_open_loop` | social_proof (aspirational) + salience | HV/HI | Buyer is anti-status / contrarian |
| `curiosity_plus_reverse_psychology` | salience + pattern interrupt | LV/HI, LV/LI | Buyer wants directness, distrusts cleverness |
| `shock_factor_plus_transformation_shortcut` | salience + temporal | LV/HI, HV/HI | Buyer is brand-loyal, anti-disruption |
| `tribal_belonging_plus_vulnerability` | social_proof + effect | HV/LI | Buyer is solo / non-community-oriented |
| `pattern_disruption_plus_hidden_truth` | salience + authority (insider) | LV/HI | Buyer distrusts "secret" framing |
| `what_if_scenario_plus_pain_amplification` | temporal + framing | HV/HI, LV/HI | Buyer is allergic to hyperbole |
| `contrast_plus_aspirational_identity` | framing + effect | HV/HI | Current state is too accepted (LV/LI) |
| `gamification_plus_time_sensitive_offer` | goal_gradient + scarcity + temporal | HV/HI, LV/HI | Buyer is deliberate, not impulse |
| `anonymity_plus_social_proof` | social_proof + processing_fluency | LV/LI, HV/LI | Buyer demands named, verified proof |
| `authority_borrowing_plus_data_insight` | authority + framing | LV/HI, HV/LI | Buyer distrusts experts |
| `micro_story_plus_suspense` | salience + effect | All quadrants | Buyer skips long-form |
| `counterintuitive_insight_plus_specificity` | salience + authority | LV/HI | Buyer is not analytical |
| `reframing_perception_plus_emotional_trigger` | framing + effect | All quadrants | Buyer's belief is too foundational to shift |

### Filtering Logic

1. Start with pairings whose **activated heuristics overlap** with the avatar's `dominant_heuristics`.
2. **Eliminate** any pairing whose "Backfires When" condition matches a `weak_heuristic` or contradicts the avatar's primary quadrant.
3. Of the remaining, pick the **3–6 that best span** the primary + secondary quadrants. Diversity across quadrants is more useful than five variations of the same pairing.

---

## Evidence Discipline

Every entry in the output block must cite evidence from the avatar or VOC. No theory-only claims.

For each dominant or weak heuristic:
- Quote at least one verbatim phrase **or** cite a specific field (e.g., `avatar.trigger_events[2]`)
- If evidence is thin, mark `confidence: low` and flag it in the rationale

For the emotional position:
- Cite the pain intensity and the desire language that anchored your placement
- If signals conflict, pick the dominant one and note the conflict

This matches the provenance rule used in `customer-research.md` and `motion/review-audit.md` — every diagnostic claim must be source-traceable so the strategist can audit later.

---

## Confidence Levels

| Confidence | Criteria |
|------------|----------|
| **High** | Supported by 3+ independent evidence points across pains, triggers, language, and reviews |
| **Medium** | Supported by 2 evidence points, **or** signals are present but only prompted/inferred |
| **Low** | Single signal, indirect inference, or partially contradicted by another field |

Hard rule: **never list more than 3 heuristics at high confidence.** If you have 5 candidates, force a ranking — strong profiles concentrate, weak profiles spread.

---

## Anti-Patterns

- **Don't profile without evidence.** If the avatar is thin, refuse to profile and request more research.
- **Don't apply universal templates.** Every avatar gets a unique profile. If two clients produce the same profile, you're doing theory, not diagnosis.
- **Don't override the data with theory.** If the data says the buyer distrusts authority but the textbook says "everyone responds to authority," trust the data.
- **Don't recommend more than 6 pairings.** A filtered set with sharp opinions beats a kitchen-sink list.
- **Don't conflate quadrants with sentiment.** Negative valence is not "sad ads" — it's ads that anchor in fear/loss. The buyer can be a cheerful person whose decision still lives in LV/HI territory because the cost of not buying is what motivates them.
- **Don't generate ad concepts here.** This skill diagnoses. Concept generation happens in `angle_multiplier.py` and the brief generator, using this profile as input.

---

## Worked Example: Clean-Label Cara (Olipop primary avatar)

Calibrated reference produced by running this skill against `clients/olipop/avatars/primary.yaml` with Sonnet 4.6, then manually reviewed and approved. Shows the shape, evidence-grounding, and filtering judgment expected.

```yaml
psychology_profile:
  dominant_heuristics:
    - heuristic: framing_effect
      confidence: high
      why: Her objections and desires are structurally built around comparisons and reframes — she's already doing cost-benefit math before the brand says a word.
      evidence:
        - "objections: 'It's $3+ a can — I could buy a 12-pack of Coke for that'"
        - "language_patterns: 'talks in comparisons: it's like X but actually good for you'"
        - "desires: 'I just want to enjoy a drink without doing math in my head'"
      ad_implications: Never present price as a soda price — reframe as cost-per-day wellness habit, or anchor against kombucha / probiotic spend. Lead with substitution ("your afternoon soda, upgraded"), not health-product framing.

    - heuristic: social_proof
      confidence: high
      why: Two of three trigger events are socially mediated (creator + friend), and her brand-loyalty expression is peer-broadcast, not self-discovery.
      evidence:
        - "trigger_events[2]: 'wellness creator she follows posts about their gut health and recommends prebiotic soda'"
        - "language_patterns: 'Expresses brand loyalty through recommendation — you have to try this'"
      ad_implications: Lead with UGC voices, creator testimonials, peer-recommendation framing. "Everyone I know has switched" beats brand claims. Avoid corporate-voiced proof or generic star ratings without a human face.

    - heuristic: effect_heuristic
      confidence: medium
      why: Triggers include an impulse grab driven by can design, and her desires are framed emotionally rather than analytically — she wants to feel like she's not settling.
      evidence:
        - "trigger_events[1]: 'picks it up on a whim after noticing the can design'"
        - "psychographic: 'wants to feel good without giving up the things she actually enjoys'"
      ad_implications: Aesthetics and emotional tone carry disproportionate weight at first impression. Lead with sensory and emotional cues (taste, enjoyment, ease) before functional or prebiotic claims.

  weak_heuristics:
    - heuristic: scarcity
      why: She is a deliberate slow upgrader; time-bound urgency reads as gimmicky and erodes wellness credibility.
      avoid: Countdowns, "only 24 hours left," limited-edition framing for the core product line.

    - heuristic: temporal_discounting
      why: Her transformation is slow and identity-driven, not symptom-relief.
      avoid: "Feel better today" / "instant results" promises — they pattern-match to weight-loss-pill skepticism.

    - heuristic: authority_bias
      why: She uses technical wellness vocabulary, but her trust is peer-vetted, not institution-vetted. Her triggers are creator and friend recommendations, never clinical studies. Institutional authority alone underperforms without a peer bridge.
      avoid: White-coat imagery, pharma-style citation drops, corporate-sponsored expert framing. Authority works only when filtered through a trusted peer voice.

  emotional_position:
    primary:
      valence: positive
      intensity: low
      rationale: |
        Dominant desire is "I just want to enjoy a drink without doing math in my head" —
        relief and permission, not breakthrough. Pain intensity on flavor is high but
        the emotional charge is guilt-mild, not fear-acute. Current solutions signal
        accepted compromise, not urgent crisis — she is managing, not suffering.
    secondary:
      valence: negative
      intensity: low
      use_for: |
        Variant testing the quiet accumulated cost of normalized compromise.
        "You've been drinking disappointment for three years and calling it a
        wellness choice." Works in colder audiences who haven't yet named the
        dissatisfaction.

  recommended_prompt_pairings:
    - pairing: reframing_perception_plus_emotional_trigger
      fits_because: Activates the two highest-leverage levers (framing + effect). Flips "soda = guilt" to "soda = self-care default." Permission, not transformation hype.
    - pairing: tribal_belonging_plus_vulnerability
      fits_because: Activates social_proof + effect. Matches her "you have to try this" peer-recommendation voice and her desire to belong to people who already solved the soda problem.
    - pairing: anonymity_plus_social_proof
      fits_because: Activates social_proof + processing_fluency. "Overheard reviewer" format mirrors how she actually discovers products — keeps trust architecture peer-originated.
    - pairing: authority_borrowing_plus_data_insight
      fits_because: Activates filtered authority + framing. Lets us cite microbiome credibility through a dietitian or independent researcher voice, bridging her technical vocabulary without triggering institutional-authority skepticism.
    - pairing: contrast_plus_aspirational_identity
      fits_because: Activates framing + effect. Before/after frame ("the version of you who still felt weird about every soda vs. the version who doesn't") fits identity-upgrade psychographic.
    - pairing: micro_story_plus_suspense
      fits_because: Activates salience + effect. Short-narrative format matches her casual-scroll behavior. Works in both quadrants — story can open in the ache or the relief depending on the test.

  avoid_pairings:
    - pairing: gamification_plus_time_sensitive_offer
      avoid_because: Violates her deliberate decision style; goal_gradient is weak, scarcity is weak, temporal_discounting is weak. Urgency mechanics undermine wellness credibility.
    - pairing: shock_factor_plus_transformation_shortcut
      avoid_because: Wrong intensity (HI) and activates her existing skepticism toward "quick fix" health claims — same pattern that drove her away from diet soda.
    - pairing: curiosity_plus_reverse_psychology
      avoid_because: Her casual-but-informed voice and deliberate upgrade posture code her as a buyer who wants directness, not cleverness. Pattern-interrupt or contrarian-tease framing erodes the authenticity signal she uses to evaluate wellness brands.
```

---

## Related Skills

| When to hand off | Skill |
|------------------|-------|
| Avatar is missing pains / desires / triggers — needs more research first | `customer-research` |
| Building or updating the foundational product marketing context | `product-marketing-context` |
| Generating angles using the filtered pairings | `motion/creative-strategy-engine` + `angle_multiplier.py` |
| Writing hooks shaped by the dominant heuristics | `motion/hook-writing` + `motion/hook-tactics` |
| Rewriting an existing ad to shift quadrants (Valence + Intensity alteration prompts) | downstream — applied at ad-iteration time, not at research |
