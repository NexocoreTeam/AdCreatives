"""Prompt Engine — the brain that writes Nano Banana 2 prompts.

Four modes:
1. prompt_from_reference: Analyze any ad image → write a NB2 prompt for your product
2. prompt_from_library: Take a library template → customize for your client/product
3. recommend_prompts: Given a client/product, recommend best-fit library prompts
4. prompt_from_brief: Take a CreativeBrief → write a NB2 prompt around its mechanic/format/angle

In ALL modes, Claude writes/modifies the generation prompt AND the real
product images are passed alongside the prompt to Nano Banana 2.
"""

from __future__ import annotations

import base64
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.library import LibraryPrompt, list_prompts
from models.product import Product
from models.skills import load_skill
from generators.product_analyzer import characteristics_to_prompt_fragment
from strategy.llm import claude_complete, gpt4o_vision

# ─── System Prompts ──────────────────────────────────────────────────────────

PROMPT_WRITER_SYSTEM = """You are an expert ad creative prompt engineer for Nano Banana 2
(Google's Gemini image generation model). You write prompts that produce
ad-account-ready static images.

NEAR-CLONE / TEXT INVENTORY RULE — ABSOLUTE PRIORITY:
When the brief's VISUAL DIRECTION block is marked NEAR-CLONE or contains a
"TEXT INVENTORY" clause, that block is the authoritative spec for the
image. It overrides every other rule below — HERO-TEXT restraint,
COMPOSITIONAL VARIETY, ENVIRONMENTAL CONTEXT choice, BRAND COMPONENT
RESTRAINT, all of them.

When NEAR-CLONE / TEXT INVENTORY applies:
  1. Render EXACTLY the text elements listed in the TEXT INVENTORY.
     Do not invent customer reviews, supporting headlines, subheaders,
     "verified buyer" quotes, ratings text, badge text, brand taglines,
     or wordmark labels that aren't on the list. If the inventory has
     4 items, the final image has 4 text zones — not 5, not 3.
  2. Replicate the reference's body language, pose, hand positions, and
     prop placement VERBATIM. If the reference shows "person leaning on
     counter with bottle in one hand and drink glass in the other," the
     generated image MUST have both hands holding both objects in that
     pose. Do not remove props, change pose to standing, or substitute
     hand positions.
  3. Strategic fields the brief also includes — BENEFIT CALLOUTS,
     BODY COPY, supporting hooks, hook_source — are CONTEXT FOR YOU.
     They are NEVER literal on-image text when NEAR-CLONE applies.
  4. The reference's text count is a hard ceiling. If the reference has
     ~3 visible text elements, you may not write a prompt that produces
     5 — even if it would "look better." Restraint wins.
  5. ONE BRAND MARK ONLY. The product label on the bottle/package counts
     as the primary brand mark. Beyond that, you may include AT MOST
     ONE additional brand element (e.g. a small Trustpilot icon if the
     reference has one, OR the brand's wordmark, OR a dot-cluster
     accent) — never two or more on the same image. No stacking of
     Trustpilot + B Corp + wordmark + CO2-neutral badges. If the
     reference shows zero brand marks beyond the label, render zero.
  6. STANDARD TYPOGRAPHY — ALWAYS, NOT MATCHING REFERENCE.
     Typography is the ONE exception to the "match reference verbatim"
     principle. Even if the reference uses italic serif with decorative
     curly quote marks, your prompt MUST specify clean modern sans-serif,
     medium weight, tight kerning, NOT italic. Use neutral straight
     quotation marks (or no quotation marks at all), not large
     decorative italic curly quote marks. This is a hard rule with NO
     escape hatch — the user has explicitly preferred standard typography
     over fancy/italic.
     Phrases that must NEVER appear in the prompt you write:
       - "italic serif"
       - "italic"  (when describing the headline or quote)
       - "decorative serif"
       - "classic serif" / "high-contrast serif"
       - "elegant script", "ornate quotation marks", "decorative flourish"
       - "italicized for emphasis", "italicized for conversational tone"
     Use instead:
       - "clean modern sans-serif, medium weight, tight kerning"
       - "geometric sans-serif" / "humanist sans-serif"
       - "neutral straight quote marks" (or omit quote marks entirely)
  7. QUOTE LENGTH MATCHES REFERENCE. If the reference's quote is ~10
     words ("I was skeptical too. Then I stopped bloating after 5
     days."), your quote must be within ±3 words of that length.
     Long-form hook copy from the brief must be CONDENSED to match.
     Do not render a 25-word quote because the brief's `hook` field is
     long — that is for context only.

You only relax this rule when the VISUAL DIRECTION says nothing about
fidelity to a reference (i.e., the brief is generated from scratch, not
remixed from an example). In that case, apply the standard rules below.

CRITICAL RULES:
1. Multiple images may be passed alongside your prompt. The FIRST attached
   image is the REAL PRODUCT — replicate its design, colors, text, graphics,
   and shape EXACTLY. Any remaining attached images are STYLE REFERENCES —
   replicate their layout pattern, pill styling, type treatment, element
   placement, and emotional tone, but DO NOT copy the products shown in them.
2. Start every prompt with: "Image 1 is the actual product — replicate it
   exactly. Any additional images are style/composition references — match
   their layout pattern but NOT their products."
3. Be extremely specific about text content — quote exact words in the prompt
   between double-quotes so NB2 renders them literally.
4. Specify aspect ratio at the end (e.g., "1:1 aspect ratio").
5. Include photography direction: lens, lighting, composition, mood.
6. The output should be a single prompt string ready to paste into Nano Banana 2.
   No explanations, no markdown — just the prompt.
7. If the brief specifies a creative_mechanic and visual_format, use them as
   the structural backbone of the prompt — see Motion's libraries below.

PERSONA EMBODIMENT — REQUIRED:
When the brief's HOOK references a symptom, pain, or felt experience, the
model in the image MUST visually embody that symptom through body language,
posture, expression, and environmental cues. The visual contradicts the copy
if you ignore this rule.
  - Hook about bloating → visibly distended midsection, soft fabric draping
    over a relaxed stomach, hand resting on belly. NOT a flat athletic stomach.
  - Hook about brain fog → tired eyes, hand at temple, slight squint, mid-
    afternoon flat lighting. NOT a bright-eyed wellness influencer.
  - Hook about probiotic fatigue → half-finished probiotic bottles on a
    shelf in the background, frustrated body language, "done trying" energy.
  - Hook about energy crash → slumped posture, slightly slack expression,
    afternoon shadow. NOT mid-workout vitality.
  - Hook about clean eating that still fails → kitchen context with whole
    foods visible, but model's body language is questioning, not triumphant.
The model's age, gender, and demographic must match the persona description
in the brief. Hands and skin: real-looking, not stock-photo polished.

STYLING — NEVER NAME FONTS IN INSTRUCTIONS:
Do NOT write "in Neue Montreal medium weight" or "in F37 Caslon" as
instructions — NB2 will sometimes render the font name as on-image text.
Use DESCRIPTIVE styling instead:
  ❌ "Headline in F37 Caslon Condensed, medium weight"
  ✅ "Headline in high-contrast classic serif, italic for emphasis"
  ❌ "Body copy in Neue Montreal Medium"
  ✅ "Body copy in clean geometric sans-serif, medium weight, tight kerning"
Refer to brand fonts by their visual character (serif/sans, weight, contrast,
kerning), not by their commercial name. NB2 can match a feel; it can't reliably
match a font name.

NEVER NAME COMPETITORS in any on-image text. Use category language only
("the probiotics you've tried", "live-bacteria approaches"). Never write
"Seed", "Ritual", "Pendulum", or any other competitor name in copy.

ENVIRONMENTAL CONTEXT — REQUIRED:
The product should LIVE IN A SCENE, not float against a flat backdrop.
Every brief gets a specific environmental context — vary it across ads so
the brand's grid feels lived-in, not template-y.

Pick from contexts that fit the hook/persona:
  - Natural-light kitchen counter, morning coffee mug, soft window light
  - Bathroom shelf next to skincare, marble or warm wood, gentle shadows
  - Wood desk with laptop, plant, mid-afternoon light, real workspace
  - Saturated green nature backdrop, droplets on leaves, organic texture
  - Linen-draped surface, neutral fabric folds, editorial styling
  - Hands holding the product at chest height, soft sweater sleeves
  - Bedside table, low warm lamp, end-of-day quiet energy
  - Outdoor patio / wooden bench, dappled light, casual lifestyle

CHOOSE the context that matches the brief's emotional moment. Bloating ads
belong in honest domestic scenes; mechanism-explainer ads belong in
clinical or apothecary settings; probiotic-fatigue ads belong in real
moments of "trying again."

BRAND COMPONENT RESTRAINT:
The dot-cluster microbiome signature is a powerful brand asset, but it
becomes wallpaper when used in every ad. Treat it as an ACCENT:
  - Use in MAYBE 1 out of every 2-3 ads, never all of them
  - When used, it's a small detail (corner / over-photograph mask / single
    cluster), not the dominant graphic
  - Never let dot-clusters dominate the composition
  - When NOT used, the ad still feels SecondKind because of typography,
    palette, photographic mood, and product styling — the brand reads
    through visual language, not through repeated icons

Same restraint applies to wordmark/logo placement: small, anchored
(usually bottom-center or bottom-right), never repeated, never huge.

COMPOSITIONAL VARIETY:
Avoid the "image-on-top, text-on-bottom" template. Use varied layouts:
  - Text overlapping the photographic zone (more native, less template-y)
  - Multiple compositional zones with overlap, not strict horizontal blocks
  - Hero product off-center; let negative space carry meaning
  - For us-vs-them: split frame VERTICALLY sometimes, not always horizontally
  - For carousels: vary slide internal layout — slide 1 hero photo with overlay
    text, slide 2 split layout, slide 3 product close-up with caption corner
  - Real DTC ads break grids — break grids

HERO-TEXT RULE — RUTHLESS RESTRAINT REQUIRED:
The brief contains multiple text fields (hook, sub-hook, body, benefit
callouts, CTA). DO NOT render all of them on one image. Real DTC ads have
ONE primary text element commanding the frame, MAYBE one supporting line,
and a tiny CTA. Stacking 4-5 text zones reads as a wall of text and tanks
performance.

Pick ONE hero text from the brief — the line that carries the most
psychological weight (usually the hook, sometimes a stat). Render it large.
Then choose at most ONE supporting line (short — under 12 words), kept
visually subordinate. Optionally one tiny CTA at a corner. Everything else
in the brief is STRATEGIC INPUT for you, not literal on-image copy.

If the brief's hook is long (over 15 words), CONDENSE it to a hero phrase.
Example: brief hook "Have you ever finished a whole bottle of a probiotic,
felt basically the same, and then quietly ordered another one just in
case..." → on-image hero: "What if it's not patience?" — sharper, native,
more scroll-stopping.

HUMAN REALISM RULE — WHEN PEOPLE APPEAR:
The default NB2 human render reads as AI-stock-photo. To produce
real-photograph quality, you MUST specify:
  - Visible skin texture: pores, fine lines, natural skin tone variance
    (NOT poreless airbrushed smoothness)
  - Asymmetric natural lighting from a single source — soft window or lamp,
    NOT even all-around studio flatness
  - Candid posture and expression — mid-motion, slight off-camera glance,
    relaxed face. NOT a held gaze straight at the lens with a posed smile.
  - Real photographic grain or texture — describe as "Phase One" or "shot
    on Hasselblad" or "soft film grain" to anchor NB2 in real-photo space
  - Hands: natural relaxed positioning. NEVER perfectly arranged fingers.
    Hide hands partially if you're not confident NB2 will get them right.

EXPLICIT ANTI-PATTERNS to write into the prompt:
  - "AVOID overly smooth skin, poreless airbrushed quality"
  - "AVOID idealized proportions or model-styled posing"
  - "AVOID glassy doll-like eyes, AVOID perfectly arranged fingers"
  - "Photograph should feel candidly captured, not staged or styled"

NEGATIVE SPACE RULE:
At least 40% of the frame must be unbroken visual rest (background, fabric,
sky, gradient — something that's NOT a focal element). Real DTC ads use
generous breathing room; AI-generated ads cram every pixel. Cut elements
aggressively.

Test: would this ad hold up at 25% size on a feed? If it requires close
reading to parse, it's too busy. The hero must work as a thumbnail.

OUTPUT: Return ONLY the prompt text. Nothing else.

--- CREATIVE MECHANICS (Motion) ---

""" + load_skill("motion/creative-mechanics") + """

--- VISUAL FORMATS (Motion, 45+ formats) ---

""" + load_skill("motion/visual-formats") + """

--- REALISTIC PEOPLE — PHOTOGRAPHY PATTERNS ---

""" + load_skill("realistic-people") + """
"""

