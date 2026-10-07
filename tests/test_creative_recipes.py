import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from PIL import Image

from strategy.creative_recipes import capture_recipe, load_recipe


def capture(tmp_path, client="savedbygrace", **kwargs):
    image = tmp_path / "source.png"
    Image.new("RGB", (100, 100), "white").save(image)
    return capture_recipe(
        clients_dir=tmp_path / "clients", client=client, product="tee",
        assets={"base": image, "final": image},
        steps=[{"tool": "pil", "inputs": ["base"], "outputs": ["final"],
                "settings": {"copy": "Brand question"}}], **kwargs,
    )


def test_snapshot_survives_source_changes_and_rejects_tampering(tmp_path):
    path = capture(tmp_path)
    recipe = load_recipe(path)
    (tmp_path / "source.png").write_bytes(b"changed")
    assert load_recipe(path) == recipe
    (path.parent / recipe["assets"]["base"]["path"]).write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash"):
        load_recipe(path)


def test_variants_have_new_identity_and_preserve_parent(tmp_path):
    parent = capture(tmp_path)
    original = parent.read_bytes()
    child = capture(tmp_path, parent=parent, changes={"setting": "porch"})
    p, c = load_recipe(parent), load_recipe(child)
    assert p["concept_id"] == c["concept_id"]
    assert p["version_id"] != c["version_id"]
    assert c["parent_version_id"] == p["version_id"]
    assert parent.read_bytes() == original
    with pytest.raises(ValueError, match="client"):
        capture(tmp_path, client="another", parent=parent, changes={"model": "new"})


def test_missing_assets_and_invalid_step_fail_without_recipe(tmp_path):
    with pytest.raises(FileNotFoundError):
        capture_recipe(clients_dir=tmp_path, client="sbg", product="tee",
                       assets={"base": tmp_path / "missing"},
                       steps=[{"tool": "pil", "outputs": ["base"]}])
    with pytest.raises(ValueError, match="unknown asset"):
        capture_recipe(clients_dir=tmp_path, client="sbg", product="tee",
                       assets={"base": Path(__file__)},
                       steps=[{"tool": "pil", "outputs": ["unknown"]}])


def test_reconstructed_capture_is_explicit(tmp_path):
    path = capture(tmp_path, provenance="reconstructed", limitations=["Only final edit known"])
    assert load_recipe(path)["provenance"] == "reconstructed"
    assert load_recipe(path)["limitations"] == ["Only final edit known"]


def test_record_and_inspect_cli_resolve_relative_assets(tmp_path):
    from cli import cli

    (tmp_path / "final.png").write_bytes(b"local test bytes")
    manifest = tmp_path / "intake.json"
    manifest.write_text(json.dumps({"client": "savedbygrace", "product": "tee",
        "provenance": "reconstructed", "limitations": ["Only output known"],
        "assets": {"final": "final.png"},
        "steps": [{"tool": "manual", "outputs": ["final"]}]}))
    runner = CliRunner()
    result = runner.invoke(cli, ["creative", "record", "--manifest", str(manifest),
                                 "--clients-dir", str(tmp_path / "clients")])
    assert result.exit_code == 0, result.output
    path = next((tmp_path / "clients").rglob("recipe.json"))
    result = runner.invoke(cli, ["creative", "inspect", "--recipe", str(path)])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["product"] == "tee"
    (path.parent / "assets" / "final.png").write_bytes(b"bad")
    result = runner.invoke(cli, ["creative", "inspect", "--recipe", str(path)])
    assert result.exit_code != 0 and "hash mismatch" in result.output


def test_rejects_client_path_escape_and_brief_mismatch(tmp_path):
    with pytest.raises(ValueError, match="client"):
        capture(tmp_path, client="../outside")
    with pytest.raises(ValueError, match="client"):
        capture(tmp_path, brief={"client": "someone-else"})


def test_ugc_cli_captures_effective_layout_and_style(tmp_path, monkeypatch):
    from cli import cli

    monkeypatch.chdir(tmp_path)
    base = tmp_path / "base.png"
    Image.new("RGB", (540, 675), "white").save(base)
    result = CliRunner().invoke(cli, ["ugc-ad", "--layout", "social-mirror",
        "--base", str(base), "--brand", "savedbygrace", "--product", "tee",
        "-o", str(tmp_path / "out.png")])
    assert result.exit_code == 0, result.output
    recipe = load_recipe(next((tmp_path / "clients").rglob("recipe.json")))
    settings = recipe["steps"][0]["settings"]
    assert settings["text_layout"][0]["text"]
    assert settings["style"]["font_path"]
    assert recipe["limitations"]


def test_native_cli_captures_effective_spec_and_base(tmp_path, monkeypatch):
    from cli import cli

    monkeypatch.chdir(tmp_path)
    base = tmp_path / "base.png"
    Image.new("RGB", (540, 675), "white").save(base)
    result = CliRunner().invoke(cli, ["native-ad", "--component", "reminder",
        "--body", "Remember your tee", "--source", "brand-authored reminder",
        "--client", "savedbygrace", "--product", "tee", "--base", str(base),
        "--size", "1x1", "-o", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    paths = list((tmp_path / "clients").rglob("recipe.json"))
    assert len(paths) == 1
    recipe = load_recipe(paths[0])
    assert recipe["steps"][0]["settings"]["native_ui"]["body"] == "Remember your tee"
    assert recipe["steps"][0]["settings"]["sizes"] == ["1x1"]
    assert recipe["provenance"] == "recorded"
    assert "base" in recipe["assets"]


def test_import_packet_is_idempotent_and_requires_local_matching_recipe(tmp_path):
    from strategy.creative_handoff import import_winners

    path = capture(tmp_path)
    recipe = load_recipe(path)
    packet = {"schema_version": 1, "kind": "creative_winners", "client": "savedbygrace",
              "packet_id": "week-2026-10-01", "status": "needs_review",
              "period_start": "2026-09-24",
              "period_end": "2026-10-01", "candidates": [
                  {"version_id": recipe["version_id"], "product": "tee", "ad_id": "123",
                   "account_id": "456", "platform": "meta", "metrics": {"roas": 2.5}}]}
    packet["candidates"][0].update(output_role="final",
                                  asset_sha256=recipe["assets"]["final"]["sha256"])
    packet_path = tmp_path / "winners.json"
    packet_path.write_text(json.dumps(packet))
    out = import_winners(packet_path, "savedbygrace", tmp_path / "clients")
    assert out == import_winners(packet_path, "savedbygrace", tmp_path / "clients")
    packet["generated_at"] = "2026-10-02T00:00:00Z"
    packet_path.write_text(json.dumps(packet))
    assert out == import_winners(packet_path, "savedbygrace", tmp_path / "clients")
    queue = json.loads(out.read_text())
    assert queue["status"] == "needs_review"
    assert queue["candidates"][0]["recipe_path"] == str(path.resolve())
    with pytest.raises(ValueError, match="client"):
        import_winners(packet_path, "another", tmp_path / "clients")
    packet["candidates"][0]["version_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    packet_path.write_text(json.dumps(packet))
    with pytest.raises((FileNotFoundError, ValueError)):
        import_winners(packet_path, "savedbygrace", tmp_path / "clients")
