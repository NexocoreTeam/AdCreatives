"""Voice of Customer mining — extract pain points and language from reviews.

Uses the customer-research skill (prompts/skills/customer-research.md) as
system context to enforce JTBD framework, money-quote selection, confidence
scoring, and sample-bias guardrails on every extraction.
"""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from models.avatar import CustomerAvatar, Desire, PainPoint
from models.skills import load_skill
from strategy.llm import claude_complete

VOC_SYSTEM = """You are a voice-of-customer research analyst specializing in direct response advertising.

Your job is to mine customer reviews and extract:
1. JOBS TO BE DONE — functional, emotional, and social outcomes the customer is hiring the product for
2. PAIN POINTS — the specific frustrations, problems, and complaints customers express
3. DESIRES — what they ultimately want to achieve or feel
4. EXACT LANGUAGE — the actual words and phrases customers use (not your paraphrase)
5. OBJECTIONS — reasons people hesitate or express dissatisfaction
6. TRIGGER EVENTS — what made them search for a solution
7. ALTERNATIVES CONSIDERED — what else they tried (including doing nothing)
8. MONEY QUOTES — 5-10 verbatim quotes per theme that best represent it

Focus on emotionally charged language. The 3-star reviews are gold — those customers
care enough to write but have real complaints. Look for:
- "I wish..." statements
- "The problem is..." statements
- "I was hoping..." statements
- Comparisons to competitors
- Specific numbers and timeframes they mention

CONFIDENCE SCORING — label every insight with a confidence level:
- high: appears in 3+ independent reviews, mentioned unprompted, consistent
- medium: appears in 2 reviews or limited to one segment
- low: single source, could be an outlier

SAMPLE BIAS — note that online reviewers skew toward power users and people with
strong opinions. Don't over-generalize from a small sample.

You operate under the customer-research skill below. Follow its extraction
framework, synthesis steps, and quality guardrails.

---

""" + load_skill("customer-research") + """

---

Output valid YAML only, no markdown fences."""

VOC_EXTRACTION_PROMPT = """Analyze these customer reviews for {product_category} products and extract voice-of-customer insights.

REVIEWS:
{reviews}

Extract and return as YAML with this structure:

jobs_to_be_done:
  - job: "the outcome they're hiring the product for"
    type: "functional/emotional/social"
    customer_language:
      - "exact quote"
    confidence: "high/medium/low"

pain_points:
  - pain: "the core pain"
    intensity: "high/medium/low"
    confidence: "high/medium/low"
    customer_language:
      - "exact quote from reviews"
      - "another exact quote"
    source: "{source}"

desires:
  - desire: "what they want"
    confidence: "high/medium/low"
    customer_language:
      - "exact quote"

objections:
  - objection: "the concern"
    confidence: "high/medium/low"
    customer_language:
      - "exact quote"

trigger_events:
  - event: "what made them look for a solution"
    confidence: "high/medium/low"

alternatives_considered:
  - alternative: "competitor or workaround they tried"
    why_rejected: "what made it not work"

language_patterns:
  - "how they talk — formal/casual, jargon, emotional register"

money_quotes:
  - quote: "the verbatim quote"
    theme: "which theme it represents (pain, desire, etc.)"
    why_it_matters: "what makes this quote useful for ad copy"

sample_notes:
  total_reviews: <integer>
  bias_warnings: ["any biases worth flagging"]
  recency: "how recent the reviews are if discernible"

Return 5-10 pain points ranked by intensity, 3-5 desires, 3-5 objections, 3-5 trigger
events, 3-5 jobs-to-be-done, 5-10 money quotes. Use ONLY language that actually
appears in the reviews. Do not invent quotes."""


def extract_voc_from_text(
    reviews_text: str,
    product_category: str,
    source: str = "reviews",
) -> dict:
    """Extract VOC insights from raw review text."""
    prompt = VOC_EXTRACTION_PROMPT.format(
        product_category=product_category,
        reviews=reviews_text[:15000],  # Token budget guard
        source=source,
    )
    result = claude_complete(prompt, system=VOC_SYSTEM)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]
    return yaml.safe_load(result)


def load_reviews_from_file(path: Path) -> str:
    """Load review text from a JSON or text file."""
    if path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
        if isinstance(data, list):
            return "\n\n---\n\n".join(
                f"Rating: {r.get('rating', 'N/A')}\n{r.get('text', r.get('body', str(r)))}"
                for r in data
            )
        return json.dumps(data, indent=2)
    with open(path) as f:
        return f.read()


def mine_voc_for_client(
    client_slug: str,
    product_category: str,
) -> dict:
    """Mine all VOC files in a client's voc/ directory and merge insights."""
    voc_dir = Path("clients") / client_slug / "voc"
    if not voc_dir.exists():
        raise FileNotFoundError(
            f"No VOC directory found at {voc_dir}. "
            f"Add review files (JSON or TXT) to clients/{client_slug}/voc/"
        )

    all_insights: list[dict] = []
    for review_file in sorted(voc_dir.glob("*")):
        if review_file.suffix in (".json", ".txt") and not review_file.name.startswith("extracted"):
            reviews_text = load_reviews_from_file(review_file)
            source = review_file.stem
            insights = extract_voc_from_text(reviews_text, product_category, source)
            all_insights.append(insights)

    if not all_insights:
        raise FileNotFoundError(
            f"No review files found in {voc_dir}. "
            "Add .json or .txt files with customer reviews."
        )

    return _merge_insights(all_insights)


def _merge_insights(insights_list: list[dict]) -> dict:
    """Merge VOC insights from multiple sources."""
    merged = {
        "jobs_to_be_done": [],
        "pain_points": [],
        "desires": [],
        "objections": [],
        "trigger_events": [],
        "alternatives_considered": [],
        "language_patterns": [],
        "money_quotes": [],
        "sample_notes": [],
    }
    for insights in insights_list:
        for key in merged:
            items = insights.get(key, [])
            if isinstance(items, list):
                merged[key].extend(items)
            elif isinstance(items, dict):
                merged[key].append(items)
    return merged


def voc_to_avatar_fields(voc_data: dict) -> dict:
    """Convert raw VOC data into fields compatible with CustomerAvatar."""
    pain_points = []
    for p in voc_data.get("pain_points", []):
        if isinstance(p, dict):
            pain_points.append(PainPoint(
                pain=p.get("pain", ""),
                intensity=p.get("intensity", "medium"),
                customer_language=p.get("customer_language", []),
                source=p.get("source", ""),
            ))

    desires = []
    for d in voc_data.get("desires", []):
        if isinstance(d, dict):
            desires.append(Desire(
                desire=d.get("desire", ""),
                customer_language=d.get("customer_language", []),
            ))

    objections = []
    for o in voc_data.get("objections", []):
        if isinstance(o, dict):
            objections.append(o.get("objection", ""))
        elif isinstance(o, str):
            objections.append(o)

    triggers = []
    for t in voc_data.get("trigger_events", []):
        if isinstance(t, dict):
            triggers.append(t.get("event", ""))
        elif isinstance(t, str):
            triggers.append(t)

    return {
        "pain_points": pain_points,
        "desires": desires,
        "objections": objections,
        "trigger_events": triggers,
        "language_patterns": voc_data.get("language_patterns", []),
    }
