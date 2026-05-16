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
    """
    url = f"{HF_BASE_URL}{endpoint if endpoint.startswith('/') else '/' + endpoint}"
    with httpx.Client(timeout=HF_REQUEST_TIMEOUT) as client:
        try:
            r = client.post(url, json=body, headers=_headers())
        except httpx.HTTPError as e:
            raise HiggsfieldError(f"POST {url} failed: {e}") from e

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
        if not with_polling or "request_id" not in response:
            return response
        return _poll(client, response["request_id"])


def _poll(client: httpx.Client, request_id: str) -> dict:
    """Poll /requests/{request_id}/status until status is terminal."""
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
        status = data.get("status")
        if status in ("completed", "failed", "nsfw"):
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
    """
    body: dict = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "quality": quality,
    }
    if soul_id:
        body["soul_id"] = soul_id
    if reference_image_url:
        body["image_reference_url"] = reference_image_url
        body["image_reference_type"] = "composition"
    return _subscribe(SOUL_TEXT_TO_IMAGE, body)


def extract_result_urls(response: dict) -> list[str]:
    """Pull image URLs from a completed soul_2 response.

    Higgs Field response shapes seen in the wild (handled defensively):
      response["jobs"][i]["results"]["raw"]["url"]
      response["results"][i]["url"]
      response["result_url"]
    """
    urls: list[str] = []
    # Shape 1: jobs[].results.raw.url
    for job in response.get("jobs", []) or []:
        url = (
            ((job.get("results") or {}).get("raw") or {}).get("url")
            or (job.get("results") or {}).get("rawUrl")
            or job.get("url")
        )
        if url:
            urls.append(url)
    # Shape 2: results[].url
    if not urls:
        for res in response.get("results", []) or []:
            if isinstance(res, dict) and res.get("url"):
                urls.append(res["url"])
    # Shape 3: flat result_url
    if not urls and response.get("result_url"):
        urls.append(response["result_url"])
    # Shape 4: the MCP returned `results.rawUrl` for soul_2 jobs we generated
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
        raise HiggsfieldError(
            f"Soul generation completed but no result URL found. Response keys: {list(response.keys())}"
        )
    return download_image(urls[0], out_path)
