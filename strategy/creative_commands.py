"""Local creative recipe and performance-handoff commands."""

from pathlib import Path

import click

from strategy.creative_handoff import import_winners
from strategy.creative_recipes import load_recipe, register_manifest


@click.group("creative")
def creative() -> None:
    """Save reusable recipes and queue performance-led variations (local/free)."""


@creative.command("record")
@click.option("--manifest", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--clients-dir", type=click.Path(path_type=Path), default="clients")
def record(manifest: Path, clients_dir: Path) -> None:
    """Snapshot a step manifest and all its assets into a new version."""
    try:
        click.echo(register_manifest(manifest, clients_dir))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        raise click.ClickException(str(exc)) from exc


@creative.command("inspect")
@click.option("--recipe", type=click.Path(exists=True, path_type=Path), required=True)
def inspect(recipe: Path) -> None:
    """Verify source hashes and print the saved recipe."""
    import json
    try:
        click.echo(json.dumps(load_recipe(recipe), indent=2))
    except (ValueError, OSError) as exc:
        raise click.ClickException(str(exc)) from exc


@creative.command("import-winners")
@click.option("--packet", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--client", required=True)
@click.option("--clients-dir", type=click.Path(path_type=Path), default="clients")
def winners(packet: Path, client: str, clients_dir: Path) -> None:
    """Create a deduplicated review queue; does not spend or run production."""
    try:
        click.echo(import_winners(packet, client, clients_dir))
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise click.ClickException(str(exc)) from exc
