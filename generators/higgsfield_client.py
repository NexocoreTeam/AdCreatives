"""Higgs Field REST API client (lightweight wrapper, no SDK dependency).

Talks to https://platform.higgsfield.ai using the same auth pattern as the
official @higgsfield/client v2 SDK. Stripped down to just what our remix
pipeline needs:

  - generate_soul_image()    → soul_2 (text-to-image with trained soul_id,
                                optional reference image for composition)
  - upload_image()           → presigned-URL upload → media_id
  - download_result()        → fetch the final PNG to disk

Auth — set ONE of these in .env (or environment):

  HF_CREDENTIALS=KEY_ID:KEY_SECRET     (preferred, single field)
  # or
  HF_API_KEY=KEY_ID
  HF_API_SECRET=KEY_SECRET

Get keys at https://platform.higgsfield.ai (Settings → API Keys, or
equivalent). The MCP OAuth session token is *different* from a REST API
key — they don't interchange.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx

HF_BASE_URL = "https://platform.higgsfield.ai"
HF_REQUEST_TIMEOUT = 120          # seconds for any single HTTP call
HF_POLL_INTERVAL = 2              # seconds between status polls
HF_MAX_POLL_TIME = 600            # 10 min total for a single generation
HF_USER_AGENT = "adcreatives-py/0.1"

# Endpoints — derived from the @higgsfield/client v2 SDK schema-loader pattern.
# These may need adjustment after the first real call; the SDK loads endpoints
# dynamically from a server-side schema so we're pinning them here statically.
SOUL_TEXT_TO_IMAGE = "/v1/text2image/soul"
MEDIA_UPLOAD = "/v1/media/upload"


# ─── Auth + transport ───────────────────────────────────────────────────────


def _get_credentials() -> str:
    """Read HF credentials from env. Returns 'KEY_ID:KEY_SECRET'.

    Raises with a clear setup hint if missing or malformed.
    """
    creds = os.environ.get("HF_CREDENTIALS", "").strip()
    if not creds:
        key = os.environ.get("HF_API_KEY", "").strip()
        secret = os.environ.get("HF_API_SECRET", "").strip()
        if key and secret:
            creds = f"{key}:{secret}"
    if not creds or ":" not in creds:
        raise RuntimeError(
            "Higgs Field credentials not configured. Set HF_CREDENTIALS=KEY_ID:KEY_SECRET "
            "in .env (or HF_API_KEY + HF_API_SECRET separately). "
            "Generate keys at https://platform.higgsfield.ai — the MCP OAuth session "
            "token is not a REST API key."
        )
    return creds


def _headers() -> dict:
    creds = _get_credentials()
    return {
        "Authorization": f"Key {creds}",
        "Content-Type": "application/json",
        "User-Agent": HF_USER_AGENT,
    }


# ─── Job submission + polling ────────────────────────────────────────────────


class HiggsfieldError(RuntimeError):
    """Raised for non-recoverable Higgs Field API errors (auth, validation, NSFW, etc.)."""


def _subscribe(endpoint: str, body: dict, with_polling: bool = True) -> dict:
    """POST to `endpoint`, optionally poll until terminal status. Returns the final response dict.

    Maps Higgs Field's `status` enum:
      queued, in_progress  → continue polling
      completed            → return (success)
      failed, nsfw         → return (caller checks status)

    Handles HF's 4-concurrent-request cap by sleeping and retrying up to
    3 times with backoff. Server-side job slots free up as previous jobs
    complete, so a short wait + retry usually unsticks a queued run.
    """
    url = f"{HF_BASE_URL}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    with httpx.Client(timeout=HF_REQUEST_TIMEOUT) as client:
        # Submit POST with retries for the concurrent-limit case. Each
        # backoff doubles roughly. HF's slots free up as previous jobs in
        # the same account finish polling.
        max_concurrent_retries = 3
        for attempt in range(max_concurrent_retries + 1):
            try:
                r = client.post(url, json=body, headers=_headers())
            except httpx.HTTPError as e:
                raise HiggsfieldError(f"POST {url} failed: {e}") from e

            # Concurrent-limit 400 → sleep + retry, don't raise yet.
            if (
                r.status_code == 400
                and "concurrent" in r.text.lower()
                and attempt < max_concurrent_retries
            ):
                wait_s = 10 * (attempt + 1)  # 10, 20, 30 seconds
                print(
                    f"  [hf] concurrent-request cap hit ({r.text[:120]}). "
                    f"Sleeping {wait_s}s then retrying (attempt "
                    f"{attempt + 2}/{max_concurrent_retries + 1})...",
                    flush=True,
                )
                time.sleep(wait_s)
                continue

            break  # any non-concurrent response, or final retry exhausted

        if r.status_code == 401:
            raise HiggsfieldError(
                "Higgs Field auth failed (401). Check HF_CREDENTIALS is "
                "'KEY_ID:KEY_SECRET' and the key is still valid."
            )
        if r.status_code == 403:
            raise HiggsfieldError(
                "Higgs Field 403 — likely out of credits. Top up at "
                "https://platform.higgsfield.ai/billing"
            )
        if r.status_code >= 400:
            raise HiggsfieldError(
                f"POST {url} returned {r.status_code}: {r.text[:400]}"
            )

        response = r.json()
        if not with_polling:
            return response
        # HF's POST response uses `id` for the request identifier in the
        # current API; older shapes used `request_id`. Accept both — if
        # neither is present we can't poll, so we return as-is and the
        # caller will fail at the URL-extraction step.
        request_id = response.get("id") or response.get("request_id")
        if not request_id:
            return response
        return _poll(client, request_id)


_TERMINAL_JOB_STATUSES = {"completed", "failed", "nsfw"}


def _poll(client: httpx.Client, request_id: str) -> dict:
    """Poll /requests/{request_id}/status until every job inside reaches a
    terminal status.

    HF's current response shape places `status` on each entry in `jobs[]`
    rather than at the request root. Earlier shapes used a top-level
    `status` field; we honor both to stay forward/back-compatible:

      - If `jobs[]` exists: terminal when EVERY job's status is in
        {completed, failed, nsfw}.
      - Otherwise: terminal when the top-level `status` is in that set.

    Polling without inspecting jobs[] was the previous bug: the request
    has no top-level status, so the loop would have polled forever — but
    even worse, `_subscribe` was skipping polling entirely because it
    checked `"request_id" not in response` and the current API uses `id`."""
    start = time.time()
    poll_url = f"{HF_BASE_URL}/requests/{request_id}/status"
    while True:
        if time.time() - start > HF_MAX_POLL_TIME:
            raise HiggsfieldError(
                f"Higgs Field polling exceeded {HF_MAX_POLL_TIME}s for {request_id}"
            )
        try:
            r = client.get(poll_url, headers=_headers())
        except httpx.HTTPError as e:
            # transient — retry
            time.sleep(HF_POLL_INTERVAL)
            continue

        if r.status_code >= 500:
            # server hiccup — retry
            time.sleep(HF_POLL_INTERVAL)
            continue
        if r.status_code >= 400:
            raise HiggsfieldError(
                f"GET {poll_url} returned {r.status_code}: {r.text[:400]}"
            )

        data = r.json()

        # New shape: check jobs[].status. Request is done when every job
        # reaches a terminal state.
        jobs = data.get("jobs", []) or []
        if jobs and all(isinstance(j, dict) for j in jobs):
            job_statuses = [(j.get("status") or "").lower() for j in jobs]
            if all(s in _TERMINAL_JOB_STATUSES for s in job_statuses):
                return data
        else:
            # Legacy shape: top-level status.
            status = (data.get("status") or "").lower()
            if status in _TERMINAL_JOB_STATUSES:
                return data

        # queued / in_progress / anything else — keep polling
        time.sleep(HF_POLL_INTERVAL)


# ─── Public API ──────────────────────────────────────────────────────────────


def generate_soul_image(
    *,
    soul_id: str | None = None,
    prompt: str,
    reference_image_url: str | None = None,
    aspect_ratio: str = "1:1",
    quality: str = "2k",
) -> dict:
    """Generate an image via soul_2.

    Pass `soul_id` for identity-locked generation (trained Soul Character).
    Pass `reference_image_url` for image-to-image / composition reference.
    Either or both can be used; with neither it's pure text-to-image.

    Returns the full response dict — call `extract_result_urls(response)` to
    pull the rendered image URLs.

    Wire-shape note: the REST endpoint expects all generation parameters
    nested under a top-level `params` key, with v1 vocabulary:
      - `width_and_height` as an enum (e.g. SQUARE_2048x2048) rather than
        aspect_ratio + quality
      - `batch_size` enum for count
    The MCP server translates "aspect_ratio + quality" to this v1 shape;
    we do that translation here for direct REST.
    """
    params: dict = {
        "model": "soul_2",
        "prompt": prompt,
        "width_and_height": _v1_size_enum(aspect_ratio, quality),
        "batch_size": 1,
        "quality": _v1_quality_enum(quality),
    }
    if soul_id:
        params["soul_id"] = soul_id
    if reference_image_url:
        params["medias"] = [
            {"value": reference_image_url, "role": "image"}
        ]
    return _subscribe(SOUL_TEXT_TO_IMAGE, {"params": params})


def _v1_size_enum(aspect_ratio: str, quality: str) -> str:
    """Map (aspect_ratio, quality) → Higgs Field v1 `width_and_height` enum.

    Valid v1 values per the API's 422 reply (literal_error):
      1152x2048, 2048x1152, 2048x1536, 1536x2048, 1344x2016, 2016x1344,
      960x1696, 1536x1536, 1536x1152, 1696x960, 1152x1536, 1088x1632,
      1632x1088, 1120x1680, 1680x1120, 2048x2048
    """
    q = (quality or "").lower()
    hi = not q.startswith("1")  # treat 1k/lower as small, 2k/higher as large
    ar = (aspect_ratio or "1:1").strip()
    if ar == "1:1":
        return "2048x2048" if hi else "1536x1536"
    if ar == "9:16":
        return "1152x2048"
    if ar == "16:9":
        return "2048x1152"
    if ar == "3:4":
        return "1536x2048"
    if ar == "4:3":
        return "2048x1536"
    if ar == "2:3":
        return "1344x2016"
    if ar == "3:2":
        return "2016x1344"
    # fallback to square
    return "2048x2048" if hi else "1536x1536"


def _v1_quality_enum(quality: str) -> str:
    """Map our quality strings to HF v1 quality enum.

    Per the API's 422 reply, v1 quality is video-style: '720p' or '1080p'.
    Our 1k/1.5k/lower maps to 720p; 2k and above maps to 1080p.
    """
    q = (quality or "").lower()
    if q in ("720p", "basic", "1k"):
        return "720p"
    return "1080p"


def extract_result_urls(response: dict) -> list[str]:
    """Pull image URLs from a completed soul_2 / nano_banana_2 response.

    The current HF REST shape (confirmed by dumping a real polled response
    on 2026-05-16) returns:

        {
          "status": "completed",
          "request_id": "...",
          "status_url": "...",
          "cancel_url": "...",
          "images": [ { "url": "https://..." }, ... ]
        }

    Earlier shapes are kept as defensive fallbacks in case HF rolls back
    or returns a different envelope for some job types.
    """
    urls: list[str] = []

    # Shape 1 (CURRENT API): images[].url — this is what we actually get
    for img in response.get("images", []) or []:
        if isinstance(img, dict) and img.get("url"):
            urls.append(img["url"])
        elif isinstance(img, str):  # defensive: bare URL strings
            urls.append(img)
    if urls:
        return urls

    # Shape 2 (job-list view from `higgsfield generate list`): jobs[].result_url
    for job in response.get("jobs", []) or []:
        if not isinstance(job, dict):
            continue
        url = (
            job.get("result_url")
            or ((job.get("results") or {}).get("raw") or {}).get("url")
            or (job.get("results") or {}).get("rawUrl")
            or job.get("url")
        )
        if url:
            urls.append(url)
    if urls:
        return urls

    # Shape 3 (legacy): results[].url
    for res in response.get("results", []) or []:
        if isinstance(res, dict) and res.get("url"):
            urls.append(res["url"])
    if urls:
        return urls

    # Shape 4 (legacy): flat result_url at the request root
    if response.get("result_url"):
        urls.append(response["result_url"])

    # Shape 5 (legacy MCP): results.rawUrl
    if not urls and isinstance(response.get("results"), dict):
        raw = response["results"].get("rawUrl")
        if raw:
            urls.append(raw)
    return urls


def download_image(url: str, out_path: Path) -> Path:
    """Fetch a Higgs Field result URL to local disk."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=HF_REQUEST_TIMEOUT) as c:
        r = c.get(url)
        r.raise_for_status()
        out_path.write_bytes(r.content)
    return out_path


