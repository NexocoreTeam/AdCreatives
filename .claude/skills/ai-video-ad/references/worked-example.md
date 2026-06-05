# Worked Example — SK Bold "Wrong Category"

A complete pass through all six stages. The real artifacts live at
`clients/secondkind-bold/animated-ads/wrong-category/`. Open `concept-v3.md` and
`prompt-pack.md` to see the locked output this skill produces.

---

## The ad in one line
Pixar-style, narrator-led, tongue-in-cheek satire. Blue probiotic capsule-soldiers
cheerfully march off and die in stomach acid; a gold postbiotic capsule + the real product
bottle are the answer. One dry narrator over silent characters; one separate "army cry."

## Stage 1 — concept + script
- **Concept** chosen first: storybook-narrator metaphor (doomed army) + a "back door"
  fakeout. Borrowed structure, not a literal copy.
- **Tone** was the hard part. Several rewrites missed until the touchstone locked it:
  "like Sausage Party, tongue-in-cheek, wholesome picture vs adult-leaning narration, not
  raunchy." Lesson: **lock the tone touchstone before writing lines.**
- **First 2 seconds** name the avatar's world (the probiotics they already take).
- **Math + ear:** 10 scenes; stats spelled out ("seventy percent," "eighty-four day"); the
  CTA was simplified for the ear ("try it for sixty days. if your gut feels nothing, you
  don't pay a cent. go to secondkind.com.").
- Output: `concept-v3.md` (scene table + VO read script + cast). Approved before generating.

## Stage 2 — image generation + character lock
- Nano Banana 2 / Pro, 9:16. Reference chaining held the blue army across scenes 1-3-6 from
  one anchor (job `e6278467`).
- **Minimal prompts + "keep accurate"** was the winning pattern (the user's explicit ask):
  e.g. scene 1 is just "six capsules march out of the bottle toward camera." The only
  art-direction left is the guardrails: real bottle stays short and squat with the real
  label; capsule mouth stays closed; the "back door" sign reads exactly `back door`; the
  two survivors move out of sync. Every one of those is a past failure point.
- Start + end frames for the two-state beats (charge -> wipeout, capsule closed -> open).

## Stage 3 — animation
- Kling 3.0, audio OFF (narrator-led, saves credits). Bookend start+end for scenes 2, 7, 8,
  9; start-only for the single-state beats.
- Prompted the journey ("they charge in and dissolve," not "they are gone"). The big "watch
  for": pills welding amber before they hit the acid (Kling associates "acid" with the
  color); fix is "stay blue until they touch the acid," or have them plunge under and vanish.

## Stage 4 — QC
- Real keep/kill calls that happened: survivor face drifted angry->shocked (killed, reverted
  to the original prompt + "make the last one look concerned"); two pills too in sync
  (re-rolled "out of sync"); capsule mouthing words (re-rolled "mouth closed"); bottle
  generating tall and cylindrical (killed, re-rolled from the real product image + "short,
  squat, wide"). All of these became standing "keep accurate" rules carried forward.

## Stage 5 — post
- `_polish_silent.py`: per-scene head-trim (0.25s), target durations, concat, then
  `eq=contrast=1.03:saturation=1.05:gamma=0.99,noise=alls=6:allf=t+u` for a warm grade +
  light grain to kill the plastic sheen. Reviewed via an HTML player opened with
  `Start-Process`.

## Stage 6 — music + VO + captions
- Suno bed: "playful, mischievous, Wallace-and-Gromit, plucky strings, goofy bassoon, no
  vocals, space for VO." VO is the user's Higgsfield audio step (one narrator + one army
  cry). Mix voice ~ -5dB / music ~ -25dB. Captions last, with the CTA + secondkind.com.

---

## Transferable lessons
1. **Lock tone before lines.** A one-sentence touchstone saved the most rounds.
2. **Minimal prompts + a short "keep accurate" list** beats verbose art direction. Let the
   model invent; protect only the non-negotiables (each is a past failure).
3. **Reference chaining is identity insurance.** Anchor once, chain forward.
4. **The picture is unchanged by copy edits.** When the VO was re-toned, only the words
   changed; the built clips stayed. Keep `concept.md` and `prompt-pack.md` in sync.
5. **Watch the runtime.** Punchy comedic VO ran ~1:30, not the planned ~40s. Catch length
   at the script (Stage 1.4), not in post.
6. **Brand guardrails are load-bearing.** No em / en dashes, jokes on the category not the
   customer, claims stay accurate (the 70% transit-death stat, the 84-day study, the 60-day
   guarantee). Load the brand context first, every time.
