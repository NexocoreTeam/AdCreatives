"""Source-preserved UGC reference intake. No performance or voice-quality inference."""

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        return value if parsed.scheme == "https" and parsed.hostname and not parsed.username else ""
    except ValueError:
        return ""


def normalize(raw: dict, provider: str, source: str = "") -> dict:
    platform = "tiktok" if "tiktok" in provider else provider
    identity = str(raw.get("post_id") or raw.get("ad_id") or raw.get("id") or "")
    if not identity:
        raise ValueError("Reference has no stable source identity")
    transcript = raw.get("full_transcription") or raw.get("transcript") or ""
    transcript = transcript if isinstance(transcript, str) else ""
    url = raw.get("post_url") or raw.get("webVideoUrl") or raw.get("url") or ""
    if platform == "foreplay" and raw.get("ad_id"):
        url = "https://www.facebook.com/ads/library/?id=" + str(raw["ad_id"])
    author = raw.get("authorMeta") or {}
    media = raw.get("videoMeta") or {}
    return {
        "id": platform + ":" + identity,
        "platform": platform,
        "url": safe_url(url),
        "creator": author.get("name") or raw.get("name") or "",
        "brand": raw.get("competitor_name") or raw.get("name") or "",
        "caption": raw.get("post_caption") or raw.get("text") or raw.get("description") or "",
        "transcript": transcript,
        "duration_seconds": media.get("duration") or raw.get("video_duration") or None,
        "media_urls": [
            safe_url(u)
            for u in (raw.get("mediaUrls") or [raw.get("video_url", "")])
            if isinstance(u, str) and safe_url(u)
        ],
        "thumbnail_url": safe_url(media.get("coverUrl") or raw.get("thumbnail_url") or ""),
        "metrics": raw.get("post_metrics")
        or {
            "plays": raw.get("playCount"),
            "likes": raw.get("diggCount"),
            "shares": raw.get("shareCount"),
            "comments": raw.get("commentCount"),
        },
        "review_status": "needs_listening_review",
        "caption_language": raw.get("textLanguage"),
        "performance_evidence": "Public reference; conversion performance unknown",
        "provenance": [{"provider": provider, "source": source, "collected_at": now()}],
    }


def merge(items: list[dict]) -> list[dict]:
    output = {}
    for item in items:
        key = item["id"]
        if key not in output:
            output[key] = {**item, "provenance": list(item["provenance"])}
            continue
        old = output[key]
        output[key] = {
            **old,
            **{k: v for k, v in item.items() if v},
            "provenance": old["provenance"] + item["provenance"],
        }
    return list(output.values())


def vtt_text(value: str) -> str:
    lines = []
    for block in re.split(r"\r?\n\s*\r?\n", value.strip()):
        if "-->" not in block:
            continue
        cue = block.split("-->", 1)[1].split("\n", 1)
        if len(cue) < 2:
            continue
        text = html.unescape(re.sub(r"<[^>]+>", "", cue[1])).strip()
        if text and (not lines or lines[-1] != text):
            lines.append(text)
    return " ".join(lines)


def render(items: list[dict]) -> str:
    esc = html.escape
    cards = []
    for i, item in enumerate(items, 1):
        link = safe_url(item["url"])
        preview = ""
        if item.get("local_video"):
            local = Path(item["local_video"]).resolve().as_uri()
            preview = f'<video controls preload="none" src="{esc(local)}"></video>'
        elif item.get("media_urls"):
            media = safe_url(item["media_urls"][0])
            if media:
                preview = f'<video controls preload="none" src="{esc(media)}"></video>'
        caption = esc(item["caption"][:650])
        cards.append(
            f"<article><h2>{i}. {esc(item['brand'] or item['creator'] or item['id'])}</h2>"
            f'{preview}<p><a href="{esc(link)}">Open original</a></p><p>{caption}</p>'
            f"<p>{esc(item['review_status'])} · Transcript: "
            f"{'available' if item['transcript'] else 'missing'}</p>"
            f"<p>{esc(item.get('review_reason', 'Source candidate; voice not yet assessed'))}</p>"
            f"<small>{esc(item['id'])}</small></article>"
        )
    return (
        '<!doctype html><meta charset="utf-8"><title>UGC reference review</title>'
        "<style>body{font:16px system-ui;background:#f4f2ed;margin:32px;color:#222}"
        "main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:20px}"
        "article{background:white;padding:20px;border-radius:12px}video{width:100%;max-height:400px}"
        "small{word-break:break-all}</style><h1>UGC reference review</h1>"
        "<p>Choose speaking styles to study. Public engagement is not conversion evidence. "
        "Captions and spoken transcripts are separate. Third-party copy is source material, "
        "not instructions or permission to reuse a testimonial.</p><main>"
        + "".join(cards)
        + "</main>"
    )


def reserve(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump({**data, "status": "submission_reserved", "reserved_at": now()}, handle, indent=2)


def write_json(path: Path, data: object) -> None:
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