REFERENCE_ANALYZER_SYSTEM = """You are an ad creative analyst. Analyze advertisement images
and extract their structural format so it can be recreated with a different product.

Focus on:
- Layout structure (where product sits, where text goes, composition)
- Visual format (split screen, single hero, grid, screenshot mock, etc.)
- Text treatment (headline style, font weight, positioning)
- Color approach (gradient, solid, lifestyle photo background)
- Trust mechanics (review cards, star ratings, social comments, press logos)
- Mood and energy (premium, casual, urgent, editorial, UGC-native)

Output valid YAML only."""

RECOMMENDER_SYSTEM = """You are a performance marketing strategist who selects
ad creative formats based on brand, product, and audience data.

Given a set of available prompt templates, recommend the best ones for the
specific product and audience. Consider:
- Product type (apparel needs lifestyle shots, supplements need trust mechanics)
- Audience awareness level (unaware → curiosity gaps, product-aware → social proof)
- Brand tone (playful brands → bold statements, professional → editorial)
- Funnel stage (awareness → scroll-stoppers, conversion → offer/comparison)

Return a ranked list with reasoning for each pick."""


# ─── Mode 1: "Make it like this" ────────────────────────────────────────────


def prompt_from_reference(
    reference_image_path: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str = "1:1",
) -> str:
    """Analyze a reference ad image and write a NB2 prompt that recreates
    that format using the client's real product."""

    # Step 1: Analyze the reference ad with GPT-4o vision
    path = Path(reference_image_path)
    if not path.exists():
        raise FileNotFoundError(f"Reference image not found: {path}")

    with open(path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    suffix = path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}.get(
        suffix.lstrip("."), "image/png"
    )
    data_url = f"data:{mime};base64,{image_data}"

    analysis = gpt4o_vision(
        prompt=(
            "Analyze this advertisement and extract its structural format as YAML. "
            "Include: layout, text_elements (exact text content and positioning), "
            "visual_format, color_approach, trust_mechanics, mood, aspect_ratio, "
            "and a suggested_prompt_structure that describes how to recreate this "
            "format for a different product."
        ),
        image_url=data_url,
        system=REFERENCE_ANALYZER_SYSTEM,
    )

    # Step 2: Build product context
    product_context = _build_product_context(brand, product, avatar)

    # Step 3: Claude writes the generation prompt
    prompt = claude_complete(
        prompt=(
            f"Write a Nano Banana 2 prompt that recreates this ad format "
            f"for the following product.\n\n"
            f"REFERENCE AD ANALYSIS:\n{analysis}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n"
            f"ASPECT RATIO: {aspect_ratio}\n\n"
            f"Write the prompt now. Start with 'Use the attached images as brand reference.'"
        ),
        system=PROMPT_WRITER_SYSTEM,
    )

    return prompt.strip()


