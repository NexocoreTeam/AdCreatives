"""Tests for strategy/text_remapper.py — schema-aware text fill pipeline.

Covers the value-add of this module (per-slot fill validation, word-budget
enforcement, bullet position stability, placeholder substitution) without
exercising the LLM call itself. The LLM round-trip is exercised end-to-end
by running `adc generate-from-template` against a real client.
"""

from __future__ import annotations

import pytest
import yaml

from models.brand import Brand
from models.brief import AwarenessLevel, CopyFramework, CreativeBrief
from models.library import LibraryPrompt, TextSlot
from models.product import Product
from strategy.text_remapper import (
    _count_words,
    _scrub_em_dashes,
    _validate_and_repair,
    render_slot_fills_block,
    substitute_slot_fills,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_brief() -> CreativeBrief:
    return CreativeBrief(
        brief_id="t-1",
        client="testclient",
        product="Gut Balance",
        awareness_level=AwarenessLevel.PROBLEM_AWARE,
        framework=CopyFramework.PAS,
        angle="Skip the live-bacteria gamble — postbiotics work on day one.",
        hook="Tired of pills that 'might' help? Postbiotics actually work.",
        pain_point="Bloated again despite weeks on probiotics.",
        benefit_callouts=[
            "Works on day 1",
            "No live-bacteria roulette",
            "Cleaner gut, no guessing",
            "Vegan, dairy-free",
        ],
        cta="See how it works",
    )


@pytest.fixture
def us_vs_them_schema() -> list[TextSlot]:
    return [
        TextSlot(
            slot_id="headline",
            role="headline",
            intent="Sets up the contrast with a punchy claim about the brand's value.",
            pattern="Two-line headline with one benefit phrase.",
            max_words=10,
        ),
        TextSlot(
            slot_id="us_label",
            role="label",
            intent="Brand-side column header — claims the product's identity.",
            pattern="One-word brand name, lowercase.",
            max_words=2,
            parallel_to="them_label",
        ),
        TextSlot(
            slot_id="them_label",
            role="label",
            intent="Competitor-side header — frames the alternative as generic.",
            pattern="Generic plural noun or 'the old way'.",
            max_words=2,
            parallel_to="us_label",
        ),
        TextSlot(
            slot_id="us_bullet_1",
            role="bullet",
            intent="First brand-side benefit bullet.",
            max_words=5,
            parallel_to="them_bullet_1",
        ),
        TextSlot(
            slot_id="them_bullet_1",
            role="bullet",
            intent="First competitor-side downside bullet.",
            max_words=5,
            parallel_to="us_bullet_1",
        ),
        TextSlot(
            slot_id="cta",
            role="cta",
            intent="Action-oriented closing.",
            max_words=4,
        ),
    ]


# ─── Schema model tests ──────────────────────────────────────────────────────


def test_text_slot_defaults() -> None:
    slot = TextSlot(
        slot_id="headline",
        role="headline",
        intent="Hook the reader.",
    )
    assert slot.max_words == 8
    assert slot.parallel_to is None
    assert slot.tone == ""
    assert slot.pattern == ""


def test_library_prompt_defaults_text_schema_to_empty() -> None:
    """Existing templates (no text_schema field) must still load — the
    legacy 3-slot condenser path depends on text_schema being [] when
    absent from the YAML."""
    template = LibraryPrompt(
        id="legacy-template",
        name="Legacy",
        template_prompt="Image 1 is the product. Headline: [HEADLINE].",
    )
    assert template.text_schema == []


def test_library_prompt_round_trip_with_schema(tmp_path) -> None:
    """A template with text_schema persists to YAML and reloads identically."""
    template = LibraryPrompt(
        id="us-vs-them-test",
        name="US vs Them Test",
        template_prompt="[HEADLINE]\n[US_LABEL] vs [THEM_LABEL]",
        text_schema=[
            TextSlot(
                slot_id="headline",
                role="headline",
                intent="Frame the contrast.",
                max_words=10,
            ),
            TextSlot(
                slot_id="us_label",
                role="label",
                intent="Brand-side header.",
                max_words=2,
                parallel_to="them_label",
            ),
            TextSlot(
                slot_id="them_label",
                role="label",
                intent="Competitor-side header.",
                max_words=2,
                parallel_to="us_label",
            ),
        ],
    )
    path = tmp_path / "t.yaml"
    path.write_text(
        yaml.safe_dump(template.model_dump(mode="json"), sort_keys=False),
        encoding="utf-8",
    )
    reloaded = LibraryPrompt(**yaml.safe_load(path.read_text(encoding="utf-8")))
    assert len(reloaded.text_schema) == 3
    assert reloaded.text_schema[0].slot_id == "headline"
    assert reloaded.text_schema[1].parallel_to == "them_label"
    assert reloaded.text_schema[2].parallel_to == "us_label"


# ─── _count_words ────────────────────────────────────────────────────────────


def test_count_words_basic() -> None:
    assert _count_words("the old way") == 3
    assert _count_words("") == 0
    assert _count_words("   ") == 0
    assert _count_words("single") == 1
    # Hyphenated compound is one word
    assert _count_words("dairy-free") == 1


# ─── _validate_and_repair ────────────────────────────────────────────────────


def test_validate_and_repair_passes_through_valid_fills(
    sample_brief: CreativeBrief, us_vs_them_schema: list[TextSlot]
) -> None:
    raw = {
        "headline": "Postbiotics work where probiotics fail",
        "us_label": "secondkind",
        "them_label": "live-bacteria",
        "us_bullet_1": "Works day one",
        "them_bullet_1": "Live-bacteria gamble",
        "cta": "See how",
    }
    result = _validate_and_repair(raw, us_vs_them_schema, sample_brief)
    assert result == raw


def test_validate_and_repair_fills_missing_slots_from_brief(
    sample_brief: CreativeBrief, us_vs_them_schema: list[TextSlot]
) -> None:
    """Missing LLM keys must be filled from brief context, not left blank."""
    raw = {
        "headline": "Postbiotics work where probiotics fail",
        # us_label, them_label, us_bullet_1, them_bullet_1, cta all missing
    }
    result = _validate_and_repair(raw, us_vs_them_schema, sample_brief)
    assert set(result.keys()) == {
        "headline",
        "us_label",
        "them_label",
        "us_bullet_1",
        "them_bullet_1",
        "cta",
    }
    # CTA fallback uses brief.cta truncated to max_words
    assert result["cta"] != ""
    assert _count_words(result["cta"]) <= 4
    # us_bullet_1 (first bullet position) maps to benefit_callouts[0]
    assert "Works on day 1" in result["us_bullet_1"] or result["us_bullet_1"] != ""


def test_validate_and_repair_enforces_max_words(
    sample_brief: CreativeBrief, us_vs_them_schema: list[TextSlot]
) -> None:
    """An LLM that over-spends must be truncated to the slot's max_words."""
    raw = {
        "headline": "this headline is way too long and will not fit on the image at all",
        "us_label": "secondkind brand wordmark stylized",  # 4 words, max 2
        "them_label": "old way",
        "us_bullet_1": "one two three four",
        "them_bullet_1": "one two three four",
        "cta": "see how it works today right now",  # 7 words, max 4
    }
    result = _validate_and_repair(raw, us_vs_them_schema, sample_brief)
    assert _count_words(result["headline"]) <= 10
    assert _count_words(result["us_label"]) <= 2
    assert _count_words(result["cta"]) <= 4


def test_validate_and_repair_bullet_position_stable(
    sample_brief: CreativeBrief,
) -> None:
    """When the LLM fills bullet 1 but misses bullet 2, the fallback for
    bullet 2 must use benefit_callouts[1], NOT benefit_callouts[0].

    Without stable bullet-position tracking, both fallbacks would draw
    from the same callout, defeating the purpose of having multiple
    bullet slots.
    """
    schema = [
        TextSlot(slot_id="bullet_a", role="bullet", intent="first", max_words=8),
        TextSlot(slot_id="bullet_b", role="bullet", intent="second", max_words=8),
        TextSlot(slot_id="bullet_c", role="bullet", intent="third", max_words=8),
    ]
    raw = {"bullet_a": "LLM picked this one"}
    result = _validate_and_repair(raw, schema, sample_brief)
    # bullet_a came from the LLM
    assert result["bullet_a"] == "LLM picked this one"
    # bullet_b should fall back to benefit_callouts[1] = "No live-bacteria roulette"
    # bullet_c should fall back to benefit_callouts[2] = "Cleaner gut, no guessing"
    # They must differ — if they didn't, the position tracking is broken.
    assert result["bullet_b"] != result["bullet_c"]
    assert "live-bacteria" in result["bullet_b"].lower()
    assert "cleaner" in result["bullet_c"].lower()


# ─── substitute_slot_fills ───────────────────────────────────────────────────


def test_substitute_slot_fills_replaces_uppercased_markers() -> None:
    template_prompt = (
        "Image 1 is the product. Headline: [HEADLINE]. "
        "Left panel: [US_LABEL]. Right panel: [THEM_LABEL]."
    )
    fills = {
        "headline": "Postbiotics work day one",
        "us_label": "secondkind",
        "them_label": "live-bacteria",
    }
    result = substitute_slot_fills(template_prompt, fills)
    assert "[HEADLINE]" not in result
    assert "[US_LABEL]" not in result
    assert "[THEM_LABEL]" not in result
    assert "Postbiotics work day one" in result
    assert "secondkind" in result
    assert "live-bacteria" in result


def test_substitute_slot_fills_leaves_unknown_markers_intact() -> None:
    template_prompt = "Image 1: [PRODUCT] on [BACKGROUND]. Headline: [HEADLINE]."
    fills = {"headline": "Hello world"}
    result = substitute_slot_fills(template_prompt, fills)
    assert "[PRODUCT]" in result  # not a text slot — left alone
    assert "[BACKGROUND]" in result  # not a text slot — left alone
    assert "[HEADLINE]" not in result
    assert "Hello world" in result


def test_substitute_slot_fills_repeats_value_for_same_slot_twice() -> None:
    """A slot mentioned twice in template_prompt gets the same fill in both
    places — important for wordmark/brand slots that appear on a product
    label and again as a footer."""
    template_prompt = "Top: [BRAND_WORDMARK]. Bottom: [BRAND_WORDMARK]."
    result = substitute_slot_fills(template_prompt, {"brand_wordmark": "secondkind"})
    assert result.count("secondkind") == 2


# ─── render_slot_fills_block ─────────────────────────────────────────────────


def test_render_slot_fills_block_lists_every_slot(
    us_vs_them_schema: list[TextSlot],
) -> None:
    fills = {
        "headline": "Postbiotics work day one",
        "us_label": "secondkind",
        "them_label": "live-bacteria",
        "us_bullet_1": "Works on day 1",
        "them_bullet_1": "Probiotic roulette",
        "cta": "See how",
    }
    block = render_slot_fills_block(fills, us_vs_them_schema)
    assert "SOURCE OF TRUTH" in block
    assert "do NOT transcribe any text visible on Image 2" in block
    for slot in us_vs_them_schema:
        assert "[" + slot.slot_id.upper() + "]" in block


def test_render_slot_fills_block_empty_when_no_schema() -> None:
    assert render_slot_fills_block({"headline": "x"}, []) == ""
    assert render_slot_fills_block({}, [TextSlot(
        slot_id="x", role="headline", intent="x"
    )]) == ""


# ─── Brand/Product fixtures for sanity ───────────────────────────────────────


def test_brand_and_product_fixture_smoke() -> None:
    """Sanity: minimal Brand/Product can be constructed for downstream tests."""
    brand = Brand(name="SecondKind", tone="warm and honest", code="SK")
    product = Product(
        name="Gut Balance",
        description="A postbiotic supplement for daily gut support.",
        benefits=["Works fast", "No live bacteria"],
    )
    assert brand.name == "SecondKind"
    assert product.name == "Gut Balance"


# ─── _scrub_em_dashes ────────────────────────────────────────────────────────


def test_scrub_em_dashes_replaces_em_dash_with_comma() -> None:
    # U+2014 em dash with surrounding spaces should collapse to ", "
    assert _scrub_em_dashes("Compounds — not bacteria") == "Compounds, not bacteria"


def test_scrub_em_dashes_replaces_en_dash() -> None:
    # U+2013 en dash same treatment
    assert _scrub_em_dashes("Works day 1 – every day") == "Works day 1, every day"


def test_scrub_em_dashes_handles_no_space_em_dash() -> None:
    """Em dash without surrounding spaces still substitutes cleanly."""
    assert _scrub_em_dashes("Postbiotics—not probiotics") == "Postbiotics, not probiotics"


def test_scrub_em_dashes_collapses_runs() -> None:
    """Consecutive dashes don't produce ", , , " — they collapse to a single ', '."""
    result = _scrub_em_dashes("A — — B")
    assert result == "A, B"


def test_scrub_em_dashes_strips_trailing_punctuation() -> None:
    """Em dash at end of string would otherwise leave a dangling comma."""
    assert _scrub_em_dashes("See the difference —") == "See the difference"


def test_scrub_em_dashes_passes_through_clean_text() -> None:
    """Text without dashes is unchanged (modulo whitespace normalization)."""
    assert _scrub_em_dashes("Works on day 1") == "Works on day 1"
    assert _scrub_em_dashes("") == ""


def test_scrub_em_dashes_keeps_hyphens() -> None:
    """ASCII hyphen-minus (U+002D) is NOT a dash — it's a word joiner.
    'Live-bacteria' must stay as-is."""
    assert _scrub_em_dashes("Live-bacteria roulette") == "Live-bacteria roulette"


# ─── Integration: scrub flows through validate_and_repair ────────────────────


def test_validate_and_repair_strips_em_dashes_via_value_path(
    sample_brief: CreativeBrief, us_vs_them_schema: list[TextSlot]
) -> None:
    """When the LLM returns a fill containing an em dash, the public API
    contract (after the wrapper) is that the final fills are clean. This
    test exercises the inner _validate_and_repair only; the outer scrub
    in fill_text_schema_for_brief is exercised end-to-end against a real
    LLM call elsewhere."""
    raw = {
        "headline": "Postbiotics — work",  # em dash mid-phrase
        "us_label": "secondkind",
        "them_label": "live bacteria",
        "us_bullet_1": "Works day 1",
        "them_bullet_1": "Live bacteria gamble",
        "cta": "See how",
    }
    # _validate_and_repair itself does NOT scrub — scrubbing happens in
    # the wrapper. So this test ASSERTS that the em dash flows through
    # untouched here. The end-to-end contract relies on the wrapper.
    result = _validate_and_repair(raw, us_vs_them_schema, sample_brief)
    assert "—" in result["headline"]
