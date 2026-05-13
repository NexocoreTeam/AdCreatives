"""Generate multiple messaging angles from a single product/avatar combination.

Uses four layered skills as system context (loaded from prompts/skills/):
- hook-methodology (DV0x): research-first hook extraction
- hook-formulas (DV0x): 10 hook types with psychology and structure
- motion/creative-strategy-engine (Motion): pain × persona × awareness matrix
- motion/hook-tactics (Motion): 35+ tactical hook formats
- motion/hook-writing (Motion): psychologically driven hook composition
- motion/hook-voice-patterns (Motion): native-feed voice swipe file

The diversity matrix enforces one hook per emotional trigger; Motion's strategic
framework anchors the *what* (pain × persona); the hook libraries supply the *how*.

Two layered constraints can also be applied at generation time:

1. PSYCHOLOGY PROFILE (Stage 1.5 `adc profile-psychology`) — when the avatar
   carries a `psychology_profile`, the diversity matrix is filtered to slots
   that activate the avatar's dominant heuristics, and the prompt is augmented
   with hard constraints on weak heuristics + banned creative-mechanic pairings.

2. COMPETITIVE GAP MAP (Stage 5.5 `adc analyze-gaps`) — when the client has a
   competitive-gaps.yaml, the synthesis block (exploitable gaps, shared
   dealbreakers, defensive priorities) is injected into the prompt so at least
   half the angles target a specific competitor weakness.

Psychology decides WHICH slots and mechanics fit this persona.
Gaps provide WHAT content (proof, evidence, ad angles) to use within those slots.
"""

from __future__ import annotations

import yaml

from models.avatar import CustomerAvatar, PsychologyProfile
from models.brand import Brand
from models.product import Product
from models.skills import load_skill
from strategy.llm import claude_complete

# Diversity matrix — adapted from DV0x/creative-ad-agent's hook-methodology.
# Each slot covers a different emotional trigger so the generated set varies
# meaningfully across cognitive levers, not just surface phrasing.
DIVERSITY_MATRIX = [
    {"slot": 1, "hook_type": "Surprising Stat", "trigger": "Social Proof / Credibility"},
    {"slot": 2, "hook_type": "Story / Result", "trigger": "Empathy + Relief"},
    {"slot": 3, "hook_type": "FOMO / Urgency", "trigger": "Loss Aversion"},
    {"slot": 4, "hook_type": "Curiosity Gap", "trigger": "Intrigue"},
    {"slot": 5, "hook_type": "Direct Address / Call-out", "trigger": "Recognition"},
    {"slot": 6, "hook_type": "Contrast / Enemy", "trigger": "Differentiation"},
    {"slot": 7, "hook_type": "Question", "trigger": "Self-reference"},
    {"slot": 8, "hook_type": "Pattern Interrupt", "trigger": "Pattern break"},
    {"slot": 9, "hook_type": "Controversial", "trigger": "Polarization"},
    {"slot": 10, "hook_type": "Problem-Solution", "trigger": "Pain → relief"},
]

# Each diversity slot primarily activates one or two of the 9 heuristics.
# Used by `filter_matrix_by_profile` to drop slots whose primary heuristics
# are all in the avatar's `weak_heuristics` set.
SLOT_TO_HEURISTICS: dict[int, list[str]] = {
    1: ["authority_bias"],                       # Surprising Stat — credibility numbers
    2: ["effect_heuristic", "social_proof"],     # Story / Result — empathy + relief
    3: ["scarcity", "temporal_discounting"],     # FOMO / Urgency — loss aversion
    4: ["salience_bias"],                        # Curiosity Gap — intrigue
    5: ["framing_effect", "social_proof"],       # Direct Address — recognition
    6: ["framing_effect"],                       # Contrast / Enemy
    7: ["framing_effect"],                       # Question — self-reference
    8: ["salience_bias"],                        # Pattern Interrupt
    9: ["salience_bias"],                        # Controversial — polarization
    10: ["framing_effect", "effect_heuristic"],  # Problem-Solution
}


def _diversity_matrix_text(slots: list[dict]) -> str:
    """Format a list of diversity slots as a readable prompt section."""
    rows = [
        f"  Slot {row['slot']}: {row['hook_type']} ({row['trigger']})"
        for row in slots
    ]
    return "\n".join(rows)


