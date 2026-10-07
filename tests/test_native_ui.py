"""Tests for generators/native_ui.py: native phone/app-screen components."""
from __future__ import annotations

from PIL import Image, ImageChops, ImageDraw

from generators.native_ui import (
    IMessageThread,
    Message,
    NotesCard,
    QuestionBox,
    ReminderPopup,
    _runs,
    render_native,
    ui_font,
    wrap,
    wrap_balanced,
)

BASE_COLOUR = (120, 90, 80)


def _base(size=(1080, 1350)):
    return Image.new("RGB", size, BASE_COLOUR)


def _changed_bbox(before: Image.Image, after: Image.Image):
    return ImageChops.difference(before, after).getbbox()


def test_question_box_draws_white_card_in_upper_half():
    base = _base()
    out = render_native(base, QuestionBox("What phrase would you put on a tee?", bold="phrase", center_y=0.3))
    assert out.size == base.size
    box = _changed_bbox(base, out)
    assert box is not None
    # card is centred and sits around 30% of the height
    assert abs((box[0] + box[2]) / 2 - 540) < 20
    assert box[1] < 0.3 * 1350 < box[3]
    assert out.getpixel((540, round(0.3 * 1350) - 40)) == (255, 255, 255)


def test_question_box_with_answer_renders():
    out = render_native(_base(), QuestionBox("Your favourite tee?", answer="Loves Jesus + America, Too"))
    assert _changed_bbox(_base(), out) is not None


def test_imessage_bubbles_use_native_colours():
    out = render_native(_base(), IMessageThread(top=0.2, messages=[
        Message("first message from them"), Message("my reply", sender="me")]))
    colours = {c for _, c in out.getcolors(1_000_000)}
    assert (233, 233, 235) in colours      # incoming #E9E9EB
    assert (10, 132, 255) in colours       # outgoing #0A84FF


def test_notes_card_checklist_and_dark_theme():
    out = render_native(_base(), NotesCard("Track the pause", ["Weight + reps", "Rest between sets"],
                                           checklist=True, checked=[0], theme="dark"))
    colours = {c for _, c in out.getcolors(1_000_000)}
    assert (28, 28, 30) in colours         # dark card #1C1C1E
    assert (226, 177, 60) in colours       # Notes accent


def test_reminder_popup_blue_button():
    out = render_native(_base(), ReminderPopup("Mind Your Own Motherhood."))
    colours = {c for _, c in out.getcolors(1_000_000)}
    assert (242, 242, 242) in colours      # alert card
    assert any(r < 60 and 100 < g < 160 and b > 220 for r, g, b in colours)  # blue OK


def test_render_native_cover_crops_to_story_size():
    out = render_native(_base((928, 1152)), ReminderPopup("hi"), size=(1080, 1920))
    assert out.size == (1080, 1920)


def test_components_scale_with_width():
    small = render_native(_base((540, 675)), ReminderPopup("Scaled card"))
    big = render_native(_base(), ReminderPopup("Scaled card"))
    sb, bb = _changed_bbox(_base((540, 675)), small), _changed_bbox(_base(), big)
    assert abs((sb[2] - sb[0]) * 2 - (bb[2] - bb[0])) <= 12


def test_wrap_balanced_avoids_orphan_word():
    d = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    f = ui_font(30)
    text = "What phrase would you put on a tee?"
    plain, balanced = wrap(d, text, f, None, 444), wrap_balanced(d, text, f, None, 444)
    assert len(plain) == len(balanced) == 2
    widths = [d.textlength(ln, font=f) for ln in balanced]
    assert min(widths) / max(widths) > 0.6


def test_emoji_runs_split():
    assert _runs("things you told us \U0001F90D") == [("things you told us ", False), ("\U0001F90D", True)]


# ─── Brief spec + CLI ───────────────────────────────────────────────────────

import pytest  # noqa: E402
from click.testing import CliRunner  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from generators.native_ui import component_from_spec  # noqa: E402
from models.brief import NativeUiSpec  # noqa: E402


def test_spec_requires_component_fields():
    with pytest.raises(ValidationError):
        NativeUiSpec(component="notes", title="only a title", content_source="reviews")


def test_spec_blocks_imessage_without_permission():
    with pytest.raises(ValidationError):
        NativeUiSpec(component="imessage", messages=[{"text": "hi"}], content_source="made up")
    ok = NativeUiSpec(component="imessage", messages=[{"text": "hi"}],
                      content_source="DM from @x, permission granted 2026-10-07")
    assert ok.messages[0].sender == "them"


def test_spec_requires_content_source():
    with pytest.raises(ValidationError):
        NativeUiSpec(component="reminder", body="hi", content_source="")


def test_component_from_spec_maps_placement():
    c = component_from_spec(NativeUiSpec(component="question_box", question="Q?", placement=0.2,
                                         content_source="brand-authored question"))
    assert isinstance(c, QuestionBox) and c.center_y == 0.2


def test_cli_native_ad_renders_requested_sizes(tmp_path):
    from cli import cli

    base = tmp_path / "base.png"
    _base((928, 1152)).save(base)
    res = CliRunner().invoke(cli, [
        "native-ad", "--component", "reminder", "--body", "Mind Your Own Motherhood.",
        "--source", "real product name", "--base", str(base), "-o", str(tmp_path / "out"),
        "--size", "4x5", "--size", "1x1",
    ])
    assert res.exit_code == 0, res.output
    assert Image.open(tmp_path / "out" / "reminder_4x5.png").size == (1080, 1350)
    assert Image.open(tmp_path / "out" / "reminder_1x1.png").size == (1080, 1080)


def test_cli_native_ad_rejects_missing_source(tmp_path):
    from cli import cli

    base = tmp_path / "base.png"
    _base().save(base)
    res = CliRunner().invoke(cli, ["native-ad", "--component", "reminder", "--body", "x",
                                   "--base", str(base), "-o", str(tmp_path / "out")])
    assert res.exit_code != 0
