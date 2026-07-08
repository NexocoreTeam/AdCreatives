"""Ad Reference Library reporting + bookkeeping.

Status counts, the needs-strategist queue (so escalations get closed, not
forgotten), and the coverage gap map. Gaps are reported as awareness_stage ×
mechanic (5 × ~9 = a readable grid a strategist can act on) — NOT format ×
mechanic, which at ~50 formats is 400+ cells of noise at library scale.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from strategy.ad_card import LIBRARY_ROOT, load_all_cards
from strategy.taxonomy import AWARENESS_STAGES, Taxonomy


def library_status(tax: Taxonomy, root: Path | None = None) -> dict[str, Any]:
    """Everything `adc library status` (and OpenClaw's "library status"
    reply) needs, as plain data."""
    cards = load_all_cards(root)
    by_status: dict[str, int] = {}
    needs_strategist: list[dict[str, str]] = []
    grid: dict[str, dict[str, int]] = {
        stage: {m: 0 for m in tax.mechanic_names()} for stage in AWARENESS_STAGES
    }

    for card in cards:
        analysis = card.get("analysis") or {}
        status = analysis.get("status", "?")
        by_status[status] = by_status.get(status, 0) + 1
        if status == "needs-strategist":
            needs_strategist.append({
                "card_id": card.get("card_id", "?"),
                "brand": card.get("brand", "?"),
                "date_added": str(card.get("date_added", "")),
                "low_confidence": ", ".join(
                    f for f, lvl in (analysis.get("field_confidence") or {}).items()
                    if lvl == "low"),
            })
        stage = analysis.get("awareness_stage")
        mech = analysis.get("mechanic")
        if stage in grid and mech in grid[stage]:
            grid[stage][mech] += 1

    empty_stages = [s for s, row in grid.items() if not any(row.values())]
    empty_mechanics = [
        m for m in tax.mechanic_names()
        if not any(grid[s][m] for s in grid)
    ]
    return {
        "total": len(cards),
        "by_status": by_status,
        "needs_strategist": needs_strategist,
        "grid": grid,
        "empty_stages": empty_stages,
        "empty_mechanics": empty_mechanics,
    }


def log_library_cost(command: str, cost: float, note: str = "",
                     root: Path | None = None) -> None:
    """Append-only cost line for library work. Same JSONL shape as the
    per-client cost logs, but the library isn't client-scoped so it keeps
    its own file (gitignored, like the client ones)."""
    lib = (root / LIBRARY_ROOT) if root else LIBRARY_ROOT
    lib.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "cost": round(cost, 4),
        "note": note,
    }
    with (lib / ".cost-log.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
