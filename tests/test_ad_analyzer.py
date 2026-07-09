"""Tests for strategy/ad_analyzer.py — prompt generation, analysis, intake.

No network: the vision call and Foreplay client are monkeypatched.
"""

from __future__ import annotations

import json

import pytest

import strategy.ad_analyzer as ad_analyzer
from strategy.ad_analyzer import (
    _runtime_signal,
    analyze_image,
    build_system_prompt,
    resolve_source,
)
from strategy.taxonomy import load_taxonomy


@pytest.fixture(scope="module")
def tax():
    return load_taxonomy()


def model_json(**overrides) -> str:
    data = {
        "brand": "Soft Services",
        "source_link": "",
        "proxy_signal": "unknown",
        "media_type": "static",
        "format": "Billboard",
        "hook_type": "Warning",
        "mechanic": "The Trojan Horse",
        "secondary_mechanic": None,
        "scan_path": ["headline", "product", "CTA"],
        "proof_element": "itemized receipt",
        "product_role": "hero",
        "awareness_stage": "problem_aware",
        "why_it_works": "Receipt framing feels audited, not advertised.",
        "cultural_note": "none",
        "steal": "Receipt-as-proof structure.",
        "avoid": "Do not reuse the creator or exact copy.",
        "field_confidence": {"format": "high", "hook_type": "med", "mechanic": "low",
                             "awareness_stage": "high", "product_role": "high"},
        "reasoning": {"mechanic": "native disguise", "awareness_stage": "felt pain"},
    }
    data.update(overrides)
    return json.dumps(data)


class TestBuildSystemPrompt:
    def test_contains_all_mechanics_and_hooks(self, tax):
        prompt = build_system_prompt(tax, "static")
        for name in tax.mechanic_names():
            assert name in prompt
        for name in tax.hook_type_names():
            assert name in prompt

    def test_static_prompt_excludes_video_only_formats(self, tax):
        prompt = build_system_prompt(tax, "static")
        assert "Billboard" in prompt
        assert "- ASMR:" not in prompt

    def test_video_prompt_includes_video_formats(self, tax):
        assert "- ASMR:" in build_system_prompt(tax, "video")

    def test_doctrine_and_stages_present(self, tax):
        prompt = build_system_prompt(tax, "static")
        assert "never to copy" in prompt
        assert "problem_aware" in prompt
        assert "secondary_mechanic" in prompt

    def test_secondary_mechanic_forbids_other(self, tax):
        # The prompt contract and the validator must agree: secondary is a
        # NAMED mechanic or null, never Other (regression: Huel, 2026-07-08).
        prompt = build_system_prompt(tax, "static")
        assert "Never use Other here" in prompt


