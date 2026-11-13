import json

import pytest
from click.testing import CliRunner

from strategy.ugc_reference_collect import cli
from strategy.ugc_references import merge, normalize, render, reserve, vtt_text


def test_caption_is_not_spoken_transcript():
    item = normalize(
        {
            "id": "1",
            "webVideoUrl": "https://www.tiktok.com/@a/video/1",
            "text": "Best bassinet ever",
        },
        "tiktok",
    )
    assert item["transcript"] == ""
    assert item["review_status"] == "needs_listening_review"


def test_duplicate_id_retains_provenance_and_richer_evidence():
    old = normalize(
        {
            "post_id": "1",
            "post_url": "https://www.tiktok.com/@a/video/1",
            "post_caption": "Useful caption",
        },
        "cached_tiktok",
        "old.json",
    )
    new = normalize(
        {
            "id": "1",
            "webVideoUrl": "https://www.tiktok.com/@a/video/1",
            "transcript": "I wanted my baby close.",
        },
        "tiktok",
        "run.json",
    )
    result = merge([old, new])
    assert len(result) == 1
    assert result[0]["transcript"] == "I wanted my baby close."
    assert result[0]["caption"] == "Useful caption"
    assert len(result[0]["provenance"]) == 2


def test_render_escapes_source_content_and_rejects_unsafe_url():
    item = normalize(
        {"id": "1", "text": "<script>alert(1)</script>", "webVideoUrl": "javascript:alert(1)"},
        "tiktok",
    )
    page = render([item])
    assert "<script>" not in page
    assert "javascript:" not in page
    assert "needs_listening_review" in page


def test_reservation_never_retries_unknown_submission(tmp_path):
    path = tmp_path / "attempt.json"
    reserve(path, {"cap_usd": 3})
    with pytest.raises(FileExistsError):
        reserve(path, {"cap_usd": 3})
    assert json.loads(path.read_text())["status"] == "submission_reserved"


def test_stable_platform_identity_not_caption():
    a = normalize({"id": "1", "text": "Same"}, "tiktok")
    b = normalize({"ad_id": "1", "description": "Same"}, "foreplay")
    assert len(merge([a, b])) == 2


def test_missing_identity_rejected():
    with pytest.raises(ValueError):
        normalize({"text": "missing id"}, "tiktok")


def test_vtt_preserves_spoken_text_not_timestamps_or_header():
    value = (
        "WEBVTT\n\n1\n00:00:01.000 --> 00:00:02.000\n"
        "<c>Hello &amp; welcome.</c>\n\n2\n00:00:02.000 --> 00:00:03.000\n"
        "Hello &amp; welcome.\n"
    )
    assert vtt_text(value) == "Hello & welcome."


@pytest.mark.parametrize("cap,approval", [(3, ""), (0, "yes"), (11, "yes"), ("NaN", "yes")])
def test_invalid_budget_never_starts_provider(tmp_path, monkeypatch, cap, approval):
    def forbidden(*args):
        pytest.fail("Provider must not be initialized")

    monkeypatch.setattr("strategy.ugc_reference_collect.client", forbidden)
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"approval": approval, "apify_cap_usd": cap}))
    env = tmp_path / "env"
    env.write_text("")
    result = CliRunner().invoke(
        cli,
        ["start-tiktok", "--plan", str(plan), "--output", str(tmp_path), "--env-file", str(env)],
    )
    assert result.exit_code != 0


def test_timeout_retains_reservation_and_blocks_second_submission(tmp_path, monkeypatch):
    class API:
        starts = 0

        def actor(self, name):
            return self

        def start(self, **kwargs):
            self.starts += 1
            assert kwargs["max_total_charge_usd"] == 3
            assert kwargs["restart_on_error"] is False
            raise TimeoutError("unknown outcome")

    api = API()
    monkeypatch.setattr("strategy.ugc_reference_collect.client", lambda _: api)
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "approval": "yes",
                "apify_cap_usd": 3,
                "post_urls": ["https://www.tiktok.com/@a/video/1"],
            }
        )
    )
    env = tmp_path / "env"
    env.write_text("")
    args = ["start-tiktok", "--plan", str(plan), "--output", str(tmp_path), "--env-file", str(env)]
    assert CliRunner().invoke(cli, args).exit_code != 0
    assert CliRunner().invoke(cli, args).exit_code != 0
    assert api.starts == 1