def filter_matrix_by_profile(
    profile: PsychologyProfile | None,
    count: int,
) -> list[dict]:
    """Filter DIVERSITY_MATRIX to slots compatible with the psychology profile.

    Drops slots whose primary heuristics are ALL in `weak_heuristics`. Returns
    the first `count` surviving slots in original order. If no profile is
    provided, returns the first `count` slots unchanged (backwards-compatible).

    Raises ValueError if fewer than `count` slots survive filtering — better
    to fail loudly than silently shrink the brief below what was requested.
    """
    if profile is None or not profile.weak_heuristics:
        if count > len(DIVERSITY_MATRIX):
            raise ValueError(
                f"count={count} exceeds diversity matrix size ({len(DIVERSITY_MATRIX)})."
            )
        return DIVERSITY_MATRIX[:count]

    weak_set = {h.heuristic for h in profile.weak_heuristics}
    surviving: list[dict] = []
    for slot in DIVERSITY_MATRIX:
        activated = SLOT_TO_HEURISTICS.get(slot["slot"], [])
        # Keep slot if NOT every activated heuristic is in the weak set.
        # (Salience-only slots are always neutral and stay.)
        if not activated or any(h not in weak_set for h in activated):
            surviving.append(slot)

    if len(surviving) < count:
        weak_names = sorted(weak_set)
        raise ValueError(
            f"Only {len(surviving)} diversity slots survive filtering against this "
            f"avatar's weak heuristics ({', '.join(weak_names)}); requested {count}. "
            f"Reduce --angles to {len(surviving)}, or use --ignore-psychology."
        )
    return surviving[:count]


def build_psychology_block(profile: PsychologyProfile | None) -> str:
    """Build the prompt segment that injects the psychology profile as guardrails.

    Returns an empty string when no profile is provided (caller drops the
    section header so the prompt stays clean).
    """
    if profile is None:
        return ""

    parts: list[str] = ["PSYCHOLOGY PROFILE FOR THIS AVATAR (HARD CONSTRAINTS):"]

    if profile.emotional_position:
        primary = profile.emotional_position.primary
        secondary = profile.emotional_position.secondary
        parts.append(
            f"  Primary emotional quadrant: {primary.valence} / {primary.intensity}"
        )
        parts.append(
            f"  Secondary quadrant (variant testing): "
            f"{secondary.valence} / {secondary.intensity}"
        )
        if primary.rationale:
            parts.append(f"  Why this quadrant: {primary.rationale[:240].strip()}")

    if profile.dominant_heuristics:
        parts.append("")
        parts.append(
            "  Dominant heuristics — every angle MUST primarily activate one of these:"
        )
        for h in profile.dominant_heuristics:
            parts.append(
                f"    - {h.heuristic} ({h.confidence}): {h.ad_implications[:200].strip()}"
            )

    if profile.weak_heuristics:
        parts.append("")
        parts.append(
            "  WEAK heuristics — do NOT lead with these. They will backfire:"
        )
        for h in profile.weak_heuristics:
            parts.append(f"    - {h.heuristic}: {h.avoid[:200].strip()}")

    if profile.recommended_prompt_pairings:
        parts.append("")
        parts.append(
            "  Pre-approved concept mechanics — prefer one of these for `creative_mechanic`:"
        )
        for p in profile.recommended_prompt_pairings:
            parts.append(f"    - {p.pairing}")

    if profile.avoid_pairings:
        parts.append("")
        parts.append(
            "  BANNED concept mechanics — do NOT use these for `creative_mechanic`:"
        )
        for p in profile.avoid_pairings:
            parts.append(
                f"    - {p.pairing} — {p.avoid_because[:160].strip()}"
            )

    return "\n".join(parts)


ANGLE_SYSTEM = """You are a direct response advertising strategist trained by the best:
Eugene Schwartz, Gary Halbert, David Ogilvy, and modern performance marketers.

Your job is to generate MULTIPLE distinct messaging angles for the same product.
Each angle attacks a different pain × persona intersection, occupies a DIFFERENT
slot in the diversity matrix below (no hook_type repeats), uses a different
copy framework, and selects a different creative mechanic + visual format.

Rules:
- Every hook is traceable to a specific source in the avatar/product data
- Each angle must be genuinely different — not just rewording the same idea
- Use the customer's actual language from the avatar data (pain, desires, money quotes)
- Be specific with numbers, timeframes, and outcomes
- Sound human, not corporate. Write like a person talking to a friend.
- Every hook must stop the scroll in under 2 seconds of reading
- Match the tone to the awareness level

You operate under SIX layered skills below. Use them together:

--- HOOK METHODOLOGY (DV0x) ---

""" + load_skill("hook-methodology") + """

--- HOOK FORMULAS (DV0x) ---

""" + load_skill("hook-formulas") + """

--- CREATIVE STRATEGY ENGINE (Motion) ---

""" + load_skill("motion/creative-strategy-engine") + """

--- HOOK TACTICS (Motion, 35+ tactics) ---

""" + load_skill("motion/hook-tactics") + """

--- HOOK WRITING (Motion) ---

""" + load_skill("motion/hook-writing") + """

--- HOOK VOICE PATTERNS (Motion, native-feed swipe file) ---

""" + load_skill("motion/hook-voice-patterns") + """

---

Output valid YAML only, no markdown fences."""

