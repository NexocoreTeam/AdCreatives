"""Resolve a Foreplay share link headlessly: screenshot + media URLs + Firestore doc sniff.

Usage: python scripts/resolve_foreplay_share.py <share_url> <out_dir>
"""
import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SHELL_HINTS = ("app.foreplay.co/img", "twitter", "//t.co", "defaultProfileImage")


def resolve(share_url: str, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    media_hits: list[str] = []
    firestore_chunks: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 2200}, user_agent=UA)

        def on_response(resp):
            url = resp.url
            ctype = (resp.headers or {}).get("content-type", "")
            is_shell = any(h in url for h in SHELL_HINTS)
            if not is_shell and (
                "video" in ctype
                or url.endswith((".mp4", ".webm"))
                or ("image" in ctype and ("r2.foreplay" in url or "cloudfront" in url or "fbcdn" in url))
            ):
                media_hits.append(f"{ctype} :: {url}")
            if "firestore.googleapis.com" in url:
                try:
                    body = resp.text()
                    if body and len(body) > 50:
                        firestore_chunks.append(body)
                except Exception:
                    pass

        page.on("response", on_response)
        page.goto(share_url, wait_until="domcontentloaded")

        real_media_found = False
        for _ in range(20):
            page.wait_for_timeout(2000)
            n_vid = page.locator("video").count()
            n_img = page.eval_on_selector_all(
                "img",
                "els => els.filter(e => e.src && !e.src.includes('app.foreplay.co/img')"
                " && !e.src.includes('twitter') && !e.src.includes('t.co')"
                " && !e.src.includes('defaultProfileImage')).length",
            )
            if n_vid > 0 or n_img > 0 or media_hits:
                real_media_found = True
                page.wait_for_timeout(3000)
                break

        videos = page.eval_on_selector_all("video", "els => els.map(e => e.currentSrc || e.src)")
        video_sources = page.eval_on_selector_all("video source", "els => els.map(e => e.src)")
        images = page.eval_on_selector_all("img", "els => els.map(e => e.src)")
        body_text = page.inner_text("body")
        page.screenshot(path=str(out_dir / "share_page.png"), full_page=True)
        browser.close()

    # Mine firestore chunks for any media-looking URLs and doc fields.
    fs_urls = sorted(
        {
            m
            for chunk in firestore_chunks
            for m in re.findall(r"https://[^\"\\\s]+", chunk)
            if not any(h in m for h in SHELL_HINTS)
        }
    )
    result = {
        "share_url": share_url,
        "real_media_found": real_media_found,
        "videos": [v for v in videos if v],
        "video_sources": [v for v in video_sources if v],
        "ad_images": [i for i in images if i and not any(h in i for h in SHELL_HINTS)],
        "media_hits": media_hits,
        "firestore_urls": fs_urls,
        "n_firestore_chunks": len(firestore_chunks),
        "body_text": body_text,
    }
    (out_dir / "share_meta.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    if firestore_chunks:
        (out_dir / "firestore_chunks.txt").write_text(
            "\n\n=====CHUNK=====\n\n".join(firestore_chunks), encoding="utf-8"
        )
    return result


if __name__ == "__main__":
    url = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("share_resolve")
    meta = resolve(url, out)
    print(json.dumps({k: v for k, v in meta.items() if k != "body_text"}, indent=2))
    print("--- BODY TEXT ---")
    print(meta["body_text"][:3000])
