from pathlib import Path
from urllib.parse import parse_qs, urlparse

from strategy.canva_oauth import (
    CanvaOAuthConfig,
    build_authorization_url,
    generate_pkce_pair,
    update_env_file,
)


def test_generate_pkce_pair_shapes():
    verifier, challenge = generate_pkce_pair()

    assert len(verifier) >= 43
    assert len(challenge) >= 43
    assert "=" not in challenge


def test_build_authorization_url_includes_required_params():
    config = CanvaOAuthConfig(
        client_id="client-id",
        client_secret="secret",
        redirect_uri="http://127.0.0.1:8787/canva/oauth/callback",
        scopes="profile:read asset:read",
    )

    url = build_authorization_url(config, state="state-123", code_challenge="abc")
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "www.canva.com"
    assert params["response_type"] == ["code"]
    assert params["client_id"] == ["client-id"]
    assert params["redirect_uri"] == [config.redirect_uri]
    assert params["scope"] == ["profile:read asset:read"]
    assert params["state"] == ["state-123"]
    assert params["code_challenge"] == ["abc"]
    assert params["code_challenge_method"] == ["S256"]


def test_update_env_file_updates_existing_and_appends_missing(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "ANTHROPIC_API_KEY=keep\n"
        "CANVA_ACCESS_TOKEN=old\n"
        "# comment\n",
        encoding="utf-8",
    )

    update_env_file(
        env_path,
        {
            "CANVA_ACCESS_TOKEN": "new-token",
            "CANVA_REFRESH_TOKEN": "refresh-token",
        },
    )

    text = env_path.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=keep" in text
    assert "CANVA_ACCESS_TOKEN=new-token" in text
    assert "CANVA_REFRESH_TOKEN=refresh-token" in text
    assert "old" not in text
