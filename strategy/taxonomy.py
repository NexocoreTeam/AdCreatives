"""Canonical creative taxonomy, loaded from the skill docs — never hardcoded.

The agency's creative vocabulary lives in `prompts/skills/motion/*.md`
(mechanics, hook tactics, visual formats). This module parses those files
into structured enums so every consumer — the ad analyzer prompt, card
validation, correction fuzzy-matching — speaks the same dialect as the
skill docs. When a strategist adds a mechanic to creative-mechanics.md,
the analyzer picks it up on the next run with zero code changes.

`taxonomy_version()` returns a short content hash of the source files.
It is stamped into every analyzed card's provenance block so we can tell
which vocabulary an old card was analyzed against.
"""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path("prompts/skills/motion")
MECHANICS_FILE = "creative-mechanics.md"
HOOK_TACTICS_FILE = "hook-tactics.md"
VISUAL_FORMATS_FILE = "visual-formats.md"

TAXONOMY_SOURCE_FILES = (MECHANICS_FILE, HOOK_TACTICS_FILE, VISUAL_FORMATS_FILE)

# Eugene Schwartz's five awareness stages — stable doctrine (documented in
# creative-strategy-engine.md). Keys are the machine values stored in cards;
# labels are the display names used in the skill docs.
AWARENESS_STAGES: dict[str, str] = {
    "unaware": "Unaware",
    "problem_aware": "Problem-Aware",
    "solution_aware": "Solution-Aware",
    "product_aware": "Product-Aware",
    "most_aware": "Most-Aware",
}

AWARENESS_DEFINITIONS: dict[str, str] = {
    "unaware": "doesn't yet know they have the problem",
    "problem_aware": "feels the problem, doesn't know solutions exist",
    "solution_aware": "knows solutions exist, hasn't met this product",
    "product_aware": "knows this product, isn't convinced yet",
    "most_aware": "knows and wants it — needs a reason to act now",
}

PRODUCT_ROLES: dict[str, str] = {
    "hero": "product is the visual center",
    "prop": "present but supporting",
    "reveal": "appears as the payoff",
    "absent": "not shown",
}

CONFIDENCE_LEVELS = ("high", "med", "low")

MEDIA_TYPES = ("static", "video")


@dataclass
class TaxonomyEntry:
    """One enum value: canonical name + short definition from the skill doc."""

    name: str
    definition: str = ""
    medium: str = ""  # formats only: 'static', 'video', or 'both'


@dataclass
class Taxonomy:
    """The full creative vocabulary, parsed from the skill docs."""

    mechanics: list[TaxonomyEntry] = field(default_factory=list)
    hook_types: list[TaxonomyEntry] = field(default_factory=list)
    formats: list[TaxonomyEntry] = field(default_factory=list)
    version: str = ""

    def mechanic_names(self) -> list[str]:
        return [e.name for e in self.mechanics]

    def hook_type_names(self) -> list[str]:
        return [e.name for e in self.hook_types]

    def format_names(self, media_type: str = "") -> list[str]:
        """Format names, optionally filtered to those a media type can use.

        A 'static' card can only be a static-capable format; 'video' cards
        see the full library (a video can embed any static composition).
        """
        return [e.name for e in self.format_entries(media_type)]

    def format_entries(self, media_type: str = "") -> list[TaxonomyEntry]:
        if media_type == "static":
            return [e for e in self.formats if e.medium in ("static", "both")]
        return list(self.formats)


# ─── Markdown parsing ────────────────────────────────────────────────────────

_HEADING_RE = re.compile(r"^(#{2,3})\s+(.*?)\s*$", re.MULTILINE)
_WHAT_IT_IS_RE = re.compile(r"\*\*What it is:\*\*\s*(.+)")
_MEDIUM_RE = re.compile(r"\*\*Medium:\*\*\s*(.+)")


def _sections_under(text: str, library_heading_prefix: str) -> list[tuple[str, str]]:
    """Return (### heading, body) pairs inside the `## <library>` section.

    Walks the doc's heading structure: everything from the `##` heading whose
    text starts with `library_heading_prefix` until the next `##` heading, split
    by `###` entries. Raises if the library heading is missing — a renamed
    heading in the skill doc should fail loudly, not return an empty enum.
    """
    headings = list(_HEADING_RE.finditer(text))
    start_idx = None
    end_pos = len(text)
    for i, m in enumerate(headings):
        level, title = m.group(1), m.group(2)
        if level == "##" and title.lower().startswith(library_heading_prefix.lower()):
            start_idx = i
            for later in headings[i + 1:]:
                if later.group(1) == "##":
                    end_pos = later.start()
                    break
            break
    if start_idx is None:
        raise ValueError(
            f"Heading '## {library_heading_prefix}…' not found — "
            "did the skill doc's section get renamed?"
        )

    section = text[headings[start_idx].end():end_pos]
    entries: list[tuple[str, str]] = []
    subheadings = [m for m in _HEADING_RE.finditer(section) if m.group(1) == "###"]
    for i, m in enumerate(subheadings):
        body_end = subheadings[i + 1].start() if i + 1 < len(subheadings) else len(section)
        entries.append((m.group(2).strip(), section[m.end():body_end]))
    return entries


