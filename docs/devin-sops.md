# Devin's SOPs — Simple Step-by-Step Guides

Every job you'll do, one page each, in plain words. When you want more
detail, the deep versions live in the two canvases in #ad-library, the
7-week plan, and `docs/experiments-e1-e7.md`.

## SOP 0 — The big picture (read this first)

We study other companies' ads to learn WHY they work. A robot (the agent
in Slack) writes the first draft of that study. The draft is called a
**card**. Your job is to check the card, fix what's wrong, and approve it.
Good cards teach our whole system to make better ads.

The one rule we never break: **we never copy another company's ad.** We
take the *idea* that makes it work. We never take their person, their
exact words, or their look. Every card has a "Steal" line (what we may
reuse) and an "Avoid" line (what we must never touch).

And one motto: **being right beats being fast.** Thirty correct cards are
worth more than sixty sloppy ones. Nobody will ever be upset that you
went slower to get it right.

## SOP 1 — Add an ad to the library

1. Open Foreplay. Set the filter: Display Format → **Image** (we don't do
   videos yet).
2. Pick a strong ad. Strong usually means it has been running a long time
   or has many versions — that means it's making money.
3. Copy the ad's long number (the ad id).
4. Go to #ad-library in Slack. Paste the number as its own message. Send.
5. Wait. The card usually shows up in about a minute. Uploaded pictures
   can take up to 3 minutes.
6. Read the whole card. Every line. Slow down extra on any line with a ⚠️
   — that mark means the robot is not sure about that line.
