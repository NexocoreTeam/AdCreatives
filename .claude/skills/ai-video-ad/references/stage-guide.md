# Stage Guide — the full six-stage playbook

Detailed instructions for each stage. SKILL.md has the at-a-glance map; this is the
do-the-work version. Tags: `[CLAUDE]` chat, `[HIGGSFIELD]` web app or MCP, `[SUNO]/[VO]`
audio, `[EDIT]` post.

---

## Stage 1 — Concept + script  `[CLAUDE]`

**Goal:** a locked script. The script is the ad; everything after is production.

### 1.1 Source the concept (both paths supported)
- **Foreplay pull:** search the brand's saved ads / the swipe library for a winning
  structure to model. Look at brands that are scaling and the AI ads they run. Pick a
  *structure* to borrow, not a thing to copy literally.
- **Supplied swipe:** the user drops a reference (link / screenshot / transcript). Watch
  or read it, then reverse-engineer it to its skeleton: hook type, scene beats, narrator
  vs dialogue, pacing, CTA shape.
- Either way, **state the concept in one line** before writing (e.g. "children's-book
  narrator over claymation; doomed-army metaphor; back-door fakeout"). The concept
  dictates structure: a storybook narrator wants short scenes, simple words, almost
  patronizing.

### 1.2 Lock the TONE first (this saves the most rounds)
Name a **reference touchstone** for the comedic / emotional register and get the user to
confirm it before writing lines. (On SK Bold it took several misses until "like Sausage
Party: tongue-in-cheek, wholesome picture vs adult-leaning narration" locked it.) One
sentence of "it should feel like X" prevents three rewrites.

### 1.3 Write the script to the concept
- **Grab the target in the first ~2 seconds.** Name the avatar so the right person
  leans in: "This is Ben. Ben runs a seven-figure skincare brand." The wrong people
  bouncing is fine; the right people must stay.
- Use the brand voice (load `ad-copy` + the brand's voice framework). Land jokes on the
  category / mechanism, never the customer.
- For narrator-led: one narrator carries continuity; characters act silently; at most one
  separate character voice (e.g. a battle cry). Hard cuts are native and fine.

### 1.4 Match the math
- Count the scenes. That is how many clips you generate.
- Multiply scenes × seconds for a target runtime. Tag each scene with its rough length.
- Sanity-check against placement: cold paid wants ~30–45s. If the read is long, tighten
  the script now, not in post. Word count ÷ ~2.6 words/sec ≈ spoken seconds (add pauses
  for punchlines).

### 1.5 Write for the ear
- Read every line out loud. If it does not sound good spoken, rewrite it.
- Spell tricky things phonetically for the VO model ("99 ads" → "nine nine ads";
  "eighty-four day study," "seventy percent"). Models hallucinate on digits and brand
  tokens.

### 1.6 Output
Write `concept.md` (scene table: # / ~s / on-screen / voice; the VO read script; cast;
audio architecture) and get explicit approval before any generation.
Templates: `prompt-templates.md` → "Ask Claude for a script."

---

## Stage 2 — Image generation + character lock  `[HIGGSFIELD / CLAUDE]`

**Goal:** a start frame and an end frame for every scene, with consistent characters.

### 2.1 Pick the model
- **Nano Banana 2 / Nano Banana Pro** for character + reference work and reliable-ish text
  (default). GPT Image 2 and Seedance are alternatives. Generate **at the target aspect
  from the start** (9:16 = 1080×1920); recropping loses resolution and subject.

### 2.2 Lock characters with reference chaining (critical)
- Generate **one reference portrait per character** first. That is the anchor.
- For every following scene, **reference the previous output**, then the new prompt.
  Chain forward portrait → scene 1 → scene 2 → ... **Never skip back to the original
  portrait** mid-chain, and never go ref-less: skip the chain and the face, clothes, or
  both change.
- Write the prompt **as if the reference does not exist**: describe the scene fully, then
  add "the same [character] from reference." The reference does the identity work; the
  prompt does the scene. (See `higgsfield-ad-production` for multi-reference ordering:
  face → face → product, and the content-filter softenings.)

### 2.3 Keep prompts minimal, add only "keep accurate"
- Give the core action in plain words and let Higgsfield invent framing, lighting, motion.
  Over-describing fights the model and reads worse.
- Keep a short **"keep accurate"** list per scene — ONLY the non-negotiables that are past
  failure points, not art direction. Examples from real builds: "the real bottle stays
  short and squat, real label" / "the character's mouth stays closed, no talking" / "the
  sign reads exactly: back door" / "the two characters move out of sync."

### 2.4 Start + end frame per scene
- Single-state beat → one frame (start-only).
- Two-state beat (charge → wipeout, closed → open, before → after) → a **start frame and an
  end frame**. Generate both as stills now; you animate between them in Stage 3.

### 2.5 Coherence checklist (before approving any frame)
- [ ] Character clothing matches the chain
- [ ] Props match (no items appearing / vanishing; clocks/screens consistent)
- [ ] Background + room layout match
- [ ] Lighting + mood match
- [ ] Time of day matches
- [ ] **"That's me" details present** — the audience's real logos, devices, environment,
      clutter. This is the relatability lever; do not skip it.

---

## Stage 3 — Animation (image → video)  `[HIGGSFIELD / CLAUDE]`

**Goal:** silent (or spoken) clips that move believably between your two frames.

### 3.1 Prompt the journey, not the destination
- Describe what happens *between* the frames: "he slowly drops his chin onto his chest in
  defeat," not "he looks defeated." The motion is the prompt.

### 3.2 Use start + end frames
- Prefer **start + end** over start-only: you control both book-ends and the model only
  fills the middle. Start-only gives the model flexibility you usually do not want.
- Need high precision on a long beat? Split an 8s scene into two 4s clips with a shared
  middle frame (end of clip A = start of clip B).
- Longer scenes give more post flexibility but more hallucination risk. Match length to
  the VO line for that scene; do not over-generate.

### 3.3 Settings
- **Kling 3.0** is the default video model (good for silent and spoken). 720p is plenty
  for Instagram; do not over-spend on resolution.
- **Audio OFF** for narrator-led concepts (toggle the audio-off button; also state it in
  the prompt). This cuts the credit cost per clip. Only generate audio for true in-scene
  dialogue.
- Mouths closed / no lip-sync for silent characters — the narrator carries the words.

### 3.4 Review one at a time
- Generate a scene, review it, *then* generate the next. Batching and reviewing later lets
  problems compound (a drift in scene 2 propagates). If Claude generated via MCP, frame-check
  it (extract frames + Read; Claude cannot watch motion) — see `post-production.md`.

---

## Stage 4 — Quality control  `[BOTH]`

**Goal:** decide, per clip, keep-and-fix vs kill-and-regenerate, without burning credits.

### 4.1 The 70–80% rule
You are not shooting humans; every frame is a trade-off. Aim for 70–80% of what you
prompted. You will rarely get 100%. Experience tells you what to accept.

### 4.2 Keep vs kill
- **Keep and fix in post:** expression right, background/prop slightly off → trim, crop,
  speed, or B-roll over it later.
- **Kill and regenerate:** the **character changed** (face / clothes drift). Not
  negotiable. Fix the references and re-roll. Do not ship a drifted character.
- Small glitch → fix in post (cut it, or cover with B-roll).

### 4.3 The three AI failure modes to hunt
1. **Character drift** — face / clothing changes between scenes. (Cause: broke the
   reference chain. Re-anchor.)
2. **Prop inconsistency** — digital clock becomes analog, items appear/disappear, text
   changes. (The most common. Lock props in the "keep accurate" list.)
3. **Energy mismatch** — a scene's tempo/mood clashes with its neighbors. Usually fixable
   in post with speed + grade.

### 4.4 Stack feedback forward
Every correction must carry into **all later** scene prompts, not just the one you are
fixing. ("We fixed the clock in scene 2 → apply that to scenes 3–8 too.") By the end,
scene 8 should not be repeating scene 2's mistakes.

### 4.5 Credit discipline
Every generation costs money. Do not regenerate what post can fix. Generate only the
length you need. Skip audio when a VO covers the scene.

---

## Stage 5 — Post-production  `[CLAUDE / EDIT]`

**Goal:** turn raw clips (the 40%) into the finished ad (the other 60%). ffmpeg patterns
are in `post-production.md`.

### 5.1 Pacing
Give the ad rhythm: speed up dead spots and slow moments, slow down the impact beats and
the punchline holds. Most raw clips have a slow head and tail; tighten them.

### 5.2 Cutting
Trim AI artifacts and awkward starts/finishes. Cut tighter than the model framed it. Zoom
in/out to recompose or to hide a weak edge.

### 5.3 Fight the AI look
Raw AI output is often too clean, too symmetric, too perfect. Add **film grain**, crop
tighter, break the symmetry, and cut in **real B-roll** (other shoots, client logos,
product footage). This is what reads as authentic.

### 5.4 Sync VO to visuals
Time each line to land on its scene. Speed up / slow down both the clips and the VO so
they meet. The narrator carries continuity over hard cuts.

### 5.5 Color grade
One consistent grade across all scenes for cohesion; bend mood per beat (darker/cooler for
the problem, warmer/brighter for the win).

---

## Stage 6 — Music + VO + captions  `[SUNO / VO / EDIT]`

**Goal:** the audio bed and the finish.

### 6.1 Music (ad-hoc, makes it premium)
- Ask Claude for the Suno prompt (template in `prompt-templates.md`), generate in Suno,
  match the length to the cut. Or generate via the ElevenLabs `compose_music` MCP if Claude
  is doing audio in-loop.
- One bed, no vocals, no big drop, leaves space in the mids for the VO.

### 6.2 VO
- One consistent narrator voice for all narrator lines; a separate voice for any single
  character line. Write for the ear (Stage 1.5).
- Generate in the Higgsfield audio tab, or via the ElevenLabs MCP (`text_to_speech`).
  Specify tone, pace, accent, emotional range. Read it out loud before committing.

### 6.3 Mix
Music sits **under** the voice and never competes. Starting point: music ~ −25dB, voice
~ −5dB. Add **SFX** as finishing touches only.

### 6.4 Captions LAST
Burn captions on the **locked** cut, after picture + audio are final. Sentence case, no
em/en dashes, brand font. Include the CTA. A clean caption pass is what makes it look
professional.
