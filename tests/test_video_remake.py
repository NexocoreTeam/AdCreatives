import json
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from models.video_remake import RemakeBrief, VideoAnalysis
from strategy.video_assets import client_file, digest
from strategy.video_remake import approve, claim, finish, now, prepare, read_packet, receipt


def analysis(source_hash="a" * 64):
    return dict(
        provenance="manual_review",
        evidence="Reviewed reference frames",
        source_sha256=source_hash,
        duration=6,
        shots=[
            dict(
                start=0,
                end=6,
                camera="Handheld mirror selfie",
                action="Steps backward",
                dialogue="",
            )
        ],
    )


def fixture_run(tmp_path):
    client = tmp_path / "savedbygrace"
    run = client / "video-remakes" / "source-test"
    (run / "assets").mkdir(parents=True)
    (run / "assets/source.mp4").write_bytes(b"source fixture")
    Image.new("RGB", (32, 32)).save(client / "product.png")
    source_hash = digest(run / "assets/source.mp4")
    (run / "source.json").write_text(
        json.dumps(dict(sha256=source_hash, duration=6, file="assets/source.mp4", source_url=""))
    )
    (client / "analysis.json").write_text(json.dumps(analysis(source_hash)))
    (client / "brief.json").write_text(
        json.dumps(
            dict(
                product="diet-coke",
                product_truth="Grey pullover with exact printed lettering",
                duration=6,
                direction="Start close, step back; lips closed",
                purpose="Reuse winning movement",
            )
        )
    )
    return client, run


def make_packet(tmp_path):
    client, run = fixture_run(tmp_path)
    packet = prepare(
        client, run.relative_to(client).as_posix(), "analysis.json", "brief.json", "product.png"
    )
    return client, packet


@pytest.mark.parametrize(
    "value",
    [
        "../secret.txt",
        "C:/secret.txt",
        "//server/share/a",
        "https://example.com/a",
        "a:stream",
        "a\\b",
    ],
)
def test_asset_boundary(tmp_path, value):
    with pytest.raises(ValueError):
        client_file(tmp_path, value)


def test_symlink_escape(tmp_path):
    folder = tmp_path / "client"
    folder.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("private")
    try:
        (folder / "link.txt").symlink_to(secret)
    except OSError:
        pytest.skip("Creating symlinks unavailable")
    with pytest.raises(ValueError):
        client_file(folder, "link.txt")


def test_analysis_requires_source_and_complete_timeline():
    bad = analysis()
    bad["shots"][0]["start"] = 1
    with pytest.raises(ValueError):
        VideoAnalysis.model_validate(bad)
    bad = analysis()
    bad["shots"][0]["end"] = 7
    with pytest.raises(ValueError):
        VideoAnalysis.model_validate(bad)


def test_silent_plan_rejects_spoken_script():
    with pytest.raises(ValueError):
        RemakeBrief(
            product="p",
            product_truth="label",
            direction="d",
            purpose="test",
            duration=6,
            script="hello",
            audio="silent",
        )


def test_prepare_is_local_immutable_and_preserves_product(tmp_path):
    client, packet = make_packet(tmp_path)
    data = read_packet(client, packet.relative_to(client).as_posix())
    prompt = data["params"]["prompt"]
    assert "printed" in prompt and "closed" in prompt
    assert data["params"]["duration"] == 6
    assert data["params"]["generate_audio"] is False
    assert "medias" not in data["params"]
    assert not (packet / "approval.json").exists()


def test_kids_remake_preserves_age_direction_without_forcing_adult(tmp_path):
    client, source = fixture_run(tmp_path)
    brief = json.loads((client / "brief.json").read_text())
    brief.update(product="kids-pullover", product_truth="Children's sweatshirt",
                 direction="A fictional six-year-old child in the kids sweatshirt")
    (client / "brief.json").write_text(json.dumps(brief))
    run = prepare(client, source.relative_to(client).as_posix(), "analysis.json",
                  "brief.json", "product.png")
    packet = read_packet(client, run.relative_to(client).as_posix())
    prompt = packet["params"]["prompt"]
    assert brief["direction"] in prompt
    assert "Use a fictional adult" not in prompt
    assert "Keep clothing fully on" in prompt
    assert packet["brief"]["product_truth"] == brief["product_truth"]


