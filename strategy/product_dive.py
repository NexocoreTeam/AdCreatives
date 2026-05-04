"""Stage 4 — product deep-dive.

Takes a product YAML stub (created during research) and enriches it by
fetching the product detail page and running motion/review-audit on the
on-page reviews/testimonials. Populates: benefits (functional/emotional/
social), unique_mechanism, price, objections, social_proof, and verbatim
customer-language quotes ready for the brief generator.

System context layers:
- motion/review-audit — review extraction methodology
- coreyhaines/customer-research — JTBD framework
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from models.brand import Brand
from models.product import Product
from models.skills import load_skill
from strategy.llm import claude_complete
from strategy.researcher import fetch_product_pages_with_raw
from strategy.reviews import (
    Review,
    VendorSignal,
    fetch_product_reviews,
    filter_reviews_by_product,
    save_reviews_as_voc,
)


PRODUCT_DIVE_SYSTEM = """You are an ecommerce product strategist. Your job is
to take a product detail page (HTML) and extract everything ad creative
needs: functional/emotional/social benefits, unique mechanism, real prices,
objections customers express, social proof (review quotes, ratings, badges),
and verbatim customer language ready to use as ad copy.

You operate under TWO layered skills:
- motion/review-audit — 5-tier review quality scoring + 5 insight buckets
- coreyhaines/customer-research — JTBD framework + confidence scoring

Apply review-audit's quality scoring to any reviews you find on the page:
score 1 = noise, score 4-5 = gold. Only pull customer language from 4s and 5s.

--- REVIEW AUDIT ---

""" + load_skill("motion/review-audit") + """

--- CUSTOMER RESEARCH ---

""" + load_skill("customer-research") + """

---

Output rules:
- Benefits split into functional / emotional / social (per JTBD framework).
- unique_mechanism explains WHY this product works in 1-2 sentences, in
  the brand's language.
- Customer language quotes must be verbatim from page reviews if present;
  if no reviews are visible, return empty list (do not fabricate).
- Price must be exact if visible on page.
- Output YAML only, no markdown fences."""


@dataclass
class ProductDiveResult:
    enriched: dict


def enrich_product(
    brand: Brand,
    product: Product,
    page_html: str,
    fetched_reviews: list[Review] | None = None,
) -> ProductDiveResult:
    """Run an LLM extraction on a product detail page to enrich the product YAML.

    If `fetched_reviews` is provided (from a vendor API like Okendo/Yotpo), the
    review text is appended to the prompt so the LLM can extract real verbatim
    customer language instead of trying to scrape it from the JS-rendered page.
    """
    reviews_text = ""
    if fetched_reviews:
        # Pass the top 30 reviews — enough volume for review-audit to work,
        # bounded for prompt size
        sampled = fetched_reviews[:30]
        rows = []
        for r in sampled:
            if not r.body:
                continue
            rows.append(
                f"Rating: {r.rating}/5 | Title: {r.title} | "
                f"Reviewer: {r.reviewer} | Product: {r.product_name}\n"
                f"  {r.body}"
            )
        reviews_text = (
            f"\n\nREAL REVIEWS FETCHED FROM REVIEW-WIDGET API "
            f"({len(sampled)} reviews):\n"
            + "\n\n".join(rows)
            + "\n\nApply motion/review-audit's 5-tier quality scoring. Pull "
            "verbatim quotes from 4-5s only. Use the review_count to ground the "
            "ratings_and_reviews_meta block."
        )

    prompt = f"""Extract structured product data from this product detail page
for {brand.name}'s "{product.name}".

CURRENT KNOWN DATA:
  name: {product.name}
  description: {product.description}
  url: {product.url or '(not specified)'}

BRAND CONTEXT:
  tone: {brand.tone}
  tagline: {getattr(brand, 'tagline', '') or '(not specified)'}
  mission: {getattr(brand, 'mission', '') or '(not specified)'}

PRODUCT PAGE HTML (cleaned):
{page_html[:35000]}
{reviews_text}

---

Return YAML matching this exact schema (no markdown fences):

price: "Exact price as displayed on page (e.g. '$28' or '$28-$44'). 'unknown' if not present."

benefits:
  functional:
    - "Concrete capability/spec the product delivers (e.g. '13g protein', 'made in NC', 'fits sizes infant-4XL')"
  emotional:
    - "How it makes the customer feel (e.g. 'feel like a kid again on Saturday morning')"
  social:
    - "How it makes them appear to others (e.g. 'support woman-owned business', 'be the proud boy mama')"

unique_mechanism: "1-2 sentences explaining WHY this product works the way it does — the proprietary thing, the founder's insight, the formulation/design that makes it different. Use the brand's language where possible."

