# Video campaigns for this client

Phase 2 / video output goes here. The directory structure mirrors the
[tvc-director](../../../references/tvc-director/) skill (MIT).

## Per-campaign layout

```
videos/
└── <campaign-slug>/
    ├── concept.md                  # Creative brief (problem, narrative model, key beats)
    ├── storyboard.md               # Shot-by-shot script
    ├── assets/
    │   └── prompts/                # Nano Banana Pro prompts for product / environment shots
    │       ├── product-multiview.md
    │       └── env-01-<scene>.md
    ├── keyframes/
    │   └── prompts/                # Nano Banana Pro prompts for storyboard keyframes
    │       ├── grid-01-brand-world.md
    │       ├── grid-02-product-world.md
    │       └── endframe.md
    └── video-scripts/              # Seedance Multi-Phase prompts
        ├── segment-01-brand-world.md
        └── segment-02-product-breakdown.md
```

## Workflow (Phase 2 — not yet implemented)

1. **Brief** — write `concept.md` from product + brand + avatar (analog of `cli.py brief` for static)
2. **Storyboard** — break the concept into shots (`storyboard.md`)
3. **Assets** — generate product multi-view + environment shots via Nano Banana Pro
4. **Keyframes** — generate storyboard keyframe grids via Nano Banana Pro
5. **Video** — generate Multi-Phase video segments via Seedance, anchored on the keyframes

## Narrative models (from tvc-director)

| Code | Model | Core logic |
|---|---|---|
| A | Pain-Solution | Pain scene → product rescues |
| B | Cinematic Product Breakdown | Multi-phase product micro-film |
| C | Brand World Crosscut | Use-case ↔ product close-up intercut |
| D | Lifestyle Film | Product always in scene, camera highlights |
| E | Emotional Anchor | Story-driven, product as vehicle |
| F | Montage Reveal | Visual spectacle → product reveal |
| G | Before/After | Strong contrast |
| H | Brand Manifesto | Values-driven, product punctuates |