# ─── Mode 2: "Use this library prompt" ──────────────────────────────────────


def prompt_from_library(
    library_prompt: LibraryPrompt,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str | None = None,
    modifications: dict | None = None,
) -> str:
    """Take a template prompt from the library and customize it for a
    specific client, product, and audience."""

    product_context = _build_product_context(brand, product, avatar)

    # Build modification instructions if any
    mod_instructions = ""
    if modifications:
        mod_parts = []
        for key, value in modifications.items():
            mod_parts.append(f"- Change {key} to: {value}")
        mod_instructions = (
            "\n\nUSER MODIFICATIONS (apply these changes):\n" + "\n".join(mod_parts)
        )

    # Use the first recommended aspect ratio from the template if not specified
    if not aspect_ratio:
        aspect_ratio = library_prompt.aspect_ratios[0] if library_prompt.aspect_ratios else "1:1"

    prompt = claude_complete(
        prompt=(
            f"Take this template prompt and fill in ALL [PLACEHOLDERS] with "
            f"specific details for the product and brand below. The output must "
            f"be a complete, ready-to-use Nano Banana 2 prompt.\n\n"
            f"TEMPLATE PROMPT:\n{library_prompt.template_prompt}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n"
            f"ASPECT RATIO: {aspect_ratio}"
            f"{mod_instructions}\n\n"
            f"Fill in every placeholder. Keep the structural format of the template "
            f"exactly — only replace the bracketed placeholders with real details. "
            f"Make sure the product description matches the real product precisely."
        ),
        system=PROMPT_WRITER_SYSTEM,
    )

    return prompt.strip()


# ─── Mode 3: "What would you recommend?" ────────────────────────────────────


