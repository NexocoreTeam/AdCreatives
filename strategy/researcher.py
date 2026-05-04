"""Brand research agent — interview-first flow.

Implements Motion's brand-intake methodology:
1. Interview the user with batched seed questions
2. Fetch the brand's website (homepage + standard sub-pages)
3. For Shopify sites, fetch best-sellers (3 pages) for true product priority
4. Use GPT-4o vision on the logo to extract real brand colors
5. Combine seed + scraped data + bestsellers + vision colors to produce
   a comprehensive brand-context.md AND structured YAML data

System context comes from prompts/skills/motion/brand-intake.md (MIT, by
Alysha at Motion). The HTTP fetcher, Shopify best-sellers, vision color
extraction, and structured-data parsing are original to AdCreatives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from models.skills import load_skill
from strategy.llm import claude_complete, claude_vision, gemini_vision

CANDIDATE_PATHS = [
    "/",
    "/about",
    "/about-us",
    "/pages/about",
    "/pages/our-story",
    "/our-story",
    "/story",
    "/collections/all",
    "/products",
    "/shop",
    "/press",
    "/pages/press",
    "/faq",
    "/pages/faq",
    "/how-it-works",
    "/pages/how-it-works",
]

USER_AGENT = (
    "Mozilla/5.0 (compatible; AdCreatives-Research/0.1; "
    "+https://github.com/NexocoreTeam/AdCreatives)"
)

MAX_HTML_PER_PAGE = 50_000
MAX_TOTAL_HTML = 200_000


# The 6 intake questions adapted from Motion's brand-intake (brand name +
# URL come from CLI flags, so we don't ask them again).
INTAKE_QUESTIONS = [
    {
        "key": "products",
        "prompt": "What product(s) are you running paid ads for? List them, or say 'all'.",
        "default": "all",
    },
    {
        "key": "focus",
        "prompt": "Should this context focus on a specific product/line, or the full brand?",
        "default": "full brand",
    },
    {
        "key": "known_audience",
        "prompt": "What do you already know about the audience? (age, gender, lifestyle, pain points, values — any/all)",
        "default": "",
    },
    {
        "key": "competitors",
        "prompt": "Who are the main competitors? (or 'I don't know' / 'skip')",
        "default": "",
    },
    {
        "key": "constraints",
        "prompt": "Any brand constraints? (e.g., can't make health claims, family-friendly tone, regulated category)",
        "default": "",
    },
    {
        "key": "existing_creative",
        "prompt": "Any existing creative or messaging from the brand to keep in mind? (or 'skip')",
        "default": "",
    },
]


@dataclass
class BrandIntakeResult:
    brand_context_md: str
    data: dict
    is_shopify: bool = False
    logo_url: str | None = None
    visual_identity: dict | None = None
    bestseller_count: int = 0


@dataclass
class ProductCard:
    name: str
    url: str
    image_url: str | None = None
    price: str | None = None
    rank: int = 0  # rank in best-sellers (1 = top)


def normalize_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def clean_html(html: str) -> str:
    html = re.sub(r"<script\b[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style\b[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"\s+", " ", html)
    return html.strip()


def fetch_pages(base_url: str, paths: list[str] | None = None) -> dict[str, str]:
    base_url = normalize_url(base_url)
    paths = paths or CANDIDATE_PATHS
    results: dict[str, str] = {}
    total_chars = 0
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        for path in paths:
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
            if not cleaned:
                continue
            results[url] = cleaned
            total_chars += len(cleaned)
            if total_chars >= MAX_TOTAL_HTML:
                break
    return results


def discover_product_urls(homepage_html: str, base_url: str, limit: int = 20) -> list[str]:
    base_url = normalize_url(base_url)
    matches = re.findall(r'href=["\']([^"\']*?/products/[^"\']+?)["\']', homepage_html)
    seen = set()
    urls = []
    for href in matches:
        full = urljoin(base_url + "/", href)
        if full not in seen and urlparse(full).netloc == urlparse(base_url).netloc:
            seen.add(full)
            urls.append(full)
    return urls[:limit]


def is_shopify_site(html: str) -> bool:
    """Detect if a page is served by Shopify."""
    indicators = ["cdn.shopify.com", "/cdn/shop/", "Shopify.theme", "shopify-section"]
    return any(ind in html for ind in indicators)


BESTSELLER_HTML_LIMIT = 600_000  # bestseller pages need more — product grid sits after huge nav


def fetch_shopify_bestsellers(base_url: str, page_count: int = 3) -> list[tuple[str, str]]:
    """Fetch the first N pages of `/collections/all?sort_by=best-selling`.

    Returns list of (url, cleaned_html) for each page that returned 200.
    Uses a much larger HTML budget than fetch_pages because Shopify nav menus
    eat the first ~10-50k chars before any product cards appear.
    """
    base_url = normalize_url(base_url)
    pages: list[tuple[str, str]] = []
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    with httpx.Client(timeout=20.0, follow_redirects=True, headers=headers) as client:
        for page in range(1, page_count + 1):
            url = f"{base_url}/collections/all?sort_by=best-selling&page={page}"
            try:
                resp = client.get(url)
            except (httpx.RequestError, httpx.TimeoutException):
                continue
            if resp.status_code != 200:
                continue
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type.lower():
                continue
            cleaned = clean_html(resp.text)[:BESTSELLER_HTML_LIMIT]
            if cleaned:
                pages.append((url, cleaned))
    return pages


# Match both relative ("/products/...") and absolute ("https://x.com/products/...") hrefs
_PRODUCT_HREF = re.compile(
    r'href=["\'](?:https?://[^"\'/]+)?(/products/[a-z0-9][a-z0-9_-]*)(?:[?#][^"\']*)?["\']',
    re.IGNORECASE,
)


def parse_shopify_product_cards(html: str, base_url: str) -> list[ProductCard]:
    """Extract product cards from a Shopify collection page.

    Strategy: find every unique /products/<slug> href in document order, then
    pull a name (preferring img alt text from later in the page) and a price
    (preferring the price closest to the product link).
    """
    base_url = normalize_url(base_url)
    cards: list[ProductCard] = []
    seen_slugs: set[str] = set()

    # Find product links in order
    href_matches = list(_PRODUCT_HREF.finditer(html))

    # Build a map of slug → (path, position)
    for match in href_matches:
        path = match.group(1)
        slug = path.split("/")[-1]
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        full_url = urljoin(base_url + "/", path.lstrip("/"))

        # Try to find the product name from the surrounding ~800 chars
        # (img alt text or a heading inside a card link)
        ctx_start = match.start()
        ctx_end = min(len(html), match.end() + 1500)
        context = html[ctx_start:ctx_end]

        name = ""
        # Prefer img alt that starts with the slug-derived name OR is a real product name
        for alt_pattern in [
            r'alt=["\']([A-Z][^"\']{4,80})["\']',  # capitalized = product name
            r'class=["\'][^"\']*(?:card__heading|product-card-title|product-title)[^"\']*["\'][^>]*>\s*(?:<[^>]+>)*\s*([^<]{3,100})',
        ]:
            m = re.search(alt_pattern, context, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                break

        if not name:
            name = slug.replace("-", " ").title()

        # Find an image url in the context
        img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', context, re.IGNORECASE)
        image_url = img_match.group(1) if img_match else None
        if image_url and image_url.startswith("//"):
            image_url = "https:" + image_url

        # Find a price token in the context
        price_match = re.search(r"\$\s?(\d{1,4}(?:\.\d{2})?)", context)
        price = f"${price_match.group(1)}" if price_match else None

        cards.append(
            ProductCard(
                name=name,
                url=full_url,
                image_url=image_url,
                price=price,
                rank=len(cards) + 1,
            )
        )

    return cards


def find_logo_url(html: str, base_url: str) -> str | None:
    """Heuristic logo URL extraction from a homepage.

    Tries: <img class*=logo>, <img alt*=logo>, apple-touch-icon, og:image.
    Decodes HTML entities (&amp; → &) so the URL is fetcher-safe.
    """
    import html as _html_lib

    base_url = normalize_url(base_url)
    patterns = [
        r'<img[^>]+class=["\'][^"\']*logo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]+class=["\'][^"\']*logo[^"\']*["\']',
        r'<img[^>]+alt=["\'][^"\']*[Ll]ogo[^"\']*["\'][^>]+src=["\']([^"\']+)["\']',
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]+alt=["\'][^"\']*[Ll]ogo[^"\']*["\']',
        r'<link[^>]+rel=["\']apple-touch-icon["\'][^>]+href=["\']([^"\']+)["\']',
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            url = _html_lib.unescape(match.group(1))
            if url.startswith("//"):
                url = "https:" + url
            elif url.startswith("/"):
                url = urljoin(base_url, url)
            elif not url.startswith("http"):
                url = urljoin(base_url + "/", url)
            return url
    return None


def discover_visual_identity_images(homepage_html: str, base_url: str, bestsellers: list[ProductCard] | None = None, max_images: int = 5) -> list[str]:
    """Pick the best images for visual-identity analysis, ordered by signal strength.

    Order matters because the Claude single-image fallback only uses image[0]:
    1. Top product hero shot (shows packaging design language — strongest signal)
    2. 2-3 more product shots from bestsellers (shows range)
    3. Logo (shows typography + mascot)
    4. og:image (lifestyle/hero fallback)
    """
    images: list[str] = []

    if bestsellers:
        for card in bestsellers[:6]:
            if card.image_url and card.image_url not in images:
                images.append(card.image_url)
                if len(images) >= max_images - 1:
                    break

    logo = find_logo_url(homepage_html, base_url)
    if logo and logo not in images:
        images.append(logo)

    if len(images) < max_images:
        og_match = re.search(
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            homepage_html,
            re.IGNORECASE,
        )
        if og_match:
            import html as _html_lib
            og = _html_lib.unescape(og_match.group(1))
            if og.startswith("//"):
                og = "https:" + og
            elif og.startswith("/"):
                og = urljoin(normalize_url(base_url), og)
            if og not in images:
                images.append(og)

    return images[:max_images]


def _validate_image_urls(urls: list[str], timeout: float = 5.0) -> list[str]:
    """Filter out URLs that 404 or fail to fetch — Gemini multi-image fails
    the whole batch if even one URL is bad."""
    headers = {"User-Agent": USER_AGENT}
    valid: list[str] = []
    with httpx.Client(timeout=timeout, follow_redirects=True, headers=headers) as client:
        for url in urls:
            try:
                resp = client.head(url)
                if resp.status_code == 405:
                    # Some servers reject HEAD; try a short GET
                    resp = client.get(url, headers={**headers, "Range": "bytes=0-0"})
                if 200 <= resp.status_code < 400:
                    valid.append(url)
            except (httpx.RequestError, httpx.TimeoutException):
                continue
    return valid


def extract_visual_identity(image_urls: list[str]) -> dict | None:
    """Use Gemini 2.5 Pro (via OpenRouter) on multiple brand images to
    extract a structured visual identity description.

    This replaces the old brand-color extraction. Visual identity (aesthetic,
    photography style, design language, mood) is far more useful for ad
    generation than raw hex codes.

    Falls back to Claude Sonnet 4.6 vision on a single image if OpenRouter
    isn't configured.
    """
    if not image_urls:
        return None

    # Drop any URLs that 404 — Gemini multi-image fails the whole batch on one bad URL.
    image_urls = _validate_image_urls(image_urls)
    if not image_urls:
        return None

    prompt = """Examine these brand images (logo, products, hero shots) and describe
