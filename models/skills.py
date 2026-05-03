"""Loader for markdown skill files in prompts/skills/.

Skill files are imported from third-party MIT-licensed repos and used as
system context for LLM calls in the strategy/ layer. See each file's
attribution header for source and adaptations.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

SKILLS_DIR = Path("prompts/skills")


@lru_cache(maxsize=16)
def load_skill(name: str) -> str:
    """Load a skill markdown file by name (without .md extension).

    Strips the leading HTML attribution comment so the returned content is
    ready to use as LLM system context.
    """
    path = SKILLS_DIR / f"{name}.md"
    if not path.exists():
        available = sorted(p.stem for p in SKILLS_DIR.glob("*.md")) if SKILLS_DIR.exists() else []
        raise FileNotFoundError(
            f"Skill '{name}' not found at {path}. Available: {', '.join(available) or '(none)'}"
        )

    content = path.read_text(encoding="utf-8")

    if content.lstrip().startswith("<!--"):
        start = content.find("<!--")
        end = content.find("-->", start)
        if end != -1:
            content = content[end + 3:].lstrip()

    return content


def list_skills() -> list[str]:
    """Return names of all available skills (without .md extension)."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(p.stem for p in SKILLS_DIR.glob("*.md"))
