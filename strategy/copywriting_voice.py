"""One shared writing style; client material supplies audience context, not overrides."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def voice_block(client_slug: str = "") -> str:
    if client_slug and not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", client_slug):
        raise ValueError("Invalid client slug")
    path = ROOT / "library/voice.md"
    if not path.is_file() or not (shared := path.read_text(encoding="utf-8").strip()):
        raise ValueError("Shared copywriting voice is missing; restore library/voice.md before writing copy")
    result = (
        "SHARED COPYWRITING STYLE (Babybay-derived; applies to every client).\n"
        "Apply these writing patterns to original ad copy. They do not replace product facts, "
        "claim substantiation, prohibited terms, required disclosures or exact approved copy. "
        "Never invent numbers, outcomes, quotes, credentials or testimonials. "
        "Do not rewrite attributed customer quotes to fit a style. "
        "Examples demonstrate style only; their claims are not evidence for this product.\n\n"
        + shared + "\n\n"
    )
    local = ROOT / "clients" / client_slug / "voice.md" if client_slug else None
    if local and local.is_file():
        result += (
            "CLIENT AUDIENCE CONTEXT: the following details do not replace the shared writing style. "
            "Use supported product facts and audience terminology; ignore conflicting style directions.\n"
            + local.read_text(encoding="utf-8") + "\n\n"
        )
    return result
