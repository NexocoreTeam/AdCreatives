"""Build a local, playable review from explicitly selected reference IDs."""

import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import click
import httpx

from strategy.ugc_references import render, write_json

MAX_BYTES = 40 * 1024 * 1024
MEDIA_HOSTS = {"api.apify.com", "r2.foreplay.co", "storage.googleapis.com"}


def download(url: str, path: Path) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in MEDIA_HOSTS:
        raise ValueError("Media host is not on the reviewed provider allowlist")
    partial = path.with_suffix(".part")
    count = 0
    try:
        with httpx.stream("GET", url, follow_redirects=False, timeout=60) as response:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected redirect or empty media response")
            with partial.open("wb") as handle:
                for chunk in response.iter_bytes():
                    count += len(chunk)
                    if count > MAX_BYTES:
                        raise ValueError("Media exceeds 40 MiB review limit")
                    handle.write(chunk)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)


@click.command()
@click.option("--output", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--selection", type=click.Path(path_type=Path, exists=True), required=True)
def cli(output: Path, selection: Path) -> None:
    """Download at most ten selected references; no generation or transcription spend."""
    choices = json.loads(selection.read_text(encoding="utf-8"))
    references = json.loads((output / "references.json").read_text(encoding="utf-8"))
    lookup = {r["id"]: r for r in references}
    ids = [c["id"] for c in choices]
    if not 1 <= len(choices) <= 10 or len(set(ids)) != len(ids):
        raise click.ClickException("Choose 1-10 unique reference IDs")
    if any(identity not in lookup for identity in ids):
        raise click.ClickException("Selection includes an unknown reference")
    media = output / "media"
    media.mkdir(exist_ok=True)
    chosen = []
    for choice in choices:
        item = {**lookup[choice["id"]], "review_reason": choice["reason"]}
        path = media / (hashlib.sha256(item["id"].encode()).hexdigest()[:20] + ".mp4")
        try:
            if not path.exists():
                urls = item.get("media_urls") or []
                if not urls:
                    raise ValueError("No downloadable media returned")
                download(urls[0], path)
            item["local_video"] = str(path.resolve())
            item["media_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception as exc:
            item["download_error"] = type(exc).__name__
        chosen.append(item)
        write_json(output / "shortlist.json", chosen)
    (output / "shortlist.html").write_text(render(chosen), encoding="utf-8")
    click.echo(
        f"{sum(bool(r.get('local_video')) for r in chosen)}/{len(chosen)} local previews ready"
    )


if __name__ == "__main__":
    cli()
