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

# We use curl_cffi (not httpx) for ALL calls to clerk.higgsfield.ai and
# fnf.higgsfield.ai. Reason: both sit behind Cloudflare bot protection,
# which rejects plain Python TLS fingerprints with a 403 + "Just a moment..."
# challenge page. curl_cffi with impersonate="chrome120" emits the exact
# JA3 + HTTP/2 frame ordering Chrome does, which Cloudflare accepts. This
# is the same trick the Hikhakk reference implementation uses; verified
# empirically against a 403 we hit without it on 2026-05-22.
try:
    from curl_cffi import requests as _impersonate_requests
except ImportError as e:
    raise ImportError(
        "curl_cffi is required for the hf-web engine (Cloudflare bypass on "
        "fnf.higgsfield.ai). Install it with:\n"
        "  py -3.14 -m pip install curl_cffi"
    ) from e

# httpx is still used for the direct CDN download at the end (no Cloudflare
# on the result-URL bucket).
import httpx

# Chrome version we impersonate. Bumped from chrome120 to chrome131 on
# 2026-05-22 after Higgsfield rolled out DataDome (separate from
# Cloudflare). chrome131 matches the TLS + HTTP/2 fingerprint of a
# late-2024 Chrome which the user's actual browser is closer to.
_IMPERSONATE = "chrome131"

# ─── Constants (reverse-engineered from Hikhakk's open-source MCP server) ────

CLERK_BASE = "https://clerk.higgsfield.ai"
FNF_BASE = "https://fnf.higgsfield.ai"

CLERK_VERSION_PARAMS = {
    "__clerk_api_version": "2024-10-01",
    "_clerk_js_version": "5.95.0",
}

COMMON_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Origin": "https://cloud.higgsfield.ai",
    "Referer": "https://cloud.higgsfield.ai/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    # Full set of Chrome client-hint headers. DataDome cross-checks these
    # against the JA3 fingerprint — having the TLS look like Chrome but
    # the headers look stripped-down is a classic bot tell.
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
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


def _read_datadome_cookie() -> str:
    """Read HIGGSFIELD_DATADOME from env. Required for fnf.higgsfield.ai
    requests — DataDome's bot protection rejects requests that lack a
    valid `datadome` cookie with a 403 + "Please enable JS" page even
    after the Cloudflare TLS check passes."""
    cookie = os.environ.get("HIGGSFIELD_DATADOME", "").strip()
    if not cookie or cookie.startswith("your_"):
        raise HiggsfieldAuthError(
            "HIGGSFIELD_DATADOME is not set in .env. fnf.higgsfield.ai sits "
            "behind DataDome bot protection which rejects requests lacking "
            "this cookie. Re-run the cookie extraction script:\n"
            "  py -3.14 scripts/extract_hf_cookies.py --paste\n"
            "and paste the `datadome` cookie value when prompted (extract "
            "it from cloud.higgsfield.ai's cookies in DevTools alongside "
            "__client and __session)."
        )
    return cookie


def _discover_session_id(client, client_cookie: str) -> str:
    """GET /v1/client → find the active session id.

    Clerk's /v1/client returns a `response.last_active_session_id` for
    accounts with exactly one active session (the common case). For
    multi-session accounts it also returns a `sessions[]` list; we fall
    back to the first session that's active or unmarked.

    `client` is a curl_cffi Session impersonating chrome120."""
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


