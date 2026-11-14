"""Bounded, resumable research intake: python -m strategy.ugc_reference_collect --help."""

import json
import os
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import click
import httpx
from apify_client import ApifyClient
from dotenv import load_dotenv

from strategy.foreplay_client import PUBLIC_API, _headers, fetch_ad_by_id, fetch_brand_ads
from strategy.ugc_references import merge, normalize, render, reserve, vtt_text, write_json

ACTOR = "clockworks/tiktok-scraper"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def client(env_file: Path) -> ApifyClient:
    load_dotenv(env_file, override=False)
    token = os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise click.ClickException("APIFY_API_TOKEN is not configured")
    return ApifyClient(token, max_retries=0)


@click.group()
def cli() -> None:
    """Collect public UGC references; paid calls require a recorded budget approval."""


@cli.command()
@click.option("--client-dir", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
def cached(client_dir: Path, output: Path) -> None:
    """Import existing TikTok comment-source metadata without network calls."""
    output.mkdir(parents=True, exist_ok=False)
    items = [
        normalize(read(p), "cached_tiktok", str(p.resolve()))
        for p in sorted((client_dir / "research" / "tiktok-comments").glob("*.json"))
    ]
    items = merge(items)
    write_json(output / "references.json", items)
    (output / "review.html").write_text(render(items), encoding="utf-8")
    click.echo(f"Imported {len(items)} cached references; no listening review implied.")


@cli.command("start-tiktok")
@click.option("--plan", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--output", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--env-file", type=click.Path(path_type=Path, exists=True), required=True)
def start_tiktok(plan: Path, output: Path, env_file: Path) -> None:
    """Submit once; reserve before the call so a timeout cannot cause a duplicate."""
    p = read(plan)
    cap = Decimal(str(p.get("apify_cap_usd", 0)))
    urls = p.get("post_urls", [])
    queries = p.get("search_queries", [])
    if not p.get("approval") or not cap.is_finite() or not 0 < cap <= 10:
        raise click.ClickException("Recorded approval and a finite cap of $0-$10 are required")
    if not urls and not queries:
        raise click.ClickException("Provide post_urls or search_queries")
    if len(urls) > 50 or len(queries) > 5:
        raise click.ClickException("Pilot is limited to 50 URLs / 5 queries")
    if any(not isinstance(u, str) or not u.startswith("https://www.tiktok.com/@") for u in urls):
        raise click.ClickException("Use canonical public TikTok post URLs")
    inputs = {
        "postURLs": urls,
        "searchQueries": queries,
        "resultsPerPage": 5,
        "scrapeRelatedVideos": False,
        "shouldDownloadVideos": True,
        "shouldDownloadCovers": False,
        "commentsPerPost": 0,
        "downloadSubtitlesOptions": "DOWNLOAD_AND_TRANSCRIBE_VIDEOS_WITHOUT_SUBTITLES",
    }
    api = client(env_file)
    journal = output / "apify-attempt.json"
    reserve(
        journal, {"approval": p["approval"], "cap_usd": str(cap), "actor": ACTOR, "input": inputs}
    )
    try:
        run = api.actor(ACTOR).start(
            run_input=inputs,
            max_total_charge_usd=cap,
            max_items=50,
            timeout_secs=600,
            restart_on_error=False,
        )
    except Exception as exc:
        raise click.ClickException(
            f"Submission uncertain ({type(exc).__name__}); inspect Apify runs. Do not submit again."
        ) from None
    write_json(journal, {**read(journal), "status": run["status"], "run_id": run["id"]})
    click.echo(f"Submitted run {run['id']}; use finish-tiktok to retrieve without resubmission.")


@cli.command("finish-tiktok")
@click.option("--output", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--env-file", type=click.Path(path_type=Path, exists=True), required=True)
def finish_tiktok(output: Path, env_file: Path) -> None:
    """Read a submitted run and preserve raw results. Never starts an actor."""
    journal = output / "apify-attempt.json"
    attempt = read(journal)
    if attempt.get("status") == "collected":
        click.echo("Already collected; unchanged.")
        return
    if not attempt.get("run_id"):
        raise click.ClickException(
            "Submission outcome unknown; reconcile in Apify before continuing"
        )
    api = client(env_file)
    run = api.run(attempt["run_id"]).get()
    if run["status"] not in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
        click.echo("Still running: " + run["status"])
        return
    raw = (
        list(api.dataset(run["defaultDatasetId"]).iterate_items())
        if run.get("defaultDatasetId")
        else []
    )
    write_json(output / "apify-raw.json", raw)
    normalized, errors = [], []
    for item in raw:
        try:
            normalized.append(normalize(item, "tiktok", attempt["run_id"]))
        except ValueError as exc:
            errors.append(str(exc))
    items = merge(read(output / "references.json") + normalized)
    write_json(output / "references.json", items)
    (output / "review.html").write_text(render(items), encoding="utf-8")
    write_json(
        journal,
        {
            **attempt,
            "status": "collected",
            "provider_status": run["status"],
            "usage_usd": run.get("usageTotalUsd"),
            "dataset_id": run.get("defaultDatasetId"),
            "returned_count": len(raw),
            "normalization_errors": errors,
        },
    )
    click.echo(
        f"Collected {len(raw)} records; provider status {run['status']}; "
        f"reported cost {run.get('usageTotalUsd')}. Audio review remains pending."
    )


@cli.command("foreplay")
@click.option("--plan", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--output", type=click.Path(path_type=Path, exists=True), required=True)
@click.option("--env-file", type=click.Path(path_type=Path, exists=True), required=True)
def foreplay(plan: Path, output: Path, env_file: Path) -> None:
    """Retrieve five video ads per domain and their transcripts (up to three domains)."""
    p = read(plan)
    domains = p.get("foreplay_domains", [])
    # Reserve one lookup plus five list and five detail credits per domain.
    required = len(domains) * 11
    if not p.get("approval") or not 1 <= len(domains) <= 3:
        raise click.ClickException("Approval and 1-3 domains required")
    if required > p.get("foreplay_credit_cap", 0):
        raise click.ClickException("Foreplay credit cap is too small")
    load_dotenv(env_file, override=False)
    journal = output / "foreplay-attempt.json"
    reserve(journal, {"approval": p["approval"], "reserved_credits": required})
    records, calls = [], []
    try:
        for domain in domains:
            response = httpx.get(
                PUBLIC_API + "/api/brand/getBrandsByDomain",
                headers=_headers(),
                params={"domain": domain},
                timeout=30,
            )
            response.raise_for_status()
            brands = response.json().get("data") or []
            calls.append({"kind": "brand_lookup", "domain": domain, "brands": brands})
            write_json(output / "foreplay-receipt.json", calls)
            if len(brands) != 1:
                continue
            ads, _ = fetch_brand_ads(brands[0]["id"], display_format=["video"], limit=5)
            calls.append({"kind": "list", "domain": domain, "returned": len(ads)})
            write_json(output / "foreplay-receipt.json", calls)
            for ad in ads[:5]:
                detailed = fetch_ad_by_id(ad.ad_id) if ad.ad_id else ad
                calls.append({"kind": "detail", "ad_id": ad.ad_id, "found": bool(detailed)})
                if detailed:
                    records.append(asdict(detailed))
                write_json(output / "foreplay-raw.json", records)
                write_json(output / "foreplay-receipt.json", calls)
    except Exception as exc:
        write_json(
            journal,
            {**read(journal), "status": "partial_or_uncertain", "error_type": type(exc).__name__},
        )
        raise click.ClickException(
            "Foreplay stopped; saved receipts must be reviewed before retry"
        ) from None
    items = merge(
        read(output / "references.json")
        + [normalize(r, "foreplay", str(output / "foreplay-raw.json")) for r in records]
    )
    write_json(output / "references.json", items)
    (output / "review.html").write_text(render(items), encoding="utf-8")
    write_json(
        journal,
        {
            **read(journal),
            "status": "collected",
            "records": len(records),
            "actual_debit": "Not independently returned by provider",
        },
    )
    click.echo(f"Collected {len(records)} Foreplay video references")


@cli.command("captions")
@click.option("--output", type=click.Path(path_type=Path, exists=True), required=True)
def captions(output: Path) -> None:
    """Read English VTT files already collected by Apify; no actor or AI calls."""
    items = read(output / "references.json")
    lookup = {item["id"]: item for item in items}
    folder = output / "captions"
    folder.mkdir(exist_ok=True)
    errors = []
    for raw in read(output / "apify-raw.json"):
        identity = "tiktok:" + str(raw.get("id", ""))
        if identity not in lookup:
            continue
        metadata = raw.get("videoMeta") or {}
        links = metadata.get("subtitleLinks") or []
        link = next((s for s in links if s.get("language", "").startswith(("en", "eng"))), None)
        transcription = metadata.get("transcriptionLink")
        is_transcription = not link and isinstance(transcription, str) and bool(transcription)
        if is_transcription:
            link = {
                "downloadLink": transcription,
                "language": "unverified",
                "source": "provider speech-to-text",
            }
        if not link:
            continue
        url = link.get("downloadLink", "")
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.netloc != "api.apify.com"
            or not parts.path.startswith("/v2/key-value-stores/")
        ):
            errors.append({"id": identity, "reason": "Unsupported caption host/path"})
            continue
        suffix = ".txt" if is_transcription else ".vtt"
        path = folder / (str(raw["id"]) + suffix)
        try:
            if not path.exists():
                with httpx.stream("GET", url, timeout=30, follow_redirects=False) as response:
                    response.raise_for_status()
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise ValueError("Caption file exceeds limit")
                path.write_bytes(body)
            content = path.read_text(encoding="utf-8-sig")
            text = content.strip() if is_transcription else vtt_text(content)
            lookup[identity].update(
                transcript=text,
                transcript_source={
                    "path": str(path.resolve()),
                    "language": link.get("language"),
                    "source": link.get("sourceUnabbreviated") or link.get("source"),
                    "limitation": "Captions may be translated or inaccurate; listening required",
                },
            )
        except Exception as exc:
            errors.append({"id": identity, "reason": type(exc).__name__})
    write_json(output / "references.json", items)
    write_json(output / "caption-errors.json", errors)
    (output / "review.html").write_text(render(items), encoding="utf-8")
    click.echo(
        f"{sum(bool(i['transcript']) for i in items)} references have text; "
        f"{len(errors)} caption errors"
    )


if __name__ == "__main__":
    cli()
