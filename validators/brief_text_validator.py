"""Cross-concept text-leakage validator for creative briefs.

When a brief is generated from a creative-matrix row, its hook / headline /
captions should restate language from that source row — not from a sibling
row. This validator scans a brief against the loaded matrix and emits
soft warnings when:

  - The brief is tied to a `source_matrix_row` but its text doesn't appear
    in that row's `what_people_say` / `static_treatment` / `complaint`
    fields (and isn't a clean paraphrase). Likely the operator forgot to
    update `source_matrix_row` after rewriting.

  - The brief's text matches a DIFFERENT row in the matrix. Likely
    cross-concept leakage — the brief is borrowing language from a
    neighbour, which can flatten the campaign's diversity.

The validator is intentionally non-blocking — it returns a list of
`BriefTextWarning` dataclasses so the caller can choose to log,
display, or escalate. The default save path (`models.loader.save_brief`)
calls it and prints warnings via the rich console without failing the save.

Matching strategy:
  - Lowercase + whitespace-normalize both sides
  - Substring match on 5+ word phrases extracted from the brief
  - Skip generic CTA-style phrases (whitelisted)

This module also exposes `validate_headline_body_premise` — a tiny Claude
call that catches bait-and-switch briefs (e.g. headline promises "3 things
X hides" but the body delivers Y). See that function's docstring for the
prompt + cost notes.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.brief import CreativeBrief

# Phrases too short or too generic to count as a meaningful match.
# These crop up across briefs naturally and would flood the warnings list.
_GENERIC_WHITELIST: frozenset[str] = frozenset({
    "shop now",
    "learn more",
    "trust me on this",
    "you're welcome",
    "ok hear me out",
    "see the mechanism",
})

# Minimum word count for a phrase to be considered "leakage-worthy".
_MIN_PHRASE_WORDS = 5


@dataclass(frozen=True)
class BriefTextWarning:
    """One soft warning emitted by `validate_brief_text`."""

    kind: str           # "missing_in_source" | "cross_concept_leakage"
    message: str        # human-readable
    brief_id: str
    source_row_id: str  # the row this warning relates to (may be "" if no source)
    matched_row_id: str = ""  # the other row, when kind == "cross_concept_leakage"
    phrase: str = ""    # the offending substring


_WORD = re.compile(r"\S+")


def _normalize(text: str) -> str:
    """Lowercase + collapse whitespace for fuzzy matching."""
    return " ".join(text.lower().split())


def _extract_phrases(text: str, min_words: int = _MIN_PHRASE_WORDS) -> list[str]:
    """Return all whitespace-separated phrases of length >= min_words in text.

    Splits on common sentence/clause delimiters first so we don't fabricate
    cross-clause phrases that never appeared together.
    """
    if not text:
        return []
    pieces = re.split(r"[.,;:!?\n\-—]+", text)
    phrases: list[str] = []
    for p in pieces:
        words = _WORD.findall(p)
        if len(words) >= min_words:
            phrase = _normalize(" ".join(words))
            if phrase and phrase not in _GENERIC_WHITELIST:
                phrases.append(phrase)
    return phrases


def _row_text_corpus(row: dict) -> str:
    """Concatenate the matrix-row fields a brief might draw from."""
    fields = [
        row.get("what_people_say", ""),
        row.get("static_treatment", ""),
        row.get("complaint", ""),
        row.get("positioning_angle", ""),
        row.get("hook_or_angle_to_amplify", ""),
        row.get("hook_angle", ""),
    ]
    return " ".join(_normalize(f or "") for f in fields)


def _brief_text_fields(brief: CreativeBrief) -> list[str]:
    """Return the brief's text fields *as a list* (do NOT concatenate).

    Phrase extraction runs over each field independently so we never
    fabricate cross-field phrases (e.g. hook + angle words that never
    appeared together).
    """
    parts: list[str] = []
    if brief.hook:
        parts.append(brief.hook)
    if brief.angle:
        parts.append(brief.angle)
    if brief.pain_point:
        parts.append(brief.pain_point)
    parts.extend(c for c in (brief.benefit_callouts or []) if c)
    if brief.text_layout:
        parts.extend(t.text for t in brief.text_layout if t.text)
    return parts


def _brief_phrases(brief: CreativeBrief) -> list[str]:
    """All leakage-worthy phrases from a brief, extracted per-field."""
    out: list[str] = []
    for field in _brief_text_fields(brief):
        out.extend(_extract_phrases(field))
    # De-dupe while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for p in out:
        if p not in seen:
            seen.add(p)
            deduped.append(p)
    return deduped


def validate_brief_text(
    brief: CreativeBrief,
    matrix_path: Path,
) -> list[BriefTextWarning]:
    """Run cross-concept text checks. Returns [] if no matrix or no source row.

    `matrix_path` should point at the client's `creative_matrix.yaml`.
    If the file is missing or unparseable, returns [].
    """
    if not matrix_path.exists():
        return []

    try:
        with open(matrix_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return []

    rows: list[dict] = []
    for tab_key in ("pain_vs_competitor", "what_they_love", "wishes_gaps", "hook_angles"):
        rows.extend(data.get(tab_key) or [])
    if not rows:
        return []

    row_by_id = {r.get("id"): r for r in rows if r.get("id")}

    source_row_id = (brief.source_matrix_row or "").strip()
    warnings: list[BriefTextWarning] = []

    brief_phrases = _brief_phrases(brief)
    if not brief_phrases:
        return []

    # ─── Check 1: brief tied to a source row that doesn't contain its text ──
    if source_row_id and source_row_id != "new":
        source_row = row_by_id.get(source_row_id)
        if source_row is None:
            warnings.append(BriefTextWarning(
                kind="missing_in_source",
                message=(
                    f"brief.source_matrix_row='{source_row_id}' but no row "
                    f"with that id exists in the matrix."
                ),
                brief_id=brief.brief_id,
                source_row_id=source_row_id,
            ))
        else:
            source_corpus = _row_text_corpus(source_row)
            found_any = any(phrase in source_corpus for phrase in brief_phrases)
            if not found_any:
                warnings.append(BriefTextWarning(
                    kind="missing_in_source",
                    message=(
                        f"brief.source_matrix_row='{source_row_id}' but none "
                        f"of the brief's longer phrases appear in that row. "
                        f"Did you re-target the brief and forget to update "
                        f"source_matrix_row?"
                    ),
                    brief_id=brief.brief_id,
                    source_row_id=source_row_id,
                ))

    # ─── Check 2: brief text matches a DIFFERENT row (leakage) ──────────────
    for row_id, row in row_by_id.items():
        if row_id == source_row_id:
            continue
        row_corpus = _row_text_corpus(row)
        if not row_corpus:
            continue
        for phrase in brief_phrases:
            if phrase in row_corpus:
                warnings.append(BriefTextWarning(
                    kind="cross_concept_leakage",
                    message=(
                        f"phrase from brief appears in matrix row "
                        f"'{row_id}' (brief.source_matrix_row="
                        f"'{source_row_id or 'unset'}'). "
                        f"Possible cross-concept leakage."
                    ),
                    brief_id=brief.brief_id,
                    source_row_id=source_row_id,
                    matched_row_id=row_id,
                    phrase=phrase[:120],
                ))
                break  # one warning per matched row is enough
    return warnings


# ────────────────────────────────────────────────────────────────────────────
# Headline-vs-body premise validator
# ────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PremiseValidationResult:
    """Outcome of a `validate_headline_body_premise` call.

    `aligned=True` means the body fulfills the headline's promise. False
    means the validator detected a bait-and-switch (e.g. headline
    promises "3 things X hides" but body delivers "our trial results").

    `confidence` is the model's own 0.0-1.0 self-rating. Callers should
    typically only act on `aligned=False` when `confidence >= 0.7` —
    lower confidence usually means the headline was ambiguous enough
    that flagging it would just create noise.

    `reasoning` is a one-sentence explanation from the model.

    `skipped` is True when the validator chose not to call the model
    (no headline, no body, missing API key, env-var bypass, etc.); in
    that case `aligned` defaults to True so callers don't warn on it.
    """

    aligned: bool
    confidence: float
    reasoning: str
    skipped: bool = False


# Confidence threshold for emitting a warning. Below this, the model
# isn't sure enough to be worth waking the operator up. Tuned at 0.7
# based on the pain-006 v2 case (which a smart human rates ~0.85
# confident as bait-and-switch).
_PREMISE_WARN_MIN_CONFIDENCE = 0.7

# Env-var bypass — when set to a truthy value, the validator returns
# `skipped=True` immediately. Use this when a brief is intentionally
# provocative (headline frames Y, body proves it via X).
_PREMISE_SKIP_ENV = "ADC_SKIP_PREMISE_CHECK"


def _split_headline_and_body(brief: CreativeBrief) -> tuple[str, str]:
    """Return (headline, body) for premise validation.

    Heuristic:
      - If `body_copy` is non-empty, headline = hook, body = body_copy.
      - Else split `hook` on the first newline: line 0 = headline, the
        rest = body.
      - If hook has no newlines and body_copy is empty, return
        (hook, "") and the caller will skip the check.
    """
    headline = (brief.hook or "").strip()
    body = (brief.body_copy or "").strip()

    if not body and "\n" in headline:
        first, _, rest = headline.partition("\n")
        return first.strip(), rest.strip()

    return headline, body


_PREMISE_SYSTEM = (
    "You are a strict ad-copy editor checking whether a brief's BODY "
    "delivers on the promise its HEADLINE makes.\n\n"
    "Critical rule: 'aligned' is NOT 'talks about the same topic'. It "
    "means the body fulfills the SPECIFIC promise the headline makes.\n\n"
    "Examples:\n"
    "  - Headline: '3 things the probiotic industry hides'. "
    "Aligned body: 3 anti-industry facts. Misaligned body: our trial "
    "results (which are pro-us, not anti-them).\n"
    "  - Headline: 'I quit after 14 days. Here's why.' "
    "Aligned body: 14-day quit story. Misaligned body: a 6-week "
    "transformation story.\n"
    "  - Headline: 'The 5 supplements I take daily'. Aligned body: "
    "list of 5 supplements. Misaligned body: a single product pitch.\n\n"
    "Return strictly: {\"aligned\": bool, \"confidence\": float (0.0-1.0), "
    "\"reasoning\": str (one short sentence)}. No prose outside JSON."
)


def _build_premise_prompt(headline: str, body: str) -> str:
    """Compact user prompt — kept short to hold the per-call cost <$0.001."""
    return (
        f"HEADLINE:\n{headline}\n\n"
        f"BODY:\n{body}\n\n"
        "Does the body deliver on the specific promise the headline makes? "
        "Reply with JSON only."
    )


def _parse_premise_response(raw: str) -> PremiseValidationResult:
    """Parse the Claude response into a PremiseValidationResult.

    Best-effort — if the model returns malformed JSON or unexpected
    fields, returns `skipped=True` with the raw text in `reasoning` so
    the operator can investigate but the brief save still succeeds.
    """
    text = (raw or "").strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return PremiseValidationResult(
            aligned=True,
            confidence=0.0,
            reasoning=f"premise model returned non-JSON: {text[:160]}",
            skipped=True,
        )
    aligned = bool(data.get("aligned", True))
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))
    reasoning = str(data.get("reasoning", "")).strip()
    return PremiseValidationResult(
        aligned=aligned, confidence=confidence, reasoning=reasoning
    )


def validate_headline_body_premise(
    brief: CreativeBrief,
) -> PremiseValidationResult:
    """Check whether the brief's body fulfills the headline's promise.

    Catches bait-and-switch briefs the cross-concept leakage validator
    misses — e.g. pain-006 v2 (headline: "3 receipts the probiotic
    industry hides", body: our trial results). The body's text DID come
    from the source row, so leakage validation passed; the premise
    DIDN'T match the headline's claim, which only this check catches.

    Returns a PremiseValidationResult. Callers should warn when
    `aligned=False AND confidence >= 0.7 AND not skipped`. Below 0.7 the
    model isn't sure enough to be worth a warning.

    The check is skipped (returns `skipped=True`, `aligned=True`) when:
      - the brief has no usable headline or body
      - the `ADC_SKIP_PREMISE_CHECK` env var is truthy
      - the `claude_complete` call raises (network, auth, parse, etc.)

    Cost target: <$0.001 per save (~150 input tokens, ~80 output, single
    shot on claude-sonnet-4-6).
    """
    if os.environ.get(_PREMISE_SKIP_ENV, "").lower() in {"1", "true", "yes", "on"}:
        return PremiseValidationResult(
            aligned=True,
            confidence=0.0,
            reasoning=f"skipped via {_PREMISE_SKIP_ENV}",
            skipped=True,
        )

    headline, body = _split_headline_and_body(brief)
    if not headline or not body:
        return PremiseValidationResult(
            aligned=True,
            confidence=0.0,
            reasoning="no separable headline + body to compare",
            skipped=True,
        )

    try:
        # Local import so the rest of this module stays importable in
        # environments without the anthropic SDK on the path (tests that
        # only exercise the leakage validator, for example).
        from strategy.llm import claude_complete

        prompt = _build_premise_prompt(headline, body)
        raw = claude_complete(prompt, system=_PREMISE_SYSTEM, max_tokens=120)
    except Exception as e:
        return PremiseValidationResult(
            aligned=True,
            confidence=0.0,
            reasoning=f"premise check raised {type(e).__name__}: {str(e)[:120]}",
            skipped=True,
        )

    return _parse_premise_response(raw)


def should_warn_on_premise(result: PremiseValidationResult) -> bool:
    """Return True iff the result is a confident misalignment.

    Pulled out so the threshold lives in one place and the save-path
    hook stays a one-liner.
    """
    return (
        not result.skipped
        and not result.aligned
        and result.confidence >= _PREMISE_WARN_MIN_CONFIDENCE
    )
