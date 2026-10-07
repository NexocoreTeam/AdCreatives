# Native phone/app-screen components

`generators/native_ui.py` renders the screens that make a static read as **organic** instead of
designed: the Instagram question box, an iMessage thread, an iOS Notes card and an iOS reminder
pop-up. They're composited with PIL onto a clean base photo (no baked-in text), pixel-exact, at
any size, for ~$0. Same pipeline idea as `ugc_overlay.py`: AI makes the photo, code sets the text.

**Why:** generated or brand-styled versions of these screens look like ads: wrong font, wrong
bubble shape, brand pills the real UI doesn't have. Specs come from measured organic templates
(organic-content repo: `ops/resources/NATIVE-UI-TEMPLATES.md`, `ELLA-STYLE-SYSTEM.md`) and
Apple/Instagram UI conventions.

## Rules (non-negotiable)

1. **Native screens keep their native look.** Don't pass brand fonts or colours into them. The
   brand shows up in the photo, the product and the words, not in the UI chrome.
2. **Only the words change.** Keep copy short enough that cards and bubbles don't reflow oddly.
   Questions and messages wrap balanced, with no orphaned last word.
3. **Real content only.** iMessage/DM threads are real conversations shared with permission.
   Reviews are real, attributed reviews. The question box is either a question the brand is
   asking (placeholder field) or a real customer's answer. Never write a fake testimonial into a
   realistic bubble: it's deceptive, and on Meta it's a policy risk.

## Components

| Component | Use it for | Key specs (at 1080 px wide; scaled to the base) |
|---|---|---|
| `QuestionBox` | "Ask me" engagement, FAQ-style hooks | white card 524 px, radius 34, avatar disc 80 px on the top edge, question 30 px (one bold word optional), grey field `#F0F0F0` radius 16, "Type something..." at ~47% opacity |
| `IMessageThread` | a real customer conversation | bubbles 33 px text, incoming `#E9E9EB` / `#1C1C1E`, outgoing `#0A84FF` / white, tails on outer corners, timestamp 24 px `#8E8E93`, optional white screenshot panel |
| `NotesCard` | lists, real review roundups, checklists | "‹ Notes" in Notes yellow `#E2A226`, bold 44 px title, 33 px rows, optional checklist circles; light or dark theme |
| `ReminderPopup` | one-line reminders, product-name punchlines | iOS alert `#F2F2F2`, radius 30, semibold title, 28 px body, divider `#C6C6C8`, blue `OK` `#0A84FF` |

```python
from generators.native_ui import QuestionBox, NotesCard, render_native
render_native("base.png", QuestionBox("What phrase would you put on a tee?", bold="phrase"),
              "out_4x5.png", size=(1080, 1350))   # also (1080, 1920) for stories
```

Placement is a fraction of image height (`center_y` / `top`). Put the component over calm
space, usually the upper third.

## Fonts

Apple's UI font (SF Pro) isn't bundled. The renderer uses **Segoe UI Variable** on Windows
(closest installed match), then SF/Inter if present, then Segoe/Arial. For maximum fidelity,
install Inter (OFL) or run on a Mac with SF, and the candidates list picks it up. Colour emoji
render via Segoe UI Emoji / Apple Color Emoji.

## SBG test (2026-10-07)

`python scripts/render_native_ui_sbg_test.py` renders four components × 4:5 and 9:16 onto SBG's
clean lifestyle bases (`clients/savedbygrace/lifestyle-background-tests/`, untracked; pass
`--base-dir` elsewhere) into `tmp/native-ui-sbg/`:
- question box with SBG's own question (honest by construction);
- Notes card with three **real attributed reviews** from `brand-context.md`;
- reminder with a real product name ("Mind Your Own Motherhood.");
- iMessage thread as a **layout test with placeholder text**. It needs a real conversation
  shared with permission before it can run.

Open items for SBG: its profile picture for the question-box avatar (`avatar=`); real customer
questions/DMs (none on file; the question lines in `voc/` come from competitors' TikTok comments).

## Next steps (not built yet)

- CLI command (e.g. `adc native-ad --component notes --base ... --size 4x5`) and brief support
  (a `native_ui` block on `CreativeBrief`), so strategists can request these without Python.
- More components measured in organic-content: DM/comment replies, Q&A answer card, Copy/Select
  menu, lock screen.
- Fold rules 1–3 into the native static QA checklist.