materials_or_ingredients:
  - "Materials/ingredients listed on page"

shipping_and_fulfillment:
  - "Lead time, shipping options, made-to-order vs in-stock notes from page"

objections_addressed_on_page:
  - "Each objection the page proactively addresses (often in FAQ section)"

social_proof:
  - quote: "Verbatim review or testimonial from page"
    review_score: 1-5  # motion/review-audit quality score
    why_it_matters: "Why this quote is useful for ad copy"

customer_language_quotes:
  - "Verbatim customer phrases that could be repurposed in ad copy"

ratings_and_reviews_meta:
  star_rating: "e.g. '4.8 / 5' — empty if no rating visible"
  review_count: "e.g. '847 reviews' — empty if not present"
  review_widget: "Yotpo / Judge.me / Stamped / Loox / Shopify Reviews / unknown"

guarantees:
  - "Refund/satisfaction guarantee language found on page"

cross_sells_or_bundles:
  - "Other products this page links to or bundles with"

extraction_confidence: "high | medium | low — how confidently this page yielded structured data"

extraction_notes: "Any caveats, gaps, or things worth flagging — e.g. 'no reviews visible on page, may be loaded dynamically'"

Quality checks:
1. Never fabricate review quotes. If no reviews visible, return empty list.
2. Benefits must be split correctly into functional/emotional/social.
3. unique_mechanism must be specific to THIS product, not generic.
4. Include the brand's actual language where possible (e.g. their exact ingredient terms, framing).

