"""Bounded local media ingestion. No URL fetching, shell or automatic installs."""

import hashlib
import json
import math
import re
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path, PureWindowsPath

from PIL import Image

MAX_VIDEO = 200 * 1024 * 1024
MAX_IMAGE = 25 * 1024 * 1024


def client_file(root: Path, relative: str, *, directory: bool = False) -> Path:
    if (
        not relative
        or "\\" in relative
        or ":" in relative
        or Path(relative).is_absolute()
        or PureWindowsPath(relative).drive
        or any(part in ("..", ".") for part in relative.split("/"))
    ):
        raise ValueError("Use a relative path inside this client folder")
    root = root.resolve(strict=True)
    current = root
    for part in relative.split("/"):
        current = current / part
        if current.is_symlink() or (hasattr(current, "is_junction") and current.is_junction()):
            raise ValueError("Linked assets are not allowed")
    target = current.resolve(strict=True)
    if not target.is_relative_to(root):
        raise ValueError("Asset escapes client folder")
    if not (target.is_dir() if directory else target.is_file()):
        raise ValueError("Expected a client file or run folder")
    return target


def digest(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(file: Path) -> dict:
    if file.stat().st_size > 1_000_000:
        raise ValueError("JSON exceeds 1 MB limit")
    value = json.loads(file.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def write_new(file: Path, value: dict) -> None:
    with file.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def command(tool: str, args: list[str], timeout: int = 120) -> str:
    executable = shutil.which(tool)
    if not executable:
        raise ValueError(f"Managed {tool} installation required; nothing was installed")
    try:
        result = subprocess.run(
            [executable, *args], shell=False, capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        raise ValueError(f"{tool} exceeded media processing timeout") from None
    if result.returncode:
        raise ValueError(f"{tool} rejected media; no generation submitted")
    return (result.stdout + result.stderr).decode("utf-8", errors="replace")


def probe(file: Path) -> dict:
    if file.suffix.lower() not in (".mp4", ".mov", ".webm", ".mkv"):
        raise ValueError("Use an MP4, MOV, WebM or MKV video file")
    if not 0 < file.stat().st_size <= MAX_VIDEO:
        raise ValueError("Video must be no larger than 200 MB")
    with file.open("rb") as stream:
        header = stream.read(12)
    if header[4:8] != b"ftyp" and header[:4] != b"\x1aE\xdf\xa3":
        raise ValueError("Media signature does not match a supported video container")
    raw = command(
        "ffprobe",
        [
            "-v",
            "error",
            "-protocol_whitelist",
            "file,pipe",
            "-show_entries",
            "format=duration:stream=codec_type,width,height,avg_frame_rate",
            "-of",
            "json",
            str(file),
        ],
        30,
    )
    info = json.loads(raw)
    duration = float(info.get("format", {}).get("duration", 0))
    videos = [s for s in info.get("streams", []) if s.get("codec_type") == "video"]
    if not math.isfinite(duration) or not 0 < duration <= 180 or not videos:
        raise ValueError("Use an explicit video excerpt of at most 180 seconds")
    video = videos[0]
    try:
        frame_rate = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        frame_rate = 0
    if not 0 < frame_rate <= 240:
        raise ValueError("Video must report a supported frame rate up to 240 fps")
    if not 0 < video.get("width", 0) <= 4096 or not 0 < video.get("height", 0) <= 4096:
        raise ValueError("Video dimensions must be at most 4096 pixels per side")
    return dict(
        duration=duration,
        width=video["width"],
        height=video["height"],
        has_audio=any(s.get("codec_type") == "audio" for s in info["streams"]),
        frame_rate=frame_rate,
    )


def copy_image(source: Path, destination: Path) -> None:
    if source.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        raise ValueError("Product reference must be PNG, JPEG or WebP")
    if not 0 < source.stat().st_size <= MAX_IMAGE:
        raise ValueError("Product image exceeds 25 MB")
    with Image.open(source) as img:
        if max(img.size) > 8192 or img.format not in ("PNG", "JPEG", "WEBP"):
            raise ValueError("Unsupported product image")
        img.verify()
    shutil.copyfile(source, destination)


def frames(file: Path, folder: Path, duration: float, frame_rate: float = 30) -> dict:
    log = command(
        "ffmpeg",
        [
            "-hide_banner",
            "-nostdin",
            "-threads",
            "2",
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(file),
            "-an",
            "-vf",
            "scale=160:-2,select='gt(scene,0.30)',showinfo",
            "-frames:v",
            "24",
            "-f",
            "null",
            "-",
        ],
    )
    cuts = sorted(set(float(t) for t in re.findall(r"pts_time:([\d.]+)", log)))
    times = sorted(
        set(
            [round(i * max(0, duration - max(0.1, 1 / frame_rate)) / 11, 3) for i in range(12)]
            + [round(t, 3) for t in cuts[:12]]
        )
    )
    tiles = []
    for index, time in enumerate(times):
        out = folder / f"frame-{index:02}.jpg"
        command(
            "ffmpeg",
            [
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-n",
                "-threads",
                "2",
                "-ss",
                str(time),
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(file),
                "-an",
                "-frames:v",
                "1",
                "-vf",
                "scale=360:-2",
                str(out),
            ],
            30,
        )
        tiles.append(dict(time=time, file=out.name, sha256=digest(out)))
    return dict(
        method="ffmpeg scene threshold 0.30 plus evenly spaced frames",
        cuts=cuts,
        frames=tiles,
        limitations=[
            "Candidate cuts are heuristic, not a verified shot list.",
            "Frames do not establish dialogue or audio contents.",
        ],
    )
