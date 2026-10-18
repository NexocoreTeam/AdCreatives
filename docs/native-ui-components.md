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

For the full briefing-to-production route, including organic captions and
existing UGC overlays, use [native-organic-workflow.md](native-organic-workflow.md).
Only the four components below are implemented; DM/comment replies and the
separate Q&A answer card require the optional template route for now.

| Component | Use it for | Key specs (at 1080 px wide; scaled to the base) |
|---|---|---|
| `QuestionBox` | "Ask me" engagement, FAQ-style hooks | white card 524 px, radius 34, avatar disc 80 px on the top edge, question 30 px (one bold word optional), grey field `#F0F0F0` radius 16, "Type something..." at ~47% opacity |
| `IMessageThread` | a real customer conversation | bubbles 33 px text, incoming `#E9E9EB` / `#1C1C1E`, outgoing `#0A84FF` / white, tails on outer corners, timestamp 24 px `#8E8E93`, optional white screenshot panel |
| `NotesCard` | lists, real review roundups, checklists | "‹ Notes" in Notes yellow `#E2A226`, bold 44 px title, 33 px rows, optional checklist circles; light or dark theme |
| `ReminderPopup` | one-line reminders, product-name punchlines | iOS alert `#F2F2F2`, radius 30, semibold title, 28 px body, divider `#C6C6C8`, blue `OK` `#0A84FF` |

### Command

```bash
adc native-ad --component question_box --question "What phrase would you put on a tee?"     --bold phrase --source "brand-authored question"     --base clients/savedbygrace/lifestyle-background-tests/03-small-town-porch-lifestyle.png     -o ai-ads/savedbygrace/native --client savedbygrace
adc native-ad --component notes --title "things you've told us" --line "..." --line "..."     --source "reviews: brand-context.md L195-201" --base <clean.png> -o <dir>
adc native-ad --component imessage --message "them: ..." --message "me: ..."     --source "DM from @x, permission granted 2026-10-07" --base <clean.png> -o <dir>
adc native-ad --brief clients/<client>/briefs/<brief>.yaml -o <dir>
```

Default sizes 4x5 + 9x16 (`--size 1x1` too). Each PNG gets a `.meta.yaml` sidecar recording
the content source.

### Brief block

```yaml
native_ui:
  component: notes            # question_box | imessage | notes | reminder
  content_source: "reviews: clients/savedbygrace/brand-context.md L195-201"
  base_image: clients/savedbygrace/lifestyle-background-tests/01-soft-home-everyday-faith.png
  sizes: [4x5, 9x16]
  title: "things you've told us"
  lines: ["“SOOO many compliments!!!” - Danielle P."]
```

Validation: each component's required fields; `content_source` always; iMessage specs must
state permission or they're rejected.

### Python

```python
from generators.native_ui import QuestionBox, render_native
render_native("base.png", QuestionBox("What phrase would you put on a tee?", bold="phrase"),
              "out_4x5.png", size=(1080, 1350))
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

## Canva route (preferred for the supplied iOS/Ella reference)

For the iOS/Ella board and its exact look, use the reusable Codex workflow in
[canva-native-ads.md](canva-native-ads.md). The code route remains available for
supported local/batch renders. Mitchell's Canva has copies of the Ella Content Club
library in the folder **"Ella Templates"** (`FAHXWdJE5hg`). Native-screen source pages:

| Screen | Copy (design ID) · page |
|---|---|
| IG question box | iOS `DAHXWe9cEqM` p33 · Content Creator `DAHXWKD2A58` p17 · Fitness `DAHXWc0SgZ8` p41 · Real Estate `DAHXWRfyiNU` p8 (Q&A) |
| iMessage / chat | Content Creator `DAHXWKD2A58` p24 · Social Media Coach `DAHXWbpUTg0` p39 · Hairstylist `DAHXWd5DkOI` p13 |
| DM / comment replies | Content Creator `DAHXWKD2A58` p18, p51 |
| Notes | Finance `DAHXWVCSelI` p51 (checklist) · iOS `DAHXWe9cEqM` p3, p5 · Wellness `DAHXWZVr4OA` p50 |
| Reminder | Fitness `DAHXWc0SgZ8` p21 · Skincare Quotes `DAHXWT3E2ww` p12 |

Workflow with the Canva connector: `copy_design` with `page_numbers: [N]` →
`start_editing_transaction` on the working copy → `perform_editing_operations`
(`find_and_replace_text` preserves existing formatting; `update_fill` swaps a
photo) → compare before/after previews → user approval → `commit_editing_transaction`.
Discover export capability separately; the current connector has no export tool.
Use an authenticated Canva browser for Download, or report export pending.
Keep the source's fonts and styling; record the actual operations and exports.

Licence (Ella CS LLC): use for clients as part of a paid service is allowed; never resell or
redistribute the templates or share the library links with clients. Full catalogue and specs
live in the organic-content repo (`ops/resources/ella-content-club.md`,
`ops/resources/NATIVE-UI-TEMPLATES.md`).

## Routing (how agents pick this up)

`AGENTS.md` (native ad design rules + reading list), `docs/pipeline-rules.md` §12,
`docs/creative-production-system.md` (Graphic / Screenshot Style, Current Tool Roles) and
`docs/phase-2-static-briefing-workflow.md` Gate 8 all point here. A request like "make an
SBG question-box ad", or a brief with a `native_ui` block, routes to `adc native-ad`
unless the operator selects the iOS/Ella Canva source or its exact treatment.

## Next steps

- More components already measured in organic-content: DM/comment replies, Q&A answer card,
  Copy/Select menu, lock screen.
- SBG: profile picture for the question-box avatar (`--avatar`); real customer questions/DMs.
- Install Inter (OFL) on render machines for closer Apple-UI type.
