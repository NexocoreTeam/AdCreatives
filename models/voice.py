"""Brand voice — the sender-side voice layer (Phase 1, Step 11).

Produced by `adc voice`. Maps how the brand should SOUND so copy feels like a
human who gets the customer, not a brand selling at them. Distinct from the
psychology profile (how the customer decides) and from the brand's own
positioning (how the brand describes itself).

The artifact's heavy-lifting field is `personas[].unspoken_truths` — a
persona-tagged bank of lines, each already a usable hook, that downstream
brief + hook generation pulls from before inventing anything new.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PersonaVoice(BaseModel):
    """How the register flexes for one persona, plus their unspoken-truths bank."""

    persona_id: str = Field(
        default="", description="Slug/role of the persona, e.g. 'primary'"
    )
    persona_name: str = Field(
        default="", description="Display name — matches the avatar"
    )
    register_note: str = Field(
        default="",
        description="How the voice flexes for this persona, including any off-limits topics",
    )
    unspoken_truths: list[str] = Field(
        default_factory=list,
        description="Persona-tagged hook bank — specific lived-experience truths in the "
        "customer's own register. Each line is already a usable hook.",
    )


class BrandVoice(BaseModel):
    """The ownable voice for a brand, found in the gap between how customers
    talk and how the category sounds. Written by `adc voice`.

    All fields default to empty so partial LLM output never fails validation —
    this is a creative artifact, not a strict schema like PsychologyProfile.
    """

    territory: str = Field(
        default="", description="The ownable voice territory, in one sentence"
    )
    why_open: str = Field(
        default="",
        description="Why the territory is open — the competitor-voice whitespace. Internal.",
    )
    voice_register: str = Field(default="", description="How the brand sounds, named")
    structural_move: str = Field(
        default="",
        description="The structural pattern, e.g. 'open in the customer's register, "
        "close in the brand's proof register'",
    )
    guardrail_test: str = Field(
        default="",
        description="The one-line test that keeps a line on-side vs shaming the customer",
    )
    hard_rules_retained: list[str] = Field(
        default_factory=list,
        description="Existing brand rules that still hold under the new voice",
    )
    personas: list[PersonaVoice] = Field(default_factory=list)
    founder_voice: str = Field(
        default="",
        description="Where the founder voice goes further than the brand voice, with an "
        "example. Empty if the brand names no founder.",
    )
    changes_vs_existing: list[str] = Field(
        default_factory=list,
        description="Explicit deltas vs the brand's current tone/rules, so the voice "
        "evolves on purpose rather than silently contradicting itself",
    )
    source: str = Field(default="auto_from_voice_step")
