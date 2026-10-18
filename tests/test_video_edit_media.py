import json
import shutil
from uuid import uuid4

import pytest
from PIL import Image

from strategy.video_assets import command, digest, probe
from strategy.video_edit_media import assemble, excerpt
from strategy.video_remake import approve, claim, finish, now, prepare, read_packet, receipt


@pytest.fixture
def media(tmp_path):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Managed FFmpeg required")
    client = tmp_path / "brand"
    client.mkdir()
    command("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=64x96:r=24:d=6",
                       "-f", "lavfi", "-i", "sine=frequency=440:duration=6", "-c:v", "libx264",
                       "-c:a", "aac", str(client / "original.mp4")])
    return client


@pytest.mark.parametrize("start,end", [(3, 2), (-1, 2), (0, 7), (float("nan"), 2)])
def test_excerpt_rejects_invalid_range(media, start, end):
    with pytest.raises(ValueError):
        excerpt(media, "original.mp4", start, end, "Selected scene")


@pytest.mark.parametrize("start,end", [(0, 2), (1, 3), (4, 6)])
def test_short_excerpt_padding_and_assembly_lineage(media, start, end):
    from strategy.creative_recipes import load_recipe

    source = excerpt(media, "original.mp4", start, end, "Explicit two-second scene test")
    info = json.loads((source / "source.json").read_text())
    assert info["duration"] == pytest.approx(4, abs=0.05)
    assert info["excerpt"]["ending_hold"] == 2
    assert info["excerpt"]["original_sha256"] == digest(media / "original.mp4")
    (media / "analysis.json").write_text(json.dumps(dict(provenance="manual_review",
        evidence="Synthetic fixture only", source_sha256=info["sha256"], duration=4,
        shots=[dict(start=0, end=4, camera="Fixed", action="Two seconds plus hold")])) )
    (media / "brief.json").write_text(json.dumps(dict(product="fixture", product_truth="Synthetic",
        purpose="Test assembly", change="setting", direction="Red", preserve="Timing",
        duration=4, billing="free")))
    run = prepare(media, source.relative_to(media).as_posix(), "analysis.json", "brief.json",
                  source.joinpath("reference.png").relative_to(media).as_posix(), element_edit=True)
    relative = run.relative_to(media).as_posix()
    packet = read_packet(media, relative)
    image_id, video_id, job = [str(uuid4()) for _ in range(3)]
    q = dict(params={**packet["params"], "medias":[dict(role="image", value=image_id),
        dict(role="video", value=video_id)]}, credits=0, quoted_at=now(), media_bindings={
        image_id:packet["assets"]["product"]["sha256"], video_id:packet["assets"]["source"]["sha256"]})
    (media / "quote.json").write_text(json.dumps(q))
    approve(media, relative, "quote.json", 0, "Fixture only, no provider call", "test")
    claim(media, relative)
    receipt(media, relative, job)
    command("ffmpeg", ["-v", "error", "-f", "lavfi", "-i", "color=c=red:s=64x96:r=24:d=4",
                       "-c:v", "libx264", str(media / "result.mp4")])
    (media / "evidence.json").write_text(json.dumps(dict(job_id=job, status="completed",
                                                       output_sha256=digest(media / "result.mp4"))))
    raw = finish(media, relative, "result.mp4", "evidence.json", "Synthetic fixture")
    with pytest.raises(ValueError, match="source"):
        assemble(media, relative, "result.mp4", "Wrong original must be rejected")
    assert not (run / "assembly-lock.json").exists()
    preview = assemble(media, relative, "original.mp4", "Synthetic fixture; no visual approval")
    record = load_recipe(preview)
    assert record["parent_version_id"] == raw.parent.name
    output = preview.parent / record["assets"]["preview"]["path"]
    assert probe(output)["duration"] == pytest.approx(6, abs=0.1)
    assert probe(output)["has_audio"]
    times = [0.5, 2.5, 5.5]
    for i, t in enumerate(times):
        frame = media / f"check-{i}.png"
        command("ffmpeg", ["-v", "error", "-ss", str(t), "-i", str(output),
                           "-frames:v", "1", str(frame)])
        red, _, blue = Image.open(frame).convert("RGB").getpixel((10, 10))
        assert (red > blue) == (start <= t < end)
    with pytest.raises(FileExistsError):
        assemble(media, relative, "original.mp4", "Do not overwrite")