# ─── Convenience: end-to-end "generate and save" ─────────────────────────────


def soul_generate_and_save(
    *,
    soul_id: str | None,
    prompt: str,
    out_path: Path,
    reference_image_url: str | None = None,
    aspect_ratio: str = "1:1",
    quality: str = "2k",
) -> Path:
    """Submit a soul_2 job, poll to completion, download the result.

    Returns the local path of the saved PNG. Raises HiggsfieldError on
    any non-terminal failure or NSFW rejection.
    """
    response = generate_soul_image(
        soul_id=soul_id,
        prompt=prompt,
        reference_image_url=reference_image_url,
        aspect_ratio=aspect_ratio,
        quality=quality,
    )
    status = response.get("status")
    if status == "failed":
        raise HiggsfieldError(
            f"Soul generation failed: {response.get('error') or response.get('detail') or response}"
        )
    if status == "nsfw":
        raise HiggsfieldError("Soul generation rejected for NSFW content.")

    urls = extract_result_urls(response)
    if not urls:
        # Dump the response to disk for triage when extraction fails. Without
        # this, all we'd see is "no result URL found" without knowing what
        # shape HF actually returned — making it impossible to fix the
        # extractor when the API drifts.
        import json as _json
        from datetime import datetime as _dt
        debug_path = Path(f".tmp_hf_response_{_dt.now().strftime('%Y%m%d_%H%M%S')}.json")
        try:
            debug_path.write_text(_json.dumps(response, indent=2, default=str), encoding="utf-8")
            hint = f" Full response dumped to {debug_path}."
        except Exception:
            hint = ""
        # Also include the jobs[] structure inline so common cases are
        # diagnosable from the error message alone.
        jobs = response.get("jobs", []) or []
        jobs_summary = ""
        if jobs:
            jobs_summary = (
                f" jobs[0] keys: {list(jobs[0].keys()) if isinstance(jobs[0], dict) else type(jobs[0]).__name__}"
                f"  jobs[0].status: {jobs[0].get('status') if isinstance(jobs[0], dict) else 'n/a'}"
            )
        raise HiggsfieldError(
            f"Soul generation completed but no result URL found. "
            f"Response keys: {list(response.keys())}.{jobs_summary}{hint}"
        )
    return download_image(urls[0], out_path)
