"""Platform-specific adaptations for Meta, TikTok, etc."""

from __future__ import annotations

# Platform-specific prompt modifiers applied on top of style modifiers
PLATFORM_CONFIGS = {
    "meta": {
        "feed": {
            "sizes": [(1080, 1080, "Feed Square"), (1080, 1350, "Feed Portrait")],
            "prompt_suffix": "polished commercial photography, clean composition, premium",
            "tone_adjustment": "",
        },
        "story": {
            "sizes": [(1080, 1920, "Story/Reel")],
            "prompt_suffix": "vertical composition, bold and immediate, story-optimized",
            "tone_adjustment": "more casual and direct",
        },
        "reels": {
            "sizes": [(1080, 1920, "Reel Cover")],
            "prompt_suffix": "dynamic vertical composition, eye-catching, reels thumbnail",
            "tone_adjustment": "energetic and bold",
        },
    },
    "tiktok": {
        "feed": {
            "sizes": [(1080, 1920, "TikTok Full Screen")],
            "prompt_suffix": (
                "authentic and raw, slightly imperfect, not overly produced, "
                "natural lighting, handheld camera aesthetic"
            ),
            "tone_adjustment": "casual, relatable, anti-polished",
        },
    },
    "youtube": {
        "thumbnail": {
            "sizes": [(1280, 720, "YouTube Thumbnail")],
            "prompt_suffix": "bold high-contrast, large readable elements, thumbnail-optimized",
            "tone_adjustment": "high energy, curiosity-driving",
        },
    },
}

# Platform-specific best practices
PLATFORM_GUIDELINES = {
    "meta": {
        "max_text_coverage": 0.20,  # Meta penalizes >20% text
        "best_performing_formats": ["benefit-callout", "social-proof", "product-hero"],
        "notes": "Polished creative performs well. AI creative gets ~12% higher CTR.",
    },
    "tiktok": {
        "max_text_coverage": 0.30,  # TikTok is more text-tolerant
        "best_performing_formats": ["lifestyle-ugc", "split-comparison"],
        "notes": (
            "Authentic/raw aesthetic outperforms polished. "
            "AI creative CTR advantage is smallest here."
        ),
    },
}


def get_platform_sizes(
    platform: str,
    placement: str = "feed",
) -> list[tuple[int, int, str]]:
    """Get image sizes for a platform + placement combo."""
    config = PLATFORM_CONFIGS.get(platform, {}).get(placement, {})
    return config.get("sizes", [(1080, 1080, "Default")])


def get_platform_prompt_suffix(platform: str, placement: str = "feed") -> str:
    """Get platform-specific prompt additions."""
    config = PLATFORM_CONFIGS.get(platform, {}).get(placement, {})
    return config.get("prompt_suffix", "")


def get_all_sizes_for_platform(platform: str) -> list[tuple[int, int, str]]:
    """Get all sizes across all placements for a platform."""
    sizes = []
    for placement_config in PLATFORM_CONFIGS.get(platform, {}).values():
        sizes.extend(placement_config.get("sizes", []))
    return sizes
