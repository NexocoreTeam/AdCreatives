---
name: ai-video-ad
description: >
  End-to-end workflow for producing AI-generated VIDEO ads (animated, claymation,
  Pixar / 3D, isometric, paper-cutout, mixed-media) with Higgsfield + Suno +
  post-production. Use when the user wants to make an animated or AI video ad, "a
  video ad like the 99ads one," a claymation / Pixar character ad, a narrator-led
  ad, or wants to go from concept to script to generated clips to a finished cut.
  Covers six stages: concept + script, image generation with character
  consistency, animation, quality control, post-production, and music / VO /
  captions. Brand-agnostic: reads the active client's context and voice. Pairs
  with higgsfield-ad-production (static image ads), ad-copy + hook-writing (the
  script), and video-editing (post). Trigger on "make a video ad," "animated ad,"
  "claymation ad," "AI ad," "narrator ad," "let's storyboard a video ad," or any
  request to build a short video ad from generated footage.
---

# AI Video Ad — Production Workflow

A repeatable system for making AI video ads that are *good ads*, not "good for AI."
Modeled on the 99ads / Alessio workflow and the SK Bold "wrong category" build.

The job splits across tools. This skill tells you, at every step, **what to do and
where** ([CLAUDE] in chat, [HIGGSFIELD] in the web app or MCP, [SUNO]/[VO] for
audio, [EDIT] for post). Run it stage by stage. Do not jump ahead.

---

## The three principles (read first, hold throughout)

1. **A good ad is a good ad, regardless of how it was made.** AI does not lower the
   bar. You pay the same for the traffic and you compete with every other ad in the
   auction. AI executes what you prompt; it does not tell you what a good hook,
   angle, or pacing is. The creative strategy comes first; the tools come second.
2. **Relatability does the work.** The whole world is available to you, so there is
   no excuse. Put the audience's exact world on screen (their dashboards, their
   logos, their 11pm desk, their specific pain) until they think "that's me." Works
   identically whether the character is claymation, Pixar, or a human.
3. **Post-production is where the magic happens.** Judge the *final ad*, never the
   single raw scene. Plan for ~40% from raw AI output and ~60% from the edit:
   pacing, cutting, fighting the AI look, syncing VO, grading. Individual scenes
   will have dead air, slow moments, and artifacts. That is fine. You fix it in
   post.

---

## How this gets driven (hybrid labor model)

Default split, overridable per ad:

| Stage | Default owner | How to decide |
|---|---|---|
| 1. Concept + script | **[CLAUDE]** | Claude writes; you approve concept + tone before anything is generated. |
| 2. Image generation | **[HIGGSFIELD] you, or [CLAUDE] via MCP** | Hero / face-critical / emotional scenes → you generate in the web app. Simple establishers, props, B-roll → Claude can generate via the Higgsfield MCP. |
| 3. Animation | **[HIGGSFIELD] you, or [CLAUDE] via MCP** | Same rule as stage 2. |
| 4. Quality control | **Both** | Claude frame-checks any MCP-generated clip (extract frames + Read; Claude cannot watch motion). You eyeball the web-generated clips. |
| 5. Post-production | **[CLAUDE / EDIT]** | Claude assembles with ffmpeg (trim, concat, speed-map, grade, grain, VO mux, captions). |
| 6. Music + VO + captions | **[SUNO]/[VO] you, or [CLAUDE] via MCP** | You generate in Suno + Higgsfield audio, or Claude generates via the ElevenLabs MCP. Captions LAST, always. |

**At kickoff, set the "who generates" flag for this ad** (you / Claude-MCP / split)
so every stage knows the hand-off.

---

## Per-ad intake (gather before Stage 1)

Ask for whatever is missing; pull the rest from the brand's context:

- **Brand / client** → load `clients/<slug>/` docs or the brand context skill (voice,
  prohibited terms, palette, fonts, guardrails). Obey them. Every brand differs.
- **Product + the one promise** the ad makes.
- **Persona + awareness stage** (from the brand's strategy matrix / creative-strategy-engine).
- **Concept / reference** → Foreplay pull or a swipe you supply (see Stage 1).
- **Visual style** (claymation, Pixar 3D, isometric, paper-cutout, realistic, etc.).
- **Placement + duration** (default 9:16, ~30–45s for cold; longer ok for warm).
- **Offer / CTA.**
- **Audio architecture** → narrator-led (one VO over silent characters, hard cuts) or
  in-scene dialogue (lip-sync, costs more credits). Plus the music vibe.

---

## The six stages (at-a-glance)

Full checklists, prompt templates, and gotchas live in `references/`. The short
version:

### Stage 1 — Concept + script  `[CLAUDE]`
The script *is* the ad; everything after is production. Choose the concept **before**
writing a word — the concept shapes the structure. Lock the **tone** with a
reference touchstone first (this is what saves the most rounds). Write the script to
the concept's format, **match the math** (count scenes × seconds so you know how many
clips and how long each runs), and **write for the ear** (read it aloud; spell tricky
words phonetically for the VO). Grab the target in the first ~2 seconds by naming the
avatar ("This is Ben. Ben runs a seven-figure skincare brand").
→ `references/stage-guide.md` (Stage 1) and `references/prompt-templates.md`.

