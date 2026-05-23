---
name: voice
description: Load the AdCreatives copywriting voice profile and apply it to any copy I draft from here on. Use this when the user wants me to write headlines, callouts, CTAs, ad copy, hooks, or any other on-image or campaign text in the brand's voice — instead of falling back to generic marketing-speak.
---

# Voice — AdCreatives copywriting voice profile

When invoked, **this skill activates the brand voice profile** for any copy I draft in the remainder of the session. The source of truth is `library/voice.md` at the repo root — the same file the Python remix code reads at runtime.

## What to do when this skill fires

1. **Read `library/voice.md`** (the full file). If it doesn't exist, fall back to `clients/<slug>/voice.md` if the user mentioned a client. If neither exists, tell the user and stop.

2. **Briefly acknowledge what loaded** — under 100 words. List the count of signature moves, the count of forbidden words, and one example to confirm the voice is active. Example:

   > Loaded voice profile: 10 signature moves, ~30 forbidden words, ~80 raw examples. Active. (Sample: "Bloat clears. Not 'Reduces bloating.'")

3. **Ask what the user wants to draft.** Don't preempt — they might want a headline, a callout pack, a CTA, a full ad concept, or a rewrite of existing copy.

4. **Apply the voice to everything you draft from here.** This is sticky for the rest of the session unless the user says otherwise. Specifically:
   - Use the **signature moves** in `library/voice.md` (negation-as-identity, three-beat period stops, rhyme, customer-quote headlines, cross-outs, "X — gone" pattern, etc.)
   - Reject every word on the **forbidden vocabulary kill-list** ("supports", "helps with", "premium", "actually", "finally", etc.). If a draft contains one, rewrite before showing it.
   - Lean on the **raw example banks** for the specific slot type (headline / pain / benefit / CTA / customer quote).

5. **When you write copy, show your work briefly** — for each line, indicate which move/pattern it's using (e.g. "Headline: three-beat period stop"). This makes feedback faster.

## Important: what this skill does NOT do

- It does NOT modify the voice profile file. To edit the voice, the user edits `library/voice.md` directly (or adds a per-client override at `clients/<slug>/voice.md`). The Python remix code re-reads the file on each run, so changes take effect immediately.

- It does NOT trigger the Python `adc remix` pipeline. This skill is for **manual drafting in Claude Code chat**. The Python pipeline reads the same `library/voice.md` automatically — no skill needed for batch runs.

- It does NOT override safety/security rules. Voice is a style layer, not a behavior modifier.

## Why this exists

The AdCreatives Python pipeline (`adc remix`, `adc generate`, `adc edit`) already injects `library/voice.md` into its LLM calls automatically — so batch-generated copy is in voice without any human in the loop. But there are moments when the user wants to **manually draft a line, brainstorm a hook, or rewrite a callout in this chat** — and the default Claude behavior drifts toward generic marketing-speak. This skill ensures that in those moments, I'm working from the same source of truth as the automated pipeline.

One file. Two consumers. Consistent voice across both.

## File precedence

```
clients/<slug>/voice.md     ← per-client override (preferred when user mentions a client)
library/voice.md            ← global default (fallback)
```

If the user mentions a specific client (e.g. "draft a headline for secondkind-bold"), check for the per-client file first.
