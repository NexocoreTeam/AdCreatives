"""File-backed cache for Drive analyses, keyed by Drive's modifiedTime.

Layout: `clients/<slug>/.drive_cache/<sanitized_name>.yaml` per file analyzed.
Each entry stores the analyzer's tag, the source file's cache_key (id + mtime),
and the analysis payload. `is_stale` returns True when the Drive file's
modifiedTime changes — picking up edits, re-uploads, or replacements automatically.

Path-independent: regenerating the cache directory is safe at any time. The
gitignore excludes the entire `.drive_cache/` tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from strategy.drive_client import DriveFile

CLIENTS_DIR = Path("clients")
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe_filename(file_id: str, name: str) -> str:
    """Build a filesystem-safe cache filename from a Drive file's name + id.

    Sanitizes BOTH the human-readable name and the file_id tail — real Drive IDs
    only contain alphanumerics + dash + underscore, but defensive sanitization
    means a malformed id can never escape the cache directory via `../`.
    """
    stem = _SAFE_NAME.sub("_", Path(name).stem)[:80]
    id_suffix = _SAFE_NAME.sub("_", file_id[-12:])
    return f"{stem}__{id_suffix}.yaml"


@dataclass
class CacheEntry:
    """One cached analysis. Compared against a fresh DriveFile to detect staleness."""

    file_id: str
    cache_key: str  # the source DriveFile.cache_key at the time of caching
    analyzer: str
    payload: dict[str, Any]

    def is_stale_for(self, file: DriveFile) -> bool:
        """True if the source file's content (modifiedTime) has changed since caching."""
        return self.cache_key != file.cache_key


class DriveCache:
    """Per-client cache directory for Drive analyses.

    Cache hits avoid repeated vision-LLM calls for unchanged Drive files.
    Setting `force=True` on a higher-level command bypasses reads but still writes.
    """

    def __init__(self, client_slug: str):
        self.client_slug = client_slug
        self.dir = CLIENTS_DIR / client_slug / ".drive_cache"
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, file: DriveFile) -> Path:
        return self.dir / _safe_filename(file.id, file.name)

    def get(self, file: DriveFile) -> CacheEntry | None:
        """Return the cached entry if present and still fresh; None otherwise."""
        path = self._path_for(file)
        if not path.exists():
            return None
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            return None
        entry = CacheEntry(
            file_id=data.get("file_id", ""),
            cache_key=data.get("cache_key", ""),
            analyzer=data.get("analyzer", ""),
            payload=data.get("payload") or {},
        )
        if entry.is_stale_for(file):
            return None
        return entry

    def put(self, file: DriveFile, analyzer: str, payload: dict[str, Any]) -> Path:
        """Write an analysis to the cache. Overwrites any prior entry for this file."""
        path = self._path_for(file)
        path.write_text(
            yaml.safe_dump(
                {
                    "file_id": file.id,
                    "name": file.name,
                    "mime_type": file.mime_type,
                    "cache_key": file.cache_key,
                    "analyzer": analyzer,
                    "payload": payload,
                },
                sort_keys=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        return path

    def invalidate(self, file: DriveFile) -> None:
        """Remove the cache entry for a file. Safe if no entry exists."""
        path = self._path_for(file)
        if path.exists():
            path.unlink()
