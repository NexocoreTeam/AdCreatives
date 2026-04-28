"""Import 14 selected prompts from YouMind-OpenLab/awesome-nano-banana-pro-prompts.

Source: https://github.com/YouMind-OpenLab/awesome-nano-banana-pro-prompts
Run: python scripts/import_youmind_selected.py
"""

from pathlib import Path
import yaml

OUTPUT_DIR = Path("prompts/library/nanobana")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE = "YouMind-OpenLab/awesome-nano-banana-pro-prompts"

TEMPLATES = [
    {
        "id": "ym-08-mirror-selfie-otaku-room",
        "name": "Mirror Selfie Room Scene",
        "category": "lifestyle",
        "description": "Detailed mirror-selfie in a styled room. Originally otaku/Asian themed — modify background for your brand's aesthetic.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["1:1"],
        "tags": ["mirror-selfie", "room-scene", "lifestyle", "detailed", "fashion"],
        "modifications_needed": "Americanize background (remove Asian/otaku theme). Change room decor to match brand.",
        "template_prompt": """### Scene
Mirror selfie in a [STYLED ROOM DESCRIPTION — e.g. cozy bedroom corner / modern vanity setup / minimalist apartment], [COLOR TONE] color tone.

### Subject
* Gender expression: [GENDER]
* Age: around [AGE]
* Ethnicity: [ETHNICITY matching target demographic]
* Body type: [BODY TYPE], natural body proportions
* Skin tone: [SKIN TONE]
* Hairstyle:
    * Length: [HAIR LENGTH]
    * Style: [HAIR STYLE]
    * Color: [HAIR COLOR]
* Pose:
    * Stance: standing in a slight contrapposto pose
    * Right hand: holding a smartphone in front of face (identity partially hidden)
    * Left arm: naturally hanging down alongside the torso
* Clothing:
    * [YOUR PRODUCT — describe the exact garment from product images]
    * [ADDITIONAL CLOTHING ITEMS]

### Environment
* Description: [ROOM DESCRIPTION] seen through a wall-mounted mirror
* Furnishings:
    * [LIST 5-8 ROOM ELEMENTS that match brand aesthetic]
* Color scheme: [BRAND COLORS applied to room decor]

### Lighting
* Light source: daylight coming from a large window, through sheer curtains
* Light quality: soft, diffused light
* White balance (K): 5200

### Camera
* Mode: smartphone rear camera shooting via mirror (no portrait/bokeh mode)
* Equivalent focal length (mm): 26
* Focus: focus on the torso and clothing in the mirror image
* Depth of field: natural smartphone deep depth of field
* Composition:
    * Aspect ratio: 1:1
    * Crop: from top of head to mid-thigh
    * Angle: slightly high angle from mirror's POV

### Negative prompts
* Beauty filters/over-smoothed skin
* Exaggerated or distorted anatomy
* Logos, brand names, or readable text (unless on product)
* Fake portrait-mode blur, CGI/illustration feel""",
    },
    {
        "id": "ym-02-realistic-mirror-selfie",
        "name": "Realistic Mirror Selfie (Fashion Focus)",
        "category": "ugc",
        "description": "Ultra-realistic smartphone mirror selfie. Focus on clothing/product, NOT model's physical features.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5"],
        "tags": ["mirror-selfie", "ugc", "realistic", "fashion", "iphone"],
        "modifications_needed": "Remove focus on model's physical features. Center attention on the clothing/product.",
        "template_prompt": """Ultra-realistic smartphone mirror selfie, natural daylight, high detail, realistic textures, clean modern room.

Camera: smartphone rear camera via mirror, close mirror reflection, chest level, 24mm-28mm smartphone lens, sharp focus, deep focus, 4K.

Subject: [PERSON DESCRIPTION matching target demographic — age, general appearance, but NOT detailed physical features]. Wearing [YOUR PRODUCT — exact description from product images]. Expression is relaxed and natural, looking at phone screen.

Outfit focus: [DETAILED DESCRIPTION OF YOUR PRODUCT as worn — how it drapes, fits, the exact text/graphics visible].

Environment: bright modern [SETTING — bedroom / living room / hallway], full-length mirror with [FRAME STYLE], [FLOOR TYPE], natural daylight from window.

Rendering notes: extreme realism, natural weight and fabric draping, correct mirror reflection geometry, no distortion, accurate anatomy, consistent lighting, high texture detail on clothing. The clothing/product is the hero — it should be the sharpest, most detailed element in the frame.

4:5 aspect ratio.""",
    },
    {
        "id": "ym-06-urban-plaza-fashion",
        "name": "Urban Plaza Fashion Portrait",
        "category": "lifestyle",
        "description": "Confident person in a modern urban plaza. Cinematic golden hour photography.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "1:1"],
        "tags": ["urban", "fashion", "golden-hour", "cinematic", "lifestyle", "portrait"],
        "modifications_needed": "Change model to match client demographic. Remove suitcase — adjust pose/prop.",
        "template_prompt": """A confident [PERSON DESCRIPTION matching target demographic] in the middle of a [LOCATION — modern American urban plaza / downtown sidewalk / city park]. They have [HAIR DESCRIPTION], wearing [YOUR PRODUCT — exact description], paired with [COMPLEMENTARY CLOTHING AND ACCESSORIES]. Their pose is relaxed yet stylish — [POSE DESCRIPTION — e.g. standing with one hand in pocket, leaning against railing, walking mid-stride]. Expression is [EXPRESSION — cool and contemplative / warm and approachable / confident and direct].

The background features [URBAN BACKGROUND — modern glass buildings / tree-lined street / city skyline], captured from a [ANGLE — low angle / eye level] during golden hour daylight. Professional cinematic photography, sharp details, realistic textures, natural lighting with soft reflections, high resolution, photorealistic, 8k.

4:5 aspect ratio.""",
    },
    {
        "id": "ym-07-candid-mirror-selfie-beauty",
        "name": "Candid Mirror Selfie Beauty Portrait",
        "category": "lifestyle",
        "description": "Close-up beauty portrait mirror selfie. Chic, relaxed look with stylized background.",
        "product_types": ["apparel", "fashion", "beauty", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["9:16"],
        "tags": ["mirror-selfie", "beauty", "close-up", "candid", "portrait", "instagram"],
        "modifications_needed": "Remove graffiti art background. Americanize model. No celebrity lookalikes.",
        "template_prompt": """An ultra-realistic extreme close-up beauty portrait of a stylish [PERSON DESCRIPTION matching target demographic — no celebrity references] taking a mirror selfie, framed from shoulders up. They are wearing [YOUR PRODUCT — visible near collarbone/shoulders], softly draped for a relaxed yet chic look. Their hand is gently holding the garment near the collar, adding a natural candid feel.

Hair: [HAIR DESCRIPTION] framing face with soft texture and movement. A few strands fall delicately across forehead and cheeks.

Facial features: glowing skin with a dewy finish, smooth complexion, highlighted cheekbones, subtle contour, natural blush. Makeup is minimal but refined. Expression is calm, confident, and slightly introspective, with direct eye contact into the mirror.

Realistic soft lighting enhances skin texture and facial depth, while a subtle white outline glow surrounds hair and silhouette, adding a dreamy aesthetic. Background is a [BLURRED BACKGROUND — soft bokeh city lights / warm interior / abstract color gradient] — softly out of focus to keep attention on face and product.

Instagram-style edit, cinematic tones, shallow depth of field, HD quality, portrait orientation. 9:16 aspect ratio.""",
    },
    {
        "id": "ym-10-photorealistic-makeup-portrait",
        "name": "Hyper-Photorealistic Lifestyle Portrait",
        "category": "lifestyle",
        "description": "Hyper-photorealistic casual portrait. Originally Douyin/Asian city — modify for American setting.",
        "product_types": ["apparel", "fashion", "beauty", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "1:1"],
        "tags": ["photorealistic", "portrait", "casual", "lifestyle", "candid"],
        "modifications_needed": "Americanize — remove Asian city/writing from background. Change makeup style to match brand.",
        "template_prompt": """Create image: A hyper-photorealistic shot of [PERSON DESCRIPTION matching target demographic], use the same subject in the attached image for facial features, ultra-realistic face, visible pores, natural dewy skin, [MAKEUP STYLE — natural glam / minimal / bold lip].

Expression / Pose: [POSE — relaxed lounging / standing casually / walking], gaze soft and [DIRECTION — toward camera / slightly away], natural candid energy.

Camera: [CAMERA STYLE — old CCD digital camera with direct flash / modern smartphone / DSLR with shallow DOF], [GRAIN/STYLE NOTES].

Hair: [HAIR DESCRIPTION].

Outfit: [YOUR PRODUCT — exact garment description from product images], [COMPLEMENTARY ITEMS].

Background: [AMERICAN SETTING — inside car on American street / cafe patio / park bench / apartment balcony], [LIGHTING — sunlight casting highlights / warm indoor glow / overcast soft light], [BACKGROUND DETAILS — no foreign-language signage].

Composition: [FRAMING — close-up upper body / full body / waist-up], natural and candid.

Negative prompt: stiff pose, unrealistic body, plastic skin, blur, foreign text or signage.

4:5 aspect ratio.""",
    },
    {
        "id": "ym-12-street-selfie-doodles",
        "name": "Street Selfie with Doodles",
        "category": "lifestyle",
        "description": "Walking selfie with playful hand-drawn doodle annotations. Originally European — modify for American street.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["9:16", "4:5"],
        "tags": ["selfie", "doodles", "street", "annotations", "playful", "instagram"],
        "modifications_needed": "Americanize city setting. Modify doodle labels for each product.",
        "template_prompt": """A stylish [PERSON DESCRIPTION matching target demographic] walking down a [AMERICAN STREET SETTING — charming downtown street / tree-lined sidewalk / urban neighborhood], holding a coffee cup in one hand and taking a selfie with a smartphone in the other, wearing [YOUR PRODUCT — exact description], [COMPLEMENTARY ITEMS — pants, shoes, bag]. Soft natural sunlight, warm tones, shallow depth of field, aesthetic travel vibe, [EXPRESSION — smiling / confident / playful], [HAIR/ACCESSORIES], urban lifestyle photography, candid moment.

With playful white hand-drawn doodles and text around the subject: [DOODLE LABELS — customize for your product, e.g. arrows pointing to shirt with "boy mama vibes", coffee cup with "fuel", bag with "essentials", shoes with "comfy"]. Stars, arrows, and swirls scattered around.

Influencer-style composition, casual luxury vibe, clean aesthetic, high resolution, lifestyle photography.

9:16 aspect ratio.""",
    },
    {
        "id": "ym-22-tropical-beach-fashion",
        "name": "Tropical Beach Sunset Fashion",
        "category": "lifestyle",
        "description": "Fashion editorial at beach sunset. Direct flash for cinematic contrast. Modify outfit for your product.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["2:3", "4:5"],
        "tags": ["beach", "sunset", "fashion", "editorial", "tropical", "golden-hour"],
        "modifications_needed": "Modify what model is wearing to your product.",
        "template_prompt": """A [PERSON DESCRIPTION matching target demographic] sitting on [SETTING — large rocks by the ocean / sandy beach / wooden dock] at sunset, wearing [YOUR PRODUCT — exact garment description from product images]. [HAIR DESCRIPTION], and dewy glowing skin. The sky is a gradient of warm orange and pink tones, with waves crashing gently in the background. Shot with direct flash, creating a contrast between the warm sunset ambiance and glossy highlights on skin. The mood is dreamy, tropical, and fashion editorial with a cinematic beach aesthetic.

Style: tropical fashion editorial, candid flash photography.
Lighting: golden hour sunset mixed with direct flash, warm tones, glossy highlights.
Camera: 50mm lens, shallow depth of field, centered framing.
Quality: high detail, ultra realistic, sharp focus.

2:3 aspect ratio.""",
    },
    {
        "id": "ym-29-streetwear-fashion-collage",
        "name": "Streetwear Fashion Collage",
        "category": "campaign-set",
        "description": "Multi-frame fashion collage (3 panels). Full body + profile + detail shot. Modify clothing for your product.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["1:1", "4:5"],
        "tags": ["collage", "multi-frame", "streetwear", "fashion", "editorial", "detail-shots"],
        "modifications_needed": "Modify what person is wearing to your product.",
        "template_prompt": """Hyper realistic fashion photo collage consisting of three detailed frames. Show a [PERSON DESCRIPTION matching target demographic] in an urban setting against a background of [BACKGROUND — dark gray metal shutters / brick wall / concrete]. Color palette: [BRAND COLORS], with [ACCENT] accents.

Left frame (full body portrait):
Stylish [PERSON] standing in a relaxed pose, looking straight at camera. Wearing [YOUR PRODUCT — exact description from product images], paired with [COMPLEMENTARY ITEMS]. [BRAND ATTITUDE — confident streetwear / cozy casual / premium minimal].

Top right frame (profile shot):
Close-up side profile. Focus on the [PRODUCT DETAIL — sleeve texture, collar, graphic print]. [POSE DETAIL — hand gesture, hood up, looking away].

Bottom right frame (detail shot):
Close-up of [PRODUCT DETAIL — hands adjusting collar / zipper / showing the graphic print]. Emphasize [TEXTURE DETAILS — fabric grain, stitching, print quality].

Lighting: cinematic and contrasty with soft reflections. Highly detailed textures on fabric, skin, and background. Premium editorial style, modern fashion campaign look.

1:1 aspect ratio.""",
    },
    {
        "id": "ym-38-street-style-selfie-doodles",
        "name": "Street Style Selfie with Doodle Annotations",
        "category": "educational",
        "description": "Casual urban selfie with hand-drawn white doodle annotations labeling outfit elements. Great for product callouts.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "9:16"],
        "tags": ["selfie", "doodles", "annotations", "callouts", "street-style", "educational"],
        "modifications_needed": "Customize doodle labels for your specific product features.",
        "template_prompt": """{
  "scene": "a [PERSON DESCRIPTION] taking a selfie while walking on a quiet urban street",
  "composition": {
    "camera_angle": "handheld selfie, slightly above eye level",
    "lens": "wide-angle smartphone lens",
    "framing": "upper body centered, extended arm visible"
  },
  "subject": {
    "appearance": "[PERSON with HAIR DESCRIPTION], wearing sunglasses",
    "expression": "smiling",
    "outfit": {
      "top": "[YOUR PRODUCT — exact description]",
      "bottom": "[COMPLEMENTARY BOTTOM]",
      "shoes": "[SHOES]",
      "accessories": [
        "[ACCESSORY 1]",
        "[ACCESSORY 2 — e.g. coffee cup]"
      ]
    }
  },
  "environment": {
    "location": "[AMERICAN STREET SETTING]",
    "details": ["parked cars", "trees", "clean sidewalk"]
  },
  "lighting": {
    "type": "natural daylight",
    "condition": "bright sunny day"
  },
  "overlays": {
    "style": "hand-drawn white doodles and annotations",
    "elements": [
      "arrows pointing to [PRODUCT] with label '[PRODUCT CALLOUT]'",
      "arrows to [ACCESSORY] with label '[ACCESSORY NAME]'",
      "arrows to shoes with label '[SHOE DESCRIPTION]'",
      "[ADDITIONAL DOODLE LABELS for brand elements]"
    ]
  }
}

4:5 aspect ratio.""",
    },
    {
        "id": "ym-50-podcast-studio-portrait",
        "name": "Cinematic Podcast Studio Portrait",
        "category": "thumbnail",
        "description": "Professional podcast host in modern studio. Warm accent lighting, realistic equipment details.",
        "product_types": ["any"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["16:9", "1:1"],
        "tags": ["podcast", "studio", "portrait", "cinematic", "youtube", "thumbnail"],
        "modifications_needed": "As-is. Good for brand content thumbnails.",
        "template_prompt": """A professional [PERSON DESCRIPTION — e.g. podcast host / brand founder / content creator] sitting at a wooden desk in a modern studio setup, facing the camera with a confident and friendly expression. Wearing [OUTFIT — e.g. fitted black shirt / brand merch / casual blazer]. Sitting in a comfortable chair. A high-quality podcast microphone on a boom arm positioned close to mouth.

On the desk: a notebook with handwritten notes, a coffee mug, and an audio interface with connected cables. Background features [BACKGROUND — stylish indoor plants and warm accent lighting / bookshelf / brand colors on wall], creating a clean, cinematic studio atmosphere.

Soft key lighting on face, subtle rim lighting, shallow depth of field, ultra-realistic details, 50mm lens, f/1.8, professional color grading, high contrast, 8K, YouTube podcast aesthetic.

16:9 aspect ratio.""",
    },
    {
        "id": "ym-52-cinematic-festival-portrait",
        "name": "Cinematic Festival Portrait",
        "category": "lifestyle",
        "description": "Energetic outdoor festival photo with neon lighting. Originally referenced a celebrity — use your own model.",
        "product_types": ["apparel", "fashion", "accessories"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["9:16"],
        "tags": ["festival", "cinematic", "neon", "energetic", "outdoor", "youth"],
        "modifications_needed": "Remove celebrity reference. Use target demographic description.",
        "template_prompt": """Create a highly detailed, cinematic, photorealistic lifestyle photograph of [PERSON DESCRIPTION matching target demographic — NO celebrity references] at an outdoor festival during early evening. They have [HAIR DESCRIPTION] and a playful expression, smiling while looking back over their shoulder directly at the camera. Makeup is light and natural.

Wearing [YOUR PRODUCT — exact description from product images], paired with [COMPLEMENTARY ITEMS]. On their feet, [SHOES].

Pose is dynamic and confident: standing with back partially facing camera, torso twisted looking over shoulder. One arm slightly raised with relaxed hand, weight on one leg, creating casual and energetic posture.

Setting is a lively outdoor festival / amusement park. Background: large Ferris wheel illuminated with neon pink and white lights. Blurred figures walking in background.

Lighting combines soft dusk light with strong cool artificial ambient from neon lights. Neon creates glowing rim light around hair, shoulders, and silhouette, while soft front fill illuminates face and body.

Mood: vibrant, youthful, energetic, cinematic summer festival. Color palette: neon pink, bright white, [BRAND COLORS].

Portrait orientation (9:16), slightly low camera angle, 85-135mm telephoto lens, shallow depth of field, sharp subject with soft bokeh background. 8K resolution.""",
    },
    {
        "id": "ym-57-subway-motion-blur",
        "name": "Subway Platform with Motion Blur",
        "category": "lifestyle",
        "description": "Cinematic photo on subway platform with passing train creating motion blur. Subject in sharp focus. Modifiable settings.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["solution_aware", "product_aware"],
        "funnel_stage": "consideration",
        "aspect_ratios": ["4:5", "9:16"],
        "tags": ["subway", "motion-blur", "cinematic", "urban", "fashion", "dramatic"],
        "modifications_needed": "Setting can be modified (subway, train station, busy street, etc).",
        "template_prompt": """Create a realistic cinematic photo of [PERSON DESCRIPTION matching target demographic] using the face from the uploaded image. Standing on a [SETTING — subway platform / train station / busy city sidewalk] while a [MOVING ELEMENT — train passes / traffic streams / crowd walks] behind at high speed, creating motion blur.

The subject is still and in sharp focus, looking slightly to the side with a calm and confident expression. Holding [PROP — bouquet of flowers / coffee cup / shopping bag / nothing] in one hand.

Outfit: [YOUR PRODUCT — exact description from product images], paired with [COMPLEMENTARY ITEMS].

Lighting is soft but cinematic, with natural indoor tones from [LIGHT SOURCE — station lights / street lamps / ambient city glow]. Background shows the [MOVING ELEMENT] blurred with streaks of motion. Floor reflects light, adding depth.

Cinematic photography, motion blur effect, atmospheric depth, realistic shadows, high detail, aesthetic composition.

4:5 aspect ratio.""",
    },
    {
        "id": "ym-86-mixed-media-urban-editorial",
        "name": "Mixed Media Urban Fashion Editorial",
        "category": "editorial",
        "description": "Fashion editorial blending realistic photography with 2D cartoon characters and hand-drawn graphic elements.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["unaware", "problem_aware"],
        "funnel_stage": "awareness",
        "aspect_ratios": ["1:1", "4:5"],
        "tags": ["mixed-media", "editorial", "cartoon", "urban", "fashion", "creative"],
        "modifications_needed": "Change cartoon characters to match brand personality. Adjust outfit to your product.",
        "template_prompt": """A full-body fashion editorial featuring a [PERSON DESCRIPTION matching target demographic] sitting casually on a [SURFACE — concrete ledge / park bench / steps] in a bright, sunlit urban environment. Wearing [YOUR PRODUCT — exact description from product images], paired with [COMPLEMENTARY ITEMS].

The image is a mixed-media composition blending high-end photorealism with classic 2D animation. To the left, [CARTOON CHARACTER 1 — e.g. a playful illustrated mascot / brand character] leans coolly against [SURFACE]. To the right, [CARTOON CHARACTER 2 — or additional illustrated elements / brand icons].

The scene is accented with hand-drawn graphic elements, including black motion lines, hand-drawn arrows, and sparkling yellow stars. Lighting is crisp with strong natural shadows, set against a clear blue sky, creating a vibrant, high-contrast, magazine-quality aesthetic.

1:1 aspect ratio.""",
    },
    {
        "id": "ym-92-boutique-mirror-selfie",
        "name": "Ultra-Realistic Boutique Mirror Selfie",
        "category": "ugc",
        "description": "Hyper-realistic boutique owner mirror selfie for Instagram. Exact outfit recreation with store environment.",
        "product_types": ["apparel", "fashion"],
        "audience_fit": ["product_aware", "most_aware"],
        "funnel_stage": "conversion",
        "aspect_ratios": ["5:7", "4:5"],
        "tags": ["boutique", "mirror-selfie", "ugc", "instagram", "hyper-realistic", "ecommerce"],
        "modifications_needed": "As-is. Perfect for apparel brands.",
        "template_prompt": """{
  "goal": "Ultra-realistic smartphone mirror selfie of a [PERSON DESCRIPTION matching target demographic] showcasing [YOUR PRODUCT — exact outfit description], indistinguishable from a real Instagram post.",
  "identity_consistency": {
    "priority": "critical",
    "reference": "Use uploaded image as absolute truth for product appearance",
    "match": ["face (natural, not overly detailed)", "body type & proportions", "skin tone & texture (pores, imperfections)", "hair (color, density, natural strands)"]
  },
  "outfit_accuracy": {
    "priority": "extreme",
    "match": ["fabric, folds, stitching, fit", "wrinkles, tension", "colors (exact)", "text/graphics on garment (exact)"],
    "behavior": "Natural wear with realistic gravity and body interaction",
    "rules": ["Do not redesign or simplify the product", "Exact recreation from reference images"]
  },
  "environment": {
    "type": "[SETTING — realistic boutique store / bedroom / walk-in closet]",
    "elements": ["mirrors", "clothing racks or hangers", "lifestyle decor"],
    "lighting": "soft, slightly warm retail/home lighting"
  },
  "scene": {
    "action": ["holding smartphone", "taking mirror selfie", "looking at phone screen"],
    "pose": "natural, relaxed, confident, slight hip shift",
    "energy": "[BRAND ENERGY — fashion entrepreneur / cozy mom / confident trendsetter]"
  },
  "camera": {
    "type": "smartphone",
    "aspect_ratio": "4:5 vertical",
    "framing": "mid to full body",
    "features": ["slight perspective distortion", "accurate mirror alignment"]
  },
  "realism_details": {
    "clothing": "visible texture, natural folds & pressure from real wear",
    "mirror": "accurate reflections",
    "hands": "anatomically correct, natural grip on phone",
    "imperfections": ["slight noise", "minor lighting inconsistencies"]
  },
  "final_expectation": "Feels like a real person casually posting a mirror selfie showcasing their outfit."
}

4:5 aspect ratio.""",
    },
]

for t in TEMPLATES:
    t["source"] = SOURCE
    t["platforms"] = ["meta", "tiktok"]
    filename = f"{t['id']}.yaml"
    path = OUTPUT_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(t, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"  Created: {path}")

print(f"\nDone! {len(TEMPLATES)} YouMind prompts imported to {OUTPUT_DIR}")