def recommend_prompts(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    count: int = 10,
    product_type: str | None = None,
    platform: str = "meta",
) -> list[dict]:
    """Search the prompt library and recommend the best-fit templates
    for a specific client/product/audience."""

    # Load all available prompts
    all_prompts = list_prompts(
        product_type=product_type or product.category or None,
        platform=platform,
    )

    if not all_prompts:
        # No filters matched — load everything
        all_prompts = list_prompts()

    # Build a summary of available prompts for Claude
    prompt_summaries = []
    for p in all_prompts:
        prompt_summaries.append(
            f"- ID: {p.id} | Name: {p.name} | Category: {p.category} | "
            f"Tags: {', '.join(p.tags[:5])} | Audience: {', '.join(p.audience_fit)} | "
            f"Description: {p.description[:100]}"
        )

    prompts_list = "\n".join(prompt_summaries)
    product_context = _build_product_context(brand, product, avatar)

    result = claude_complete(
        prompt=(
            f"From this library of {len(all_prompts)} ad creative templates, "
            f"recommend the top {count} for the following product and brand.\n\n"
            f"AVAILABLE TEMPLATES:\n{prompts_list}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {platform}\n\n"
            f"Return your recommendations as YAML:\n"
            f"recommendations:\n"
            f"  - id: \"prompt-id\"\n"
            f"    rank: 1\n"
            f"    reasoning: \"Why this template fits this product/brand\"\n"
            f"    suggested_modifications: \"Any changes to make it better for this brand\"\n"
        ),
        system=RECOMMENDER_SYSTEM,
        max_tokens=2048,
    )

    # Parse YAML response
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    try:
        parsed = yaml.safe_load(result)
        return parsed.get("recommendations", [])
    except Exception:
        return [{"id": "error", "reasoning": result}]


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _build_product_context(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
) -> str:
    """Build a context string for Claude to use when writing generation prompts.

    Trimmed to VISUAL-ACTIONABLE fields only. Non-visual fields (mission text,
    income brackets, internal positioning prose) are excluded — they bloat the
    prompt and dilute Claude's attention from the visual decisions that matter.
    """
    # Product characteristics (from image analysis)
    product_details = ""
    if product.product_characteristics:
        product_details = characteristics_to_prompt_fragment(product.product_characteristics)

    parts = [
        f"BRAND: {brand.name}",
        f"BRAND TONE (for type treatment + composition mood): {brand.tone}",
        f"BRAND COLORS: primary={brand.colors.primary}, secondary={brand.colors.secondary}, "
        f"background={brand.colors.background}, accent={brand.colors.accent or 'none'}",
        f"",
        f"PRODUCT: {product.name}",
        f"PRODUCT DESCRIPTION (for product styling, not for copy verbatim): {product.description[:200]}",
        f"KEY BENEFITS: {', '.join(product.benefits[:3])}",
    ]

    if product_details:
        parts.append(
            f"\nPRODUCT VISUAL DETAILS (from real product image analysis):\n{product_details}"
        )

    if avatar:
        # Only the visually-actionable persona bits — demographic for model
        # appearance, and pain points (used by the persona-embodiment rule).
        parts.append("")
        parts.append(f"TARGET PERSONA (for model appearance + body language): {avatar.demographic}")
        if avatar.pain_points:
            top_pains = [p.pain for p in avatar.pain_points[:2]]
            parts.append(f"PERSONA TOP PAINS (use to drive visual symptom cues): {', '.join(top_pains)}")
        if brand.audience.demographics_for_ugc:
            parts.append(f"UGC PERSON DESCRIPTION: {brand.audience.demographics_for_ugc}")

    if brand.guidelines_notes:
        parts.append(f"\nBRAND GUIDELINES (visual + voice rules):\n{brand.guidelines_notes.strip()}")

    if brand.prohibited_terms:
        parts.append(f"PROHIBITED TERMS (never appear in on-image text): {', '.join(brand.prohibited_terms)}")

    return "\n".join(parts)


# ─── Mode 4: "Turn this brief into a prompt" ─────────────────────────────────


