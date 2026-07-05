"""Build the secondkind-bold-context SKILL.md file from Phase 1 artifacts.

Writes the same file to two locations:
1. ~/.claude/skills/secondkind-bold-context/SKILL.md
2. clients/secondkind-bold/exports/secondkind-bold-context/SKILL.md
"""

import os
import yaml

BASE = "clients/secondkind-bold"


def read_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    # Build the brief summary table data
    brief_dir = os.path.join(BASE, "briefs")
    briefs = []
    for f in sorted(os.listdir(brief_dir)):
        if not f.endswith(".yaml"):
            continue
        with open(os.path.join(brief_dir, f), "r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        hook = (d.get("hook", "") or "").strip().replace("\n", " ").replace("|", "/")
        briefs.append(
            {
                "id": d.get("brief_id", "")[-6:],
                "persona": d.get("persona", ""),
                "awareness": d.get("awareness_level", ""),
                "hook_type": d.get("hook_type", ""),
                "slot": d.get("slot", ""),
                "framework": d.get("framework", ""),
                "hook_preview": hook[:80],
            }
        )
    briefs.sort(key=lambda b: (b["persona"], b["slot"]))

    # Discover archetypes
    archetype_dir = os.path.join(BASE, "reference_ads", "analyses")
    archetype_order = [
        "testimonial-review",
        "ugc",
        "before-and-after",
        "editorial",
        "facts-stats",
        "features-benefits",
        "headline",
        "media-press",
        "promotion-discount",
        "reasons-why",
        "ai-unique",
        "us-vs-them",
    ]
    archetypes = {}
    for a in archetype_order:
        d = os.path.join(archetype_dir, a)
        if os.path.isdir(d):
            files = sorted(
                [
                    f
                    for f in os.listdir(d)
                    if f.endswith(".yaml") and not f.startswith("_")
                ]
            )
            archetypes[a] = files
        else:
            archetypes[a] = []

    # Read source files
    brand_yaml = read_file(os.path.join(BASE, "brand.yaml"))

    brand_context = read_file(os.path.join(BASE, "brand-context.md"))
    bc_lines = brand_context.split("\n")
    if bc_lines[0].startswith("# "):
        brand_context = "\n".join(bc_lines[1:]).lstrip("\n")

    avatars_index = read_file(os.path.join(BASE, "avatars", "_index.yaml"))
    idx = yaml.safe_load(avatars_index)

    persona_contents = []
    for p in idx["personas"]:
        pid = p["id"]
        fname = f"{pid}.yaml"
        persona_yaml = read_file(os.path.join(BASE, "avatars", fname))
        pdata = yaml.safe_load(persona_yaml)
        has_psych = pdata.get("psychology_profile") is not None
        persona_contents.append(
            {
                "name": p["name"],
                "role": p["role"],
                "yaml": persona_yaml,
                "has_psych": has_psych,
            }
        )

    gut_balance_yaml = read_file(os.path.join(BASE, "products", "gut-balance.yaml"))
    offers_yaml = read_file(os.path.join(BASE, "offers.yaml"))
    competitors_yaml = read_file(os.path.join(BASE, "competitors.yaml"))

    competitive_gaps_md = read_file(
        os.path.join(BASE, "research", "competitive-gaps.md")
    )
    cg_lines = competitive_gaps_md.split("\n")
    if cg_lines[0].startswith("# "):
        competitive_gaps_md = "\n".join(cg_lines[1:]).lstrip("\n")

    strategy_matrix_md = read_file(os.path.join(BASE, "strategy-matrix.md"))
    sm_lines = strategy_matrix_md.split("\n")
    if sm_lines[0].startswith("# "):
        strategy_matrix_md = "\n".join(sm_lines[1:]).lstrip("\n")

    creative_strategy_md = read_file(os.path.join(BASE, "creative-strategy.md"))
    cs_lines = creative_strategy_md.split("\n")
    start_idx = 0
    for i, line in enumerate(cs_lines):
        if line.startswith("## Executive Summary"):
            start_idx = i
            break
    creative_strategy_md = "\n".join(cs_lines[start_idx:])

    voc_yaml = read_file(os.path.join(BASE, "voc", "extracted_pains.yaml"))
    trending_yaml = read_file("trending_formats.yaml")

    parts = []

    parts.append(
        '---\n'
        'name: secondkind-bold-context\n'
        'description: Loads complete strategic context for SecondKind Bold (postbiotic gut-health brand). '
        'Includes brand essentials, 6 personas with full psychology profiles, products, offers, '
        'competitive landscape, the 30-cell strategy matrix (6 personas × 5 awareness stages), '
        'competitive gaps, brief summaries, creative strategy doc with the 4 mental stages + '
        '9 psychology heuristics + V×I quadrants + 4 paired-mechanism patterns + 4 biggest levers + '
        'rules of engagement, VoC corpus, reference ad archetype library, and trending format library. '
        'Use when working on any creative for SecondKind Bold — ad copy, scripts, social posts, '
        'hooks, concepts, shoot direction, landing pages. Self-contained — no AdCreatives repo or '
        'API keys required.\n'
        '---\n\n'
        '# SecondKind Bold — Complete Strategy Context\n\n'
        '## How to use this context\n\n'
        'You are operating as a creative director / content strategist for **SecondKind Bold** — '
        'the bold/challenger voice variant of the SecondKind postbiotic gut-health brand. The full '
        'strategic context is embedded below: brand essentials, brand-voice rules, six personas with '
        'their psychological profiles, the Gut Balance product, offers, competitive landscape, '
        'the 30-cell strategy matrix, the synthesized creative strategy, voice-of-customer corpus, '
        'reference ad archetype library, and trending format library.\n\n'
        'When the user asks you to make anything — ad copy, scripts, hooks, social posts, '
        'concepts, shoot direction, landing pages, email — pull directly from this context and '
        'cite the section you\'re drawing from (e.g., "Pulling Danielle\'s pain about end-of-day '
        'bloating from the Personas section…"). Do not paraphrase the brand voice into '
        'something more polished than the brand actually sounds — the confrontational, '
        'declarative, science-armed register is the strategic asset. Match it.\n\n'
        'When the user asks for something this context doesn\'t cover, say so explicitly rather '
        'than fabricate. The whole point of this context is that you have the same evidence base '
        'the original strategist had — don\'t drift outside it.\n\n'
        '---\n\n'
        '## Brand essentials\n\n'
        '```yaml\n'
    )
    parts.append(brand_yaml.rstrip("\n"))
    parts.append("\n```\n\n---\n\n## Brand context\n\n")
    parts.append(brand_context.rstrip("\n"))
    parts.append("\n\n---\n\n## Personas\n\n")

    for p in persona_contents:
        role_str = p["role"]
        parts.append(f"### {p['name']} ({role_str})\n\n")
        if not p["has_psych"]:
            parts.append(
                "> **Note:** This persona has `psychology_profile: null` — heuristic "
                "guardrails (dominant heuristics, weak heuristics, emotional position, "
                "recommended pairings) are NOT included. Use other personas with full "
                "profiles as the reference when in doubt about creative direction for "
                "this persona.\n\n"
            )
        parts.append("```yaml\n")
        parts.append(p["yaml"].rstrip("\n"))
        parts.append("\n```\n\n")

    parts.append("---\n\n## Products\n\n### Gut Balance\n\n```yaml\n")
    parts.append(gut_balance_yaml.rstrip("\n"))
    parts.append("\n```\n\n---\n\n## Offers\n\n```yaml\n")
    parts.append(offers_yaml.rstrip("\n"))
    parts.append(
        "\n```\n\n---\n\n## Competitive landscape\n\n### Competitors\n\n```yaml\n"
    )
    parts.append(competitors_yaml.rstrip("\n"))
    parts.append("\n```\n\n### Exploitable gaps\n\n")
    parts.append(competitive_gaps_md.rstrip("\n"))
    parts.append("\n\n---\n\n## Strategy matrix\n\n")
    parts.append(strategy_matrix_md.rstrip("\n"))
    parts.append("\n\n---\n\n## Brief summaries\n\n")
    parts.append(
        "| Brief ID | Persona | Awareness | Hook type | Slot | Framework | Hook (first 80 chars) |\n"
    )
    parts.append("|---|---|---|---|---|---|---|\n")
    for b in briefs:
        parts.append(
            f"| {b['id']} | {b['persona']} | {b['awareness']} | {b['hook_type']} | "
            f"{b['slot']} | {b['framework']} | {b['hook_preview']} |\n"
        )
    parts.append(
        "\n> Full brief YAMLs are in the AdCreatives repo at "
        "`clients/secondkind-bold/briefs/`. Ask the sender for any specific brief you "
        "want in full.\n\n"
    )

    parts.append("---\n\n## Creative strategy synthesis\n\n")
    parts.append(creative_strategy_md.rstrip("\n"))
    parts.append("\n\n---\n\n## Voice of customer (VoC) corpus\n\n")
    parts.append(
        "**Caveat — read before relying on this corpus.** This VoC corpus has known "
        "bias: 222 of 299 comments were discarded as score-1 noise (emoji reactions, "
        "one-word affirmations, off-topic tangents); only 6 of 247 comments in the largest "
        "set scored 4–5; zero comments in the TikTok set scored 5; and the sample "
        "skews heavily toward engaged brand followers (detractors and churned customers "
        "are underrepresented). Treat every confidence rating as one tier lower than "
        "labeled, and lean on the cancellation quotes in the **Exploitable gaps** section "
        "(under Competitive landscape) as the primary VoC evidence for ad copy decisions. "
        "Use this corpus for directional color, real customer language patterns, and "
        "money-quote inspiration — not as the sole basis for any persona or "
        "messaging decision.\n\n"
    )
    parts.append("```yaml\n")
    parts.append(voc_yaml.rstrip("\n"))
    parts.append("\n```\n\n---\n\n## Reference ad archetype library\n\n")
    parts.append(
        "This brand has 86 reference ads analyzed across 12 archetype categories. Use this "
        "library to find structural inspiration when designing new creative — every "
        "archetype below has been broken down into its hook, visual format, creative "
        "mechanic, and emotional mood in the corresponding analysis YAMLs.\n\n"
        "### Archetype categories and when each works for SecondKind Bold\n\n"
    )

    archetype_when = {
        "testimonial-review": (
            "Works best for **Evaluation-stage** creative — once the mechanism is "
            "established, a single customer voice in the persona's register (e.g., a "
            "Danielle-coded postpartum-mom Q&A, or an Isaac-coded male peer reporting "
            "fewer sick weeks) carries social proof without violating the no-influencer "
            "rule. Skip generic star aggregates; SK's audience filters those out."
        ),
        "ugc": (
            "Strong for **Trigger and Exploration** stages, especially Danielle and "
            "Natalie. Phone-shot intimate aesthetic, mom-to-mom for Natalie, "
            "peer-to-peer for Danielle. Never polished-influencer UGC — that "
            "pattern-matches to the hype the bold voice rejects."
        ),
        "before-and-after": (
            "**Conditional use only.** Allowed for Danielle (bloating, owned in her own "
            "language). **Off-limits for Natalie** (postpartum body is sacred ground per "
            "brand rules). For Paul, before/after of patient outcomes only, never personal "
            "body. The 'before' must be a felt experience (bloated by 7pm, foggy by 10am), "
            "not a body silhouette."
        ),
        "editorial": (
            "**Highest-affinity archetype for this brand.** Editorial-minimalism is the "
            "visual signature — Kinfolk-meets-apothecary, F37 Caslon Condensed serif "
            "headlines on snow-white backgrounds. Use this archetype as the default register "
            "for vindication statics, mechanism reveals, and the 'literature ahead of "
            "practice' hooks for Paula and Paul."
        ),
        "facts-stats": (
            "Mandatory architecture for **Exploration and Evaluation** stages. The 70% "
            "transit-mortality stat, the EpiCor 17%, the Bereum 84-day study — these "
            "are the brand's strongest receipts and must appear visually as data, not as "
            "marketing claims. Bold numerical callouts on dark or snow-white backgrounds. "
            "Especially powerful for Brandon, Isaac, Paul."
        ),
        "features-benefits": (
            "Use sparingly and only at **Evaluation/Purchase**. The brand explicitly "
            "avoids 'better probiotic' feature framing. When used, the feature must be a "
            "structural delivery distinction (already-active compounds, no survival "
            "required, no colonization needed) — not generic supplement claims."
        ),
        "headline": (
            "The brand's most native archetype. Typography-only statics carrying the "
            "load-bearing claims — *'You weren't wrong. The product was.'* / *'Stop "
            "swallowing corpses.'* / *'Probiotics are dead bacteria.'* F37 Caslon "
            "Condensed, tight kerning, sentence case, no effects. Best for Trigger and "
            "Exploration."
        ),
        "media-press": (
            "Strong for **Evaluation-stage** trust-building. The brand has CBS, NBC, USA "
            "Today, Daily Mail press. Editorial advertorial format — looks like a "
            "wellness column, reads like one, lands the mechanism explanation without "
            "sounding like an ad. Especially powerful for Paula (literature-ahead-of-"
            "practice frame)."
        ),
        "promotion-discount": (
            "**Use minimally and never as the lead.** Per brand rules: operational claims "
            "close, they don't open. The 60-day money-back guarantee belongs at **Purchase "
            "stage only**. The 30% first-purchase discount is acquisition-only — "
            "never sitewide, never as a sale frame. Never lead a static with a discount."
        ),
        "reasons-why": (
            "Listicle / numbered format. Works well for Brandon (his analytical register) "
            "and Paul (clinical brief format). Negative framing — *'3 reasons your "
            "probiotic isn't doing anything (it's not what you think)'* — outperforms "
            "positive listicles for this cohort because it matches their skeptic posture."
        ),
        "ai-unique": (
            "Includes the 'Obvious AI Slop' format (animated probiotic dramatically dying "
            "in transit). High-risk / high-reward — works only when the cringe lands "
            "the mechanism (the 70% death rate) viscerally. The category indictment is "
            "delivered through entertainment, sidestepping skepticism. Test with caution; "
            "can read off-brand if the cringe overwhelms the diagnosis."
        ),
        "us-vs-them": (
            "Use category-level only — *never name competitor brands.* The 'them' is "
            "the live-bacteria delivery model, the CFU arms race, the probiotic-industrial "
            "complex. The 'us' is postbiotics-as-already-active. Split-screen "
            "problem/solution statics are native to this — works across Brandon, "
            "Danielle, Paula."
        ),
    }

    for a in archetype_order:
        desc = archetype_when.get(a, "")
        parts.append(f"#### {a}\n\n{desc}\n\n**Examples in library:**\n")
        files = archetypes.get(a, [])
        if not files:
            parts.append("- (no examples in this archetype)\n")
        for fn in files:
            parts.append(f"- `{fn}`\n")
        parts.append("\n")

    parts.append(
        "Full analyses live in `clients/secondkind-bold/reference_ads/analyses/"
        "<archetype>/` in the AdCreatives repo. The raw reference images are gitignored "
        "— ask the sender if you need them.\n\n---\n\n"
        "## Trending format library\n\n"
        "These are time-bound — what's trending now will fade. Use them as inspiration "
        "for video/static alternatives you can produce in parallel to a primary static ad. "
        "Each format has a `best_when` block that scores its fit against a creative "
        "concept:\n\n"
        "- `awareness_levels` — Schwartz stages where this format works\n"
        "- `persona_types` — free-form persona tags it resonates with\n"
        "- `product_categories` — categories it fits (or `any`)\n\n"
        "**Scoring rubric for picking a trending format for a new piece of content:** "
        "score each candidate by:\n\n"
        "- +2 if your piece's awareness stage (or the persona's stage) is in "
        "`best_when.awareness_levels`\n"
        "- +1 per persona token from `best_when.persona_types` that appears in your target "
        "persona description\n"
        "- +1 if `best_when.product_categories` includes `any`\n\n"
        "Take the top 5 by score, then pick the rank-1 by which one most directly maps to "
        "your concept's angle and hook type. For each pick, write a 1–2 sentence "
        "rationale explaining why this format fits THIS piece (cite specific persona traits "
        "or the angle), and a 1-sentence production note on what to be careful about "
        "producing this format for the SecondKind Bold brand specifically.\n\n"
        "```yaml\n"
    )
    parts.append(trending_yaml.rstrip("\n"))
    parts.append("\n```\n\n---\n\n")

    parts.append(
        "## How to write new content for this brand\n\n"
        "The brief set in the **Brief summaries** section above was built with a specific "
        "discipline. The same methodology applies when you're writing **anything** for "
        "SecondKind Bold — paid ad scripts, organic social posts, TikTok hooks, "
        "LinkedIn captions, landing-page sections, email subject lines, founder-voice "
        "voiceovers. The medium changes; the strategic spine does not.\n\n"
        "### Step 1 — Pick a persona and awareness stage\n\n"
        "Open the **Strategy matrix** section. Each of the 30 cells (6 personas × 5 "
        "awareness stages) has a defined angle, gap-to-fill, hook style, framework, "
        "creative mechanic, and proof to surface. Pick the cell you're writing for. Don't "
        "drift — if the persona is `problem_aware`, language stays at the problem "
        "level (the customer doesn't yet know \"postbiotic\" as a category word).\n\n"
        "### Step 2 — Pick a slot from the Hook Diversity Matrix\n\n"
        "Each piece in a content set must occupy a different cognitive slot. This forces "
        "variety on the psychological lever, not just the phrasing.\n\n"
        "| Slot | Hook Type | Emotional Trigger |\n"
        "|---|---|---|\n"
        "| 1 | Surprising Stat | Social Proof / Credibility |\n"
        "| 2 | Story / Result | Empathy + Relief |\n"
        "| 3 | FOMO / Urgency | Loss Aversion |\n"
        "| 4 | Curiosity Gap | Intrigue |\n"
        "| 5 | Direct Address / Call-out | Recognition |\n"
        "| 6 | Contrast / Enemy | Differentiation |\n"
        "| 7 | Question | Self-reference |\n"
        "| 8 | Pattern Interrupt | Pattern break |\n"
        "| 9 | Controversial | Polarization |\n"
        "| 10 | Problem-Solution | Pain → relief |\n\n"
        "Look at the **Brief summaries** table — the `Slot` column tells you which "
        "slots are already covered for each persona. Aim for slots that aren't used yet, "
        "OR write variations within the same slot tuned to a different persona.\n\n"
        "**Important for this brand:** Slot 3 (FOMO/Urgency) is **categorically "
        "off-limits** — scarcity and time-pressure are weak heuristics across all six "
        "personas and violate the editorial brand voice. Skip slot 3 entirely.\n\n"
        "If the persona has a `psychology_profile` block (look for it on the persona YAML "
        "in the Personas section), drop any slots whose primary heuristics appear in the "
        "persona's `weak_heuristics` list. Don't write a \"Surprising Stat\" hook for a "
        "persona who isn't moved by authority bias.\n\n"
        "### Step 3 — Source the hook from real persona language\n\n"
        "Open the chosen persona's YAML and find a `customer_language` quote that maps to "
        "the pain or desire your slot frames. The hook should feel like that customer "
        "speaking, not like a copywriter writing about that customer.\n\n"
        "The `hook_source` field on a brief captures this: `\"Pain: '<verbatim pain quote>' "
        "— Desire: '<verbatim desire quote>'\"`. If you can't fill that with verbatim "
        "quotes from the persona, the hook isn't grounded yet — go back to the "
        "persona file. For social posts and short-form, the verbatim line often **is** "
        "the hook.\n\n"
        "### Step 4 — Pick a creative mechanic and visual format\n\n"
        "The strategy matrix cell already suggests one mechanic + one visual format. You "
        "can swap to another if the slot calls for it (e.g., Slot 4 Curiosity Gap pairs "
        "naturally with \"Talking Head Confession\" or \"Open Loop B-roll\", not with a "
        "static product hero). If you have access to the `creative-mechanics` and "
        "`visual-formats` skills, consult them. Otherwise, use the mechanic that already "
        "showed up in similar briefs in the **Brief summaries** table.\n\n"
        "### Step 5 — Apply the gap map\n\n"
        "Look at the **Exploitable gaps** section under Competitive landscape. At least "
        "half of any new content set should target a specific gap — that's where the "
        "brand wins on the merits. Reference the gap's `Our advantage` content as proof. "
        "Apply the hard rule: **never name competitors.** Abstract to category (\"the "
        "probiotics you've tried,\" \"the live-bacteria model,\" \"billions of CFUs nobody "
        "can decode\") or to mechanism (\"the survival lottery,\" \"the colonization "
        "step\").\n\n"
        "### Step 6 — Pick top 3 trending formats (optional)\n\n"
        "Score each format in the **Trending format library** section against your new "
        "piece using the rubric in that section. Top 3 by score are your shortlist; pick "
        "rank-1 by which one most directly maps to your concept's angle and hook type. "
        "For each pick, write rationale + production note.\n\n"
        "This is informational — trending picks suggest parallel video/static "
        "executions to test alongside the primary creative. They don't change the primary "
        "work.\n\n"
        "### Step 7 — Validate against the operating rules below\n\n"
        "Before shipping, run the piece against the **Operating rules** section. If any "
        "rule is violated, fix the upstream creative choice — don't band-aid the "
        "output.\n\n"
        "### Optional: enhancing skills\n\n"
        "If the recipient's Claude Code environment has these Anthropic skills available, "
        "the work gets sharper:\n\n"
        "| Skill | Use it for |\n"
        "|---|---|\n"
        "| `hook-writing` | Composing the actual hook line with psychological precision |\n"
        "| `hook-tactics` | Reference library of 35+ tactical hook formats |\n"
        "| `hook-voice-patterns` | Native-feed sentence structures that stop the scroll |\n"
        "| `creative-mechanics` | Structural patterns connecting hook + visual + narrative |\n"
        "| `visual-formats` | 45+ Meta/paid social visual format options |\n"
        "| `creative-strategy-engine` | Mapping pain × persona × awareness systematically |\n"
        "| `copywriting` | Production-ready ad copy in brand voice |\n"
        "| `content-engine` | Platform-native repurposing (X, LinkedIn, TikTok, YouTube, newsletter) |\n\n"
        "These are not required — the methodology above stands on its own. But if "
        "available, they make Claude's writing tighter.\n\n"
        "---\n\n"
        "## Operating rules\n\n"
        "These are not style preferences — they are load-bearing strategy. Every "
        "piece of content for SecondKind Bold obeys them.\n\n"
        "### Always\n\n"
        "- **Validate her experience before pitching.** Open with the suspicion she "
        "already had; the product enters after.\n"
        "- **Lead with the mechanism failure.** The 70% transit-mortality stat is the "
        "brand's most powerful opening move.\n"
        "- **Pair every claim with a receipt in the next line.** Study name, duration, "
        "named outcome. Never a claim without a citation.\n"
        "- **Hold the four-beat arc on every piece.** Name the suspicion → diagnose "
        "the mechanism → vindicate her → convert with the offer.\n"
        "- **Lead with outcome; ingredient names are receipts, not headlines.** "
        "Exceptions: Brandon and Paul pattern-match positively on patented names (EpiCor, "
        "Bereum, Totipro) as authority signals; use them in body copy for those two "
        "personas.\n"
        "- **Match register to persona.** Six personas, six registers. Don't write one "
        "ad for \"the gut-health audience.\"\n"
        "- **Sentence case only.** No ALL CAPS, no drop shadows, no outlined text, no "
        "expanded type.\n"
        "- **F37 Caslon Condensed (headlines) + Neue Montreal (body) only.** Tight "
        "kerning (-2) on Caslon.\n"
        "- **Include the 60-day money-back guarantee at Purchase stage.** Never as a "
        "lead, always as the close.\n"
        "- **FDA structure-function compliance.** \"Helps support,\" \"may help,\" "
        "\"supports\" live in fine print only, never in headlines.\n\n"
        "### Never\n\n"
        "- **Never frame as \"a better probiotic.\"** The brand is the categorical "
        "alternative to a broken delivery model, not a better entrant inside it.\n"
        "- **Never name competitors by brand.** Not Seed, not Arrae, not Ritual, not "
        "Garden of Life. Category-level indictment only (\"the probiotics you've tried,\" "
        "\"the live-culture model,\" \"the CFU arms race,\" \"proprietary blends nobody "
        "can decode\").\n"
        "- **Never mock the customer's past purchases.** The cut lands on the industry or "
        "the mechanism, never on her.\n"
        "- **Never bash doctors or the medical establishment.** Frame as \"literature "
        "ahead of practice\" — Practitioner Paul is a target persona.\n"
        "- **Never lead with operational claims.** 60-day guarantee, refund, subscription "
        "flex — these close, they don't open. Lead with mechanism.\n"
        "- **Never use aesthetic / body-appearance framing for Natalie.** The postpartum "
        "body is sacred ground. Name function (gut, bloat, fog), never form.\n"
        "- **Never use scarcity, urgency, or countdown timers.** Weak heuristic across "
        "all six personas; pattern-matches to hype the cohort already filtered out.\n"
        "- **Never use puffery or wellness-cheese.** No \"miracle,\" \"magical,\" "
        "\"revolutionary,\" \"life-changing,\" \"game-changer,\" \"amazing,\" "
        "\"incredible,\" \"mind-blowing,\" \"transform your,\" \"journey,\" \"ritual,\" "
        "\"find your best self,\" \"unlock your,\" \"embrace your,\" \"begin your,\" "
        "\"wellness lifestyle,\" \"holistic.\"\n"
        "- **Never lead a hook with a patented ingredient name** for Danielle, Natalie, "
        "Paula, or most of Isaac's surface area — reads as marketing jargon and "
        "triggers the exact skepticism we're working to disarm.\n"
        "- **Never compete on price.** The argument is mechanism, not cost.\n"
        "- **Never use rhetorical questions or clickbait** (\"What if everything you knew "
        "about probiotics was wrong?\"). We don't ask, we tell.\n\n"
        "The safe zone: keep the cut on the category, never on the customer. That's both "
        "the policy and the conversion lever.\n\n"
        "---\n\n"
        "## Phasing and scope\n\n"
        "This skill loads context for a **paid-acquisition conversion test** of the bold "
        "voice — not a brand-level reset. The polite voice (in the sibling "
        "`secondkind/` workspace) operates on the main site, email, PR, and packaging. "
        "The bold voice operates only where it has to fight for attention against the "
        "scroll.\n\n"
        "### Phase 1 (current scope — what this context is for)\n\n"
        "- Paid acquisition (Meta, TikTok)\n"
        "- Dedicated bold landing pages\n"
        "- The main site stays measured under the polite voice\n"
        "- This is a **conversion test of the voice**, not a brand-level reset\n\n"
        "### Phase 2 (post-validation)\n\n"
        "- Manifesto page on the main site\n"
        "- Founder origin video\n"
        "- Homepage hero migrates to bold voice\n"
        "- Some bold language enters email and CRM\n\n"
        "### Phase 3 (optional — voice unification)\n\n"
        "- Packaging refresh in the bold register\n"
        "- PR and earned-media voice unification\n"
        "- Whole-brand voice migration\n\n"
        "When writing content, default to **Phase 1 scope** unless the user explicitly "
        "says they're working on a Phase 2 or Phase 3 surface. A bold-voice headline that's "
        "right for a Meta ad may be too sharp for a packaging label.\n\n"
        "---\n\n"
        "*Generated 2026-05-23 from clients/secondkind-bold/ Phase 1 artifacts and the "
        "creative-strategy.md synthesis. Re-generate this skill if the underlying strategy "
        "is updated.*\n"
    )

    full = "".join(parts)

    out1 = "C:/Users/ReadyPlayerOne/.claude/skills/secondkind-bold-context/SKILL.md"
    out2 = (
        "C:/Users/ReadyPlayerOne/AdCreatives/clients/secondkind-bold/"
        "exports/secondkind-bold-context/SKILL.md"
    )
    os.makedirs(os.path.dirname(out1), exist_ok=True)
    os.makedirs(os.path.dirname(out2), exist_ok=True)

    with open(out1, "w", encoding="utf-8") as f:
        f.write(full)
    with open(out2, "w", encoding="utf-8") as f:
        f.write(full)

    sz = os.path.getsize(out1)
    lc = full.count("\n") + 1
    print("OK")
    print(f"Path 1: {out1}")
    print(f"Path 2: {out2}")
    print(f"Size: {sz:,} bytes")
    print(f"Lines: {lc:,}")
    print(f"Personas: {len(persona_contents)}")
    print(f"Briefs in table: {len(briefs)}")


if __name__ == "__main__":
    main()
