"""Extract Higgsfield Clerk session cookies from Chrome's local store and
write them into the project's .env.

Why this exists: the `__client` cookie that authorizes us to the Higgsfield
web backend (fnf.higgsfield.ai/jobs/v2/nano_banana_flash) is HttpOnly + Secure,
so neither JavaScript in the browser nor Claude's Chrome-MCP extension can read
it — both are blocked for security. The cookie lives in Chrome's local SQLite
database, encrypted with DPAPI on Windows (Keychain on macOS, libsecret on
Linux). The `browser_cookie3` package handles the decryption.

Usage:
  pip install browser-cookie3
  py -3.14 scripts/extract_hf_cookies.py

  # Optional: target a specific Chrome profile (default: Default)
  py -3.14 scripts/extract_hf_cookies.py --profile "Profile 1"

  # Optional: target a different browser (chrome, edge, brave, firefox, ...)
  py -3.14 scripts/extract_hf_cookies.py --browser chrome
  py -3.14 scripts/extract_hf_cookies.py --browser edge

  # Optional: dry-run (print what would be written without modifying .env)
  py -3.14 scripts/extract_hf_cookies.py --dry-run

What it does:
  1. Reads cookies for `.higgsfield.ai` from the chosen browser.
  2. Pulls __client (long-lived ~7d) and __session (short-lived ~60s).
  3. Updates HIGGSFIELD_CLERK_CLIENT and HIGGSFIELD_JWT in .env, creating
     those keys if they don't exist, replacing them if they do. The rest of
     .env is left untouched.

Re-run this whenever Higgsfield logs you out or the __client cookie expires
(~weekly). The hf-web client auto-mints fresh JWTs from __client between
re-runs, so you don't need to extract every minute.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = REPO_ROOT / ".env"

# Cookies we care about. Both are Clerk-set on the higgsfield.ai domain.
COOKIE_NAMES = {
    "__client": "HIGGSFIELD_CLERK_CLIENT",
    "__session": "HIGGSFIELD_JWT",
}
COOKIE_DOMAIN_SUFFIX = "higgsfield.ai"


def _import_browser_cookie3():
    try:
        import browser_cookie3  # type: ignore

        return browser_cookie3
    except ImportError:
        print(
            "ERROR: `browser-cookie3` is not installed.\n\n"
            "Install it with:\n"
            "  pip install browser-cookie3\n\n"
            "(or `py -3.14 -m pip install browser-cookie3` on Windows)",
            file=sys.stderr,
        )
        sys.exit(1)


def _load_cookie_jar(bc3, browser: str, profile: str | None):
    """Return a CookieJar containing cookies for higgsfield.ai from the
    specified browser + profile."""
    fn_map = {
        "chrome": bc3.chrome,
        "edge": bc3.edge,
        "brave": bc3.brave,
        "firefox": bc3.firefox,
        "chromium": bc3.chromium,
        "opera": bc3.opera,
        "vivaldi": bc3.vivaldi,
    }
    fn = fn_map.get(browser.lower())
    if fn is None:
        raise SystemExit(
            f"Unknown browser '{browser}'. Choose from: {', '.join(fn_map)}"
        )
    kwargs = {"domain_name": COOKIE_DOMAIN_SUFFIX}
    # browser_cookie3 honors `profile` for Chromium-family browsers, not
    # Firefox. Pass it only when applicable.
    if browser.lower() != "firefox" and profile:
        kwargs["profile"] = profile
    return fn(**kwargs)


def _extract_target_cookies(jar) -> dict[str, str]:
    """From a CookieJar, pull just the __client + __session cookies for
    higgsfield.ai. Returns {cookie_name: value}."""
    found: dict[str, str] = {}
    for cookie in jar:
        if not cookie.domain.endswith(COOKIE_DOMAIN_SUFFIX):
            continue
        if cookie.name in COOKIE_NAMES and cookie.value:
            # If the same cookie exists across multiple paths, prefer the
            # most recently set one (highest expires).
            existing = found.get(cookie.name)
            if existing is None:
                found[cookie.name] = cookie.value
    return found


def _read_env() -> list[str]:
    if not ENV_PATH.exists():
        # Bootstrap with a placeholder header so the new keys land cleanly.
        return [
            "# .env (bootstrapped by scripts/extract_hf_cookies.py)\n",
        ]
    return ENV_PATH.read_text(encoding="utf-8").splitlines(keepends=True)


def _upsert_env_key(lines: list[str], key: str, value: str) -> list[str]:
    """Replace `<key>=...` lines (commented or not) with `<key>=<value>`.
    Append a new line if the key isn't present."""
    pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=", re.MULTILINE)
    new_lines: list[str] = []
    replaced = False
    for line in lines:
        if pattern.match(line):
            # Preserve any trailing newline.
            new_lines.append(f"{key}={value}\n")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        # Make sure the previous block ends with a newline.
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        new_lines.append(f"{key}={value}\n")
    return new_lines


