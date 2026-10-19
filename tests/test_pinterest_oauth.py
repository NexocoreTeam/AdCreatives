from pathlib import Path
from urllib.parse import parse_qs, urlparse

from strategy.pinterest_oauth import (
    PinterestOAuthConfig,
    build_authorization_url,
    update_env_file,
)


def test_build_authorization_url_includes_required_params():
    config = PinterestOAuthConfig(
        client_id="app-id",
        client_secret="secret",
        redirect_uri="http://127.0.0.1:8787/pinterest/oauth/callback",
        scopes="ads:read,ads:write,pins:read",
    )

    url = build_authorization_url(config, state="state-123")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.pinterest.com"
    assert parsed.path == "/oauth/"
    assert params["client_id"] == ["app-id"]
    assert params["redirect_uri"] == [config.redirect_uri]
    assert params["response_type"] == ["code"]
    assert params["scope"] == ["ads:read,ads:write,pins:read"]
    assert params["state"] == ["state-123"]


def test_update_env_file_updates_existing_and_appends_missing(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=keep\n"
        "PINTEREST_ACCESS_TOKEN=old\n"
        "# comment\n",
        encoding="utf-8",
    )

    update_env_file(
        env_path,
        {
            "PINTEREST_ACCESS_TOKEN": "new-token",
            "PINTEREST_REFRESH_TOKEN": "refresh-token",
        },
    )

    text = env_path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=keep" in text
    assert "PINTEREST_ACCESS_TOKEN=new-token" in text
    assert "PINTEREST_REFRESH_TOKEN=refresh-token" in text
    assert "old" not in text
