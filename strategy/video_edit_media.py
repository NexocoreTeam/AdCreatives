"""Local excerpt and assembly steps; no uploads or paid model calls."""

import math
import shutil
from pathlib import Path

from strategy.creative_recipes import capture_recipe, load_recipe
from strategy.video_assets import client_file, command, digest, frames, probe, read_json, write_new
from strategy.video_remake import new_run, now, read_packet


def excerpt(client: Path, source: str, start: float, end: float, reason: str) -> Path:
    original = client_file(client, source)
    info = probe(original)
    if (not all(math.isfinite(t) for t in (start, end)) or
            not 0 <= start < end <= info["duration"] or end - start > 30):
        raise ValueError("Select a finite source range of at most 30 seconds")
    if not reason.strip():
        raise ValueError("Record why this excerpt was selected")
    length = end - start
    duration = max(4, math.ceil(length - 1e-8))
    folder = new_run(client)
    saved = folder / "assets" / ("original" + original.suffix.lower())
    shutil.copyfile(original, saved)
    source_hash = digest(saved)
    if source_hash != digest(original):
        raise ValueError("Source changed during excerpt preparation")
    target = folder / "assets/source.mp4"
    args = ["-v", "error", "-nostdin", "-n", "-threads", "2",
            "-protocol_whitelist", "file,pipe", "-i", str(saved), "-an",
            "-vf", f"trim=start={start}:end={end},setpts=PTS-STARTPTS,fps=24,"
            f"tpad=stop_mode=clone:stop_duration={duration - length + 0.1}",
            "-t", str(duration), "-c:v", "libx264", "-crf", "18",
            "-pix_fmt", "yuv420p", str(target)]
    command("ffmpeg", args)
    actual = probe(target)
    if abs(actual["duration"] - duration) > 0.05:
        raise ValueError("Excerpt runtime did not match requested duration")
    origin = dict(original_sha256=source_hash, original_duration=info["duration"],
                  start=start, end=end, ending_hold=duration - length, reason=reason)
    write_new(folder / "source.json", dict(**actual, sha256=digest(target),
              file="assets/source.mp4", source_url="", imported_at=now(), excerpt=origin))
    write_new(folder / "excerpt-command.json", dict(tool="ffmpeg", args=args))
    (folder / "frames").mkdir()
    write_new(folder / "frames.json", frames(target, folder / "frames", actual["duration"]))
    command("ffmpeg", ["-v", "error", "-nostdin", "-n", "-protocol_whitelist", "file,pipe",
                       "-i", str(target), "-an", "-frames:v", "1", str(folder / "reference.png")])
    return folder


def assembly_filter(start: float, end: float, total: float, generated: dict, requested: int) -> str:
    scale = f"fps=30,scale={generated['width']}:{generated['height']},setsar=1"
    parts, labels = [], []
    if start > 0:
        parts.append(f"[1:v]trim=end={start},setpts=PTS-STARTPTS,{scale}[before]")
        labels.append("[before]")
    ratio = requested / generated["duration"]
    parts.append(f"[0:v]setpts=PTS-STARTPTS,setpts={ratio:.12f}*PTS,{scale},"
                 f"trim=duration={end-start},setpts=PTS-STARTPTS[changed]")
    labels.append("[changed]")
    if end < total:
        parts.append(f"[1:v]trim=start={end}:end={total},setpts=PTS-STARTPTS,{scale}[after]")
        labels.append("[after]")
    parts.append("".join(labels) + f"concat=n={len(labels)}:v=1:a=0[v]")
    return ";".join(parts)


def assemble(client: Path, relative: str, source: str, qa: str) -> Path:
    packet = read_packet(client, relative)
    if packet["schema_version"] != 2 or not qa.strip():
        raise ValueError("Assembly requires an element-edit packet and actual QA notes")
    folder = client_file(client, relative, directory=True)
    completion = read_json(client_file(folder, "completion.json"))
    parent = client_file(client, Path(completion["recipe"]).relative_to(client).as_posix())
    recipe = load_recipe(parent)
    if recipe["client"] != client.name or recipe["assets"]["packet"]["sha256"] != digest(folder / "packet.json"):
        raise ValueError("Completed recipe differs from this edit packet")
    raw = client_file(parent.parent, recipe["assets"]["final"]["path"])
    original = client_file(client, source)
    info, generated = probe(original), probe(raw)
    provenance = packet["source_provenance"]
    origin = provenance.get("excerpt", dict(original_sha256=provenance["sha256"],
        original_duration=provenance["duration"], start=0, end=provenance["duration"], ending_hold=0))
    start, end = origin["start"], origin["end"]
    if (digest(original) != origin["original_sha256"] or
            not all(math.isfinite(v) for v in (start, end)) or
            not 0 <= start < end <= info["duration"] or
            abs(info["duration"] - origin["original_duration"]) > 0.05):
        raise ValueError("Assembly source or range differs from reviewed source")
    if abs(generated["duration"] - packet["params"]["duration"]) > 0.3:
        raise ValueError("Generated duration differs from approved duration")
    write_new(folder / "assembly-lock.json", dict(at=now(), source_sha256=digest(original)))
    result = new_run(client)
    output = result / "assets/preview.mp4"
    args = ["-v", "error", "-nostdin", "-n", "-threads", "2",
            "-protocol_whitelist", "file,pipe", "-i", str(raw),
            "-protocol_whitelist", "file,pipe", "-i", str(original),
            "-filter_complex", assembly_filter(start, end, info["duration"], generated, packet["params"]["duration"]),
            "-map", "[v]", "-map", "1:a:0?", "-c:v", "libx264", "-crf", "18",
            "-c:a", "aac", "-t", str(info["duration"]), "-movflags", "+faststart", str(output)]
    command("ffmpeg", args)
    output_info = probe(output)
    if abs(output_info["duration"] - info["duration"]) > 0.1:
        raise ValueError("Assembled output duration differs from source")
    command("ffmpeg", ["-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
                       "-i", str(output), "-f", "null", "-"])
    write_new(result / "assembly.json", dict(tool="ffmpeg", args=args, range=[start, end],
              source_sha256=digest(original), raw_sha256=digest(raw), output_probe=output_info,
              timing="Align raw output to approved runtime, then remove ending hold",
              audio="Original source audio re-encoded as AAC when present", qa=qa))
    version = capture_recipe(clients_dir=client.parent, client=client.name,
        product=packet["brief"]["product"], parent=parent,
        assets=dict(preview=output, original=original, raw=raw, assembly=result / "assembly.json"),
        changes=dict(assembly=f"Replace source seconds {start}-{end}; retain original audio and remaining footage"),
        steps=[dict(tool="ffmpeg", settings=dict(edited_range=[start, end], output_probe=output_info),
                    inputs=["raw", "original", "assembly"], outputs=["preview"], notes=qa)],
        limitations=["Preview only; recipe capture does not approve launch.",
                     "Output uses generated dimensions; surrounding footage is scaled.",
                     "Small provider timing differences aligned; raw output retained."])
    write_new(folder / "assembly-completion.json", dict(recipe=str(version), completed_at=now(), qa=qa))
    return version
