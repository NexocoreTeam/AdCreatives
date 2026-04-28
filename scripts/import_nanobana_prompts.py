"""Import curated nano banana prompts from GitHub repos into the library.

Sources:
- https://github.com/ZeroLu/awesome-nanobanana-pro
- https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts
- https://github.com/0aicoder0/Ultimate-Nano-Banana-Pro-Collection

Run: python scripts/import_nanobana_prompts.py
"""

from pathlib import Path
import yaml

OUTPUT_DIR = Path("prompts/library/nanobana")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATES = [
    {
        "id": "nb-product-photography-clean",
        "name": "Clean E-Commerce Product Shot",
        "source": "ZeroLu/awesome-nanobanana-pro",
        "category": "product-hero",
        "description": "Professional e-commerce product shot on pure white background. Auto-removes hands, clutter, and imperfections.",
        "product_types": ["any"],
        "audience_fit": ["product_aware", "most_aware"],
        "funnel_stage": "conversion",
        "aspect_ratios": ["1:1", "4:5"],
        "tags": ["ecommerce", "clean", "white-background", "product-listing", "studio"],
        "template_prompt": "Use the attached images as brand reference. Identify the main product and recreate it as a premium e-commerce product shot. Subject Isolation: Cleanly extract the product, completely removing any fingers, hands, or clutter. Background: Place the product on a pure white studio background (RGB 255, 255, 255) with a subtle, natural contact shadow at the base to ground it. Lighting: Use soft, commercial studio lighting to highlight the product's texture and material. Ensure even illumination with no harsh glare. Retouching: Automatically fix any lens distortion, improve sharpness, and color-correct to make the product look brand new and professional. 1:1 aspect ratio.",
    },
    {
        "id": "nb-virtual-model-tryon",
        "name": "Virtual Model Try-On",
        "source": "ZeroLu/awesome-nanobanana-pro",
        "category": "lifestyle",
        "description": "Put your garment on a model. Hyper-realistic full-body fashion photo with natural draping and folds.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "9:16"],
        "tags": ["model", "try-on", "fashion", "lifestyle", "apparel", "virtual-fitting"],
        "template_prompt": "Use the attached images as brand reference — Image 1 is the garment, use it to match exact colors, print, and design. Create: a hyper-realistic full-body fashion photo where [PERSON DESCRIPTION matching target demographic] is wearing the garment. Crucial Fit Details: The garment must drape naturally on the model's body, conforming to their posture and creating realistic folds and wrinkles. High-Fidelity Preservation: Preserve the original fabric texture, color, and any logos/graphics from the product image with extreme accuracy. Seamless Integration: Blend the garment into the scene by perfectly matching the ambient lighting, color temperature, and shadow direction. Photography Style: [STYLE like clean e-commerce lookbook / casual street style / editorial fashion]. Shot on a Canon EOS R5 with a 50mm f/1.8 lens for a natural, professional look. [SETTING like studio with neutral background / urban street / cozy home]. 4:5 aspect ratio.",
    },
    {
        "id": "nb-beverage-hero-splash",
        "name": "Beverage Hero with Splash",
        "source": "0aicoder0/Ultimate-Nano-Banana-Pro-Collection",
        "category": "product-hero",
        "description": "Ultra-realistic luxury beverage shot with condensation, splash effects, and dramatic lighting.",
        "product_types": ["beverage", "food", "supplement"],
        "audience_fit": ["product_aware", "most_aware"],
        "funnel_stage": "conversion",
        "aspect_ratios": ["2:3", "4:5"],
        "tags": ["beverage", "splash", "premium", "luxury", "hero-shot", "condensation"],
        "template_prompt": "Use the attached images as brand reference. Match the exact product design, label, and colors precisely. Create: Ultra-realistic luxury product photography of [YOUR PRODUCT]. The container appears crisp and glossy with realistic highlights, subtle reflections, and visible cold texture with condensation water droplets. Dynamic liquid splash frozen in mid-air, crown-shaped splash at the base. Shot in a minimalist commercial beverage advertising style against a [BACKGROUND COLOR] gradient background. Camera: Canon EOS R5 with 100mm macro f/2.8 lens. Lighting: Key light 45 degrees left, rim light behind, white bounce fill, subtle accent gel. Film emulation: Kodak Portra 400. 8K resolution, photorealistic, commercial quality. 2:3 aspect ratio.",
    },
    {
        "id": "nb-commercial-poster",
        "name": "Commercial Promotional Poster",
        "source": "ZeroLu/awesome-nanobanana-pro",
        "category": "poster",
        "description": "Professional promotional poster with text integration areas for post-production overlay.",
        "product_types": ["any"],
        "audience_fit": ["problem_aware", "solution_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["4:5", "9:16"],
        "tags": ["poster", "promotional", "text-overlay", "editorial", "commercial"],
        "template_prompt": "Use the attached images as brand reference. Design a professional promotional poster for [BRAND NAME]. Composition: A cinematic close-up of [PRODUCT SCENE DESCRIPTION] in a [MOOD like cozy / energetic / premium] atmosphere. Text Integration: 1. Main Title: '[HEADLINE]' written in elegant, [BRAND COLOR] [FONT STYLE like serif / sans-serif] typography at the top. 2. Offer: '[OFFER TEXT]' clearly displayed in a modern badge or sticker style on the side. 3. Footer: '[CTA TEXT]' in small, clean text at the bottom. Quality: Ensure all text is perfectly spelled, centered, and integrated into the image's depth of field. 4:5 aspect ratio.",
    },
    {
        "id": "nb-japanese-commercial",
        "name": "Japanese Commercial Style",
        "source": "YouMind-OpenLab/awesome-nano-banana-pro-prompts",
        "category": "lifestyle",
        "description": "High-resolution Japanese commercial style. Bold geometric color blocks, bright studio lighting, playful and energetic.",
        "product_types": ["apparel", "beauty", "food", "beverage"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["1:1", "4:5"],
        "tags": ["japanese", "commercial", "colorful", "energetic", "bold", "lifestyle"],
        "template_prompt": "Use the attached images as brand reference. Create: High-resolution Japanese commercial advertisement style photo, [PERSON DESCRIPTION matching target demographic] posing against a clean white background with bold geometric color blocks ([BRAND COLORS] arranged diagonally). [PERSON] is [ACTION like holding / wearing / using] [YOUR PRODUCT] with [EXPRESSION like a genuine smile / excited look / casual confidence]. Bright studio lighting, soft shadows, vibrant colors, sharp focus, clean commercial composition, modern Japanese advertising aesthetic, playful and energetic mood, ultra-detailed, crisp skin tones. No text, no logos, no typography anywhere in the image. 1:1 aspect ratio.",
    },
    {
        "id": "nb-product-grid-3x3",
        "name": "Product Grid 3x3 Campaign Set",
        "source": "0aicoder0/Ultimate-Nano-Banana-Pro-Collection",
        "category": "campaign-set",
        "description": "3x3 grid showing product from 9 angles/contexts. Great for carousel ads and campaign visual sets.",
        "product_types": ["any"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["1:1"],
        "tags": ["grid", "3x3", "campaign", "carousel", "multi-shot", "product-focused"],
        "template_prompt": "Use the attached images as brand reference. Match the exact product design precisely. Create: A 3x3 image grid showcasing [YOUR PRODUCT] across 9 distinct panels. Each panel features the exact same product with consistent branding. Global directives: Ultra-high fidelity product rendering, consistent color accuracy across all panels, commercial photography quality. Grid cells: 1. Hero Still Life — product centered, dramatic studio lighting 2. Extreme Macro Detail — close-up of product texture and craftsmanship 3. Dynamic Interaction — product in use, motion energy 4. Minimal Sculptural — product as art object, geometric shadows 5. Lifestyle Context — product in natural environment 6. Color Story — product with color-matched props 7. Scale Comparison — product next to everyday objects 8. Benefit Highlight — visual metaphor for key benefit 9. Social Proof — product with warm trust elements. 1:1 aspect ratio.",
    },
    {
        "id": "nb-food-cinematic",
        "name": "Cinematic Food Ad",
        "source": "0aicoder0/Ultimate-Nano-Banana-Pro-Collection",
        "category": "product-hero",
        "description": "Hollywood-quality food product photography with cinematic lighting and dynamic elements.",
        "product_types": ["food", "beverage"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["2:3", "4:5"],
        "tags": ["food", "cinematic", "luxury", "dynamic", "appetite-appeal", "premium"],
        "template_prompt": "Use the attached images as brand reference. Match the exact product design, packaging, and label precisely. Create: Cinematic food product photography. [YOUR PRODUCT] as the hero element, shot on ARRI Alexa 65, anamorphic lens, film emulation Kodak Portra 400. Artistic direction: [MOOD like warm and indulgent / fresh and vibrant / dark and luxurious]. Zero-gravity dynamic elements — [INGREDIENT ELEMENTS like scattered pieces, crumbs, drips, splashes] floating in mid-air around the product, creating motion and appetite appeal. Lighting: Dramatic rim light from behind, soft key from 45 degrees, warm fill. Background: [BACKGROUND like dark moody gradient / clean white / rustic wood surface]. Commercial advertising quality, 8K, photorealistic detail. 2:3 aspect ratio.",
    },
    {
        "id": "nb-lifestyle-casual-hold",
        "name": "Casual Product Hold (UGC Style)",
        "source": "YouMind-OpenLab/awesome-nano-banana-pro-prompts",
        "category": "ugc",
        "description": "Casual person holding/using product. iPhone quality, not overly produced. UGC-native for TikTok/Reels.",
        "product_types": ["any"],
        "audience_fit": ["problem_aware", "solution_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["9:16", "4:5"],
        "tags": ["ugc", "casual", "authentic", "lifestyle", "tiktok-native", "hand-held"],
        "template_prompt": "Use the attached images as brand reference. Match the exact product design and packaging precisely. Do NOT use polished ad layouts. This must look like a real person's Instagram Story or TikTok. Create: a casual photo of [PERSON DESCRIPTION matching target demographic]'s hand holding [YOUR PRODUCT] in a natural grip, shot over [SURFACE/SETTING like a kitchen counter / desk / bathroom shelf]. Natural overhead daylight, slightly warm, iPhone quality. Background slightly blurred with [LIFESTYLE PROPS like coffee mug, keys, everyday items] scattered casually. Not centered — slightly off-center framing. Slight natural grain. The person's face is not visible — just their hand and forearm. Product label clearly visible. No text overlay. Should feel completely native and organic. 9:16 aspect ratio.",
    },
    {
        "id": "nb-thumbnail-reaction",
        "name": "Viral Video Thumbnail",
        "source": "ZeroLu/awesome-nanobanana-pro",
        "category": "thumbnail",
        "description": "Video thumbnail with person reacting/pointing at the product. Bold text overlay. YouTube/TikTok native.",
        "product_types": ["any"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["16:9", "1:1"],
        "tags": ["thumbnail", "reaction", "youtube", "tiktok", "scroll-stopper", "pointing"],
        "template_prompt": "Use the attached images as brand reference. Create: a viral video thumbnail. Face Consistency: [PERSON DESCRIPTION] with an expression of [EMOTION like excitement / surprise / amazement]. Action: Pose the person on the left side, pointing their finger towards the right side of the frame. Subject: On the right side, place [YOUR PRODUCT] photographed clearly with studio lighting. Graphics: Add a bold [BRAND COLOR] arrow connecting the person's finger to the product. Text: Overlay massive, pop-style text in the center: '[HOOK TEXT, 3-5 words]'. Use a thick white outline and drop shadow. Background: A blurred, bright [SETTING] background. High saturation and contrast. 16:9 aspect ratio.",
    },
    {
        "id": "nb-bento-grid-infographic",
        "name": "Product Infographic (Bento Grid)",
        "source": "YouMind-OpenLab/awesome-nano-banana-pro-prompts",
        "category": "educational",
        "description": "Multi-card bento grid layout with product hero, benefits, metrics, and usage info. Information-dense but scannable.",
        "product_types": ["supplement", "food", "beauty", "health", "saas"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "1:1"],
        "tags": ["infographic", "bento-grid", "educational", "data-driven", "multi-card", "benefits"],
        "template_prompt": "Use the attached images as brand reference. Match the exact product design precisely. Create: a bento grid product infographic with 6-8 cards arranged in a modern grid layout on [BACKGROUND COLOR] background. Card 1 (large, top): Hero product shot with [HEADLINE]. Card 2: Key stat in large bold text '[STAT like 20g Protein]' with small label below. Card 3: Ingredient/benefit visual with icon and '[BENEFIT]'. Card 4: Star rating '[RATING]' with '[REVIEW COUNT] reviews'. Card 5: Usage instruction '[HOW TO USE]' with simple icon. Card 6: Price/CTA '[PRICE]' with '[CTA like Shop Now]'. Cards have rounded corners, subtle shadows, and [BRAND COLOR] accents. Clean, modern, information-dense but scannable. 4:5 aspect ratio.",
    },
]

for t in TEMPLATES:
    t["platforms"] = ["meta", "tiktok"]
    filename = f"{t['id'].replace('nb-', '')}.yaml"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(t, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"  Created: {path}")

print(f"\nDone! {len(TEMPLATES)} Nano Banana prompts imported to {OUTPUT_DIR}")