def test_tampered_asset_rejected(tmp_path):
    client, packet = make_packet(tmp_path)
    (packet / "assets/product.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="hash"):
        read_packet(client, packet.relative_to(client).as_posix())


def test_wrong_source_analysis_rejected(tmp_path):
    client, run = fixture_run(tmp_path)
    (client / "analysis.json").write_text(json.dumps(analysis()))
    with pytest.raises(ValueError, match="source"):
        prepare(
            client, run.relative_to(client).as_posix(), "analysis.json", "brief.json", "product.png"
        )


def test_cost_approval_exact_params_and_single_claim(tmp_path):
    client, packet = make_packet(tmp_path)
    relative = packet.relative_to(client).as_posix()
    data = read_packet(client, relative)
    params = dict(
        data["params"], medias=[dict(role="image", value="a6484881-e0a1-4f88-9969-a422fe69e27e")]
    )
    quote = dict(params=params, credits=12, quoted_at="2099-01-01T00:00:00+00:00")
    quote["media_bindings"] = {params["medias"][0]["value"]: data["assets"]["product"]["sha256"]}
    (client / "quote.json").write_text(json.dumps(quote))
    with pytest.raises(ValueError):
        approve(client, relative, "quote.json", 11, "Approved", "Mitchell")
    quote["quoted_at"] = now()
    (client / "quote.json").write_text(json.dumps(quote))
    approve(client, relative, "quote.json", 12, "Approved 12 credits", "Mitchell")
    first = claim(client, relative)
    assert first["params"] == params
    with pytest.raises((ValueError, FileExistsError)):
        claim(client, relative)
    receipt(client, relative, "de80c33b-2151-47aa-93e9-20588aba2300")
    with pytest.raises((ValueError, FileExistsError)):
        receipt(client, relative, "de80c33b-2151-47aa-93e9-20588aba2300")


def test_quote_cannot_change_prompt(tmp_path):
    client, packet = make_packet(tmp_path)
    data = read_packet(client, packet.relative_to(client).as_posix())
    params = dict(data["params"], prompt="changed", medias=[])
    (client / "quote.json").write_text(
        json.dumps(dict(params=params, credits=12, quoted_at="2026-10-17T00:00:00+00:00"))
    )
    with pytest.raises(ValueError):
        approve(client, packet.relative_to(client).as_posix(), "quote.json", 12, "yes", "M")


def quote_for(client, packet):
    data = read_packet(client, packet.relative_to(client).as_posix())
    media = "a6484881-e0a1-4f88-9969-a422fe69e27e"
    quote = dict(
        params=dict(data["params"], medias=[dict(role="image", value=media)]),
        credits=12,
        quoted_at=now(),
        media_bindings={media: data["assets"]["product"]["sha256"]},
    )
    return quote


@pytest.mark.parametrize("kind", ["stale", "future", "binding", "missing_binding", "nan"])
def test_quote_rejects_unsafe_inputs(tmp_path, kind):
    client, packet = make_packet(tmp_path)
    q = quote_for(client, packet)
    if kind in ("stale", "future"):
        delta = -2 if kind == "stale" else 2
        q["quoted_at"] = (datetime.now(timezone.utc) + timedelta(days=delta)).isoformat()
    elif kind == "binding":
        q["media_bindings"] = {next(iter(q["media_bindings"])): "a" * 64}
    elif kind == "missing_binding":
        q.pop("media_bindings")
    else:
        q["credits"] = float("nan")
    (client / "quote.json").write_text(json.dumps(q))
    with pytest.raises(ValueError):
        approve(client, packet.relative_to(client).as_posix(), "quote.json", 12, "yes", "M")
    assert not (packet / "approval.json").exists()


def test_concurrent_claim_has_one_winner(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    client, packet = make_packet(tmp_path)
    relative = packet.relative_to(client).as_posix()
    (client / "quote.json").write_text(json.dumps(quote_for(client, packet)))
    approve(client, relative, "quote.json", 12, "Approved", "M")

    def attempt():
        try:
            return claim(client, relative)
        except FileExistsError:
            return None

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: attempt(), range(4)))
    assert sum(r is not None for r in results) == 1