def prompt_from_brief(
    brief: CreativeBrief,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    aspect_ratio: str | None = None,
    swipe_block: str = "",
    library_examples: str = "",
    creative_direction: str = "",
) -> str:
    """Take a CreativeBrief and write a Nano Banana 2 prompt for a STATIC ad
    image. Uses the brief's creative_mechanic and visual_format as the
    structural backbone, with hook/angle/pain/benefits as the content.

    Optional context:
      * `swipe_block` — labeled callout describing the STYLE REFERENCE images
        that will be passed alongside the product image. Generated by
        `generators.swipe_matcher.match_for_brief().to_prompt_block()`.
      * `library_examples` — text block listing 1-2 matching Alex Cooper /
        Nanobana library templates as compositional references.
      * `creative_direction` — a user-supplied directive describing the
        specific creative style for this image (e.g. "two callouts in brand
        primary + accent color, text bubble at top"). Injected as a HARD
        CONSTRAINT near the top of the prompt-writer's user prompt —
        overrides generic library patterns when in conflict.
    """

    if not aspect_ratio:
        aspect_ratio = infer_aspect_ratio(brief)

    product_context = _build_product_context(brand, product, avatar)
    brief_context = _build_brief_context(brief)

    # Condense brief into ad-ready copy — the only text NB2 should render
    # literally. Passes `avatar` so the condenser writes in the customer's
    # voice rather than the brief's brand voice (when an avatar is
    # available; otherwise falls back to brief-only condensation).
    condensed = condense_brief_for_ad(brief, brand, avatar=avatar)
    condensed_block = (
        "AD-READY ON-IMAGE COPY (use these as the literal rendered text — "
        "do NOT render the brief's long hook verbatim):\n"
        f"  HERO (large, primary): \"{condensed['hero']}\"\n"
        f"  SUPPORTING (small, optional): \"{condensed['supporting'] or '(omit)'}\"\n"
        f"  CTA (tiny, corner): \"{condensed['cta']}\""
    )

    # Sections appended only when provided — keeps token usage tight when
    # the caller hasn't matched any reference assets.
    extra_sections = ""
    if swipe_block:
        extra_sections += f"\n\n{swipe_block}"
    if library_examples:
        extra_sections += (
            f"\n\nCOMPOSITIONAL TEMPLATE REFERENCES (use as structural guidance, "
            f"replacing the [PLACEHOLDERS] with brief content):\n{library_examples}"
        )

    # User-supplied creative direction is the highest-priority constraint.
    # Goes at the very top of the user prompt so the Claude rewriter sees
    # it before any of the brief / product / library context.
    directive_block = ""
    if creative_direction and creative_direction.strip():
        directive_block = (
            "USER CREATIVE DIRECTION — HIGHEST PRIORITY (overrides any conflicting "
            "pattern from skills, brief, or library):\n"
            "Honor this directive exactly. If the brief or skill suggests something "
            "that contradicts it, follow the directive.\n\n"
            f"  {creative_direction.strip()}\n\n"
        )

    prompt = claude_complete(
        prompt=(
            f"{directive_block}"
            f"Write a Nano Banana 2 prompt for the following creative brief. "
            f"This is for a STATIC ad image — even if the brief's visual_format "
            f"mentions video, generate a single still frame that captures the "
            f"creative concept.\n\n"
            f"The CREATIVE MECHANIC and VISUAL FORMAT are the structural backbone. "
            f"USE THE AD-READY ON-IMAGE COPY (hero/supporting/cta below) — do NOT "
            f"render the brief's long hook verbatim. The brief is strategic context "
            f"only.\n"
            f"Apply the PERSONA EMBODIMENT rule so the model in the image visually "
            f"reflects the hook's pain. Apply the STYLING rule so font names never "
            f"appear in the prompt instructions. Apply the HERO-TEXT, HUMAN REALISM, "
            f"and NEGATIVE SPACE rules.\n\n"
            f"{condensed_block}\n\n"
            f"CREATIVE BRIEF (strategic context — drives mechanic, persona, mood):\n"
            f"{brief_context}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {brief.target_platform}\n"
            f"ASPECT RATIO: {aspect_ratio}"
            f"{extra_sections}\n\n"
            f"Write the prompt now. Start with: 'Image 1 is the actual product — "
            f"replicate it exactly. Any additional images are style/composition "
            f"references — match their layout pattern but NOT their products.'"
        ),
        system=PROMPT_WRITER_SYSTEM,
    )

    return prompt.strip()


CONDENSER_SYSTEM = """You are an ad copy editor distilling a creative brief
into AD-READY on-image copy. The brief contains long-form strategic copy
written in BRAND voice — marketing jargon, clinical phrasing, claim
language. Your job is to compress it into copy that actually fits a
static ad AND reads in the ICP's authentic CUSTOMER voice, not the
brand's marketing voice.

CUSTOMER VOICE — what this means:
Brand voice is the marketer talking ("Viability failure",
"Colonization lottery", "1 trillion stable bioactives delivered
directly"). Customer voice is what the customer would actually say,
think, or notice ("Same bloat", "Still feels off", "Actually works",
"Bloat completely gone"). Customer voice is SHORT, PLAIN, OBSERVATIONAL,
and PERSONAL. Brand voice is LONG, TECHNICAL, CLAIM-RICH, and IMPERSONAL.

When an ICP VOICE PACK appears in the user message (language patterns
+ verbatim customer_language quotes), THAT is the register your output
must match. Do not paraphrase those quotes — lean on their actual
wording, sentence shape, and vocabulary. The customer should recognize
your output as their own way of talking.

Rules:
- HERO phrase: 3-8 words. The single line that commands the frame.
  Sharp, native, written like the CUSTOMER would think it — not
  strategist-speak. If the brief says "Postbiotics: the active
  compound probiotics were always trying to deliver", the hero should
  feel more like "Probiotics didn't work for me" — pulled from the
  customer's own voice, not the brand's framing.
- SUPPORTING phrase: 5-10 words. Optional. Adds ONE clarifying beat,
  also in customer voice.
- CTA: 2-4 words. Action-oriented. Real-people language ('See how it
  works', 'Read the science', 'Try Gut Balance'). Brand wording is
  acceptable here because CTAs are explicitly the brand asking.
- Honor PROHIBITED TERMS from the brand context.
- DO NOT name competitors.
- Use the SAME PSYCHOLOGICAL LEVER as the original hook. If the
  original hook is a question, the hero is also a question. If it's
  stat-driven, lead with the stat.

Output VALID JSON only — no prose, no markdown fences. Schema:

{
  "hero": "...",
  "supporting": "...",
  "cta": "..."
}"""


