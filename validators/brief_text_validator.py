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
"""

from __future__ import annotations

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
