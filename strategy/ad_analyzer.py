"""AI first-pass analysis of a competitor ad → draft reference card.

The expert-eye layer of the Ad Reference Library: a vision model breaks an
ad down into the agency's creative vocabulary (format, hook tactic,
mechanic, scan path, proof, awareness stage) plus honest steal/avoid lines.
The output is a DRAFT — a human reviewer approves, corrects, or escalates
before anything reaches the library (see strategy/ad_card.py).

The system prompt is GENERATED from the taxonomy skill docs on every call
(strategy/taxonomy.py), so the analyzer's vocabulary can never drift from
the strategist's. The taxonomy content hash is stamped into every draft.

Intake accepts either a local image file or a Foreplay ad id — the Foreplay
path pulls brand, headline, and exact runtime from the API so the operator
never retypes (or mistypes) the proxy signal.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from strategy.ad_card import (
    drafts_dir,
    render_display,
    utc_now_iso,
    validate_card,
)
from strategy.llm import vision_complete
from strategy.taxonomy import (
    AWARENESS_STAGES,
    PRODUCT_ROLES,
    Taxonomy,
    load_taxonomy,
)

DEFAULT_MODEL = "claude-sonnet-4-6"

# Optional few-shot examples file, maintained by the strategist after the
# gold set exists (see references/swipe/gold/README.md). Appended verbatim.
EXAMPLES_FILE = Path("references/swipe/gold/examples.md")

AWARENESS_DEFINITIONS: dict[str, str] = {
    "unaware": "doesn't yet know they have the problem",
    "problem_aware": "feels the problem, doesn't know solutions exist",
    "solution_aware": "knows solutions exist, hasn't met this product",
    "product_aware": "knows this product, isn't convinced yet",
    "most_aware": "knows and wants it — needs a reason to act now",
}


def build_system_prompt(tax: Taxonomy, media_type: str = "static") -> str:
    """Generate the analyzer system prompt from the live taxonomy."""
    lines = [
        "You are an expert performance-marketing creative strategist analyzing "
        "competitor ads for an e-commerce ad agency. Your analysis is used ONLY to "
        "extract transferable mechanics — never to copy an ad. The agency's rule: "
        "steal the mechanic and structure, never the creator, exact copy, or "
        "visual identity.",
        "",
        "Analyze the provided ad image and return ONLY a valid JSON object with "
        "exactly these keys: brand, source_link, proxy_signal, media_type, format, "
        "hook_type, mechanic, secondary_mechanic, scan_path, proof_element, "
        "product_role, awareness_stage, why_it_works, cultural_note, steal, avoid, "
        "field_confidence, reasoning. No preamble, no markdown fences, no commentary.",
        "",
        f"media_type — always \"{media_type}\" for this ad.",
        "",
        "FIELD DEFINITIONS AND ALLOWED VALUES:",
        "",
        "format — the production structure of the ad. Choose ONE:",
    ]
    for e in tax.format_entries(media_type):
        lines.append(f"- {e.name}: {e.definition}")
    lines += [
        "- Other (name it in one or two words in parentheses) — use rarely, only "
        "when nothing above fits.",
        "",
        "hook_type — the strategic frame of the opening line/headline. Choose ONE:",
    ]
    for e in tax.hook_types:
        lines.append(f"- {e.name}: {e.definition}")
    lines += [
        "",
        "mechanic — the cognitive/emotional move that makes the ad land. Choose ONE "
        "primary:",
    ]
    for e in tax.mechanics:
        lines.append(f"- {e.name}: {e.definition}")
    lines += [
        "- Other (describe in 3-6 words) — use rarely.",
        "",
        "secondary_mechanic — mechanics often layer. If a second mechanic from the "
        "NAMED list above clearly reinforces the primary, name it; otherwise null. "
        "Never use Other here — if the reinforcing move isn't a named mechanic, "
        "output null. The primary shapes the concept architecture; the secondary "
        "adds depth.",
        "",
        "scan_path — ordered list of 2-5 elements describing where the eye travels, "
        "in order. Example: [\"headline\", \"receipt total\", \"product\", \"CTA\"]",
        "",
        "proof_element — what makes the claim believable, in one short phrase "
        "(e.g. \"itemized receipt with real prices\", \"1,400 five-star reviews badge\").",
        "",
        "product_role — ONE of: "
        + "; ".join(f"{k} ({v})" for k, v in PRODUCT_ROLES.items()) + ".",
        "",
        "awareness_stage — the customer awareness stage this ad targets. ONE of:",
    ]
    for key, label in AWARENESS_STAGES.items():
        lines.append(f"- {key} — {label}: {AWARENESS_DEFINITIONS[key]}")
    lines += [
        "",
        "why_it_works — the single strongest reason this ad persuades, max 40 words. "
        "Be specific, not generic. \"Clean design\" is not an answer; \"the receipt "
        "format makes the savings claim feel audited rather than advertised\" is.",
        "",
        "cultural_note — any meme format, platform-native convention, trend, or "
        "in-group signal the ad borrows (e.g. \"mimics iOS Notes app = personal "
        "confession energy\"). Write \"none\" if none.",
        "",
        "steal — what the agency should reuse: the mechanic, structure, scan path, "
        "or proof logic. One sentence.",
        "",
        "avoid — what must NOT be copied: the specific creator/person, exact copy "
        "lines, brand visual identity, or anything legally/ethically off-limits. "
        "One sentence. Always include at minimum: do not reuse the creator or "
        "exact copy.",
        "",
        "proxy_signal — repeat any performance evidence provided in the context "
        "(runtime, variation count); if none was provided, write \"unknown\".",
        "",
        "brand — the advertiser, from the context or visible in the ad. "
        "\"unknown\" if unclear.",
        "",
        "field_confidence — object rating your confidence for each of format, "
        "hook_type, mechanic, awareness_stage, product_role as \"high\", \"med\", "
        "or \"low\". Be honest — a low-confidence field routes to human review, "
        "which is the correct outcome when the ad is ambiguous. Never present a "
        "guess as a certainty.",
        "",
        "reasoning — object with one-line explanations for mechanic and "
        "awareness_stage only.",
        "",
        "GENERAL RULES:",
        "- Choose from the allowed values. Only use Other when nothing fits.",
        "- Judge the ad as a cold viewer scrolling a feed would experience it.",
        "- If text in the image is partially unreadable, analyze what is visible "
        "and lower your confidence accordingly.",
        "- Never output anything except the JSON object.",
    ]
    if EXAMPLES_FILE.exists():
        lines += ["", "EXAMPLES OF CORRECT ANALYSIS:", "",
                  EXAMPLES_FILE.read_text(encoding="utf-8").strip()]
    return "\n".join(lines)


def _parse_json_response(text: str) -> dict:
    """Robust JSON extraction — strips markdown fences, finds first {..} block."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"No JSON object in response: {text[:200]}")
    return json.loads(text[start:end + 1])


