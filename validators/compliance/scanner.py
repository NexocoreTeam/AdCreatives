"""Compliance scanner — check ad copy and briefs for prohibited claims."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import yaml


class Severity(str, Enum):
    ERROR = "ERROR"       # Must fix — legally/platform prohibited
    WARNING = "WARNING"   # Should review — potentially problematic


@dataclass
class ComplianceIssue:
    severity: Severity
    rule: str
    match: str
    context: str
    category: str


def load_rules(category: str) -> list[dict]:
    """Load compliance rules for a category."""
    path = Path("validators/compliance/rules") / f"{category}.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("rules", []) if data else []


def load_client_overrides(client_slug: str) -> list[dict]:
    """Load client-specific compliance overrides."""
    path = Path("validators/compliance/client_overrides") / f"{client_slug}.yaml"
    if not path.exists():
        return []
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("rules", []) if data else []


def scan_text(
    text: str,
    categories: list[str] | None = None,
    client_slug: str | None = None,
) -> list[ComplianceIssue]:
    """Scan text for compliance issues across specified rule categories."""
    if categories is None:
        categories = ["general"]

    all_rules: list[dict] = []
    for category in categories:
        all_rules.extend(load_rules(category))

    if client_slug:
        all_rules.extend(load_client_overrides(client_slug))

    issues: list[ComplianceIssue] = []
    text_lower = text.lower()

    for rule in all_rules:
        patterns = rule.get("patterns", [])
        severity = Severity(rule.get("severity", "WARNING"))
        rule_name = rule.get("name", "unknown")
        category = rule.get("category", "general")

        for pattern in patterns:
            if pattern.startswith("regex:"):
                regex = pattern[6:]
                matches = re.finditer(regex, text_lower)
                for match in matches:
                    issues.append(ComplianceIssue(
                        severity=severity,
                        rule=rule_name,
                        match=match.group(),
                        context=_get_context(text, match.start()),
                        category=category,
                    ))
            else:
                if pattern.lower() in text_lower:
                    pos = text_lower.index(pattern.lower())
                    issues.append(ComplianceIssue(
                        severity=severity,
                        rule=rule_name,
                        match=pattern,
                        context=_get_context(text, pos),
                        category=category,
                    ))

    return issues


def scan_brief(
    brief_data: dict,
    categories: list[str] | None = None,
    client_slug: str | None = None,
) -> list[ComplianceIssue]:
    """Scan all text fields in a creative brief for compliance issues."""
    text_fields = ["hook", "pain_point", "body_copy", "angle", "visual_direction"]
    all_text_parts = []

    for field in text_fields:
        val = brief_data.get(field, "")
        if val:
            all_text_parts.append(val)

    callouts = brief_data.get("benefit_callouts", [])
    all_text_parts.extend(callouts)

    combined = " ".join(all_text_parts)
    return scan_text(combined, categories=categories, client_slug=client_slug)


def _get_context(text: str, pos: int, window: int = 40) -> str:
    """Get surrounding context for a match position."""
    start = max(0, pos - window)
    end = min(len(text), pos + window)
    return f"...{text[start:end]}..."
