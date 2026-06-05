# Prompt Templates

Copy-paste scaffolds for each stage. Fill the `<...>` slots. These mirror how the 99ads
workflow used Claude (drop a quick brief, let Claude write the production prompts), adapted
to this repo.

---

## A. Ask Claude for the script (Stage 1)

> I need a script for a `<style: claymation / Pixar 3D / isometric / paper-cutout>` video ad
> for `<brand>`. Product: `<product>`. Target: `<persona>` at `<awareness stage>`. The promise:
> `<one promise>`. Concept / reference to model on: `<Foreplay pull or pasted swipe>`. Tone
> touchstone: `<e.g. Sausage Party tongue-in-cheek, wholesome picture vs adult narration>`.
> Placement `<9:16>`, target `<~35s>`, CTA `<offer>`.
>
> Open by naming the avatar in the first 2 seconds. Give me: (1) a scene table (#, ~seconds,
> on-screen action, voice), (2) the clean VO read script, (3) the cast list, (4) the audio
> architecture. Match the math (scene count x seconds). Write for the ear. Obey `<brand>`'s
> voice and prohibited terms. Land jokes on the category, never the customer.

Lock TONE before writing lines. Approve the script before any generation.

---

## B. Ask Claude for the image prompts (Stage 2)

> For each scene in the locked script, give me the Higgsfield image prompt(s). Keep them
> minimal: the core action only, let the model invent framing and lighting. For two-state
> scenes give a START-frame prompt and an END-frame prompt; for single-state, one frame.
> Add a short "keep accurate" line per scene with ONLY the non-negotiables (past failure
> points), not art direction. Note which reference image to chain from. Prepend our global
> style tag. 9:16, 2k.

**Global style tag pattern** (adapt palette per brand):

> `<style> animation style, high-end 3D render, soft ambient lighting, cinematic depth of
> field, rounded soft geometry, studio-quality; <brand> palette: <bg hex> background, <muted
> neutrals>, a single <accent hex> accent; clean minimal premium, refined not cartoonish;
> 9:16 vertical.`

After scene 1, append: *"lighting and palette matching the prior shot, warm tones, no cool
blue-grey."*

**Reference chaining recap:** portrait -> scene 1 (ref portrait) -> scene 2 (ref scene-1
output) -> ... Pass the face reference first in `medias`. Never skip the chain.

---

## C. Ask Claude for the animation prompts (Stage 3)

> Give me the Kling animation prompt for each scene. Describe the JOURNEY between the start
> and end frame, not the destination (e.g. "he slowly drops his chin in defeat"). Mark each
> as bookend (start + end) or start-only. Mouths closed, no talking (narrator carries it).
> Audio off. Note the target clip length tied to that scene's VO line. Flag the one thing
> to "watch for" per scene (the likely failure).

---

## D. Higgsfield settings cheat-sheet

| Setting | Default | Note |
|---|---|---|
| Image model | Nano Banana 2 / Pro | character + reference work; generate at 9:16 from the start |
| Video model | Kling 3.0 | 720p is plenty for IG; Seedance / Veo are alternatives |
| Audio | OFF for narrator-led | toggle the audio-off button; also say it in the prompt |
| References | face -> face -> product | faces first anchor identity |
| Two-state beat | start frame + end frame | you control both book-ends |
| 8s precision | split into two 4s | shared middle frame |
| Concurrency (Ultra) | 6-8 jobs | batch in waves; queue 30-180s |

If Claude generates via MCP: `generate_image` (nano_banana_pro), `generate_video`
(kling3_0, `sound:"off"`), pass refs as `medias:[{role, value:<job_id or https URL>}]`,
`get_cost:true` to preflight. The queue degrades sometimes; resubmit fresh to clear zombies.

---

## E. Ask Claude for the Suno music prompt (Stage 6)

> This is the ad `<one-line vibe>`. Give me a Suno prompt for the background music. I want
> `<playful / mischievous / tense / warm>`, like `<reference, e.g. a Wallace and Gromit
> cue>`. Instrumental, no vocals, no big drop, leave space in the mids for a voiceover,
> length `<match the cut>`.

Example output to paste into Suno:

> Instrumental, ~`<N>`s, ~95 BPM. Playful, mischievous, whimsical comedic underscore. Light
> plucky strings and pizzicato, a cheeky bassoon or tuba being goofy, soft marimba, warming
> into a hopeful turn in the final third. Bright, characterful, premium. No vocals, no big
> drop. Leave space in the mids for a voiceover.

Or generate via the ElevenLabs `compose_music` MCP if Claude is doing audio in-loop.

---

## F. VO direction (Stage 6)

> One narrator voice for all narrator lines; a separate voice for `<the one character line>`.
> Tone: `<dry, deadpan, trailer-narrator>`. Pace: `<unhurried, land the pauses>`. Read for
> the ear; numbers spelled out. Generate in the Higgsfield audio tab, or via the ElevenLabs
> MCP (`text_to_speech`).

Mix: music ~ -25dB under voice ~ -5dB. Captions LAST.

---

## G. `concept.md` skeleton

```markdown
---
client: <brand>
concept: <slug>
version: "vN locked <date>"
persona: <persona>
awareness_stage: <stage>
style: <claymation / pixar / ...>
variant: narrator-led | dialogue
audio_architecture: "<one narrator VO + N character lines + one music bed, laid in post>"
tone: "<touchstone>"
---

# <Concept> — script (locked)

## Cast
- <character> — <one-line design>

## Style tag (verbatim in every image prompt)
> <global style tag>

## Script (locked) — scene table
| # | ~s | On screen | Voice |
|---|----|-----------|-------|
| 1 | 9  | <basic action> | Narrator: "<line>" |

**Math:** <N> scenes ~ <total>s, 9:16.

## VO read script (for the audio tab, read in order, stats spelled out)
1. "<line>"

## Production plan
1. Stills -> 2. Clips (audio off) -> 3. VO -> 4. Assemble -> 5. Music + captions last.
```

## H. `prompt-pack.md` skeleton (per scene)

```markdown
## Scene N - <title> - ~<s> - <start-only | bookend>
**VO:** "<line>"
**Prompt:** <core action, minimal>
**Generate:** <refs + mode; chain from job <id>>
**Keep:** <only the non-negotiables>
```
