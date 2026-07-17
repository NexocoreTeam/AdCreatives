"""Canva Connect OAuth helpers.

Canva Connect uses OAuth 2.0 authorization code flow with PKCE. These helpers
keep the security-sensitive bits in one place and avoid printing token values.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import urllib.parse
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import httpx

AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"
DEFAULT_CANVA_SCOPES = (
    "asset:read asset:write "
    "design:meta:read "
    "folder:read"
)


@dataclass(frozen=True)
class CanvaOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: str = DEFAULT_CANVA_SCOPES


def load_config_from_env() -> CanvaOAuthConfig:
    """Load Canva OAuth config from environment variables."""
    missing = [
        key
        for key in ("CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET", "CANVA_REDIRECT_URI")
        if not os.environ.get(key, "").strip()
    ]
    if missing:
        raise ValueError(f"Missing Canva OAuth env var(s): {', '.join(missing)}")
    return CanvaOAuthConfig(
        client_id=os.environ["CANVA_CLIENT_ID"].strip(),
        client_secret=os.environ["CANVA_CLIENT_SECRET"].strip(),
        redirect_uri=os.environ["CANVA_REDIRECT_URI"].strip(),
        scopes=os.environ.get("CANVA_SCOPES", DEFAULT_CANVA_SCOPES).strip()
        or DEFAULT_CANVA_SCOPES,
    )


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, S256 code_challenge)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge


def build_authorization_url(
    config: CanvaOAuthConfig,
    *,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "scope": config.scopes,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"


def _basic_auth_header(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def exchange_code_for_tokens(
    config: CanvaOAuthConfig,
    *,
    code: str,
    code_verifier: str,
    timeout: float = 30.0,
) -> dict[str, Any]:
    response = httpx.post(
        TOKEN_URL,
        headers={
            "Authorization": _basic_auth_header(config.client_id, config.client_secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def refresh_access_token(
    config: CanvaOAuthConfig,
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
        },
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def default_state_path() -> Path:
    return Path.home() / ".adcreatives" / "canva-oauth-state.json"


def save_oauth_state(path: Path, *, state: str, code_verifier: str, redirect_uri: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "code_verifier": code_verifier,
        "redirect_uri": redirect_uri,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_oauth_state(path: Path) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "state": str(payload["state"]),
        "code_verifier": str(payload["code_verifier"]),
        "redirect_uri": str(payload["redirect_uri"]),
    }


def update_env_file(path: Path, updates: dict[str, str]) -> None:
    """Add or update env keys without printing secrets."""
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
        updates["CANVA_ACCESS_TOKEN"] = str(token_response["access_token"])
    if token_response.get("refresh_token"):
        updates["CANVA_REFRESH_TOKEN"] = str(token_response["refresh_token"])
    if token_response.get("expires_in"):
        updates["CANVA_TOKEN_EXPIRES_IN"] = str(token_response["expires_in"])
    if token_response.get("scope"):
        updates["CANVA_GRANTED_SCOPES"] = str(token_response["scope"])
    return updates


def run_callback_server(
    *,
    config: CanvaOAuthConfig,
    expected_state: str,
    code_verifier: str,
    env_path: Path,
    port: int,
    path: str = "/canva/oauth/callback",
) -> dict[str, Any]:
    """Handle one OAuth callback request, exchange code, and update .env."""
    result: dict[str, Any] = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

        def do_GET(self) -> None:  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path != path:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"Unknown Canva OAuth callback path.")
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
                tokens = exchange_code_for_tokens(
                    config,
                    code=code,
                    code_verifier=code_verifier,
                )
                updates = token_updates(tokens)
                if updates:
                    update_env_file(env_path, updates)
                result["tokens"] = tokens
                self.send_response(200)
                self.end_headers()
                self.wfile.write(
                    b"Canva OAuth succeeded. Tokens were saved locally. "
                    b"You can close this tab."
                )
            except Exception as exc:  # pragma: no cover - exercised manually.
                result["error"] = str(exc)
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"Canva OAuth failed: {exc}".encode("utf-8"))

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.handle_request()
    if "error" in result:
        raise RuntimeError(str(result["error"]))
    return result.get("tokens", {})
