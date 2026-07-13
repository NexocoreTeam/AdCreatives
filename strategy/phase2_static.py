"""Phase 2 static-ad briefing scaffold.

This module creates the operator-facing workbook used after the Audience
Conversion Report and before ad production. It is intentionally local/free:
it does not scrape ads, call LLMs, or generate images.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CLIENTS_DIR = Path("clients")


@dataclass(frozen=True)
class StaticPhase2WorkbookResult:
    path: Path
    client_slug: str
    product: str | None
    focus_avatar: str | None
    mass_desire: str | None


def create_static_phase2_workbook(
    client_slug: str,
    *,
    product: str | None = None,
    focus_avatar: str | None = None,
    mass_desire: str | None = None,
    filename: str = "phase-2-static-briefing-workbook.md",
    force: bool = False,
    clients_dir: Path = CLIENTS_DIR,
) -> StaticPhase2WorkbookResult:
    """Create the Phase 2 static-ad briefing workbook for a client."""

    client_dir = clients_dir / client_slug
    if not client_dir.exists():
        raise FileNotFoundError(f"Client not found: {client_dir}")

    out_dir = client_dir / "research" / "audience-conversion"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    if path.exists() and not force:
        raise FileExistsError(f"Workbook already exists: {path}. Use --force to overwrite.")

    path.write_text(
        _render_workbook(
            client_slug=client_slug,
            product=product,
            focus_avatar=focus_avatar,
            mass_desire=mass_desire,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ),
        encoding="utf-8",
    )
    return StaticPhase2WorkbookResult(
        path=path,
        client_slug=client_slug,
        product=product,
        focus_avatar=focus_avatar,
        mass_desire=mass_desire,
    )


def _render_workbook(
    *,
    client_slug: str,
    product: str | None,
    focus_avatar: str | None,
    mass_desire: str | None,
    generated_at: str,
) -> str:
    product_label = product or "TBD"
    avatar_label = focus_avatar or "TBD - choose before concepting"
    mass_desire_label = mass_desire or "TBD - choose after research synthesis"
    return f"""# Phase 2 Static Briefing Workbook

Client: `{client_slug}`
Product: `{product_label}`
Generated: `{generated_at}`

This workbook is the required bridge between the Audience Conversion Report and
static ad production. Do not jump directly into visual formats or image
generation. Complete the gates in order.

## Operating Sequence

1. Synthesize audience research.
2. Pick one avatar.
3. Pick one mass desire, core objection, misconception, failed solution, or
   behavior/moment.
4. Pull and analyze competitor plus adjacent-niche ads.
5. Build the 70/20/10 concept source mix.
6. Build the angle bank by awareness level.
7. Ask the operator to choose the visual format/template.
8. Write template-specific benefits, negatives, and headlines.
9. Run the Static Mistake Filter.
10. Get approval before production or paid generation.

## Gate 1: Audience Research Synthesis

Use the Audience Conversion Report and source-truth check. Fill this before
concepting.

### Psychographics

| Insight | Source language | Why it matters for ads |
|---|---|---|
|  |  |  |

### Problems And Desires

| Problem/desire | Exact language | Source | Ad implication |
|---|---|---|---|
|  |  |  |  |

### Behaviors And Moments

| Moment | Trigger | Behavior | Exact language | Ad angle |
|---|---|---|---|---|
|  |  |  |  |  |

### Objections And Misconceptions

| Objection/misconception | Customer wording | Source | How the ad should handle it |
|---|---|---|---|
|  |  |  |  |

### Exact Customer Terminology

Use explicit notes like: "We are using this phrase because customers said
`<phrase>` in `<reviews/Reddit/TikTok/source>`."

| Phrase | Source/context | What it means | How to use it | Avoid polishing into |
|---|---|---|---|---|
|  |  |  |  |  |

## Gate 2: Avatar Selection

Selected avatar: **{avatar_label}**

Choose one avatar before concepting. If multiple avatars are attractive, make
separate concept batches.

| Avatar | Core desire | Core pain | Core objection | Language style | Source support |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

Decision:

- Selected avatar:
- Why this avatar first:
- Angles to avoid for this avatar:

## Gate 3: Mass Desire Selection

Selected mass desire / core focus: **{mass_desire_label}**

Ask the operator to choose one before building the angle bank.

Candidate mass desires:

| Mass desire | Source-backed proof | Best awareness level | Why it is worth testing |
|---|---|---|---|
|  |  |  |  |

Decision:

- Selected mass desire:
- Related objection/misconception:
- Related behavior/moment:

## Gate 4: Competitor And Adjacent Ad Pull Plan