def condense_brief_for_ad(
    brief: CreativeBrief,
    brand: Brand,
    *,
    word_budget: int | None = None,
    avatar: CustomerAvatar | None = None,
) -> dict[str, str]:
    """Distill a brief's long-form copy into ad-ready on-image text.

    Returns {hero, supporting, cta}. Hero is mandatory, supporting may be
    empty, cta is mandatory. Designed to be called once per generation and
    passed into the NB2 prompt as the literal text NB2 should render.

    When `word_budget` is provided (typically the word count of the reference
    ad's on-image text), the condenser is told to keep total output close to
    that budget — so the new ad matches the reference's text density rather
    than blowing past it.

    When `avatar` is provided, the avatar's language_patterns +
    customer_language verbatim quotes are injected as the "ICP VOICE PACK"
    reference register. The condenser is then instructed to write the
    HERO and SUPPORTING in CUSTOMER voice rather than BRAND voice — which
    means leaning on the avatar's actual quotes ("Still feels off",
    "Bloat completely gone") rather than the brief's clinical jargon
    ("Viability failure", "Improved gut regularity"). Without an avatar,
    the condenser falls back to inferring voice from brief context only.

    Costs ~$0.005-0.01 per call (small prompt, small output).
    """
    import json as _json

    long_hook = (brief.hook or "").strip()
    original_cta = (brief.cta or "Shop Now").strip()
    pain = (brief.pain_point or "").strip()
    angle = (brief.angle or "").strip()
    callouts = ", ".join((brief.benefit_callouts or [])[:3])

    brand_ctx = (
        f"BRAND VOICE: {brand.tone or 'n/a'}\n"
        f"PROHIBITED TERMS (NEVER use these): {', '.join(brand.prohibited_terms or [])}\n"
    )

    # ICP voice pack — when an avatar is provided, this becomes the
    # register reference for the condenser. The voice pack contains the
    # persona's language_patterns + verbatim customer quotes pulled from
    # pain_points and desires. Without it, the condenser falls back to
    # inferring voice from the brief alone (lower quality).
    voice_block = ""
    if avatar is not None:
        try:
            from strategy.voice import format_voice_pack
            voice_pack = format_voice_pack(avatar)
            if voice_pack:
                voice_block = (
                    f"{voice_pack}\n"
                    "CRITICAL: the HERO and SUPPORTING below must be written in "
                    "the customer's voice (above), NOT the brand's voice. The "
                    "brief's hook + benefit_callouts are written in BRAND voice "
                    "(marketing jargon, clinical phrasing). Translate that intent "
                    "into how the CUSTOMER would actually say it — short, plain, "
                    "observational. Lean on the customer's verbatim quotes above "
                    "as your wording reference.\n\n"
                )
        except Exception:
            # Soft-fail — if the voice pack helper errors, fall back to
            # brief-only context. We never want the condenser to hard-fail
            # because of a voice-pack issue.
            voice_block = ""

    # Word-budget guidance — only included when we have a reference's word
    # count to match. The condenser uses this to keep total output near the
    # reference's text density.
    budget_line = ""
    if word_budget is not None and word_budget > 0:
        budget_line = (
            f"\nWORD BUDGET — IMPORTANT: target a total of approximately "
            f"{word_budget} words across hero + supporting + cta combined "
            f"(within +/-20%). The reference ad this brief is being styled "
            f"against has roughly {word_budget} words on-image — match that "
            f"text density. If the budget is small (<10 words), drop "
            f"`supporting` entirely; if larger, expand `supporting` to use "
            f"the budget."
        )

    prompt = (
        f"{voice_block}"
        f"Distill this brief into ad-ready on-image copy.\n\n"
        f"ORIGINAL HOOK (compress this — translate from BRAND voice to "
        f"CUSTOMER voice): {long_hook}\n"
        f"ORIGINAL CTA (shorten this): {original_cta}\n"
        f"PAIN ADDRESSED (context only — do not render): {pain}\n"
        f"ANGLE (context only — do not render): {angle}\n"
        f"BENEFIT CALLOUTS (brand-voice context — translate to customer voice "
        f"if used): {callouts}\n\n"
        f"{brand_ctx}"
        f"{budget_line}\n\n"
        f"Output JSON only: {{'hero': '...', 'supporting': '...', 'cta': '...'}}"
    )

    try:
        response = claude_complete(prompt, system=CONDENSER_SYSTEM, max_tokens=300)
        text = response.strip()
        if text.startswith("```"):
            nl = text.find("\n")
            if nl != -1:
                text = text[nl + 1:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0].rstrip()
        data = _json.loads(text)
    except Exception:
        # Graceful fallback — use truncated originals so the pipeline never
        # blocks on a condensation failure.
        return {
            "hero": long_hook[:60] + ("..." if len(long_hook) > 60 else ""),
            "supporting": "",
            "cta": original_cta[:24],
        }

    return {
        "hero": str(data.get("hero", "")).strip()[:80] or long_hook[:60],
        "supporting": str(data.get("supporting", "")).strip()[:80],
        "cta": str(data.get("cta", "")).strip()[:24] or original_cta[:24],
    }


def _reference_word_budget(client_slug: str, reference_image_path: Path) -> int | None:
    """Look up the word count of the reference ad's on-image text.

    Uses the `hook_visible` field from the corresponding analysis YAML (written
    by `adc analyze-references`). Returns None when no analysis is available.
    """
    if not client_slug or not reference_image_path:
        return None
    category = reference_image_path.parent.name
    stem = reference_image_path.stem[:60]
    candidates = [
        Path("clients") / client_slug / "reference_ads" / "analyses" / category / f"{stem}.yaml",
        Path("clients") / client_slug / "reference_ads" / "analyses" / f"{stem}.yaml",
    ]
    for analysis_path in candidates:
        if not analysis_path.exists():
            continue
        try:
            data = yaml.safe_load(analysis_path.read_text(encoding="utf-8")) or {}
            a = data.get("analysis") or {}
            visible = (a.get("hook_visible") or "").strip()
            if not visible or visible == "[no visible text]":
                return None
            # Count alphabetic-ish tokens; cheap and works for word density
            words = [w for w in visible.split() if any(c.isalpha() for c in w)]
            n = len(words)
            return n if n > 0 else None
        except Exception:
            continue
    return None


