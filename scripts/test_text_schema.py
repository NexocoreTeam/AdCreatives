"""End-to-end smoke test for the new text_schema pipeline.

Runs against `clients/secondkind/reference_ads/raw/us-vs-them/us-vs-them-Ad-1-PetLab Co..png`
and SecondKind's primary avatar ("Done-Everything Danielle") + Gut Balance product.

Steps:
  1. Run the (updated) template_extractor on the PetLab us-vs-them image —
     prints the new YAML including text_schema with [SLOT_ID] placeholders.
  2. Build a synthetic CreativeBrief for a postbiotic-vs-probiotic angle.
  3. Run fill_text_schema_for_brief() — prints the per-slot ICP-language fills.
  4. Run substitute_slot_fills() + render_slot_fills_block() — prints the
     final NB2-ready template body and the SOURCE OF TRUTH block.

This is a manual/visual smoke test; assertion-style coverage lives in
tests/test_text_remapper.py.

Run from the worktree root:
    python scripts/test_text_schema.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# The `adcreatives` package is editable-installed from the main repo, so a
# bare `from models.library import ...` resolves THERE — not in this worktree.
# Prepend the worktree root to sys.path so our updated TextSlot is picked up.
_WORKTREE_ROOT = Path(__file__).resolve().parent.parent
if str(_WORKTREE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKTREE_ROOT))

import os

import yaml
from dotenv import find_dotenv, load_dotenv

# Walk parents — .env lives at the AdCreatives repo root, not the worktree.
# Override=True is necessary on Windows where the shell sets API key vars to
# empty strings (e.g. `ANTHROPIC_API_KEY=`). With override=False, dotenv treats
# the empty string as "already set" and won't write the real value.
_DOTENV_PATH = find_dotenv()
if _DOTENV_PATH:
    # Only override keys that are missing or empty in the current env. Real
    # shell-set values still win — matches cli.py's bootstrap behavior.
    from dotenv import dotenv_values

    for _k, _v in (dotenv_values(_DOTENV_PATH) or {}).items():
        if _k and (not os.environ.get(_k)):
            os.environ[_k] = _v or ""
load_dotenv(override=False)

from datetime import datetime

from generators import fal_client
from generators.prompt_engine import prompt_from_brief_and_template
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.library import LibraryPrompt, TextSlot
from models.loader import (
    load_all_avatars,
    load_avatar,
    load_brand,
    load_product_by_name,
)
from strategy.brand_enricher import _downscale_to_data_uri
from strategy.llm import gemini_vision
from strategy.template_extractor import (
    TEMPLATE_EXTRACTOR_SYSTEM,
    _build_user_prompt,
    _load_existing_analysis,
    _parse_yaml_response,
)
from strategy.text_remapper import (
    fill_text_schema_for_brief,
    render_slot_fills_block,
    substitute_slot_fills,
)


def _extract_with_visibility(image_path: Path, client: str, category: str) -> dict:
    """Run the extractor's vision call and ALWAYS print the raw response, so
    parser failures are debuggable. Mirrors strategy.template_extractor.
    extract_template_from_ad but with a debug shim."""
    suffix = image_path.suffix.lower()
    mime = (
        "image/png" if suffix == ".png"
        else "image/jpeg" if suffix in (".jpg", ".jpeg")
        else "image/webp" if suffix == ".webp"
        else "application/octet-stream"
    )
    raw_bytes = image_path.read_bytes()
    data_uri = _downscale_to_data_uri(raw_bytes, mime)
    analysis = _load_existing_analysis(client, category, image_path.stem)
    user_prompt = _build_user_prompt(image_path.name, category, analysis)

    response = gemini_vision(
        prompt=user_prompt,
        image_urls=[data_uri],
        system=TEMPLATE_EXTRACTOR_SYSTEM,
        max_tokens=6144,
    )
    print("--- RAW MODEL RESPONSE ---")
    print(response)
    print("--- END RAW ---")
    return _parse_yaml_response(response)


CLIENT = "secondkind"
CATEGORY = "us-vs-them"
IMAGE = Path(
    "clients/secondkind/reference_ads/raw/us-vs-them/us-vs-them-Ad-1-PetLab Co..png"
)


def banner(title: str) -> None:
    print()
    print("=" * 78)
    print(f"  {title}")
    print("=" * 78)


def main() -> None:
    if not IMAGE.exists():
        raise SystemExit(f"Image not found: {IMAGE}")

    banner("STEP 1 — Extract template + text_schema from PetLab us-vs-them ad")
    print(f"Source image: {IMAGE}")
    raw = _extract_with_visibility(IMAGE, CLIENT, CATEGORY)
    raw.setdefault("text_schema", [])
    print()
    print(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True, width=100))

    schema_raw = raw.get("text_schema") or []
    if not schema_raw:
        raise SystemExit(
            "Extractor returned empty text_schema. Check the model response."
        )

    template = LibraryPrompt(
        id=raw.get("id", "test-template"),
        name=raw.get("name", "Test"),
        source=raw.get("source", ""),
        category=raw.get("category", CATEGORY),
        product_types=raw.get("product_types", ["any"]),
        audience_fit=raw.get("audience_fit", []),
        funnel_stage=raw.get("funnel_stage", "consideration"),
        platforms=raw.get("platforms", ["meta"]),
        aspect_ratios=raw.get("aspect_ratios", ["1:1"]),
        template_prompt=raw.get("template_prompt", ""),
        text_schema=[TextSlot(**s) for s in schema_raw],
        description=raw.get("description", ""),
        tags=raw.get("tags", []),
    )

    banner(
        "STEP 2 — Load SecondKind context + synthesize a us-vs-them brief"
    )
    brand = load_brand(CLIENT)
    product = load_product_by_name(CLIENT, "Gut Balance")
    # Prefer the curated `avatars/primary.yaml` over the auto-drafted legacy
    # `avatar.yaml` so the fill step has real pain quotes to work with.
    all_avatars = load_all_avatars(CLIENT)
    avatar = all_avatars[0] if all_avatars else load_avatar(CLIENT)
    print(f"Brand: {brand.name}")
    print(f"Product: {product.name}")
    print(f"Avatar: {avatar.name if avatar else '(none)'}")

    brief = CreativeBrief(
        brief_id=f"{CLIENT}-gut-balance-test-vs-them",
        client=CLIENT,
        product=product.name,
        awareness_level=AwarenessLevel.PROBLEM_AWARE,
        framework=CopyFramework.PAS,
        angle=(
            "Skip the live-bacteria gamble. Postbiotics deliver the actual "
            "compounds your gut needs — no roulette, no waiting weeks."
        ),
        hook=(
            "Tried three probiotics and still bloated by dinner? "
            "Postbiotics work on day one because they ARE the active compounds."
        ),
        hook_type="contrast",
        hook_tactic="reframe the category",
        creative_mechanic="reframing_perception_plus_emotional_trigger",
        visual_format="split-screen comparison, us-vs-them",
        pain_point="Probiotic fatigue — spent real money on brands that did nothing.",
        benefit_callouts=[
            "Works on day one",
            "1 trillion bioactive compounds",
            "No live-bacteria guessing",
            "Shelf-stable, vegan, third-party tested",
        ],
        cta="See the difference",
        target_platform="meta",
        persona=(avatar.name if avatar else "Done-Everything Danielle"),
    )

    banner("STEP 3 — fill_text_schema_for_brief() — ICP-language per-slot fills")
    fills = fill_text_schema_for_brief(
        brief=brief,
        schema=template.text_schema,
        brand=brand,
        product=product,
        avatar=avatar,
    )
    for slot in template.text_schema:
        marker = "[" + slot.slot_id.upper() + "]"
        print(
            f"  {marker:<24} ({slot.role}, max {slot.max_words}w, "
            f"parallel_to={slot.parallel_to or '-'})"
        )
        print(f"      intent: {slot.intent}")
        print(f'      fill  : "{fills.get(slot.slot_id, "")}"')
        print()

    banner("STEP 4 — substitute_slot_fills() — rendered template_prompt body")
    rendered = substitute_slot_fills(template.template_prompt, fills)
    print(rendered)

    banner("STEP 5 — render_slot_fills_block() — SOURCE OF TRUTH appended to NB2 prompt")
    print(render_slot_fills_block(fills, template.text_schema))

    banner("STEP 6 — Build the full NB2 prompt + generate an actual image")
    nb2_prompt = prompt_from_brief_and_template(
        brief=brief,
        template=template,
        brand=brand,
        product=product,
        avatar=avatar,
        aspect_ratio="9:16",
        reference_image_path=IMAGE,
        client_slug=CLIENT,
    )
    print("--- NB2 PROMPT (truncated to 1500 chars) ---")
    print(nb2_prompt[:1500])
    if len(nb2_prompt) > 1500:
        print(f"...[truncated, full length {len(nb2_prompt)} chars]")
    print("--- END NB2 PROMPT ---")

    # Resolve product + reference image URLs for fal.ai. The product image
    # has a public URL; the PetLab reference is local and needs uploading.
    print()
    print("Resolving image URLs for fal.ai...")
    product_url = product.image_url
    if not product_url:
        raise SystemExit(
            f"Product '{product.name}' has no public image_url. Set "
            "image_url in the product YAML or upload the local file first."
        )
    reference_url = fal_client.upload_image(IMAGE)
    print(f"  Product image:   {product_url}")
    print(f"  Reference image: {reference_url}")

    # Generate. nano-banana-2/edit accepts multiple reference images; the
    # first is the actual product (replicated exactly), the second is the
    # PetLab ad (layout / typography / mood reference only — slot fills
    # are the source of truth for on-image text).
    save_dir = Path("scripts/test_text_schema_output")
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename_prefix = f"us-vs-them-test-{timestamp}"

    print(f"\nCalling fal.ai NB2 (this typically takes 30-60s)...")
    results = fal_client.generate_and_save(
        prompt=nb2_prompt,
        product_image_urls=[product_url, reference_url],
        save_dir=save_dir,
        filename_prefix=filename_prefix,
        aspect_ratio="9:16",
        resolution="1K",
        num_images=1,
    )

    banner("DONE")
    if results and results[0].local_path:
        print(f"Image saved: {results[0].local_path}")
        print(f"Image URL:   {results[0].image_url}")
        print(f"Seed:        {results[0].seed}")
    else:
        print("No image returned — check fal.ai response above.")
    print()
    print("If the slot fills above sound like SecondKind talking about Gut")
    print("Balance to Done-Everything Danielle, and the rendered image's")
    print("on-image text matches the SLOT FILLS exactly (no 'PetLabCo.',")
    print("no 'Grass eating', no em-dashes), the new pipeline is working")
    print("end-to-end.")


if __name__ == "__main__":
    main()
