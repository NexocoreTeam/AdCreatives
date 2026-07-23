"""Small Canva Connect API client for AdCreatives handoff workflows.

This module intentionally wraps only the Connect endpoints we have a clear
workflow for today: OAuth-backed token refresh, design metadata listing, asset
upload/read, and listing items in a known folder. Higher-risk design content
creation/export stays out until scopes and endpoint behavior are proven.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

import httpx

from strategy.canva_oauth import (
    load_config_from_env,
    refresh_access_token,
    token_updates,
    update_env_file,
)

API_BASE = "https://api.canva.com/rest/v1"
DEFAULT_API_VERSION = "2026-02-02"


class CanvaConnectError(RuntimeError):
    """Raised when Canva Connect cannot complete a request."""


def granted_scopes() -> set[str]:
    """Return scopes stored after OAuth, falling back to requested scopes."""
    raw = os.environ.get("CANVA_GRANTED_SCOPES") or os.environ.get("CANVA_SCOPES", "")
    return {scope.strip() for scope in raw.split() if scope.strip()}


def missing_scopes(required: list[str]) -> list[str]:
    scopes = granted_scopes()
    return [scope for scope in required if scope not in scopes]


def _access_token() -> str:
    token = os.environ.get("CANVA_ACCESS_TOKEN", "").strip()
    if not token:
        raise CanvaConnectError("Missing CANVA_ACCESS_TOKEN. Run `adc canva auth-url` first.")
    return token


def _api_headers(*, token: str | None = None, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token or _access_token()}",
        "Canva-Connect-API-Version": os.environ.get("CANVA_API_VERSION", DEFAULT_API_VERSION),
    }
    if extra:
        headers.update(extra)
    return headers


def _refresh_token_to_env(env_path: Path) -> str:
    refresh_token = os.environ.get("CANVA_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise CanvaConnectError("Canva access token expired and CANVA_REFRESH_TOKEN is missing.")
    config = load_config_from_env()
    response = refresh_access_token(config, refresh_token=refresh_token)
    updates = token_updates(response)
    if not updates.get("CANVA_ACCESS_TOKEN"):
        raise CanvaConnectError("Canva token refresh did not return an access token.")
    update_env_file(env_path, updates)
    os.environ.update(updates)
    return updates["CANVA_ACCESS_TOKEN"]


def request_json(
    method: str,
    path: str,
    *,
    env_path: Path = Path(".env"),
    retry_refresh: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a Canva JSON endpoint and refresh the token once on 401."""
    url = path if path.startswith("https://") else f"{API_BASE}{path}"
    response = httpx.request(method, url, headers=_api_headers(), timeout=30.0, **kwargs)
    if response.status_code == 401 and retry_refresh:
        token = _refresh_token_to_env(env_path)
        response = httpx.request(method, url, headers=_api_headers(token=token), timeout=30.0, **kwargs)
    if response.status_code >= 400:
        raise CanvaConnectError(f"Canva API {method} {path} failed: {response.status_code} {response.text}")
    if not response.content:
        return {}
    return response.json()


def list_designs(*, query: str | None = None, continuation: str | None = None, limit: int = 25) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation
    return request_json("GET", "/designs", params=params)


def get_design(design_id: str) -> dict[str, Any]:
    return request_json("GET", f"/designs/{design_id}")


def get_asset(asset_id: str) -> dict[str, Any]:
    return request_json("GET", f"/assets/{asset_id}")


def list_folder_items(folder_id: str, *, continuation: str | None = None, limit: int = 50) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": limit}
    if continuation:
        params["continuation"] = continuation
    return request_json("GET", f"/folders/{folder_id}/items", params=params)


def upload_asset(file_path: Path, *, name: str | None = None) -> dict[str, Any]:
    """Upload an image/video asset to Canva and return the async job payload."""
    if not file_path.exists():
        raise CanvaConnectError(f"Asset file not found: {file_path}")
    display_name = (name or file_path.name)[:50]
    metadata = {"name_base64": base64.b64encode(display_name.encode("utf-8")).decode("ascii")}
    headers = _api_headers(
        extra={
            "Content-Type": "application/octet-stream",
            "Asset-Upload-Metadata": json.dumps(metadata, separators=(",", ":")),
        }
    )
    response = httpx.post(
        f"{API_BASE}/asset-uploads",
        headers=headers,
        content=file_path.read_bytes(),
        timeout=60.0,
    )
    if response.status_code == 401:
        token = _refresh_token_to_env(Path(".env"))
        headers["Authorization"] = f"Bearer {token}"
        response = httpx.post(
            f"{API_BASE}/asset-uploads",
            headers=headers,
            content=file_path.read_bytes(),
            timeout=60.0,
        )
    if response.status_code >= 400:
        raise CanvaConnectError(f"Canva asset upload failed: {response.status_code} {response.text}")
    return response.json()
