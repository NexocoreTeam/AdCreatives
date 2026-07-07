"""Tests for strategy/taxonomy.py — parsing the skill docs into enums.

These run against the REAL skill docs on purpose: if a strategist renames a
section heading or a mechanic, the taxonomy loader (and therefore the ad
analyzer's vocabulary) must fail loudly here, not drift silently.
"""

from __future__ import annotations

import pytest

from strategy.taxonomy import (
    AWARENESS_STAGES,
    Taxonomy,
    TaxonomyEntry,
    load_taxonomy,
    match_enum,
    taxonomy_version,
)


@pytest.fixture(scope="module")
def tax() -> Taxonomy:
    return load_taxonomy()


class TestLoadTaxonomy:
    def test_mechanics_match_skill_doc(self, tax):
        names = tax.mechanic_names()
        assert "The Implied Answer" in names
        assert "The Trojan Horse" in names
        assert "The Contrast Without Comment" in names
        assert len(names) >= 8

    def test_hook_types_load(self, tax):
        names = tax.hook_type_names()
        assert "Warning" in names
        assert "Bold Claim" in names
        assert len(names) >= 30

    def test_formats_have_medium(self, tax):
        by_name = {e.name: e for e in tax.formats}
        assert by_name["Billboard"].medium == "static"
        assert by_name["ASMR"].medium == "video"
        assert by_name["Before and After"].medium == "both"

    def test_static_filter_excludes_video_only(self, tax):
        static_names = tax.format_names("static")
        assert "Billboard" in static_names
        assert "Before and After" in static_names
        assert "ASMR" not in static_names
        assert len(static_names) < len(tax.format_names())

    def test_entries_carry_definitions(self, tax):
        for entry in tax.mechanics + tax.hook_types:
            assert entry.definition, f"{entry.name} has no definition"

    def test_version_is_stable_short_hash(self, tax):
        v = taxonomy_version()
        assert v == tax.version
        assert len(v) == 10

    def test_awareness_stages_are_schwartz_five(self):
        assert list(AWARENESS_STAGES) == [
            "unaware", "problem_aware", "solution_aware", "product_aware", "most_aware"]

    def test_missing_source_files_raise(self, tmp_path):
        with pytest.raises((FileNotFoundError, OSError)):
            load_taxonomy(root=tmp_path)


class TestMatchEnum:
    MECHANICS = [
        "The Implied Answer", "The Social Witness", "The Trojan Horse",
        "The Contrast Without Comment", "This and a…",
    ]

    def test_exact(self):
        assert match_enum("The Trojan Horse", self.MECHANICS) == ("The Trojan Horse", True)

    def test_case_and_leading_the_dropped(self):
        assert match_enum("trojan horse", self.MECHANICS) == ("The Trojan Horse", True)

    def test_unique_substring_is_fuzzy(self):
        matched, exact = match_enum("trojan", self.MECHANICS)
        assert matched == "The Trojan Horse"
        assert exact is False

    def test_ellipsis_normalized(self):
        matched, _ = match_enum("this and a...", self.MECHANICS)
        assert matched == "This and a…"

    def test_typo_close_match(self):
        matched, exact = match_enum("trojen horse", self.MECHANICS)
        assert matched == "The Trojan Horse"
        assert exact is False

    def test_nonsense_rejected(self):
        assert match_enum("completely unrelated", self.MECHANICS) == (None, False)

    def test_empty_rejected(self):
        assert match_enum("", self.MECHANICS) == (None, False)

    def test_ambiguous_substring_rejected(self):
        # "the" normalizes away entirely; "s" matches nothing cleanly
        assert match_enum("the", self.MECHANICS)[0] is None


class TestEntryModel:
    def test_taxonomy_entry_defaults(self):
        e = TaxonomyEntry(name="X")
        assert e.definition == "" and e.medium == ""
