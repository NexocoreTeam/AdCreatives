"""Backfill trending_format_recommendations onto existing brief YAML files.

Handles three input shapes:

  1. A single YAML file containing a LIST of briefs (e.g. remix output
     `briefs.yaml`).
  2. A single YAML file containing ONE brief (e.g. the per-brief files
     under `clients/{slug}/briefs/*.yaml`).
  3. A client slug — walks `clients/{slug}/briefs/*.yaml` and runs the
     single-brief backfill on each file.

Usage:
    python scripts/backfill_trending.py <path-to-briefs.yaml>
    python scripts/backfill_trending.py --client <slug>

Idempotent — re-running overwrites existing recs in place.
"""

from __future__ import annotations

import argparse
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

CLIENTS_DIR = REPO_ROOT / "clients"


# ─── Per-brief rec attachment (in-memory) ───────────────────────────────────


def _attach_recs(brief_dict: dict, *, label: str) -> bool:
    """Add `trending_format_recommendations` to a brief dict in place.

    Returns True on success, False on parse/rec error.
    """
    brief_id = brief_dict.get("brief_id", "?")
    try:
        brief_obj = CreativeBrief(**brief_dict)
    except Exception as e:
        print(f"  {label} {brief_id}: skip (parse error: {e})")
        return False

    try:
        recs = recommend_trending_formats(brief_obj)
    except Exception as e:
        print(f"  {label} {brief_id}: skip (rec error: {e})")
        return False

    brief_dict["trending_format_recommendations"] = recs
    names = ", ".join(r.get("name", "?") for r in recs) if recs else "(none)"
    print(f"  {label} {brief_id}: {len(recs)} recs - {names}")
    return True


# ─── File-level handlers ────────────────────────────────────────────────────


def backfill_list_file(path: Path) -> None:
    """Backfill a single YAML file containing a LIST of briefs."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(raw, list):
        print(f"Expected a list at {path}, got {type(raw).__name__}.")
        return

    print(f"Loaded {len(raw)} briefs from {path}")
    for i, b in enumerate(raw, 1):
        _attach_recs(b, label=f"[{i}/{len(raw)}]")

    path.write_text(
        yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"Wrote updated briefs back to {path}")


def backfill_single_brief_file(path: Path, *, label: str = "") -> None:
    """Backfill a single YAML file containing ONE brief."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        print(f"Expected a dict at {path}, got {type(raw).__name__}.")
        return

    if _attach_recs(raw, label=label or path.name):
        path.write_text(
            yaml.safe_dump(raw, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )


def backfill_client_briefs(slug: str) -> None:
    """Walk `clients/{slug}/briefs/*.yaml` and backfill each."""
    briefs_dir = CLIENTS_DIR / slug / "briefs"
    if not briefs_dir.exists():
        print(f"No briefs directory: {briefs_dir}")
        return

    files = sorted(briefs_dir.glob("*.yaml"))
    if not files:
        print(f"No brief YAMLs found in {briefs_dir}")
        return

    print(f"Backfilling {len(files)} briefs in {briefs_dir}")
    for i, f in enumerate(files, 1):
        backfill_single_brief_file(f, label=f"[{i}/{len(files)}]")
    print(f"Done. {len(files)} brief file(s) processed.")


# ─── Entrypoint ─────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a briefs.yaml (list-of-briefs) or a single brief file.",
    )
    parser.add_argument(
        "--client",
        help="Client slug. Walks clients/<slug>/briefs/*.yaml and backfills each.",
    )
    args = parser.parse_args()

    if args.client:
        backfill_client_briefs(args.client)
        return

    if not args.path:
        parser.print_help()
        sys.exit(2)

    path = Path(args.path)
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(2)

    # Decide list-of-briefs vs single-brief by inspecting the YAML shape.
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        backfill_list_file(path)
    elif isinstance(raw, dict):
        backfill_single_brief_file(path)
    else:
        print(f"Unexpected YAML shape at {path}: {type(raw).__name__}")
        sys.exit(2)


if __name__ == "__main__":
    main()
