import json

from strategy import pinterest_ads


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = json.dumps(self._payload).encode("utf-8") if payload is not None else b""

    def json(self):
        return self._payload


def test_granted_scopes_accepts_comma_or_space(monkeypatch):
    monkeypatch.setenv("PINTEREST_SCOPES", "ads:read,ads:write pins:read")
    monkeypatch.setenv("PINTEREST_GRANTED_SCOPES", "ads:read,pins:read")

    assert pinterest_ads.requested_scopes() == {"ads:read", "ads:write", "pins:read"}
    assert pinterest_ads.granted_scopes() == {"ads:read", "pins:read"}
    assert pinterest_ads.missing_scopes(["ads:read", "ads:write"]) == ["ads:write"]


def test_request_json_refreshes_once_on_401(monkeypatch, tmp_path):
    calls = []

    def fake_request(method, url, headers, timeout, **kwargs):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return FakeResponse(401, {"error": "expired"}, "expired")
        return FakeResponse(200, {"items": [{"id": "ad-account-1"}]})

    monkeypatch.setenv("PINTEREST_ACCESS_TOKEN", "old-token")
    monkeypatch.setattr(pinterest_ads.httpx, "request", fake_request)
    monkeypatch.setattr(pinterest_ads, "_refresh_token_to_env", lambda env_path: "new-token")

    payload = pinterest_ads.request_json("GET", "/ad_accounts", env_path=tmp_path / ".env")

    assert payload["items"][0]["id"] == "ad-account-1"
    assert calls == ["Bearer old-token", "Bearer new-token"]