def _mint_jwt(client, client_cookie: str, sid: str) -> str:
    """POST /v1/client/sessions/{sid}/tokens → fresh JWT.

    `client` is a curl_cffi Session. curl_cffi's POST takes the body as
    `data=` (not `content=` like httpx). Empty body matches upstream impl."""
    url = f"{CLERK_BASE}/v1/client/sessions/{sid}/tokens"
    r = client.post(
        url,
        params=CLERK_VERSION_PARAMS,
        headers=COMMON_HEADERS,
        cookies={"__client": client_cookie},
        data="",
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

        # Path 3: refresh from __client cookie via Clerk. Use curl_cffi
        # with chrome120 impersonation to clear Cloudflare's bot check.
        client_cookie = _read_client_cookie()
        with _impersonate_requests.Session(impersonate=_IMPERSONATE) as client:
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


def upload_image_for_edit(image_path: Path) -> tuple[str, str]:
    """Upload an image into Higgsfield's web-app media store (fnf.higgsfield.ai
    /media). Returns `(media_id, public_url)`.

    This is DIFFERENT from generators.higgsfield_client.upload_image, which
    uses platform.higgsfield.ai/files. The two media stores are separate
    namespaces — the platform.higgsfield.ai upload returns CloudFront URLs
    that nano_banana_flash on fnf.higgsfield.ai refuses to recognize
    ("Media input not found" 404).

    Three-step flow, matching what the MCP media_upload tool does behind
    the scenes:
      1. POST /media/batch  →  {items: [{upload_url, id, url}, ...]}
      2. PUT raw bytes to upload_url (S3 presigned)
      3. POST /media/{id}/upload  →  registers the media so nano_banana_flash
                                       can reference it
    Auth: Clerk JWT + datadome cookie, just like the generation submit.
    """
    image_path = Path(image_path)
    suffix = image_path.suffix.lower()
    content_type_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }
    content_type = content_type_map.get(suffix, "image/png")

    with _impersonate_requests.Session(impersonate=_IMPERSONATE) as session:
        # Step 1: request a presigned upload URL + media id.
        r = session.post(
            f"{FNF_BASE}/media/batch",
            json={"mimetypes": [content_type], "source": "user_upload"},
            headers=_auth_headers(include_datadome=True),
            timeout=HTTP_TIMEOUT_S,
        )
        if r.status_code >= 400:
            raise HiggsfieldWebError(
                f"POST /media/batch returned {r.status_code}: {r.text[:300]}"
            )
        try:
            payload = r.json()
        except ValueError as e:
            raise HiggsfieldWebError(
                f"POST /media/batch returned non-JSON: {r.text[:200]}"
            ) from e
        # The endpoint sometimes returns a bare list, sometimes wraps in
        # {items: [...]} or {media: [...]} depending on the API version.
        # Accept all three shapes.
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = payload.get("items") or payload.get("media") or []
        else:
            items = []
        if not items:
            raise HiggsfieldWebError(
                f"POST /media/batch returned no items: {payload!r}"
            )
        item = items[0]
        upload_url = item.get("upload_url")
        media_id = item.get("id") or item.get("media_id")
        public_url = item.get("url") or item.get("public_url")
        if not upload_url or not media_id:
            raise HiggsfieldWebError(
                f"/media/batch item missing upload_url/id: {item!r}"
            )

        # Step 2: PUT raw bytes to S3. The presigned URL has auth baked in,
        # so we do NOT send any cookies/headers — those would actually
        # confuse some S3 endpoints.
        try:
            data = image_path.read_bytes()
        except OSError as e:
            raise HiggsfieldWebError(
                f"Failed to read image at {image_path}: {e}"
            ) from e
        put_resp = session.put(
            upload_url,
            data=data,
            headers={"Content-Type": content_type},
            timeout=HTTP_TIMEOUT_S,
        )
        if put_resp.status_code >= 400:
            raise HiggsfieldWebError(
                f"PUT to presigned URL returned {put_resp.status_code}: "
                f"{put_resp.text[:200]}"
            )

        # Step 3: finalize. Tells the server the upload succeeded so the
        # media_id becomes referenceable from generation jobs.
        confirm = session.post(
            f"{FNF_BASE}/media/{media_id}/upload",
            json={},
            headers=_auth_headers(include_datadome=True),
            timeout=HTTP_TIMEOUT_S,
        )
        if confirm.status_code >= 400:
            raise HiggsfieldWebError(
                f"POST /media/{media_id}/upload returned "
                f"{confirm.status_code}: {confirm.text[:200]}"
            )

    return str(media_id), str(public_url or "")


