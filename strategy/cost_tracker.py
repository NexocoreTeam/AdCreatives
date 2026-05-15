"""Append-only cost log per client.

Each paid CLI command (anything that calls an LLM or external paid API) calls
`log_cost(client, command, cost)` after success. The log lives at
clients/<slug>/.cost-log.jsonl — one JSON object per line, append-only, easy to
read with `read_costs()` or open in any editor.

Cost estimates here are deliberately rounded — they're forecast costs, not
exact billing. Use them for budget awareness and "what's expensive" intuition,
not for invoicing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

CLIENTS_DIR = Path("clients")
LOG_FILENAME = ".cost-log.jsonl"

# Forecast cost rates — keep these in sync with what the CLI tells users.
# Update when underlying provider pricing changes.
COST_RATES: dict[str, float] = {
    # Strategy stages (per run)
    "adc research": 1.50,
    "adc product-deep-dive": 0.50,
    "adc personas": 0.50,
    "adc offers": 0.30,
    "adc strategy-matrix": 0.50,
    "adc mine-voc": 0.30,
    "adc profile-psychology": 0.30,    # per avatar profiled

    # Brief & ad production
    "adc brief": 0.50,                  # one batch of 6 briefs
    "adc prompts": 0.05,                # per brief picked
    "adc generate": 0.08,               # per image (prompt + fal.ai)
    "adc remix": 0.10,                  # per variation (vision + angle + prompt)
    "adc remix-images": 0.08,           # per image (fal.ai)
    "adc remix-refine": 0.10,           # per refined image (Claude rewrite + fal.ai)

    # Competitive research
    "adc research-web": 0.50,
    "adc research-competitors": 2.00,   # one full pull
    "adc research-amazon": 0.05,        # per actor call (Apify free tier)
    "adc analyze-gaps": 1.50,           # full pass; --synthesis-only is ~0.30
    "adc analyze-gaps-synthesis": 0.30,
}


@dataclass
class CostEntry:
    timestamp: str
    command: str
    cost: float
    note: str = ""

    def to_json(self) -> dict:
        return asdict(self)


def _log_path(client_slug: str) -> Path:
    return CLIENTS_DIR / client_slug / LOG_FILENAME


def log_cost(
    client_slug: str,
    command: str,
    cost: Optional[float] = None,
    note: str = "",
    multiplier: float = 1.0,
) -> CostEntry:
    """Append a cost entry to the client's log.

    If `cost` is None, look up the default rate for `command` in COST_RATES
    and multiply by `multiplier` (useful when the command processed N items).
    Silently no-ops if the client folder doesn't exist (e.g. during init).
    """
    if cost is None:
        rate = COST_RATES.get(command, 0.0)
        cost = round(rate * multiplier, 4)

    entry = CostEntry(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        command=command,
        cost=cost,
        note=note,
    )

    client_dir = CLIENTS_DIR / client_slug
    if not client_dir.exists():
        # No client folder yet — caller probably just initialized. Skip silently.
        return entry

    path = _log_path(client_slug)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_json()) + "\n")
    return entry


def read_costs(client_slug: str) -> list[CostEntry]:
    """Read all cost entries for a client. Returns empty list if no log yet."""
    path = _log_path(client_slug)
    if not path.exists():
        return []
    entries: list[CostEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            entries.append(CostEntry(**data))
        except Exception:
            continue
    return entries


def total_for_month(
    client_slug: str,
    year: int | None = None,
    month: int | None = None,
) -> float:
    """Sum the cost entries for a single calendar month. Defaults to current."""
    now = datetime.now()
    year = year or now.year
    month = month or now.month
    total = 0.0
    for e in read_costs(client_slug):
        try:
            ts = datetime.fromisoformat(e.timestamp)
        except Exception:
            continue
        if ts.year == year and ts.month == month:
            total += e.cost
    return round(total, 2)


def total_all_time(client_slug: str) -> float:
    """Sum every cost entry for the client."""
    return round(sum(e.cost for e in read_costs(client_slug)), 2)


def recent_entries(client_slug: str, limit: int = 10) -> list[CostEntry]:
    """Return the most recent N cost entries (newest first)."""
    entries = read_costs(client_slug)
    return list(reversed(entries))[:limit]
