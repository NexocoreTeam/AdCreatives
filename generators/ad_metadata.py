"""Sidecar metadata writer for generated ad files.

Every generated ad gets a YAML sidecar at `<ad_path>.meta.yaml` recording
how it was made, what it was iterated from, and whether it's the current
"ship" version. This makes the ai-ads/ folder self-documenting — an
operator can trace any image back to its prompt, references, and parent.

Schema (all optional except `version` and `timestamp`):

  version:         str   — semantic version or operator-chosen tag
                           ("v1", "v2-amber", "social-mirror-final")
  timestamp:       str   — ISO-8601 generation time
  engine:          str   — "hf-web" | "pil-overlay" | "hybrid" | "soul" | etc.
  cost_usd:        float — best-effort cost in USD
  prompt_or_layout: str  — prompt for AI engines, or layout name for PIL
  references_used: list[str] — reference image paths fed to the model
  parent_version:  str   — what this was iterated from (the previous filename)
  ship_status:     str   — "ship" | "alt" | "superseded"
  notes:           str   — operator notes
  brief_id:        str   — owning brief if any

Set-ship pointer:
  Per concept folder, an operator can mark one file as "ship" via
  `set_ship_version`. The helper writes a `current.png.meta.yaml` sidecar
  that points at the chosen filename and (best effort on Windows) creates
  a `current.png` symlink — falls back to a plain copy if symlinks aren't
  available.
"""

from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def metadata_path_for(ad_path: Path) -> Path:
    """Return the sidecar metadata path for an ad file."""
    return ad_path.with_suffix(ad_path.suffix + ".meta.yaml")


def write_ad_metadata(
    ad_path: Path | str,
    *,
    version: str | None = None,
    engine: str = "",
    cost_usd: float | None = None,
    prompt_or_layout: str = "",
    references_used: list[str] | None = None,
    parent_version: str = "",
    ship_status: str = "alt",
    notes: str = "",
    brief_id: str = "",
    extra: dict[str, Any] | None = None,
) -> Path:
    """Write (or update) the sidecar YAML for an ad file.

    Existing metadata fields are preserved unless explicitly overridden.
    Returns the metadata file path.

    `version` defaults to the ad file's stem when omitted.
    `timestamp` is always set fresh on each call.
    `ship_status` defaults to "alt" — promote with set_ship_version().
    """
    ad_path = Path(ad_path)
    meta_path = metadata_path_for(ad_path)

    existing: dict[str, Any] = {}
    if meta_path.exists():
        try:
            existing = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            existing = {}

    data: dict[str, Any] = dict(existing)
    data["version"] = version or existing.get("version") or ad_path.stem
    data["timestamp"] = datetime.now().isoformat(timespec="seconds")
    if engine:
        data["engine"] = engine
    if cost_usd is not None:
        data["cost_usd"] = round(float(cost_usd), 4)
    if prompt_or_layout:
        data["prompt_or_layout"] = prompt_or_layout
    if references_used is not None:
        data["references_used"] = [str(p) for p in references_used]
    if parent_version:
        data["parent_version"] = parent_version
    if ship_status:
        data["ship_status"] = ship_status
    if notes:
        data["notes"] = notes
    if brief_id:
        data["brief_id"] = brief_id
    if extra:
        for k, v in extra.items():
            data[k] = v

    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return meta_path


def set_ship_version(concept_dir: Path | str, version_filename: str) -> Path:
    """Mark a specific file in `concept_dir` as the current "ship" version.

    Effects:
      - Updates that file's metadata sidecar: ship_status='ship'
      - Demotes any other file in the folder previously marked 'ship'
        to 'superseded'
      - Creates / refreshes `current.png` in the folder. Tries a symlink
        first (Windows requires Developer Mode); falls back to a copy.
      - Writes `current.png.meta.yaml` pointing at the chosen version.

    Returns the path to the `current.png`.
    """
    concept_dir = Path(concept_dir)
    if not concept_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {concept_dir}")

    target = concept_dir / version_filename
    if not target.exists():
        raise FileNotFoundError(
            f"Version '{version_filename}' not found in {concept_dir}"
        )

    # Demote previous ship-marked files in the same folder.
    for sibling in concept_dir.glob("*.meta.yaml"):
        # Don't touch the current.png sidecar — we'll rewrite that below.
        if sibling.name.startswith("current."):
            continue
        try:
            data = yaml.safe_load(sibling.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        if data.get("ship_status") == "ship" and not sibling.name.startswith(target.name):
            data["ship_status"] = "superseded"
            sibling.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    # Mark target as ship.
    write_ad_metadata(target, ship_status="ship")

    # Build / refresh current.png.
    current = concept_dir / f"current{target.suffix}"
    if current.exists() or current.is_symlink():
        try:
            current.unlink()
        except OSError:
            pass

    # Symlink first (cheaper, transparent in tools). Fall back to copy.
    try:
        os.symlink(target.name, current)
    except (OSError, NotImplementedError):
        shutil.copy2(target, current)

    # Sidecar for the current.png pointing at the chosen version.
    write_ad_metadata(
        current,
        version=target.stem,
        ship_status="ship",
        notes=f"Pointer to ship version: {target.name}",
        extra={"points_to": target.name},
    )

    return current
