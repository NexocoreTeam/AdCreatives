# AdCreatives

AI-powered ad creative generation for Meta and TikTok. Combines psychological messaging strategy with AI image generation to produce ads that convert.

## Architecture

```
Strategy Layer          →  Generation Layer  →  Validation Layer
(what to say & why)        (visual execution)    (quality gates)

• VOC Mining               • Prompt Composer      • Brand Compliance
• Schwartz Awareness       • fal.ai Client        • Platform Specs
• Angle Multiplier         • Reference Analyzer   • Legal/Compliance
• Brief Generator          • Platform Adapter     • Performance Loop
• Pattern Learner
• Matrix Builder
```

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

## Requirements

- Python 3.11+
- fal.ai API key (image generation)
- Anthropic API key (strategy/copy)
- OpenAI API key (vision analysis, optional)
