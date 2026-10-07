"""Capture effective renderer inputs, rather than just a mutable layout name."""

from pathlib import Path

import click

from generators.ad_metadata import write_ad_metadata
from strategy.creative_recipes import capture_recipe, load_recipe


def capture_render(
    *, client: str, product: str, base: Path, outputs: list[Path], engine: str,
    settings: dict, brief: dict | None, extra_assets: dict[str, Path] | None = None,
    parent: str | None = None, changes: tuple[str, ...] = (),
) -> Path | None:
    if not client or not product:
        click.echo("Recipe not captured: provide client/product in a brief or CLI flags.")
        return None
    change_map = {}
    for entry in changes:
        key, sep, value = entry.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise click.ClickException("--change must be component=value")
        change_map[key.strip()] = value.strip()
    assets = {"base": base, **(extra_assets or {})}
    base_meta = base.with_suffix(base.suffix + ".meta.yaml")
    if base_meta.exists():
        assets["base_metadata"] = base_meta
    input_roles = list(assets)
    output_roles = [f"final_{index}" for index in range(len(outputs))]
    assets.update(dict(zip(output_roles, outputs)))
    try:
        path = capture_recipe(
            clients_dir=Path("clients"), client=client, product=product, assets=assets,
            steps=[{"tool": engine, "inputs": input_roles, "outputs": output_roles,
                    "settings": settings}], brief=brief,
            parent=Path(parent) if parent else None, changes=change_map,
            limitations=["Final render captured. Upstream photo generation/manual edits are "
                         "not a complete recipe unless registered separately.",
                         "Fonts are environment dependencies; archive licensed fonts separately."],
        )
        recipe = load_recipe(path)
        for output in outputs:
            write_ad_metadata(output, extra={"recipe_version_id": recipe["version_id"],
                                            "recipe_path": str(path.resolve())})
    except (ValueError, OSError) as exc:
        raise click.ClickException(f"Render exists but recipe capture failed: {exc}") from exc
    click.echo(f"Recipe saved: {path}")
    return path
