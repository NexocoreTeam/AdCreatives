"""Test run: Generate 4 spring outdoor photoshoot variants for the
'LOVES JESUS + AMERICA, TOO.' tee via Nano Banana 2."""

import os
import sys

os.environ["FAL_KEY"] = "c6c17b6b-4bee-4e56-a79f-994e3342d8e6:76bcb6bcc7a522d649c3b0a7cdbe68e1"

from pathlib import Path
import fal_client
import httpx

PRODUCT_IMAGES = [
    "https://cdn.shopify.com/s/files/1/2833/1370/files/Screenshot2025-05-13at4.15.55PM.png?v=1762463560",
    "https://cdn.shopify.com/s/files/1/2833/1370/files/Screenshot2025-05-13at4.16.38PM.png?v=1747167437",
    "https://cdn.shopify.com/s/files/1/2833/1370/files/Screenshot2025-05-13at4.15.31PM.png?v=1747167437",
]

OUTPUT_DIR = Path("output/sbg-co/test-loves-jesus-tee")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PROMPTS = {
    "01-natural-cinematic": (
        'Use the attached images as brand reference. Match the exact product design, color, and text precisely. '
        'Create a highly detailed, cinematic, photorealistic lifestyle photograph of a woman in her late 20s to early 30s, '
        'warm approachable smile, medium-length wavy brown hair, natural minimal makeup. She is sitting casually on the grass '
        'in a sunlit spring meadow - lush green grass with small wildflowers scattered naturally. '
        'She is wearing the exact garment from the reference images: a crimson/brick red garment-dyed Comfort Colors crewneck '
        't-shirt, relaxed oversized fit, with white small-caps text reading "LOVES JESUS + AMERICA, TOO." centered across the '
        'chest. The text must be reproduced exactly as shown - all capitals, with the plus sign and period. '
        'Paired with light-wash high-waisted jeans and tan/beige sneakers. '
        'Her pose is relaxed and natural - one hand resting on the grass beside her, the other touching her hair or resting on '
        'her knee. She is looking slightly off-camera with a calm, genuine, content expression. Not posed - a real moment captured. '
        'The setting is a beautiful open meadow or park during golden hour. Warm afternoon sunlight coming from behind and to the '
        'right, creating a soft golden rim light around her hair and shoulders. Background is soft bokeh of green trees and blue '
        'sky with gentle lens flare. '
        'Camera: portrait prime 85mm, f/2.8, shallow depth of field. Subject tack sharp, background melting into creamy bokeh. '
        'Subtle 35mm film grain for warmth. 8K resolution, photorealistic detail on fabric texture and skin. '
        'Mood: warm, peaceful, authentic. Like a friend Instagram post on a beautiful spring day. '
        '4:5 aspect ratio.'
    ),
    "02-editorial-flash": (
        'Use the attached images as brand reference. Match the exact product design, color, and text precisely. '
        'A woman in her late 20s, confident warm expression, shoulder-length dark hair with natural texture, minimal dewy makeup. '
        'She is standing in a lush green spring field - tall grass reaching her mid-shin, scattered with small white and yellow '
        'wildflowers. '
        'She is wearing the exact garment from the reference images: a crimson/brick red garment-dyed Comfort Colors crewneck '
        't-shirt, relaxed oversized fit, with white small-caps text reading "LOVES JESUS + AMERICA, TOO." centered across the '
        'chest. Text must be exact - all capitals, plus sign, period after TOO. Paired with light-wash denim cutoff shorts and '
        'tan sandals. '
        'Her pose is mid-stride or standing with one hand on her hip, looking directly at camera with a genuine bright smile. '
        'Wind catching her hair slightly. '
        'Shot with direct on-camera flash creating a contrast between the glossy highlights on her skin and the warm golden hour '
        'sunset ambiance behind her. The sky is a gradient of warm peach and soft pink tones. Grass catching golden backlight. '
        'Camera: 50mm lens, shallow depth of field, centered framing. Direct flash mixed with golden hour creates editorial '
        'fashion-meets-authentic energy. '
        'Style: fashion editorial meets real-life candid. Not overly produced - but beautifully lit. '
        'Quality: high detail, ultra realistic, sharp focus on subject and garment text, photorealistic skin texture. '
        '4:5 aspect ratio.'
    ),
    "03-warm-lifestyle": (
        'Use the attached images as brand reference. Match the exact product design, color, and text precisely. '
        'A woman in her early 30s, approachable and natural, light brown skin, wavy dark hair past her shoulders, genuine '
        'relaxed smile. She is sitting cross-legged on a soft blanket spread on lush spring grass in a park or backyard. '
        'Dappled sunlight filtering through trees above. '
        'She is wearing the exact garment from the reference images: a crimson/brick red garment-dyed Comfort Colors crewneck '
        't-shirt, relaxed oversized fit with natural fabric drape, with white small-caps text reading "LOVES JESUS + AMERICA, '
        'TOO." centered across the chest. The garment-dyed texture is visible - slightly faded, soft, lived-in feel. Paired with '
        'light-wash high-waisted mom jeans rolled at the ankle, barefoot on the blanket. '
        'A coffee cup sits beside her on the blanket. She is laughing or mid-conversation - candid, not posed. One hand holding '
        'her phone casually, the other gesturing naturally. '
        'Camera: 35-50mm portrait lens, f/2.0, hyper-detailed skin textures with visible pores and natural complexion. No '
        'airbrushing. Influencer lifestyle photography aesthetic. '
        'Lighting: soft dappled natural light through tree canopy, warm tones, gentle shadows on the blanket. Bright but not '
        'harsh. Spring afternoon feel. '
        'Background: blurred green park setting - trees, maybe a fence or garden visible but soft. Shallow depth of field keeps '
        'focus on her and the shirt. '
        'Mood: cozy, authentic. Feels like a real person Instagram, not a brand photoshoot. '
        '4:5 aspect ratio.'
    ),
    "04-influencer-casual": (
        'Use the attached images as brand reference. Match the exact product design, color, and text precisely. '
        'A woman in her late 20s, radiant smile, medium-length wavy dark hair, natural glowing makeup with soft bronzer and '
        'glossy lips. She is walking through a sun-drenched park path lined with lush green trees and spring blooms, taking a '
        'candid photo - not a selfie, but shot by a friend walking beside her. '
        'She is wearing the exact garment from the reference images: a crimson/brick red garment-dyed Comfort Colors crewneck '
        't-shirt, relaxed oversized fit with the front casually tucked into the waistband on one side, with white small-caps text '
        'reading "LOVES JESUS + AMERICA, TOO." centered across the chest. Text must be exact - all capitals, plus sign, period '
        'after TOO. The garment-dyed wash texture is visible. Paired with high-waisted light-wash straight-leg jeans, white '
        'sneakers, and a small tan crossbody bag. Thin gold hoop earrings and a simple gold necklace. '
        'She is mid-stride, one hand adjusting her hair or holding an iced coffee, the other swinging naturally. Looking at '
        'camera with a big genuine laugh like her friend just said something funny. Slightly turned body - not straight-on, a '
        'natural three-quarter angle. '
        'Camera: smartphone quality but elevated - shot on iPhone 15 Pro at 24mm, slightly wide perspective, natural portrait '
        'mode blur on the tree-lined path behind her. Bright, clean, slightly warm color grade. '
        'Lighting: bright midday spring sun, soft shadows from tree canopy overhead creating beautiful light patches on the path '
        'and her face. Natural sun highlights in her hair. No harsh shadows - open shade energy with pockets of direct light. '
        'Style: influencer-casual. Not a photoshoot - looks like her friend tagged her in this on Instagram stories. Aspirational '
        'but completely accessible. The shirt is the quiet hero of the image. '
        'No text overlays, no logos, no brand elements besides what is on the shirt. This should look like organic content, not '
        'an ad. '
        '4:5 aspect ratio.'
    ),
}


def download(url: str, path: Path):
    with httpx.Client(timeout=60) as c:
        r = c.get(url)
        r.raise_for_status()
        path.write_bytes(r.content)


for name, prompt in PROMPTS.items():
    print(f"Generating {name}...")
    try:
        result = fal_client.subscribe(
            "fal-ai/nano-banana-2/edit",
            arguments={
                "prompt": prompt,
                "image_urls": PRODUCT_IMAGES,
                "aspect_ratio": "4:5",
                "resolution": "1K",
                "num_images": 1,
                "output_format": "png",
            },
        )
        for img in result.get("images", []):
            url = img.get("url", "")
            save_path = OUTPUT_DIR / f"{name}.png"
            download(url, save_path)
            print(f"  Saved: {save_path}")
    except Exception as e:
        print(f"  ERROR: {e}")
    print()

print("Done! All 4 prompts generated.")