### Stage 2 — Image generation + character lock  `[HIGGSFIELD / CLAUDE]`
Generate the **start frame and end frame** for each scene. Lock characters with
**reference chaining**: one portrait per character, then every new scene references
the *previous* output, never skipping back to the original (skip the chain and the
face/clothes drift). Keep prompts **minimal** and let the model fill in styling; add
only "keep accurate" non-negotiables (past failure points). Run the **coherence
checklist** (clothing, props, background, lighting, time of day) and stack in
**"that's me" details**.
→ `references/stage-guide.md` (Stage 2). Image mechanics: the `higgsfield-ad-production` skill.

### Stage 3 — Animation (image → video)  `[HIGGSFIELD / CLAUDE]`
Prompt the **journey between the two frames**, not the destination ("he slowly drops
his chin in defeat," not "he looks defeated"). Use **start + end frames** for
control; for an 8s beat that needs precision, split into two 4s clips with a shared
middle frame. **Audio off** for narrator-led concepts (saves credits). **Review one
scene before generating the next** — do not batch-and-review-later; problems compound.
→ `references/stage-guide.md` (Stage 3) and `references/prompt-templates.md`.

### Stage 4 — Quality control  `[BOTH]`
Every frame is a trade-off; aim for **70–80% great**. **Keep-and-fix-in-post** when
the expression is right but the background or a prop is off. **Kill-and-regenerate**
when the character drifts (face/clothes change) — that is non-negotiable, fix the
references. Watch for the three failure modes: character drift, prop inconsistency,
energy mismatch. **Stack feedback forward**: every correction carries into all later
scene prompts so scene 8 doesn't repeat scene 2's bug.
→ `references/stage-guide.md` (Stage 4 + failure taxonomy).

### Stage 5 — Post-production  `[CLAUDE / EDIT]`
Where the final 60% comes together. **Pacing** (speed up dead spots, slow the impact
beats). **Cutting** (trim AI artifacts, awkward starts/ends; cut tighter than the AI
framed it). **Fight the AI look** (grain, tighter crops, break the symmetry, real
B-roll / client logos). **Sync VO to visuals** so each line lands on its scene.
**Color grade** for consistency and mood.
→ `references/stage-guide.md` (Stage 5) and `references/post-production.md` (ffmpeg).

### Stage 6 — Music + VO + captions  `[SUNO / VO / EDIT]`
Ad-hoc **music** makes it feel premium: ask Claude for the Suno prompt, generate, drop
it under the VO. **VO**: one consistent narrator (plus any separate character voice);
write for the ear. **Mix**: music ~ −25dB sitting under voice ~ −5dB, never competing.
**SFX** as finishing touches. **Captions LAST**, on the locked cut.
→ `references/stage-guide.md` (Stage 6) and `references/prompt-templates.md` (Suno + VO).

---

## File + folder convention (per ad)

```
clients/<slug>/animated-ads/<concept>/
  concept.md            # locked script: scene table, VO read script, cast, audio architecture
  prompt-pack.md        # the Higgsfield execution doc: per-scene prompt + refs + "keep accurate"
  generated/
    clips/              # S01.mp4 ... + the rough concat + the polished cut
    vo/                 # narrator + any character lines
    music/              # the Suno bed
  _polish.py            # ffmpeg assembly (trim heads, concat, grade + grain, mux, captions)
  preview.html          # HTML player(s) for review (open with Start-Process)
```

Source of truth is `concept.md` + `prompt-pack.md`. Keep them in sync when copy changes.

---

## Worked example

The SK Bold "wrong category" ad is a complete pass through all six stages, with the
real `concept-v3.md` and `prompt-pack.md` to model from.
→ `references/worked-example.md`.

---

## Non-negotiables (every ad)

- Obey the **active brand's** voice, prohibited terms, and compliance (claims must
  stay accurate for health/finance/etc.). Load the brand context first.
- Jokes land on the category / the mechanism, **never the customer**.
- **No em / en dashes** anywhere on screen or in these docs. Sentence case unless the
  brand says otherwise.
- The **script is approved before generation**; the **tone is locked before the script**.
- Judge the **final ad**, not the scene. Captions **last**.
