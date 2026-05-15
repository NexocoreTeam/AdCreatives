"""Backfill trending_format_recommendations onto an existing briefs.yaml.

Usage:
    python scripts/backfill_trending.py <path-to-briefs.yaml>

Loads each brief, hands it to the trending recommender, and writes the
result back in-place. Idempotent — re-running overwrites existing recs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# Make repo root importable.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# dotenv first so ANTHROPIC_API_KEY is set before strategy.llm imports.
try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except Exception:
    pass

from models.brief import CreativeBrief
from strategy.trending import recommend_trending_formats


def backfill(briefs_path: Path) -> None:
    raw = yaml.safe_load(briefs_path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        print(f"Expected a list at {briefs_path}, got {type(raw).__name__}.")
        return

    print(f"Loaded {len(raw)} briefs from {briefs_path}")

    for i, b in enumerate(raw, 1):
        brief_id = b.get("brief_id", f"?{i}")
        try:
            brief_obj = CreativeBrief(**b)
        except Exception as e:
            print(f"  [{i}/{len(raw)}] {brief_id}: skip (parse error: {e})")
            continue

        try:
            recs = recommend_trending_formats(brief_obj)
        except Exception as e:
            print(f"  [{i}/{len(raw)}] {brief_id}: skip (rec error: {e})")
            continue

        b["trending_format_recommendations"] = recs
        n = len(recs)
        names = ", ".join(r.get("name", "?") for r in recs) if recs else "(none)"
        print(f"  [{i}/{len(raw)}] {brief_id}: {n} recs - {names}")

    briefs_path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote updated briefs back to {briefs_path}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python scripts/backfill_trending.py <briefs.yaml>")
        sys.exit(2)
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(2)
    backfill(path)


if __name__ == "__main__":
    main()