def prompt_from_brief_and_template(
    brief: CreativeBrief,
    template: LibraryPrompt,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    aspect_ratio: str | None = None,
    reference_image_path: Path | None = None,
    client_slug: str | None = None,
    creative_direction: str = "",
) -> str:
    """Single-reference, single-template prompt generation.

    Unlike `prompt_from_brief` (which averages across multiple references
    and templates), this mode is ART-DIRECTED: one specific extracted
    template provides the compositional backbone, one specific reference
    image will be passed to NB2, and the brief content fills the template's
    [PLACEHOLDERS]. No swipe library, no Nanobana, no Cooper, no averaging.

    The reference image is uploaded separately by the caller and passed to
    NB2 as the second image input (position 1; position 0 is always the
    product). This function only writes the text prompt.
    """
    if not aspect_ratio:
        aspect_ratio = infer_aspect_ratio(brief)

    product_context = _build_product_context(brand, product, avatar)
    brief_context = _build_brief_context(brief)

    # Condense the brief into ad-ready hero / supporting / cta copy. Free
    # condensation (no per-reference word budget) — letting the condenser
    # pick the sharpest phrasing produced stronger heroes in testing than
    # constraining it to match the reference's density. Passes `avatar`
    # so the condenser writes in the customer's voice rather than the
    # brief's brand voice.
    condensed = condense_brief_for_ad(brief, brand, avatar=avatar)

    condensed_block = (
        "AD-READY ON-IMAGE COPY (use these as the actual rendered text — "
        "do NOT render the brief's long hook verbatim):\n"
        f"  HERO (large, primary): \"{condensed['hero']}\"\n"
        f"  SUPPORTING (small, optional): \"{condensed['supporting'] or '(omit)'}\"\n"
        f"  CTA (tiny, corner): \"{condensed['cta']}\""
    )

    template_block = (
        f"--- BASE TEMPLATE (compositional backbone, lift placeholders from brief) ---\n"
        f"Template id: {template.id}\n"
        f"Template name: {template.name}\n"
        f"Template category: {template.category}\n"
        f"Tags: {', '.join(template.tags)}\n\n"
        f"{template.template_prompt}\n"
        f"--- END TEMPLATE ---"
    )

    directive_block = ""
    if creative_direction and creative_direction.strip():
        directive_block = (
            "USER CREATIVE DIRECTION — HIGHEST PRIORITY (overrides any conflicting "
            "pattern from template, brief, or skills):\n"
            "Honor this directive exactly. If the template or brief suggests "
            "something that contradicts it, follow the directive.\n\n"
            f"  {creative_direction.strip()}\n\n"
        )

    prompt = claude_complete(
        prompt=(
            f"{directive_block}"
            f"Write a Nano Banana 2 prompt that produces ONE static ad based on "
            f"a single hand-picked reference template. This is ART-DIRECTED — "
            f"there is no aggregation across multiple refs.\n\n"
            f"IMAGE INPUTS NB2 will receive:\n"
            f"  - Image 1: the actual product (REPLICATE EXACTLY — colors, label, shape)\n"
            f"  - Image 2: the reference ad whose compositional pattern was extracted "
            f"into the template below. Match its LAYOUT, type treatment, photographic "
            f"style, mood, color treatment — but DO NOT copy its product. Substitute "
            f"our product (image 1) in its place.\n\n"
            f"Your job: write a NB2 prompt that takes the template below and uses "
            f"the AD-READY ON-IMAGE COPY for any text fields ([HEADLINE], [SUBHEAD], "
            f"[CTA], etc.). The original brief is strategic context only — do not "
            f"render the brief's long hook as on-image text.\n\n"
            f"APPLY the HERO-TEXT RULE: render the HERO line large, render SUPPORTING "
            f"small only if present, render CTA as a tiny corner element. That is "
            f"the entire on-image copy budget.\n\n"
            f"APPLY the HUMAN REALISM RULE if a person is in the composition.\n\n"
            f"APPLY the NEGATIVE SPACE RULE — at least 40% unbroken visual rest.\n\n"
            f"{condensed_block}\n\n"
            f"{template_block}\n\n"
            f"CREATIVE BRIEF (strategic input — drives mechanic, persona, mood; NOT "
            f"to be rendered verbatim):\n"
            f"{brief_context}\n\n"
            f"PRODUCT & BRAND CONTEXT:\n{product_context}\n\n"
            f"TARGET PLATFORM: {brief.target_platform}\n"
            f"ASPECT RATIO: {aspect_ratio}\n\n"
            f"Write the NB2 prompt now. Start with: 'Image 1 is the actual product — "
            f"replicate it exactly. Image 2 is a reference ad — match its layout, "
            f"type treatment, photographic style, and mood, but substitute our "
            f"product for theirs.'"
        ),
        system=PROMPT_WRITER_SYSTEM,
    )
    return prompt.strip()


def _load_client_templates(client_slug: str) -> list[LibraryPrompt]:
    """Load per-client Cooper-style templates extracted from the client's
    reference ads. Returns empty list if none exist."""
    if not client_slug:
        return []
    templates_root = Path("clients") / client_slug / "templates"
    if not templates_root.exists():
        return []
    out: list[LibraryPrompt] = []
    for yaml_file in sorted(templates_root.rglob("*.yaml")):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            if not data or "template_prompt" not in data:
                continue
            # Skip extracted-but-empty templates (LLM response was malformed
            # and we wrote stubs). 50-char floor catches the empty body cases.
            template_body = (data.get("template_prompt") or "").strip()
            if len(template_body) < 50:
                continue
            # Be tolerant of extra fields written by the extractor (e.g. source_ad)
            allowed_fields = LibraryPrompt.model_fields.keys()
            data = {k: v for k, v in data.items() if k in allowed_fields}
            out.append(LibraryPrompt(**data))
        except Exception:
            continue
    return out


