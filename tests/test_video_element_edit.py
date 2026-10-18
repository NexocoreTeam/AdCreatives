import json
from uuid import uuid4

import pytest

from strategy.video_remake import approve, claim, prepare, read_packet
from tests.test_video_remake import fixture_run, now


def edit_packet(tmp_path, billing="credits", change="person"):
    client, source = fixture_run(tmp_path)
    brief = dict(product="table", product_truth="White extending table and exact rails",
                 purpose="Change one element", direction="New adult in a blue blouse",
                 change=change, preserve="Same kitchen and movement", duration=6,
                 billing=billing, reference_role="preservation")
    (client / "brief.json").write_text(json.dumps(brief))
    run = prepare(client, source.relative_to(client).as_posix(), "analysis.json",
                  "brief.json", "product.png", element_edit=True)
    return client, run, read_packet(client, run.relative_to(client).as_posix())


def quote(packet):
    image, video = str(uuid4()), str(uuid4())
    return dict(params={**packet["params"], "medias": [
        {"role": "video_references", "value": video},
        {"role": "image_references", "value": image}]},
        credits=0 if packet["brief"]["billing"] == "free" else 28, quoted_at=now(),
        media_bindings={image: packet["assets"]["product"]["sha256"],
                        video: packet["assets"]["source"]["sha256"]})


@pytest.mark.parametrize("change", ["person", "setting", "person_and_setting"])
def test_element_packet_pins_model_and_preserved_elements(tmp_path, change):
    client, run, packet = edit_packet(tmp_path, change=change)
    assert packet["schema_version"] == 2
    assert packet["params"]["model"] == "hf_mult_replace_object"
    assert packet["params"]["use_unlim"] is False
    assert "Same kitchen and movement" in packet["params"]["prompt"]
    assert "preservation" in packet["params"]["prompt"]
    q = quote(packet)
    (client / "quote.json").write_text(json.dumps(q))
    relative = run.relative_to(client).as_posix()
    approve(client, relative, "quote.json", 28, "Use 28 credits", "alex")
    assert {m["role"] for m in claim(client, relative)["params"]["medias"]} == {"image", "video"}
    with pytest.raises(FileExistsError):
        claim(client, relative)


@pytest.mark.parametrize("mutation", ["no_video", "billing", "cost", "binding"])
def test_free_edit_cannot_fall_back_to_paid_or_wrong_media(tmp_path, mutation):
    client, run, packet = edit_packet(tmp_path, billing="free")
    q = quote(packet)
    if mutation == "no_video":
        q["params"]["medias"].pop(0)
    elif mutation == "billing":
        q["params"]["use_free_gens"] = False
    elif mutation == "cost":
        q["credits"] = 28
    else:
        q["media_bindings"][next(iter(q["media_bindings"]))] = "0" * 64
    (client / "quote.json").write_text(json.dumps(q))
    with pytest.raises(ValueError):
        approve(client, run.relative_to(client).as_posix(), "quote.json", 28, "Free only", "alex")


def test_free_edit_zero_cost_is_explicit_and_single_use(tmp_path):
    client, run, packet = edit_packet(tmp_path, billing="free")
    (client / "quote.json").write_text(json.dumps(quote(packet)))
    relative = run.relative_to(client).as_posix()
    approve(client, relative, "quote.json", 0, "Use free generation", "alex")
    assert claim(client, relative)["params"]["use_free_gens"] is True


def test_free_edit_rejects_1080p():
    from models.video_remake import ElementEditBrief
    with pytest.raises(ValueError, match="480p or 720p"):
        ElementEditBrief(product="p", product_truth="table", purpose="test", change="person",
                         direction="different adult", preserve="table", duration=4,
                         billing="free", resolution="1080p")


def test_edit_requires_matching_source_duration_even_with_reason(tmp_path):
    client, source = fixture_run(tmp_path)
    (client / "brief.json").write_text(json.dumps(dict(product="p", product_truth="table",
        purpose="test", change="setting", direction="kitchen", preserve="table",
        duration=4, duration_change_reason="Cannot override source duration")))
    with pytest.raises(ValueError, match="duration"):
        prepare(client, source.relative_to(client).as_posix(), "analysis.json",
                "brief.json", "product.png", element_edit=True)
