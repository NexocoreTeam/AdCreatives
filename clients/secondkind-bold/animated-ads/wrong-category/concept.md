---
client: SecondKind (Bold)
concept: wrong-category
persona: Done-Everything Danielle
awareness_stage: problem_aware
angle: "The ~70% transit-death mechanism, vindication, postbiotics deliver what bacteria were supposed to make"
style: pixar
variant: talking-cast
anchor_frame: generated/P01-b.png   # confirmed
status: "all 15 stills generated, pending review then video"
picks: { gut: P05-a (16c6b7f6), hero: P09-v5b (9fcea811, real bottle + lid-face, small in frame), product: P15-a (87d6ed2b) }
---

# Pilot: "The Wrong Category"

Done-Everything Danielle, problem-aware. Voice: our four-beat arc and receipts (name the suspicion, diagnose the mechanism, vindicate, convert). Structure: borrowed talking-character cast. Pixar style art-directed to the SK Bold editorial palette so personification reads premium, not as AI slop.

## Cast
- **Probiotic**: the old category. Sympathetic, doomed, the fall guy for the delivery model. Sheepish, honest, not silly.
- **Gut**: the customer's gut. Tired victim, waiting for compounds that never arrive. Weary, dry, warm.
- **Gut Balance**: the brand product as the calm hero. Grounded, confident, science-literate peer who sides with her.

