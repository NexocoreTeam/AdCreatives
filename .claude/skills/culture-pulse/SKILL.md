---
name: culture-pulse
description: >-
  Recurring culture-read system that keeps a client's voice alive instead of
  frozen in its brand docs. Scrapes/ingests how the audience actually talks
  right now (TikTok UGC comments, trends, reviews, web research), then updates
  the client's living culture layer: pulse report, vocabulary lexicon with
  expiry dates, and bold-bets ladder. Use when the user says "run a culture
  pulse", "refresh the voice", "what's trending in our space", "is our copy
  current", before any creative sprint, or on the biweekly cadence. Also use
  to review/promote/kill bold bets. Worked example: secondkind-bold.
---

# Culture Pulse

The voice docs (brand-context, voice.yaml, ad-copy skill) are Layers 0-2: law, identity, taste defaults. They change slowly and that's correct. This skill maintains **Layer 3: the culture layer**, which changes weekly and lives in dated, expiring artifacts. The system's premise: documents don't decide what's current, evidence does, on a schedule.

## The operating model (read this first in any fresh session)

**Four layers:**
- L0 Law: claims discipline (FDA/FTC). Never breaks.
- L1 Identity: whose side we're on, where the cut lands. Never breaks.
- L2 Taste defaults: the voice rulebook. Breakable per surface with evidence.
- L3 Culture: vernacular, moods, formats. Expires by default; this skill maintains it.

**Four surface tiers:** T1 comments (max license) → T2 organic → T3 paid organic-style → T4 paid hooks/LPs (full rulebook). L3 wins register conflicts on T1-T2; L0-L1 win everywhere always.

**The promotion ladder:** lines and registers debut at T1/T2, climb on evidence, and a bet surviving 60 days at T3 becomes a proposed edit to the L2 docs. Full rules: `clients/<slug>/culture/bold-bets.md`.

## Artifacts (per client)

```
clients/<slug>/culture/
  pulse-YYYY-MM-DD.md      # the dated read; stale after 30 days
  vocabulary.yaml           # living lexicon; every entry dated, expires (default 60d)
  bold-bets.md              # the ladder: active bets, gate, post-mortems
  guidelines-audit.md       # the layer sort of the existing rulebook (refresh quarterly)
```

If `culture/` doesn't exist for a client, run the guidelines audit first (sort every rule in their voice docs into L0/L1/L2), then a first pulse.

## When to run

- Biweekly (or monthly minimum), and always before a creative sprint.
- When a pulse is >30 days old, treat it as expired: re-run before using.
- Ad-hoc: a trend window opens, a bet hits its kill date, or shipped creative produced surprising comments.

## The run

### 1. Gather signal (pick what's available; never block on a missing source)

**a. Scraped UGC comments (highest signal).** The Tier-3 infra already exists:
- Add *category* search queries to `clients/<slug>/competitors.yaml` (not just competitor reviews): e.g. `tiktok_search_queries: ["bloating tiktok", "probiotics don't work", "gut health honest"]` on the relevant competitor entries, or maintain a dedicated culture entry.
- Run `adc research-social --client <slug> --max-comments 100` (~$1.50-3/run, see docs/tier-3-social-sourcing.md). UGC review comments >> brand-owned comments (validated 10/10 vs 3/10 pain-point yield).
- Read the freshest bundles in `clients/<slug>/research/*-comments/` and `voc/`.

**b. Own-account comments** (once accounts are live): screenshot exports or scraped threads from the client's own posts. This is the feedback loop on shipped boldness.

**c. Web research pass** (always available). Search recipes:
- `<niche> TikTok culture <current month year> trends how people talk`
- `TikTok content trends <current month year> formats sounds brands`
- `<category> reviews reddit how people talk` and platform-discover pages
- One case-study search on a bold brand relevant to the moment
- One legal check if claims territory shifted: `FTC FDA <category> enforcement <year>`

**d. Performance of shipped creative.** Collect any `bends:` tags + results from briefs/post logs since the last pulse. Include the POV-short results log (`clients/<slug>/copy/tiktok-pov-shorts.md`): it is the highest-frequency messaging test bed and its winners are graduation candidates.

**e. Own-feed harvest (operator step, 10 minutes).** Caption formats currently surfacing in the operator's own TikTok/Reels feed: screenshot or transcribe 3-5. These seed the POV-short line bank wrappers and the vocabulary constructions section. Formats older than ~2 weeks in the feed are already stale; harvest fresh each pulse.

### 2. Analyze (five passes over the gathered signal)

1. **Vocabulary extraction:** new phrases, constructions, emoji usage, identity badges, enemy props. Verbatim, with provenance.
2. **Mood/momentum read:** what ambient energy is rising (the user's "energy moving through the culture"). Map each live mood to the client's persona quadrants; flag 1:1 matches as ride-now candidates with windows.
3. **Format shifts:** overlay conventions, sound-led formats, comment-section mechanics.
4. **Bet review:** for each active bet past its review/kill date: promote (next rung), hold, or kill with a one-line post-mortem.
5. **New bet candidates:** anywhere the culture evidence contradicts an L2 default, draft a bet through the six-question gate (in bold-bets.md). Anywhere a bet survived 60 days at T3, draft the L2 guideline edit for operator sign-off.

### 3. Write

- New `pulse-YYYY-MM-DD.md` (TL;DR, audience state, live mood map with windows, register findings, openings, routing).
- Update `vocabulary.yaml`: add new entries (dated, expiring), bump re-observed entries, DELETE expired ones (don't comment them out; the file stays lean).
- Update `bold-bets.md`: statuses, post-mortems, new bets.
- If guideline edits are proposed: list them at the top of the pulse under "Proposed L2 edits (operator sign-off)". Never edit the L2 voice docs without operator approval; that's the one human gate in the loop.

### 4. Route into production

- Creative work in the same session: load the fresh pulse + vocabulary BEFORE writing copy; they govern T1-T2 register.
- Tag every new creative with `bends:` (which L2 defaults it bends) so the next pulse can correlate.
- Trend rides with short windows (sounds, moods): ship through the fast lane (six-question gate), not the full T4 pre-flight.

## Hard rules for this skill

- Every entry and claim in the culture layer carries a date, a source, and an expiry. No undated vibes.
- Decay is enforced: expired = deleted on the next run unless re-observed.
- The culture layer NEVER overrides L0 (claims) or L1 (identity). It only fights L2, and only with evidence.
- Don't borrow teen slang for a 28-50 buyer; borrow constructions and moods, not vocabulary, unless the audience itself uses the word (check scraped comments, not trend listicles).
- Mainstream trends: 24-48h window or skip (late brand participation reads as embarrassing). Niche-native memes: longer half-life, lower risk, prefer these.
- Operator preference flags (e.g. SK Bold: no em-dashes ever; all-lowercase prose previously rejected) are L1: they survive every pulse.

## SK Bold quick links (worked example)

- Layer sort: `clients/secondkind-bold/culture/guidelines-audit.md`
- First pulse: `clients/secondkind-bold/culture/pulse-2026-06-10.md`
- Ladder: `clients/secondkind-bold/culture/bold-bets.md`
- Companion skills: `secondkind-bold-context` (L0-L2 strategy context), `ad-copy` (T3-T4 formats). Load culture artifacts on top for T1-T2 work.
