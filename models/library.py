"""Prompt library model and loader for ad creative templates."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

LIBRARY_DIR = Path("prompts/library")


class LibraryPrompt(BaseModel):
    """A single prompt template from the library."""

    id: str = Field(description="Unique identifier, e.g. 'cooper-07-us-vs-them'")
    name: str = Field(description="Human-readable name")
    source: str = Field(default="", description="Attribution: 'Alex Cooper / Adcrate', repo URL, etc.")
    category: str = Field(
        default="general",
        description="Ad format category: headline, offer, testimonial, comparison, "
        "ugc, editorial, social-proof, product-hero, lifestyle, etc.",
    )
    product_types: list[str] = Field(
        default_factory=lambda: ["any"],
        description="Product types this works for: any, food, beverage, apparel, "
        "supplement, saas, beauty, home, etc.",
    )
    audience_fit: list[str] = Field(
        default_factory=list,
        description="Schwartz awareness levels this suits: unaware, problem_aware, "
        "solution_aware, product_aware, most_aware",
    )
    funnel_stage: str = Field(
        default="consideration",
        description="Funnel stage: awareness, consideration, conversion, retention",
    )
    platforms: list[str] = Field(
        default_factory=lambda: ["meta", "tiktok"],
        description="Target platforms",
    )
    aspect_ratios: list[str] = Field(
        default_factory=lambda: ["1:1", "4:5"],
        description="Recommended aspect ratios",
    )
    template_prompt: str = Field(
        description="The full prompt template with [PLACEHOLDERS] in caps. "
        "Claude fills these in with client-specific details.",
    )
    description: str = Field(
        default="",
        description="When to use this template and what it does",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Searchable tags for filtering",
    )


def load_prompt(prompt_id: str) -> LibraryPrompt:
    """Load a single prompt by ID. Searches all library subdirectories."""
    for yaml_file in LIBRARY_DIR.rglob("*.yaml"):
        if yaml_file.name == "_index.yaml":
            continue
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        if data and data.get("id") == prompt_id:
            return LibraryPrompt(**data)

    # Also try matching by filename stem
    for yaml_file in LIBRARY_DIR.rglob("*.yaml"):
        if yaml_file.stem == prompt_id or yaml_file.stem.endswith(prompt_id):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if data:
                return LibraryPrompt(**data)

    raise FileNotFoundError(f"Prompt '{prompt_id}' not found in {LIBRARY_DIR}")


def list_prompts(
    category: str | None = None,
    product_type: str | None = None,
    platform: str | None = None,
    source_dir: str | None = None,
    tags: list[str] | None = None,
) -> list[LibraryPrompt]:
    """List and filter prompts from the library."""
    prompts = []
    search_dir = LIBRARY_DIR / source_dir if source_dir else LIBRARY_DIR

    for yaml_file in sorted(search_dir.rglob("*.yaml")):
        if yaml_file.name == "_index.yaml":
            continue
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            if not data or "template_prompt" not in data:
                continue
            prompt = LibraryPrompt(**data)
        except Exception:
            continue

        # Apply filters
        if category and prompt.category != category:
            continue
        if product_type and product_type not in prompt.product_types and "any" not in prompt.product_types:
            continue
        if platform and platform not in prompt.platforms:
            continue
        if tags and not any(t in prompt.tags for t in tags):
            continue

        prompts.append(prompt)

    return prompts


def list_categories() -> list[str]:
    """Get all unique categories in the library."""
    categories = set()
    for prompt in list_prompts():
        categories.add(prompt.category)
    return sorted(categories)


def save_prompt(prompt: LibraryPrompt, subdir: str = "custom") -> Path:
    """Save a prompt to the library."""
    dir_path = LIBRARY_DIR / subdir
    dir_path.mkdir(parents=True, exist_ok=True)
    # Create filename from ID
    filename = prompt.id.replace("/", "-").replace(" ", "-") + ".yaml"
    path = dir_path / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            prompt.model_dump(mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
        )
    return path
