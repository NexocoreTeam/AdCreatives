"""Preflight grading for research runs — say it BEFORE spending money.

The Zoka run taught the lesson twice: config quality decides yield
(brand handles = 16 comments, search queries = 268), and finding that out
after the run wastes the spend. These graders read competitors.yaml and
produce a plain verdict the CLI prints before executing.

Pure functions, no network, no filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass

# grade meanings:
#   strong — explicit URLs/IDs or search queries: high expected yield
#   weak   — brand-owned handle only: low-volume/generic VOC
#   none   — nothing configured for the platform
GRADE_STRONG = "strong"
GRADE_WEAK = "weak"
GRADE_NONE = "none"


@dataclass
class SourceGrade:
    competitor: str
    platform: str   # youtube | tiktok | instagram
    grade: str
    source: str     # human description of what's configured


def grade_social_sources(competitors) -> list[SourceGrade]:
    grades: list[SourceGrade] = []
    for c in competitors:
        if c.youtube_video_ids:
            yt = (GRADE_STRONG, f"{len(c.youtube_video_ids)} explicit video ID(s)")
        elif getattr(c, "youtube_search_queries", None):
            yt = (GRADE_STRONG, f"search: {', '.join(c.youtube_search_queries[:2])}")
        elif c.youtube_channel_id or c.youtube_handle:
            yt = (GRADE_WEAK, f"brand handle only ({c.youtube_handle or c.youtube_channel_id})")
        else:
            yt = (GRADE_NONE, "nothing configured")
        grades.append(SourceGrade(c.name, "youtube", *yt))

        if c.tiktok_post_urls:
            tt = (GRADE_STRONG, f"{len(c.tiktok_post_urls)} explicit post URL(s)")
        elif c.tiktok_search_queries:
            tt = (GRADE_STRONG, f"search: {', '.join(c.tiktok_search_queries[:2])}")
        elif c.tiktok_handle:
            tt = (GRADE_WEAK, f"brand handle only ({c.tiktok_handle})")
        else:
            tt = (GRADE_NONE, "nothing configured")
        grades.append(SourceGrade(c.name, "tiktok", *tt))

        if c.instagram_post_urls:
            ig = (GRADE_STRONG, f"{len(c.instagram_post_urls)} explicit post URL(s)")
        elif c.instagram_handle:
            ig = (GRADE_WEAK, f"brand handle only ({c.instagram_handle})")
        else:
            ig = (GRADE_NONE, "nothing configured")
        grades.append(SourceGrade(c.name, "instagram", *ig))
    return grades


def social_preflight_lines(competitors, client_slug: str) -> list[str]:
    """Summary lines for the CLI. Last line is the verdict."""
    grades = grade_social_sources(competitors)
    configured = [g for g in grades if g.grade != GRADE_NONE]
    strong = [g for g in configured if g.grade == GRADE_STRONG]
    weak = [g for g in configured if g.grade == GRADE_WEAK]

    lines = [
        f"Source preflight: {len(strong)} strong / {len(weak)} weak of "
        f"{len(configured)} configured (platform, competitor) source(s)."
    ]
    for g in weak:
        lines.append(f"  weak: {g.platform}/{g.competitor} — {g.source}")

    if not configured:
        lines.append(
            "VERDICT: nothing configured — add search queries / post URLs to "
            f"competitors.yaml first (adc scaffold-competitors --client {client_slug} --apply)."
        )
    elif not strong:
        lines.append(
            "VERDICT: expected yield LOW — every configured source is a "
            "brand-owned handle. Add *_search_queries or explicit URLs before "
            f"spending (adc scaffold-competitors --client {client_slug} --apply)."
        )
    elif weak:
        lines.append(
            "VERDICT: OK — strong sources present; weak handle-only rows will "
            "under-deliver and can be upgraded with search queries."
        )
    else:
        lines.append("VERDICT: OK — all configured sources are strong.")
    return lines


def amazon_preflight_line(competitors, client_slug: str) -> str:
    with_urls = sum(1 for c in competitors if c.amazon_urls)
    if with_urls:
        return (
            f"Amazon preflight: {with_urls}/{len(competitors)} competitor(s) "
            f"have amazon_urls configured."
        )
    return (
        f"Amazon preflight: no amazon_urls configured — that layer will be "
        f"skipped (candidates: adc suggest-amazon --client {client_slug})."
    )


def homepage_preflight_line(competitors, client_slug: str) -> str | None:
    """Warn when competitors lack homepage URLs — the on-site review layer
    and PDP discovery silently come back empty for them (found live on the
    expand-furniture kickoff: scaffolded file ran before urls were filled)."""
    missing = [c.name for c in competitors if not (c.url or "").strip()]
    if not missing:
        return None
    shown = ", ".join(missing[:4]) + (" (+more)" if len(missing) > 4 else "")
    return (
        f"Homepage preflight: {len(missing)} competitor(s) have no url — "
        f"on-site reviews and PDP discovery will be EMPTY for: {shown}. "
        f"Fill url fields in clients/{client_slug}/competitors.yaml first."
    )
