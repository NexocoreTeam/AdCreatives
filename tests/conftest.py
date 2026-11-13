import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class _DirectResponse:
    status_code = 200
    headers = {"content-type": "text/html; charset=utf-8"}
    text = "<html>direct</html>"


@pytest.fixture
def direct(monkeypatch):
    """Replace httpx.Client for one test; return the list of URLs fetched directly.

    Every direct fetch answers 200 with the page "<html>direct</html>". No network.
    """
    fetched: list[str] = []

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url, **kwargs):
            fetched.append(url)
            return _DirectResponse()

    monkeypatch.setattr(httpx, "Client", Client)
    return fetched
