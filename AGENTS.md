# AGENTS.md

Instructions for AI coding agents (Codex, Claude Code, OpenCode, Cursor, etc.) working
in this repo. Read this before making changes.

## What this project is

AdCreatives is an AI-powered ad creative pipeline for an ad agency running multiple
client accounts. Two-phase model:

- **Phase 1 — Strategy.** Brand research → personas → products → offers → strategy
  matrix → psychology profiles → creative briefs. Eleven steps, not just one CLI call.
  Outputs live in `clients/<slug>/`.
- **Phase 2 — Image generation.** Briefs → fal.ai prompts → rendered PNGs. Outputs
  live in `ai-ads/<slug>/` (gitignored, regenerable).

Read `docs/pipeline-rules.md` before touching the pipeline. It encodes hard-won
operating rules (one product per run for multi-SKU brands, persona awareness
calibration, gap-map filters, no-competitor-naming) — do not relax them without
explicit user discussion.

## Quickstart

- Python **3.11+**.
- `pip install -e .` from the repo root (or `pip install -e ".[dev]"` for tests).
- `.env` at repo root supplies API keys (fal, OpenAI, Anthropic, Exa, Apify, Google,
  `HF_CREDENTIALS`). Not committed. The CLI auto-loads it via `_bootstrap_env_from_dotenv`.
- CLI entry: `adc --help` (defined in `cli.py`).
- Dashboard: `adc dashboard` (Streamlit, reads local files only, no API calls).

## Higgsfield integration

Higgsfield AI is wired into both the brief→image pipeline (`--engine
higgsfield-soul`) and the agent's own toolset. Three layers:

1. **Runtime REST client** at `generators/higgsfield_client.py` — used by
   `adc remix-images`, `adc remix-refine`, and `adc generate` when
   `--engine higgsfield-soul` is set. Auth via `HF_CREDENTIALS` in `.env`.
   This is the path the dashboard buttons call. Do NOT refactor it to shell
   out to the CLI — direct HTTP is faster and has retry control.
2. **Higgsfield CLI** at `higgsfield` (and `hf`) on PATH — for agent
   management tasks: list trained Souls, check credits, train new Souls,
   one-off generations. Install: `npm install -g @higgsfield/cli` (or the
   release binary if npm postinstall fails on Windows). Auth:
   `higgsfield auth login` (browser device flow).
3. **Skill pack** under `.agents/skills/` (gitignored, per-machine) — four
   slash commands installed via `npx skills add higgsfield-ai/skills`:
   `/higgsfield-generate`, `/higgsfield-soul-id`,
   `/higgsfield-product-photoshoot`, `/higgsfield-marketplace-cards`. They
   wrap the CLI with structured prompts. Prefer these over the deprecated
   Higgsfield MCP connector.

The previous Higgsfield Claude.ai MCP connector (`mcp.higgsfield.ai/mcp`)
is being phased out in favor of the CLI + skills. Per-persona Soul
Characters are tracked under each avatar YAML's `higgsfield:` block
(`soul_id`, `soul_status`).

## Repo layout

| Path | Purpose |
|---|---|
| `cli.py` | All `adc` commands (Click). One file by design. |
| `strategy/` | Phase 1 logic: research, personas, matrix, status, costs |
| `generators/` | Prompt composers, fal.ai client, reference analyzer |
| `validators/` | Brand compliance, platform specs, copy limits |
| `models/` | Pydantic schemas |
| `dashboard/app.py` | Streamlit web dashboard |
| `clients/<slug>/` | Per-client strategy data (YAML + MD). Mostly gitignored — only the listed test clients in `.gitignore` are committed. |
| `ai-ads/<slug>/` | Generated PNGs + prompt txts. Gitignored, regenerable. |
| `prompts/skills/` | LLM system-prompt skills, loaded at runtime |
| `references/` | Reference ad images, curated by archetype |
| `docs/` | Operating rules and design docs — read these |
| `scripts/` | One-off maintenance scripts (backfills, uploads) |
| `tests/` | pytest suite |

## Conventions

