"""Test renders of the native phone/app-screen components for Saved by Grace (SBG).

Usage (from the repo root):
    python scripts/render_native_ui_sbg_test.py [--base-dir DIR] [--out DIR]

Content rules applied here (see generators/native_ui.py):
  - Question box: SBG asking its own question, so nothing is fabricated.
  - Notes card: real customer reviews from clients/savedbygrace/brand-context.md, attributed.
  - Reminder: a real SBG product name.
  - iMessage thread: LAYOUT TEST ONLY with placeholder text; a real conversation shared with
    permission is required before any iMessage-style ad runs.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from generators.native_ui import (  # noqa: E402
    IMessageThread, Message, NotesCard, QuestionBox, ReminderPopup, render_native,
)

DEFAULT_BASE_DIR = Path("C:/AdCreatives/clients/savedbygrace/lifestyle-background-tests")

JOBS = [
    ("01-question-box", "03-small-town-porch-lifestyle.png",
     QuestionBox(question="What phrase would you put on a tee?", bold="phrase", center_y=0.30)),
    ("02-notes-real-reviews", "01-soft-home-everyday-faith.png",
     NotesCard(title="things you\u2019ve told us \U0001F90D", top=0.14, lines=[
         "\u201cSOOO many compliments!!!\u201d - Danielle P.",
         "\u201camazing quality like always\u201d - Cathy B.",
         "\u201cmy love for Jesus and dogs, both\u201d - Heidi H.",
     ])),
    ("03-reminder-product-name", "04-mom-life-casual.png",
     ReminderPopup(body="Mind Your Own Motherhood.", center_y=0.26)),
    ("04-imessage-LAYOUT-TEST-placeholder-text", "02-boutique-studio-editorial.png",
     IMessageThread(top=0.16, messages=[
         Message("[real customer message goes here]"),
         Message("[real reply goes here] \U0001F90D", sender="me"),
     ])),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    ap.add_argument("--out", type=Path, default=Path("tmp/native-ui-sbg"))
    args = ap.parse_args()
    for name, base, component in JOBS:
        for label, size in (("4x5", (1080, 1350)), ("9x16", (1080, 1920))):
            out = args.out / f"{name}_{label}.png"
            render_native(args.base_dir / base, component, out, size=size)
            print("wrote", out)


if __name__ == "__main__":
    main()
