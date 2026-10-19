"""Pinterest OAuth helpers for Ads API access.

Pinterest API v5 uses OAuth 2.0 authorization code flow with a client secret.
These helpers mirror the Canva local callback pattern and never print token
values.
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

AUTHORIZE_URL = "https://www.pinterest.com/oauth/"
TOKEN_URL = "https://api.pinterest.com/v5/oauth/token"
DEFAULT_PINTEREST_SCOPES = "ads:read,ads:write,boards:read,pins:read,pins:write"


@dataclass(frozen=True)
class PinterestOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str = DEFAULT_PINTEREST_SCOPES
    continuous_refresh: bool = True


def load_config_from_env() -> PinterestOAuthConfig:
    missing = [
        key
        for key in (
            "PINTEREST_CLIENT_ID",
            "PINTEREST_CLIENT_SECRET",
            "PINTEREST_REDIRECT_URI",
        )
        if not os.environ.get(key, "").strip()
    ]
    if missing:
        raise ValueError(f"Missing Pinterest OAuth env var(s): {', '.join(missing)}")
    continuous_raw = os.environ.get("PINTEREST_CONTINUOUS_REFRESH", "true").strip().lower()
    return PinterestOAuthConfig(
        client_id=os.environ["PINTEREST_CLIENT_ID"].strip(),
        client_secret=os.environ["PINTEREST_CLIENT_SECRET"].strip(),
        redirect_uri=os.environ["PINTEREST_REDIRECT_URI"].strip(),
        scopes=os.environ.get("PINTEREST_SCOPES", DEFAULT_PINTEREST_SCOPES).strip()
        or DEFAULT_PINTEREST_SCOPES,
        continuous_refresh=continuous_raw not in {"0", "false", "no"},
    )


def build_authorization_url(config: PinterestOAuthConfig, *, state: str) -> str:
    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "scope": config.scopes,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def exchange_code_for_tokens(
    config: PinterestOAuthConfig,
    *,
    code: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": config.redirect_uri,
    }
    if config.continuous_refresh:
        data["continuous_refresh"] = "true"
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(config.client_id, config.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=data,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(
    config: PinterestOAuthConfig,
    *,
    refresh_token: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(config.client_id, config.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": config.scopes,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def default_state_path() -> Path:
    return Path.home() / ".adcreatives" / "pinterest-oauth-state.json"


def save_oauth_state(path: Path, *, state: str, redirect_uri: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "redirect_uri": redirect_uri,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_oauth_state(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "state": str(payload["state"]),
        "redirect_uri": str(payload["redirect_uri"]),
    }


def update_env_file(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(updates)
    output: list[str] = []
    for line in existing:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        key, _, _ = line.partition("=")
        key = key.strip()
        if key in remaining:
            output.append(f"{key}={remaining.pop(key)}")
        else:
            output.append(line)
    if remaining:
        if output and output[-1].strip():
            output.append("")
        for key, value in remaining.items():
            output.append(f"{key}={value}")
    path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def token_updates(token_response: dict[str, Any]) -> dict[str, str]:
    updates: dict[str, str] = {}
    if token_response.get("access_token"):
        updates["PINTEREST_ACCESS_TOKEN"] = str(token_response["access_token"])
    if token_response.get("refresh_token"):
        updates["PINTEREST_REFRESH_TOKEN"] = str(token_response["refresh_token"])
    if token_response.get("expires_in"):
        updates["PINTEREST_TOKEN_EXPIRES_IN"] = str(token_response["expires_in"])
    if token_response.get("refresh_token_expires_in"):
        updates["PINTEREST_REFRESH_TOKEN_EXPIRES_IN"] = str(
            token_response["refresh_token_expires_in"]
        )
    if token_response.get("refresh_token_expires_at"):
        updates["PINTEREST_REFRESH_TOKEN_EXPIRES_AT"] = str(
            token_response["refresh_token_expires_at"]
        )
    if token_response.get("scope"):
        updates["PINTEREST_GRANTED_SCOPES"] = str(token_response["scope"])
    return updates


def run_callback_server(
    *,
    config: PinterestOAuthConfig,
    expected_state: str,
    env_path: Path,
    port: int,
    path: str = "/pinterest/oauth/callback",
) -> dict[str, Any]:
    result: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Unknown Pinterest OAuth callback path.")
                return
            params = urllib.parse.parse_qs(parsed.query)
            state = params.get("state", [""])[0]
            code = params.get("code", [""])[0]
            error = params.get("error", [""])[0]
            try:
                if error:
                    raise RuntimeError(error)
                if not code:
                    raise RuntimeError("Missing authorization code.")
                if state != expected_state:
                    raise RuntimeError("OAuth state mismatch.")
                tokens = exchange_code_for_tokens(config, code=code)
                updates = token_updates(tokens)
                if updates:
                    update_env_file(env_path, updates)
                result["tokens"] = tokens
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    b"Pinterest OAuth succeeded. Tokens were saved locally. "
                    b"You can close this tab."
                )
            except Exception as exc:  # pragma: no cover - exercised manually.
                result["error"] = str(exc)
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Pinterest OAuth failed: {exc}".encode("utf-8"))

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.handle_request()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result.get("tokens", {})