- **Immutability.** Return new objects; do not mutate inputs.
- **File size.** 200–400 lines typical, hard cap 800. `cli.py` is the exception.
- **Function size.** Aim under 50 lines.
- **Paths.** Use `pathlib.Path` everywhere. The repo runs on Windows and Unix.
- **Types.** Type hints on public functions. Pydantic for structured payloads.
- **Errors.** Handle at the boundary, fail fast with a clear message. Don't swallow.
- **Secrets.** Never hardcode. `.env` is the only source. Never commit it.
- **Comments.** Default to none. Add one only when the *why* is non-obvious.
- **Backwards-compat shims.** Don't add them for code that isn't shipped.
- **Em-dashes are banned in ad copy output.** They are fine in repo docs and comments.

## Cost awareness

This project spends real money on every `adc generate`, `adc research`, `adc prompts`,
`adc mine-voc`, `adc research-amazon`, and `adc research-competitors` run.

- **Never run image generation, Amazon scraping, or large research jobs without
  confirming with the user first.** Quote the expected cost from the cost log if
  available (`clients/<slug>/.cost-log.jsonl`) or estimate before asking.
- Local-only commands (`adc status`, `adc dashboard`, `adc list-clients`,
  `adc list-templates`, `adc menu`, `adc show-prompt`) are free — run freely.

## Native ad design rules (when working on visual templates or ad copy)

These are hard rules. If you're editing templates, brief outputs, or prompt copy:

- No em-dashes in ad copy.
- Sourcing rule applies (cite review sources when claims appear in copy).
- No UI chrome in image ads (no fake browser bars, fake DM overlays unless the
  template is explicitly that format).
- Pill sizing matches the visual format spec.
- Wild brand aesthetic where applicable.

Full design philosophy and template work belongs in the relevant style files under
`styles/` and `prompts/skills/`. Do not invent new rules — confirm with the user.

## Common commands

Phase 1 (strategy):
```
adc init-client --name <slug>
adc research --client <slug> --url <homepage>
adc personas --client <slug>
adc product-deep-dive --client <slug>
adc offers --client <slug>
adc strategy-matrix --client <slug>
adc profile-psychology --client <slug>
adc research-competitors --client <slug>
adc research-amazon --client <slug>
adc analyze-gaps --client <slug>
adc brief --client <slug> --product <id> --angles 6
```

Phase 2 (image gen):
```
adc menu --client <slug>
adc prompts --client <slug> --pick 1,2,3
adc generate --client <slug> --pick 1,2,3
```

Status / browsing (free, local):
```
adc status --client <slug>
adc dashboard
adc list-clients
adc list-templates --client <slug>
```

## Git

- Conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`, `docs:`, `test:`,
  `perf:`, `ci:`.
- No co-author / attribution footer.
- Never commit `.env`, `ai-ads/`, `__pycache__/`, `clients/<new-slug>/` for non-test
  clients, or any `*.png` outside `references/`.
- Before committing: check `git status` for accidentally-tracked binaries.

## Testing

- `pytest` from the repo root. Target 80%+ coverage on new code.
- Tests live under `tests/`. Mirror module layout when adding new ones.
- TDD for new behavior: failing test first, then minimal implementation.

## Things to never do

- Run paid commands (`generate`, `research-*`, `mine-voc`) without user confirmation.
- Commit secrets, generated images, or per-client working dirs that aren't in the
  whitelist.
- Use destructive git operations (`reset --hard`, force push, branch delete) without
  asking.
- Relax pipeline rules (`docs/pipeline-rules.md`) silently — surface the trade-off.
- Add features beyond what was asked. Bug fixes don't need cleanup; one-shot tasks
  don't need helpers.

## When the user pastes an API key in chat

Remind them to rotate it after the session. Do not store it in code, comments, or
commit history.

## Pointers to other docs

- `README.md` — user-facing overview and full quickstart
- `docs/pipeline-rules.md` — pipeline operating rules (read before pipeline work)
- `dashboard/app.py` — Streamlit web view (run via `adc dashboard`)
- `pyproject.toml` — deps and optional extras