def _auth_headers(include_datadome: bool = False) -> dict[str, str]:
    """Standard auth header set for fnf.higgsfield.ai.

    When include_datadome=True, the datadome cookie is added explicitly
    via the Cookie header. We send it via the header rather than the
    per-request `cookies={"datadome": ...}` kwarg because curl_cffi
    sometimes doesn't merge per-request cookies with the impersonated
    Chrome cookie-handling logic correctly, and DataDome is strict
    about cookie presence."""
    jwt = _get_fresh_jwt()
    headers = {
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        **COMMON_HEADERS,
    }
    if include_datadome:
        headers["Cookie"] = f"datadome={_read_datadome_cookie()}"
    return headers


def _aspect_to_width_height(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    """Map (aspect_ratio, resolution) → (width, height) pixel dimensions.

    The fnf endpoint accepts `aspect_ratio` in the body but ALSO requires
    explicit `width` + `height` fields (verified via a 422 "Field required"
    on width — the server doesn't compute them from aspect_ratio alone).

    Targets roughly 1MP at 1k, 4MP at 2k, 8MP at 4k, with the ratio
    enforced precisely. Numbers chosen to match what nano_banana_flash
    accepts (multiples of 64 are safest for diffusion-family models)."""
    # Base "long side" pixels for each resolution tier.
    long_side_map = {"1k": 1280, "2k": 2048, "4k": 3840}
    long_side = long_side_map.get(resolution.lower(), 1280)
    # Parse the W:H ratio.
    try:
        w_part, h_part = aspect_ratio.split(":")
        wr, hr = float(w_part), float(h_part)
    except (ValueError, AttributeError):
        # Fallback: square at the long-side dimension.
        return long_side, long_side
    if wr >= hr:
        # Landscape (or square). Width = long_side, height scaled.
        width = long_side
        height = int(round(long_side * hr / wr))
    else:
        # Portrait. Height = long_side, width scaled.
        height = long_side
        width = int(round(long_side * wr / hr))
    # Round both to multiples of 64 to avoid model-side validation rejection.
    width = max(64, (width // 64) * 64)
    height = max(64, (height // 64) * 64)
    return width, height


def submit_nano_banana_edit(
    *,
    prompt: str,
    input_media: list[tuple[str, str]],
    aspect_ratio: str = "1:1",
    resolution: str = "1k",
    batch_size: int = 1,
    seed: int | None = None,
    enhance_prompt: bool = False,
) -> str:
    """Submit a nano_banana_flash edit job. Returns the job_id.

    `input_media` is a list of `(media_id, public_url)` pairs — both
    obtained from `upload_image_for_edit()`. Reference image first,
    product image second by convention. Up to 16 entries supported.

    The media_id MUST come from fnf.higgsfield.ai/media (NOT from
    platform.higgsfield.ai/files) — the two stores are separate
    namespaces and the wrong one yields "Media input not found" 404.

    Returns the job_id immediately. Callers then poll via
    `wait_for_result_url(job_id)` to get the final image URL."""
    if not input_media:
        raise ValueError("input_media must contain at least one (id, url) pair")
    if len(input_media) > 16:
        raise ValueError(
            f"input_media capped at 16, got {len(input_media)}"
        )

    url = f"{FNF_BASE}/jobs/v2/nano_banana_flash"
    # The fnf endpoint requires explicit width + height — aspect_ratio is
    # accepted but doesn't auto-populate them (verified empirically:
    # submitting only aspect_ratio returned 422 "Field required" on width).
    width, height = _aspect_to_width_height(aspect_ratio, resolution)
    # Images go in the `medias` array with the shape
    #   {role: "image", data: {id: <media_id>, url: <public_url>, type: "media_input"}}
    # which matches what the MCP server sends. Both id and url come from
    # upload_image_for_edit() which uses fnf.higgsfield.ai/media/* — the
    # only media store nano_banana_flash will accept ids from.
    medias: list[dict[str, Any]] = [
        {
            "role": "image",
            "data": {"id": media_id, "url": public_url, "type": "media_input"},
        }
        for (media_id, public_url) in input_media
    ]
    params: dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "width": width,
        "height": height,
        "batch_size": batch_size,
        "medias": medias,
        "enhance_prompt": enhance_prompt,
    }
    if seed is not None:
        params["seed"] = seed
    body = {"params": params, "use_unlim": False, "use_free_gens": False}

    # curl_cffi Session impersonating Chrome 131 to clear Cloudflare's TLS
    # check. datadome cookie sent via the Cookie header (in _auth_headers).
    with _impersonate_requests.Session(impersonate=_IMPERSONATE) as client:
        # Try once with cached JWT, retry once on 401 with forced refresh.
        for attempt in range(2):
            r = client.post(
                url, json=body, headers=_auth_headers(include_datadome=True),
                timeout=HTTP_TIMEOUT_S,
            )
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

    # The fnf submit response is shaped as
    #   { id: <workspace_id>,          ← NOT what we want
    #     job_sets: [{
    #         id: <job_set_id>,
    #         type: "nano_banana_flash",
    #         jobs: [{id: <job_id>, status: "queued", ...}]
    #     }],
    #     has_more: bool }
    # The actual job id we poll on is job_sets[0].jobs[0].id. The top-level
    # `id` is the workspace/project id and matching on it never finds the
    # job in /jobs listings (different namespace).
    job_id: str | None = None
    job_sets = payload.get("job_sets") or []
    if isinstance(job_sets, list) and job_sets:
        first_set = job_sets[0]
        if isinstance(first_set, dict):
            jobs = first_set.get("jobs") or []
            if isinstance(jobs, list) and jobs:
                first_job = jobs[0]
                if isinstance(first_job, dict):
                    job_id = first_job.get("id") or first_job.get("trace_id")
    # Fallback chain in case the response shape ever changes — kept defensive
    # so a schema tweak doesn't break us silently.
    if not job_id:
        job_id = (
            payload.get("request_id")
            or payload.get("job_id")
        )
    if not job_id:
        raise HiggsfieldWebError(
            f"submit returned no job id at expected paths. Response keys: "
            f"{list(payload.keys())}, payload snippet: {str(payload)[:400]}"
        )
    return str(job_id)


# ─── Polling + result extraction ─────────────────────────────────────────────


_TERMINAL = {"completed", "failed", "nsfw", "cancelled", "rejected"}


def _find_job_by_request_id(
    client, request_id: str
) -> dict | None:
    """GET /jobs?size=100 and find the entry whose request_id matches.

    Higgsfield's /jobs endpoint returns recent jobs (up to size). We
    don't have a per-request status URL the way platform.higgsfield.ai
    does, so we have to filter the list.

    Retries on Cloudflare 502/503/504 — the /jobs endpoint occasionally
    flakes when other parts of fnf.higgsfield.ai are fine. Short retry
    cycle (0.5s, 1s, 2s) to avoid extending the overall polling cadence
    by much when a single fetch fails.

    `client` is a curl_cffi Session impersonating chrome131."""

    def _do_get():
        return client.get(
            f"{FNF_BASE}/jobs",
            params={"size": 100},
            headers=_auth_headers(include_datadome=True),
            timeout=HTTP_TIMEOUT_S,
        )

    r = None
    for attempt, wait_s in enumerate([0, 0.5, 1.0, 2.0]):
        if wait_s > 0:
            time.sleep(wait_s)
        r = _do_get()
        if r.status_code == 401 and attempt == 0:
            _get_fresh_jwt(force_refresh=True)
            continue
        if r.status_code in (502, 503, 504):
            # Cloudflare upstream blip — retry without re-auth.
            continue
        break
    assert r is not None
    if r.status_code >= 400:
        raise HiggsfieldWebError(
            f"GET /jobs returned {r.status_code} after retries: {r.text[:200]}"
        )
    try:
        payload = r.json()
    except ValueError as e:
        raise HiggsfieldWebError(f"GET /jobs returned non-JSON") from e
    items = payload.get("items") or payload.get("jobs") or []
    # Debug: on the very first poll, dump the shape of the first job entry
    # so we can verify request_id field name actually matches. Cheap because
    # it fires once per orchestrator call.
    global _logged_first_jobs_shape
    if not _logged_first_jobs_shape and items:
        first = items[0]
        if isinstance(first, dict):
            print(
                f"[hf-web] /jobs first-entry keys: {list(first.keys())}",
                flush=True,
            )
        _logged_first_jobs_shape = True
    for item in items:
        if not isinstance(item, dict):
            continue
        # Try every plausible field name for the request id. Some endpoints
        # use request_id, others id, others job_id; we filter on any match.
        rids = {
            str(item.get(k)) for k in ("request_id", "id", "job_id")
            if item.get(k)
        }
        if str(request_id) in rids:
            return item
    return None


# Module-level flag for the debug log in _find_job_by_request_id.
_logged_first_jobs_shape = False


def _extract_result_url(job: dict) -> str:
    """Pull the OUTPUT image URL from a completed nano_banana_flash job.

    Verified shape (2026-05-22):
        results: {
            raw: {type: "image", url: <hf cdn rendered image>},
            min: {type: "image", url: <small webp version>}
        }
    so `results.raw.url` is what we want. The earlier walk-everything
    fallback was matching INPUT image URLs from params.medias because
    they share the same CloudFront host as the output — we now anchor
    on the d8j0ntlcm91z4 CDN distribution (HF's RENDERED-OUTPUT bucket,
    distinct from d2ol7oe51mr4n9 which serves input medias)."""
    # Primary path: results.raw.url
    results = job.get("results")
    if isinstance(results, dict):
        raw = results.get("raw")
        if isinstance(raw, dict):
            url = raw.get("url")
            if isinstance(url, str) and url:
                return url
        # Some older endpoints used a flat `results.url`. Try that too.
        for k in ("rawUrl", "url"):
            v = results.get(k)
            if isinstance(v, str) and v:
                return v
        # List-of-results variant.
        items = results.get("items")
        if isinstance(items, list):
            for r in items:
                if isinstance(r, dict):
                    for k in ("url", "rawUrl"):
                        v = r.get(k)
                        if isinstance(v, str) and v:
                            return v
    # `result` (singular) used by some other endpoints.
    result = job.get("result")
    if isinstance(result, dict):
        raw = result.get("raw")
        if isinstance(raw, dict):
            url = raw.get("url")
            if isinstance(url, str) and url:
                return url
        for k in ("rawUrl", "url"):
            v = result.get(k)
            if isinstance(v, str) and v:
                return v
    # Legacy: images[]/outputs[] collections.
    for collection_key in ("images", "outputs"):
        coll = job.get(collection_key)
        if isinstance(coll, list):
            for entry in coll:
                if isinstance(entry, dict):
                    for k in ("url", "rawUrl"):
                        v = entry.get(k)
                        if isinstance(v, str) and v:
                            return v
                elif isinstance(entry, str):
                    return entry
    flat = job.get("result_url")
    if isinstance(flat, str) and flat:
        return flat
    # Diagnostic dump if all else fails.
    import json as _json
    raise HiggsfieldWebError(
        f"Could not extract result URL from completed job. Keys: "
        f"{list(job.keys())}. result={_json.dumps(job.get('result'), default=str)[:300]} "
        f"results={_json.dumps(job.get('results'), default=str)[:300]}"
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
    with _impersonate_requests.Session(impersonate=_IMPERSONATE) as client:
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
    input_media: list[tuple[str, str]],
    aspect_ratio: str = "1:1",
    resolution: str = "1k",
    timeout_s: int = 600,
    seed: int | None = None,
) -> str:
    """Convenience: submit a job and block until the result URL is ready."""
    job_id = submit_nano_banana_edit(
        prompt=prompt,
        input_media=input_media,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        seed=seed,
    )
    return wait_for_result_url(job_id, timeout_s=timeout_s)


def download_result(url: str, out_path: Path) -> Path:
    """Save the result image (Higgsfield CDN URL) to a local file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=HTTP_TIMEOUT_S) as c:
        r = c.get(url)
        r.raise_for_status()
        out_path.write_bytes(r.content)
    return out_path