class TestAnalyzeImage:
    def test_happy_path_payload(self, tax, tmp_path, monkeypatch):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"x")
        calls = []

        def fake_vision(prompt, image, **kwargs):
            calls.append(prompt)
            return model_json()

        monkeypatch.setattr(ad_analyzer, "vision_complete", fake_vision)
        payload = analyze_image(img, tax=tax, brand="Soft Services",
                                proxy_signal="running 4 months", model="claude-test")
        assert payload["card"]["mechanic"] == "The Trojan Horse"
        assert payload["card"]["proxy_signal"] == "running 4 months"  # operator wins
        assert payload["issues"] == []
        assert "⚠️ *Mechanic:*" in payload["display"]  # low confidence flagged
        assert payload["meta"]["model"] == "claude-test"
        assert payload["meta"]["taxonomy_version"] == tax.version
        assert len(calls) == 1
        assert "running 4 months" in calls[0]  # context reached the model

    def test_invalid_json_retries_once_then_succeeds(self, tax, tmp_path, monkeypatch):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"x")
        responses = iter(["sorry, here's my analysis!", model_json()])
        seen_prompts = []

        def fake_vision(prompt, image, **kwargs):
            seen_prompts.append(prompt)
            return next(responses)

        monkeypatch.setattr(ad_analyzer, "vision_complete", fake_vision)
        payload = analyze_image(img, tax=tax)
        assert payload["card"]["format"] == "Billboard"
        assert len(seen_prompts) == 2
        assert "not valid JSON" in seen_prompts[1]

    def test_invalid_json_twice_raises_no_fabrication(self, tax, tmp_path, monkeypatch):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"x")
        monkeypatch.setattr(ad_analyzer, "vision_complete",
                            lambda *a, **k: "not json, ever")
        with pytest.raises(RuntimeError, match="invalid JSON twice"):
            analyze_image(img, tax=tax)

    def test_markdown_fenced_json_accepted(self, tax, tmp_path, monkeypatch):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"x")
        monkeypatch.setattr(ad_analyzer, "vision_complete",
                            lambda *a, **k: f"```json\n{model_json()}\n```")
        assert analyze_image(img, tax=tax)["card"]["format"] == "Billboard"

    def test_bad_enum_from_model_becomes_issue(self, tax, tmp_path, monkeypatch):
        img = tmp_path / "ad.jpg"
        img.write_bytes(b"x")
        monkeypatch.setattr(ad_analyzer, "vision_complete",
                            lambda *a, **k: model_json(mechanic="The Sneaky Pete"))
        payload = analyze_image(img, tax=tax)
        assert any("mechanic" in i for i in payload["issues"])


class TestRuntimeSignal:
    def test_months_and_live(self):
        import datetime
        started = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=122)
        sig = _runtime_signal(int(started.timestamp() * 1000), True)
        assert "~4 months" in sig and "still live" in sig

    def test_days_when_fresh(self):
        import datetime
        started = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=12)
        sig = _runtime_signal(int(started.timestamp() * 1000), False)
        assert "12 days" in sig and "no longer live" in sig

    def test_zero_is_empty(self):
        assert _runtime_signal(0, True) == ""


class TestResolveSource:
    def test_local_image_passthrough(self, tmp_path):
        img = tmp_path / "ad.png"
        img.write_bytes(b"x")
        path, media, meta, ctx = resolve_source(str(img))
        assert path == img and media == "static" and meta == {} and ctx == {}

    def test_garbage_source_rejected(self):
        with pytest.raises(ValueError, match="neither an existing image"):
            resolve_source("not-an-ad")

    def test_video_ad_blocked_without_flag(self, tmp_path, monkeypatch):
        from strategy.foreplay_client import ForeplayAd

        ad = ForeplayAd(ad_id="1234567890123", name="Soft Services",
                        display_format="video", video_url="https://v",
                        thumbnail_url="https://t.jpg", started_running=0)
        import strategy.foreplay_client as fc
        monkeypatch.setattr(fc, "fetch_ad_by_id", lambda ad_id: ad)
        with pytest.raises(ValueError, match="VIDEO"):
            resolve_source("1234567890123", root=tmp_path)

    def test_video_ad_thumbnail_with_flag(self, tmp_path, monkeypatch):
        from strategy.foreplay_client import ForeplayAd

        ad = ForeplayAd(ad_id="1234567890123", name="Soft Services",
                        display_format="video", video_url="https://v",
                        thumbnail_url="https://t.jpg", link_url="https://brand.com",
                        started_running=1673997984000, live=True)
        import strategy.foreplay_client as fc
        monkeypatch.setattr(fc, "fetch_ad_by_id", lambda ad_id: ad)

        def fake_download(url, dest, **kwargs):
            dest.write_bytes(b"thumb")
            return dest

        monkeypatch.setattr(fc, "download_asset", fake_download)
        path, media, meta, ctx = resolve_source(
            "https://app.foreplay.co/whatever/1234567890123",
            allow_video=True, root=tmp_path)
        assert media == "video"
        assert path.read_bytes() == b"thumb"
        assert meta["brand"] == "Soft Services"
        assert "running" in ctx["proxy_signal"]
