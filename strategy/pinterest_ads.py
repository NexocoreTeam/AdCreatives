"""Small Pinterest Ads API client for launch-readiness checks.

This module starts with read-only endpoints. Write operations should be added
behind explicit confirmation once OAuth and account discovery are proven.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx

from strategy.pinterest_oauth import (
    load_config_from_env,
    refresh_access_token,
    token_updates,
    update_env_file,
)

API_BASE = "https://api.pinterest.com/v5"


class PinterestAdsError(RuntimeError):
    """Raised when Pinterest Ads API access cannot complete a request."""


def _split_scopes(raw: str) -> set[str]:
    return {scope.strip() for scope in raw.replace(",", " ").split() if scope.strip()}


def requested_scopes() -> set[str]:
    return _split_scopes(os.environ.get("PINTEREST_SCOPES", ""))


def granted_scopes() -> set[str]:
    raw = os.environ.get("PINTEREST_GRANTED_SCOPES") or os.environ.get("PINTEREST_SCOPES", "")
    return _split_scopes(raw)


def missing_scopes(required: list[str]) -> list[str]:
    scopes = granted_scopes()
    return [scope for scope in required if scope not in scopes]


def _access_token() -> str:
    token = os.environ.get("PINTEREST_ACCESS_TOKEN", "").strip()
    if not token:
        raise PinterestAdsError(
            "Missing PINTEREST_ACCESS_TOKEN. Run `adc pinterest auth-url` first."
        )
    return token


def _api_headers(*, token: str | None = None) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token or _access_token()}",
        "Content-Type": "application/json",
    }


def _refresh_token_to_env(env_path: Path) -> str:
    refresh_token = os.environ.get("PINTEREST_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise PinterestAdsError(
            "Pinterest access token expired and PINTEREST_REFRESH_TOKEN is missing."
        )
    config = load_config_from_env()
    response = refresh_access_token(config, refresh_token=refresh_token)
    updates = token_updates(response)
    if not updates.get("PINTEREST_ACCESS_TOKEN"):
        raise PinterestAdsError("Pinterest token refresh did not return an access token.")
    update_env_file(env_path, updates)
    os.environ.update(updates)
    return updates["PINTEREST_ACCESS_TOKEN"]


def request_json(
    method: str,
    path: str,
    *,
    env_path: Path = Path(".env"),
    retry_refresh: bool = True,
    **kwargs: Any,
) -> dict[str, Any]:
    url = path if path.startswith("https://") else f"{API_BASE}{path}"
    response = httpx.request(method, url, headers=_api_headers(), timeout=30.0, **kwargs)
    if response.status_code == 401 and retry_refresh:
        token = _refresh_token_to_env(env_path)
        response = httpx.request(method, url, headers=_api_headers(token=token), timeout=30.0, **kwargs)
    if response.status_code >= 400:
        raise PinterestAdsError(
            f"Pinterest API {method} {path} failed: {response.status_code} {response.text}"
        )
    if not response.content:
        return {}
    return response.json()


def get_user_account() -> dict[str, Any]:
    return request_json("GET", "/user_account")


def list_ad_accounts(*, page_size: int = 25, bookmark: str | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {"page_size": page_size}
    if bookmark:
        params["bookmark"] = bookmark
    return request_json("GET", "/ad_accounts", params=params)


def list_campaigns(
    ad_account_id: str,
    *,
    page_size: int = 25,
    bookmark: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {"page_size": page_size}
    if bookmark:
        params["bookmark"] = bookmark
    return request_json("GET", f"/ad_accounts/{ad_account_id}/campaigns", params=params)
