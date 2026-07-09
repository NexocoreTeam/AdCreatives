"""Ad Reference Library card schema — validation, corrections, sidecar IO.

A "card" is the structured breakdown of one competitor ad: what format it
uses, which hook tactic opens it, which creative mechanic makes it land,
where the eye travels, what makes it believable, and the steal/avoid lines
that keep our rebuilds brand-owned. Cards live as YAML sidecars next to
their image in `references/swipe/analyzed/` — the same layout the rest of
the swipe library uses, so downstream matching can consume them.

Flow: `adc analyze` produces a DRAFT (dict + issues, saved under .drafts/),
a human reviews it in Slack (via OpenClaw) or the terminal, corrections are
applied with fuzzy enum matching, and `adc library save` validates strictly
and writes the sidecar. Nothing reaches the library without an explicit
approve/escalate — that rule is enforced here by save_card requiring a
status, and upstream by the OpenClaw runbook.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from strategy.taxonomy import (
    AWARENESS_STAGES,
    CONFIDENCE_LEVELS,
    MEDIA_TYPES,
    PRODUCT_ROLES,
    Taxonomy,
    match_enum,
)

LIBRARY_ROOT = Path("references/swipe/analyzed")
DRAFTS_DIRNAME = ".drafts"

STATUS_APPROVED = "approved"
STATUS_NEEDS_STRATEGIST = "needs-strategist"
STATUSES = (STATUS_APPROVED, STATUS_NEEDS_STRATEGIST)

# Fields the vision model must return. Order doubles as display order.
CONFIDENCE_FIELDS = ("format", "hook_type", "mechanic", "awareness_stage", "product_role")
REASONING_FIELDS = ("mechanic", "awareness_stage")

# Loose reviewer names → canonical field names ("awareness = …" etc.)
FIELD_ALIASES: dict[str, str] = {
    "awareness": "awareness_stage",
    "stage": "awareness_stage",
    "hook": "hook_type",
    "secondary": "secondary_mechanic",
    "proof": "proof_element",
    "role": "product_role",
    "signal": "proxy_signal",
    "culture": "cultural_note",
    "note": "cultural_note",
    "why": "why_it_works",
}

TEXT_FIELDS = (
    "brand", "source_link", "proxy_signal", "proof_element",
    "why_it_works", "cultural_note", "steal", "avoid",
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class ValidationResult:
    """Normalized card data plus everything a reviewer needs to see."""

    card: dict[str, Any]
    issues: list[str] = field(default_factory=list)      # block strict save
    warnings: list[str] = field(default_factory=list)    # surfaced, non-blocking

    @property
    def ok(self) -> bool:
        return not self.issues


def _enum_targets(tax: Taxonomy, media_type: str) -> dict[str, list[str]]:
    return {
        "format": tax.format_names(media_type),
        "hook_type": tax.hook_type_names(),
        "mechanic": tax.mechanic_names(),
        "secondary_mechanic": tax.mechanic_names(),
        "awareness_stage": list(AWARENESS_STAGES),
        "product_role": list(PRODUCT_ROLES),
    }


def _is_other(value: str) -> bool:
    """`Other (two-word name)` is allowed for format and mechanic."""
    return bool(re.match(r"^other\b", value.strip(), re.IGNORECASE))


def validate_card(data: dict[str, Any], tax: Taxonomy) -> ValidationResult:
    """Normalize a model draft (or corrected card) against the taxonomy.

    Lenient by design: invalid enum values are KEPT (flagged as issues and
    confidence-dropped to low) so the reviewer sees what the model actually
    said instead of a silently blanked field. `save_card` refuses to write
    while issues remain.
    """
    card = dict(data)
    issues: list[str] = []
    warnings: list[str] = []

    media_type = str(card.get("media_type") or "static").strip().lower()
    if media_type not in MEDIA_TYPES:
        issues.append(f"media_type: '{media_type}' must be one of {MEDIA_TYPES}")
        media_type = "static"
    card["media_type"] = media_type

    targets = _enum_targets(tax, media_type)
    confidence = dict(card.get("field_confidence") or {})

    for fname, allowed in targets.items():
        raw = card.get(fname)
        if fname == "secondary_mechanic" and not raw:
            card[fname] = None  # optional — most ads have one mechanic
            continue
        raw = str(raw or "").strip()
        if not raw:
            issues.append(f"{fname}: missing")
            continue
        matched, exact = match_enum(raw, allowed)
        if matched:
            card[fname] = matched
            if not exact:
                warnings.append(f"{fname}: '{raw}' matched to '{matched}'")
        elif fname in ("format", "mechanic") and _is_other(raw):
            card[fname] = raw
        elif fname == "secondary_mechanic":
            # Optional enrichment field — an unnamed/Other secondary can't be
            # queried or matched downstream, so drop it rather than block the
            # save over optional data. The warning keeps it reviewable.
            card[fname] = None
            warnings.append(
                f"secondary_mechanic: '{raw}' isn't a named mechanic — dropped "
                "(re-add with a correction if it should stay)")
        else:
            issues.append(f"{fname}: '{raw}' is not in the allowed values")
            if fname in CONFIDENCE_FIELDS:
                confidence[fname] = "low"

    if card.get("secondary_mechanic") and card["secondary_mechanic"] == card.get("mechanic"):
        card["secondary_mechanic"] = None
        warnings.append("secondary_mechanic: same as primary — dropped")

    scan = card.get("scan_path")
    if isinstance(scan, str):
        scan = [s.strip() for s in re.split(r"→|->|,", scan) if s.strip()]
    if not isinstance(scan, list) or not (2 <= len(scan) <= 5):
        issues.append("scan_path: needs an ordered list of 2-5 elements")
        scan = scan if isinstance(scan, list) else []
    card["scan_path"] = [str(s).strip() for s in scan]

    for fname in TEXT_FIELDS:
        card[fname] = str(card.get(fname) or "").strip()
    for fname in ("proof_element", "why_it_works", "steal", "avoid"):
        if not card[fname]:
            issues.append(f"{fname}: missing — every card needs an honest {fname} line")
    card["brand"] = card["brand"] or "unknown"
    card["proxy_signal"] = card["proxy_signal"] or "unknown"
    card["cultural_note"] = card["cultural_note"] or "none"
    if len(card["why_it_works"].split()) > 45:
        warnings.append("why_it_works: over 40 words — trim to the single strongest reason")

    for fname in CONFIDENCE_FIELDS:
        level = str(confidence.get(fname) or "low").strip().lower()
        confidence[fname] = level if level in CONFIDENCE_LEVELS else "low"
    card["field_confidence"] = confidence

    reasoning = dict(card.get("reasoning") or {})
    for fname in REASONING_FIELDS:
        reasoning[fname] = str(reasoning.get(fname) or "").strip()
    card["reasoning"] = reasoning

    return ValidationResult(card=card, issues=issues, warnings=warnings)


# ─── Reviewer corrections ────────────────────────────────────────────────────


@dataclass
class CorrectionReport:
    applied: list[str] = field(default_factory=list)
    fuzzy: list[str] = field(default_factory=list)     # applied, but inexact — confirm
    rejected: list[str] = field(default_factory=list)  # not applied


def _match_field_name(raw: str, tax: Taxonomy) -> str | None:
    norm = raw.strip().lower().replace(" ", "_").replace("-", "_")
    known = set(_enum_targets(tax, "video")) | set(TEXT_FIELDS) | {"scan_path", "media_type"}
    if norm in known:
        return norm
    if norm in FIELD_ALIASES:
        return FIELD_ALIASES[norm]
    matched, _ = match_enum(norm, list(known))
    return matched


def parse_corrections(text: str) -> list[tuple[str, str]]:
    """Parse `field = value` pairs, one per line or comma-separated.

    Commas only split when the next segment looks like another `field =`
    pair, so values containing commas survive.
    """
    pairs: list[tuple[str, str]] = []
    for line in text.splitlines():
        parts = re.split(r",(?=\s*[\w\s-]{1,30}=)", line)
        for part in parts:
            if "=" not in part:
                continue
            fname, _, value = part.partition("=")
            if fname.strip() and value.strip():
                pairs.append((fname.strip(), value.strip()))
    return pairs


def apply_corrections(
    card: dict[str, Any], corrections: str, tax: Taxonomy,
) -> tuple[dict[str, Any], CorrectionReport]:
    """Apply reviewer corrections with fuzzy field + enum matching.

    Every applied correction resets that field's confidence to high (a human
    made the call) and is reported so the caller can re-post the updated card.
    Unmatchable fields or values are REJECTED loudly, never guessed into the
    wrong category.
    """
    updated = dict(card)
    report = CorrectionReport()
    targets = _enum_targets(tax, str(card.get("media_type") or "static"))
    confidence = dict(updated.get("field_confidence") or {})
    reasoning = dict(updated.get("reasoning") or {})

    for raw_field, raw_value in parse_corrections(corrections):
        fname = _match_field_name(raw_field, tax)
        if not fname:
            report.rejected.append(f"{raw_field}: unknown field")
            continue
        if fname == "secondary_mechanic" and raw_value.strip().lower() in (
                "none", "null", "-", "no"):
            updated[fname] = None
            report.applied.append("secondary_mechanic = none")
            continue
        if fname in targets:
            matched, exact = match_enum(raw_value, targets[fname])
            if matched is None and fname in ("format", "mechanic") and _is_other(raw_value):
                matched, exact = raw_value, True
            if matched is None:
                allowed_hint = ", ".join(targets[fname][:8])
                report.rejected.append(
                    f"{fname}: '{raw_value}' matches nothing (allowed starts: {allowed_hint}…)")
                continue
            updated[fname] = matched
            line = f"{fname} = {matched}"
            (report.applied if exact else report.fuzzy).append(
                line if exact else f"{line} (from '{raw_value}' — confirm)")
        elif fname == "scan_path":
            updated[fname] = [s.strip() for s in re.split(r"→|->|,", raw_value) if s.strip()]
            report.applied.append(f"scan_path = {' → '.join(updated[fname])}")
        else:
            updated[fname] = raw_value
            report.applied.append(f"{fname} = {raw_value}")
        if fname in CONFIDENCE_FIELDS:
            confidence[fname] = "high"
        if fname in REASONING_FIELDS and updated.get(fname) != card.get(fname):
            # The model's reasoning explained ITS choice — keeping it under a
            # human-corrected value reads as contradiction on the card.
            reasoning[fname] = "(corrected by reviewer)"

    updated["field_confidence"] = confidence
    updated["reasoning"] = reasoning
    return updated, report


# ─── Display ─────────────────────────────────────────────────────────────────


def render_display(card: dict[str, Any], *, card_id: str = "", status: str = "") -> str:
    """Slack-ready card text. Low-confidence fields get a ⚠️ prefix."""
    conf = card.get("field_confidence") or {}
    reasoning = card.get("reasoning") or {}

    def flag(fname: str) -> str:
        return "⚠️ " if conf.get(fname) == "low" else ""

    title = f"🃏 *AD CARD — {card_id or 'DRAFT'}* ({card.get('brand', 'unknown')})"
    if status:
        title += f" [{status}]"
    lines = [
        title,
        "─────────────────────",
        f"{flag('format')}*Format:* {card.get('format', '?')}",
        f"{flag('hook_type')}*Hook type:* {card.get('hook_type', '?')}",
        f"{flag('mechanic')}*Mechanic:* {card.get('mechanic', '?')}",
    ]
    if reasoning.get("mechanic"):
        lines.append(f"   _{reasoning['mechanic']}_")
    if card.get("secondary_mechanic"):
        lines.append(f"*Secondary mechanic:* {card['secondary_mechanic']}")
    stage = card.get("awareness_stage", "?")
    lines.append(f"{flag('awareness_stage')}*Awareness stage:* "
                 f"{AWARENESS_STAGES.get(stage, stage)}")
    if reasoning.get("awareness_stage"):
        lines.append(f"   _{reasoning['awareness_stage']}_")
    lines += [
        f"{flag('product_role')}*Product role:* {card.get('product_role', '?')}",
        f"*Scan path:* {' → '.join(card.get('scan_path') or [])}",
        f"*Proof:* {card.get('proof_element', '')}",
        f"*Why it works:* {card.get('why_it_works', '')}",
        f"*Cultural note:* {card.get('cultural_note', 'none')}",
        f"✅ *Steal:* {card.get('steal', '')}",
        f"🚫 *Avoid:* {card.get('avoid', '')}",
        f"*Signal:* {card.get('proxy_signal', 'unknown')}",
        "─────────────────────",
    ]
    return "\n".join(lines)


# ─── Sidecar IO ──────────────────────────────────────────────────────────────


def _library_root(root: Path | None = None) -> Path:
    return (root / LIBRARY_ROOT) if root else LIBRARY_ROOT


def drafts_dir(root: Path | None = None) -> Path:
    return _library_root(root) / DRAFTS_DIRNAME


def next_card_id(root: Path | None = None) -> str:
    """Next sequential AD-### id, scanning existing sidecars. Ids are
    assigned at save time so abandoned drafts never burn numbers."""
    lib = _library_root(root)
    highest = 0
    if lib.exists():
        for path in lib.glob("ad-*.yaml"):
            m = re.match(r"ad-(\d+)", path.stem)
            if m:
                highest = max(highest, int(m.group(1)))
    return f"AD-{highest + 1:03d}"


def card_paths(card_id: str, root: Path | None = None) -> tuple[Path, list[Path]]:
    """(sidecar_path, existing image paths) for a card id."""
    lib = _library_root(root)
    stem = card_id.lower()
    return lib / f"{stem}.yaml", list(lib.glob(f"{stem}.[jp][pn]g"))


def save_card(
    card: dict[str, Any],
    *,
    status: str,
    image_path: Path | None,
    tax: Taxonomy,
    provenance: dict[str, Any],
    added_by: str = "",
    strategist_notes: str = "",
    root: Path | None = None,
) -> tuple[str, Path]:
    """Validate strictly and write the card sidecar (+ image) to the library.

    Raises ValueError on validation issues or a bad status — the caller
    (CLI / OpenClaw) reports the problem instead of a broken card landing
    in the library.
    """
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, got '{status}'")
    result = validate_card(card, tax)
    if not result.ok:
        raise ValueError("Card has unresolved issues:\n  - " + "\n  - ".join(result.issues))

    lib = _library_root(root)
    lib.mkdir(parents=True, exist_ok=True)
    card_id = next_card_id(root)
    stem = card_id.lower()

    image_name = ""
    if image_path is not None:
        suffix = image_path.suffix.lower()
        if suffix not in (".jpg", ".jpeg", ".png"):
            raise ValueError(f"Unsupported image type: {image_path.name}")
        image_name = f"{stem}{'.jpg' if suffix == '.jpeg' else suffix}"
        (lib / image_name).write_bytes(image_path.read_bytes())

    clean = result.card
    sidecar: dict[str, Any] = {
        "card_id": card_id,
        "date_added": datetime.now().date().isoformat(),
        "added_by": added_by or provenance.get("added_by", ""),
        "brand": clean["brand"],
        "source_link": clean["source_link"],
        "media_type": clean["media_type"],
        "assets": {"primary": image_name},
    }
    if provenance.get("foreplay"):
        sidecar["foreplay"] = provenance.pop("foreplay")
    sidecar["analysis"] = {
        k: clean.get(k) for k in (
            "format", "hook_type", "mechanic", "secondary_mechanic", "scan_path",
            "proof_element", "product_role", "awareness_stage", "why_it_works",
            "cultural_note", "steal", "avoid", "proxy_signal",
            "field_confidence", "reasoning",
        )
    }
    sidecar["analysis"]["status"] = status
    sidecar["analysis"]["strategist_notes"] = strategist_notes
    sidecar["provenance"] = provenance

    path = lib / f"{stem}.yaml"
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(sidecar, f, sort_keys=False, allow_unicode=True, width=100)
    return card_id, path


def load_card(card_id: str, root: Path | None = None) -> dict[str, Any]:
    path, _ = card_paths(card_id, root)
    if not path.exists():
        raise FileNotFoundError(f"No card {card_id} at {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def update_card(
    card_id: str,
    *,
    corrections: str = "",
    status: str = "",
    strategist_notes: str = "",
    updated_by: str = "",
    tax: Taxonomy,
    root: Path | None = None,
) -> tuple[dict[str, Any], CorrectionReport]:
    """Apply corrections / a status change to an EXISTING card (the
    escalation close-out path). Appends to the provenance corrections trail
    rather than overwriting it."""
    sidecar = load_card(card_id, root)
    analysis = dict(sidecar.get("analysis") or {})
    report = CorrectionReport()

    if corrections:
        flat = {**analysis, "brand": sidecar.get("brand", ""),
                "media_type": sidecar.get("media_type", "static"),
                "source_link": sidecar.get("source_link", "")}
        updated, report = apply_corrections(flat, corrections, tax)
        result = validate_card(updated, tax)
        if not result.ok:
            raise ValueError(
                "Corrections leave unresolved issues:\n  - " + "\n  - ".join(result.issues))
        clean = result.card
        sidecar["brand"] = clean["brand"]
        for k in list(analysis):
            if k in clean:
                analysis[k] = clean[k]

    if status:
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}, got '{status}'")
        analysis["status"] = status
    if strategist_notes:
        analysis["strategist_notes"] = strategist_notes

    prov = dict(sidecar.get("provenance") or {})
    trail = list(prov.get("corrections") or [])
    stamp = f"{utc_now_iso()} by {updated_by or 'unknown'}"
    for line in report.applied + report.fuzzy:
        trail.append(f"{line} ({stamp})")
    if status:
        trail.append(f"status = {status} ({stamp})")
    prov["corrections"] = trail
    sidecar["provenance"] = prov
    sidecar["analysis"] = analysis

    path, _ = card_paths(card_id, root)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(sidecar, f, sort_keys=False, allow_unicode=True, width=100)
    return sidecar, report


def load_all_cards(root: Path | None = None) -> list[dict[str, Any]]:
    lib = _library_root(root)
    cards = []
    if lib.exists():
        for path in sorted(lib.glob("ad-*.yaml")):
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if data.get("card_id"):
                cards.append(data)
    return cards


# ─── Draft persistence (between `adc analyze` and `adc library save`) ────────


def write_draft(payload: dict[str, Any], root: Path | None = None) -> Path:
    d = drafts_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    brand = re.sub(r"[^a-z0-9]+", "-", str(payload.get("card", {}).get("brand", "ad")).lower())
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = d / f"draft-{stamp}-{brand or 'ad'}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def read_draft(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