7. Now pick ONE of three replies (always reply in that ad's thread):
   - Everything right → reply `approve`
   - Something wrong → fix it (SOP 3)
   - You truly can't tell → reply `escalate` (SOP 4)

Rules: one ad per message. Never approve a card you didn't fully read.

## SOP 2 — What the words on a card mean

- **Format** — what kind of ad it looks like (a receipt, a meme, a
  product photo, a list...).
- **Hook type** — the trick the first line uses to make you stop
  scrolling (a question, a warning, a bold claim...).
- **Mechanic** — the most important one. It's the *move* the ad makes so
  you end up believing it. Example: showing two things side by side and
  letting YOU notice the difference — that move is called "The Contrast
  Without Comment."
- **Scan path** — where your eyes go, in order, when you look at the ad.
- **Proof** — the part that makes the claim feel true (real prices, a
  review, a demo).
- **Product role** — how big a part the product plays: hero (the star),
  prop (in the scene), reveal (shows up at the end), absent (not shown).
- **Awareness stage** — how much the shopper already knows, from
  "doesn't know they have a problem" to "ready to buy, just needs a
  push."
- **Why it works** — the one biggest reason this ad persuades.
- **Steal / Avoid** — what we may reuse / what we must never copy.

Every allowed choice for every field is in the **Creative Taxonomy**
canvas at the top of #ad-library. And you can always ask the robot right
in the channel: "what's The Trojan Horse mechanic?" It will explain.
That's part of its job.

## SOP 3 — Fix a wrong field

1. In the ad's thread, reply with the fix, like this:
   `mechanic = The Reframe`
2. More than one fix? Use commas:
   `mechanic = The Reframe, hook = warning`
3. Plain English works too: "the hook is more of a warning than a bold
   claim."
4. The robot posts the card again with your fix. Check it.
5. If the robot asks "Did you mean ...?" — answer it. It's making sure it
   understood you.
6. When the card is right, reply `approve`.

Already approved it and THEN spotted a mistake? No problem. Reply in the
same thread: `update AD-012: hook = warning` (use the card's real
number).

## SOP 4 — Escalate when you're not sure

If you've really tried and still can't decide, reply `escalate`. The card
goes to the Creative Strategist to finish.

This is a GOOD move, not a failure. Guessing is the only wrong answer
here — a wrong card quietly teaches the whole system the wrong lesson.
Escalating is you protecting the library.

## SOP 5 — When the robot says no (or nothing)

- **"This ad is a VIDEO"** → skip it. Videos are not our job yet. Pick a
  different ad.
- **"No downloadable image"** → Foreplay won't hand over the picture.
  Open the ad in Foreplay, save the image yourself, then upload it in
  #ad-library with one line like: `Brand: Huel | Link: <the ad's link>`
- **The robot posts an error** → do NOT post the same ad again. If the
  error doesn't tell you what to do, copy it and send it to Mitchell.
- **Nothing happens for 3 minutes** → ask in the channel: "did you see my
  ad?" Don't re-post it — re-posting makes duplicate cards.

## SOP 6 — Check on the library

Type `library status` in #ad-library. You'll see:

- how many cards we have
- which cards are waiting on the strategist
- a grid showing which idea-combinations have ZERO cards yet

Those empty spots are your shopping list — try to find ads that fill
them.

## SOP 7 — Run an experiment (the E's)

Each experiment (E1, E2...) has its own page in the protocols doc with
exact steps. But they all follow the same shape:

1. Read that E's page first. It tells you what to compare.
2. Gather your pieces: the card, its ad image, our product picture.
3. Make the ad each way being compared — and make it **3 times each
   way**. The AI is random, so one try proves nothing.
4. Grade every output with the scorecard (SOP 8).
5. Average the 3 scores for each way. Highest average wins. If it's a
   tie, the way with fewer steps wins (cheaper and faster).
6. Write one row in the experiment log (SOP 10).
7. Teach the agent the winner (SOP 9). An experiment isn't done until the
   agent knows the answer.

Golden rule: change ONE thing at a time. If you change two things, you
can't know which one mattered.

## SOP 8 — Grade an output (the scorecard)

Five questions. Score each 0, 1, or 2 (0 = no, 1 = sort of, 2 = yes).
Add them up for a score out of 10.

1. Does the ad still do the card's main trick — the mechanic, with its
   proof?
2. Do your eyes travel in the card's order (the scan path)?
3. Is the product as big or small a deal as the card says (its role)?
4. Is it fully OURS — no copied person, words, or brand look?
5. Is it clean — normal hands, sharp edges, undamaged labels, no weird
   AI spots?

One trap: the headline text is added by our tools AFTER the AI image is
made. Don't take points off the AI step for text it was never supposed to
draw.

## SOP 9 — Teach the agent a lesson

When an experiment picks a winner, the agent has to learn it. Same week,
every time:

1. Write the lesson as ONE clear sentence. Example: "For receipt-style
   remakes: two steps — remake with our product first, restyle second.
   Never combined."
2. Tell the agent to add that rule to its instructions.
3. The agent must SHOW you the exact words it added. If it just says
   "got it," say: "show me the updated instruction." No shown change =
   nothing was learned.
4. Prove it: open a brand-new chat. Give a fresh task. No hints. Does the
   agent do it the winning way on its own? If not, reword the rule and
   try again.
5. Re-run the standard test tasks (S1–S4) to make sure the new rule
   didn't break an old lesson. If it did, make the rule narrower — "for
   receipt-style..." instead of "always..."
6. Log it: the lesson, the proof link, verified ✅, regression ✅.

## SOP 10 — Log your work

- **Hours**: write them in the tracker the SAME DAY you work them. Send
  them to VFC weekly. Your stipend depends on this being right.
- **Experiments**: one row per run set — which experiment and variant,
  which card, the setup, the 3 output links, the average score, who won,
  why, and whether it's been taught ✅.
- **Anything you learn about Higgsfield** goes in the shared findings
  log — Wasif and the production team read it too.

## SOP 11 — When you're stuck

The 30-minute rule: stuck for 30 minutes → ask. In Slack, out loud.

- Word or field you don't understand → ask the robot in #ad-library.
- Everything else → ask Mitchell or the strategist.

Asking fast is a skill here, not a weakness. The only bad question is the
one you sat on for two days.