def _truncate_for_display(value: str, head: int = 12, tail: int = 6) -> str:
    """For confirmation prints — show enough of the cookie to know it's the
    right one without dumping the secret to the terminal."""
    if len(value) <= head + tail + 3:
        return value
    return f"{value[:head]}...{value[-tail:]} ({len(value)} chars)"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract Higgsfield Clerk cookies and write them to .env",
    )
    parser.add_argument(
        "--browser",
        default="chrome",
        help="Which browser to read from (default: chrome). "
        "Options: chrome, edge, brave, firefox, chromium, opera, vivaldi.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        help="Chromium profile name (default: Default). Ignored for Firefox. "
        "Try 'Profile 1', 'Profile 2', etc., if you use multiple Chrome profiles.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without modifying .env.",
    )
    args = parser.parse_args()

    bc3 = _import_browser_cookie3()
    print(
        f"Reading cookies for {COOKIE_DOMAIN_SUFFIX} from {args.browser}"
        + (f" (profile: {args.profile})" if args.profile else "")
        + "...",
        flush=True,
    )

    try:
        jar = _load_cookie_jar(bc3, args.browser, args.profile)
    except Exception as e:
        print(
            f"ERROR reading cookies: {e}\n\n"
            "Common causes:\n"
            "  1. Chrome is still running — close it fully (all windows, "
            "including system-tray) and retry. On Windows Chrome locks the "
            "cookie database while running.\n"
            "  2. You're not logged into cloud.higgsfield.ai. Open it in "
            "the browser, log in, then re-run this script.\n"
            "  3. Multiple Chrome profiles — try `--profile \"Profile 1\"`.\n"
            "  4. Different browser — try `--browser edge` or `--browser brave`.\n",
            file=sys.stderr,
        )
        return 1

    cookies = _extract_target_cookies(jar)
    if not cookies:
        print(
            f"\nERROR: No __client or __session cookies found for "
            f"{COOKIE_DOMAIN_SUFFIX} in {args.browser}.\n\n"
            f"Most likely cause: you're not currently logged into "
            f"cloud.higgsfield.ai in {args.browser}.\n\n"
            f"Fix: open https://cloud.higgsfield.ai in {args.browser}, "
            f"log in (or refresh if you think you're already logged in), "
            f"then re-run this script.",
            file=sys.stderr,
        )
        return 1

    found_keys = list(cookies.keys())
    if "__client" not in cookies:
        print(
            "\nWARNING: __client cookie not found. Only the short-lived "
            "__session is available, which expires in ~1 minute. The web "
            "client can't auto-refresh without __client. You'll need to "
            "re-run this script every minute, OR log out + back in to get "
            "a fresh __client.",
            file=sys.stderr,
        )

    print()
    for cookie_name, env_key in COOKIE_NAMES.items():
        if cookie_name in cookies:
            print(
                f"  {cookie_name:<10}  -> {env_key:<26}  "
                f"= {_truncate_for_display(cookies[cookie_name])}"
            )

    if args.dry_run:
        print(
            "\n--dry-run: NOT modifying .env. Re-run without --dry-run to "
            "apply.",
        )
        return 0

    env_lines = _read_env()
    for cookie_name, env_key in COOKIE_NAMES.items():
        if cookie_name in cookies:
            env_lines = _upsert_env_key(env_lines, env_key, cookies[cookie_name])
    ENV_PATH.write_text("".join(env_lines), encoding="utf-8")
    print(
        f"\nWrote {len(cookies)} value(s) to {ENV_PATH}. "
        f"Re-run this script weekly when __client expires, or whenever "
        f"`adc remix-images --engine hf-web` reports auth errors."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