Do not invent the 70% lane from memory. Pull or reuse ads from Foreplay, Apify,
Meta/TikTok ad libraries, Pinterest mechanics, or approved ad-library cards.
Quote cost and get approval before paid pulls.

### Direct Competitors / Category Sources

Target: 10 usable ideas.

| Brand/source | Where to pull | Why this source | Status |
|---|---|---|---|
|  |  |  | not pulled |

### Adjacent Niches

Target: 10 usable ideas.

| Adjacent niche | Example brands/sources | Why it maps to this avatar/desire | Status |
|---|---|---|---|
|  |  |  | not pulled |

## Gate 5: Ad Analysis And Opportunity Extraction

Use this table for every pulled competitor or adjacent ad. Do not only
summarize the ad. Extract the opportunity.

| ID | Source lane | Reference | Mechanic | What works | What they did wrong | Missed opportunity | How we can emulate |
|---|---|---|---|---|---|---|---|
|  | direct_competitor |  |  |  |  |  |  |
|  | adjacent_niche |  |  |  |  |  |  |

## Gate 6: 70 / 20 / 10 Concept Source Mix

Use this mix before selecting formats.

| Lane | Target | Actual | Notes |
|---|---:|---:|---|
| 70% proven outside references |  |  | direct competitors + adjacent niches |
| 20% internal winners |  |  | prior client/agency winners if available |
| 10% new swings |  |  | fresh hypotheses only after proven lanes |

### 10 Competitor Ideas

| Idea | Source ad | Mechanic | Awareness level | Evidence level | Adaptation note |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

### 10 Adjacent Niche Ideas

| Idea | Source ad | Mechanic | Awareness level | Evidence level | Adaptation note |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

### Internal Winners

| Winner | What worked | How to remix | Evidence |
|---|---|---|---|
|  |  |  |  |

### New Swings

| Idea | Hypothesis | Risk | Why it may be worth testing |
|---|---|---|---|
|  |  |  |  |

## Gate 7: Angle Bank By Awareness Level

Build this after choosing the mass desire. Use exact source language where
possible.

| Awareness level | Angle | Hook territory | Source phrase | Why it works | Proof needed |
|---|---|---|---|---|---|
| unaware |  |  |  |  |  |
| problem-aware |  |  |  |  |  |
| solution-aware |  |  |  |  |  |
| product-aware |  |  |  |  |  |
| most-aware |  |  |  |  |  |

## Gate 8: Visual Format / Template Selection

Stop here and ask the operator which format/template to use.

Examples:

- us vs them
- receipt comparison
- apology note
- calendar screenshot
- testimonial/story overlay
- comparison grid
- TikTok pill stack
- IG Story square box
- organic caption
- founder note

Selected format/template:

- Format:
- Why this format fits the angle:
- What the template controls:
- What research controls:

## Gate 9: Template-Specific Copy Set

Complete this only after the operator chooses the visual format/template.

### Benefits To List

| Awareness level | Benefit | Benefit-depth level | Source phrase/proof |
|---|---|---|---|
| unaware |  |  |  |
| problem-aware |  |  |  |
| solution-aware |  |  |  |
| product-aware |  |  |  |
| most-aware |  |  |  |

### Negatives / Comparison Bullets To List

| Awareness level | Negative/comparison bullet | What it contrasts against | Source phrase/proof |
|---|---|---|---|
| unaware |  |  |  |
| problem-aware |  |  |  |
| solution-aware |  |  |  |
| product-aware |  |  |  |
| most-aware |  |  |  |

### Five Headline Options

Keep headlines clear. Prefer 6-10 words when possible. Rank by
scroll-stopping power and relevance.

| Rank | Headline | Awareness level | Why it works | Source language |
|---:|---|---|---|---|
| 1 |  |  |  |  |
| 2 |  |  |  |  |
| 3 |  |  |  |  |
| 4 |  |  |  |  |
| 5 |  |  |  |  |

## Gate 10: Static Mistake Filter

Before production, confirm:

- Main hook is readable in one second.
- Main hook survives center 1:1 crop.
- The concept moves the sale forward.
- The copy is not generic.
- The hook uses benefit depth beyond level one when research supports it.
- The line is grounded in research, not cleverness.
- The visual authenticity matches the claim.

Failure notes:

- 

## Approval Gate

Do not make the ads until the operator approves:

- selected avatar
- selected mass desire
- source mix / references
- angle bank
- selected visual format/template
- template-specific benefits, negatives, and headlines
- Static Mistake Filter pass

Approval status:

- [ ] Approved for production
- [ ] Needs revision
"""
