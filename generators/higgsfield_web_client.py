"""Higgsfield "web backend" client — hits the same internal API that
cloud.higgsfield.ai's UI uses, which is what the official Higgsfield MCP
server proxies behind the scenes.

Why this file exists separately from generators/higgsfield_client.py:
the public REST API at platform.higgsfield.ai (which the official `higgsfield`
CLI talks to) accepts model="nano_banana_2" in submissions but doesn't
actually route those to the real edit-capable backend — jobs queue but
never produce reference-faithful output. The edit-capable backend lives at
fnf.higgsfield.ai/jobs/v2/* under a different auth scheme (Clerk JWT
session cookies), and that's what produces the near-perfect output we
saw via the MCP test on 2026-05-22.

Auth model (two cookies from cloud.higgsfield.ai):
  - __session  →  short-lived JWT (~1 minute TTL). Set as HIGGSFIELD_JWT
                   in .env for fast-path. Auto-refreshed from __client.
  - __client   →  long-lived (~7 days). Set as HIGGSFIELD_CLERK_CLIENT.
                   Used to discover the active session id and mint fresh
                   JWTs via Clerk's /v1/client/sessions/{sid}/tokens.

Refresh flow (cribbed from Hikhakk/higgsfield-mcp-unified):
  GET  https://clerk.higgsfield.ai/v1/client          → { last_active_session_id }
  POST https://clerk.higgsfield.ai/v1/client/sessions/{sid}/tokens  → { jwt }
A fresh JWT lasts ~60s; the cached value is reused until ~10s before expiry.

Image generation flow:
  POST https://fnf.higgsfield.ai/jobs/v2/nano_banana_flash
    Authorization: Bearer <jwt>
    body: { params: { prompt, aspect_ratio, resolution, batch_size,
                       input_image_urls: [URL, URL, ...] },
            use_unlim: false, use_free_gens: false }
  → { request_id, ... }
Polling: GET https://fnf.higgsfield.ai/jobs?size=100, filter by request_id
in the response's jobs list, extract result URL from results/images/outputs.

What's reused from the existing higgsfield_client.py:
  - upload_image() to host reference + product images at the
    platform.higgsfield.ai/files presigned-URL store. The fnf endpoint
    accepts arbitrary public URLs in input_image_urls, so we just feed it
    the CloudFront URLs that come back from upload.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

# ─── Constants (reverse-engineered from Hikhakk's open-source MCP server) ────

CLERK_BASE = "https://clerk.higgsfield.ai"
FNF_BASE = "https://fnf.higgsfield.ai"

CLERK_VERSION_PARAMS = {
    "__clerk_api_version": "2024-10-01",
    "_clerk_js_version": "5.95.0",
}

COMMON_HEADERS = {
    "Accept": "*/*",
    "Origin": "https://cloud.higgsfield.ai",
    "Referer": "https://cloud.higgsfield.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Minimum lifetime to consider a cached JWT still usable. Clerk JWTs are
# ~60s TTL; we refresh 10s early to avoid races.
JWT_REFRESH_MARGIN_S = 10

# How long any one HTTP call can hang. Generation jobs themselves are
# polled separately and have a longer overall timeout.
HTTP_TIMEOUT_S = 60


# ─── Errors ──────────────────────────────────────────────────────────────────


class HiggsfieldWebError(RuntimeError):
    """Raised for non-recoverable HF web backend errors (auth, validation,
    NSFW rejection, job failure)."""


class HiggsfieldAuthError(HiggsfieldWebError):
    """Specifically: Clerk auth failed. Distinct error class so callers
    can surface an actionable "re-paste your cookies" message instead of
    a generic API error."""


# ─── JWT cache + refresh ─────────────────────────────────────────────────────


@dataclass
class _CachedJWT:
    jwt: str
    expires_at: float  # unix timestamp


_jwt_lock = threading.Lock()
_jwt_cache: _CachedJWT | None = None
_session_id_cache: str | None = None


def _decode_jwt_exp(jwt: str) -> float:
    """Best-effort: decode the JWT payload to extract its `exp` claim.

    Returns a unix timestamp. If the JWT is malformed or has no exp,
    returns 0 (forces immediate refresh on next use). We don't verify the
    signature — Clerk JWTs are server-side validated; we just want to know
    when to refresh."""
    try:
        # JWT format: <header>.<payload>.<signature>. We want the payload.
        parts = jwt.split(".")
        if len(parts) < 2:
            return 0.0
        payload_b64 = parts[1]
        # Pad to multiple of 4 for base64 decoding
        padding = "=" * (-len(payload_b64) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(payload_b64 + padding).decode()
        )
        return float(payload.get("exp", 0))
    except Exception:
        return 0.0


def _read_client_cookie() -> str:
    """Read the __client cookie from env (HIGGSFIELD_CLERK_CLIENT).

    Raises HiggsfieldAuthError with extraction instructions if unset."""
    cookie = os.environ.get("HIGGSFIELD_CLERK_CLIENT", "").strip()
    if not cookie or cookie.startswith("your_"):
        raise HiggsfieldAuthError(
            "HIGGSFIELD_CLERK_CLIENT is not set in .env. "
            "Extract it from https://cloud.higgsfield.ai (open dev tools, "
            "Application > Cookies > cloud.higgsfield.ai, copy the value "
            "of the `__client` cookie) and paste it into .env. The cookie "
            "lasts ~7 days. See docs/hf-web-engine.md for details."
        )
    return cookie


def _read_env_jwt() -> str | None:
    """Read HIGGSFIELD_JWT from env if set. Used as a fast-path before
    we try refreshing from the __client cookie — operator can paste a
    fresh JWT directly to skip the Clerk roundtrip."""
    jwt = os.environ.get("HIGGSFIELD_JWT", "").strip()
    if not jwt or jwt.startswith("your_"):
        return None
    return jwt


def _discover_session_id(client: httpx.Client, client_cookie: str) -> str:
    """GET /v1/client → find the active session id.

    Clerk's /v1/client returns a `response.last_active_session_id` for
    accounts with exactly one active session (the common case). For
    multi-session accounts it also returns a `sessions[]` list; we fall
    back to the first session that's active or unmarked."""
    url = f"{CLERK_BASE}/v1/client"
    r = client.get(
        url,
        params=CLERK_VERSION_PARAMS,
        headers=COMMON_HEADERS,
        cookies={"__client": client_cookie},
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 401 or r.status_code == 403:
        raise HiggsfieldAuthError(
            f"Clerk session discovery failed ({r.status_code}). The "
            f"HIGGSFIELD_CLERK_CLIENT cookie has likely expired (~7 day "
            f"lifetime). Re-extract from cloud.higgsfield.ai's __client "
            f"cookie and re-paste into .env."
        )
    if r.status_code != 200:
        raise HiggsfieldWebError(
            f"GET {url} returned {r.status_code}: {r.text[:200]}"
        )
    try:
        payload = r.json()
    except ValueError as e:
        raise HiggsfieldWebError(
            f"GET {url} returned non-JSON: {r.text[:200]}"
        ) from e
    response = payload.get("response") or {}
    sid = response.get("last_active_session_id")
    if sid:
        return str(sid)
    # Fallback: iterate sessions[]
    for s in response.get("sessions") or []:
        if not isinstance(s, dict):
            continue
        status = s.get("status")
        if status in (None, "active"):
            sid_alt = s.get("id")
            if isinstance(sid_alt, str):
                return sid_alt
    raise HiggsfieldAuthError(
        f"Clerk session discovery succeeded but no active session id "
        f"was found in the response. Likely your __client cookie is for "
        f"a logged-out browser. Log into cloud.higgsfield.ai, re-extract "
        f"the cookie, and try again."
    )


def _mint_jwt(client: httpx.Client, client_cookie: str, sid: str) -> str:
    """POST /v1/client/sessions/{sid}/tokens → fresh JWT."""
    url = f"{CLERK_BASE}/v1/client/sessions/{sid}/tokens"
    r = client.post(
        url,
        params=CLERK_VERSION_PARAMS,
        headers=COMMON_HEADERS,
        cookies={"__client": client_cookie},
        content="",  # empty body, matching the upstream impl
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 401 or r.status_code == 403:
        raise HiggsfieldAuthError(
            f"Clerk JWT minting failed ({r.status_code}) for session "
            f"{sid}. Your __client cookie may have just expired. "
            f"Re-extract from cloud.higgsfield.ai and update .env."
        )
    if r.status_code != 200:
        raise HiggsfieldWebError(
            f"POST {url} returned {r.status_code}: {r.text[:200]}"
        )
    try:
        body = r.json()
    except ValueError as e:
        raise HiggsfieldWebError(
            f"POST {url} returned non-JSON: {r.text[:200]}"
        ) from e
    jwt = body.get("jwt") if isinstance(body, dict) else None
    if not isinstance(jwt, str) or not jwt:
        raise HiggsfieldWebError(
            f"POST {url} returned no jwt field: {body!r}"
        )
    return jwt


def _get_fresh_jwt(force_refresh: bool = False) -> str:
    """Return a non-expired JWT — refresh from __client cookie if needed.

    Order of attempts:
      1. If HIGGSFIELD_JWT env var is set and not expired, return it as-is.
         (Lets the operator paste a fresh JWT directly for one-off use.)
      2. Use cached JWT if we have one and it's not within
         JWT_REFRESH_MARGIN_S of expiry.
      3. Mint a new JWT via Clerk using the __client cookie.

    Thread-safe via a module-level lock so concurrent generations don't
    each fire their own refresh."""
    global _jwt_cache, _session_id_cache
    now = time.time()

    # Path 1: env-supplied JWT (operator pasted a fresh one)
    if not force_refresh:
        env_jwt = _read_env_jwt()
        if env_jwt is not None:
            exp = _decode_jwt_exp(env_jwt)
            if exp - now > JWT_REFRESH_MARGIN_S:
                return env_jwt
            # else: expired, fall through to refresh

    with _jwt_lock:
        # Path 2: cached JWT
        if (
            not force_refresh
            and _jwt_cache is not None
            and _jwt_cache.expires_at - now > JWT_REFRESH_MARGIN_S
        ):
            return _jwt_cache.jwt

        # Path 3: refresh from __client cookie via Clerk
        client_cookie = _read_client_cookie()
        with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
            sid = _session_id_cache
            if sid is None or force_refresh:
                sid = _discover_session_id(client, client_cookie)
                _session_id_cache = sid
            try:
                jwt = _mint_jwt(client, client_cookie, sid)
            except HiggsfieldWebError:
                # Session ID may have rotated — retry once with fresh sid.
                sid = _discover_session_id(client, client_cookie)
                _session_id_cache = sid
                jwt = _mint_jwt(client, client_cookie, sid)

        exp = _decode_jwt_exp(jwt) or (now + 50.0)  # fallback ~50s if no exp
        _jwt_cache = _CachedJWT(jwt=jwt, expires_at=exp)
        return jwt


# ─── Image-edit submission ───────────────────────────────────────────────────


def _auth_headers() -> dict[str, str]:
    jwt = _get_fresh_jwt()
    return {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        **COMMON_HEADERS,
    }


def submit_nano_banana_edit(
    *,
    prompt: str,
    input_image_urls: list[str],
    aspect_ratio: str = "1:1",
    resolution: str = "1k",
    batch_size: int = 1,
    seed: int | None = None,
    enhance_prompt: bool = False,
) -> str:
    """Submit a nano_banana_flash edit job. Returns the request_id.

    `input_image_urls` is the list of input images (reference first, product
    second by convention — same ordering that worked in the MCP test). Up
    to 16 URLs supported by the backend.

    Returns the request_id immediately. Callers should then poll via
    `wait_for_result_url(request_id)` to get the final image URL."""
    if not input_image_urls:
        raise ValueError("input_image_urls must contain at least one URL")
    if len(input_image_urls) > 16:
        raise ValueError(
            f"input_image_urls capped at 16, got {len(input_image_urls)}"
        )

    url = f"{FNF_BASE}/jobs/v2/nano_banana_flash"
    params: dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "batch_size": batch_size,
        "input_image_urls": input_image_urls,
        "enhance_prompt": enhance_prompt,
    }
    if seed is not None:
        params["seed"] = seed
    body = {"params": params, "use_unlim": False, "use_free_gens": False}

    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        # Try once with cached JWT, retry once on 401 with forced refresh.
        for attempt in range(2):
            r = client.post(url, json=body, headers=_auth_headers())
            if r.status_code == 401 and attempt == 0:
                _get_fresh_jwt(force_refresh=True)
                continue
            if r.status_code >= 400:
                raise HiggsfieldWebError(
                    f"POST {url} returned {r.status_code}: {r.text[:400]}"
                )
            break
        try:
            payload = r.json()
        except ValueError as e:
            raise HiggsfieldWebError(
                f"POST {url} returned non-JSON: {r.text[:200]}"
            ) from e

    request_id = (
        payload.get("request_id")
        or payload.get("id")
        or (payload.get("jobs") or [{}])[0].get("request_id")
    )
    if not request_id:
        raise HiggsfieldWebError(
            f"submit returned no request_id: {payload!r}"
        )
    return str(request_id)


# ─── Polling + result extraction ─────────────────────────────────────────────


_TERMINAL = {"completed", "failed", "nsfw", "cancelled", "rejected"}


def _find_job_by_request_id(
    client: httpx.Client, request_id: str
) -> dict | None:
    """GET /jobs?size=100 and find the entry whose request_id matches.

    Higgsfield's /jobs endpoint returns recent jobs (up to size). We
    don't have a per-request status URL the way platform.higgsfield.ai
    does, so we have to filter the list."""
    r = client.get(
        f"{FNF_BASE}/jobs",
        params={"size": 100},
        headers=_auth_headers(),
        timeout=HTTP_TIMEOUT_S,
    )
    if r.status_code == 401:
        _get_fresh_jwt(force_refresh=True)
        r = client.get(
            f"{FNF_BASE}/jobs",
            params={"size": 100},
            headers=_auth_headers(),
            timeout=HTTP_TIMEOUT_S,
        )
    if r.status_code >= 400:
        raise HiggsfieldWebError(
            f"GET /jobs returned {r.status_code}: {r.text[:200]}"
        )
    try:
        payload = r.json()
    except ValueError as e:
        raise HiggsfieldWebError(f"GET /jobs returned non-JSON") from e
    items = payload.get("items") or payload.get("jobs") or []
    for item in items:
        if not isinstance(item, dict):
            continue
        rid = item.get("request_id") or item.get("id")
        if str(rid) == str(request_id):
            return item
    return None


def _extract_result_url(job: dict) -> str:
    """Pull the image URL out of a completed job entry.

    HF's job shape uses one of: `results.rawUrl`, `images[].url`,
    `outputs[].url`, or a flat `result_url`. We try them in order."""
    results = job.get("results")
    if isinstance(results, dict):
        for k in ("rawUrl", "raw_url", "url"):
            v = results.get(k)
            if isinstance(v, str) and v:
                return v
    if isinstance(results, list):
        for r in results:
            if isinstance(r, dict):
                for k in ("rawUrl", "raw_url", "url"):
                    v = r.get(k)
                    if isinstance(v, str) and v:
                        return v
    for collection_key in ("images", "outputs"):
        coll = job.get(collection_key)
        if isinstance(coll, list):
            for entry in coll:
                if isinstance(entry, dict):
                    for k in ("url", "rawUrl", "raw_url"):
                        v = entry.get(k)
                        if isinstance(v, str) and v:
                            return v
                elif isinstance(entry, str):
                    return entry
    flat = job.get("result_url")
    if isinstance(flat, str) and flat:
        return flat
    raise HiggsfieldWebError(
        f"Could not extract result URL from completed job: keys={list(job.keys())}"
    )


def wait_for_result_url(
    request_id: str,
    *,
    timeout_s: int = 600,
    poll_interval_s: int = 3,
) -> str:
    """Poll until the given job reaches a terminal state, return its
    result URL. Raises HiggsfieldWebError on failure / nsfw / timeout."""
    deadline = time.time() + timeout_s
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as client:
        while True:
            job = _find_job_by_request_id(client, request_id)
            if job is None:
                # Just submitted — likely not in the recent-jobs list yet.
                if time.time() >= deadline:
                    raise HiggsfieldWebError(
                        f"Timed out waiting for request_id={request_id} "
                        f"to appear in /jobs after {timeout_s}s."
                    )
                time.sleep(poll_interval_s)
                continue
            status = str(job.get("status") or "").lower()
            if status in _TERMINAL:
                if status == "completed":
                    return _extract_result_url(job)
                raise HiggsfieldWebError(
                    f"Job {request_id} ended with status={status}: "
                    f"{job.get('error') or job}"
                )
            if time.time() >= deadline:
                raise HiggsfieldWebError(
                    f"Timed out waiting for request_id={request_id} after "
                    f"{timeout_s}s (last status: {status})."
                )
            time.sleep(poll_interval_s)


def submit_and_wait(
    *,
    prompt: str,
    input_image_urls: list[str],
    aspect_ratio: str = "1:1",
    resolution: str = "1k",
    timeout_s: int = 600,
    seed: int | None = None,
) -> str:
    """Convenience: submit a job and block until the result URL is ready."""
    request_id = submit_nano_banana_edit(
        prompt=prompt,
        input_image_urls=input_image_urls,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        seed=seed,
    )
    return wait_for_result_url(request_id, timeout_s=timeout_s)


def download_result(url: str, out_path: Path) -> Path:
    """Save the result image (Higgsfield CDN URL) to a local file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as c:
        r = c.get(url)
        r.raise_for_status()
        out_path.write_bytes(r.content)
    return out_path
