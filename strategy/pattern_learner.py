"""Analyze performance data and extract winning patterns for the feedback loop."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from models.result import (
    CreativeResult,
    HookPerformance,
    StylePerformance,
    WinningPatterns,
)
from strategy.llm import claude_complete

ANALYSIS_SYSTEM = """You are a performance marketing analyst. Given a set of ad creative
performance data, identify actionable patterns and make specific recommendations
for the next batch of creatives.

Be specific. Don't say "try different hooks" — say "pain-number hooks averaged 2.1% CTR
vs 1.3% for question hooks, lean into pain-number format."

Output 3-5 specific, actionable recommendations."""


def analyze_results(
    results: list[CreativeResult],
    client_slug: str,
    days: int = 90,
) -> WinningPatterns:
    """Compute winning patterns from performance log data."""
    cutoff = date.today() - timedelta(days=days)
    recent = [r for r in results if r.date_logged >= cutoff]

    if not recent:
        return WinningPatterns(
            client=client_slug,
            days_analyzed=days,
            total_creatives_analyzed=0,
            recommendations=["No performance data yet. Run some ads and log results."],
        )

    # Aggregate by style
    style_metrics = _aggregate_by_field(recent, "style")
    best_styles = sorted(style_metrics, key=lambda s: s.avg_ctr, reverse=True)
    worst_styles = sorted(style_metrics, key=lambda s: s.avg_ctr)

    # Aggregate by hook type (simplified — uses angle as proxy)
    hook_metrics = _aggregate_hooks(recent)

    # Aggregate by framework
    framework_counts: dict[str, list[float]] = defaultdict(list)
    for r in recent:
        if r.framework and r.ctr is not None:
            framework_counts[r.framework].append(r.ctr)
    best_frameworks = sorted(
        framework_counts.keys(),
        key=lambda f: sum(framework_counts[f]) / len(framework_counts[f]),
        reverse=True,
    )

    # Aggregate callout themes
    callout_scores: dict[str, list[float]] = defaultdict(list)
    for r in recent:
        if r.ctr is not None:
            for callout in r.callouts:
                # Simple keyword extraction from callouts
                for keyword in _extract_callout_theme(callout):
                    callout_scores[keyword].append(r.ctr)
    best_callout_themes = sorted(
        callout_scores.keys(),
        key=lambda k: sum(callout_scores[k]) / len(callout_scores[k]),
        reverse=True,
    )[:5]

    # Platform insights
    platform_insights = _platform_breakdown(recent)

    # AI-generated recommendations
    recommendations = _generate_recommendations(recent, best_styles, worst_styles)

    return WinningPatterns(
        client=client_slug,
        days_analyzed=days,
        total_creatives_analyzed=len(recent),
        best_styles=best_styles[:3],
        worst_styles=worst_styles[:3],
        best_hooks=hook_metrics[:5],
        best_angles=[],  # Populated by recommendations
        best_callout_themes=best_callout_themes,
        best_frameworks=best_frameworks[:3],
        platform_insights=platform_insights,
        recommendations=recommendations,
    )


def _aggregate_by_field(results: list[CreativeResult], field: str) -> list[StylePerformance]:
    """Aggregate CTR/CPA/ROAS by a given field."""
    buckets: dict[str, list[CreativeResult]] = defaultdict(list)
    for r in results:
        val = getattr(r, field, "")
        if val:
            buckets[val].append(r)

    performances = []
    for style_name, items in buckets.items():
        ctrs = [r.ctr for r in items if r.ctr is not None]
        cpas = [r.cpa for r in items if r.cpa is not None]
        roases = [r.roas for r in items if r.roas is not None]
        if ctrs:
            performances.append(StylePerformance(
                style=style_name,
                avg_ctr=sum(ctrs) / len(ctrs),
                avg_cpa=sum(cpas) / len(cpas) if cpas else None,
                avg_roas=sum(roases) / len(roases) if roases else None,
                sample_size=len(items),
            ))
    return performances


def _aggregate_hooks(results: list[CreativeResult]) -> list[HookPerformance]:
    """Aggregate performance by hook/angle."""
    hook_buckets: dict[str, list[CreativeResult]] = defaultdict(list)
    for r in results:
        hook_type = r.angle or r.hook or "unknown"
        hook_buckets[hook_type].append(r)

    performances = []
    for hook_type, items in hook_buckets.items():
        ctrs = [r.ctr for r in items if r.ctr is not None]
        if ctrs:
            best = max(items, key=lambda r: r.ctr or 0)
            performances.append(HookPerformance(
                hook_type=hook_type,
                avg_ctr=sum(ctrs) / len(ctrs),
                sample_size=len(items),
                best_example=best.hook,
            ))
    return sorted(performances, key=lambda h: h.avg_ctr, reverse=True)


def _extract_callout_theme(callout: str) -> list[str]:
    """Extract theme keywords from a callout string."""
    themes = []
    callout_lower = callout.lower()
    theme_keywords = {
        "time": ["save", "hour", "minute", "fast", "quick", "time"],
        "money": ["save", "cost", "price", "free", "cheap", "afford"],
        "ease": ["easy", "simple", "no hassle", "effortless", "one-click"],
        "trust": ["review", "star", "rated", "trusted", "proven"],
        "results": ["result", "outcome", "achieve", "success", "growth"],
    }
    for theme, keywords in theme_keywords.items():
        if any(kw in callout_lower for kw in keywords):
            themes.append(theme)
    return themes or ["other"]


def _platform_breakdown(results: list[CreativeResult]) -> dict[str, str]:
    """Summarize performance by platform."""
    platform_buckets: dict[str, list[float]] = defaultdict(list)
    for r in results:
        if r.ctr is not None:
            platform_buckets[r.platform].append(r.ctr)

    insights = {}
    for platform, ctrs in platform_buckets.items():
        avg = sum(ctrs) / len(ctrs)
        insights[platform] = f"Avg CTR: {avg:.2f}% across {len(ctrs)} creatives"
    return insights


def _generate_recommendations(
    results: list[CreativeResult],
    best: list[StylePerformance],
    worst: list[StylePerformance],
) -> list[str]:
    """Use Claude to generate actionable recommendations from the data."""
    if len(results) < 5:
        return ["Not enough data yet (need 5+ logged results). Keep testing and logging."]

    summary = "PERFORMANCE DATA SUMMARY:\n\n"
    summary += f"Total creatives analyzed: {len(results)}\n\n"

    if best:
        summary += "BEST PERFORMING STYLES:\n"
        for s in best[:3]:
            summary += f"  - {s.style}: {s.avg_ctr:.2f}% CTR (n={s.sample_size})\n"

    if worst:
        summary += "\nWORST PERFORMING STYLES:\n"
        for s in worst[:3]:
            summary += f"  - {s.style}: {s.avg_ctr:.2f}% CTR (n={s.sample_size})\n"

    summary += "\nINDIVIDUAL RESULTS:\n"
    for r in sorted(results, key=lambda x: x.ctr or 0, reverse=True)[:10]:
        summary += (
            f"  - [{r.verdict or 'n/a'}] {r.style} | hook: '{r.hook}' | "
            f"CTR: {r.ctr}% | angle: {r.angle}\n"
        )

    try:
        result = claude_complete(
            prompt=f"Analyze this ad creative performance data and give 3-5 specific, "
            f"actionable recommendations for the next batch:\n\n{summary}",
            system=ANALYSIS_SYSTEM,
            max_tokens=1024,
        )
        return [line.strip().lstrip("0123456789.-) ") for line in result.strip().split("\n") if line.strip()]
    except Exception:
        # Fallback to simple rules if LLM call fails
        recs = []
        if best:
            recs.append(f"Double down on '{best[0].style}' style — it's your top performer.")
        if worst:
            recs.append(f"Consider dropping '{worst[0].style}' style — lowest CTR.")
        return recs or ["Log more results to unlock AI-powered recommendations."]
