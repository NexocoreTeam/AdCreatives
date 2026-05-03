# tvc-director (reference snapshot)

Source: https://github.com/Ethanxwang/tvc-director
Author: Ethan Wang (@Ethanxwang)
License: MIT (see LICENSE in this directory)
Imported: 2026-05-03

## Why this is here

This is a frozen reference snapshot of the `tvc-director` Cursor/Claude Code skill,
imported as the architectural pattern for our Phase 2 video pipeline. It is
NOT actively executed by AdCreatives code today — files live in `references/`
specifically so they don't get loaded by the existing pipeline.

## What's in this directory

| File | Purpose in the source repo |
|---|---|
| `SKILL.md` | Producer-level orchestration (always loaded) |
| `references/treatment.md` | Creative-director knowledge (creative proposal, narrative models) |
| `references/shot-language.md` | DP knowledge (visual style, shot types, composition) |
| `references/pre-production.md` | Production crew (casting, product shots, location) |
| `references/storyboard.md` | Director knowledge (shot lists, video scripts, product breakdown) |
| `references/delivery.md` | Post knowledge (output formats, 11 common failure modes) |
| `README_en.md` | English overview of the system |

## How we plan to use this

When Phase 2 starts:
1. Port the 7-phase pipeline structure (Brief → Creative → Visual tone → Pre-prod → Storyboard → Review → Delivery)
2. Adopt the output directory layout (`concept.md`, `assets/prompts/`, `keyframes/prompts/`, `video-scripts/`) — already mirrored under `clients/_template/videos/`
3. Add the 8 narrative models (Pain-Solution, Cinematic Product Breakdown, Brand World Crosscut, Lifestyle Film, etc.) to a new `strategy/video_narrative.py`
4. Build a `generators/video_orchestrator.py` that runs the 7 phases and writes outputs to `clients/<slug>/videos/<campaign>/`

## License terms

MIT — see [LICENSE](LICENSE). Copying, modification, and redistribution
permitted with attribution preserved.