def _build_user_message(context: dict[str, str]) -> str:
    lines = ["Analyze this ad image."]
    provided = {k: v for k, v in context.items() if v}
    if provided:
        lines.append("")
        lines.append("Context provided by the operator (none of it is required):")
        for k, v in provided.items():
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


def analyze_image(
    image_path: Path,
    *,
    tax: Taxonomy | None = None,
    media_type: str = "static",
    model: str = DEFAULT_MODEL,
    brand: str = "",
    proxy_signal: str = "",
    source_link: str = "",
    extra_context: dict[str, str] | None = None,
    foreplay_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the vision analysis and return a draft payload.

    Payload shape (what the CLI prints as JSON and OpenClaw carries in-thread):
        card      — normalized field dict (may still contain flagged issues)
        display   — Slack-ready card text (⚠️ on low-confidence fields)
        issues    — validation problems that BLOCK saving until corrected
        warnings  — non-blocking normalization notes
        meta      — model, taxonomy_version, analyzed_at, image, foreplay

    Invalid JSON from the model is retried once; a second failure raises —
    per the workflow rule, the caller reports the error plainly and stops
    rather than fabricating a card.
    """
    tax = tax or load_taxonomy()
    system = build_system_prompt(tax, media_type)
    context = {
        "brand": brand,
        "proxy_signal": proxy_signal,
        "source_link": source_link,
        **(extra_context or {}),
    }
    user_msg = _build_user_message(context)

    raw = vision_complete(user_msg, str(image_path), system=system,
                          model=model, max_tokens=2048)
    try:
        data = _parse_json_response(raw)
    except (ValueError, json.JSONDecodeError):
        retry_msg = (user_msg + "\n\nYour previous response was not valid JSON. "
                     "Return ONLY the JSON object, nothing else.")
        raw = vision_complete(retry_msg, str(image_path), system=system,
                              model=model, max_tokens=2048)
        try:
            data = _parse_json_response(raw)
        except (ValueError, json.JSONDecodeError) as exc:
            raise RuntimeError(
                f"Model returned invalid JSON twice — not fabricating a card. "
                f"Last response started: {raw[:200]!r}") from exc

    data["media_type"] = media_type
    if brand:
        data["brand"] = brand
    if proxy_signal:
        data["proxy_signal"] = proxy_signal
    if source_link:
        data["source_link"] = source_link
    data.setdefault("source_link", "")

    result = validate_card(data, tax)
    return {
        "card": result.card,
        "display": render_display(result.card),
        "issues": result.issues,
        "warnings": result.warnings,
        "meta": {
            "model": model,
            "taxonomy_version": tax.version,
            "analyzed_at": utc_now_iso(),
            "image": str(image_path),
            "foreplay": foreplay_meta or {},
        },
    }


# ─── Intake: local image or Foreplay ad id ───────────────────────────────────


def _runtime_signal(started_running_ms: int, live: bool) -> str:
    """Human proxy signal from Foreplay's start timestamp — the longevity
    read the operator would otherwise eyeball and retype."""
    if not started_running_ms:
        return ""
    started = datetime.fromtimestamp(started_running_ms / 1000, tz=timezone.utc)
    days = max(0, (datetime.now(timezone.utc) - started).days)
    months = days / 30.4
    span = f"{days} days" if days < 60 else f"~{months:.0f} months"
    state = "still live" if live else "no longer live"
    return f"running {span} (since {started.date().isoformat()}), {state}"


def resolve_source(
    source: str,
    *,
    allow_video: bool = False,
    root: Path | None = None,
) -> tuple[Path, str, dict[str, Any], dict[str, str]]:
    """Turn the operator's input into (image_path, media_type, foreplay_meta,
    context) ready for analyze_image.

    Accepts a local image path, a bare Foreplay/Facebook ad id (long digit
    run), or a URL containing one. Foreplay video ads analyze the thumbnail
    and require allow_video=True so static-library scope stays a deliberate
    choice, not an accident.
    """
    p = Path(source)
    if p.exists() and p.suffix.lower() in (".jpg", ".jpeg", ".png"):
        return p, "static", {}, {}

    m = re.search(r"\d{10,}", source)
    if not m:
        raise ValueError(
            f"'{source}' is neither an existing image file nor contains an ad id. "
            "Pass a .jpg/.png path or a numeric Foreplay ad id / URL.")
    ad_id = m.group(0)

    from strategy.foreplay_client import download_asset, fetch_ad_by_id
    ad = fetch_ad_by_id(ad_id)
    if ad is None:
        raise ValueError(f"Foreplay has no ad with id {ad_id}")

    is_video = (ad.display_format == "video") or (bool(ad.video_url) and not ad.image_url)
    if is_video and not allow_video:
        raise ValueError(
            f"Ad {ad_id} is a VIDEO. The library's v1 scope is static ads — rerun "
            "with --allow-video to analyze its thumbnail frame as a video card.")

    asset_url = ad.image_url or ad.thumbnail_url or ad.mobile_screenshot
    if not asset_url:
        raise ValueError(f"Ad {ad_id} has no downloadable image asset")

    dest = drafts_dir(root) / f"foreplay-{ad_id}.jpg"
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_asset(asset_url, dest)

    # Foreplay's asset URLs don't reveal the real format — name the file by
    # its bytes, or the declared media type lies downstream (Anthropic 400s
    # on mismatch) and the library sidecar stores a wrong extension.
    from strategy.llm import sniff_image_mime
    mime = sniff_image_mime(dest.read_bytes()[:32])
    actual_ext = {"image/png": ".png", "image/jpeg": ".jpg"}.get(mime or "")
    if actual_ext is None:
        dest.unlink(missing_ok=True)
        raise ValueError(
            f"Foreplay asset for ad {ad_id} is {mime or 'not a recognized image'} — "
            "only PNG/JPEG ads are supported. Save the ad image manually and "
            "analyze the file instead.")
    if dest.suffix != actual_ext:
        corrected = dest.with_suffix(actual_ext)
        dest.replace(corrected)
        dest = corrected

    foreplay_meta = {
        "ad_id": ad.ad_id or ad_id,
        "foreplay_id": ad.foreplay_id,
        "brand": ad.name,
        "headline": ad.headline,
        "description": ad.description,
        "cta": ad.cta_title or ad.cta_type,
        "link_url": ad.link_url,
        "display_format": ad.display_format,
        "started_running": ad.started_running,
        "live": ad.live,
        "niches": ad.niches,
        "publisher_platform": ad.publisher_platform,
        "fetched_at": utc_now_iso(),
    }
    context = {
        "brand": ad.name,
        "proxy_signal": _runtime_signal(ad.started_running, ad.live),
        "source_link": ad.link_url,
        "headline": ad.headline,
        "description": (ad.description or "")[:300],
    }
    return dest, ("video" if is_video else "static"), foreplay_meta, context
