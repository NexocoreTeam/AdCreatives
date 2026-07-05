# SecondKind Native Static QA Checklist

Use this checklist before sending SecondKind UGC-style statics, before/after statics, creator overlays, whiteboards, and competitor-inspired native formats.

## Copy

- Lead with a lived customer thought, not strategy language.
- Keep the first read plain enough for someone who does not know what a postbiotic is.
- Use one idea per frame.
- Prefer lines like:
  - `Still bloated after taking probiotics?`
  - `I finally felt less bloated.`
  - `I just learned why probiotics did not work for me.`
  - `Maybe probiotics were not the answer.`
- Put mechanism or proof second, if it appears at all.
- Do not name competitor brands.
- Do not use disease claims, cure/treat/prevent language, or skinny-promise framing.
- Do not use em-dashes in ad copy.

## Visual Mechanic

- Preserve the reference ad's persuasion mechanic, not its surface design.
- For before/after bloating, the before image must show a clear side-profile or 3/4-side bloating read.
- The before image should be large enough to read on mobile, roughly 32-38% of frame width when used as an inset.
- The after image should feel like a casual phone photo, not a polished studio transformation.
- The SecondKind jar is secondary. It should feel like an incidental prop, not the hero.
- Avoid medical imagery, weight-loss framing, and body-shaming posture.

## Native Text Treatment

- Generate or choose a clean base image with no baked-in text.
- Add text locally after generation.
- For TikTok/CapCut-style captions, use white rectangular line boxes.
- One text line per box, stacked, touching or slightly overlapping.
- Use modest corner radius, not branded pill shapes.
- Use TikTok Sans / CapCut Classic-feeling typography.
- Avoid cream/green branded design pills unless the reference specifically calls for them.
- Text should feel like a creator caption, not a designed ad module.

## QA Before Sending

- Mobile read: can the before inset and main caption be understood in two seconds?
- Taste read: does it feel native, or does it feel agency-designed?
- Claim read: would the line still be safe if a compliance reviewer saw it alone?
- Product read: is the jar recognizable but not distracting?
- Mechanic read: does the image actually communicate the intended transformation?

## Current Approved Pattern

For the v3 before/after bloating creative, the cleanest local overlay is:

```text
I finally felt less bloated.
```

Use the connected white-box TikTok/CapCut treatment from `scripts/finish_story_ramble.py` with `--preset capcut_tiktok`.