the BRAND'S VISUAL IDENTITY — what a creative strategist would document so a
designer or AI image model could produce on-brand creative.

Return YAML only (no markdown fences) with this exact structure:

aesthetic: "1-2 sentence overall vibe — what does this brand FEEL like visually?"
photography_style: "Is it studio? Lifestyle UGC? Editorial? Flat lay? Mixed?"
design_language: "Minimalist, maximalist, retro, cartoon, editorial, brutalist, etc."
typography_feel: "Modern sans, handwritten, retro display, classic serif, hand-lettered, etc."
mascot_or_character: "Describe any mascots/characters, or 'none'"
visual_references:
  - "Adjacent brands or design movements (e.g., 'Wes Anderson palettes', 'Y2K design', 'Trader Joe's hand-drawn aesthetic')"
  - "Cultural reference points"
mood: "3-5 adjectives capturing the emotional register"
notable_visual_signatures:
  - "Specific, repeatable visual elements that define this brand"
  - "Things a designer would copy if asked to make on-brand creative"
color_mood: "Palette feel WITHOUT hex codes — 'warm earth tones', 'high-saturation neon', 'monochromatic charcoal', 'pastel candy colors', etc."

Be specific and opinionated. Don't write generic strategist-speak. Reference real brands, design eras, and visual idioms when they apply."""

    system = (
        "You are a creative director and brand strategist. You can look at a brand's "
        "visual assets and articulate exactly what makes them visually distinct, in "
        "language a designer can act on."
    )

    try:
        result = gemini_vision(
            prompt=prompt,
            image_urls=image_urls,
            system=system,
            max_tokens=2048,
        )
    except Exception as e:
        import sys
        print(f"[visual identity error: {type(e).__name__}: {str(e)[:200]}]", file=sys.stderr)
        return None

    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    try:
        return yaml.safe_load(result)
    except Exception:
        return None


