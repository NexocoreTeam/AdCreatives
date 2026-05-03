# AdCreatives

AI-powered ad creative generation for Meta and TikTok. Combines psychological messaging strategy with AI image generation to produce ads that convert.

## Architecture

```
Strategy Layer          →  Generation Layer  →  Validation Layer
(what to say & why)        (visual execution)    (quality gates)

• VOC Mining               • Prompt Composer      • Brand Compliance
• Schwartz Awareness       • fal.ai Client        • Platform Specs
• Angle Multiplier         • Reference Analyzer   • Copy char limits
• Brief Generator          • Platform Adapter     • Legal/Compliance
• Pattern Learner                                 • Performance Loop
• Matrix Builder
```

The strategy layer loads markdown skills from [prompts/skills/](prompts/skills/) as
LLM system context. Each skill carries an attribution header — see
[Skill provenance](#skill-provenance) below.

## Quick Start

```bash
# Install
pip install -e .

# Copy .env.example to .env and add your API keys
cp .env.example .env

# Create your first client
adc init-client --name my-client

# Edit the brand profile
# → clients/my-client/brand.yaml

# Add a product
# → clients/my-client/products/my-product.yaml

# Add customer reviews for VOC mining (optional but recommended)
# → clients/my-client/voc/amazon_reviews.json

# Mine voice of customer
adc mine-voc --client my-client --category saas

# Generate creative briefs (messaging strategy)
adc brief --client my-client --product my-product --angles 5

# Generate images from a brief + style
adc generate --client my-client --product my-product --style benefit-callout

# Or generate from a reference image
adc generate --client my-client --product my-product --style product-hero --reference ./competitor-ad.png

# Log results for the feedback loop
adc log-result --client my-client --creative-id ad_001 --ctr 2.3 --verdict winner --notes "callouts worked"

# Analyze what's working
adc analyze-results --client my-client --days 90

# Check compliance
adc check-compliance --text "Guaranteed to cure your problems!" --category general supplements

# Validate an image
adc validate --image output/my-client/ad.png --client my-client --platform meta

# List available styles
adc list-styles

# Creative matrix testing
adc matrix --client my-client --product my-product --hooks "pain-number,question,shock" --styles "benefit-callout,lifestyle-ugc" --platforms "meta,tiktok"
```

## Workflow

### 1. Onboard Client
Create brand profile (colors, fonts, tone, audience), add products, add customer reviews.

### 2. Strategy (what to say)
- **VOC Mining**: Extract pain points and exact customer language from reviews
- **Awareness Mapping**: Determine where your audience sits on Schwartz's spectrum
- **Brief Generation**: AI creates messaging angles with hooks, callouts, and visual direction

### 3. Generate (visual execution)
- Pick a style template (product-hero, benefit-callout, lifestyle-ugc, split-comparison, social-proof)
- Composer merges brief + brand + style into a fal.ai prompt
- Platform adapter adjusts for Meta (polished) vs TikTok (authentic)

### 4. Validate & Ship
- Compliance scanner checks for prohibited claims
- Platform checker verifies sizes and specs
- Brand checker confirms color accuracy

### 5. Learn & Iterate
- Log performance data (CTR, CPA, ROAS)
- Pattern learner identifies what works
- Next batch of briefs is informed by real performance data

## Available Styles

| Style | Best For | Description |
|-------|----------|-------------|
| `product-hero` | Product/Most Aware | Clean product shot, minimal text |
| `benefit-callout` | Solution/Product Aware | Product + 3 benefit callouts |
| `lifestyle-ugc` | Problem/Solution Aware | Person using product naturally |
| `split-comparison` | Problem Aware/Unaware | Before/after split screen |
| `social-proof` | Solution/Product Aware | Reviews and trust elements |

## Copy Frameworks

| Framework | Best For | Structure |
|-----------|----------|-----------|
| PAS | Problem Aware | Problem → Agitation → Solution |
| AIDA | Broad | Attention → Interest → Desire → Action |
| BAB | Transformation | Before → After → Bridge |
| FAB | Features | Features → Advantages → Benefits |
| SLAP | Most Aware | Stop → Look → Act → Purchase |

## Hook Diversity Matrix

The angle multiplier enforces one hook per emotional trigger so generated sets
vary across cognitive levers, not just phrasing.

| Slot | Hook Type | Trigger |
|---|---|---|
| 1 | Surprising Stat | Social Proof / Credibility |
| 2 | Story / Result | Empathy + Relief |
| 3 | FOMO / Urgency | Loss Aversion |
| 4 | Curiosity Gap | Intrigue |
| 5 | Direct Address / Call-out | Recognition |
| 6 | Contrast / Enemy | Differentiation |
| 7 | Question | Self-reference |
| 8 | Pattern Interrupt | Pattern break |
| 9 | Controversial | Polarization |
| 10 | Problem-Solution | Pain → relief |

## Copy Validation

Check ad copy against platform char limits before shipping:

```bash
# Single check
adc check-copy --text "Your headline" --platform meta --field headline --trim

# See all platform/field limits
adc list-copy-specs
```

Supported: meta, google, tiktok, linkedin, x — full table in
[validators/copy_checker.py](validators/copy_checker.py).

## Phase 2 — Video (scaffolded, not yet wired)

Per-client video output goes under `clients/<slug>/videos/<campaign>/`. The
directory layout mirrors the [tvc-director](references/tvc-director/) skill —
see [clients/_template/videos/README.md](clients/_template/videos/README.md)
for the structure, narrative models, and intended workflow.

## Brand Onboarding (interview-first research)

```bash
adc research --client my-client --url https://example.com
```

Phase 1 collects 6 batched seed questions (products, audience, competitors,
constraints, existing creative). Phase 2 fetches the homepage and standard
sub-pages. Phase 3 compiles a comprehensive `brand-context.md` doc using
Motion's [brand-intake skill](prompts/skills/motion/brand-intake.md).
Phase 4 walks through extracted fields by confidence (high = auto-accept,
medium = quick confirm, low/unknown = your input), then writes
`brand.yaml`, `products/<slug>.yaml`, and a draft `avatar.yaml`.

## Skill provenance

Markdown skills in [prompts/skills/](prompts/skills/) are imported from
third-party MIT-licensed repos. Each file has an attribution header.

### From [Motion](https://github.com/motion-team/creative-strategy-skills) (Alysha @ Motion)

| Skill | Used by |
|---|---|
| [motion/brand-intake.md](prompts/skills/motion/brand-intake.md) | `strategy/researcher.py` (interview + research → brand-context.md) |
| [motion/review-audit.md](prompts/skills/motion/review-audit.md) | `strategy/voc_miner.py` (5-tier review scoring + 5 insight buckets) |
| [motion/creative-strategy-engine.md](prompts/skills/motion/creative-strategy-engine.md) | `strategy/angle_multiplier.py` (pain × persona × awareness matrix) |
| [motion/hook-tactics.md](prompts/skills/motion/hook-tactics.md) | `strategy/angle_multiplier.py` (35+ tactical hook formats) |
| [motion/hook-writing.md](prompts/skills/motion/hook-writing.md) | `strategy/angle_multiplier.py` (psychologically driven composition) |
| [motion/hook-voice-patterns.md](prompts/skills/motion/hook-voice-patterns.md) | `strategy/angle_multiplier.py` (native-feed swipe file) |
| [motion/creative-mechanics.md](prompts/skills/motion/creative-mechanics.md) | `generators/prompt_engine.py` (structural ad concepts) |
| [motion/visual-formats.md](prompts/skills/motion/visual-formats.md) | `generators/prompt_engine.py` (45+ Meta/paid social formats) |

### From [coreyhaines31/marketingskills](https://github.com/coreyhaines31/marketingskills)

| Skill | Used by |
|---|---|
| [customer-research.md](prompts/skills/customer-research.md) | `strategy/voc_miner.py` (JTBD, confidence scoring, sample bias) |
| [product-marketing-context.md](prompts/skills/product-marketing-context.md) | reference for brand/avatar schema expansion |

### From [DV0x/creative-ad-agent](https://github.com/DV0x/creative-ad-agent)

| Skill | Used by |
|---|---|
| [hook-methodology.md](prompts/skills/hook-methodology.md) | `strategy/angle_multiplier.py` (research-first hook extraction) |
| [hook-formulas.md](prompts/skills/hook-formulas.md) | `strategy/angle_multiplier.py` (10 hook types, organized by emotional trigger) |

Reference snapshot of the [tvc-director](references/tvc-director/) skill
([Ethanxwang/tvc-director](https://github.com/Ethanxwang/tvc-director), MIT)
is kept under `references/` for the future Phase 2 video pipeline.

## Requirements

- Python 3.11+
- fal.ai API key (image generation)
- Anthropic API key (strategy/copy)
- OpenAI API key (vision analysis, optional)