def test_complete_recipe_and_reject_wrong_download(tmp_path, monkeypatch):
    from strategy.creative_recipes import load_recipe

    client, packet = make_packet(tmp_path)
    relative = packet.relative_to(client).as_posix()
    (client / "quote.json").write_text(json.dumps(quote_for(client, packet)))
    approve(client, relative, "quote.json", 12, "Approved", "M")
    claim(client, relative)
    job = "de80c33b-2151-47aa-93e9-20588aba2300"
    receipt(client, relative, job)
    output = client / "output.mp4"
    output.write_bytes(b"generated output fixture")
    evidence = dict(job_id=job, status="completed", output_sha256="a" * 64)
    (client / "evidence.json").write_text(json.dumps(evidence))
    monkeypatch.setattr("strategy.video_remake.probe", lambda _: dict(duration=6))
    with pytest.raises(ValueError, match="bytes"):
        finish(client, relative, "output.mp4", "evidence.json", "Reviewed fixture")
    evidence["output_sha256"] = digest(output)
    (client / "evidence.json").write_text(json.dumps(evidence))
    path = finish(client, relative, "output.mp4", "evidence.json", "Fixture only, no live QA")
    result = load_recipe(path)
    assert result["assets"]["final"]["sha256"] == digest(output)
    assert result["steps"][0]["settings"]["job_id"] == job
    with pytest.raises(FileExistsError):
        finish(client, relative, "output.mp4", "evidence.json", "No duplicate")


def test_network_playlist_is_not_media(tmp_path):
    from strategy.video_assets import probe

    file = tmp_path / "playlist.mp4"
    file.write_text("#EXTM3U\nhttps://internal.example/secret")
    with pytest.raises(ValueError, match="signature"):
        probe(file)


def test_cli_prepare_and_escape(tmp_path):
    from click.testing import CliRunner

    from cli import cli

    client, run = fixture_run(tmp_path)
    args = [
        "video-reference",
        "--client",
        client.name,
        "--clients-dir",
        str(tmp_path),
        "prepare",
        "--reference",
        run.relative_to(client).as_posix(),
        "--analysis",
        "analysis.json",
        "--brief",
        "brief.json",
    ]
    result = CliRunner().invoke(cli, args + ["--product-image", "../secret.png"])
    assert result.exit_code != 0
    result = CliRunner().invoke(cli, args + ["--product-image", "product.png"])
    assert result.exit_code == 0, result.output


def test_real_video_ingest_is_bounded_and_preserves_bytes(tmp_path):
    import shutil

    from strategy.video_assets import command
    from strategy.video_remake import ingest

    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Managed FFmpeg not installed")
    client = tmp_path / "client"
    client.mkdir()
    file = client / "source.mp4"
    command(
        "ffmpeg",
        [
            "-v",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x64:r=5:d=1",
            "-c:v",
            "mpeg4",
            str(file),
        ],
    )
    run = ingest(client, "source.mp4", "https://example.com/ad?token=secret")
    info = json.loads((run / "source.json").read_text())
    assert info["source_url"] == "https://example.com/ad"
    assert info["sha256"] == digest(file)
    assert info["has_audio"] is False
    frame_info = json.loads((run / "frames.json").read_text())
    assert 12 <= len(frame_info["frames"]) <= 24
    assert all((run / "frames" / f["file"]).is_file() for f in frame_info["frames"])


def test_media_process_timeout_and_error_are_sanitized(monkeypatch):
    import subprocess

    from strategy.video_assets import command

    monkeypatch.setattr("strategy.video_assets.shutil.which", lambda _: "ffmpeg")

    def timeout(*args, **kwargs):
        assert kwargs["shell"] is False
        assert kwargs["timeout"] == 2
        raise subprocess.TimeoutExpired("secret-url", 2)

    monkeypatch.setattr("strategy.video_assets.subprocess.run", timeout)
    with pytest.raises(ValueError, match="timeout") as error:
        command("ffmpeg", ["arbitrary; text"], 2)
    assert "secret" not in str(error.value)
    monkeypatch.setattr(
        "strategy.video_assets.subprocess.run",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, b"", b"secret-token"),
    )
    with pytest.raises(ValueError) as error:
        command("ffmpeg", [])
    assert "secret" not in str(error.value)


def test_approval_tampering_blocks_receipt(tmp_path):
    client, packet = make_packet(tmp_path)
    relative = packet.relative_to(client).as_posix()
    (client / "quote.json").write_text(json.dumps(quote_for(client, packet)))
    approve(client, relative, "quote.json", 12, "Approved", "M")
    claim(client, relative)
    approval_file = packet / "approval.json"
    approval_file.write_text(approval_file.read_text() + " ")
    with pytest.raises(ValueError, match="changed"):
        receipt(client, relative, "de80c33b-2151-47aa-93e9-20588aba2300")
