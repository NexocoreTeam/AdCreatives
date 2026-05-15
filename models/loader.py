"""Load client, product, style, avatar, and result data from YAML files."""

from __future__ import annotations

import re
from pathlib import Path

import yaml


# Characters forbidden in Windows filenames + ones that produce unfriendly paths.
# Forward slash and backslash are particularly important — they create accidental
# subdirectories that don't exist and crash file writes.
_BRIEF_ID_BAD_CHARS = re.compile(r'[\\/:*?"<>|+,]')


def _sanitize_brief_id(brief_id: str) -> str:
    """Make a brief_id safe to use as a filename across Windows + Unix.

    Replaces filesystem-invalid characters with hyphens, collapses runs of
    hyphens, and strips leading/trailing punctuation. Idempotent.
    """
    safe = _BRIEF_ID_BAD_CHARS.sub("-", brief_id)
    safe = re.sub(r"-+", "-", safe)
    return safe.strip("-.")

from models.avatar import CustomerAvatar
from models.brand import Brand
from models.brief import CreativeBrief
from models.product import Product
from models.result import CreativeResult, WinningPatterns
from models.style import Style

CLIENTS_DIR = Path("clients")
STYLES_DIR = Path("styles")
RESULTS_DIR = Path("results")


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_brand(client_slug: str) -> Brand:
    path = CLIENTS_DIR / client_slug / "brand.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Brand file not found: {path}")
    return Brand(**_load_yaml(path))


def load_product(client_slug: str, product_slug: str) -> Product:
    path = CLIENTS_DIR / client_slug / "products" / f"{product_slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Product file not found: {path}")
    return Product(**_load_yaml(path))


def load_product_by_name(client_slug: str, product_name: str) -> Product:
    """Find a product by its display name (CreativeBrief stores name, not slug)."""
    products_dir = CLIENTS_DIR / client_slug / "products"
    if not products_dir.exists():
        raise FileNotFoundError(f"Products dir not found: {products_dir}")
    for path in products_dir.glob("*.yaml"):
        product = Product(**_load_yaml(path))
        if product.name == product_name:
            return product
    raise FileNotFoundError(
        f"No product with name '{product_name}' in {products_dir}"
    )


def load_avatar(client_slug: str) -> CustomerAvatar | None:
    path = CLIENTS_DIR / client_slug / "avatar.yaml"
    if not path.exists():
        return None
    return CustomerAvatar(**_load_yaml(path))


# Canonical role ordering for the per-client `avatars/` folder. Anything not
# in this list (e.g. a custom slug like "switcher.yaml") sorts after the
# known roles, alphabetically by filename.
_AVATAR_ROLE_ORDER = ("primary", "secondary", "tertiary", "quaternary", "quinary")


def load_all_avatars(client_slug: str) -> list[CustomerAvatar]:
    """Load every avatar in `clients/{slug}/avatars/`, ordered by role.

    Skips index/private files (anything beginning with `_`). If the
    directory doesn't exist or is empty, returns []. Callers can then
    fall back to the legacy `load_avatar()` (single `avatar.yaml`) if
    they need to support older client folders.
    """
    avatars_dir = CLIENTS_DIR / client_slug / "avatars"
    if not avatars_dir.exists():
        return []

    paths = [
        p for p in avatars_dir.glob("*.yaml")
        if not p.name.startswith("_")
    ]
    if not paths:
        return []

    def _sort_key(p: Path) -> tuple[int, str]:
        stem = p.stem.lower()
        if stem in _AVATAR_ROLE_ORDER:
            return (_AVATAR_ROLE_ORDER.index(stem), stem)
        return (len(_AVATAR_ROLE_ORDER), stem)

    paths.sort(key=_sort_key)
    return [CustomerAvatar(**_load_yaml(p)) for p in paths]


