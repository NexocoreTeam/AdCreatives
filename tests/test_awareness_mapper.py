"""Tests for strategy/awareness_mapper.py.

Focus is on the deterministic mental-stage distribution logic — Schwartz
awareness strategy tables are data, not logic, and don't warrant unit tests
of their own.
"""

from __future__ import annotations

import pytest

from models.brief import AwarenessLevel, MentalStage
from strategy.awareness_mapper import (
    distribute_across_stages,
    get_mental_stage_strategy,
    primary_mental_stage,
)


class TestDistributeAcrossStages:
    def test_zero_count_returns_empty(self):
        assert distribute_across_stages(0, AwarenessLevel.PROBLEM_AWARE) == []

    def test_negative_count_returns_empty(self):
        assert distribute_across_stages(-3, AwarenessLevel.PROBLEM_AWARE) == []

    def test_count_one_returns_primary_stage(self):
        """A single brief should target the avatar's center of gravity, not
        always trigger. Critical for callers that fan briefs at 1-per-avatar."""
        assert distribute_across_stages(1, AwarenessLevel.UNAWARE) == [
            MentalStage.TRIGGER
        ]
        assert distribute_across_stages(1, AwarenessLevel.PROBLEM_AWARE) == [
            MentalStage.EXPLORATION
        ]
        assert distribute_across_stages(1, AwarenessLevel.SOLUTION_AWARE) == [
            MentalStage.EVALUATION
        ]
        assert distribute_across_stages(1, AwarenessLevel.MOST_AWARE) == [
            MentalStage.PURCHASE
        ]

    def test_small_count_guarantees_primary_is_included(self):
        """With count=2 and most_aware avatar, the funnel-order slice would
        be [trigger, exploration] — but primary (purchase) MUST be in the
        result, so the last slot gets swapped to purchase."""
        result = distribute_across_stages(2, AwarenessLevel.MOST_AWARE)
        assert MentalStage.PURCHASE in result
        assert result == [MentalStage.TRIGGER, MentalStage.PURCHASE]

    def test_count_three_swaps_primary_into_slice_when_missing(self):
        """count=3 with most_aware: naive slice would skip purchase. Primary
        gets swapped into the last slot."""
        result = distribute_across_stages(3, AwarenessLevel.MOST_AWARE)
        assert MentalStage.PURCHASE in result
        assert result == [
            MentalStage.TRIGGER,
            MentalStage.EXPLORATION,
            MentalStage.PURCHASE,
        ]

    def test_count_four_covers_all_stages_in_order(self):
        result = distribute_across_stages(4, AwarenessLevel.SOLUTION_AWARE)
        assert result == [
            MentalStage.TRIGGER,
            MentalStage.EXPLORATION,
            MentalStage.EVALUATION,
            MentalStage.PURCHASE,
        ]

    def test_count_six_problem_aware_biases_toward_exploration(self):
        """problem_aware → primary stage is exploration → extras should bias there."""
        result = distribute_across_stages(6, AwarenessLevel.PROBLEM_AWARE)
        assert len(result) == 6
        # First 4 cover all stages
        assert set(result[:4]) == {
            MentalStage.TRIGGER,
            MentalStage.EXPLORATION,
            MentalStage.EVALUATION,
            MentalStage.PURCHASE,
        }
        # Extras (positions 5 and 6) — first extra is primary stage
        assert result[4] == MentalStage.EXPLORATION

    def test_count_six_most_aware_biases_toward_purchase(self):
        """most_aware → primary stage is purchase."""
        result = distribute_across_stages(6, AwarenessLevel.MOST_AWARE)
        assert result[4] == MentalStage.PURCHASE

    def test_count_three_skips_purchase(self):
        """count < 4 walks funnel order from trigger forward."""
        result = distribute_across_stages(3, AwarenessLevel.PROBLEM_AWARE)
        assert result == [
            MentalStage.TRIGGER,
            MentalStage.EXPLORATION,
            MentalStage.EVALUATION,
        ]

    def test_large_count_still_covers_all_four_stages(self):
        """At any count ≥ 4, every stage must appear at least once."""
        result = distribute_across_stages(20, AwarenessLevel.UNAWARE)
        assert len(result) == 20
        assert set(result) == {
            MentalStage.TRIGGER,
            MentalStage.EXPLORATION,
            MentalStage.EVALUATION,
            MentalStage.PURCHASE,
        }


class TestPrimaryMentalStage:
    @pytest.mark.parametrize(
        "awareness,expected",
        [
            (AwarenessLevel.UNAWARE, MentalStage.TRIGGER),
            (AwarenessLevel.PROBLEM_AWARE, MentalStage.EXPLORATION),
            (AwarenessLevel.SOLUTION_AWARE, MentalStage.EVALUATION),
            (AwarenessLevel.PRODUCT_AWARE, MentalStage.EVALUATION),
            (AwarenessLevel.MOST_AWARE, MentalStage.PURCHASE),
        ],
    )
    def test_each_awareness_maps_to_expected_stage(
        self, awareness: AwarenessLevel, expected: MentalStage
    ):
        assert primary_mental_stage(awareness) == expected


class TestMentalStageStrategies:
    """Each stage must have the three rule keys the prompt builder reads."""

    @pytest.mark.parametrize("stage", list(MentalStage))
    def test_every_stage_has_required_keys(self, stage: MentalStage):
        strat = get_mental_stage_strategy(stage)
        assert "approach" in strat and strat["approach"].strip()
        assert "brief_on" in strat and strat["brief_on"].strip()
        assert "avoid" in strat and strat["avoid"].strip()

    def test_exploration_strategy_mentions_category_not_product(self):
        """Sarah's core insight — exploration speaks to the category."""
        strat = get_mental_stage_strategy(MentalStage.EXPLORATION)
        joined = " ".join(strat.values()).lower()
        assert "category" in joined
        assert "background" in joined or "not the product" in joined

    def test_evaluation_strategy_mentions_permission_not_urgency(self):
        """Change #3 — evaluation = permission, not urgency."""
        strat = get_mental_stage_strategy(MentalStage.EVALUATION)
        joined = " ".join(strat.values()).lower()
        assert "permission" in joined or "certainty" in joined
        assert "manufactured urgency" in joined or "no manufactured" in joined or (
            "urgency" in strat["avoid"].lower()
        )

    def test_trigger_strategy_warns_against_product_hero(self):
        strat = get_mental_stage_strategy(MentalStage.TRIGGER)
        assert "product hero" in strat["avoid"].lower() or (
            "not the product" in strat["approach"].lower()
        )
