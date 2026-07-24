import base64
import json

from strategy import canva_connect


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="ok"):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.content = json.dumps(self._payload).encode("utf-8") if payload is not None else b""

    def json(self):
        return self._payload


def test_granted_scopes_prefers_actual_granted_scopes(monkeypatch):
    monkeypatch.setenv("CANVA_SCOPES", "asset:read asset:write folder:read")
    monkeypatch.setenv("CANVA_GRANTED_SCOPES", "asset:read")

    assert canva_connect.requested_scopes() == {"asset:read", "asset:write", "folder:read"}
    assert canva_connect.granted_scopes() == {"asset:read"}
    assert canva_connect.missing_scopes(["asset:read", "asset:write"]) == ["asset:write"]


def test_request_json_refreshes_once_on_401(monkeypatch, tmp_path):
    calls = []

    def fake_request(method, url, headers, timeout, **kwargs):
        calls.append(headers["Authorization"])
        if len(calls) == 1:
            return FakeResponse(401, {"error": "expired"}, "expired")
        return FakeResponse(200, {"items": [{"id": "design-1"}]})

    monkeypatch.setenv("CANVA_ACCESS_TOKEN", "old-token")
    monkeypatch.setattr(canva_connect.httpx, "request", fake_request)
    monkeypatch.setattr(canva_connect, "_refresh_token_to_env", lambda env_path: "new-token")

    payload = canva_connect.request_json("GET", "/designs", env_path=tmp_path / ".env")

    assert payload["items"][0]["id"] == "design-1"
    assert calls == ["Bearer old-token", "Bearer new-token"]


def test_upload_asset_sends_canva_metadata(monkeypatch, tmp_path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"png-bytes")
    captured = {}

    def fake_post(url, headers, content, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["content"] = content
        return FakeResponse(200, {"job": {"id": "job-1", "status": "success"}})

    monkeypatch.setenv("CANVA_ACCESS_TOKEN", "token")
    monkeypatch.setenv("CANVA_API_VERSION", "2026-02-02")
    monkeypatch.setattr(canva_connect.httpx, "post", fake_post)

    payload = canva_connect.upload_asset(image_path, name="AdCreatives API Test")

    metadata = json.loads(captured["headers"]["Asset-Upload-Metadata"])
    assert captured["url"].endswith("/asset-uploads")
    assert captured["headers"]["Authorization"] == "Bearer token"
    assert captured["headers"]["Content-Type"] == "application/octet-stream"
    assert captured["content"] == b"png-bytes"
    assert base64.b64decode(metadata["name_base64"]).decode("utf-8") == "AdCreatives API Test"
    assert payload["job"]["id"] == "job-1"
