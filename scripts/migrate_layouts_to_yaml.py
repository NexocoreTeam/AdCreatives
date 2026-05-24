"""One-shot migration: dump generators.ugc_overlay.LAYOUTS into per-concept
YAML files under clients/secondkind-bold/ai-ads/phase-1/<concept>/.

Each output file is `text-layout.yaml` and validates as
`list[models.brief.TextOverlay]`. Operators can re-run this any time to
re-seed the on-disk layouts from the Python registry.

The mapping (layout name → concept folder):
  social-mirror      -> social-mirror
  native-reel-woman  -> native-reel
  native-reel-man    -> native-reel
  native-pain-010    -> pain-010

Both native-reel-man and native-reel-woman target the same folder
(native-reel/) so the filenames are suffixed: text-layout-woman.yaml,
text-layout-man.yaml.

Usage:
    python scripts/migrate_layouts_to_yaml.py [--client <slug>]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from generators.ugc_overlay import LAYOUTS, text_overlays_from_layout
from models.brief import TextOverlay

# Maps registry layout names to (subfolder, output filename) tuples relative
# to the client's `ai-ads/phase-1/` directory.
LAYOUT_TARGETS: dict[str, tuple[str, str]] = {
    "social-mirror":    ("social-mirror", "text-layout.yaml"),
    "native-reel-woman": ("native-reel",  "text-layout-woman.yaml"),
    "native-reel-man":   ("native-reel",  "text-layout-man.yaml"),
    "native-pain-010":   ("pain-010",     "text-layout.yaml"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--client",
        default="secondkind-bold",
        help="Client slug (default: secondkind-bold)",
    )
    parser.add_argument(
        "--phase",
        default="phase-1",
        help="Phase subfolder under ai-ads/ (default: phase-1)",
    )
    args = parser.parse_args()

    base = Path("clients") / args.client / "ai-ads" / args.phase
    if not base.exists():
        print(f"Target dir not found: {base}")
        return 1

    written = 0
    skipped: list[str] = []
    for layout_name, (subfolder, out_name) in LAYOUT_TARGETS.items():
        if layout_name not in LAYOUTS:
            skipped.append(f"{layout_name} (not in registry)")
            continue

        target_dir = base / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        out_path = target_dir / out_name

        overlays = [TextOverlay(**entry) for entry in text_overlays_from_layout(layout_name)]
        payload = [o.model_dump() for o in overlays]
        out_path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        print(f"Wrote {out_path}")
        written += 1

    print(f"\nDone. {written} layout file(s) written.")
    for s in skipped:
        print(f"  skipped: {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