ANGLE_PROMPT = """Generate {count} distinct messaging angles for this product, one per
diversity slot. Do not repeat hook_type across slots. Vary the framework across
slots — do not pick one framework and apply it to all angles.

DIVERSITY MATRIX (use these hook types in this order):
{diversity_matrix}

AVAILABLE FRAMEWORKS (pick one per slot, vary across the set):
{frameworks}

PRODUCT:
  Name: {product_name}
  Description: {product_description}
  Key Benefits: {benefits}
  Unique Mechanism: {mechanism}
  Social Proof: {social_proof}

CUSTOMER AVATAR:
  Demographic: {demographic}
  Top Pain Points: {pain_points}
  Desires: {desires}
  Objections: {objections}
  Awareness Level: {awareness_level}
  How They Talk: {language_patterns}

{psychology_block}

BRAND TONE: {brand_tone}
MESSAGING APPROACH: {approach}
{competitive_gaps_section}
For each angle, return:

angles:
  - slot: <integer matching the diversity matrix>
    hook_type: "exact hook type from the matrix"
    hook_tactic: "specific tactic from Motion's 35+ hook-tactics (e.g. 'Specific stat with a story', 'Pattern interrupt with a confession')"
    angle: "brief description of the angle (e.g., 'time savings for busy parents')"
    hook: "the actual scroll-stopping hook text"
    source: "which research element this hook came from (pain X, benefit Y, quote Z)"
    pain_addressed: "which pain point this targets"
    persona: "which persona segment this targets (from creative-strategy-engine pain × persona mapping)"
    awareness_stage: "unaware | problem_aware | solution_aware | product_aware | most_aware"
    framework: "one of the frameworks above — pick the best fit for this slot"
    creative_mechanic: "name a structural mechanic from Motion's creative-mechanics that fits this angle (e.g. 'Pattern Interrupt with Reveal', 'Before/After Split', 'Talking Head Confession')"
    visual_format: "name a visual format from Motion's visual-formats library that fits this concept (e.g. 'UGC Static', 'Split-screen video', 'Text-on-product photo')"
    benefit_callouts:
      - "Short punchy callout 1"
      - "Short punchy callout 2"
      - "Short punchy callout 3"
    cta: "Call to action text"
    visual_direction: "What the image should convey to support this angle"
    why_it_works: "1-sentence explanation of the psychological trigger"

Quality checks before returning:
1. Every hook must be traceable to a specific research element via `source`.
2. Frameworks vary across slots — no repeats.
3. Creative mechanics vary across slots — no repeats.
4. Visual formats vary across slots when possible.
5. Hooks read like real human language, not ad copy.
6. When COMPETITIVE GAPS are provided, AT LEAST half of the angles should
   exploit a specific gap. Use `source` to reference the gap (e.g.,
   "competitive-gap: Poppi's gut-health claim legally discredited") and
   incorporate the customer evidence quote into the hook construction."""