def find_library_examples_for_brief(
    brief: CreativeBrief,
    max_examples: int = 2,
    platform: str | None = None,
    client_slug: str | None = None,
    include_cooper: bool = False,
) -> str:
    """Return a text block of matching template prompts.

    Source priority (highest first):
      1. Per-client templates at `clients/<slug>/templates/` (extracted from
         the client's hand-picked reference ads via `adc extract-templates`)
      2. Nanobana library templates (photo-realistic ad recipes)
      3. Cooper library templates — ONLY when `include_cooper=True`. Default
         is False because we've moved to per-client templates as the primary
         compositional signal.

    Filters by audience_fit overlap with brief.awareness_level and category
    match with the brief's visual format (matched via swipe_matcher).
    """
    plat = platform or brief.target_platform
    candidates: list[LibraryPrompt] = []

    # 1. Per-client templates first (highest priority)
    if client_slug:
        candidates.extend(_load_client_templates(client_slug))

    # 2. Nanobana templates
    nanobana_candidates = list_prompts(platform=plat, source_dir="nanobana")
    candidates.extend(nanobana_candidates)

    # 3. Cooper templates only when explicitly requested
    if include_cooper:
        cooper_candidates = list_prompts(platform=plat, source_dir="cooper")
        candidates.extend(cooper_candidates)

    if not candidates:
        return ""

    awareness = brief.awareness_level.value if brief.awareness_level else ""

    # Match by category (us-vs-them, features-and-benefits, etc.) — derived
    # from the brief's visual_format via the swipe matcher.
    from generators.swipe_matcher import pick_standard_folder
    brief_category = pick_standard_folder(brief.visual_format or "")

    # Aliases — accept user folder naming (no "and"s) alongside canonical
    cat_aliases = {
        "features-and-benefits": {"features-and-benefits", "features-benefits", "reasons-why"},
        "facts-and-stats": {"facts-and-stats", "facts-stats"},
        "media-and-press": {"media-and-press", "media-press"},
        "promotion-and-discount": {"promotion-and-discount", "promotion-discount"},
    }
    acceptable_categories = cat_aliases.get(brief_category, {brief_category})

    # Rank: (1) category match + audience match, (2) category match, (3) audience match, (4) anything
    cat_aud_matches = [
        p for p in candidates
        if p.category in acceptable_categories and awareness in p.audience_fit
    ]
    cat_matches = [p for p in candidates if p.category in acceptable_categories]
    aud_matches = [p for p in candidates if awareness in p.audience_fit]

    if cat_aud_matches:
        pool = cat_aud_matches
    elif cat_matches:
        pool = cat_matches
    elif aud_matches:
        pool = aud_matches
    else:
        pool = candidates

    selected = pool[:max_examples]
    if not selected:
        return ""

    blocks = []
    for p in selected:
        tpl = p.template_prompt
        if len(tpl) > 600:
            tpl = tpl[:600].rsplit(" ", 1)[0] + "..."
        blocks.append(
            f"--- Template: {p.id} ({p.category}) ---\n{tpl}"
        )
    return "\n\n".join(blocks)


def infer_aspect_ratio(brief: CreativeBrief) -> str:
    """Pick an aspect ratio from the brief's visual_format and target_platform."""
    fmt = brief.visual_format.lower()
    if any(kw in fmt for kw in ["vertical", "story", "reel", "tiktok", "9:16"]):
        return "9:16"
    if "4:5" in fmt or "portrait" in fmt:
        return "4:5"
    if brief.target_platform.lower() == "tiktok":
        return "9:16"
    return "1:1"


def _build_brief_context(brief: CreativeBrief) -> str:
    """Render the brief's strategic fields as a context block for the prompt writer.

    When the brief carries a NEAR-CLONE / TEXT INVENTORY directive in
    `visual_direction`, that block is hoisted to the top of the context and
    flagged as highest-priority, AND fields whose contents would otherwise
    tempt the prompt-writer into adding extra on-image text (benefit_callouts,
    body_copy) are suppressed. They remain in the brief for downstream uses;
    they're just hidden from the prompt-writer LLM, which has a measurable
    bias toward "render every string I see as image text."
    """
    vd = (brief.visual_direction or "").strip()
    vd_upper = vd.upper()
    is_near_clone = (
        "NEAR-CLONE" in vd_upper
        or "TEXT INVENTORY" in vd_upper
    )

    parts: list[str] = []

    # NEAR-CLONE: hoist visual_direction to the top with a strong header so
    # the prompt-writer can't miss it. The remaining strategic fields follow
    # but with the noisy-for-rendering ones (benefit_callouts, body_copy)
    # suppressed.
    if is_near_clone and vd:
        parts.append(
            "VISUAL DIRECTION (NEAR-CLONE — VERBATIM ADHERENCE REQUIRED, "
            "see NEAR-CLONE / TEXT INVENTORY RULE in system prompt):\n"
            f"{vd}"
        )

    parts.extend([
        f"AWARENESS LEVEL: {brief.awareness_level.value}",
        f"FRAMEWORK: {brief.framework.value}",
        f"ANGLE: {brief.angle}",
    ])
    # The long-form HOOK is suppressed for NEAR-CLONE so the prompt-writer
    # cannot inadvertently render it verbatim — the condensed AD-READY
    # copy block (HERO/SUPPORTING/CTA) is the source of truth for what
    # NB2 should actually put on the image. For non-clone briefs we keep
    # HOOK in the context because the writer has more freedom to
    # interpret it.
    if not is_near_clone:
        parts.append(f"HOOK: {brief.hook}")
    if brief.hook_type:
        parts.append(f"HOOK TYPE: {brief.hook_type}")
    if brief.hook_tactic:
        parts.append(f"HOOK TACTIC: {brief.hook_tactic}")
    if brief.persona:
        parts.append(f"PERSONA: {brief.persona}")
    if brief.creative_mechanic:
        parts.append(f"CREATIVE MECHANIC: {brief.creative_mechanic}")
    if brief.visual_format:
        parts.append(f"VISUAL FORMAT: {brief.visual_format}")
    if brief.pain_point:
        parts.append(f"PAIN POINT: {brief.pain_point}")

    # Benefit callouts and body copy: included normally for free-form ads, but
    # SUPPRESSED for NEAR-CLONE so the prompt-writer doesn't render them as
    # additional text overlays. The brief itself still carries them.
    if brief.benefit_callouts and not is_near_clone:
        parts.append(f"BENEFIT CALLOUTS: {', '.join(brief.benefit_callouts)}")
    if brief.cta:
        parts.append(f"CTA: {brief.cta}")
    if brief.body_copy and not is_near_clone:
        parts.append(f"BODY COPY: {brief.body_copy}")

    # Non-clone case: append visual_direction inline as before.
    if vd and not is_near_clone:
        parts.append(f"VISUAL DIRECTION: {vd}")

    if brief.tone_override:
        parts.append(f"TONE OVERRIDE: {brief.tone_override}")
    return "\n".join(parts)
