"""Reference ad analysis — vision over performant past ads pulled from Drive.

For each file in `reference-ads/`:
- Images (PNG/JPG/WebP): vision directly
- Videos (MP4/MOV/WebM): extract a representative frame via ffmpeg, then vision

Output: per-file YAML at `clients/<slug>/reference_ads/analyses/<stem>.yaml`,
plus a `_summary.yaml` index. Used downstream by `pattern_learner.py` and as
optional reference input to the angle multiplier.

Cached by Drive modifiedTime — re-uploads invalidate automatically.
"""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from models.loader import CLIENTS_DIR, load_brand
from strategy.brand_enricher import _downscale_to_data_uri, _parse_json_response
from strategy.drive_cache import DriveCache
from strategy.drive_client import DriveClient, DriveFile
from strategy.llm import gemini_vision

ANALYSES_DIRNAME = "analyses"
SUMMARY_FILENAME = "_summary.yaml"
VIDEO_FRAME_TIMESTAMP = "00:00:01.000"  # representative early-but-past-intro frame


REFERENCE_AD_SYSTEM = """You are an expert direct-response advertising strategist
analyzing a past creative asset to extract patterns the brand should learn from.
You see one frame of a static or video ad. Output a structured analysis that
the angle multiplier and pattern learner will consume downstream.

Hard rules:
- Output VALID JSON only. No prose, no markdown fences.
- Quote the visible hook/copy VERBATIM where readable; mark text [unreadable]
  if obscured. Don't paraphrase.
- For videos analyzed via a single extracted frame, note that limitation in
  `confidence_notes` — you're inferring the full ad from one moment.
- Specific > generic. "Talking-head UGC creator in a kitchen, 30s woman, holding
  the can to camera" beats "lifestyle ad".

Output JSON schema:

{
  "hook_visible": "the visible text/copy in the ad, verbatim, or '[no visible text]'",
  "hook_type": "stat | story | question | contrast | fomo | direct_call_out | pattern_interrupt | controversial | problem_solution",
  "copy_treatment": "1 sentence on how the copy is laid out (overlay, caption, on-product, etc.)",
  "visual_format": "ugc_static | product_hero | before_after | talking_head | split_screen | text_card | lifestyle | other",
  "creative_mechanic": "name of the structural mechanic if recognizable (e.g. 'pattern interrupt with reveal', 'before/after split', 'cart inventory reveal')",
  "elements_present": ["product_shot", "human_face", "text_overlay", "lifestyle_imagery", "logo_visible", "ugc_aesthetic", "studio_aesthetic"],
  "mood": ["adjective1", "adjective2", "adjective3"],
  "color_palette_dominant": ["#XXXXXX", "#XXXXXX"],
  "composition_notes": "1 sentence on framing, focal point, eye-flow",
  "likely_strengths": "1-2 sentences on why this ad might have performed well",
  "likely_weaknesses": "1-2 sentences on what might limit its performance",
  "extraction_confidence": "high | medium | low",
  "confidence_notes": "What you could/couldn't tell from this frame"
}"""


@dataclass
class ReferenceAdAnalysis:
    """One reference ad's structured analysis. Persisted per-file."""

    filename: str
    file_id: str
    mime_type: str
    is_video_frame: bool  # True if analysis came from a single video frame
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReferenceAdsResult:
    """Outcome of analyze-references run."""

    analyses: list[ReferenceAdAnalysis] = field(default_factory=list)
    cache_hits: int = 0
    new_analyses: int = 0
    skipped: list[tuple[str, str]] = field(default_factory=list)


# ─── Public entry point ─────────────────────────────────────────────────────


def analyze_references_from_drive(
    client_slug: str,
    *,
    force: bool = False,
) -> ReferenceAdsResult:
    """Pull `reference-ads/` files from Drive, vision-analyze each, write per-file YAMLs.

    Videos are analyzed via a single representative frame extracted with ffmpeg.
    Re-running against an unchanged Drive file is a no-op (cache hit).
    """
    brand = load_brand(client_slug)
    if not brand.drive_folder_id:
        raise ValueError(
            f"Client '{client_slug}' has no drive_folder_id. Set it in brand.yaml first."
        )

    drive = DriveClient()
    cache = DriveCache(client_slug)

    files = drive.list_subfolder(brand.drive_folder_id, "reference-ads")
    if not files:
        raise ValueError(
            f"No files in Drive reference-ads/ for '{client_slug}'. "
            f"Drop past performant ads (PNG/JPG/MP4/MOV) into the folder and re-run."
        )

    analyses_dir = CLIENTS_DIR / client_slug / "reference_ads" / ANALYSES_DIRNAME
    analyses_dir.mkdir(parents=True, exist_ok=True)

    result = ReferenceAdsResult()

    for f in files:
        if f.is_image:
            analyzer_tag = "reference_image"
        elif f.is_video:
            analyzer_tag = "reference_video_frame"
        else:
            result.skipped.append((f.name, f"unsupported mime: {f.mime_type}"))
            continue

        cached = None if force else cache.get(f)
        if cached and cached.analyzer == analyzer_tag:
            payload = cached.payload
            result.cache_hits += 1
        else:
            if f.is_image:
                payload = _analyze_image(drive, f)
            else:
                payload = _analyze_video(drive, f)
                if payload is None:
                    result.skipped.append((f.name, "ffmpeg frame extraction failed"))
                    continue
            cache.put(f, analyzer_tag, payload)
            result.new_analyses += 1

        analysis = ReferenceAdAnalysis(
            filename=f.name,
            file_id=f.id,
            mime_type=f.mime_type,
            is_video_frame=f.is_video,
            payload=payload,
        )
        result.analyses.append(analysis)
        _write_per_file_yaml(analyses_dir, analysis)

    _write_summary(analyses_dir, result)
    return result


