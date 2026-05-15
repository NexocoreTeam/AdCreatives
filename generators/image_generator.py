"""Image generation orchestrator — ties prompt engine + fal client + validators together.

Four generation modes matching the prompt engine:
1. generate_from_reference: "Make it like this" ad
2. generate_from_library: Use a library prompt template
3. generate_from_recommendation: Let the system pick the best templates
4. generate_from_brief: Drive both prompt + image from a CreativeBrief

All modes pass real product images alongside the prompt to Nano Banana 2.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.library import LibraryPrompt, load_prompt
from models.product import Product
from generators.fal_client import (
    GenerationResult,
    generate_and_save,
    resolve_product_images,
    upload_image,
)
from generators.prompt_engine import (
    find_library_examples_for_brief,
    infer_aspect_ratio,
    prompt_from_brief,
    prompt_from_brief_and_template,
    prompt_from_library,
    prompt_from_reference,
    recommend_prompts,
)
from generators.swipe_matcher import match_for_brief


def _get_product_image_urls(product: Product, client_slug: str) -> list[str]:
    """Collect all product image URLs for passing to Nano Banana 2."""
    urls = []

    # Primary image URL (preferred)
    if product.image_url:
        urls.append(product.image_url)

    # If no URL, try uploading local files
    if not urls and product.image_path:
        local = Path("clients") / client_slug / product.image_path
        if not local.exists():
            local = Path(product.image_path)
        urls = resolve_product_images(product_image_paths=[local])

    if not urls:
        raise ValueError(
            f"No product images found for '{product.name}'. "
            "Real product images are REQUIRED. Add image_url or image_path to the product YAML."
        )

    return urls


def _build_output_dir(client_slug: str, label: str) -> Path:
    today = date.today().isoformat()
    return Path("output") / client_slug / today / label


# ─── Mode 1: "Make it like this" ────────────────────────────────────────────


def generate_like_this(
    reference_image_path: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str = "1:1",
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    thinking_level: str = "disabled",
) -> tuple[str, list[GenerationResult]]:
    """Analyze a reference ad and generate a similar one for your product.

    Returns (prompt_used, generation_results).
    """
    # Get real product images
    product_urls = _get_product_image_urls(product, client_slug)

    # Claude writes the prompt based on the reference ad
    prompt = prompt_from_reference(
        reference_image_path=reference_image_path,
        brand=brand,
        product=product,
        avatar=avatar,
        platform=platform,
        aspect_ratio=aspect_ratio,
    )

    # Generate with Nano Banana 2
    if output_dir is None:
        output_dir = _build_output_dir(client_slug, "make-like-this")

    product_slug = product.name.lower().replace(" ", "-")
    results = generate_and_save(
        prompt=prompt,
        product_image_urls=product_urls,
        save_dir=output_dir,
        filename_prefix=product_slug,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    return prompt, results


# ─── Mode 2: "Use this library prompt" ──────────────────────────────────────


def generate_from_library(
    prompt_id: str,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    aspect_ratio: str | None = None,
    modifications: dict | None = None,
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    thinking_level: str = "disabled",
) -> tuple[str, list[GenerationResult]]:
    """Generate an ad using a library prompt template customized for your product.

    Returns (prompt_used, generation_results).
    """
    # Load the template
    library_prompt = load_prompt(prompt_id)

    # Get real product images
    product_urls = _get_product_image_urls(product, client_slug)

    # Claude customizes the template
    prompt = prompt_from_library(
        library_prompt=library_prompt,
        brand=brand,
        product=product,
        avatar=avatar,
        platform=platform,
        aspect_ratio=aspect_ratio,
        modifications=modifications,
    )

    # Use template's aspect ratio if not overridden
    final_ratio = aspect_ratio or (
        library_prompt.aspect_ratios[0] if library_prompt.aspect_ratios else "1:1"
    )

    # Generate with Nano Banana 2
    if output_dir is None:
        output_dir = _build_output_dir(client_slug, library_prompt.id)

    product_slug = product.name.lower().replace(" ", "-")
    results = generate_and_save(
        prompt=prompt,
        product_image_urls=product_urls,
        save_dir=output_dir,
        filename_prefix=f"{product_slug}_{library_prompt.id}",
        aspect_ratio=final_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    return prompt, results


# ─── Mode 3: "What would you recommend?" ────────────────────────────────────


def get_recommendations(
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    count: int = 10,
    platform: str = "meta",
) -> list[dict]:
    """Get prompt recommendations for a product. Does NOT generate images.

    Returns a ranked list of recommended prompt IDs with reasoning.
    Use generate_from_library() to actually generate images from a recommendation.
    """
    return recommend_prompts(
        brand=brand,
        product=product,
        avatar=avatar,
        count=count,
        product_type=product.category or None,
        platform=platform,
    )


# ─── Batch generation ────────────────────────────────────────────────────────


def generate_batch(
    prompt_ids: list[str],
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    platform: str = "meta",
    client_slug: str = "",
    num_images: int = 1,
) -> list[tuple[str, list[GenerationResult]]]:
    """Generate ads from multiple library prompts in sequence.

    Returns list of (prompt_used, results) tuples.
    """
    all_results = []
    for prompt_id in prompt_ids:
        prompt, results = generate_from_library(
            prompt_id=prompt_id,
            brand=brand,
            product=product,
            avatar=avatar,
            platform=platform,
            client_slug=client_slug,
            num_images=num_images,
        )
        all_results.append((prompt, results))
    return all_results


# ─── Mode 4: "Turn this brief into a finished ad image" ──────────────────────


def _classify_brief_style(brief: CreativeBrief) -> str:
    """Classify a brief as 'ugc' or 'editorial' based on visual format text.

    Used as a SECONDARY fallback when the ad-type category doesn't match
    any client ref folder. UGC signals: talking head, founder-to-camera,
    voice-note, UGC, kitchen, POV, mirror selfie, vertical reel, casual
    handheld. Editorial signals: everything else.

    Defaults to 'editorial' when ambiguous.
    """
    fmt = (brief.visual_format or "").lower()
    ugc_keywords = (
        "ugc", "talking head", "talking-head", "founder-to-camera",
        "founder to camera", "voice-note", "voice note", "kitchen",
        "pov", "mirror selfie", "handheld", "vertical reel", "selfie",
        "phone", "tiktok", "story",
    )
    if any(kw in fmt for kw in ugc_keywords):
        return "ugc"
    return "editorial"


# Canonical ad-type category → alternate folder names that should also match.
# Lets the same routing work whether the operator uses the swipe-library
# canonical naming ("features-and-benefits") or shorter user-friendly names
# ("features-benefits").
_CATEGORY_ALIASES: dict[str, list[str]] = {
    "us-vs-them": ["us-vs-them", "us-vs-them"],
    "testimonial-review": ["testimonial-review"],
    "before-and-after": ["before-and-after"],
    "features-and-benefits": ["features-and-benefits", "features-benefits", "reasons-why"],
    "facts-and-stats": ["facts-and-stats", "facts-stats"],
    "media-and-press": ["media-and-press", "media-press"],
    "promotion-and-discount": ["promotion-and-discount", "promotion-discount"],
    # New categories that don't exist in the swipe library — still resolve
    # if the brief hints at them.
    "headline": ["headline"],
    "ai-unique": ["ai-unique"],
}


def _classify_brief_category(brief: CreativeBrief) -> str:
    """Classify a brief into an ad-type category that maps to a client-refs
    subfolder. Reuses the swipe matcher's keyword logic for consistency.
    """
    # Lazy import to avoid circular issues
    from generators.swipe_matcher import pick_standard_folder
    return pick_standard_folder(brief.visual_format or "")


def _resolve_category_folder(
    base_dir: Path,
    canonical_category: str,
) -> str | None:
    """Given a canonical category like 'features-and-benefits', find which
    folder name exists under `base_dir`. Tries the canonical name plus any
    aliases. Returns the matched folder name or None.
    """
    aliases = _CATEGORY_ALIASES.get(canonical_category, [canonical_category])
    for alias in aliases:
        candidate = base_dir / alias
        if candidate.exists() and candidate.is_dir():
            # Only return if it has actual image files
            for p in candidate.iterdir():
                if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                    return alias
    return None


def _list_client_raw_files(raw_dir: Path, style: str | None) -> list[Path]:
    """Return raw reference image paths.

    Layout supported (priority order):
      1. style subfolder (`raw/<style>/*`) when `style` is provided —
         also tries category aliases so `features-benefits` matches when the
         brief routes to `features-and-benefits`
      2. flat layout (`raw/*`) — backwards-compatible with --local-dir flat mode
    """
    exts = {".png", ".jpg", ".jpeg", ".webp"}
    if not raw_dir.exists():
        return []

    # Try the style subfolder first (with alias resolution)
    if style:
        # Resolve canonical name → actual folder name (handles user's shorter naming)
        resolved = _resolve_category_folder(raw_dir, style) or style
        style_dir = raw_dir / resolved
        if style_dir.exists() and style_dir.is_dir():
            return sorted(
                p for p in style_dir.iterdir()
                if p.is_file() and p.suffix.lower() in exts
            )

    # Fallback: flat layout (files directly in raw/)
    return sorted(
        p for p in raw_dir.iterdir()
        if p.is_file() and p.suffix.lower() in exts
    )


def _collect_client_reference_ads(
    client_slug: str,
    max_refs: int = 3,
    style: str | None = None,
) -> tuple[list[str], str]:
    """Find SecondKind-specific reference ads (from --local-dir or Drive) and
    return (uploaded URLs, prompt-ready descriptive block).

    Priority is HIGHER than the generic swipe library — these are hand-picked
    by the operator for this exact brand, so they outrank generic DTC refs.

    When `style` is provided, prefers refs from `raw/<style>/` (e.g.,
    `raw/ugc/` for UGC briefs, `raw/editorial/` for editorial briefs).
    Falls back to flat `raw/` when no style subfolder exists.

    Returns (urls, block). Block is empty when no client refs exist; URLs is
    empty in that case too.
    """
    if not client_slug:
        return [], ""

    raw_dir = Path("clients") / client_slug / "reference_ads" / "raw"
    analyses_dir = Path("clients") / client_slug / "reference_ads" / "analyses"

    raw_files = _list_client_raw_files(raw_dir, style)
    if not raw_files:
        return [], ""

    # Cap at max_refs so we don't blow NB2's input budget on a huge folder
    chosen = raw_files[:max_refs]

    urls: list[str] = []
    for path in chosen:
        try:
            urls.append(upload_image(path))
        except Exception:
            continue

    # Build a labeled block describing the client refs. Pull each one's analysis
    # if available so Claude knows WHAT to take from them (mood, palette, composition).
    # Analysis layout mirrors raw/ layout: try `analyses/<style>/` first, fall back
    # to flat `analyses/`.
    import yaml as _yaml
    analysis_lines: list[str] = []
    for path in chosen:
        stem = path.stem[:60]
        candidate_paths = []
        if style:
            candidate_paths.append(analyses_dir / style / f"{stem}.yaml")
        candidate_paths.append(analyses_dir / f"{stem}.yaml")
        analysis_path = next((p for p in candidate_paths if p.exists()), None)
        if analysis_path is None:
            continue
        try:
            data = _yaml.safe_load(analysis_path.read_text(encoding="utf-8")) or {}
            a = data.get("analysis") or {}
            mood = a.get("mood") or []
            palette = a.get("color_palette_dominant") or []
            comp = a.get("composition_notes") or ""
            visual_format = a.get("visual_format") or ""
            label = path.name
            bits = []
            if visual_format:
                bits.append(f"format: {visual_format}")
            if mood:
                bits.append(f"mood: {', '.join(mood[:3])}")
            if palette:
                bits.append(f"palette: {', '.join(palette[:3])}")
            if comp:
                bits.append(f"composition: {comp[:120]}")
            analysis_lines.append(f"  - {label} — {' | '.join(bits)}")
        except Exception:
            continue

    style_label = f" ({style.upper()} style)" if style else ""
    block_lines = [
        f"CLIENT-SPECIFIC REFERENCE ADS{style_label} — HIGHEST PRIORITY STYLE TARGETS",
        f"({len(urls)} image(s) passed alongside the product image, IN ORDER, "
        f"directly after the product image).",
        "These are hand-picked by the operator as the AESTHETIC TARGET for this "
        "brand. Replicate their mood, photography style, environmental context, "
        "lighting, type treatment, polish level — but DO NOT copy the products "
        "shown in them. Outranks the generic swipe library references below.",
    ]
    if analysis_lines:
        block_lines.append("")
        block_lines.append("Per-reference structural notes:")
        block_lines.extend(analysis_lines)

    return urls, "\n".join(block_lines)


def _auto_pick_best_template(
    brief: CreativeBrief,
    client_slug: str,
) -> tuple[str, Path] | None:
    """Score every per-client template against the brief and return the
    single best match's (template_id, source_image_path). Returns None
    if no templates exist for the client or no usable match was found.

    Scoring:
      +20 if template category matches the brief's resolved category
      +10 if template's audience_fit includes the brief's awareness level
      +1  per overlapping tag-keyword between template.tags and brief text
    """
    if not client_slug:
        return None

    import yaml as _yaml

    templates_root = Path("clients") / client_slug / "templates"
    raw_root = Path("clients") / client_slug / "reference_ads" / "raw"
    if not templates_root.exists() or not raw_root.exists():
        return None

    brief_category = _classify_brief_category(brief)
    aliases = _CATEGORY_ALIASES.get(brief_category, [brief_category])
    awareness = brief.awareness_level.value if brief.awareness_level else ""

    # Build a bag of brief-relevant keywords for tag scoring
    brief_text = " ".join(filter(None, [
        brief.visual_format, brief.creative_mechanic, brief.angle,
        brief.hook_type, brief.hook_tactic,
    ])).lower()

    best: tuple[float, str, Path] | None = None
    for yaml_file in templates_root.rglob("*.yaml"):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                td = _yaml.safe_load(f) or {}
            if not td.get("template_prompt") or len(td["template_prompt"].strip()) < 50:
                continue

            score = 0.0
            template_cat = td.get("category", "")
            if template_cat in aliases or template_cat == brief_category:
                score += 20
            if awareness and awareness in (td.get("audience_fit") or []):
                score += 10
            for tag in (td.get("tags") or []):
                if tag.lower() in brief_text:
                    score += 1

            if score == 0:
                continue

            # Resolve the source image path
            category = yaml_file.parent.name
            stem = yaml_file.stem
            source_image = None
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = raw_root / category / f"{stem}{ext}"
                if candidate.exists():
                    source_image = candidate
                    break
            if source_image is None:
                continue

            if best is None or score > best[0]:
                best = (score, td["id"], source_image)
        except Exception:
            continue

    if best is None:
        return None
    _score, template_id, source_image = best
    return template_id, source_image


def generate_from_brief(
    brief: CreativeBrief,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    aspect_ratio: str | None = None,
    thinking_level: str = "disabled",
    use_references: bool = True,
    force_multi_ref: bool = False,
    creative_direction: str = "",
    offer: str = "NONE",
) -> tuple[str, list[GenerationResult]]:
    """Take a CreativeBrief, write the prompt with prompt_from_brief(), then
    generate the image(s) with Nano Banana 2 using the product's real images.

    When `use_references=True` (default), also:
      * Matches the brief to swipe library reference images (standard +
        psychology folders) and passes them to NB2 as STYLE refs.
      * Matches Cooper/Nanobana library templates by audience_fit and feeds
        their compositional skeletons into the prompt-writer's user prompt.

    The product image is ALWAYS position 0 in the image_urls list — NB2 is
    instructed in the system prompt to replicate image 1 exactly, and to
    treat any additional images as composition-only references.

    Returns (prompt_used, generation_results). Each GenerationResult has
    its local_path populated.
    """
    # ─── Auto single-pick mode ───
    # When client templates exist, default behavior is to pick the single best
    # template and run art-directed single-ref mode (no averaging). Set
    # `force_multi_ref=True` to override and use the legacy multi-reference
    # averaging behavior.
    # Build campaign_name eagerly so the prompt notes header includes it
    # and we can write a sidecar next to each generated image.
    if not getattr(brief, "campaign_name", ""):
        try:
            from strategy.naming import build_campaign_name
            brief.campaign_name = build_campaign_name(
                brief,
                brand,
                offer=offer,
                iteration=1,
                source="AI",
            )
        except (ValueError, Exception):
            # Brand.code missing or naming module error — leave empty.
            pass

    if use_references and not force_multi_ref and client_slug:
        auto_pick = _auto_pick_best_template(brief, client_slug)
        if auto_pick is not None:
            template_id, source_image = auto_pick
            return generate_from_brief_and_template(
                brief=brief,
                template_id=template_id,
                reference_image_path=source_image,
                brand=brand,
                product=product,
                avatar=avatar,
                client_slug=client_slug,
                output_dir=output_dir,
                num_images=num_images,
                aspect_ratio=aspect_ratio,
                thinking_level=thinking_level,
                creative_direction=creative_direction,
                offer=offer,
            )

    # ─── Multi-reference fallback (legacy behavior) ───
    product_urls = _get_product_image_urls(product, client_slug)

    if aspect_ratio is None:
        aspect_ratio = infer_aspect_ratio(brief)

    # ─── Build style references ───
    # Priority order (highest first):
    #   1. Product image (always position 0 — replicate exactly)
    #   2. Client-specific reference ads (hand-picked aesthetic targets)
    #   3. Generic swipe library (brand-agnostic ad-type + emotion refs)
    client_ref_urls: list[str] = []
    client_ref_block = ""
    swipe_block = ""
    library_examples = ""
    swipe_urls: list[str] = []

    if use_references:
        # Two-axis client-ref routing (priority order):
        #   1. AD-TYPE CATEGORY (us-vs-them, testimonial-review, features-and-
        #      benefits, etc.) — from the brief's visual_format. Highest
        #      fidelity because each category has a distinct composition.
        #   2. PRODUCTION STYLE (ugc vs editorial) — fallback when no
        #      ad-type folder matches or has content.
        brief_category = _classify_brief_category(brief)
        brief_style = _classify_brief_style(brief)

        # Try ad-type first
        ad_type_urls, ad_type_block = _collect_client_reference_ads(
            client_slug, max_refs=2, style=brief_category,
        )
        # Also pull 1 ref from style folder (editorial / ugc) — production style
        # is an orthogonal axis from ad-type, so we layer one of each.
        style_urls, _ = _collect_client_reference_ads(
            client_slug, max_refs=1, style=brief_style,
        )

        client_ref_urls = ad_type_urls + style_urls
        client_ref_block = ad_type_block  # the ad-type block carries the labeling

        # Fall back to style folder if ad-type didn't match at all
        if not client_ref_urls:
            client_ref_urls, client_ref_block = _collect_client_reference_ads(
                client_slug, max_refs=2, style=brief_style,
            )

        # Generic swipe library ONLY when we have no client refs. With a
        # curated client library in place, the generic 144-ad pool is noise.
        if not client_ref_urls:
            match = match_for_brief(
                visual_format=brief.visual_format,
                creative_mechanic=brief.creative_mechanic,
                seed=hash(brief.brief_id) % (2**32),  # stable per-brief seed
            )
            swipe_block = match.to_prompt_block()
            for path in match.all_images:
                try:
                    swipe_urls.append(upload_image(path))
                except Exception:
                    continue

        # Per-client templates (extracted via `adc extract-templates`) take
        # priority over Nanobana; Cooper is dropped entirely (include_cooper=False).
        library_examples = find_library_examples_for_brief(
            brief, max_examples=2, client_slug=client_slug,
        )

    # Combined reference block — clients first (priority signal to Claude)
    combined_block_parts = [b for b in (client_ref_block, swipe_block) if b]
    combined_swipe_block = "\n\n".join(combined_block_parts)

    # ─── Write the prompt ───
    prompt = prompt_from_brief(
        brief=brief,
        brand=brand,
        product=product,
        avatar=avatar,
        aspect_ratio=aspect_ratio,
        swipe_block=combined_swipe_block,
        library_examples=library_examples,
        creative_direction=creative_direction,
    )

    # ─── Generate ───
    if output_dir is None:
        output_dir = Path("ai-ads") / client_slug / "images"

    # Final image_urls = product first (position 0 = replicate exactly), then
    # client refs (highest-priority style targets), then swipe refs (generic
    # style refs). Order matters; the system prompt and combined_swipe_block
    # both depend on it.
    full_image_urls = product_urls + client_ref_urls + swipe_urls

    results = generate_and_save(
        prompt=prompt,
        product_image_urls=full_image_urls,
        save_dir=output_dir,
        filename_prefix=brief.brief_id,
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    # Write a sidecar <stem>_campaign.txt next to each generated image so
    # operators can copy/paste the full taxonomy name into Meta Ads Manager.
    _write_campaign_sidecars(results, getattr(brief, "campaign_name", ""))

    return prompt, results


def _write_campaign_sidecars(results: list[GenerationResult], campaign_name: str) -> None:
    """Write `<image_stem>_campaign.txt` next to each saved image.
    No-op if campaign_name is empty (e.g. brand.code missing)."""
    if not campaign_name:
        return
    for r in results:
        if r.local_path is None:
            continue
        sidecar = r.local_path.with_name(r.local_path.stem + "_campaign.txt")
        try:
            sidecar.write_text(campaign_name + "\n", encoding="utf-8")
        except OSError:
            pass


# ─── Single-reference, single-template mode (art-directed) ───────────────────


def generate_from_brief_and_template(
    brief: CreativeBrief,
    template_id: str,
    reference_image_path: Path,
    brand: Brand,
    product: Product,
    avatar: CustomerAvatar | None = None,
    client_slug: str = "",
    output_dir: Path | None = None,
    num_images: int = 1,
    aspect_ratio: str | None = None,
    thinking_level: str = "disabled",
    creative_direction: str = "",
    offer: str = "NONE",
) -> tuple[str, list[GenerationResult]]:
    """ART-DIRECTED generation: one brief + one extracted template + one
    reference image. No swipe library, no template averaging, no Nanobana
    aggregation — just the single hand-picked reference doing its job.

    The reference image is uploaded and passed to NB2 alongside the product
    image (positions 0 and 1 respectively). The template's `template_prompt`
    becomes the compositional backbone; brief content fills the placeholders.

    Returns (prompt_used, generation_results).
    """
    # Resolve the template by ID (search per-client templates first, then library)
    from models.library import load_prompt
    from pathlib import Path as _Path
    template = None
    if client_slug:
        client_templates_root = _Path("clients") / client_slug / "templates"
        for yaml_file in client_templates_root.rglob("*.yaml"):
            try:
                import yaml as _yaml
                with open(yaml_file, encoding="utf-8") as f:
                    data = _yaml.safe_load(f)
                if data and data.get("id") == template_id:
                    # Filter to LibraryPrompt fields (drop source_ad etc.)
                    from models.library import LibraryPrompt
                    allowed = LibraryPrompt.model_fields.keys()
                    data = {k: v for k, v in data.items() if k in allowed}
                    template = LibraryPrompt(**data)
                    break
            except Exception:
                continue
    if template is None:
        # Fallback to global library
        try:
            template = load_prompt(template_id)
        except FileNotFoundError:
            raise ValueError(
                f"Template '{template_id}' not found in client templates or global library."
            )

    if not reference_image_path.exists():
        raise FileNotFoundError(f"Reference image not found: {reference_image_path}")

    product_urls = _get_product_image_urls(product, client_slug)

    if aspect_ratio is None:
        aspect_ratio = infer_aspect_ratio(brief)

    # Upload the single reference image
    reference_url = upload_image(reference_image_path)

    # Write the prompt using the brief + template + reference combo.
    # Passing reference_image_path lets the prompt engine look up the
    # reference's on-image word count and target that text density.
    prompt = prompt_from_brief_and_template(
        brief=brief,
        template=template,
        brand=brand,
        product=product,
        avatar=avatar,
        aspect_ratio=aspect_ratio,
        reference_image_path=reference_image_path,
        client_slug=client_slug,
        creative_direction=creative_direction,
    )

    if output_dir is None:
        output_dir = Path("ai-ads") / client_slug / "images"

    # Exactly 2 images to NB2: [product, reference] — no aggregation
    image_urls = product_urls + [reference_url]

    # Build campaign_name if not already set
    if not getattr(brief, "campaign_name", ""):
        try:
            from strategy.naming import build_campaign_name
            brief.campaign_name = build_campaign_name(
                brief,
                brand,
                offer=offer,
                iteration=1,
                source="AI",
            )
        except (ValueError, Exception):
            pass

    results = generate_and_save(
        prompt=prompt,
        product_image_urls=image_urls,
        save_dir=output_dir,
        filename_prefix=f"{brief.brief_id}_ref_{template.id[:30]}",
        aspect_ratio=aspect_ratio,
        num_images=num_images,
        thinking_level=thinking_level,
    )

    _write_campaign_sidecars(results, getattr(brief, "campaign_name", ""))

    return prompt, results