## Style tag (reused verbatim in every image prompt)
> Pixar animation style, high-end 3D render, soft ambient lighting, cinematic depth of field, rounded soft geometry, subtle subsurface scattering, studio-quality; SecondKind editorial palette: warm snow-white (#fefcf6) background, muted stone and charcoal neutrals, a single marigold (#fcb348) accent; clean minimal premium studio, refined not cartoonish; 9:16 vertical.

Palette-lock clause appended to every prompt after P1: "lighting and palette matching P1, warm snow-white and stone with marigold accent, no cool blue-grey tones, no harsh shadows."

## Character bible (feed forward as reference images)
- **Probiotic**: a small translucent pale-blue gel capsule character, rounded soft body with a faint glossy sheen, big slightly worried eyes, short stubby arms, gentle sheepish posture; sympathetic, not goofy.
- **Gut**: a soft coral-pink anthropomorphized gut-lining character, gentle sculpted folds, tired expressive eyes, slightly slumped weary posture; warm and sympathetic.
- **Gut Balance**: the dark amber glass apothecary jar (glossy black lid, stone-grey papery label) as a Pixar hero with a kind confident sculpted face and a subtle warm marigold glow; dignified, premium, not cartoonish.
- **Woman (Danielle)**: a Pixar woman in her late 30s, natural brown hair, warm relatable everyday look; appears only in P7 and P8; reacts silently, never speaks. (Optional: use Danielle Soul `64cbc304-...` if generating photoreal instead of Pixar.)

## 1. Script (scene table)

| # | VO (speaker) | On-screen | Speaks |
|---|---|---|---|
| P1 | **Probiotic:** "I'm the probiotic you've taken every morning for two years." | Pale-blue capsule alone on a clean snow-white set. Sheepish. (World + palette anchor.) | lip-sync |
| P2 | **Probiotic:** "Here's what I never told you. Roughly 70% of me dies in your stomach before I reach your gut." | Capsule at the edge of a churning amber-acid stomach, looking down. | lip-sync |
| P3 | **Probiotic:** "The trip is brutal. Most of us don't survive it." | Tiny bacteria tumble into the acid and fade as the capsule watches. | lip-sync |
| P4 | **Probiotic:** "The few who make it are supposed to move in and stay. We almost never do." | Two survivor bacteria try to grip a glossy gut wall, slide off. | lip-sync |
| P5 | **Gut:** "I'm her gut. I've been waiting years for these guys to actually make something." | Weary coral-pink gut-lining character, slumped, faint clock behind. | lip-sync |
| P6 | **Gut:** "Still waiting." | Gut alone, calendar pages drifting, flat light. A held beat. | lip-sync |
| P7 | **Gut (VO):** "She eats clean. She trains. She still feels bloated and uncomfortable by dinner." | Pixar woman, salad in a bright kitchen by day, uneasy by evening. | VO, woman silent |
| P8 | **Gut (VO):** "And she's started to think it's her fault." | The woman, end of day, hand on stomach, quiet self-doubt. | VO, woman silent |
| P9 | **Gut Balance:** "It was never her fault. It was the delivery." | Amber jar hero steps in, warm marigold glow lifts the room. | lip-sync |
| P10 | **Gut Balance:** "I'm a postbiotic. I'm what those bacteria were supposed to make in the first place." | Hero in a calm pose, microbiome dot-cluster shimmering behind. | lip-sync |
| P11 | **Gut Balance (VO):** "Already made. Already active. Nothing to survive on the way down. Nothing to move into." | Cross-section: a warm compound flows straight into the gut wall, bypassing the acid. | VO, no characters |
| P12 | **Gut Balance (VO):** "Your gut finally gets what it was waiting for." | The Gut straightens, brightens, the slump gone. | VO, Gut reacts silently |
| P13 | **Gut Balance (VO):** "In an 84-day study, people reported less bloating, less stress, better days." | Editorial proof card, "84-day study" in serif, calm gut beside it. | VO, no characters |
| P14 | **Gut Balance:** "You weren't wrong to keep trying. You were just handed the wrong category." | Hero front and center; the probiotic gives an accepting nod, steps back. | lip-sync |
| P15 | **Gut Balance (VO):** "Try Gut Balance for 60 days. If your gut doesn't feel different, you don't pay." | Real product hero shot, amber jar on snow-white, CTA fades in. | VO, product only |

Spoken runtime lands around 45 to 50 seconds.

## 2. Nano Banana Pro image prompts (P1 to P15)

Settings: model `nano_banana_pro`, 9:16, 2k, 3 variations, pick best. Feed P1 (anchor) as a reference image into P2-P6 and P14; feed P9 into P10 and P14; feed P5 into P6, P12, P13; feed a real Gut Balance photo into P9 and P15.

```
P1: [style tag]. A single small translucent pale-blue gel capsule character centered on a seamless warm snow-white studio floor: rounded soft body with a faint glossy sheen, big slightly worried eyes, short stubby arms, gentle sheepish posture. Soft warm key light from upper left, clean negative space above for text. This frame sets the world: lock this palette and lighting.

P2: [style tag]. The same pale-blue gel capsule character (reference P1) standing at the edge of a softly churning warm-amber acidic stomach environment, looking down with worry. Faint acidic haze and gentle bubbles below, the capsule small against the space. Lighting and palette matching P1, warm tones, no cool blue-grey.

P3: [style tag]. The pale-blue capsule character (reference P1) at the left edge of frame. In the mid-ground, several tiny rounded bacteria characters tumble into a swirling warm-amber acidic pool and softly dissolve, expressive faces, melancholy but gentle. Palette and lighting matching P1, no cool tones.

P4: [style tag]. The pale-blue capsule character (reference P1) in the foreground. Behind it, two small bacteria characters try to grip a glossy curved coral-pink gut wall and slide back down. Soft warm interior-body setting. Palette matching P1.

P5: [style tag]. A soft coral-pink anthropomorphized gut-lining character: gentle sculpted folds, tired expressive eyes, slightly slumped weary posture, seated in a warm soft interior-body environment with a faint glowing clock motif behind. Sympathetic and dignified. Lighting and palette matching P1.

P6: [style tag]. The same coral-pink gut-lining character (reference P5) alone, slumped and waiting, soft calendar pages drifting past in the muted background, flat quiet light. Palette matching P1.

P7: [style tag]. A Pixar woman in her late 30s with natural brown hair, warm relatable everyday look, in a bright minimal kitchen holding a fresh salad in daylight, expressive and real, not glamorized. Composition leaves room for a later evening beat. Lighting and palette matching P1, warm snow-white and stone.

P8: [style tag]. The same Pixar woman (reference P7) in the evening, seated, resting a hand on her stomach, eyes lowered in a quiet private moment of self-doubt. Soft muted warm light, gentle and non-shaming. Palette matching P1, no harsh shadows.

P9: [style tag]. The SecondKind Gut Balance hero character stepping into frame: a dark amber glass apothecary jar with a glossy black lid and a stone-grey papery label, a kind confident sculpted face, dignified premium presence, a warm marigold glow spreading around it and lifting the room. Reference the real product for jar shape. Palette matching P1 with a stronger marigold accent, warm tones only.

P10: [style tag]. The amber glass jar hero character (reference P9) in a calm centered hero pose. Behind it, a soft cluster of glowing white dots with a single marigold dot (the SecondKind microbiome motif) shimmers gently. Soft warm glow, premium and calm. Palette matching P1.

P11: [style tag]. A clean educational cross-section of a coral-pink gut wall. A glowing warm compound flows directly and smoothly into the tissue from a small stream, bypassing a faded acidic stomach shown off to one side. Warm scientific aesthetic, glowing particles, clean minimal background. Palette matching P1, no cool blue-grey.

P12: [style tag]. The coral-pink gut-lining character (reference P5) now upright and relieved, folds smoothed, eyes bright, warm light growing around it, the microbiome dot cluster brightening behind. Hopeful and calm. Palette matching P1, warm tones.

P13: [style tag]. A clean editorial proof card in the Pixar world: the words "84-day study" set in a classic condensed serif on a warm snow-white panel, soft settling particles, the calm coral-pink gut character (reference P12) resting beside it. Refined, magazine-like. Palette matching P1.

P14: [style tag]. The amber glass jar hero character (reference P9) front and center with quiet conviction. Beside it, the small pale-blue probiotic capsule (reference P1) gives a small accepting nod and steps back. Warm reconciling light. Palette matching P1.

P15: [style tag]. Premium product hero shot of the real SecondKind Gut Balance jar: dark amber glass, glossy black lid, stone-grey papery label with "Gut Balance" in a classic condensed serif and small sans-serif detail text, centered on a seamless warm snow-white studio set. A soft cluster of white dots with one marigold dot shimmering, clean negative space below for a call-to-action line. Reference a real product photo for label accuracy. Palette matching P1, premium editorial finish.
```

## 3. Kling animation prompts (V1 to V15)

Settings: Kling 3.0 (or Veo 3.1) image-to-video, 9:16, ~8s, 1080p, start frame = the matching Pn still. Mute generated audio; the VO is layered separately. Optional end-frame blends on the mechanism run (P10 to P11 to P12).

```
V1: Animate this small translucent pale-blue gel capsule character talking calmly and a little sheepishly to camera saying: "I'm the probiotic you've taken every morning for two years." It shifts its weight and gives a small resigned shrug, faint sheen rippling; the snow-white studio stays clean and still. Pixar animation style.

V2: Animate this pale-blue gel capsule character talking to camera with a quiet confession saying: "Here's what I never told you. Roughly 70% of me dies in your stomach before I reach your gut." It glances down toward the churning stomach, eyes worried, body tensing; a faint acidic haze drifts behind. Warm palette matching the prior shot, no cool tones. Pixar animation style.

V3: Animate this pale-blue capsule character at the edge of frame talking to camera saying: "The trip is brutal. Most of us don't survive it." Behind it, tiny rounded bacteria tumble into a swirling acidic pool and gently fade as it watches. Only the capsule speaks; the falling bacteria stay silent. Warm palette matching prior shots. Pixar animation style.

V4: Animate this pale-blue capsule character talking to camera saying: "The few who make it are supposed to move in and stay. We almost never do." Behind it, two small bacteria try to grip a glossy curved gut wall and slide back down. Only the capsule speaks, expression apologetic; the bacteria stay silent. Palette matching prior shots. Pixar animation style.

V5: Animate this soft coral-pink gut-lining character talking wearily to camera saying: "I'm her gut. I've been waiting years for these guys to actually make something." Its folds sag slightly, tired eyes shifting, a slow weight-shift of fatigue; a faint clock motif glows softly behind. Warm palette matching prior shots. Pixar animation style.

V6: Animate this coral-pink gut-lining character delivering two flat, tired words to camera: "Still waiting." It barely moves, a small slump and a slow blink; calendar pages drift past in the soft background. Palette matching prior shots. Pixar animation style.

V7: Animate this Pixar woman in her late 30s in a bright minimal kitchen, holding a salad in daylight, her expression shifting from fine to quietly uneasy as evening light settles and she rests a hand on her stomach. She does not speak, no lip-sync. As a tired voiceover says "She eats clean. She trains. She still feels bloated and uncomfortable by dinner," her posture softens. Warm palette matching prior shots, no speaking on screen. Pixar animation style.

V8: Animate this Pixar woman at the end of the day, resting a hand on her stomach, eyes lowered in a quiet private moment. She does not speak, no lip-sync. As a soft voiceover says "And she's started to think it's her fault," her shoulders lower slightly. Muted warm tone matching prior shots, no harsh shadows, no speaking on screen. Pixar animation style.

V9: Animate this dark amber glass jar hero character with a kind confident face stepping into frame as a warm marigold glow spreads, talking gently to camera saying: "It was never her fault. It was the delivery." It moves with calm authority, a soft golden glow pulsing once as it speaks; the room brightens. Warm snow-white and amber palette, no cool tones. Pixar animation style.

V10: Animate this amber glass jar hero character in a calm hero pose talking to camera saying: "I'm a postbiotic. I'm what those bacteria were supposed to make in the first place." A soft cluster of glowing white dots, one marigold, drifts and shimmers behind it; its glow breathes steadily with quiet confidence. Palette matching prior shots. Pixar animation style.

V11: Animate a clean cross-section of a gut wall as a glowing warm compound flows directly and smoothly into the tissue, bypassing an acidic stomach entirely; the tissue gently illuminates. No characters speak, no lip-sync. As a calm voiceover says "Already made. Already active. Nothing to survive on the way down, nothing to move into," the glow settles like a deep exhale. Warm palette matching prior shots, no speaking on screen. Pixar animation style.

V12: Animate this coral-pink gut-lining character straightening up, sagging folds smoothing, tired eyes brightening, posture lifting as warm light grows and the microbiome dots brighten. It does not speak, no lip-sync. As a calm voiceover says "Your gut finally gets what it was waiting for," it stands tall and settles, relieved. Palette matching prior shots, no speaking on screen. Pixar animation style.

V13: Animate a clean editorial proof card resolving: the words "84-day study" sharpen into focus in a classic condensed serif on a warm snow-white panel, soft particles settling, the calm gut character resting beside it. No characters speak, no lip-sync. As a calm voiceover says "In an 84-day study, people reported less bloating, less stress, better days," the type gently sharpens. Palette matching prior shots. Pixar animation style.

V14: Animate this amber glass jar hero character talking to camera with quiet conviction saying: "You weren't wrong to keep trying. You were just handed the wrong category." Beside it, the small pale-blue probiotic capsule gives a small accepting nod and steps back, mouth closed and silent. Only the jar speaks. Warm palette matching prior shots. Pixar animation style.

V15: Animate a premium product hero shot: the real SecondKind Gut Balance jar on a seamless warm snow-white studio set, a cluster of soft white dots with one marigold dot shimmering gently, a clean call-to-action line fading in below. No characters, no speaking on screen. As a calm voiceover says "Try Gut Balance for 60 days. If your gut doesn't feel different, you don't pay," the lighting warms and the product holds center. Pixar animation style.
```

## 4. Audio

**ElevenLabs (multi-character, Variant A).** One voice per character, generated separately, kept consistent across the ad, speed 1.05 to 1.15x.
- **Probiotic**: mid-range, soft, sheepish, honest, a little deflated. Resigned, owning up.
- **Gut**: weary and dry, faintly deadpan but warm underneath. "Still waiting" lands flat and tired.
- **Gut Balance (hero)**: calm, grounded, quietly confident. A trusted, science-literate peer on her side. Never an announcer, never hype.

**Suno underscore.** Restrained orchestral underscore, soft piano and warm strings, editorial and premium (not childlike). Arc starts curious and a little melancholy, lifts to warm and hopeful at the hero entrance, settles calm and confident at the close. Minimal, sophisticated, European restraint. Sits under the VO. No vocals.

## 5. Production notes
- Generate all 15 stills first. Lock the P1 palette; feed P1, P5, P9, and a real product photo forward as reference images per section 2.
- Animate each Pn as its own ~8s Kling clip; mute Kling's generated audio.
- CapCut: import V1-V15 in order, speed-map about 2 to 2.5x (Pixar), trim dead frames. Soft mix-dissolves 0.5 to 0.7s on dialogue beats; hard cuts on the fast diagnosis run (P2-P4). Layer the continuous ElevenLabs VO and the Suno underscore.
- Captions via the Captions app, clean "Mini" style, no overlay on the final product frame.
- Export 1080p 30fps. Optional Topaz 2x to 4K 60fps, grain amount 2 size 1.
- Watch the tonal tightrope: if generations come back too cute or too saturated, push them back toward the snow-white editorial restraint before animating. That is the line between premium and "AI slop."

## Pre-flight (SK Bold guardrails) — PASS
- [x] Opens on a probiotic-industry receipt (the ~70% transit-death stat)
- [x] Backs it with the colonization-failure mechanism in the next beat
- [x] Punch lands on the delivery model, never on Danielle
- [x] No competitor brand named
- [x] No doctor-bashing
- [x] Vindicates her ("you weren't wrong to keep trying... the wrong category")
- [x] Closes with mechanism + offer, not an operational lead
- [x] Sentence case; no em-dashes or en-dashes; no prohibited terms
- [x] Body/aesthetic frame on-policy for Danielle (blame lands on the mechanism)

## Generation log
- 2026-05-29: P1 generated x3 via Higgsfield MCP (nano_banana_pro, 9:16, 2k). Jobs `2c3e171a` (P01-a), `c2680fed` (P01-b), `87eadc8f` (P01-c). Anchor locked: **P01-b**.
- 2026-05-29: Wave 1 generated, reference-anchored. P2/P3/P4 ref P01-b; P5 x3 and P9 x3 as best-of-3 establishers; P9/P15 also ref the real product photo (secondkind.com CDN). Picks: gut **P05-a** (`16c6b7f6`), hero **P09-a** (`a1576752`), product **P15-a** (`87d6ed2b`).
- 2026-05-29: Wave 2 generated, anchored to the picks. P6/P12/P13 ref P05-a; P8 ref P07; P10 ref P09-a; P14 ref P09-a + P01-b (two references). P13/P14 completed; P4 failed (transient error, wrong resolution) and was re-rendered successfully as `ce394027`. All 15 scene frames saved (P01-b, P02-P14, P15-a/b).
- Contact sheet helper: `animated-ads/contact_sheet.py`. Storyboard: `generated/_storyboard.png`.
- Spend to date: ~44 credits (balance 2290.74 of 2334.74).
- TODO on review: P13 renders "84-DAY STUDY" in caps; regenerate in sentence case ("84-day study") per SK Bold typography rule. P8 runs a touch dark; optional warm-up pass.
- 2026-05-30: User review. Feedback: hero jar too large (forcing a face above the label oversized the bottle). Fixed P9 at true bottle scale, best-of-3, pick **P09-v2a** (`366f3618`); cascaded P10 (`43d24ddc`) and P14 (`c4267746`) to the corrected hero. P13 regenerated in sentence case (`9bf9687a`). P15 = option A. Review gallery: `review.html`.
- Delivery note: SendUserFile attachments do NOT render in the terminal client. Use `review.html` (opened via Start-Process / preview panel) to show stills going forward.
- Kling 3.0 pricing (preflight): ~16 credits per std 8s clip; full 15-scene video ~240 credits at std. Plan: 3-clip animation test (P1 lip-sync, P9 hero lip-sync, P11 motion-only) first (~48 cr) to validate lip-sync + motion, then the remaining 12.
- 2026-05-30: Hero iteration. "Too big" feedback resolved across rounds: v2 (close-up, too big) -> v3 (small in frame, still had glass shoulder above label) -> v4 (lid-face, no glass above label, but googly eyes + wrap-around arms) -> v5 (refined: real height, small lid-eyes, small arms at sides, small in frame). User picked **HERO B = P09-v5b** (`9fcea811`). Cascaded P10 (`af8108e2`) and P14 (`617964c0`) to it. Lesson: a real jar has no natural face spot; lid-face + small arms + small framing is the workable personification. Generic-skill note worth adding: personify organic shapes freely, but product packaging needs the lid-as-face approach or a no-face real-product reveal.
- 2026-05-30: 3-clip Kling test fired (std, 8s, ~48 cr): V1 P1 capsule lip-sync (`ff74fa41`), V9 hero lip-sync on P09-v5b (`df663697`), V11 P11 mechanism no-speak (`05299c5f`). Note: generate_video flagged a preset match on the hero prompt; declined preset and generated literally. Validating lip-sync + motion before the full 15-clip run.
- 2026-05-31: Test clips approved. P10-v3 (`af8108e2`) and P14-v3 (`617964c0`) verified consistent with Hero B before animating. ElevenLabs MCP installed: `claude mcp add elevenlabs -s user -e ELEVENLABS_API_KEY=... -- uvx elevenlabs-mcp` (user config, not committed). Key valid: Starter plan, 90k chars/mo, our VO ~1.1k chars (~1.2%). Server needs a Claude Code restart to connect; rotate the key after use.
- 2026-05-31: Remaining 12 clips fired (Kling std/8s, ~192 cr). Jobs: V2 `e6ca152a`, V3 `1839e1b4`, V4 `c3f611fa`, V5 `22d3c893`, V6 `9730eef8`, V7 `4c11d929`, V8 `f4860eef`, V10 `611b65b8`, V12 `4d86e07b`, V13 `1b8891c9`, V14 `0216d407`, V15 `538fc9ec`. Plus test clips V1 `ff74fa41`, V9 `df663697`, V11 `05299c5f`. GOTCHA: generate_video repeatedly flags the "IN THE DARK" preset (`24bae836-...`); pass `declined_preset_id` to generate literally.
- 2026-05-31: Rough-cut feedback = raw clips slow + gappy. Reframed: pace is fixed by speed-map 2-2.5x + trim (built `generated/assembled_rough.mp4`, 49.5s silent); flow is fixed by the continuous VO. VO generated via direct ElevenLabs API (`_make_vo.py`, eleven_multilingual_v2). GOTCHA: voice names carry descriptive suffixes ("Brian - Deep, Resonant..."), so match on the leading token. Voices: Brian (hero), Will (probiotic), River (gut). Built VO-timed cut (`_assemble_vo.py`) -> `generated/final_vo.mp4` (61.2s; each clip speed-mapped to its line, continuous VO over the top). Players: assembled.html (VO cut), clips.html (per-clip).
- ElevenLabs usage ~2.2k chars across two passes (~2.4% of the 90k Starter month). ROTATE the key.
- 2026-05-31: KEY LESSON. User rejected the ElevenLabs overlay ("way off"). Cause: the Kling clips (sound:on) already carry a voice LIP-SYNCED to the animated mouths. Replacing it with an external VO (and speeding the video to fit) desyncs the mouths AND mismatches voices. Rule: do NOT mute/replace audio on lip-synced talking-character clips. To tighten pace, trim dead air + speed AUDIO AND VIDEO TOGETHER (atempo + setpts at the same factor) so lip-sync stays locked. `_assemble_kling.py` -> `generated/final_kling.mp4` (67s, dead air trimmed, 1.4x sync-preserving). assembled.html now points to it; ElevenLabs `final_vo.mp4` kept only for comparison.
- OPEN TRADE-OFF: Kling voices are per-clip (not brand-consistent, not controllable). A single consistent brand voice would require re-animating talking shots WITHOUT lip-sync + narrating over them (loses the talking mouths). Decide which matters more.
- 2026-05-31: "Gaps between talking" feedback. ROOT CAUSE: Kling (sound:on) bakes a music/ambient bed + the voice into each clip; the voice fills only part of the 8s and music runs loud to the end. Plain silencedetect and speech-band silencedetect both fail to find the voice-end (music has speech-band energy throughout). Workaround that helped: detect LOUD voice peaks (highpass=220,lowpass=3200 then silencedetect=noise=-16dB:d=0.2) to find voice-START and trim the music lead-ins -> final_kling.mp4 now 61s, gaps mostly closed. RISK: -16dB can clip soft word-onsets; user to verify.
- CLEAN PATH (for a polished ad, not yet done): vocal-isolate the Kling voice per clip (Demucs/Spleeter) to drop its baked music, trim the voice gaps cleanly, then lay ONE consistent Suno music bed under the whole thing. Keeps the liked voice + lip-sync, kills gaps, gives consistent music. Needs a one-time separation-tool install. Else: accept Kling's 15 inconsistent music beds.
- NEXT: user judges 61s cut; decide quick-trim vs clean voice-isolation path; then dissolves + single music bed + export. (Rotate ElevenLabs key.)

## Script v2 (APPROVED 2026-05-31) — supersedes the 15-scene script above

Feedback that drove it: not fast-paced enough, and the script's scene-to-scene logic didn't make sense (POV whiplash I/she/you; redundant vindication; personified-creatures world vs realistic woman). Fixes: ONE POV (direct "you" throughout), TWO characters only (Probiotic confessor + Gut Balance hero), NO separate gut character, ONE vindication, tighter (10 beats). Meta ad, ~50s ok.

| # | Speaker | VO | Visual | start still |
|---|---|---|---|---|
| 1 | Probiotic (lip-sync) | "I'm the probiotic you take every morning. Time for the truth." | probiotic to camera | P01-b `c2680fed` |
| 2 | Probiotic (lip-sync) | "About 70% of me dies in your stomach before I reach your gut." | at the acid | P02 `3da005e5` |
| 3 | Probiotic (lip-sync) | "The few that survive are supposed to move in and stay. We don't." | bacteria slide off gut wall | P04 `ce394027` |
| 4 | Probiotic (VO) | "You eat clean. You train. You're still bloated by 7. And you blame yourself." | human, end of day, hand on stomach (reads as "you") | P08 `e27cd3ae` |
| 5 | Gut Balance (lip-sync) | "It was never you. It was the delivery." | hero jar enters | P09-v5b `9fcea811` |
| 6 | Gut Balance (lip-sync) | "I'm a postbiotic. What those bacteria were supposed to make." | hero + dots | P10-v3 `af8108e2` |
| 7 | Gut Balance (VO) | "Already made. Already active. Nothing to survive, nothing to move into." | mechanism into gut wall | P11 `4180508d` |
| 8 | Gut Balance (VO) | "Your gut finally gets what it's been waiting for." | healthy glowing gut, NO character | NEW |
| 9 | Gut Balance (VO) | "84-day study. Less bloating. Less stress." | clean proof card, NO character | NEW |
| 10 | Gut Balance (VO) | "Gut Balance. 60 days. Feel the difference, or you don't pay." | real product + CTA | P15-a `87d6ed2b` |

Dropped from v1: separate gut character (old P5/P6/P12), third-person woman narration, the double vindication. Beat 4 keeps a human visual but the line is 2nd-person so it reads as the viewer.

### v2 generation log (2026-06-01)
- Reused stills: P01-b, P02, P04, P08, P09-v5b, P10-v3, P11, P15-a. New stills: beat 8 healthy gut `97d9bdb4`, beat 9 proof card `569145c4` (picked proof-b).
- 10 clips regenerated (Kling std/8s, ~160 cr) with new lines. Jobs B01 `b6554c5f`, B02 `4499f3a5`, B03 `442ca6b6`, B04 `69f4229d`, B05 `4f993c6f`, B06 `419bddb0`, B07 `de52f53b`, B08 `f1a2ee43`, B09 `09c7589b`, B10 `148eb16f`. In `generated/clips_v2/`.
- Assembled `_assemble_v2.py` -> `generated/final_v2.mp4` (40.9s, loud-peak leading-trim + 1.4x, Kling voices kept). Player: assembled.html.
- NEXT: user judges v2 flow/pace; then the clean audio pass (isolate voice + single Suno bed) + dissolves + export. (Rotate ElevenLabs key.)
