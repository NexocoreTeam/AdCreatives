"""competitors.yaml scaffolding + enrichment.

Research depth is a direct function of competitors.yaml quality — on the
Zoka set, brand handles yielded 16 comments where search queries yielded
268. This module makes the high-yield fields exist by default:

- scaffold_competitors: create a full template file from competitor names
- enrich_competitors: add missing *_search_queries to an existing file
  WITHOUT touching anything the operator hand-wrote (ruamel round-trip,
  comments preserved)

Search-query templates are deliberately boring — "<competitor> review",
"<competitor> vs <brand>" — because that is exactly what worked live.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

from strategy.exa_queries import slugify

CLIENTS_DIR = Path("clients")


def default_youtube_queries(competitor_name: str, brand_name: str) -> list[str]:
    queries = [f"{competitor_name} review"]
    if brand_name and brand_name.lower() != competitor_name.lower():
        queries.append(f"{competitor_name} vs {brand_name}")
    return queries


def default_tiktok_queries(competitor_name: str) -> list[str]:
    return [f"{competitor_name} review"]


def _yaml() -> YAML:
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml


def scaffold_competitors(
    client_slug: str,
    brand_name: str,
    names: list[str],
    urls: dict[str, str] | None = None,
) -> Path:
    """Create clients/<slug>/competitors.yaml from competitor names.

    Refuses to overwrite an existing file — use enrich_competitors for that.
    """
    path = CLIENTS_DIR / client_slug / "competitors.yaml"
    if path.exists():
        raise FileExistsError(
            f"{path} already exists — use enrich_competitors (adc "
            f"scaffold-competitors enriches in place when the file is present)."
        )

    urls = urls or {}
    competitors = []
    for name in names:
        name = name.strip()
        if not name:
            continue
        competitors.append({
            "name": name,
            "slug": slugify(name),
            "url": urls.get(name, ""),
            "type": "direct",
            "priority": "tier1",
            "notes": "",
            "amazon_urls": [],
            "youtube_search_queries": default_youtube_queries(name, brand_name),
            "tiktok_search_queries": default_tiktok_queries(name),
        })

    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    buffer.write(
        "# Scaffolded by `adc scaffold-competitors` — review before running research:\n"
        "#   - fill url per competitor (homepage)\n"
        "#   - adjust type (direct|adjacent|switch-from) and priority (tier1-3)\n"
        "#   - add amazon_urls ONLY if the exact product is genuinely sold on Amazon\n"
        "#   - search queries beat brand handles for VOC; tune them per competitor\n"
    )
    _yaml().dump({"competitors": competitors}, buffer)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return path


def enrich_competitors(
    client_slug: str,
    brand_name: str,
    apply: bool = False,
) -> list[str]:
    """Fill missing *_search_queries in an existing competitors.yaml.

    Returns human-readable change lines. Only ADDS missing fields — never
    rewrites values, handles, notes, or comments the operator set. With
    apply=False this is a dry run.
    """
    path = CLIENTS_DIR / client_slug / "competitors.yaml"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — scaffold it first.")

    yaml = _yaml()
    data = yaml.load(path.read_text(encoding="utf-8")) or {}
    competitors = data.get("competitors") or []

    changes: list[str] = []
    for comp in competitors:
        name = str(comp.get("name", "") or "")
        if not name:
            continue
        if not comp.get("youtube_search_queries"):
            comp["youtube_search_queries"] = default_youtube_queries(name, brand_name)
            changes.append(
                f"{name}: + youtube_search_queries {comp['youtube_search_queries']}"
            )
        if not comp.get("tiktok_search_queries"):
            comp["tiktok_search_queries"] = default_tiktok_queries(name)
            changes.append(
                f"{name}: + tiktok_search_queries {comp['tiktok_search_queries']}"
            )

    if changes and apply:
        buffer = io.StringIO()
        yaml.dump(data, buffer)
        path.write_text(buffer.getvalue(), encoding="utf-8")
    return changes
