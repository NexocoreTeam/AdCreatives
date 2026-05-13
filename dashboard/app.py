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
    full_cmd = [sys.executable, str(REPO_ROOT / "cli.py")] + cmd_args
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

    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Personas", _summary_value(strategy_stages, "Personas", "0"))
    kpi_cols[1].metric("Briefs", _summary_value(asset_stages, "Briefs", "0"))
    kpi_cols[2].metric("Finished Ads", _summary_value(asset_stages, "Generated ad images", "0"))
    gap_stage = _stage_by_name(competitive_stages, "Competitive gap map")
    kpi_cols[3].metric(
        "Exploitable Gaps",
        gap_stage.summary.split()[0] if gap_stage and gap_stage.summary else "0",
    )
    kpi_cols[4].metric(
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

    tabs = st.tabs(
        ["📊 Status", "📝 Briefs", "🖼️ Ads", "🎯 Gap Map", "🧠 Psychology", "💵 Costs", "⚡ Actions"]
    )

    with tabs[0]:
        _render_status_tab(selected, strategy_stages, competitive_stages, asset_stages)
    with tabs[1]:
        _render_briefs_tab(selected)
    with tabs[2]:
        _render_ads_tab(selected)
    with tabs[3]:
        _render_gaps_tab(selected)
    with tabs[4]:
        _render_psychology_tab(selected)
    with tabs[5]:
        _render_costs_tab(selected)
    with tabs[6]:
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


def _render_briefs_tab(selected):
    briefs_dir = CLIENTS_DIR / selected / "briefs"
    brief_files = sorted(briefs_dir.glob("*.yaml")) if briefs_dir.exists() else []
    if not brief_files:
        st.info(f"No briefs yet. Run: `adc brief --client {selected} --product <id>`")
        return
    st.write(f"**{len(brief_files)} brief(s)** — click any to expand")
    for f in brief_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        slot = d.get("slot", "—")
        hook = (d.get("hook", "") or "")[:80]
        with st.expander(f"Slot {slot} — {hook}..."):
            col_l, col_r = st.columns([2, 1])
            with col_l:
                st.markdown(f"**Hook:** {d.get('hook', '—')}")
                st.markdown(f"**Angle:** {d.get('angle', '—')}")
                st.markdown(f"**Pain point:** {d.get('pain_point', '—')}")
                st.markdown(f"**Persona:** {d.get('persona', '—')}")
                st.markdown(f"**CTA:** {d.get('cta', '—')}")
                if d.get("benefit_callouts"):
                    st.markdown("**Benefit callouts:**")
                    for b in d["benefit_callouts"]:
                        st.markdown(f"  - {b}")
                if d.get("visual_direction"):
                    st.markdown(f"**Visual direction:** {d['visual_direction']}")
            with col_r:
                st.markdown(f"**Framework:** `{d.get('framework', '—')}`")
                st.markdown(f"**Mechanic:** `{d.get('creative_mechanic', '—')}`")
                st.markdown(f"**Format:** `{d.get('visual_format', '—')}`")
                st.markdown(f"**Awareness:** `{d.get('awareness_level', '—')}`")
                st.caption(f"ID: `{d.get('brief_id', f.stem)}`")


def _render_ads_tab(selected):
    images_dir = AI_ADS_DIR / selected / "images"
    image_files = sorted(images_dir.glob("*.png")) if images_dir.exists() else []
    if not image_files:
        st.info(
            f"No generated ad images yet. Run: "
            f"`adc generate --client {selected} --pick 1,2,3`"
        )
        return
    st.write(f"**{len(image_files)} generated ad(s)**")
    cols_per_row = 3
    for i in range(0, len(image_files), cols_per_row):
        row = st.columns(cols_per_row)
        for j, f in enumerate(image_files[i:i + cols_per_row]):
            with row[j]:
                brief_id = f.stem.rsplit("_", 1)[0]
                aspect = f.stem.rsplit("_", 1)[-1] if "_" in f.stem else ""
                st.image(str(f), use_container_width=True)
                st.caption(f"`{brief_id}` ({aspect})")


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
    avatar_files = [f for f in avatar_files if f.name != "_index.yaml"]
    if not avatar_files:
        st.info(f"No avatars yet for {selected}. Run `adc personas --client {selected}` first.")
        return
    st.write(f"**{len(avatar_files)} avatar(s)**")
    for f in avatar_files:
        try:
            d = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        name = f.stem
        profile = d.get("psychology_profile") or {}
        has_profile = bool(profile)
        with st.expander(
            f"{'✅' if has_profile else '⬜'} {name}"
            + (f" — {len(profile.get('dominant_heuristics', []))} dominant heuristics"
               if has_profile else " (no profile yet)")
        ):
            if not has_profile:
                st.warning(
                    f"This avatar has no psychology profile. "
                    f"Run `adc profile-psychology --client {selected} --avatar {name}`."
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
                    st.markdown("**Dominant heuristics**")
                    for h in profile["dominant_heuristics"]:
                        st.markdown(f"- `{h.get('heuristic', '')}` ({h.get('confidence', '')})")
                        if h.get("ad_implications"):
                            st.caption(h["ad_implications"])
                if profile.get("recommended_prompt_pairings"):
                    st.markdown("**Recommended pairings**")
                    for p in profile["recommended_prompt_pairings"]:
                        st.markdown(f"- `{p.get('pairing', '')}`")
            with col_r:
                if profile.get("weak_heuristics"):
                    st.markdown("**Avoid (weak) heuristics**")
                    for h in profile["weak_heuristics"]:
                        st.markdown(f"- `{h.get('heuristic', '')}`")
                        if h.get("avoid"):
                            st.caption(h["avoid"])
                if profile.get("avoid_pairings"):
                    st.markdown("**Banned pairings**")
                    for p in profile["avoid_pairings"]:
                        st.markdown(f"- `{p.get('pairing', '')}`")


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

    # ─── Psychology actions ───────────────────────────────────────────────
    st.markdown("#### Psychology")
    pc1, pc2 = st.columns(2)
    avatars_dir = CLIENTS_DIR / selected / "avatars"
    avatar_files = sorted(avatars_dir.glob("*.yaml")) if avatars_dir.exists() else []
    avatar_files = [f for f in avatar_files if f.name != "_index.yaml"]
    avatar_names = [f.stem for f in avatar_files]

    with pc1:
        if st.button("🧠 Profile ALL avatars",
                     help="adc profile-psychology (all)", use_container_width=True):
            run_adc_command(["profile-psychology", "--client", selected],
                            label="Diagnosing buyer psychology (~$0.30/avatar)")
            st.rerun()
        st.caption(f"Est: ~$0.30 × {len(avatar_names)} avatar(s)")

    with pc2:
        if avatar_names:
            chosen = st.selectbox("Or one avatar:", avatar_names, key="psych_avatar")
            if st.button(f"🧠 Profile `{chosen}` only", use_container_width=True):
                run_adc_command(
                    ["profile-psychology", "--client", selected, "--avatar", chosen],
                    label=f"Diagnosing psychology for {chosen} (~$0.30)",
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
            )
        with ic2:
            num_images = st.number_input("Variations", min_value=1, max_value=4, value=1, key="generate_num_images")

        if st.button("🖼️ Generate images for picks",
                     use_container_width=True, type="primary",
                     disabled=not picks.strip()):
            args = ["generate", "--client", selected, "--pick", picks.strip(),
                    "--num-images", str(int(num_images))]
            n_picks = len([p for p in picks.split(",") if p.strip()])
            total_imgs = n_picks * int(num_images)
            run_adc_command(args, label=f"Generating {total_imgs} image(s) (~${total_imgs * 0.08:.2f})")
            st.rerun()
        st.caption("Est: ~$0.08 per image (Sonnet prompt + fal.ai NB2)")


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
