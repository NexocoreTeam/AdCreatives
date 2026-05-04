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
from strategy.llm import claude_complete, claude_vision

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
    vision_colors: dict | None = None
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


def extract_brand_colors_via_vision(logo_url: str) -> dict | None:
    """Use Claude Sonnet 4.6 vision on the logo to identify real brand colors.

    Returns dict with primary/secondary/accent hex values, or None on failure.
    Logo is a stronger signal than CSS theme colors (which include navigation,
    body text, neutral backgrounds, etc.).
    """
    if not logo_url:
        return None

    prompt = (
        "Identify the BRAND COLORS in this logo. Ignore the page background "
        "behind the logo — focus only on the colors that appear inside the "
        "logo design itself.\n\n"
        "Return YAML in this exact format (no markdown fences):\n\n"
        "primary: \"#RRGGBB\"      # the main/dominant brand color\n"
        "secondary: \"#RRGGBB\"    # the accent or supporting brand color\n"
        "accent: \"#RRGGBB\"       # optional third color, only if clearly present\n"
        "logo_description: \"brief 1-sentence description of the logo design\"\n"
        "confidence: high|medium|low\n\n"
        "Hex codes must be your best estimate of the actual brand colors. "
        "Round to common palette values when reasonable (e.g., '#1a1a1a' for "
        "near-black, '#ffffff' for white)."
    )
    try:
        result = claude_vision(
            prompt=prompt,
            image_url=logo_url,
            system="You are a brand identity expert. You identify exact hex colors from logos.",
            max_tokens=512,
        )
    except Exception as e:
        # Surface the error type for easier diagnosis but don't crash the run
        import sys
        print(f"[vision error: {type(e).__name__}: {str(e)[:200]}]", file=sys.stderr)
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
    vision_colors: dict | None = None,
) -> BrandIntakeResult:
    """Combine seed answers + fetched pages + bestsellers + vision-extracted
    colors into a brand-context doc + data.

    System context: motion/brand-intake (full Motion methodology).
    Returns both the human-readable markdown context AND structured data
    for our YAML pipeline.
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

    vision_text = ""
    if vision_colors and isinstance(vision_colors, dict) and vision_colors.get("primary"):
        vision_text = (
            f"\n\nLOGO VISION ANALYSIS (extracted by GPT-4o vision from the brand "
            f"logo image — these are the REAL brand colors, more reliable than CSS "
            f"theme variables):\n"
            f"  primary: {vision_colors.get('primary')}\n"
            f"  secondary: {vision_colors.get('secondary')}\n"
            f"  accent: {vision_colors.get('accent', 'none')}\n"
            f"  logo: {vision_colors.get('logo_description', '')}\n"
            f"  vision_confidence: {vision_colors.get('confidence', 'medium')}\n\n"
            "Use these as the SOURCE OF TRUTH for brand.colors. Mark them as "
            "high confidence with source 'logo via GPT-4o vision'."
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
brand field:

```yaml
brand:
  name: {{value: "...", confidence: high|medium|low|unknown, source: "..."}}
  tagline: {{value: "...", confidence: ..., source: ...}}
  mission: {{value: "...", confidence: ..., source: ...}}
  founded: {{value: "YYYY", confidence: ..., source: ...}}
  founder: {{value: "...", confidence: ..., source: ...}}
  colors:
    primary: {{value: "#RRGGBB", confidence: ..., source: ...}}
    secondary: {{value: "#RRGGBB", confidence: ..., source: ...}}
    background: {{value: "#RRGGBB", confidence: ..., source: ...}}
  typography:
    heading: {{value: "...", confidence: ..., source: ...}}
    body: {{value: "...", confidence: ..., source: ...}}
  tone:
    value: "1-2 sentence brand voice description"
    confidence: ...
    source: ...
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
{vision_text}

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
    return BrandIntakeResult(
        brand_context_md=md_part,
        data=data,
        bestseller_count=len(bestsellers) if bestsellers else 0,
        vision_colors=vision_colors,
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
