"""Brand research agent — interview-first flow.

Implements Motion's brand-intake methodology:
1. Interview the user with batched seed questions
2. Fetch the brand's website (homepage + standard sub-pages)
3. Combine seed + scraped data to produce a comprehensive brand-context.md
4. Also emit structured data for our YAML pipeline (brand/product/avatar)

System context comes from prompts/skills/motion/brand-intake.md (MIT, by
Alysha at Motion). The HTTP fetcher and the structured-data extraction are
original to AdCreatives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from models.skills import load_skill
from strategy.llm import claude_complete

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
) -> BrandIntakeResult:
    """Combine seed answers + fetched pages into a brand-context doc + data.

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
    return BrandIntakeResult(brand_context_md=md_part, data=data)


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
