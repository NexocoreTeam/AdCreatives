"""Capture immutable recipe bundles with private copies of their source assets."""

from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import PIL

from models.creative_recipe import CreativeRecipe


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def validate_slug(value: str) -> str:
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
        raise ValueError("Invalid client slug")
    return value


def load_recipe(path: Path) -> dict:
    """Validate a bundle, including file contents, before reuse or handoff."""
    data = CreativeRecipe.model_validate_json(path.read_text(encoding="utf-8"))
    root = path.parent.resolve()
    for asset in data.assets.values():
        target = (root / asset.path).resolve()
        if not target.is_relative_to(root):
            raise ValueError("Recipe asset escapes bundle")
        if file_hash(target) != asset.sha256:
            raise ValueError(f"Asset hash mismatch: {asset.path}")
    return data.model_dump(mode="json")


def _runtime() -> dict[str, str]:
    repo = Path(__file__).resolve().parents[1]
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo,
                              capture_output=True, text=True, check=False)
    return {"python": platform.python_version(), "pillow": PIL.__version__,
            "git_commit": revision.stdout.strip() if revision.returncode == 0 else "unknown",
            "native_renderer_sha256": file_hash(repo / "generators/native_ui.py"),
            "ugc_renderer_sha256": file_hash(repo / "generators/ugc_overlay.py")}


def capture_recipe(
    *, clients_dir: Path, client: str, product: str, assets: dict[str, Path],
    steps: list[dict], brief: dict | None = None, parent: Path | None = None,
    changes: dict[str, str] | None = None, provenance: str = "recorded",
    limitations: list[str] | None = None,
) -> Path:
    """Snapshot one version; never overwrite a prior recipe or its assets."""
    validate_slug(client)
    if brief and brief.get("client") not in (None, "", client):
        raise ValueError("Brief belongs to another client")
    ancestor = load_recipe(parent) if parent else None
    if ancestor and ancestor["client"] != client:
        raise ValueError("Parent recipe belongs to another client")
    version_id = str(uuid4())
    records = {}
    for role, source in assets.items():
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", role):
            raise ValueError(f"Invalid asset role: {role}")
        source = Path(source).resolve()
        if not source.is_file():
            raise FileNotFoundError(source)
        records[role] = {"path": f"assets/{role}{source.suffix}",
                         "source_path": str(source), "sha256": file_hash(source)}
    data = CreativeRecipe(
        client=client, product=product,
        concept_id=ancestor["concept_id"] if ancestor else str(uuid4()),
        version_id=version_id, parent_version_id=ancestor["version_id"] if ancestor else None,
        created_at=datetime.now(timezone.utc).isoformat(), provenance=provenance,
        limitations=limitations or [], changes=changes or {}, brief=brief,
        runtime=_runtime(), assets=records, steps=steps,
    )
    folder = clients_dir / client / "creative-recipes" / version_id
    folder.mkdir(parents=True, exist_ok=False)
    (folder / "assets").mkdir()
    for record in records.values():
        target = folder / record["path"]
        shutil.copyfile(record["source_path"], target)
        if file_hash(target) != record["sha256"]:
            raise ValueError("Source changed during capture; incomplete bundle was not registered")
    path = folder / "recipe.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(data.model_dump_json(indent=2) + "\n")
    return path


def register_manifest(manifest_path: Path, clients_dir: Path) -> Path:
    """Register a human-supplied step manifest; relative paths use its directory."""
    spec = json.loads(manifest_path.read_text(encoding="utf-8"))
    assets = {role: manifest_path.parent / value for role, value in spec.pop("assets").items()}
    if spec.get("parent"):
        spec["parent"] = manifest_path.parent / spec["parent"]
    return capture_recipe(clients_dir=clients_dir, assets=assets, **spec)
