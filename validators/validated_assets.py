"""Source-asset known-issues registry.

Each client may have a `clients/<slug>/validated_assets.yaml` recording
known problems with specific source assets (typos on labels, wrong
copyright marks, low-res scans, etc.). Before any generation step
references one of these files, the CLI checks this registry and prints
a warning so the operator can decide whether to proceed.

Schema (YAML at `clients/<slug>/validated_assets.yaml`):

  known_issues:
    - file: "_refs/gut-balance-product.png"   # path relative to client root
      issue: "label reads 'Posthiotic' instead of 'Postbiotic'"
      severity: "warning"   # "warning" | "block" (currently not enforced)
      workaround: "fix at brand level — label print run"

`file` is matched as a *suffix* against the provided asset path so the
caller doesn't have to know whether the path is absolute, relative to
cwd, or relative to the client root.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AssetIssue:
    """One known issue with a source asset."""

    file: str
    issue: str
    severity: str = "warning"   # "warning" | "block"
    workaround: str = ""


def _path_for(client_slug: str) -> Path:
    return Path("clients") / client_slug / "validated_assets.yaml"


def load_issues(client_slug: str) -> list[AssetIssue]:
    """Return the list of recorded issues for a client. [] if no file."""
    path = _path_for(client_slug)
    if not path.exists():
        return []
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    entries = data.get("known_issues") or []
    out: list[AssetIssue] = []
    for entry in entries:
        if not isinstance(entry, dict) or not entry.get("file"):
            continue
        out.append(AssetIssue(
            file=str(entry["file"]),
            issue=str(entry.get("issue", "")),
            severity=str(entry.get("severity", "warning")),
            workaround=str(entry.get("workaround", "")),
        ))
    return out


def find_issues_for_paths(
    client_slug: str,
    asset_paths: list[Path | str],
) -> list[tuple[Path, AssetIssue]]:
    """For each asset path, return any recorded issues.

    Matching is suffix-based — an issue recorded as
    `_refs/gut-balance-product.png` matches any path ending in
    `_refs/gut-balance-product.png` (case-insensitive on Windows).
    """
    issues = load_issues(client_slug)
    if not issues:
        return []

    matches: list[tuple[Path, AssetIssue]] = []
    for raw in asset_paths:
        p = Path(raw)
        path_str = str(p).replace("\\", "/").lower()
        for iss in issues:
            needle = iss.file.replace("\\", "/").lower().lstrip("./")
            if path_str.endswith(needle):
                matches.append((p, iss))
    return matches
