"""Tests for strategy/llm.py image helpers (no network)."""

from __future__ import annotations

from strategy.llm import sniff_image_mime


class TestSniffImageMime:
    def test_png(self):
        assert sniff_image_mime(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) == "image/png"

    def test_jpeg(self):
        assert sniff_image_mime(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "image/jpeg"

    def test_webp(self):
        assert sniff_image_mime(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"

    def test_gif(self):
        assert sniff_image_mime(b"GIF89a" + b"\x00" * 8) == "image/gif"

    def test_unknown_is_none(self):
        assert sniff_image_mime(b"not an image") is None
        assert sniff_image_mime(b"") is None
