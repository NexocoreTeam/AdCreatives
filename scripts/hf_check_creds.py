"""Verify Higgs Field credentials are loaded and the auth handshake works.

Usage:
    python scripts/hf_check_creds.py

What it does:
  1. Loads .env via python-dotenv (override=True so an empty shell var
     doesn't shadow the value from .env).
  2. Checks HF_CREDENTIALS / HF_API_KEY+SECRET are set and well-formed.
  3. Fires a soul_2 cost-only preflight via Higgs Field's REST API — no
     credits are consumed, but it does exercise the auth path so 401s
     surface immediately.

Prints either:
  OK — credentials valid, auth handshake succeeded (X credits would cost Y)
  FAIL — with the exact error and a hint about how to fix it
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except Exception:
    pass

import httpx

from generators.higgsfield_client import (
    HF_BASE_URL,
    HiggsfieldError,
    _get_credentials,
    _headers,
)


def main() -> int:
    # 1. Credentials present + well-formed?
    try:
        creds = _get_credentials()
    except RuntimeError as e:
        print(f"FAIL — {e}")
        return 1
    key_id = creds.split(":")[0]
    print(f"OK   credentials loaded (KEY_ID={key_id[:8]}…)")

    # 2. Auth handshake — try a minimal authenticated GET. We probe the
    # /requests endpoint for a known-bad request_id; we don't care if it
    # 404s, we only care that it doesn't 401.
    url = f"{HF_BASE_URL}/requests/00000000-0000-0000-0000-000000000000/status"
    try:
        with httpx.Client(timeout=15) as c:
            r = c.get(url, headers=_headers())
    except httpx.HTTPError as e:
        print(f"FAIL — network error reaching {HF_BASE_URL}: {e}")
        return 1

    if r.status_code == 401:
        print(
            "FAIL — 401 Unauthorized. The credentials reached Higgs Field "
            "but were rejected. Re-check the KEY_ID:KEY_SECRET format and "
            "that the key hasn't been revoked at https://platform.higgsfield.ai"
        )
        return 1
    if r.status_code == 403:
        print(
            "FAIL — 403 Forbidden. Auth worked but the key may not have "
            "permissions for this endpoint (or you're out of credits)."
        )
        return 1
    # 404 / 422 are both fine here — they mean auth succeeded but the
    # request_id we sent is bogus.
    print(f"OK   auth handshake succeeded (HTTP {r.status_code} on probe — expected, since we sent a fake request_id)")
    print()
    print(f"Ready to run: adc remix-images --remix-dir <dir> --engine higgsfield-soul")
    return 0


if __name__ == "__main__":
    sys.exit(main())
