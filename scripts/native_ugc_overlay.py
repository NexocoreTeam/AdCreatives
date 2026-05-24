"""Thin wrapper around `generators.ugc_overlay` — kept for backwards
compatibility with the original one-shot script invocation pattern.

The actual rendering primitives now live in `generators/ugc_overlay.py`
(imported as a module by `adc ugc-ad` and by this script). Re-exports:

  - render_native_ugc_ad
  - LAYOUTS
  - BoxStyle
  - PillStyle
  - DEFAULT_UGC_STYLE
  - FONT_BOLD / FONT_EMOJI (legacy constants)

Usage:
    python scripts/native_ugc_overlay.py <base_image.png> <output.png> [layout]
"""

from __future__ import annotations

import sys
from pathlib import Path

from generators.ugc_overlay import (  # re-export for legacy importers
    DEFAULT_UGC_STYLE,
    LAYOUTS,
    BoxStyle,
    PillStyle,
    list_layouts,
    render_native_ugc_ad,
)

# Legacy module-level font constants — kept so any external caller still
# importing them keeps working. The module is the source of truth now.
FONT_BOLD = DEFAULT_UGC_STYLE.font_path
FONT_EMOJI = DEFAULT_UGC_STYLE.emoji_font_path


def main() -> int:
    if len(sys.argv) < 3 or len(sys.argv) > 4:
        print(
            "Usage: python scripts/native_ugc_overlay.py <base.png> <out.png> [layout_name]",
            file=sys.stderr,
        )
        print(f"Available layouts: {list_layouts()}", file=sys.stderr)
        return 2
    base = Path(sys.argv[1])
    out = Path(sys.argv[2])
    layout_name = sys.argv[3] if len(sys.argv) == 4 else "social-mirror"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_native_ugc_ad(base, out, layout=layout_name)
    size_kb = out.stat().st_size / 1024
    print(f"Wrote {out} ({size_kb:.1f} KB) — layout: {layout_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