def save_avatar(client_slug: str, avatar: CustomerAvatar, backup: bool = True) -> Path:
    """Save an avatar to disk. Backs up the existing file to avatar.yaml.bak by default."""
    import shutil

    path = CLIENTS_DIR / client_slug / "avatar.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)

    if backup and path.exists():
        shutil.copy2(path, path.with_suffix(".yaml.bak"))

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            avatar.model_dump(mode="json"),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return path


def load_style(style_slug: str, category: str = "static") -> Style:
    path = STYLES_DIR / category / f"{style_slug}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Style file not found: {path}")
    return Style(**_load_yaml(path))


def list_clients() -> list[str]:
    return sorted(
        d.name
        for d in CLIENTS_DIR.iterdir()
        if d.is_dir() and d.name != "_template" and (d / "brand.yaml").exists()
    )


def list_products(client_slug: str) -> list[str]:
    products_dir = CLIENTS_DIR / client_slug / "products"
    if not products_dir.exists():
        return []
    return sorted(p.stem for p in products_dir.glob("*.yaml"))


def list_styles(category: str = "static") -> list[str]:
    style_dir = STYLES_DIR / category
    if not style_dir.exists():
        return []
    return sorted(p.stem for p in style_dir.glob("*.yaml"))


def load_performance_log(client_slug: str) -> list[CreativeResult]:
    path = RESULTS_DIR / client_slug / "performance_log.yaml"
    if not path.exists():
        return []
    data = _load_yaml(path)
    if not data or not isinstance(data, list):
        return []
    return [CreativeResult(**entry) for entry in data]


def save_performance_log(client_slug: str, results: list[CreativeResult]) -> None:
    dir_path = RESULTS_DIR / client_slug
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / "performance_log.yaml"
    data = [r.model_dump(mode="json", exclude_none=True) for r in results]
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def load_winning_patterns(client_slug: str) -> WinningPatterns | None:
    path = RESULTS_DIR / client_slug / "winning_patterns.yaml"
    if not path.exists():
        return None
    return WinningPatterns(**_load_yaml(path))


def save_winning_patterns(client_slug: str, patterns: WinningPatterns) -> None:
    dir_path = RESULTS_DIR / client_slug
    dir_path.mkdir(parents=True, exist_ok=True)
    path = dir_path / "winning_patterns.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            patterns.model_dump(mode="json", exclude_none=True),
            f,
            default_flow_style=False,
            sort_keys=False,
        )


def save_brief(client_slug: str, brief: CreativeBrief) -> Path:
    dir_path = CLIENTS_DIR / client_slug / "briefs"
    dir_path.mkdir(parents=True, exist_ok=True)
    # Sanitize the brief_id for the filename AND the persisted YAML field, so
    # the on-disk name and the in-file identifier stay in sync. The input brief
    # object is not mutated — we operate on the dumped dict.
    safe_id = _sanitize_brief_id(brief.brief_id)
    data = brief.model_dump(mode="json")
    data["brief_id"] = safe_id
    path = dir_path / f"{safe_id}.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            data,
            f,
            default_flow_style=False,
            sort_keys=False,
        )
    return path


def load_brief(client_slug: str, brief_id: str) -> CreativeBrief:
    # Defensive: sanitize incoming id the same way save_brief does, so callers
    # passing the raw LLM-generated id still resolve to the on-disk file.
    safe_id = _sanitize_brief_id(brief_id)
    path = CLIENTS_DIR / client_slug / "briefs" / f"{safe_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Brief not found: {path}")
    return CreativeBrief(**_load_yaml(path))


def load_all_briefs(client_slug: str) -> list[CreativeBrief]:
    """Load every brief on disk for a client, sorted by product then slot."""
    dir_path = CLIENTS_DIR / client_slug / "briefs"
    if not dir_path.exists():
        return []
    briefs = [CreativeBrief(**_load_yaml(p)) for p in sorted(dir_path.glob("*.yaml"))]
    briefs.sort(key=lambda b: (b.product, b.slot or 0, b.brief_id))
    return briefs
