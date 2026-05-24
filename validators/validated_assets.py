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
      auto_fix_prompt_addition: |              # optional
        IMPORTANT: change the label text on the product to read
        'Postbiotic' (not 'Posthiotic').

`file` is matched as a *suffix* against the provided asset path so the
caller doesn't have to know whether the path is absolute, relative to
cwd, or relative to the client root.

When `auto_fix_prompt_addition` is set, the `adc edit` / `adc ugc-ad`
commands will append it to the operator's prompt automatically — turning
a warning into self-healing behaviour for source-asset defects that can't
be corrected at the source (e.g. a product label print-run typo).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AssetIssue:
    """One known issue with a source asset.

    `auto_fix_prompt_addition` is text that will be automatically appended
    to any hf-web edit prompt that uses this asset. Used to self-heal
    known asset issues that can't be fixed at the source. E.g. for a
    product image with a label typo, this would be 'IMPORTANT: change the
    label text on the product to read X (not Y).' Empty string = no
    auto-fix; caller's prompt is sent unchanged.
    """

    file: str
    issue: str
    severity: str = "warning"   # "warning" | "block"
    workaround: str = ""
    auto_fix_prompt_addition: str = ""


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
            auto_fix_prompt_addition=str(
                entry.get("auto_fix_prompt_addition", "") or ""
            ).strip(),
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


def get_auto_fix_additions(
    asset_paths: list[Path | str],
    client_slug: str,
) -> list[str]:
    """Return all auto-fix prompt additions for the given asset paths.

    For every asset path that matches a known issue with a non-empty
    `auto_fix_prompt_addition` field, the addition is included in the
    return list. Duplicate strings are de-duped (so listing the same
    asset twice doesn't double-append the fix).

    Empty list if no client slug, no registry, or no matching assets.
    Order is preserved on first-seen.

    Used by `adc edit` and `adc ugc-ad` to self-heal known asset defects
    that can't be fixed at the source — see module docstring.
    """
    if not client_slug:
        return []
    matches = find_issues_for_paths(client_slug, asset_paths)
    out: list[str] = []
    seen: set[str] = set()
    for _, iss in matches:
        addition = iss.auto_fix_prompt_addition.strip()
        if not addition or addition in seen:
            continue
        seen.add(addition)
        out.append(addition)
    return out