def fetch_product_pages(urls: list[str]) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html"}
    results: dict[str, str] = {}
    total_chars = 0
    with httpx.Client(timeout=15.0, follow_redirects=True, headers=headers) as client:
        for url in urls:
            try:
                resp = client.get(url)
            except (httpx.RequestError, httpx.TimeoutException):
                continue
            if resp.status_code != 200:
                continue
            cleaned = clean_html(resp.text)[:MAX_HTML_PER_PAGE]
            if cleaned:
                results[url] = cleaned
                total_chars += len(cleaned)
                if total_chars >= MAX_TOTAL_HTML:
                    break
    return results


def run_brand_intake(
    brand_name: str,
    brand_url: str,
    seed_answers: dict[str, str],
    pages: dict[str, str],
    bestsellers: list[ProductCard] | None = None,
    visual_identity: dict | None = None,
) -> BrandIntakeResult:
    """Combine seed answers + fetched pages + bestsellers + vision-extracted
    visual identity into a brand-context doc + data.

    System context: motion/brand-intake (full Motion methodology).
    Returns both the human-readable markdown context AND structured data
    for our YAML pipeline.

    Note: brand colors are NOT extracted by research (CSS extraction was
    unreliable; logo vision often missed the actual palette). Clients fill
    colors directly in brand.yaml. Visual identity captures the broader
    design language which is more useful for ad generation.
    """
    if not pages:
        raise ValueError(
            "No pages fetched. Check the URL responds to / or /about."
        )

    pages_text = "\n\n".join(
        f"=== PAGE: {url} ===\n{html}" for url, html in pages.items()
    )

    seed_text = "\n".join(
        f"- {key.replace('_', ' ').title()}: {value or '(not provided)'}"
        for key, value in seed_answers.items()
    )

    bestsellers_text = ""
    if bestsellers:
        rows = "\n".join(
            f"  {c.rank}. {c.name} — {c.url} — {c.price or 'price unknown'}"
            + (f" — image: {c.image_url}" if c.image_url else "")
            for c in bestsellers[:30]
        )
        bestsellers_text = (
            f"\n\nTOP-SELLING PRODUCTS (from Shopify /collections/all?sort_by=best-selling, "
            f"ranked by sales — these are the REAL hero products, more reliable than "
            f"homepage features):\n{rows}\n\n"
            "When building the product catalog, prioritize these. The first ~5 are "
            "the brand's true hero SKUs; the collection that appears most often in "
            "the top 20 is the likely hero collection."
        )

    visual_identity_text = ""
    if visual_identity and isinstance(visual_identity, dict):
        vi_yaml = yaml.dump(visual_identity, default_flow_style=False, sort_keys=False)
        visual_identity_text = (
            f"\n\nVISUAL IDENTITY ANALYSIS (extracted by Gemini 2.5 Pro from "
            f"multiple brand images — logo + product shots + hero):\n{vi_yaml}\n"
            "Use this verbatim as visual_identity in the structured data. Also "
            "weave it into the 'Brand Voice & Tone' and 'Must-Know Strategic "
            "Context' sections of the brand-context.md."
        )

    prompt = f"""You are doing a brand intake. The user has answered seed questions
and provided their site URL. You've fetched the homepage and key sub-pages.

Produce TWO things in your response, separated by `---STRUCTURED-DATA---`:

PART 1: A complete brand-context.md document following the format in your
brand-intake skill instructions. Save sections for: Brand Overview, Brand
Story & Origin, Product Catalog, What Makes Them Different, Competitor
Landscape, The Alternative Solution, Core Audience(s), Brand Voice & Tone,
Creative Constraints, Must-Know Strategic Context, Research Notes (cite
sources, flag gaps).

PART 2: After `---STRUCTURED-DATA---`, return YAML matching this schema (used
to populate brand.yaml, products/*.yaml, avatar.yaml). Confidence-tag every
brand field. DO NOT include brand colors — those are filled in directly by
the client, not extracted from the site.

```yaml
brand:
  name: {{value: "...", confidence: high|medium|low|unknown, source: "..."}}
  tagline: {{value: "...", confidence: ..., source: ...}}
  mission: {{value: "...", confidence: ..., source: ...}}
  founded: {{value: "YYYY", confidence: ..., source: ...}}
  founder: {{value: "...", confidence: ..., source: ...}}
  typography:
    heading: {{value: "...", confidence: ..., source: ...}}
    body: {{value: "...", confidence: ..., source: ...}}
  tone:
    value: "1-2 sentence brand voice description"
    confidence: ...
    source: ...
  visual_identity:
    # Use the VISUAL IDENTITY ANALYSIS provided in the input verbatim if available;
    # otherwise leave fields empty for the client to fill in.
    aesthetic: "..."
    photography_style: "..."
    design_language: "..."
    typography_feel: "..."
    mascot_or_character: "..."
    visual_references: ["..."]
    mood: "..."
    notable_visual_signatures: ["..."]
    color_mood: "..."
  audience:
    age_range: {{value: "...", confidence: ..., source: ...}}
    gender: {{value: "...", confidence: ..., source: ...}}
    interests: {{value: ["..."], confidence: ..., source: ...}}
  press_mentions:
    value: ["..."]
    confidence: ...
    source: ...
  social_proof:
    value: ["..."]
    confidence: ...
    source: ...

products:
  - name: {{value: "...", confidence: ..., source: ...}}
    url: {{value: "...", confidence: ..., source: ...}}
    description: {{value: "...", confidence: ..., source: ...}}
    price: {{value: "...", confidence: ..., source: ...}}
    image_url: {{value: "...", confidence: ..., source: ...}}
    is_likely_hero: true|false

avatar_signals:
  inferred_demographic: "..."
  inferred_pain_points: ["..."]
  inferred_desires: ["..."]
  inferred_awareness_level: "unaware|problem_aware|solution_aware|product_aware|most_aware"
  inferred_objections: ["..."]
  inferred_trigger_events: ["..."]
  confidence: low

questions_for_user:
  - field: "..."
    question: "..."
    why_asking: "..."
```

INPUT:

BRAND NAME (from user): {brand_name}
BRAND URL (from user): {brand_url}

SEED ANSWERS FROM USER:
{seed_text}

PAGES FETCHED ({len(pages)} pages):
{pages_text}
{bestsellers_text}
{visual_identity_text}

Respond with PART 1 markdown, then `---STRUCTURED-DATA---`, then PART 2 YAML.
No code fences in PART 2."""

    system = load_skill("motion/brand-intake")
    raw = claude_complete(prompt, system=system, max_tokens=12000)

    if "---STRUCTURED-DATA---" not in raw:
        raise ValueError(
            "Model output missing the ---STRUCTURED-DATA--- separator. "
            "Got:\n" + raw[:500]
        )

    md_part, yaml_part = raw.split("---STRUCTURED-DATA---", 1)
    md_part = md_part.strip()
    yaml_part = yaml_part.strip()

    if yaml_part.startswith("```"):
        yaml_part = yaml_part.split("\n", 1)[1]
    if yaml_part.endswith("```"):
        yaml_part = yaml_part.rsplit("```", 1)[0]

    data = yaml.safe_load(yaml_part) or {}
    # Inject visual_identity directly into the data so it survives the YAML round-trip
    # even if the model didn't echo it back perfectly
    if visual_identity and isinstance(visual_identity, dict):
        data.setdefault("brand", {})["visual_identity"] = visual_identity

    return BrandIntakeResult(
        brand_context_md=md_part,
        data=data,
        bestseller_count=len(bestsellers) if bestsellers else 0,
        visual_identity=visual_identity,
    )


def confidence_buckets(data: dict) -> dict[str, list[tuple[str, dict]]]:
    """Walk extracted brand data and bucket fields by confidence."""
    buckets: dict[str, list[tuple[str, dict]]] = {
        "high": [],
        "medium": [],
        "low": [],
        "unknown": [],
    }

    def walk(obj, prefix=""):
        if not isinstance(obj, dict):
            return
        if "confidence" in obj and "value" in obj:
            conf = str(obj.get("confidence", "unknown")).lower()
            if conf in buckets:
                buckets[conf].append((prefix.rstrip("."), obj))
            return
        for key, value in obj.items():
            walk(value, f"{prefix}{key}.")

    walk(data.get("brand", {}), "brand.")
    return buckets
