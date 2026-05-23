"""Shared shapes for Tier 3 social-comment scraping.

TikTok, Instagram, and YouTube comment scrapers all produce the same logical
artifact: a list of SocialComment objects scoped to one source post, grouped
into a SocialCommentBundle per (platform, competitor, post).

Raw archival lives at:
    clients/<slug>/research/<platform>-comments/<competitor>-<post_id>.json

A flattened voc-miner-friendly dump lives at:
    clients/<slug>/voc/<platform>-comments.json

voc_miner.py already loads every *.json in voc/ (except those starting with
`extracted`), so dropping a list of {rating, body} records there is enough to
fold these new sources into the existing extraction pipeline. No changes to
voc_miner are required.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

CLIENTS_DIR = Path("clients")


# ─── Models ─────────────────────────────────────────────────────────────────


@dataclass
class SocialComment:
    """One comment from TikTok, Instagram, or YouTube.

    Cross-platform shape — fields irrelevant to a given platform are left blank.
    Engagement (likes / replies) is captured because it's the strongest
    indicator of which comments resonated with other viewers.
    """

    platform: str = ""             # "tiktok" | "instagram" | "youtube"
    text: str = ""                 # the comment body
    author: str = ""               # handle, no @
    likes: int = 0
    reply_count: int = 0
    posted_at: str = ""            # ISO-8601 or platform timestamp string
    comment_id: str = ""
    post_id: str = ""              # parent post / video id
    post_url: str = ""             # parent post URL
    is_reply: bool = False         # True if this is a reply, not a top-level comment


@dataclass
class SocialCommentBundle:
    """All comments scraped from one source post for one competitor."""

    platform: str = ""
    competitor_slug: str = ""
    competitor_name: str = ""
    post_id: str = ""
    post_url: str = ""
    post_caption: str = ""
    post_metrics: dict = field(default_factory=dict)  # views, likes, etc. on the post itself
    comments: list[SocialComment] = field(default_factory=list)
    fetched_at: str = ""
    notes: str = ""

    def to_json(self) -> dict:
        return {
            "platform": self.platform,
            "competitor_slug": self.competitor_slug,
            "competitor_name": self.competitor_name,
            "post_id": self.post_id,
            "post_url": self.post_url,
            "post_caption": self.post_caption,
            "post_metrics": self.post_metrics,
            "comments": [asdict(c) for c in self.comments],
            "fetched_at": self.fetched_at,
            "notes": self.notes,
        }


# ─── Cache + voc-dump helpers ───────────────────────────────────────────────


def _research_dir(client_slug: str, platform: str) -> Path:
    """clients/<slug>/research/<platform>-comments/"""
    return CLIENTS_DIR / client_slug / "research" / f"{platform}-comments"


def cache_bundle(client_slug: str, bundle: SocialCommentBundle) -> Path:
    """Persist one raw bundle under research/<platform>-comments/.

    Filename pattern: <competitor-slug>-<post-id>.json
    """
    out_dir = _research_dir(client_slug, bundle.platform)
    out_dir.mkdir(parents=True, exist_ok=True)
    post_part = bundle.post_id or "unknown"
    path = out_dir / f"{bundle.competitor_slug}-{post_part}.json"
    path.write_text(json.dumps(bundle.to_json(), indent=2), encoding="utf-8")
    return path


def load_cached_bundles(client_slug: str, platform: str) -> list[SocialCommentBundle]:
    """Reload every cached bundle for one platform. Used by future
    gap_analyzer integration and by the voc-dump refresh path."""
    raw_dir = _research_dir(client_slug, platform)
    if not raw_dir.exists():
        return []
    bundles: list[SocialCommentBundle] = []
    for path in sorted(raw_dir.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        bundles.append(SocialCommentBundle(
            platform=data.get("platform", platform),
            competitor_slug=data.get("competitor_slug", ""),
            competitor_name=data.get("competitor_name", ""),
            post_id=data.get("post_id", ""),
            post_url=data.get("post_url", ""),
            post_caption=data.get("post_caption", ""),
            post_metrics=data.get("post_metrics", {}) or {},
            comments=[SocialComment(**c) for c in data.get("comments", [])],
            fetched_at=data.get("fetched_at", ""),
            notes=data.get("notes", ""),
        ))
    return bundles


def write_voc_dump(client_slug: str, platform: str) -> Path | None:
    """Flatten every cached bundle for one platform into a voc-miner JSON file.

    voc_miner.load_reviews_from_file expects a list[dict] with `body` (or
    `text`) plus optional `rating`. We emit:
        [{"rating": "N/A", "body": "<comment text>", "source": "<context>"}, ...]

    The `source` field is a human-readable breadcrumb — competitor name + post
    snippet — so the LLM can attribute pain-points back when extracting.

    Returns the path written, or None if no bundles exist for this platform.
    """
    bundles = load_cached_bundles(client_slug, platform)
    if not bundles:
        return None

    voc_dir = CLIENTS_DIR / client_slug / "voc"
    voc_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict] = []
    for bundle in bundles:
        source_label = (
            f"{platform}:{bundle.competitor_name or bundle.competitor_slug}"
            + (f" — {bundle.post_caption[:80]}" if bundle.post_caption else "")
        )
        for comment in bundle.comments:
            if not comment.text.strip():
                continue
            records.append({
                "rating": "N/A",
                "body": comment.text,
                "author": comment.author,
                "likes": comment.likes,
                "is_reply": comment.is_reply,
                "post_url": comment.post_url or bundle.post_url,
                "source": source_label,
            })

    # Sort by likes desc so high-resonance comments lead — improves the LLM's
    # signal-to-noise when voc_miner truncates to its 15K-char budget.
    records.sort(key=lambda r: r.get("likes", 0) or 0, reverse=True)

    out_path = voc_dir / f"{platform}-comments.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path