def _format_competitive_gaps(gaps_data: dict | None) -> str:
    """Render the synthesis section of competitive-gaps.yaml into a prompt block.

    Includes only the strategic high-leverage sections (exploitable_gaps,
    shared_dealbreakers, defensive_priorities). Per-brand analyses are skipped
    here — they'd blow up token usage and aren't directly actionable as hook
    fodder.
    """
    if not gaps_data:
        return ""
    syn = gaps_data.get("synthesis", {})
    if not isinstance(syn, dict) or not syn:
        return ""

    parts = ["", "COMPETITIVE GAP MAP (use as primary hook fodder):", ""]

    if syn.get("summary"):
        parts.extend(["STRATEGIC THESIS:", f"  {syn['summary']}", ""])

    gaps = syn.get("exploitable_gaps") or []
    if gaps:
        parts.append("EXPLOITABLE GAPS (each is a ready-made angle source):")
        for i, g in enumerate(gaps[:8], 1):
            opp = g.get("opportunity", "")
            comps = ", ".join(g.get("competitors_failing", []) or [])
            evidence = (g.get("customer_evidence", "") or "").strip()
            advantage = (g.get("our_advantage", "") or "").strip()
            angle = (g.get("ad_angle", "") or "").strip()
            parts.extend([
                f"  Gap {i}: {opp}",
                f"    competitors failing: {comps}",
                f"    customer evidence: \"{evidence[:300]}\"",
                f"    our advantage: {advantage[:300]}",
                f"    ad angle direction: {angle[:300]}",
            ])
        parts.append("")

    dealbreakers = syn.get("shared_dealbreakers") or []
    if dealbreakers:
        parts.append("CATEGORY-WIDE DEALBREAKERS (lead with our solution):")
        for d in dealbreakers[:4]:
            parts.append(
                f"  - {d.get('issue', '')[:200]} -> our response: {d.get('our_response', '')[:200]}"
            )
        parts.append("")

    defensive = syn.get("defensive_priorities") or []
    if defensive:
        parts.append("DEFENSIVE PRIORITIES (objections to pre-empt, not lead with):")
        for d in defensive[:4]:
            parts.append(
                f"  - {d.get('objection', '')[:150]} -> pre-empt: {d.get('pre_empt', '')[:200]}"
            )
        parts.append("")

    return "\n".join(parts)


def generate_angles(
    product: Product,
    avatar: CustomerAvatar,
    brand: Brand,
    awareness_strategy: dict,
    count: int = 6,
    frameworks: list[str] | None = None,
    use_profile: bool = True,
    competitive_gaps: dict | None = None,
) -> list[dict]:
    """Generate multiple messaging angles for a product/avatar combo.

    Default count is 6 to fill the first six slots of the diversity matrix
    (Stat, Story, FOMO, Curiosity, Call-out, Contrast/Enemy) — the same set
    DV0x's creative-ad-agent uses for one campaign.

    `frameworks` is a list of CopyFramework values (e.g. ["pas", "bab", "fab"]);
    the model is instructed to vary the framework across slots. Defaults to a
    sensible set covering most awareness levels.

    Two layered constraints:

    1. When `use_profile=True` (default) and the avatar carries a
       `psychology_profile`, the diversity matrix is filtered to slots that
       activate the avatar's dominant heuristics, and the prompt is augmented
       with explicit guardrails on weak heuristics + recommended/banned Tether
       Lab pairings. Set `use_profile=False` to bypass — useful for
       before/after comparison.

    2. When `competitive_gaps` is provided (typically auto-loaded from
       clients/<slug>/research/competitive-gaps.yaml by the caller), its
       synthesis block is injected so at least half of generated angles target
       a specific competitor weakness.
    """
    profile = avatar.psychology_profile if use_profile else None

    matrix = filter_matrix_by_profile(profile, count)
    psychology_block = build_psychology_block(profile)

    if not frameworks:
        frameworks = ["pas", "aida", "bab", "fab"]

    pain_summary = "\n".join(
        f"  - [{p.intensity}] {p.pain}: {', '.join(p.customer_language[:2])}"
        for p in avatar.pain_points[:5]
    )
    desire_summary = "\n".join(
        f"  - {d.desire}: {', '.join(d.customer_language[:2])}"
        for d in avatar.desires[:3]
    )
    frameworks_text = "\n".join(f"  - {f}" for f in frameworks)

    prompt = ANGLE_PROMPT.format(
        count=count,
        diversity_matrix=_diversity_matrix_text(matrix),
        frameworks=frameworks_text,
        product_name=product.name,
        product_description=product.description,
        benefits=", ".join(product.benefits[:5]),
        mechanism=product.unique_mechanism or "Not specified",
        social_proof=", ".join(product.social_proof[:3]) or "None provided",
        demographic=avatar.demographic,
        pain_points=pain_summary or "Not specified",
        desires=desire_summary or "Not specified",
        objections=", ".join(avatar.objections[:3]) or "Not specified",
        awareness_level=avatar.awareness_level,
        language_patterns=", ".join(avatar.language_patterns[:3]) or "casual and direct",
        psychology_block=psychology_block,
        brand_tone=brand.tone,
        approach=awareness_strategy.get("approach", ""),
        competitive_gaps_section=_format_competitive_gaps(competitive_gaps),
    )

    result = claude_complete(prompt, system=ANGLE_SYSTEM)
    result = result.strip()
    if result.startswith("```"):
        result = result.split("\n", 1)[1]
    if result.endswith("```"):
        result = result.rsplit("```", 1)[0]

    parsed = yaml.safe_load(result)
    return parsed.get("angles", [])
