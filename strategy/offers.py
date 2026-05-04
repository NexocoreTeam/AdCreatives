"""Stage 3 — offers extraction + AI-suggested offers.

Two halves in one stage:
1. Crawl the brand's site for offers already running (announcement bar,
   FAQ, shipping/returns policy pages, product subscription widgets).
2. LLM-generate suggested offers tailored to this specific brand using
   established direct-response offer-engineering frameworks (value
   equation, offer stack, guarantees, urgency, premium positioning).

Output: clients/<slug>/offers.yaml — structured for downstream brief
generation to use in CTAs and as testing roadmap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

import httpx
import yaml

from models.brand import Brand
from models.avatar import CustomerAvatar
from models.product import Product
from strategy.llm import claude_complete
from strategy.researcher import (
    USER_AGENT,
    MAX_HTML_PER_PAGE,
    clean_html,
    normalize_url,
)


@dataclass
class OffersResult:
    existing_offers: list[dict]
    suggested_offers: list[dict]
    notes: dict


# Pages that commonly carry offer language on DTC ecommerce sites.
OFFER_CANDIDATE_PATHS = [
    "/pages/faq",
    "/pages/shipping",
    "/pages/returns",
    "/pages/refund-policy",
    "/pages/shipping-policy",
    "/pages/return-policy",
    "/policies/refund-policy",
    "/policies/shipping-policy",
    "/policies/return-policy",
    "/policies/terms-of-service",
    "/pages/subscribe",
    "/pages/subscription",
    "/pages/wholesale",
    "/pages/rewards",
    "/pages/refer-a-friend",
]


def fetch_offer_pages(base_url: str) -> dict[str, str]:
    """Fetch pages that commonly carry offer language."""
    base_url = normalize_url(base_url)
    results: dict[str, str] = {}
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        for path in OFFER_CANDIDATE_PATHS:
            url = urljoin(base_url + "/", path.lstrip("/"))
            try:
                resp = client.get(url)
            except (httpx.RequestError, httpx.TimeoutException):
                continue
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type.lower():
                continue
            cleaned = clean_html(resp.text)[:MAX_HTML_PER_PAGE]
            if cleaned:
                results[url] = cleaned
    return results


OFFERS_SYSTEM = """You are a direct-response offer architect for ecommerce
DTC brands. You operate in two modes simultaneously:

1. EXTRACTION — pull every offer that's already running on the brand's site
   from the pages provided (announcement bars, FAQs, policies, popups,
   subscription widgets, free shipping thresholds, refund guarantees).
2. SUGGESTION — propose new offers tailored to this brand using established
   offer-engineering principles. Apply the value equation explicitly:

   Value = (Dream Outcome × Perceived Likelihood) / (Time Delay × Effort)

   Increase value by:
   - Bigger dream outcome (specific, vivid)
   - Higher perceived likelihood (proof, guarantees, case studies, reviews)
   - Lower time delay (faster results, instant delivery, immediate gratification)
   - Lower effort (done-for-you, simplified setup, removed friction)

   Use the offer hierarchy: hook (lead magnet/trial) → core (the main thing)
   → upsell (premium tier) → continuity (subscription/membership).

Output rules:
- Every existing offer must cite where_found (which page).
- Every suggested offer must explain rationale grounded in this brand's
  context (founder story, audience pain, category dynamics, ICP).
- Never suggest discounts that would erode brand premium positioning.
- Be specific to the brand's ecommerce reality — these are physical
  products with shipping costs, made-to-order timelines, etc.
- Output YAML only, no markdown fences."""


def build_offers(
    brand: Brand,
    avatars: list[CustomerAvatar],
    products: list[Product],
    offer_pages: dict[str, str],
    homepage_html: str = "",
    brand_context_md: str = "",
) -> OffersResult:
    """Extract existing offers from crawled pages + suggest new ones."""

    pages_text = "\n\n".join(
        f"=== PAGE: {url} ===\n{html[:30000]}"
        for url, html in offer_pages.items()
    )
    if homepage_html:
        pages_text = (
            f"=== HOMEPAGE (announcement bar / footer / popups) ===\n{homepage_html[:20000]}\n\n"
            + pages_text
        )

    persona_summary = ""
    for av in avatars[:3]:
        objections = ", ".join(av.objections[:3])
        persona_summary += (
            f"- {av.name or 'Persona'} ({av.awareness_level}): "
            f"top objections — {objections}\n"
        )

    products_summary = "\n".join(
        f"- {p.name}: {p.description[:160]}" for p in products[:5]
    )

    prompt = f"""Build the offers document for {brand.name}.

