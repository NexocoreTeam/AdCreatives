"""AdCreatives dashboard — Streamlit web app.

Local-only by default. Run from the repo root:
    streamlit run dashboard/app.py
Or via the CLI wrapper:
    adc dashboard

Two views:
    1. Overview — grid of all clients with status traffic-lights + cost-this-month
    2. Client detail — deep view of one client (status / briefs / ads / gaps / psychology)

Reads the same files the CLI status command reads. No data is sent anywhere.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

# Ensure repo root is on the path when Streamlit launches the file directly
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from strategy.cost_tracker import (  # noqa: E402
    read_costs,
    recent_entries,
    total_all_time,
    total_for_month,
)
from strategy.status_dashboard import (  # noqa: E402
    ad_assets_status,
    build_recommendations,
    competitive_research_status,
    strategy_status,
)

CLIENTS_DIR = REPO_ROOT / "clients"
AI_ADS_DIR = REPO_ROOT / "ai-ads"


# ───────────────────────────────────────────────────────────────────────────
# Plain-English glossaries — psychology jargon translated for non-specialists
# ───────────────────────────────────────────────────────────────────────────
# Used in the Psychology tab to display a short definition under each
# heuristic / pairing name. Anyone reading the brief should be able to act
# on it without prior buyer-psychology training.

HEURISTIC_GLOSSARY: dict[str, str] = {
    "scarcity":
        "Limited supply, time, or availability makes things feel more valuable. "
        "Triggered by 'only 12 left', 'ends midnight', 'this batch only'.",
    "social_proof":
        "People copy what similar others are doing. Reviews, ratings, 'as seen on', "
        "'10k+ customers', user-generated content — all activate this.",
    "authority_bias":
        "Trust signals from experts, credentials, or recognized institutions. "
        "Doctor / PhD endorsements, clinical studies, named research compounds.",
    "effect_heuristic":
        "Buying decisions driven by gut-level emotional reaction, not analytical "
        "comparison. The vibe / aesthetic / feeling of the product matters more "
        "than the spec sheet.",
    "processing_fluency":
        "Easy-to-process content feels more true. Clean design, plain language, "
        "familiar layouts. Confusing copy reads as dishonest copy.",
    "temporal_discounting":
        "Immediate rewards beat future rewards in the buyer's mind. 'Feel it in "
        "two weeks' wins over 'long-term gut health'. Speed matters.",
    "salience_bias":
        "Whatever is most vivid, visible, or surprising gets weighted heaviest. "
        "Pattern-interrupt hooks, bold colors, unexpected angles — all designed "
        "to hijack attention.",
    "goal_gradient":
        "Motivation rises as people get closer to a goal. Progress bars, "
        "step-by-step protocols, 'you're almost there' framing — all push action "
        "as the finish line approaches.",
    "framing_effect":
        "How something is presented changes how it's judged. '90% lean' vs '10% "
        "fat' — same fact, opposite reactions. Word choice and reference points "
        "shape perception.",
}

PAIRING_GLOSSARY: dict[str, str] = {
    "first_principles_plus_loss_aversion":
        "Explain the mechanism from the ground up + show what they lose by not "
        "switching. Combines understanding with urgency to avoid regret.",
    "status_signaling_plus_open_loop":
        "Aspirational identity + a story or claim left unfinished. The buyer "
        "stays engaged to find out 'who am I if I use this?'",
    "curiosity_plus_reverse_psychology":
        "Plant intrigue + 'this isn't for everyone'. Self-qualifies the buyer "
        "and amplifies wanting via implied exclusivity.",
    "shock_factor_plus_transformation_shortcut":
        "Dramatic before/after + quick-path promise. High attention, low "
        "credibility — often reads as TikTok-y or miracle-pill territory.",
    "tribal_belonging_plus_vulnerability":
        "'People like you' framing + honest confession of a shared struggle. "
        "Creates kinship through admitting the pain out loud.",
    "pattern_disruption_plus_hidden_truth":
        "Break the expected pattern + reveal an industry secret. 'You've been "
        "told X. Here's what's actually true.'",
    "what_if_scenario_plus_pain_amplification":
        "Walk the buyer through a hypothetical worst case + dwell on the pain. "
        "Future-pacing the consequences of doing nothing.",
    "contrast_plus_aspirational_identity":
        "Side-by-side contrast (old vs new approach) + the future self this "
        "unlocks. Comparison + identity in one frame.",
    "gamification_plus_time_sensitive_offer":
        "Game mechanics (badges, streaks, points) + countdown urgency. Often "
        "reads as cheap or manipulative for premium audiences.",
    "anonymity_plus_social_proof":
        "Anonymous testimonials + crowd validation. Lower-stakes social proof — "
        "no celebrity dependency, just collective signal.",
    "authority_borrowing_plus_data_insight":
        "Expert endorsement + a specific, verifiable statistic. Doctor + 92% — "
        "credentialed source paired with a number.",
    "micro_story_plus_suspense":
        "Short personal story + cliffhanger or unresolved tension. Story keeps "
        "them watching; suspense delays the payoff.",
    "counterintuitive_insight_plus_specificity":
        "Surprising claim + precise detail that makes it credible. 'Postbiotics "
        "skip the live-bacteria step entirely' + named compounds and doses.",
    "reframing_perception_plus_emotional_trigger":
        "Change the way they think about the problem + emotional hit. 'It's not "
        "your willpower — it's your microbiome' lands harder than dieting advice.",
}


def _glossary_caption(name: str, glossary: dict[str, str]) -> str | None:
    """Return the plain-English definition for a heuristic / pairing name."""
    return glossary.get(name)


# ───────────────────────────────────────────────────────────────────────────
# Page config
# ───────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AdCreatives Dashboard",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _list_clients() -> list[str]:
    if not CLIENTS_DIR.exists():
        return []
    return sorted(
        d.name for d in CLIENTS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "brand.yaml").exists()
    )


def _brand_name(client: str) -> str:
    brand_yaml = CLIENTS_DIR / client / "brand.yaml"
    if not brand_yaml.exists():
        return client
    try:
        b = yaml.safe_load(brand_yaml.read_text(encoding="utf-8")) or {}
        return b.get("name", client)
    except Exception:
        return client


# ───────────────────────────────────────────────────────────────────────────
# Subprocess action runner (for action buttons)
# ───────────────────────────────────────────────────────────────────────────


def run_adc_command(cmd_args: list[str], label: str = "Running...") -> tuple[int, str]:
    """Execute an `adc` CLI command, stream output to the UI, return (returncode, full_output).

    Streams stdout/stderr live so long-running commands don't appear frozen.
    """
    full_cmd = [sys.executable, "-u", str(REPO_ROOT / "cli.py")] + cmd_args
    # Force the child Python to flush stdout line-by-line. Without this,
    # piped stdout is block-buffered (~8KB) and the dashboard log appears
    # frozen for the entire LLM call.
    child_env = {**os.environ, "PYTHONUNBUFFERED": "1"}
    log_lines: list[str] = []

    with st.status(label, expanded=True) as status:
        try:
            proc = subprocess.Popen(
                full_cmd,
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                # Force UTF-8 decoding so non-ASCII output (em-dashes, curly
                # quotes, etc. emitted by Rich or by the LLM) doesn't crash
                # on Windows where the default subprocess encoding is cp1252.
                encoding="utf-8",
                errors="replace",
                env=child_env,
            )
        except Exception as e:
            status.update(label=f"Failed to launch: {e}", state="error")
            return -1, str(e)

        log_container = st.empty()
        assert proc.stdout is not None
        for line in proc.stdout:
            log_lines.append(line.rstrip())
            # Keep just the last 30 lines visible
            log_container.code("\n".join(log_lines[-30:]))
        rc = proc.wait()
        if rc == 0:
            status.update(label=f"Done: {label}", state="complete")
        else:
            status.update(label=f"Failed (exit {rc}): {label}", state="error")

    if rc != 0:
        # Halt the script run so the caller's st.rerun() never fires.
        # Without this, the error status box (with the traceback) is
        # erased before the user can read it.
        st.error(
            f"Command failed with exit code {rc}. "
            "Expand the status box above to see the full traceback."
        )
        st.stop()
    return rc, "\n".join(log_lines)


# ───────────────────────────────────────────────────────────────────────────
# View 1: Multi-client overview
# ───────────────────────────────────────────────────────────────────────────


def _stage_score(stages) -> tuple[int, int]:
    done = sum(1 for s in stages if s.done)
    total = len(stages)
    return done, total


def _traffic_light(done: int, total: int) -> str:
    if total == 0:
        return "⚪"
    ratio = done / total
    if ratio >= 1.0:
        return "🟢"
    if ratio >= 0.5:
        return "🟡"
    return "🔴"


def render_overview(clients: list[str]):
    st.title("🎯 AdCreatives — All Clients")
    st.caption(f"{len(clients)} client(s) onboarded")

    # Aggregate KPIs across all clients
    total_clients = len(clients)
    total_briefs = 0
    total_ads = 0
    total_cost_month = 0.0
    total_cost_all_time = 0.0
    for c in clients:
        assets = ad_assets_status(c)
        for s in assets:
            if s.name == "Briefs":
                total_briefs += _safe_count(s.summary)
            elif s.name == "Generated ad images":
                total_ads += _safe_count(s.summary)
        total_cost_month += total_for_month(c)
        total_cost_all_time += total_all_time(c)

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Clients", total_clients)
    kpi_cols[1].metric("Total briefs", total_briefs)
    kpi_cols[2].metric("Total ads", total_ads)
    kpi_cols[3].metric(
        f"Spent {datetime.now().strftime('%b %Y')}",
        f"${total_cost_month:.2f}",
        delta=f"${total_cost_all_time:.2f} all-time",
        delta_color="off",
    )

    st.divider()

    # Per-client cards
    if not clients:
        st.warning("No clients found. Run `adc init-client --name <slug>` first.")
        return

    rows = []
    for c in clients:
        strat = strategy_status(c)
        comp = competitive_research_status(c)
        assets = ad_assets_status(c)
        recs = build_recommendations(c, strat, comp, assets)

        s_done, s_total = _stage_score(strat)
        c_done, c_total = _stage_score(comp)
        a_done, a_total = _stage_score(assets)

        cost_month = total_for_month(c)
        cost_all = total_all_time(c)

        ad_count = 0
        brief_count = 0
        for s in assets:
            if s.name == "Briefs":
                brief_count = _safe_count(s.summary)
            elif s.name == "Generated ad images":
                ad_count = _safe_count(s.summary)

        rows.append({
            "client": c,
            "brand": _brand_name(c),
            "strategy": f"{_traffic_light(s_done, s_total)} {s_done}/{s_total}",
            "competitive": f"{_traffic_light(c_done, c_total)} {c_done}/{c_total}",
            "ads_pipeline": f"{_traffic_light(a_done, a_total)} {a_done}/{a_total}",
            "briefs": brief_count,
            "ad_images": ad_count,
            "cost_month": cost_month,
            "cost_all": cost_all,
            "next_action": recs[0] if recs else "—",
        })

    # Render as a styled DataFrame
    df = pd.DataFrame(rows)
    display_df = df[[
        "brand", "strategy", "competitive", "ads_pipeline",
        "briefs", "ad_images", "cost_month", "cost_all", "next_action"
    ]].copy()
    display_df.columns = [
        "Brand", "Strategy", "Competitive", "Ad Pipeline",
        "Briefs", "Ads", "This month", "All time", "Recommended next"
    ]
    st.dataframe(
        display_df,
        hide_index=True,
        use_container_width=True,
        column_config={
            "This month": st.column_config.NumberColumn(format="$%.2f"),
            "All time": st.column_config.NumberColumn(format="$%.2f"),
            "Recommended next": st.column_config.TextColumn(width="large"),
        },
    )

    st.divider()
    st.subheader("Open a client")
    pick_cols = st.columns(min(len(clients), 6))
    for i, c in enumerate(clients):
        with pick_cols[i % len(pick_cols)]:
            if st.button(_brand_name(c), key=f"open_{c}", use_container_width=True):
                st.session_state["selected_client"] = c
                st.session_state["view"] = "detail"
                st.rerun()


def _safe_count(summary: str) -> int:
    """Pull the first integer out of a summary string like '12 brief(s)'."""
    if not summary:
        return 0
    import re as _re
    m = _re.search(r"\d+", summary)
    return int(m.group(0)) if m else 0


# ───────────────────────────────────────────────────────────────────────────
# View 2: Client detail
# ───────────────────────────────────────────────────────────────────────────


def render_client_detail(selected: str):
    brand_name = _brand_name(selected)
    st.title(f"🎯 {brand_name}")
    st.caption(f"Client slug: `{selected}`")

    strategy_stages = strategy_status(selected)
    competitive_stages = competitive_research_status(selected)
    asset_stages = ad_assets_status(selected)
    recommendations = build_recommendations(
        selected, strategy_stages, competitive_stages, asset_stages
    )

    def _summary_value(stages, name, default="—"):
        for s in stages:
            if s.name == name:
                return s.summary if s.done else default
        return default

    def _stage_by_name(stages, name):
        for s in stages:
            if s.name == name:
                return s
        return None

    # Pull leading-integer summaries for the KPI cards so the metric reads
    # cleanly even when the underlying stage summary is a longer descriptor.
    def _leading_int(stage_name: str, source_stages, default: str = "0") -> str:
        st_obj = _stage_by_name(source_stages, stage_name)
        if not st_obj or not st_obj.summary:
            return default
        return st_obj.summary.split()[0] if st_obj.summary[0].isdigit() else default

    kpi_cols = st.columns(7)
    kpi_cols[0].metric("Personas", _leading_int("Personas", strategy_stages, "0"))
    kpi_cols[1].metric("Products", _leading_int("Products", strategy_stages, "0"))
    kpi_cols[2].metric("Competitors", _leading_int("Competitors list", competitive_stages, "0"))
    gap_stage = _stage_by_name(competitive_stages, "Competitive gap map")
    kpi_cols[3].metric(
        "Exploitable Gaps",
        gap_stage.summary.split()[0] if gap_stage and gap_stage.summary else "0",
    )
    kpi_cols[4].metric("Briefs", _leading_int("Briefs", asset_stages, "0"))
    kpi_cols[5].metric("Finished Ads", _leading_int("Generated ad images", asset_stages, "0"))
    kpi_cols[6].metric(
        f"Spent {datetime.now().strftime('%b')}",
        f"${total_for_month(selected):.2f}",
        delta=f"${total_all_time(selected):.2f} all-time",
        delta_color="off",
    )

    # Recommendations panel
    st.subheader("🚀 Recommended next steps")
    if recommendations and recommendations[0].startswith("All stages"):
        st.success(recommendations[0])
    else:
        for r in recommendations:
            st.info(f"→ {r}")

    st.divider()

    tabs = st.tabs([
        "📊 Status",
        "🎨 Brand",
        "👥 Personas",
        "📦 Products",
        "💰 Offers",
        "🥊 Competitors",
        "🎯 Gap Map",
        "🧠 Psychology",
        "🗺️ Strategy",
        "📝 Briefs",
        "🖼️ Ads",
        "✨ Remix",
        "📐 Templates",
        "💵 Costs",
        "⚡ Actions",
    ])

    with tabs[0]:
        _render_status_tab(selected, strategy_stages, competitive_stages, asset_stages)
    with tabs[1]:
        _render_brand_tab(selected)
    with tabs[2]:
        _render_personas_tab(selected)
    with tabs[3]:
        _render_products_tab(selected)
    with tabs[4]:
        _render_offers_tab(selected)
    with tabs[5]:
        _render_competitors_tab(selected)
    with tabs[6]:
        _render_gaps_tab(selected)
    with tabs[7]:
        _render_psychology_tab(selected)
    with tabs[8]:
        _render_strategy_tab(selected)
    with tabs[9]:
        _render_briefs_tab(selected)
    with tabs[10]:
        _render_ads_tab(selected)
    with tabs[11]:
        _render_remix_tab(selected)
    with tabs[12]:
        _render_templates_tab(selected)
    with tabs[13]:
        _render_costs_tab(selected)
    with tabs[14]:
        _render_actions_tab(selected)


# ─── Tabs ───────────────────────────────────────────────────────────────────


def _render_stage_table(stages, key_prefix: str):
    rows = []
    for s in stages:
        age = ""
        if s.age_days is not None:
            if s.age_days == 0:
                age = "today"
            elif s.age_days == 1:
                age = "1 day ago"
            else:
                age = f"{s.age_days} days ago"
        rows.append({
            "": "✅" if s.done else "⬜",
            "Stage": s.name,
            "Details": s.summary or "—",
            "Last update": age or "—",
            "Notes": "; ".join(s.notes) if s.notes else "",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, hide_index=True, use_container_width=True, key=key_prefix)


def _render_status_tab(selected, strategy_stages, competitive_stages, asset_stages):
    st.subheader("Strategy")
    _render_stage_table(strategy_stages, "strategy_table")

    st.subheader("Competitive Research")
    _render_stage_table(competitive_stages, "competitive_table")

    # Amazon star breakdown chart
    amazon_path = CLIENTS_DIR / selected / "research" / "amazon-reviews"
    if amazon_path.exists():
        by_star_by_competitor: dict[str, dict[str, int]] = {}
        for f in sorted(amazon_path.glob("*.json")):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            comp = d.get("competitor_name", "?")
            star = d.get("star_filter", "all_stars")
            short_map = {
                "five_star": "5★", "four_star": "4★", "three_star": "3★",
                "two_star": "2★", "one_star": "1★", "all_stars": "all",
            }
            short = short_map.get(star, star)
            n = len(d.get("reviews", []) or [])
            by_star_by_competitor.setdefault(comp, {}).setdefault(short, 0)
            by_star_by_competitor[comp][short] += n
        if by_star_by_competitor:
            chart_df = pd.DataFrame(by_star_by_competitor).T.fillna(0)
            ordered = [c for c in ["5★", "4★", "3★", "2★", "1★", "all"] if c in chart_df.columns]
            chart_df = chart_df[ordered]
            st.subheader("Amazon reviews by competitor × star tier")
            st.bar_chart(chart_df, height=320)

    st.subheader("Ad Production")
    _render_stage_table(asset_stages, "assets_table")


def _render_brand_tab(selected):
    """Brand identity, voice, colors, fonts, signatures, social proof."""
    brand_yaml = CLIENTS_DIR / selected / "brand.yaml"
    context_md = CLIENTS_DIR / selected / "brand-context.md"
    if not brand_yaml.exists():
        st.info(
            f"No brand profile yet. Run "
            f"`adc research --client {selected} --url <homepage>` to create one."
        )
        return
    try:
        b = yaml.safe_load(brand_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        b = {}

    # ── Header
    st.subheader(b.get("name", selected))
    if b.get("tagline"):
        st.markdown(f"_{b['tagline']}_")
    if b.get("mission"):
        st.caption(b["mission"])

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if b.get("founder"):
            st.markdown(f"**Founder:** {b['founder']}")
    with col_b:
        if b.get("founded") and b["founded"] != "unknown":
            st.markdown(f"**Founded:** {b['founded']}")

    st.divider()

    # ── Colors with swatches
    colors = b.get("colors") or {}
    if colors:
        st.markdown("### Color palette")
        color_cols = st.columns(min(5, max(1, sum(1 for v in colors.values() if v))))
        i = 0
        for label, hex_val in colors.items():
            if not hex_val:
                continue
            with color_cols[i % len(color_cols)]:
                st.markdown(
                    f"<div style='background:{hex_val};height:60px;border-radius:6px;"
                    f"border:1px solid #ddd;'></div>",
                    unsafe_allow_html=True,
                )
                st.caption(f"**{label}** `{hex_val}`")
            i += 1

    # ── Typography + tone
    typ = b.get("typography") or {}
    col_l, col_r = st.columns(2)
    with col_l:
        if typ:
            st.markdown("### Typography")
            if typ.get("heading"):
                st.markdown(f"**Heading:** {typ['heading']}")
            if typ.get("body"):
                st.markdown(f"**Body:** {typ['body']}")
            if typ.get("accent"):
                st.markdown(f"**Accent:** {typ['accent']}")
    with col_r:
        if b.get("tone"):
            st.markdown("### Tone")
            st.markdown(b["tone"])

    # ── Visual identity (rich Gemini block)
    vi = b.get("visual_identity") or {}
    if vi and (vi.get("aesthetic") or vi.get("notable_visual_signatures")):
        st.markdown("### Visual identity")
        if vi.get("aesthetic"):
            st.markdown(f"**Aesthetic:** {vi['aesthetic']}")
        if vi.get("design_language"):
            st.markdown(f"**Design language:** {vi['design_language']}")
        if vi.get("photography_style"):
            st.markdown(f"**Photography:** {vi['photography_style']}")
        if vi.get("mood"):
            st.markdown(f"**Mood:** {' · '.join(vi['mood'])}")
        if vi.get("notable_visual_signatures"):
            st.markdown("**Signatures:**")
            for sig in vi["notable_visual_signatures"]:
                st.markdown(f"- {sig}")
        if vi.get("visual_references"):
            st.markdown("**References:**")
            for ref in vi["visual_references"]:
                st.markdown(f"- _{ref}_")

    # ── Audience
    aud = b.get("audience") or {}
    if aud:
        st.markdown("### Audience")
        if aud.get("age_range"):
            st.markdown(f"**Age range:** {aud['age_range']}")
        if aud.get("gender"):
            st.markdown(f"**Gender:** {aud['gender']}")
        if aud.get("interests"):
            st.markdown(f"**Interests:** {', '.join(aud['interests'])}")

    # ── Press + social proof
    col_p, col_s = st.columns(2)
    with col_p:
        if b.get("press_mentions"):
            st.markdown("### Press mentions")
            for p in b["press_mentions"]:
                st.markdown(f"- {p}")
    with col_s:
        if b.get("social_proof"):
            st.markdown("### Social proof")
            for s in b["social_proof"]:
                st.markdown(f"- {s}")

    # ── Voice constraints
    col_pt, col_gn = st.columns(2)
    with col_pt:
        if b.get("prohibited_terms"):
            st.markdown("### Prohibited terms")
            st.caption("Never use these in ad copy")
            for term in b["prohibited_terms"]:
                st.markdown(f"- `{term}`")
    with col_gn:
        if b.get("guidelines_notes"):
            with st.expander("Brand guidelines (visual + voice rules)", expanded=False):
                st.markdown(b["guidelines_notes"])

    # ── Full brand-context.md at the bottom for completeness
    if context_md.exists():
        with st.expander("Full brand-context.md", expanded=False):
            st.markdown(context_md.read_text(encoding="utf-8"))


def _render_personas_tab(selected):
    """All personas with full detail — pain, desires, objections, triggers, language."""
    avatars_dir = CLIENTS_DIR / selected / "avatars"
    avatar_files = sorted(avatars_dir.glob("*.yaml")) if avatars_dir.exists() else []
    avatar_files = [f for f in avatar_files if f.name != "_index.yaml" and not f.name.endswith(".bak")]
    if not avatar_files:
        legacy = CLIENTS_DIR / selected / "avatar.yaml"
        if legacy.exists():
            avatar_files = [legacy]
    if not avatar_files:
        st.info(f"No personas yet for {selected}. Run `adc personas --client {selected}` first.")
        return

    st.write(f"**{len(avatar_files)} persona(s)**")
    for f in avatar_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = d.get("name") or f.stem
        awareness = d.get("awareness_level") or "—"
        with st.expander(f"**{name}** — awareness: `{awareness}`", expanded=False):
            if d.get("demographic"):
                st.markdown(f"**Demographic:** {d['demographic']}")
            if d.get("psychographic"):
                st.markdown(f"**Psychographic:** {d['psychographic']}")

            # Three-column layout for pains/desires/objections
            col1, col2, col3 = st.columns(3)
            with col1:
                if d.get("pain_points"):
                    st.markdown("**Pain points**")
                    for p in d["pain_points"]:
                        if isinstance(p, dict):
                            intensity = p.get("intensity", "")
                            st.markdown(f"- _{intensity}_ — {p.get('pain', '')}")
                            for q in (p.get("customer_language") or [])[:2]:
                                st.caption(f"\"{q}\"")
            with col2:
                if d.get("desires"):
                    st.markdown("**Desires**")
                    for des in d["desires"]:
                        if isinstance(des, dict):
                            st.markdown(f"- {des.get('desire', '')}")
                            for q in (des.get("customer_language") or [])[:2]:
                                st.caption(f"\"{q}\"")
            with col3:
                if d.get("objections"):
                    st.markdown("**Objections**")
                    for obj in d["objections"]:
                        if isinstance(obj, dict):
                            st.markdown(f"- {obj.get('objection', obj)}")
                        else:
                            st.markdown(f"- {obj}")

            # Triggers, current solutions, language
            if d.get("trigger_events"):
                st.markdown("**Trigger events**")
                for t in d["trigger_events"]:
                    st.markdown(f"- {t}")
            if d.get("current_solutions"):
                st.markdown("**Current solutions (competitors they're using now)**")
                for s in d["current_solutions"]:
                    st.markdown(f"- {s}")
            if d.get("language_patterns"):
                st.markdown("**Language patterns**")
                for lp in d["language_patterns"]:
                    st.markdown(f"- _{lp}_")


def _render_products_tab(selected):
    """Enriched product detail — benefits, mechanism, objections, ingredients."""
    products_dir = CLIENTS_DIR / selected / "products"
    product_files = sorted(products_dir.glob("*.yaml")) if products_dir.exists() else []
    product_files = [p for p in product_files if p.name != "example-product.yaml"]
    if not product_files:
        st.info(f"No products yet. Run `adc research --client {selected} --url <homepage>` first.")
        return

    st.write(f"**{len(product_files)} product(s)**")
    for f in product_files:
        try:
            p = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = p.get("name") or f.stem
        price = p.get("price") or "—"
        with st.expander(f"**{name}** — {price}", expanded=False):
            if p.get("description"):
                st.markdown(p["description"])

            col_l, col_r = st.columns([2, 1])
            with col_l:
                if p.get("benefits"):
                    st.markdown("**Benefits**")
                    for b in p["benefits"]:
                        st.markdown(f"- {b}")
                if p.get("unique_mechanism"):
                    st.markdown("**Unique mechanism**")
                    st.markdown(p["unique_mechanism"])
                if p.get("objections"):
                    st.markdown("**Objections handled**")
                    for o in p["objections"]:
                        st.markdown(f"- {o}")
            with col_r:
                if p.get("image_url"):
                    st.image(p["image_url"], use_container_width=True)
                pc = p.get("product_characteristics") or {}
                ings = pc.get("materials_or_ingredients") or []
                if ings:
                    st.markdown("**Ingredients**")
                    for i in ings:
                        st.markdown(f"- {i}")
                shipping = pc.get("shipping_and_fulfillment") or []
                if shipping:
                    st.markdown("**Shipping**")
                    for s in shipping:
                        st.markdown(f"- {s}")
                if p.get("url"):
                    st.markdown(f"[View product page]({p['url']})")


def _render_offers_tab(selected):
    """Existing offers + AI-suggested offers with priority ranking."""
    offers_path = CLIENTS_DIR / selected / "offers.yaml"
    if not offers_path.exists():
        st.info(
            f"No offers yet. Run `adc offers --client {selected} --url <homepage>` first."
        )
        return
    try:
        data = yaml.safe_load(offers_path.read_text(encoding="utf-8")) or {}
    except Exception:
        st.error(f"Could not parse {offers_path}")
        return

    existing = data.get("existing_offers") or []
    suggested = data.get("suggested_offers") or []
    priority_test = data.get("priority_test") or data.get("highest_priority_test")

    if priority_test:
        st.success(f"**Top test recommendation:** {priority_test if isinstance(priority_test, str) else priority_test.get('name', '—')}")
        if isinstance(priority_test, dict) and priority_test.get("rationale"):
            st.caption(priority_test["rationale"])

    if existing:
        st.subheader(f"Existing offers ({len(existing)})")
        rows = []
        for o in existing:
            if isinstance(o, dict):
                rows.append({
                    "Name": o.get("name") or o.get("title") or "—",
                    "Type": o.get("type") or "—",
                    "Description": (o.get("description") or o.get("details") or "")[:140],
                    "Where": (o.get("source") or o.get("location") or o.get("where") or "")[:80],
                })
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    if suggested:
        st.subheader(f"AI-suggested offers ({len(suggested)})")
        for s in suggested:
            if not isinstance(s, dict):
                continue
            lift = s.get("estimated_lift") or s.get("expected_lift") or s.get("lift") or "—"
            persona = s.get("target_persona") or s.get("persona") or "—"
            awareness = s.get("target_awareness_stage") or s.get("awareness") or "—"
            with st.expander(
                f"**{s.get('name', '—')}** — type: `{s.get('type', '—')}` · "
                f"persona: `{persona}` · awareness: `{awareness}` · lift: `{lift}`",
                expanded=False,
            ):
                # Lead with the strategic creative angle if present (what the
                # ad would actually say) — most actionable single field
                if s.get("creative_angle"):
                    st.success(f"**Creative angle:** {s['creative_angle']}")

                # What we're actually offering
                if s.get("suggested_structure"):
                    st.markdown("**What we offer (structure):**")
                    st.markdown(s["suggested_structure"])

                # The Hormozi-style value equation block
                ve = s.get("value_equation") or {}
                if isinstance(ve, dict) and ve:
                    st.markdown("**Value equation:**")
                    ve_cols = st.columns(2)
                    with ve_cols[0]:
                        if ve.get("dream_outcome"):
                            st.markdown(f"- _Dream outcome:_ {ve['dream_outcome']}")
                        if ve.get("perceived_likelihood"):
                            st.markdown(f"- _Perceived likelihood:_ {ve['perceived_likelihood']}")
                    with ve_cols[1]:
                        if ve.get("time_delay"):
                            st.markdown(f"- _Time delay:_ {ve['time_delay']}")
                        if ve.get("effort_and_sacrifice"):
                            st.markdown(f"- _Effort & sacrifice:_ {ve['effort_and_sacrifice']}")

                # Strategic reasoning
                if s.get("rationale"):
                    st.markdown(f"**Rationale:** {s['rationale']}")

                # Risk / urgency / pricing mechanics
                if s.get("risk_reversal"):
                    st.markdown(f"**Risk reversal:** {s['risk_reversal']}")
                if s.get("urgency_mechanic"):
                    st.markdown(f"**Urgency mechanic:** {s['urgency_mechanic']}")
                if s.get("pricing_anchor_logic"):
                    st.markdown(f"**Pricing anchor:** {s['pricing_anchor_logic']}")

                # Catch-all fallbacks for older offer shapes
                if s.get("description"):
                    st.markdown(f"**Description:** {s['description']}")
                if s.get("mechanic") and not s.get("urgency_mechanic"):
                    st.markdown(f"**Mechanic:** {s['mechanic']}")
                if s.get("implementation"):
                    st.markdown(f"**Implementation:** {s['implementation']}")

                if s.get("notes"):
                    st.caption(f"_Notes: {s['notes']}_")


def _render_competitors_tab(selected):
    """Competitor list with notes, tier, and Amazon URL status."""
    competitors_path = CLIENTS_DIR / selected / "competitors.yaml"
    if not competitors_path.exists():
        st.info(
            f"No competitors yet. Create `clients/{selected}/competitors.yaml` "
            "with 3-5 competitors to unlock competitive research."
        )
        return
    try:
        data = yaml.safe_load(competitors_path.read_text(encoding="utf-8")) or {}
    except Exception:
        st.error(f"Could not parse {competitors_path}")
        return

    comps = data.get("competitors") or []
    if not comps:
        st.info("competitors.yaml exists but contains no competitors.")
        return

    # Counts by tier and type
    tiers: dict[str, int] = {}
    types: dict[str, int] = {}
    for c in comps:
        if isinstance(c, dict):
            tiers[c.get("priority", "—")] = tiers.get(c.get("priority", "—"), 0) + 1
            types[c.get("type", "—")] = types.get(c.get("type", "—"), 0) + 1

    cols = st.columns(4)
    cols[0].metric("Competitors", len(comps))
    cols[1].metric("Tier 1", tiers.get("tier1", 0))
    cols[2].metric("Direct", types.get("direct", 0))
    cols[3].metric("With Amazon URLs", sum(1 for c in comps if isinstance(c, dict) and c.get("amazon_urls")))

    st.divider()

    # Group by tier
    by_tier: dict[str, list] = {}
    for c in comps:
        if not isinstance(c, dict):
            continue
        by_tier.setdefault(c.get("priority", "—"), []).append(c)

    for tier in ["tier1", "tier2", "tier3", "—"]:
        if tier not in by_tier:
            continue
        st.subheader(f"{tier.upper()}")
        for c in by_tier[tier]:
            type_badge = c.get("type", "—")
            url = c.get("url", "")
            amazon_count = len(c.get("amazon_urls") or [])
            with st.expander(
                f"**{c.get('name', '—')}** — `{type_badge}` · "
                f"{amazon_count} Amazon URL(s)",
                expanded=False,
            ):
                if url:
                    st.markdown(f"[{url}]({url})")
                if c.get("notes"):
                    st.markdown(c["notes"])
                if c.get("amazon_urls"):
                    st.markdown("**Amazon URLs:**")
                    for au in c["amazon_urls"]:
                        st.markdown(f"- {au}")


def _render_strategy_tab(selected):
    """Schwartz × persona strategy matrix — every messaging cell for paid creative."""
    matrix_yaml = CLIENTS_DIR / selected / "strategy-matrix.yaml"
    matrix_md = CLIENTS_DIR / selected / "strategy-matrix.md"
    if not matrix_yaml.exists():
        st.info(
            f"No strategy matrix yet. Run `adc strategy-matrix --client {selected}` first."
        )
        return
    try:
        data = yaml.safe_load(matrix_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        st.error(f"Could not parse {matrix_yaml}")
        return

    personas = data.get("matrix") or []
    obs = data.get("cross_stage_observations") or {}

    # ── Headline metrics
    total_cells = sum(len(p.get("cells", []) or []) for p in personas)
    m1, m2, m3 = st.columns(3)
    m1.metric("Personas", len(personas))
    m2.metric("Awareness stages", 5)
    m3.metric("Total cells", total_cells)

    # ── Cross-stage observations at top
    if obs:
        if obs.get("highest_leverage_stages"):
            st.success(
                f"**Highest-leverage stages:** {', '.join(obs['highest_leverage_stages'])}"
            )
        if obs.get("weakest_stages"):
            st.warning(
                f"**Weakest stages:** {', '.join(obs['weakest_stages'])}"
            )
        if obs.get("ad_distribution_recommendation"):
            with st.expander("📊 Budget / creative distribution recommendation", expanded=False):
                st.markdown(obs["ad_distribution_recommendation"])
        if obs.get("category_specific_notes"):
            with st.expander("📝 Category-specific notes", expanded=False):
                st.markdown(obs["category_specific_notes"])

    st.divider()

    # ── Per-persona cells — radio to pick which persona to view
    if not personas:
        st.info("Matrix file exists but has no persona cells.")
        return

    persona_names = [p.get("persona_name", f"Persona {i+1}") for i, p in enumerate(personas)]
    chosen_persona_name = st.radio(
        "View persona:",
        persona_names,
        horizontal=True,
        key="matrix_persona_picker",
    )
    chosen_persona = next(
        (p for p in personas if p.get("persona_name") == chosen_persona_name),
        personas[0],
    )

    cells = chosen_persona.get("cells") or []
    if not cells:
        st.info(f"No cells for {chosen_persona_name}.")
        return

    # Show 5 awareness stages as expandable rows
    stage_emoji = {
        "unaware": "🌫️",
        "problem_aware": "🤔",
        "solution_aware": "🔍",
        "product_aware": "🛒",
        "most_aware": "🎯",
    }
    stage_order = ["unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]
    cells_sorted = sorted(
        cells,
        key=lambda c: stage_order.index(c.get("awareness_stage", "unaware"))
        if c.get("awareness_stage") in stage_order else 99,
    )

    for cell in cells_sorted:
        stage = cell.get("awareness_stage", "—")
        emoji = stage_emoji.get(stage, "▫️")
        angle = cell.get("primary_angle", "—")
        funnel = cell.get("funnel_placement", "—")
        with st.expander(
            f"{emoji} **{stage.replace('_', ' ').title()}** — {angle[:100]}"
            + ("..." if len(angle) > 100 else "")
            + f"  ·  `{funnel}`",
            expanded=False,
        ):
            # Top context band
            col_a, col_b = st.columns(2)
            with col_a:
                if cell.get("what_they_know"):
                    st.markdown("**What they currently know/believe:**")
                    st.caption(cell["what_they_know"])
            with col_b:
                if cell.get("what_they_dont_know_yet"):
                    st.markdown("**Gap to fill:**")
                    st.caption(cell["what_they_dont_know_yet"])

            # Hero: primary angle + example hook
            st.markdown(f"**Angle:** {cell.get('primary_angle', '—')}")
            if cell.get("example_hook"):
                st.markdown(f"> *\"{cell['example_hook']}\"*")

            # Mechanics row
            col_l, col_r = st.columns(2)
            with col_l:
                if cell.get("hook_style"):
                    st.markdown(f"**Hook style:** `{cell['hook_style']}`")
                if cell.get("framework"):
                    st.markdown(f"**Framework:** `{cell['framework']}`")
                if cell.get("creative_mechanic"):
                    st.markdown(f"**Creative mechanic:** `{cell['creative_mechanic']}`")
            with col_r:
                if cell.get("cta"):
                    st.markdown(f"**CTA:** {cell['cta']}")
                if cell.get("funnel_placement"):
                    st.markdown(f"**Funnel:** `{cell['funnel_placement']}`")
                if cell.get("proof_to_surface"):
                    st.markdown(f"**Proof:** {cell['proof_to_surface']}")

            if cell.get("notes"):
                st.info(f"_{cell['notes']}_")

    # Full markdown render at the bottom
    if matrix_md.exists():
        with st.expander("📄 Full strategy-matrix.md", expanded=False):
            st.markdown(matrix_md.read_text(encoding="utf-8"))


def _render_briefs_tab(selected):
    briefs_dir = CLIENTS_DIR / selected / "briefs"
    brief_files = list(briefs_dir.glob("*.yaml")) if briefs_dir.exists() else []
    if not brief_files:
        st.info(f"No briefs yet. Run: `adc brief --client {selected} --product <id>`")
        return

    # Load each brief and sort with the same key as models.loader.load_all_briefs
    # — (product, slot, brief_id) — so the picker's `--pick N` index matches
    # the order shown here. Without this, dashboard list order disagrees with
    # `adc generate --pick N` and the user picks the wrong brief.
    loaded: list[tuple[Path, dict]] = []
    for f in brief_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        loaded.append((f, d))
    loaded.sort(key=lambda t: (
        t[1].get("product", ""),
        t[1].get("slot") or 0,
        t[1].get("brief_id", ""),
    ))

    st.write(f"**{len(loaded)} brief(s)** — click any to expand. `#N` matches the `--pick N` index used in the Ads tab.")
    for i, (f, d) in enumerate(loaded, 1):
        slot = d.get("slot", "—")
        hook = (d.get("hook", "") or "")[:80]
        persona_label = d.get("persona") or "—"
        # Header order: brief # (matches Ads tab picker), slot (from
        # diversity matrix), persona, then truncated hook. The leading # is
        # what callers use; everything after is context for the human reader.
        with st.expander(f"#{i}  ·  Slot {slot}  ·  👤 {persona_label}  —  {hook}..."):
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown(f"**Hook:** {d.get('hook', '—')}")
                st.markdown(f"**Angle:** {d.get('angle', '—')}")
                st.markdown(f"**Pain point:** {d.get('pain_point', '—')}")
                st.markdown(f"**Persona:** {d.get('persona', '—')}")
                if d.get("persona_traits"):
                    st.caption(f"_Buyer thumbnail: {d['persona_traits']}_")
                st.markdown(f"**CTA:** {d.get('cta', '—')}")
                if d.get("benefit_callouts"):
                    st.markdown("**Benefit callouts:**")
                    for b in d["benefit_callouts"]:
                        st.markdown(f"  - {b}")
                if d.get("visual_direction"):
                    st.markdown(f"**Visual direction:** {d['visual_direction']}")
            with col_r:
                st.markdown(f"**Framework:** `{d.get('framework', '—')}`")
                # Mechanic with plain-English caption from the glossary
                mech = d.get("creative_mechanic", "—")
                st.markdown(f"**Mechanic:** `{mech}`")
                mech_caption = _glossary_caption(mech, PAIRING_GLOSSARY)
                if mech_caption:
                    st.caption(f"💡 {mech_caption}")

                # Visual format primary + alternatives
                fmt = d.get("visual_format", "—")
                alts = d.get("visual_format_alternatives") or []
                st.markdown(f"**Format (primary):** {fmt}")
                if alts:
                    st.markdown("**Alternates to test:**")
                    for alt in alts:
                        st.markdown(f"  - {alt}")

                st.markdown(f"**Awareness:** `{d.get('awareness_level', '—')}`")
                st.caption(f"ID: `{d.get('brief_id', f.stem)}`")

            # Trending format alternatives — separate row, full width.
            trending = d.get("trending_format_recommendations") or []
            if trending:
                st.markdown("---")
                st.markdown("**🔥 Trending format alternatives** (top 3)")
                for rec in trending[:3]:
                    rank = rec.get("rank", "?")
                    name = rec.get("name", "—")
                    fmt_type = rec.get("format_type", "—")
                    complexity = rec.get("production_complexity", "—")
                    rationale = rec.get("rationale", "")
                    notes = rec.get("production_notes", "")
                    st.markdown(
                        f"**#{rank} — {name}**  "
                        f"`{fmt_type}` · `{complexity}-complexity`"
                    )
                    if rationale:
                        st.caption(f"_{rationale}_")
                    if notes:
                        st.caption(f"⚠️ {notes}")


def _render_ads_tab(selected):
    """Show generated ad images, grouped by variant folder.

    Discovers every directory under ai-ads/<client>/ that starts with `images`.
    The default `images/` folder is labeled "current"; folders like
    `images-baseline/`, `images-patch-a/`, etc. show as their suffix.
    Lets you compare runs side-by-side without leaving the dashboard.
    """
    client_root = AI_ADS_DIR / selected
    if not client_root.exists():
        st.info(
            f"No generated ad images yet. Run: "
            f"`adc generate --client {selected} --pick 1,2,3`"
        )
        return

    # Find every images* folder for this client
    variant_dirs: list[tuple[str, "Path"]] = []
    for d in sorted(client_root.iterdir()):
        if not d.is_dir() or not d.name.startswith("images"):
            continue
        label = "current" if d.name == "images" else d.name.removeprefix("images-")
        if any(d.glob("*.png")):
            variant_dirs.append((label, d))

    if not variant_dirs:
        st.info(
            f"No generated ad images yet. Run: "
            f"`adc generate --client {selected} --pick 1,2,3`"
        )
        return

    # Aggregate: build {brief_id: {variant_label: [file, file, ...]}}
    aggregated: dict[str, dict[str, list]] = {}
    for label, d in variant_dirs:
        for f in sorted(d.glob("*.png")):
            brief_id = f.stem.rsplit("_", 1)[0]
            aggregated.setdefault(brief_id, {}).setdefault(label, []).append(f)

    # Header KPIs
    total_imgs = sum(len(list(d.glob("*.png"))) for _, d in variant_dirs)
    m1, m2, m3 = st.columns(3)
    m1.metric("Total images", total_imgs)
    m2.metric("Variant folders", len(variant_dirs))
    m3.metric("Unique briefs", len(aggregated))

    # View toggle: compare across variants OR show all images from a single variant
    if len(variant_dirs) > 1:
        view_mode = st.radio(
            "View mode",
            ["📊 Compare across variants", "📁 Single variant only"],
            horizontal=True,
            key="ads_view_mode",
        )
    else:
        view_mode = "📁 Single variant only"

    if view_mode == "📊 Compare across variants":
        # Per brief, show one row across all variants (side by side)
        st.caption(
            "Each row is one brief; each column is one variant folder. "
            "Same brief_id across columns means same brief, different pipeline run."
        )
        variant_labels = [label for label, _ in variant_dirs]
        for brief_id, by_variant in aggregated.items():
            st.markdown(f"**Brief:** `{brief_id}`")
            cols = st.columns(len(variant_labels))
            for i, label in enumerate(variant_labels):
                with cols[i]:
                    st.caption(f"_{label}_")
                    files = by_variant.get(label, [])
                    if not files:
                        st.markdown("_(not generated for this variant)_")
                    else:
                        for f in files:
                            st.image(str(f), use_container_width=True)
                            aspect = f.stem.rsplit("_", 1)[-1] if "_" in f.stem else ""
                            if aspect:
                                st.caption(f"`{aspect}`")
            st.divider()
    else:
        # Single-variant view: pick a folder and show its images in a 3-col grid
        labels = [label for label, _ in variant_dirs]
        chosen_label = st.selectbox(
            "Variant folder",
            labels,
            index=labels.index("current") if "current" in labels else 0,
            key="ads_variant_picker",
        )
        chosen_dir = next(d for label, d in variant_dirs if label == chosen_label)
        files = sorted(chosen_dir.glob("*.png"))
        st.caption(f"`{chosen_dir.relative_to(AI_ADS_DIR.parent)}` — {len(files)} image(s)")

        cols_per_row = 3
        for i in range(0, len(files), cols_per_row):
            row = st.columns(cols_per_row)
            for j, f in enumerate(files[i:i + cols_per_row]):
                with row[j]:
                    brief_id = f.stem.rsplit("_", 1)[0]
                    aspect = f.stem.rsplit("_", 1)[-1] if "_" in f.stem else ""
                    st.image(str(f), use_container_width=True)
                    st.caption(f"`{brief_id}` ({aspect})")


def _list_remix_runs(selected: str) -> list[dict]:
    """List all remix runs for a client, newest first.

    Each entry has: timestamp, dir, analysis, briefs, reference (Path or None),
    images (list[Path])."""
    remixes_dir = CLIENTS_DIR / selected / "remixes"
    if not remixes_dir.exists():
        return []
    runs: list[dict] = []
    for d in sorted(remixes_dir.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        analysis_path = d / "analysis.yaml"
        briefs_path = d / "briefs.yaml"
        if not analysis_path.exists() or not briefs_path.exists():
            continue
        try:
            analysis = yaml.safe_load(analysis_path.read_text(encoding="utf-8")) or {}
            briefs = yaml.safe_load(briefs_path.read_text(encoding="utf-8")) or []
        except Exception:
            continue
        reference = None
        for ext in ("png", "jpg", "jpeg", "webp"):
            cand = d / f"reference.{ext}"
            if cand.exists():
                reference = cand
                break
        images_dir = d / "images"
        images = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
        runs.append({
            "timestamp": d.name,
            "dir": d,
            "analysis": analysis,
            "briefs": briefs,
            "reference": reference,
            "images": images,
        })
    return runs


def _render_remix_tab(selected):
    """Remix an example ad for your product — upload an image (or paste a
    Foreplay link), tune variation count + fidelity, then generate briefs and
    images. Past runs are listed below the form, newest first."""
    st.markdown("### ✨ Remix an example ad")
    st.caption(
        "Drop in an ad you like (local file or Foreplay link). The system "
        "extracts its strategic + visual DNA and produces N variations for "
        "your product, mixing high-fidelity near-clones with persona-tuned "
        "variants."
    )

    products_dir = CLIENTS_DIR / selected / "products"
    product_slugs: list[str] = []
    if products_dir.exists():
        for f in sorted(products_dir.glob("*.yaml")):
            if f.name == "example-product.yaml":
                continue
            product_slugs.append(f.stem)

    if not product_slugs:
        st.warning(
            f"No products configured for `{selected}`. Run `adc research --client {selected} --url <site>` first."
        )
        return

    avatars_dir = CLIENTS_DIR / selected / "avatars"
    avatar_count = (
        len([p for p in avatars_dir.glob("*.yaml") if not p.name.startswith("_")])
        if avatars_dir.exists()
        else 0
    )
    if avatar_count == 0:
        legacy = CLIENTS_DIR / selected / "avatar.yaml"
        if legacy.exists():
            avatar_count = 1
    if avatar_count == 0:
        st.warning(
            f"No avatars yet for `{selected}`. Run `adc personas --client {selected}` first — "
            "the remixer needs personas to vary across."
        )
        return

    with st.expander("➕ New remix", expanded=True):
        source_mode = st.radio(
            "Reference source",
            ["Upload image", "Foreplay URL / ID"],
            horizontal=True,
            key=f"remix_source_{selected}",
        )

        ref_path: Path | None = None
        foreplay_ref: str = ""

        if source_mode == "Upload image":
            uploaded = st.file_uploader(
                "Reference ad image",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"remix_upload_{selected}",
                help="PNG/JPG/WEBP of the ad you want to remix",
            )
            if uploaded is not None:
                upload_dir = REPO_ROOT / "references" / "_dashboard_uploads"
                upload_dir.mkdir(parents=True, exist_ok=True)
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                ext = Path(uploaded.name).suffix.lower() or ".png"
                ref_path = upload_dir / f"{selected}_{stamp}{ext}"
                ref_path.write_bytes(uploaded.getbuffer())
                col_img, _col_sp = st.columns([1, 2])
                with col_img:
                    st.image(str(ref_path), caption="Reference preview", use_container_width=True)
        else:
            foreplay_ref = st.text_input(
                "Foreplay URL or numeric ad ID",
                placeholder="https://app.foreplay.co/ad/12345  (or just 12345)",
                key=f"remix_foreplay_{selected}",
            ).strip()

        col_p, col_v, col_h, col_m = st.columns([2, 1, 1, 1])
        with col_p:
            chosen_product = st.selectbox(
                "Product", product_slugs, key=f"remix_product_{selected}"
            )
        with col_v:
            variations = st.number_input(
                "Variations",
                min_value=1,
                max_value=10,
                value=5,
                key=f"remix_variations_{selected}",
            )
        with col_h:
            high_fidelity = st.number_input(
                "High-fid",
                min_value=0,
                max_value=int(variations),
                value=min(2, int(variations)),
                key=f"remix_high_{selected}",
                help="Near-clones of the reference (same setting/person/typography)",
            )
        with col_m:
            medium_fidelity = st.number_input(
                "Medium-fid",
                min_value=0,
                max_value=int(variations),
                value=min(2, max(0, int(variations) - int(high_fidelity))),
                key=f"remix_medium_{selected}",
                help="Core identity matches, small persona-tuned variation",
            )

        low_fidelity = max(0, int(variations) - int(high_fidelity) - int(medium_fidelity))
        st.caption(
            f"Mix: {int(high_fidelity)} high · {int(medium_fidelity)} medium · {low_fidelity} low  ·  "
            f"Est cost: ~${0.10 * int(variations):.2f}"
        )

        cd_key = f"remix_cd_{selected}"
        creative_direction = st.text_area(
            "Creative direction (optional)",
            key=cd_key,
            placeholder=(
                "e.g. 'two callouts in primary brand color + accent color, "
                "text bubble at top, hand from bottom holding product, no FDA disclaimer'"
            ),
            height=80,
            help=(
                "Pre-generation directive applied to ALL variations. Use it to lock in "
                "structural elements (text bubble, two callouts) or styling cues (brand "
                "colors for pills, generous whitespace). Highest-priority constraint — "
                "overrides any conflicting pattern from the reference DNA."
            ),
        )

        offer_key = f"remix_offer_{selected}"
        offer_input = st.text_input(
            "Offer code (optional, slot 9 of the naming taxonomy)",
            value="NONE",
            key=offer_key,
            placeholder="e.g. FREESHIP, BFCM25, 20OFF",
            help=(
                "Promo code that appears in the campaign name (slot 9). "
                "Alphanumeric only, capped at 12 chars. Use 'NONE' for ads without an offer."
            ),
        )

        # ── Prompt mode ──────────────────────────────────────────────────
        # Strategic: verbose ~1500-word prompts that describe a fresh ad
        # inspired by the reference. Best for new-brief generation.
        # Differential: vision-extract source text, Claude maps source→target
        # via the brief, produce a short surgical-edit prompt. Best for
        # layout-faithful remixes like us-vs-them comparison ads.
        mode = st.radio(
            "Prompt mode",
            ["Strategic (default — fresh ad inspired by the reference)",
             "Differential (surgical edit — swap product + text, preserve layout)"],
            index=0,
            key=f"remix_mode_{selected}",
            horizontal=False,
            help=(
                "Strategic produces verbose prompts that describe a brand-new ad. "
                "Best when you want psychology + persona to drive a different visual. "
                "Differential produces short edit-style prompts that swap product and "
                "text while preserving layout, fonts, decorative marks, and lighting. "
                "Best for us-vs-them comparison ads or any time you want the result to "
                "look nearly identical to the reference with surgical content changes. "
                "Differential mode pairs naturally with 'Creative direction' above — "
                "any text you put there becomes the ONLY allowed deviation (e.g. "
                "'change background to spring grassy field')."
            ),
        )
        mode_flag = "differential" if mode.lower().startswith("differential") else "strategic"

        ready = (ref_path is not None) or bool(foreplay_ref)
        if not ready:
            st.info("Upload an image or paste a Foreplay URL/ID to continue.")
        else:
            button_suffix = " (differential)" if mode_flag == "differential" else ""
            if st.button(
                f"✨ Generate {int(variations)} remix variation(s){button_suffix}",
                type="primary",
                use_container_width=True,
                key=f"remix_run_{selected}",
            ):
                args = [
                    "remix",
                    "--client", selected,
                    "--product", chosen_product,
                    "--variations", str(int(variations)),
                    "--high-fidelity", str(int(high_fidelity)),
                    "--medium-fidelity", str(int(medium_fidelity)),
                    "--offer", offer_input.strip() or "NONE",
                    "--mode", mode_flag,
                ]
                if creative_direction.strip():
                    args += ["--creative-direction", creative_direction.strip()]
                if ref_path is not None:
                    args += ["--reference", str(ref_path)]
                else:
                    args += ["--foreplay-url", foreplay_ref]
                run_adc_command(
                    args,
                    label=(
                        f"Remixing for {selected} "
                        f"(~${0.10 * int(variations):.2f}, mode={mode_flag})"
                    ),
                )
                st.rerun()

    st.divider()

    runs = _list_remix_runs(selected)
    if not runs:
        st.info("No remix runs yet. Use the form above to create your first one.")
        return

    st.markdown(f"### 📚 Past remixes  · _{len(runs)} run(s)_")

    for run in runs:
        analysis = run["analysis"]
        briefs = run["briefs"]
        images = run["images"]
        run_dir: Path = run["dir"]

        ad_type = analysis.get("ad_type") or "—"
        levers = analysis.get("psych_levers") or []
        n_briefs = len(briefs)
        n_images = len(images)
        title = (
            f"🗓️ {run['timestamp']}  ·  "
            f"{ad_type}  ·  {n_briefs} brief(s)  ·  "
            f"{n_images} image(s)"
        )

        with st.expander(title, expanded=(run is runs[0])):
            top_l, top_r = st.columns([1, 2])
            with top_l:
                if run["reference"] is not None:
                    st.image(str(run["reference"]), caption="Reference", use_container_width=True)
                else:
                    st.caption("(no reference image on disk)")
            with top_r:
                st.markdown(f"**Ad type:** `{ad_type}` "
                            f"_(conf {analysis.get('ad_type_confidence', 0):.2f})_")
                st.markdown(f"**Psych levers:** {', '.join(levers) or '—'}")
                st.markdown(f"**Framework:** `{analysis.get('framework', '—')}`")
                st.markdown(f"**Creative mechanic:** {analysis.get('creative_mechanic', '—')}")
                st.markdown(f"**Visual format:** {analysis.get('visual_format', '—')}")
                if analysis.get("pain_attacked"):
                    st.markdown(f"**Pain attacked:** {analysis['pain_attacked']}")
                if analysis.get("enemy"):
                    st.markdown(f"**Enemy:** {analysis['enemy']}")

            st.markdown("---")
            st.markdown("**Briefs**")
            rows = []
            for i, b in enumerate(briefs, 1):
                rows.append({
                    "#": i,
                    "Persona": b.get("persona", "—"),
                    "Hook": (b.get("hook", "") or "")[:90],
                    "CTA": b.get("cta", "—"),
                })
            if rows:
                st.dataframe(
                    pd.DataFrame(rows),
                    hide_index=True,
                    use_container_width=True,
                    key=f"remix_briefs_{run['timestamp']}",
                )

            # Trending alternatives — one row per brief, collapsed by default.
            any_trending = any(
                (b.get("trending_format_recommendations") or [])
                for b in briefs
            )
            if any_trending:
                with st.expander("🔥 Trending format alternatives (top 3 per brief)", expanded=False):
                    for b in briefs:
                        recs = b.get("trending_format_recommendations") or []
                        if not recs:
                            continue
                        st.markdown(f"**{b.get('persona', '—')}** — `{b.get('brief_id', '?')[-6:]}`")
                        for rec in recs[:3]:
                            rank = rec.get("rank", "?")
                            name = rec.get("name", "—")
                            fmt_type = rec.get("format_type", "—")
                            complexity = rec.get("production_complexity", "—")
                            rationale = rec.get("rationale", "")
                            st.markdown(
                                f"  • **#{rank} {name}**  "
                                f"`{fmt_type}` · `{complexity}-complexity` — {rationale}"
                            )
                        st.markdown("")

            st.markdown("---")
            if images:
                st.markdown(f"**Images** ({len(images)})")
                # Group images by brief_id so each idea's versions appear together.
                briefs_by_id = {b["brief_id"]: b for b in briefs}
                groups: dict[str, list[Path]] = {}
                for img in images:
                    matched_id = next(
                        (bid for bid in briefs_by_id if img.stem.startswith(bid)),
                        None,
                    )
                    if matched_id:
                        groups.setdefault(matched_id, []).append(img)
                    else:
                        groups.setdefault("__unmatched__", []).append(img)

                for bid, brief_imgs in groups.items():
                    if bid == "__unmatched__":
                        st.caption("Images without a matching brief:")
                    else:
                        brief = briefs_by_id[bid]
                        persona = brief.get("persona", "—")
                        hook_preview = (brief.get("hook", "") or "")[:80]
                        st.markdown(
                            f"#### {persona}  ·  _{hook_preview}_"
                            if hook_preview
                            else f"#### {persona}"
                        )

                    # Sort: original first (no _v suffix), then v2, v3, ...
                    def _version_key(p: Path) -> tuple[int, str]:
                        import re as _re
                        m = _re.search(r"_v(\d+)", p.stem)
                        return (int(m.group(1)) if m else 1, p.name)
                    brief_imgs_sorted = sorted(brief_imgs, key=_version_key)

                    cols_per_row = 3
                    for i in range(0, len(brief_imgs_sorted), cols_per_row):
                        row = st.columns(cols_per_row)
                        for j, img in enumerate(brief_imgs_sorted[i:i + cols_per_row]):
                            with row[j]:
                                st.image(str(img), use_container_width=True)
                                # Show "Original" / "v2" / "v2 (a)" etc.
                                import re as _re
                                m = _re.search(r"_v(\d+)(?:_([a-z]))?", img.stem)
                                if m:
                                    suffix = f"v{m.group(1)}"
                                    if m.group(2):
                                        suffix += f" ({m.group(2)})"
                                    st.caption(suffix)
                                else:
                                    st.caption("Original")
                                # Show Meta campaign name from the per-image
                                # sidecar (preferred — has correct iteration)
                                # or fall back to the brief's V1 name.
                                sidecar = img.with_name(img.stem + "_campaign.txt")
                                campaign_text = ""
                                if sidecar.exists():
                                    try:
                                        campaign_text = sidecar.read_text(
                                            encoding="utf-8"
                                        ).strip()
                                    except OSError:
                                        campaign_text = ""
                                if not campaign_text:
                                    brief_obj = briefs_by_id.get(bid, {})
                                    campaign_text = brief_obj.get("campaign_name", "") or ""
                                if campaign_text:
                                    st.code(campaign_text, language=None)

                    # Per-brief refinement form
                    if bid != "__unmatched__":
                        with st.expander(f"🔄 Refine `{bid[-6:]}`", expanded=False):
                            fb_key = f"refine_fb_{run['timestamp']}_{bid}"
                            vn_key = f"refine_vn_{run['timestamp']}_{bid}"
                            base_key = f"refine_base_{run['timestamp']}_{bid}"
                            feedback = st.text_area(
                                "What would you like to change?",
                                key=fb_key,
                                placeholder=(
                                    "e.g. 'make the lighting warmer and lower the hand position', "
                                    "or 'change the right-circle text to focus on bloat'"
                                ),
                                height=80,
                                help=(
                                    "Visual tweaks (color, position, mood) preserve the layout. "
                                    "Copy changes (hook, callouts) rewrite the text."
                                ),
                            )

                            # Build base-version selector. Default: Original
                            # (so feedback doesn't compound on top of unwanted
                            # changes from a previous refinement).
                            import re as _re_b
                            def _base_label(p: Path) -> str:
                                m = _re_b.search(r"_v(\d+)(?:_([a-z]))?", p.stem)
                                if m:
                                    s = f"v{m.group(1)}"
                                    if m.group(2):
                                        s += f" ({m.group(2)})"
                                    return s
                                return "Original"
                            base_options: list[tuple[str, str]] = []  # (label, filename)
                            for p in brief_imgs_sorted:
                                base_options.append((_base_label(p), p.name))
                            default_idx = 0  # Original first in sorted order
                            base_choice = st.selectbox(
                                "Refine FROM which version?",
                                options=range(len(base_options)),
                                format_func=lambda i: base_options[i][0],
                                index=default_idx,
                                key=base_key,
                                help=(
                                    "Default 'Original' restarts from the clean v1 — recommended "
                                    "if you want the change in isolation. Pick a later version to "
                                    "stack feedback on top of previous refinements."
                                ),
                            )
                            base_filename = base_options[base_choice][1]

                            # ── Engine toggle for refinement ──────────────
                            # When ON: route through Higgs Field soul_2 +
                            # PIL overlay (iterative refinement using the
                            # previous SCENE image as a composition ref).
                            # Falls back to NB2 if HF credits are empty.
                            refine_use_hf = st.checkbox(
                                "Use Higgs Field for refinement (iterative, identity-locked)",
                                key=f"refine_use_hf_{run['timestamp']}_{bid}",
                                help=(
                                    "Off: NB2 with Claude prompt-rewrite (default, "
                                    "edits the layout precisely; product image is a ref). "
                                    "On: routes through the persona's trained Soul "
                                    "Character via Higgs Field soul_2 + PIL text overlay, "
                                    "using the previous SCENE image as a composition "
                                    "reference — mirrors the manual HF workflow "
                                    "(generate → use as reference → iterate). "
                                    "Requires HF_CREDENTIALS in .env and a 'ready' Soul "
                                    "Character on this brief's persona. Falls back to NB2 "
                                    "if HF credits are empty."
                                ),
                            )

                            cols_form = st.columns([1, 4])
                            with cols_form[0]:
                                n_vars = st.number_input(
                                    "Variations",
                                    min_value=1,
                                    max_value=4,
                                    value=1,
                                    key=vn_key,
                                )
                            with cols_form[1]:
                                engine_suffix = " (HF Soul)" if refine_use_hf else ""
                                refine_label = (
                                    f"🔄 Refine from {base_options[base_choice][0]}"
                                    f"{engine_suffix} "
                                    f"({int(n_vars)} variation(s), ~${0.10 * int(n_vars):.2f})"
                                )
                                if st.button(
                                    refine_label,
                                    disabled=not feedback.strip(),
                                    key=f"refine_btn_{run['timestamp']}_{bid}",
                                    use_container_width=True,
                                ):
                                    args = [
                                        "remix-refine",
                                        "--remix-dir", str(run_dir),
                                        "--brief", bid,
                                        "--feedback", feedback.strip(),
                                        "--num-images", str(int(n_vars)),
                                        "--from-image", base_filename,
                                    ]
                                    if refine_use_hf:
                                        args += [
                                            "--engine", "higgsfield-soul",
                                            "--fallback-engine", "nb2",
                                        ]
                                    run_adc_command(
                                        args,
                                        label=(
                                            f"Refining {bid[-6:]} from {base_options[base_choice][0]} "
                                            f"— {int(n_vars)} variation(s)"
                                            + (" via Higgs Field Soul" if refine_use_hf else "")
                                        ),
                                    )
                                    st.rerun()
            else:
                st.info("No images generated yet for this run.")

            # ── Engine toggle ────────────────────────────────────────────
            # When ON: route through Higgs Field soul_2 with each persona's
            # trained Soul Character (identity-locked face) + PIL text overlay.
            # Falls back to NB2 automatically if HF API credits are empty.
            use_hf = st.checkbox(
                "Use Higgs Field (identity-locked) — falls back to NB2 if HF credits are empty",
                key=f"remix_use_hf_{run['timestamp']}",
                help=(
                    "Off: fast NB2 with your product image (default, no identity lock). "
                    "On: routes through each persona's trained Soul Character via Higgs "
                    "Field soul_2 + PIL text overlay — same face every generation. "
                    "Requires HF_CREDENTIALS in .env and a 'ready' Soul Character on each "
                    "persona's avatar YAML. If the Higgs Field REST API has no credits, "
                    "the run automatically falls back to NB2 instead of aborting."
                ),
            )

            action_l, action_r = st.columns(2)
            engine_suffix = " (HF Soul)" if use_hf else ""
            label_button = (
                f"♻️ Re-fire {n_briefs} image(s){engine_suffix} (~${0.08 * n_briefs:.2f})"
                if images
                else f"🖼️ Generate {n_briefs} image(s){engine_suffix} (~${0.08 * n_briefs:.2f})"
            )
            with action_l:
                if st.button(
                    label_button,
                    use_container_width=True,
                    key=f"remix_genimg_{run['timestamp']}",
                ):
                    args = [
                        "remix-images",
                        "--remix-dir", str(run_dir),
                        "--num-images", "1",
                    ]
                    if use_hf:
                        args += [
                            "--engine", "higgsfield-soul",
                            "--fallback-engine", "nb2",
                        ]
                    run_adc_command(
                        args,
                        label=(
                            f"Generating {n_briefs} image(s) for {run['timestamp']}"
                            + (" via Higgs Field Soul" if use_hf else "")
                        ),
                    )
                    st.rerun()
            with action_r:
                rel = run_dir.relative_to(REPO_ROOT)
                st.caption(f"📂 `{rel}`")


def _render_gaps_tab(selected):
    gap_yaml = CLIENTS_DIR / selected / "research" / "competitive-gaps.yaml"
    if not gap_yaml.exists():
        st.info(
            f"No gap map yet. Run: `adc research-competitors --client {selected}` "
            f"then `adc analyze-gaps --client {selected}`."
        )
        return
    try:
        gd = yaml.safe_load(gap_yaml.read_text(encoding="utf-8")) or {}
    except Exception:
        gd = {}
    syn = gd.get("synthesis", {})
    if syn.get("summary"):
        st.markdown(f"**Strategic thesis:** {syn['summary']}")
        st.divider()
    if syn.get("exploitable_gaps"):
        st.subheader(f"Exploitable Gaps ({len(syn['exploitable_gaps'])})")
        for g in syn["exploitable_gaps"]:
            with st.expander(g.get("opportunity", "—")):
                st.markdown(f"**Competitors failing:** {', '.join(g.get('competitors_failing', []) or [])}")
                if g.get("customer_evidence"):
                    st.markdown(f"**Evidence:** _{g['customer_evidence']}_")
                if g.get("our_advantage"):
                    st.markdown(f"**Our advantage:** {g['our_advantage']}")
                if g.get("ad_angle"):
                    st.success(f"**Ad angle:** {g['ad_angle']}")
    if syn.get("shared_dealbreakers"):
        st.subheader(f"Category-wide Dealbreakers ({len(syn['shared_dealbreakers'])})")
        for d in syn["shared_dealbreakers"]:
            with st.expander(d.get("issue", "—")):
                st.markdown(f"**Affects:** {', '.join(d.get('affected_competitors', []) or [])}")
                if d.get("our_response"):
                    st.markdown(f"**Our response:** {d['our_response']}")
    if syn.get("defensive_priorities"):
        st.subheader(f"Defensive Priorities ({len(syn['defensive_priorities'])})")
        for d in syn["defensive_priorities"]:
            with st.expander(d.get("objection", "—")):
                if d.get("pre_empt"):
                    st.markdown(f"**Pre-empt:** {d['pre_empt']}")


def _render_psychology_tab(selected):
    avatars_dir = CLIENTS_DIR / selected / "avatars"
    avatar_files = sorted(avatars_dir.glob("*.yaml")) if avatars_dir.exists() else []
    avatar_files = [f for f in avatar_files if f.name != "_index.yaml" and not f.name.endswith(".bak")]
    if not avatar_files:
        st.info(f"No avatars yet for {selected}. Run `adc personas --client {selected}` first.")
        return

    # Plain-English glossary for non-specialists. Always available at the top.
    with st.expander("📚 Glossary — what these psychology terms mean (in plain English)"):
        gl_cols = st.columns(2)
        with gl_cols[0]:
            st.markdown("**Heuristics** (mental shortcuts buyers use)")
            for name, defn in HEURISTIC_GLOSSARY.items():
                st.markdown(f"- **`{name}`** — {defn}")
        with gl_cols[1]:
            st.markdown("**Creative pairings** (combinations of two psychology levers)")
            for name, defn in PAIRING_GLOSSARY.items():
                st.markdown(f"- **`{name}`** — {defn}")
    st.divider()

    st.write(f"**{len(avatar_files)} avatar(s)**")
    for f in avatar_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        # The file stem (e.g. "primary", "secondary") is the role slug used by
        # `adc profile-psychology --avatar <slug>`, while d["name"] is the
        # human-readable persona ("Done-Everything Danielle"). Show both —
        # otherwise the user just sees "Primary / Secondary / ..." with no
        # way to tell which buyer that maps to.
        role_slug = f.stem
        display_name = (d.get("name") or "").strip() or role_slug
        profile = d.get("psychology_profile") or {}
        has_profile = bool(profile)
        with st.expander(
            f"{'✅' if has_profile else '⬜'} {display_name}  ·  _{role_slug}_"
            + (f"  —  {len(profile.get('dominant_heuristics', []))} dominant heuristics"
               if has_profile else "  (no profile yet)")
        ):
            if not has_profile:
                st.warning(
                    f"This avatar has no psychology profile. "
                    f"Run `adc profile-psychology --client {selected} --avatar {role_slug}`."
                )
                st.caption(f"Demographic: {d.get('demographic', '—')}")
                continue
            ep = profile.get("emotional_position") or {}
            pri = ep.get("primary") or {}
            sec = ep.get("secondary") or {}
            if pri:
                st.markdown(
                    f"**Emotional position:** primary `{pri.get('valence', '')}/"
                    f"{pri.get('intensity', '')}`, secondary `{sec.get('valence', '')}/"
                    f"{sec.get('intensity', '')}`"
                )
                if pri.get("rationale"):
                    st.caption(pri["rationale"])
            col_l, col_r = st.columns(2)
            with col_l:
                if profile.get("dominant_heuristics"):
                    st.markdown("**Dominant heuristics** (lean into these)")
                    for h in profile["dominant_heuristics"]:
                        name = h.get("heuristic", "")
                        st.markdown(
                            f"- `{name}` _({h.get('confidence', '')} confidence)_"
                        )
                        glossary = _glossary_caption(name, HEURISTIC_GLOSSARY)
                        if glossary:
                            st.caption(f"💡 _What it means:_ {glossary}")
                        if h.get("ad_implications"):
                            st.caption(f"📌 _For this buyer:_ {h['ad_implications']}")
                if profile.get("recommended_prompt_pairings"):
                    st.markdown("**Recommended creative pairings**")
                    for p in profile["recommended_prompt_pairings"]:
                        name = p.get("pairing", "")
                        st.markdown(f"- `{name}`")
                        glossary = _glossary_caption(name, PAIRING_GLOSSARY)
                        if glossary:
                            st.caption(f"💡 _What it means:_ {glossary}")
                        if p.get("fits_because"):
                            st.caption(f"📌 _Fits because:_ {p['fits_because']}")
            with col_r:
                if profile.get("weak_heuristics"):
                    st.markdown("**Avoid these heuristics** (will backfire)")
                    for h in profile["weak_heuristics"]:
                        name = h.get("heuristic", "")
                        st.markdown(f"- `{name}`")
                        glossary = _glossary_caption(name, HEURISTIC_GLOSSARY)
                        if glossary:
                            st.caption(f"💡 _What it means:_ {glossary}")
                        if h.get("avoid"):
                            st.caption(f"⚠️ _What NOT to do:_ {h['avoid']}")
                if profile.get("avoid_pairings"):
                    st.markdown("**Banned creative pairings**")
                    for p in profile["avoid_pairings"]:
                        name = p.get("pairing", "")
                        st.markdown(f"- `{name}`")
                        glossary = _glossary_caption(name, PAIRING_GLOSSARY)
                        if glossary:
                            st.caption(f"💡 _What it means:_ {glossary}")
                        if p.get("avoid_because"):
                            st.caption(f"⚠️ _Why avoid:_ {p['avoid_because']}")


def _render_templates_tab(selected):
    """Browse Cooper-style templates extracted from the client's reference ads.

    Each template's source image is shown alongside its metadata (id, name,
    tags, category). Copy the template ID into the Actions → Image Generation
    → Manual override picker to force generation against a specific template.
    """
    templates_root = CLIENTS_DIR / selected / "templates"
    raw_root = CLIENTS_DIR / selected / "reference_ads" / "raw"

    if not templates_root.exists():
        st.info(
            f"No templates extracted yet for `{selected}`. Run "
            f"`adc extract-templates --client {selected}` first. "
            "Requires reference ads in `clients/<slug>/reference_ads/raw/`."
        )
        return

    # Load all usable templates (template_prompt > 50 chars)
    all_templates: list[dict] = []
    for tpl_yaml in sorted(templates_root.rglob("*.yaml")):
        try:
            d = yaml.safe_load(tpl_yaml.read_text(encoding="utf-8")) or {}
            body = (d.get("template_prompt") or "").strip()
            if not body or len(body) < 50:
                continue
            # Resolve source image
            category = tpl_yaml.parent.name
            stem = tpl_yaml.stem
            source_image = None
            for ext in (".png", ".jpg", ".jpeg", ".webp"):
                candidate = raw_root / category / f"{stem}{ext}"
                if candidate.exists():
                    source_image = candidate
                    break
            all_templates.append({
                "id": d.get("id", stem),
                "name": d.get("name", "—"),
                "category": d.get("category", category),
                "tags": d.get("tags") or [],
                "description": d.get("description", ""),
                "source_image": source_image,
                "yaml_path": tpl_yaml,
                "template_prompt": body,
            })
        except Exception:
            continue

    if not all_templates:
        st.info(
            "Templates folder exists but no usable templates found. "
            f"Re-run `adc extract-templates --client {selected} --force`."
        )
        return

    # Header metrics + category filter
    cats = sorted({t["category"] for t in all_templates})
    by_cat: dict[str, int] = {}
    for t in all_templates:
        by_cat[t["category"]] = by_cat.get(t["category"], 0) + 1

    c1, c2, c3 = st.columns(3)
    c1.metric("Total templates", len(all_templates))
    c2.metric("Categories", len(cats))
    c3.metric("Largest category",
              f"{max(by_cat, key=by_cat.get)} ({max(by_cat.values())})")

    chosen_cat = st.selectbox(
        "Category", ["(all)"] + cats, index=0, key="templates_filter_category",
    )

    filtered = (
        all_templates if chosen_cat == "(all)"
        else [t for t in all_templates if t["category"] == chosen_cat]
    )

    st.caption(
        f"Showing {len(filtered)} template(s). "
        "Click any thumbnail to enlarge. Copy the Template ID into "
        "Actions → Image Generation → Manual override to use it."
    )

    # Grid: 3 columns, each card = thumbnail + metadata + "Copy ID" affordance
    cols_per_row = 3
    for i in range(0, len(filtered), cols_per_row):
        row = st.columns(cols_per_row)
        for j, t in enumerate(filtered[i:i + cols_per_row]):
            with row[j]:
                if t["source_image"] and t["source_image"].exists():
                    st.image(str(t["source_image"]), use_container_width=True)
                else:
                    st.markdown("_(source image not found on disk)_")
                st.markdown(f"**{t['name']}**")
                st.caption(f"`{t['category']}`")
                st.code(t["id"], language=None)
                if t["tags"]:
                    st.caption("Tags: " + ", ".join(t["tags"][:5]))
                with st.expander("Template body", expanded=False):
                    st.markdown(f"_{t['description']}_" if t["description"] else "")
                    st.text(t["template_prompt"])


def _render_costs_tab(selected):
    entries = read_costs(selected)
    cur_month = total_for_month(selected)
    all_time = total_all_time(selected)

    col1, col2, col3 = st.columns(3)
    col1.metric(f"Spent {datetime.now().strftime('%b %Y')}", f"${cur_month:.2f}")
    col2.metric("All time", f"${all_time:.2f}")
    col3.metric("Logged runs", len(entries))

    if not entries:
        st.info(
            "No cost entries logged yet. Costs will accumulate as you run paid commands "
            "(brief, generate, research-competitors, analyze-gaps, etc.)."
        )
        return

    # Cost by command (pie/bar)
    by_cmd: dict[str, float] = {}
    for e in entries:
        by_cmd[e.command] = by_cmd.get(e.command, 0.0) + e.cost
    cmd_df = pd.DataFrame(
        sorted(by_cmd.items(), key=lambda x: -x[1]),
        columns=["Command", "Spent"],
    )
    st.subheader("Spend by command (all-time)")
    st.bar_chart(cmd_df.set_index("Command"), height=240)

    st.subheader("Recent activity")
    recent = recent_entries(selected, limit=25)
    rows = []
    for e in recent:
        ts = datetime.fromisoformat(e.timestamp)
        rows.append({
            "When": ts.strftime("%Y-%m-%d %H:%M"),
            "Command": e.command,
            "Cost": e.cost,
            "Note": e.note,
        })
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
        column_config={"Cost": st.column_config.NumberColumn(format="$%.4f")},
    )


def _render_actions_tab(selected):
    st.subheader("Run commands directly from the dashboard")
    st.caption(
        "Each action shells out to the CLI in the background. Output streams live. "
        "Costs are deducted from your provider accounts (Anthropic, Apify, fal.ai, Exa, "
        "Firecrawl) — estimated costs shown next to each button."
    )

    # ─── Research actions ─────────────────────────────────────────────────
    st.markdown("#### Research")
    rc1, rc2, rc3 = st.columns(3)

    with rc1:
        if st.button("🔍 Refresh web research", help="adc research-competitors", use_container_width=True):
            run_adc_command(["research-competitors", "--client", selected],
                            label="Pulling competitive web sentiment (~$2)")
            st.rerun()
        st.caption("Est: ~$2 (Exa + Firecrawl)")

    with rc2:
        if st.button("⭐ Pull Amazon reviews (stratified)",
                     help="adc research-amazon (5/3/1 star tiers)", use_container_width=True):
            run_adc_command(["research-amazon", "--client", selected],
                            label="Scraping Amazon reviews (free tier, ~$0)")
            st.rerun()
        st.caption("Est: free tier (Apify $5/mo budget)")

    with rc3:
        if st.button("🎯 Refresh gap map", help="adc analyze-gaps", use_container_width=True):
            run_adc_command(["analyze-gaps", "--client", selected],
                            label="Running gap analysis (~$1.50)")
            st.rerun()
        st.caption("Est: ~$1.50 (Sonnet 4.6)")

    st.divider()

    # ─── Avatar discovery (shared by Personas + Psychology sections) ──────
    # Built once because both sections below need the same set: persona
    # management (add/delete) and psychology profiling. The (label, slug)
    # tuple lets dropdowns show the buyer's name while still passing the
    # filename stem to the CLI.
    avatars_dir = CLIENTS_DIR / selected / "avatars"
    avatar_files = sorted(avatars_dir.glob("*.yaml")) if avatars_dir.exists() else []
    avatar_files = [f for f in avatar_files if f.name != "_index.yaml"]
    avatar_options: list[tuple[str, str]] = []
    for f in avatar_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            d = {}
        display = (d.get("name") or "").strip() or f.stem
        avatar_options.append((f"{display}  ·  {f.stem}", f.stem))

    # Hard cap on personas. Matches strategy.personas.MAX_PERSONAS; copied
    # here so the dashboard doesn't import a strategy module just for a
    # constant. If you bump that, update this too.
    MAX_PERSONAS = 6

    # ─── Personas (add / delete) ──────────────────────────────────────────
    st.markdown("#### Personas")
    n_personas = len(avatar_options)
    at_cap = n_personas >= MAX_PERSONAS
    st.caption(
        f"{n_personas} / {MAX_PERSONAS} personas. "
        + ("**At cap** — delete one below before adding another." if at_cap else
           "You can add more, up to the cap.")
    )

    ac1, ac2 = st.columns(2)
    with ac1:
        add_disabled = at_cap or n_personas == 0  # need brand context first
        if st.button(
            "➕ Add a new persona",
            help=("Generates ONE new persona that's distinct from the existing set "
                  "(different pains, triggers, awareness). ~$0.10 in API cost."),
            use_container_width=True,
            disabled=at_cap,
        ):
            run_adc_command(
                ["add-persona", "--client", selected],
                label="Generating one new persona (~$0.10)",
            )
            st.rerun()
        st.caption("Est: ~$0.10 (Sonnet 4.6, single persona)")

    with ac2:
        if avatar_options:
            labels = [label for label, _slug in avatar_options]
            del_label = st.selectbox(
                "Delete a persona:",
                labels,
                key="delete_persona_pick",
                help="The avatar file and its entry in _index.yaml are removed. "
                     "Existing briefs that reference the persona by name are NOT touched.",
            )
            del_slug = dict(avatar_options)[del_label]
            # The actual delete is gated by a confirm checkbox so the user
            # can't fat-finger a destructive click. We pass --yes to the CLI
            # because the confirm has already happened in the UI.
            confirm = st.checkbox(
                f"I understand — permanently delete `{del_slug}.yaml`",
                key=f"delete_persona_confirm_{del_slug}",
            )
            if st.button(
                f"🗑️ Delete `{del_label}`",
                use_container_width=True,
                disabled=not confirm,
                type="secondary",
            ):
                run_adc_command(
                    ["delete-persona", "--client", selected, "--avatar", del_slug, "--yes"],
                    label=f"Deleting persona {del_slug}",
                )
                st.rerun()
        else:
            st.caption("No personas to delete yet.")

    st.divider()

    # ─── Psychology actions ───────────────────────────────────────────────
    st.markdown("#### Psychology")
    pc1, pc2 = st.columns(2)

    with pc1:
        if st.button("🧠 Profile ALL avatars",
                     help="adc profile-psychology (all)", use_container_width=True):
            run_adc_command(["profile-psychology", "--client", selected],
                            label="Diagnosing buyer psychology (~$0.30/avatar)")
            st.rerun()
        st.caption(f"Est: ~$0.30 × {len(avatar_options)} avatar(s)")

    with pc2:
        if avatar_options:
            labels = [label for label, _slug in avatar_options]
            chosen_label = st.selectbox("Or one avatar:", labels, key="psych_avatar")
            chosen_slug = dict(avatar_options)[chosen_label]
            if st.button(f"🧠 Profile `{chosen_label}` only", use_container_width=True):
                run_adc_command(
                    ["profile-psychology", "--client", selected, "--avatar", chosen_slug],
                    label=f"Diagnosing psychology for {chosen_label} (~$0.30)",
                )
                st.rerun()
        else:
            st.caption("No avatars to profile yet.")

    st.divider()

    # ─── Brief generation ─────────────────────────────────────────────────
    st.markdown("#### Brief generation")
    products_dir = CLIENTS_DIR / selected / "products"
    product_slugs: list[str] = []
    if products_dir.exists():
        for f in sorted(products_dir.glob("*.yaml")):
            if f.name == "example-product.yaml":
                continue
            product_slugs.append(f.stem)

    if not product_slugs:
        st.info(f"No products yet for {selected}. Run `adc research --client {selected} --url ...` first.")
    else:
        bc1, bc2, bc3 = st.columns([2, 1, 1])
        with bc1:
            chosen_product = st.selectbox("Product", product_slugs, key="brief_product")
        with bc2:
            n_angles = st.number_input("Angles", min_value=1, max_value=10, value=6, key="brief_angles")
        with bc3:
            ignore_psych = st.checkbox("Ignore psychology", key="brief_ignore_psych",
                                       help="Bypass psychology profile guardrails for comparison")
        if st.button(f"📝 Generate {n_angles} briefs for `{chosen_product}`",
                     use_container_width=True, type="primary"):
            args = ["brief", "--client", selected, "--product", chosen_product,
                    "--angles", str(int(n_angles))]
            if ignore_psych:
                args.append("--ignore-psychology")
            run_adc_command(args, label=f"Generating {n_angles} briefs (~$0.50)")
            st.rerun()
        st.caption("Est: ~$0.50 (Sonnet 4.6)")

    st.divider()

    # ─── Image generation ─────────────────────────────────────────────────
    st.markdown("#### Image generation")
    briefs_dir = CLIENTS_DIR / selected / "briefs"
    n_briefs = len(list(briefs_dir.glob("*.yaml"))) if briefs_dir.exists() else 0
    if n_briefs == 0:
        st.info("No briefs to generate from yet.")
    else:
        ic1, ic2 = st.columns([3, 1])
        with ic1:
            picks = st.text_input(
                f"Brief picks (1-{n_briefs}, comma-separated)",
                placeholder="e.g. 1,3,5",
                key="generate_picks",
                help="The `#N` in each brief's header (Briefs tab) corresponds to the pick number used here.",
            )
        with ic2:
            num_images = st.number_input("Variations", min_value=1, max_value=4, value=1, key="generate_num_images")

        include_alts = st.checkbox(
            "Include visual-format alternates (3 variants per brief instead of 1)",
            key="generate_include_alternates",
            help="Generates the primary visual_format + each visual_format_alternatives "
            "entry per brief. Same psychological mechanic, different production styles — "
            "useful for A/B/C variance testing. Triples the image count and cost.",
        )

        # ── Reference mode toggle ────────────────────────────────────────
        # Auto-pick is default. Manual picks a specific template for all picks.
        # Build the template list from disk so the picker stays in sync with
        # whatever templates have been extracted.
        templates_dir = CLIENTS_DIR / selected / "templates"
        all_templates: list[dict] = []
        if templates_dir.exists():
            for tpl_yaml in sorted(templates_dir.rglob("*.yaml")):
                try:
                    td = yaml.safe_load(tpl_yaml.read_text(encoding="utf-8")) or {}
                    body = (td.get("template_prompt") or "").strip()
                    if not body or len(body) < 50:
                        continue
                    all_templates.append({
                        "id": td.get("id", tpl_yaml.stem),
                        "name": td.get("name", "—"),
                        "category": td.get("category", "—"),
                        "tags": td.get("tags") or [],
                    })
                except Exception:
                    continue

        reference_mode = st.radio(
            "Reference mode",
            ["Auto-pick (system picks the best template per brief)",
             "Manual override (use ONE specific template for ALL picks in this run)"],
            index=0,
            key="generate_reference_mode",
            horizontal=False,
        )

        chosen_template_id = None
        if reference_mode.startswith("Manual") and all_templates:
            cats = sorted({t["category"] for t in all_templates})
            mc1, mc2 = st.columns([1, 3])
            with mc1:
                chosen_cat = st.selectbox(
                    "Category filter", ["(all)"] + cats, key="generate_ref_category",
                )
            filtered = (
                all_templates if chosen_cat == "(all)"
                else [t for t in all_templates if t["category"] == chosen_cat]
            )
            with mc2:
                if filtered:
                    label_for = lambda t: f"[{t['category']}] {t['id']} — {t['name']}"
                    chosen_label = st.selectbox(
                        "Template",
                        [label_for(t) for t in filtered],
                        key="generate_ref_template",
                    )
                    chosen_template_id = next(
                        (t["id"] for t in filtered if label_for(t) == chosen_label),
                        None,
                    )
                else:
                    st.caption("No templates in this category.")
            if chosen_template_id:
                st.caption(f"Will pass `--reference {chosen_template_id}` to generate.")
        elif reference_mode.startswith("Manual") and not all_templates:
            st.warning(
                "No client templates extracted yet. Run "
                f"`adc extract-templates --client {selected}` first."
            )

        gen_cd = st.text_area(
            "Creative direction (optional)",
            key="generate_creative_direction",
            placeholder=(
                "e.g. 'two callouts in primary brand color + accent, text bubble at top, "
                "hand from bottom holding product, no FDA disclaimer'"
            ),
            height=70,
            help=(
                "Pre-generation directive applied to EVERY picked brief. Locks in "
                "structural elements (text bubble, callouts) and styling cues (brand colors "
                "for pills). Highest-priority constraint — overrides defaults from "
                "the brief / template / library skills when in conflict."
            ),
        )

        gen_offer = st.text_input(
            "Offer code (slot 9 of the naming taxonomy)",
            value="NONE",
            key="generate_offer",
            placeholder="e.g. FREESHIP, BFCM25, 20OFF",
            help=(
                "Promo code that appears in the campaign name (slot 9). "
                "Alphanumeric only, capped at 12 chars. Use 'NONE' for ads without an offer."
            ),
        )

        # ── Engine toggle ───────────────────────────────────────────────
        # When ON: route through Higgs Field soul_2 with each persona's
        # trained Soul Character + PIL text overlay. Ignores --reference and
        # the product image because soul_2 doesn't accept multi-image edits.
        # Falls back to NB2 automatically if HF API credits are empty.
        use_hf_gen = st.checkbox(
            "Use Higgs Field (identity-locked) — falls back to NB2 if HF credits are empty",
            key="generate_use_hf",
            help=(
                "Off: fast NB2 with your product image + auto-pick / manual template "
                "(default, no identity lock). "
                "On: routes through each persona's trained Soul Character via Higgs "
                "Field soul_2 + PIL text overlay — same face every generation. "
                "Reference templates are ignored in HF mode because soul_2 doesn't "
                "accept multi-image edits. Requires HF_CREDENTIALS in .env and a "
                "'ready' Soul Character on each persona's avatar YAML. If the Higgs "
                "Field REST API has no credits, the run automatically falls back to NB2."
            ),
        )

        engine_suffix = " (HF Soul)" if use_hf_gen else ""
        if st.button(f"🖼️ Generate images for picks{engine_suffix}",
                     use_container_width=True, type="primary",
                     disabled=not picks.strip()):
            args = ["generate", "--client", selected, "--pick", picks.strip(),
                    "--num-images", str(int(num_images)),
                    "--offer", gen_offer.strip() or "NONE"]
            if include_alts:
                args.append("--include-alternates")
            if reference_mode.startswith("Manual") and chosen_template_id and not use_hf_gen:
                args.extend(["--reference", chosen_template_id])
            if gen_cd.strip():
                args.extend(["--creative-direction", gen_cd.strip()])
            if use_hf_gen:
                args.extend([
                    "--engine", "higgsfield-soul",
                    "--fallback-engine", "nb2",
                ])
            n_picks = len([p for p in picks.split(",") if p.strip()])
            variants_per_brief = 3 if include_alts else 1
            total_imgs = n_picks * int(num_images) * variants_per_brief
            run_adc_command(
                args,
                label=(
                    f"Generating {total_imgs} image(s) (~${total_imgs * 0.08:.2f})"
                    + (" via Higgs Field Soul" if use_hf_gen else "")
                ),
            )
            st.rerun()
        st.caption(
            "Est: ~$0.08 per image (Sonnet prompt + fal.ai NB2). "
            "HF Soul mode uses Higgs Field Ultra credits instead. "
            "Auto-pick picks 1 reference per brief (ignored in HF mode); "
            "Manual override applies one template to all picks (ignored in HF mode)."
        )


# ───────────────────────────────────────────────────────────────────────────
# Sidebar router
# ───────────────────────────────────────────────────────────────────────────


clients = _list_clients()

with st.sidebar:
    st.title("AdCreatives")
    if not clients:
        st.warning("No clients found.")
        st.stop()

    if "view" not in st.session_state:
        st.session_state["view"] = "overview" if len(clients) > 1 else "detail"
    if "selected_client" not in st.session_state:
        st.session_state["selected_client"] = clients[0]

    view = st.radio(
        "View",
        ["Overview", "Client detail"],
        index=0 if st.session_state["view"] == "overview" else 1,
        key="view_radio",
    )
    st.session_state["view"] = "overview" if view == "Overview" else "detail"

    if st.session_state["view"] == "detail":
        idx = clients.index(st.session_state["selected_client"]) if (
            st.session_state["selected_client"] in clients
        ) else 0
        chosen = st.selectbox("Client", clients, index=idx)
        st.session_state["selected_client"] = chosen

    if st.button("↻ Refresh data", use_container_width=True):
        st.rerun()

    st.divider()
    st.caption(f"Repo: `{REPO_ROOT.name}`")


# ───────────────────────────────────────────────────────────────────────────
# Dispatch
# ───────────────────────────────────────────────────────────────────────────


if st.session_state["view"] == "overview":
    render_overview(clients)
else:
    render_client_detail(st.session_state["selected_client"])
