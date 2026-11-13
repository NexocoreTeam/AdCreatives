import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _DirectResponse:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    text = "<html>direct</html>"

    def json(self):
        raise ValueError("not JSON")


class _Fetched(list):
    """URLs fetched directly, plus the User-Agent each request really sent."""

    def __init__(self, library_default: str):
        super().__init__()
        self.user_agents: list[str] = []
        self.library_default = library_default


@pytest.fixture
def direct(monkeypatch):
    """Replace httpx.Client for one test; return the list of URLs fetched directly.

    Every direct fetch answers 200 with the page "<html>direct</html>". The list
    also has `user_agents`, the User-Agent each request would really have sent
    (httpx's own name when the code sets none), and `library_default`, that own
    name. No network.
    """
    real_client = httpx.Client
    with real_client() as probe:
        fetched = _Fetched(probe.headers["user-agent"])

    class Client:
        def __init__(self, *args, headers=None, **kwargs):
            with real_client(headers=headers) as merged:
                self._user_agent = merged.headers.get("user-agent", "")

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, headers=None, **kwargs):
            fetched.append(url)
            fetched.user_agents.append(
                httpx.Headers(headers or {}).get("user-agent") or self._user_agent
            )
            return _DirectResponse()

    monkeypatch.setattr(httpx, "Client", Client)
    return fetched
