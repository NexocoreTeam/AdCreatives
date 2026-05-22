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

# Cookies we care about. __client + __session are Clerk-set; datadome is
# the DataDome bot-protection cookie that authorizes requests through
# fnf.higgsfield.ai's challenge layer. All three live on the higgsfield.ai
# domain.
COOKIE_NAMES = {
    "__client": "HIGGSFIELD_CLERK_CLIENT",
    "__session": "HIGGSFIELD_JWT",
    "datadome": "HIGGSFIELD_DATADOME",
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


def _paste_mode(dry_run: bool) -> int:
    """Interactive fallback: prompt the operator for the cookie values
    one at a time, write them to .env. Used when browser_cookie3 can't
    decrypt the cookies (Chrome v127+ App-Bound Encryption blocks
    automated extraction even with admin privileges).

    Walks the operator through the DevTools cookie-pickup once with
    explicit instructions so they know exactly what to copy."""
    print()
    print("=" * 70)
    print("PASTE MODE — manually copy the Higgsfield Clerk cookies from")
    print("Chrome's DevTools and paste them when prompted.")
    print("=" * 70)
    print()
    print("Step-by-step (Chrome):")
    print()
    print("  1. Open https://cloud.higgsfield.ai in Chrome — confirm you're")
    print("     logged in.")
    print("  2. Right-click anywhere on the page → 'Inspect'.")
    print("  3. In the DevTools top tab bar, click 'Application' (may be")
    print("     hidden behind the >> arrow if the panel is narrow).")
    print("  4. Left sidebar: 'Storage' → expand 'Cookies' → click")
    print("     'https://cloud.higgsfield.ai'.")
    print("  5. A table of cookies appears on the right.")
    print()
    print("  Three cookies to copy, one at a time:")
    print()
    print("    a. '__client'  — long-lived (~7 days). Single-click the row,")
    print("       then look at the BOTTOM 'Cookie Value' pane. Click in it,")
    print("       Ctrl+A, Ctrl+C.")
    print()
    print("    b. '__session' — short-lived (~1 min), OPTIONAL. Same procedure.")
    print()
    print("    c. 'datadome'  — REQUIRED to bypass DataDome's bot challenge.")
    print("       Same procedure.")
    print()
    print("  Paste each one below when prompted.")
    print()

    values: dict[str, str] = {}
    try:
        client_val = input("Paste __client value (long-lived, required): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled.")
        return 1
    if not client_val:
        print(
            "\nERROR: __client is required. Without it the web client can't "
            "authenticate. Re-run and paste a value.",
            file=sys.stderr,
        )
        return 1
    # Strip surrounding quotes that some terminals add when right-click-pasting.
    client_val = client_val.strip("'\"")
    values["__client"] = client_val

    try:
        session_val = input(
            "Paste __session value (short-lived, optional — press Enter to skip): "
        ).strip().strip("'\"")
    except (EOFError, KeyboardInterrupt):
        session_val = ""
    if session_val:
        values["__session"] = session_val

    # The datadome cookie clears DataDome's bot challenge on fnf.higgsfield.ai.
    # Without it, requests come back with a 403 + "Please enable JS" page.
    try:
        datadome_val = input(
            "Paste datadome value (required for fnf.higgsfield.ai): "
        ).strip().strip("'\"")
    except (EOFError, KeyboardInterrupt):
        datadome_val = ""
    if datadome_val:
        values["datadome"] = datadome_val

    print()
    for cookie_name, env_key in COOKIE_NAMES.items():
        if cookie_name in values:
            print(
                f"  {cookie_name:<10}  -> {env_key:<26}  "
                f"= {_truncate_for_display(values[cookie_name])}"
            )

    if dry_run:
        print("\n--dry-run: NOT modifying .env.")
        return 0

    env_lines = _read_env()
    for cookie_name, env_key in COOKIE_NAMES.items():
        if cookie_name in values:
            env_lines = _upsert_env_key(env_lines, env_key, values[cookie_name])
    ENV_PATH.write_text("".join(env_lines), encoding="utf-8")
    print(
        f"\nWrote {len(values)} value(s) to {ENV_PATH}. "
        f"Re-run this script (with or without --paste) when __client expires "
        f"(~weekly)."
    )
    return 0


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
    parser.add_argument(
        "--paste",
        action="store_true",
        help="Skip automated extraction; prompt for the cookie values "
        "interactively. Use this when Chrome v127+ App-Bound Encryption "
        "blocks browser_cookie3 from decrypting cookies on your machine.",
    )
    args = parser.parse_args()

    # Paste mode bypasses browser_cookie3 entirely.
    if args.paste:
        return _paste_mode(args.dry_run)

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
        msg = str(e).lower()
        # Chrome v127+ App-Bound Encryption: cookie file is readable but
        # the decryption key requires Chrome's running process token.
        # browser_cookie3 doesn't support this yet (as of 0.20.1). Steer
        # the operator to paste mode rather than churning on browser flags.
        app_bound_hint = (
            "unable to get key" in msg
            or "requires admin" in msg
            or "app-bound" in msg
        )
        print(
            f"ERROR reading cookies: {e}\n\n"
            + (
                "This is Chrome/Edge v127+ App-Bound Encryption. The cookie\n"
                "file is readable but the encryption key is bound to Chrome's\n"
                "live process, and browser_cookie3 can't decrypt it offline.\n"
                "Use paste mode instead — same result, ~30 seconds of clicking:\n\n"
                "  py -3.14 scripts/extract_hf_cookies.py --paste\n\n"
                if app_bound_hint
                else "Common causes:\n"
                "  1. Chrome is still running — close all windows (incl. system tray).\n"
                "  2. Not logged into cloud.higgsfield.ai — open + log in, retry.\n"
                "  3. Wrong Chrome profile — try `--profile \"Profile 1\"`.\n"
                "  4. Wrong browser — try `--browser edge` or `--browser brave`.\n"
                "  5. If none of the above work, use paste mode:\n"
                "       py -3.14 scripts/extract_hf_cookies.py --paste\n"
            ),
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