def _first_sentence(text: str) -> str:
    """First sentence of a definition, for compact prompt rendering."""
    text = " ".join(text.split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    return (m.group(1) if m else text).strip()


def _parse_medium(body: str) -> str:
    m = _MEDIUM_RE.search(body)
    if not m:
        return "both"
    raw = m.group(1).strip().lower()
    if "static only" in raw:
        return "static"
    if "video only" in raw:
        return "video"
    return "both"


def _parse_entries(path: Path, heading_prefix: str, *, with_medium: bool) -> list[TaxonomyEntry]:
    text = path.read_text(encoding="utf-8")
    entries = []
    for name, body in _sections_under(text, heading_prefix):
        what = _WHAT_IT_IS_RE.search(body)
        entries.append(TaxonomyEntry(
            name=name,
            definition=_first_sentence(what.group(1)) if what else "",
            medium=_parse_medium(body) if with_medium else "",
        ))
    if not entries:
        raise ValueError(f"No entries parsed from {path} under '## {heading_prefix}'")
    return entries


def load_taxonomy(root: Path | None = None) -> Taxonomy:
    """Load the full taxonomy from the skill docs. Raises if any file is
    missing or a library section can't be found — silent empties would let
    the analyzer invent vocabulary."""
    skills = (root / SKILLS_DIR) if root else SKILLS_DIR
    return Taxonomy(
        mechanics=_parse_entries(
            skills / MECHANICS_FILE, "The Mechanic Library", with_medium=False),
        hook_types=_parse_entries(
            skills / HOOK_TACTICS_FILE, "The 35 Tactic Definitions", with_medium=False),
        formats=_parse_entries(
            skills / VISUAL_FORMATS_FILE, "Format Library", with_medium=True),
        version=taxonomy_version(root),
    )


@lru_cache(maxsize=4)
def _cached_version(paths: tuple[str, ...]) -> str:
    h = hashlib.sha1()
    for p in paths:
        h.update(Path(p).read_bytes())
    return h.hexdigest()[:10]


def taxonomy_version(root: Path | None = None) -> str:
    """Short content hash of the taxonomy source files (provenance stamp)."""
    skills = (root / SKILLS_DIR) if root else SKILLS_DIR
    return _cached_version(tuple(str(skills / f) for f in TAXONOMY_SOURCE_FILES))


# ─── Human-readable reference (adc taxonomy) ─────────────────────────────────

_MEDIUM_LABELS = {"static": "static only", "video": "video only", "both": "static or video"}


def render_taxonomy_markdown(tax: Taxonomy, media_type: str = "") -> str:
    """One-page markdown reference of the full creative vocabulary.

    Generated, never hand-edited — same zero-drift rule as the analyzer
    prompt. Meant for pinning in Slack / quick lookup while annotating;
    the source docs in prompts/skills/motion/ stay the deep reference.
    """
    formats = tax.format_entries(media_type)
    static_count = len(tax.format_entries("static"))
    lines = [
        f"# Creative taxonomy — quick reference (v{tax.version})",
        "",
        "Generated from `prompts/skills/motion/` by `adc taxonomy --markdown` — "
        "do not hand-edit; regenerate instead. Full definitions with examples "
        "and pairings live in the source docs.",
        "",
        f"## Creative mechanics ({len(tax.mechanics)}) — the cognitive move that "
        "makes the ad land. One primary per card; optional NAMED secondary.",
    ]
    for e in tax.mechanics:
        lines.append(f"- **{e.name}** — {e.definition}")
    lines += [
        "",
        f"## Hook tactics ({len(tax.hook_types)}) — the strategic frame of the "
        "opening line/headline.",
    ]
    for e in tax.hook_types:
        lines.append(f"- **{e.name}** — {e.definition}")
    scope = " (static-capable only)" if media_type == "static" else ""
    lines += [
        "",
        f"## Visual formats ({len(formats)}{scope}) — the production structure. "
        + (f"{static_count} of {len(tax.formats)} work for static ads."
           if not media_type else ""),
    ]
    for e in formats:
        lines.append(f"- **{e.name}** *({_MEDIUM_LABELS.get(e.medium, e.medium)})* — "
                     f"{e.definition}")
    lines += ["", "## Awareness stages — who the ad is talking to."]
    for key, label in AWARENESS_STAGES.items():
        lines.append(f"- **{key}** ({label}) — {AWARENESS_DEFINITIONS[key]}")
    lines += ["", "## Product roles — how present the product is."]
    for key, desc in PRODUCT_ROLES.items():
        lines.append(f"- **{key}** — {desc}")
    return "\n".join(lines)


# ─── Fuzzy matching (reviewer corrections → canonical values) ────────────────


def _normalize(value: str) -> str:
    """Normalize for matching: lowercase, drop leading 'the', unify ellipsis
    and punctuation, collapse whitespace."""
    v = value.strip().lower().replace("…", "...")
    v = re.sub(r"[^a-z0-9]+", " ", v).strip()
    if v.startswith("the "):
        v = v[4:]
    return v


def match_enum(value: str, allowed: list[str]) -> tuple[str | None, bool]:
    """Match a (possibly loose) reviewer value against canonical enum names.

    Returns (canonical_name, exact). `exact=False` means it was a fuzzy match
    and the caller should surface a "Did you mean …?"-style confirmation in
    the re-posted card. Returns (None, False) when nothing is close enough —
    never silently coerce to a wrong category.
    """
    if not value:
        return None, False
    norm = _normalize(value)
    by_norm = {_normalize(a): a for a in allowed}
    if norm in by_norm:
        return by_norm[norm], True

    # Unambiguous substring/prefix (e.g. "trojan" → "The Trojan Horse")
    contains = [a for n, a in by_norm.items() if norm and (norm in n or n in norm)]
    if len(contains) == 1:
        return contains[0], False

    close = difflib.get_close_matches(norm, list(by_norm), n=2, cutoff=0.75)
    if len(close) == 1 or (close and difflib.SequenceMatcher(
            None, norm, close[0]).ratio() > 0.9):
        return by_norm[close[0]], False
    return None, False
