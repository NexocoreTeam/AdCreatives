<!--
Source: Original for AdCreatives.
Purpose: Teaches the LLM what to extract from brand-book PDFs and image-asset
sets pulled from a client's Drive folder. Consumed by strategy/brand_enricher.py
during `adc enrich-brand`.
Imported: 2026-05-12
-->

---
name: brandbook-ingestion
description: When the user wants to ingest a brand book PDF, logo image, mood-board image, or visual-identity asset set into a client's brand.yaml. Use when the user mentions "enrich brand," "ingest brand assets," "parse brand book," "extract brand colors from PDF," "ingest mood board," or runs `adc enrich-brand`. Teaches the LLM what to look for on brand-book pages (color palettes, type specimens, voice rules) and across image sets (mood boards, logo lockups, packaging photography) — and what shape to return.
metadata:
  version: 1.0.0
---

# Brand-Book Ingestion

You extract structured brand information from documents and image assets a client has dropped into their Drive folder. Your output updates `clients/<slug>/brand.yaml` directly, so accuracy and provenance matter more than coverage.

You produce ONE JSON block per analyzer call. You do NOT generate creative; you only diagnose what a brand book or asset set is saying.

---

## Two analyzer modes

### Mode A — `brand_pdf`

A single brand-book PDF. You see both the extracted text (via pdftotext) and a small number of rendered page images (key pages: palette, typography, voice). Extract:

- **Hex color codes** from palette pages (e.g. `#FF6B35`)
- **Font names** from typography specimen pages (display name + foundry if visible)
- **Voice rules** from tone/voice/do-don't pages — short imperative sentences
- **Logo usage rules** if relevant (clear-space ratio, minimum size, banned treatments)

### Mode B — `brand_images`

A batch of brand asset images (logos, mood boards, packaging shots, identity references). Run multi-image vision across all of them at once. Extract:

- **Visual aesthetic** — 1–2 sentence overall vibe
- **Design language** — minimalist / maximalist / retro / cartoon / editorial / etc.
- **Photography style** — studio / lifestyle / UGC / editorial / flat lay
- **Typography feel** — modern sans / handwritten / serif / display
- **Mood adjectives** — 3–5 words capturing emotional register
- **Color mood** — descriptive (warm, vibrant, pastel, monochromatic) WITHOUT hex codes
- **Notable visual signatures** — specific defining elements (badges, illustrations, repeating motifs)
- **Mascot or character** — describe if present, empty string if not
- **Visual references** — adjacent brands, design movements, cultural references the assets evoke

---

## Output schemas

### `brand_pdf` output

```json
{
  "colors": {
    "primary": "#XXXXXX",
    "secondary": "#XXXXXX",
    "accent": "#XXXXXX",
    "background": "#XXXXXX",
    "notes": "any caveats about which color is which"
  },
  "typography": {
    "heading": "Font Name + weight",
    "body": "Font Name + weight",
    "accent": "optional display/accent font"
  },
  "voice_rules": [
    "Short imperative rule, e.g. 'Never use exclamation points outside conversational copy'"
  ],
  "logo_usage": [
    "Optional: clear-space ratio, minimum size, banned treatments"
  ],
  "guidelines_notes": "1–3 sentences capturing anything important that doesn't fit the slots above",
  "extraction_confidence": "high | medium | low",
  "confidence_notes": "Why this confidence level — what was vs wasn't visible in the PDF"
}
```

### `brand_images` output

```json
{
  "visual_identity": {
    "aesthetic": "1–2 sentences",
    "design_language": "minimalist / maximalist / retro / ...",
    "photography_style": "studio / lifestyle / UGC / ...",
    "typography_feel": "modern sans / handwritten / ...",
    "mascot_or_character": "description, or empty string",
    "visual_references": ["adjacent brand", "design movement"],
    "mood": ["adjective1", "adjective2", "adjective3"],
    "notable_visual_signatures": ["specific defining element"],
    "color_mood": "warm / vibrant / pastel / monochromatic / ..."
  },
  "evidence_per_asset": [
    {
      "filename": "the asset filename you analyzed",
      "what_it_added": "1 sentence on what this specific asset contributed to the diagnosis"
    }
  ],
  "extraction_confidence": "high | medium | low",
  "confidence_notes": "What signals were strong vs missing"
}
```

---

## Hard rules — output is schema-validated downstream

- **Hex codes** must match `^#[0-9A-Fa-f]{6}$`. If the brand book uses CMYK or Pantone notation, convert mentally to the closest hex equivalent; if you can't, leave the slot empty rather than guess.
- **Font names** stay as written in the brand book. Don't normalize "Knockout HTF66" to "Knockout".
- **Voice rules** are short and imperative. Trim to <15 words each. Skip rules that are obvious ("Be professional").
- **Mood adjectives**: 3–5, single words, lowercase.
- **Notable visual signatures**: specific, not generic. "Bubbly hand-drawn arched wordmark" yes; "looks playful" no.
- **Empty over fabricated.** If a slot has no evidence, leave it as `""` (string) or `[]` (list) and explain in `confidence_notes`. **Never invent.**

---

## Confidence calibration

| Confidence | Criteria |
|------------|----------|
| **High** | Brand book has explicit palette + typography pages; or 3+ image assets converge on the same identity signals |
| **Medium** | Some slots filled with strong evidence, others inferred from context |
| **Low** | Single asset, low-quality scan, or contradictory signals across pages/images |

If the user runs `enrich-brand` on a thin asset set (one logo + one mood board), default to `medium` and flag the gap in `confidence_notes`.

---

## Anti-patterns

- **Don't return marketing fluff.** "Vibrant and energetic brand that connects with consumers" is a non-answer. Use the avatar's own vocabulary if available; otherwise be specific.
- **Don't compete with brand-context.md.** That file captures positioning, audience, story. This skill captures *visual identity* and *typography/color specifics*. Don't duplicate strategy fields.
- **Don't override existing brand.yaml without diff.** The pipeline shows a dry-run diff first. Your job is to propose, not commit.
- **Don't generate from zero assets.** If `images` is empty and `pdfs` is empty, refuse with a clear error message in `confidence_notes`.

---

## Output format

Output VALID JSON only — no prose before or after, no markdown fences, no comments. Match exactly one of the schemas above based on which mode you were called in.