Output YAML only. No markdown fences."""

    raw = claude_complete(prompt, system=PRODUCT_DIVE_SYSTEM, max_tokens=6000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    data = yaml.safe_load(raw) or {}
    return ProductDiveResult(enriched=data)


def merge_enrichment_into_product(product: Product, enriched: dict) -> dict:
    """Merge enriched fields back into the product YAML structure.

    Returns a dict ready to write back to clients/<slug>/products/<id>.yaml.
    Preserves all existing product fields; only fills in empty/missing ones
    or appends to existing lists.
    """
    product_dict = product.model_dump(mode="json")

    # Price: replace 'unknown' / empty / None with extracted price
    extracted_price = enriched.get("price")
    if extracted_price and extracted_price.lower() != "unknown":
        if not product_dict.get("price") or str(product_dict["price"]).lower() in ("unknown", "none", ""):
            product_dict["price"] = extracted_price

    # Benefits: flatten functional + emotional + social into existing list, dedup
    benefits_block = enriched.get("benefits", {}) or {}
    flat_benefits: list[str] = []
    for category in ("functional", "emotional", "social"):
        for b in benefits_block.get(category, []) or []:
            if b:
                flat_benefits.append(f"[{category}] {b}")
    if flat_benefits:
        existing = product_dict.get("benefits") or []
        seen = {b.lower() for b in existing}
        for b in flat_benefits:
            if b.lower() not in seen:
                existing.append(b)
        product_dict["benefits"] = existing

    # Unique mechanism: only fill if empty
    if enriched.get("unique_mechanism") and not product_dict.get("unique_mechanism"):
        product_dict["unique_mechanism"] = enriched["unique_mechanism"]

    # Objections: extend
    new_objections = enriched.get("objections_addressed_on_page") or []
    if new_objections:
        existing = product_dict.get("objections") or []
        seen = {o.lower() for o in existing}
        for o in new_objections:
            if o and o.lower() not in seen:
                existing.append(o)
        product_dict["objections"] = existing

    # Social proof: take review quotes (score 4+) and append
    new_proof = []
    for sp in enriched.get("social_proof", []) or []:
        if isinstance(sp, dict):
            score = sp.get("review_score")
            if score is None or (isinstance(score, (int, float)) and score >= 3):
                quote = sp.get("quote", "")
                if quote:
                    new_proof.append(quote)
    if new_proof:
        existing = product_dict.get("social_proof") or []
        seen = {p.lower() for p in existing}
        for p in new_proof:
            if p.lower() not in seen:
                existing.append(p)
        product_dict["social_proof"] = existing

    # Stash enrichment-only fields under product_characteristics so they
    # survive the round-trip without bloating the canonical Product schema
    chars = product_dict.get("product_characteristics") or {}
    chars["materials_or_ingredients"] = enriched.get("materials_or_ingredients") or []
    chars["shipping_and_fulfillment"] = enriched.get("shipping_and_fulfillment") or []
    chars["ratings_and_reviews_meta"] = enriched.get("ratings_and_reviews_meta") or {}
    chars["guarantees"] = enriched.get("guarantees") or []
    chars["cross_sells_or_bundles"] = enriched.get("cross_sells_or_bundles") or []
    chars["customer_language_quotes"] = enriched.get("customer_language_quotes") or []
    chars["extraction_confidence"] = enriched.get("extraction_confidence", "medium")
    chars["extraction_notes"] = enriched.get("extraction_notes", "")
    product_dict["product_characteristics"] = chars

    return product_dict


def deep_dive_products(
    client_slug: str,
    brand: Brand,
    products: list[Product],
) -> dict[str, dict]:
    """Run deep-dive on each product, write enriched YAMLs back.

    For each product:
    1. Fetch the product detail page HTML
    2. Detect the review-widget vendor and pull real reviews from its public API
    3. Pass HTML + real reviews to the LLM with motion/review-audit guidance
    4. Save raw reviews to clients/<slug>/voc/<vendor>-reviews.json (mine-voc compatible)
    5. Merge enrichment back into the product YAML

    Returns a map of {product_name: extraction_summary} for CLI display.
    """
    if not products:
        return {}

    urls = [p.url for p in products if p.url]
    if not urls:
        return {}

    pages = fetch_product_pages_with_raw(urls)
    summary: dict[str, dict] = {}

    # Fetch reviews ONCE per detected vendor — for store-level vendors (Okendo)
    # one call returns reviews across all products. For per-product vendors
    # (Yotpo, Judge.me) we'll need one call per product.
    cached_reviews_by_vendor: dict[str, list[Review]] = {}
    cached_signal_by_vendor: dict[str, VendorSignal] = {}

    for product in products:
        if not product.url or product.url not in pages:
            summary[product.name] = {"status": "skipped", "reason": "no URL or fetch failed"}
            continue

        raw_html = pages[product.url]["raw"]
        cleaned_html = pages[product.url]["cleaned"]

        # Pull vendor reviews — cache by vendor since store-level endpoints
        # (Okendo) return reviews across all products in one call
        product_reviews: list[Review] = []
        signal: VendorSignal | None = None
        try:
            from urllib.parse import urlparse
            base_url = f"{urlparse(product.url).scheme}://{urlparse(product.url).netloc}"
            cache_key = None
            from strategy.reviews import detect_review_vendor
            preliminary_signal = detect_review_vendor(raw_html)  # raw — has scripts
            if preliminary_signal.vendor == "okendo":
                cache_key = f"okendo:{preliminary_signal.identifiers.get('subscriber_id', '')}"
            if cache_key and cache_key in cached_reviews_by_vendor:
                all_reviews = cached_reviews_by_vendor[cache_key]
                signal = cached_signal_by_vendor[cache_key]
            else:
                all_reviews, signal = fetch_product_reviews(
                    html=raw_html,  # raw HTML so identifiers in <script> survive
                    product_url=product.url,
                    base_url=base_url,
                )
                if cache_key:
                    cached_reviews_by_vendor[cache_key] = all_reviews
                    cached_signal_by_vendor[cache_key] = signal

            product_reviews = (
                filter_reviews_by_product(all_reviews, product.name)
                if all_reviews
                else []
            )
        except Exception as e:
            import sys
            print(f"[reviews fetch error for {product.name}: {type(e).__name__}: {str(e)[:200]}]", file=sys.stderr)
            signal = None

        result = enrich_product(
            brand=brand,
            product=product,
            page_html=cleaned_html,  # cleaned for LLM prompt size
            fetched_reviews=product_reviews,
        )
        merged = merge_enrichment_into_product(product, result.enriched)

        # Save raw reviews to voc/ so mine-voc can use them too
        if product_reviews and signal:
            try:
                save_reviews_as_voc(client_slug, signal.vendor, product_reviews)
            except Exception:
                pass

        # Write back to disk
        from models.loader import CLIENTS_DIR
        slug = _filename_slug(product.name)
        path = CLIENTS_DIR / client_slug / "products" / f"{slug}.yaml"
        if not path.exists():
            # Find the existing product file by matching name
            for existing_path in (CLIENTS_DIR / client_slug / "products").glob("*.yaml"):
                with open(existing_path, encoding="utf-8") as f:
                    existing_data = yaml.safe_load(f) or {}
                if existing_data.get("name") == product.name:
                    path = existing_path
                    break

        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(merged, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        summary[product.name] = {
            "status": "enriched",
            "path": str(path),
            "price": merged.get("price"),
            "benefit_count": len(merged.get("benefits") or []),
            "social_proof_count": len(merged.get("social_proof") or []),
            "confidence": result.enriched.get("extraction_confidence", "medium"),
            "reviews_fetched": len(product_reviews),
            "review_vendor": signal.vendor if signal else "none",
        }

    return summary


def _filename_slug(name: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "untitled"