def test_collected_run_is_not_retrieved_or_resubmitted(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "strategy.ugc_reference_collect.client", lambda _: pytest.fail("network call")
    )
    (tmp_path / "apify-attempt.json").write_text('{"status":"collected"}')
    env = tmp_path / "env"
    env.write_text("")
    result = CliRunner().invoke(
        cli, ["finish-tiktok", "--output", str(tmp_path), "--env-file", str(env)]
    )
    assert result.exit_code == 0


def test_media_rejects_untrusted_host_before_fetch(tmp_path):
    from strategy.ugc_reference_review import download

    with pytest.raises(ValueError):
        download("https://localhost/private", tmp_path / "video.mp4")


def test_partial_run_collects_valid_items_and_records_failures(tmp_path, monkeypatch):
    class API:
        def run(self, identity):
            assert identity == "known-run"
            return self

        def get(self):
            return {"status": "FAILED", "defaultDatasetId": "dataset", "usageTotalUsd": 0.12}

        def dataset(self, identity):
            assert identity == "dataset"
            return self

        def iterate_items(self):
            return iter(
                [
                    {"id": "1", "webVideoUrl": "https://www.tiktok.com/@a/video/1"},
                    {"error": "private post"},
                ]
            )

    monkeypatch.setattr("strategy.ugc_reference_collect.client", lambda _: API())
    (tmp_path / "references.json").write_text("[]")
    (tmp_path / "apify-attempt.json").write_text('{"run_id":"known-run","status":"RUNNING"}')
    env = tmp_path / "env"
    env.write_text("")
    result = CliRunner().invoke(
        cli, ["finish-tiktok", "--output", str(tmp_path), "--env-file", str(env)]
    )
    assert result.exit_code == 0, result.output
    receipt = json.loads((tmp_path / "apify-attempt.json").read_text())
    assert receipt["provider_status"] == "FAILED"
    assert receipt["usage_usd"] == 0.12
    assert len(receipt["normalization_errors"]) == 1
    assert len(json.loads((tmp_path / "references.json").read_text())) == 1


def test_caption_reader_reuses_download_and_preserves_source(tmp_path):
    reference = normalize({"id": "1"}, "tiktok")
    (tmp_path / "references.json").write_text(json.dumps([reference]))
    (tmp_path / "apify-raw.json").write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "videoMeta": {
                        "subtitleLinks": [
                            {
                                "language": "eng-US",
                                "downloadLink": "https://api.apify.com/v2/key-value-stores/store/records/file",
                                "source": "MT",
                                "sourceUnabbreviated": "machine translation",
                            }
                        ]
                    },
                }
            ]
        )
    )
    folder = tmp_path / "captions"
    folder.mkdir()
    (folder / "1.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello there.\n")
    result = CliRunner().invoke(cli, ["captions", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    item = json.loads((tmp_path / "references.json").read_text())[0]
    assert item["transcript"] == "Hello there."
    assert item["transcript_source"]["source"] == "machine translation"
    assert item["review_status"] == "needs_listening_review"


def test_foreplay_skips_ambiguous_brand_instead_of_guessing(tmp_path, monkeypatch):
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "a"}, {"id": "b"}]}

    monkeypatch.setattr("strategy.ugc_reference_collect.httpx.get", lambda *a, **kw: Response())
    monkeypatch.setattr("strategy.ugc_reference_collect._headers", lambda: {})
    monkeypatch.setattr(
        "strategy.ugc_reference_collect.fetch_brand_ads",
        lambda *a, **kw: pytest.fail("Ambiguous brand must not be collected"),
    )
    (tmp_path / "references.json").write_text("[]")
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {"approval": "yes", "foreplay_domains": ["example.com"], "foreplay_credit_cap": 11}
        )
    )
    env = tmp_path / "env"
    env.write_text("")
    args = ["foreplay", "--plan", str(plan), "--output", str(tmp_path), "--env-file", str(env)]
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "foreplay-attempt.json").read_text())["records"] == 0
