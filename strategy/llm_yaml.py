"""Shared helpers for parsing LLM-emitted YAML.

Extraction models occasionally emit near-valid YAML (misindented commentary
keys, unquoted parentheticals after quoted scalars). These helpers implement
the cheap half of the recovery ladder: strip fences, and on a parse error ask
the model to fix its own output (re-reading ~6K tokens of its own document
instead of the full source corpus).

`complete_fn` is injected by the caller so each module's `claude_complete`
binding (and any test monkeypatch on it) stays authoritative.
"""

from __future__ import annotations

from typing import Callable

import yaml

YAML_REPAIR_PROMPT = """The following YAML document failed to parse.

PARSE ERROR:
{error}

BROKEN YAML:
{broken}

Re-emit the ENTIRE document as valid YAML. Rules:
- Fix only the syntax; do not change, add, or drop content that already parses.
- Any scalar containing quotes, colons, or parentheses must be properly quoted
  or a block scalar.
- Do not add keys that were not requested (no commentary, no analyst notes).
- Output valid YAML only, no markdown fences."""


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text


def try_repair_yaml(
    broken: str,
    err: yaml.YAMLError,
    complete_fn: Callable[..., str],
) -> dict | None:
    """One LLM pass asking for the same document with the syntax fixed.

    Returns the parsed mapping, or None if the repair itself fails to parse
    (callers decide whether to re-extract or raise)."""
    fixed = complete_fn(
        YAML_REPAIR_PROMPT.format(error=err, broken=broken),
        max_tokens=8192,
    )
    try:
        parsed = yaml.safe_load(strip_fences(fixed))
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None