# ─── Image analysis ─────────────────────────────────────────────────────────


def _analyze_image(drive: DriveClient, f: DriveFile) -> dict[str, Any]:
    raw = drive.download_bytes(f.id)
    data_uri = _downscale_to_data_uri(raw, f.mime_type)
    user_prompt = (
        f"Reference ad filename: {f.name}\n"
        f"Format: static image\n\n"
        f"Apply the analysis schema. Output JSON only."
    )
    response = gemini_vision(
        prompt=user_prompt,
        image_urls=[data_uri],
        system=REFERENCE_AD_SYSTEM,
        max_tokens=1500,
    )
    return _parse_json_response(response, "reference_image")


# ─── Video analysis (ffmpeg frame extract → vision) ─────────────────────────


def _analyze_video(drive: DriveClient, f: DriveFile) -> dict[str, Any] | None:
    """Download video, extract a frame via ffmpeg, run vision on the frame.

    Returns None if ffmpeg is unavailable or frame extraction fails. The caller
    treats None as a soft skip.
    """
    if not shutil.which("ffmpeg"):
        return None

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        video_path = tmp_path / f.name
        frame_path = tmp_path / "frame.png"

        drive.download_to(f.id, video_path)
        extracted = _extract_frame(video_path, frame_path)
        if not extracted:
            return None

        raw = frame_path.read_bytes()
        data_uri = _downscale_to_data_uri(raw, "image/png")

    user_prompt = (
        f"Reference ad filename: {f.name}\n"
        f"Format: VIDEO — analyzing a single representative frame extracted at "
        f"{VIDEO_FRAME_TIMESTAMP} (just past the intro). The hook may be on a "
        f"different frame; note this in confidence_notes if the hook isn't visible.\n\n"
        f"Apply the analysis schema. Output JSON only."
    )
    response = gemini_vision(
        prompt=user_prompt,
        image_urls=[data_uri],
        system=REFERENCE_AD_SYSTEM,
        max_tokens=1500,
    )
    return _parse_json_response(response, "reference_video_frame")


def _extract_frame(video_path: Path, frame_path: Path) -> bool:
    """Extract a single frame at VIDEO_FRAME_TIMESTAMP via ffmpeg. Returns success."""
    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",  # overwrite output
                "-ss", VIDEO_FRAME_TIMESTAMP,
                "-i", str(video_path),
                "-frames:v", "1",
                "-q:v", "2",
                str(frame_path),
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0 or not frame_path.exists():
            # Try again from the very start in case the video is shorter than the
            # default timestamp (1s). Pulls the first frame instead.
            result = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i", str(video_path),
                    "-frames:v", "1",
                    "-q:v", "2",
                    str(frame_path),
                ],
                capture_output=True,
                timeout=60,
            )
        return frame_path.exists() and frame_path.stat().st_size > 0
    except (subprocess.SubprocessError, OSError):
        return False


# ─── Output writing ─────────────────────────────────────────────────────────


def _write_per_file_yaml(analyses_dir: Path, analysis: ReferenceAdAnalysis) -> Path:
    stem = Path(analysis.filename).stem
    # Truncate very long hash-based filenames for readability
    if len(stem) > 60:
        stem = stem[:8] + "_" + stem[-8:]
    path = analyses_dir / f"{stem}.yaml"
    data = {
        "filename": analysis.filename,
        "file_id": analysis.file_id,
        "mime_type": analysis.mime_type,
        "is_video_frame": analysis.is_video_frame,
        "analysis": analysis.payload,
    }
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return path


def _write_summary(analyses_dir: Path, result: ReferenceAdsResult) -> Path:
    """Write a compact index of all analyzed references."""
    summary_path = analyses_dir / SUMMARY_FILENAME
    entries = []
    for a in result.analyses:
        p = a.payload
        entries.append(
            {
                "filename": a.filename,
                "format": "video_frame" if a.is_video_frame else "image",
                "hook_type": p.get("hook_type", ""),
                "visual_format": p.get("visual_format", ""),
                "creative_mechanic": p.get("creative_mechanic", ""),
                "mood": p.get("mood", []),
                "hook_visible": (p.get("hook_visible") or "")[:120],
            }
        )
    summary = {
        "total_analyzed": len(result.analyses),
        "cache_hits": result.cache_hits,
        "new_analyses": result.new_analyses,
        "skipped": result.skipped,
        "entries": entries,
    }
    summary_path.write_text(
        yaml.safe_dump(summary, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    return summary_path