BRAND:
  Name: {brand.name}
  Tone: {brand.tone}
  Mission: {getattr(brand, 'mission', '') or '(not specified)'}
  Tagline: {getattr(brand, 'tagline', '') or '(not specified)'}

PERSONAS:
{persona_summary or '(no personas defined yet)'}

PRODUCTS:
{products_summary or '(no products defined)'}

BRAND CONTEXT (excerpt):
{brand_context_md[:6000]}

PAGES CRAWLED FOR EXISTING OFFERS:
{pages_text or '(no pages fetched — extraction will rely on brand-context excerpts only)'}

---

PART 1 — EXTRACT EXISTING OFFERS

Find every concrete offer currently running on the brand's site. Examples
include: free shipping thresholds, subscribe-and-save, refund/satisfaction
guarantees, refer-a-friend, holiday/seasonal promos, made-to-order policies,
return windows, trial offers, BOGO, military/student discounts.

PART 2 — SUGGEST NEW OFFERS

Generate 4-7 offer ideas tailored to this specific brand. Use the value
equation framework. Each must address a real persona objection or amplify
a real desire. Vary the type: lead-magnet/trial, core product offer,
bundle/upsell, subscription, seasonal, win-back.

Return YAML matching this exact schema (no markdown fences):

existing_offers:
  - name: "Short offer name (e.g. 'Free shipping at $125+')"
    type: "shipping_threshold | subscription | refund_guarantee | refer_a_friend | seasonal_promo | made_to_order_policy | wholesale | trial | bundle | other"
    details: "Concrete details — exact thresholds, percentages, durations"
    where_found: "URL or 'homepage announcement bar' / 'FAQ' / etc."
    on_brand: true | false  # is this offer aligned with brand voice?
    notes: "Anything strategic worth flagging"

suggested_offers:
  - name: "Specific offer name (e.g. 'Boy Mama Matching Bundle')"
    type: "lead_magnet | trial | core | bundle | upsell | subscription | seasonal | winback | refer_a_friend"
    rationale: "Why this offer fits THIS brand AND THIS audience — reference specific pain, persona, or product"
    target_persona: "primary | secondary | tertiary | all"
    target_awareness_stage: "unaware | problem_aware | solution_aware | product_aware | most_aware"
    value_equation:
      dream_outcome: "What customer ultimately wants (concrete outcome)"
      perceived_likelihood_lever: "What proof/guarantee makes it believable"
      time_delay_lever: "How this offer makes results faster"
      effort_lever: "How this offer reduces friction"
    suggested_structure: "Concrete mechanic — e.g. 'Buy mom tee + kid tee, get $X off' or 'First box ships in 7 days vs standard 14 with priority option'"
    risk_reversal: "Money-back, replacement, or other guarantee that removes risk"
    urgency_mechanic: "Time-limited, quantity-limited, or seasonal trigger (only if genuinely justifiable)"
    pricing_anchor_logic: "How to frame price (vs competitors, vs cost-of-doing-nothing, vs perceived value)"
    estimated_lift: "low | medium | high"
    creative_angle: "1-2 sentence hook angle this offer unlocks for ad creative"
    notes: "Edge cases, brand-fit considerations, regulatory flags"

notes:
  brand_premium_constraints: "What offer types would erode this brand's premium positioning"
  category_dynamics: "How this product category typically structures offers (e.g., apparel = seasonal, supplements = subscription, food = trial sizes)"
  highest_priority_test: "Which suggested offer to test first and why"
  audience_specific_recommendations: "How offer mix should differ by persona"

Quality checks:
1. Every existing_offer must cite where_found.
2. Every suggested_offer must reference a real persona objection or desire.
3. Suggestions must NOT be generic (no '10% off first order' unless that's the only fit).
4. value_equation fields must be specific, not boilerplate.

Output YAML only. No markdown fences."""

    raw = claude_complete(prompt, system=OFFERS_SYSTEM, max_tokens=10000)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]

    data = yaml.safe_load(raw) or {}
    return OffersResult(
        existing_offers=data.get("existing_offers", []) or [],
        suggested_offers=data.get("suggested_offers", []) or [],
        notes=data.get("notes", {}) or {},
    )


def save_offers(client_slug: str, result: OffersResult) -> Path:
    """Persist the offers document."""
    path = Path("clients") / client_slug / "offers.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "existing_offers": result.existing_offers,
        "suggested_offers": result.suggested_offers,
        "notes": result.notes,
    }
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    return path
