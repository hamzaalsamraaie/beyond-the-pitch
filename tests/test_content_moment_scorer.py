"""Tests for the football moment scoring system."""

from __future__ import annotations

import pytest

from src.content.moment_scorer import (
    DEFAULT_WEIGHTS,
    LAUNCH_MOMENT_IDEAS,
    FootballMomentScore,
    MomentCandidate,
    MomentScorer,
    MomentType,
    _PLAYER_RECOGNITION,
)


class TestMomentType:
    def test_all_types_defined(self):
        expected = {"skill", "goal", "save", "sequence", "nostalgia", "celebration", "analysis"}
        actual = {t.value for t in MomentType}
        assert actual == expected


class TestPlayerRecognition:
    def test_messi_is_max(self):
        assert _PLAYER_RECOGNITION["messi"] == 1.0

    def test_ronaldo_is_max(self):
        assert _PLAYER_RECOGNITION["ronaldo"] == 1.0

    def test_all_values_bounded(self):
        for name, score in _PLAYER_RECOGNITION.items():
            assert 0.0 <= score <= 1.0, f"{name} score {score} out of range"

    def test_known_players_above_default(self):
        default = _PLAYER_RECOGNITION["__default__"]
        assert _PLAYER_RECOGNITION["neymar"] > default
        assert _PLAYER_RECOGNITION["mbappe"] > default


class TestMomentScorer:
    def _make_candidate(self, player="Messi", moment_type=MomentType.SKILL):
        return MomentCandidate(
            player_name=player,
            moment_type=moment_type,
            description=f"Test {moment_type.value} by {player}",
        )

    def test_score_one_returns_football_moment_score(self):
        scorer = MomentScorer()
        result = scorer.score_one(self._make_candidate())
        assert isinstance(result, FootballMomentScore)

    def test_total_score_bounded(self):
        scorer = MomentScorer()
        result = scorer.score_one(self._make_candidate())
        assert 0.0 <= result.total_score <= 1.0

    def test_messi_skill_scores_high(self):
        scorer = MomentScorer()
        result = scorer.score_one(self._make_candidate("Messi", MomentType.SKILL))
        assert result.total_score > 0.7

    def test_analysis_scores_lower_than_skill(self):
        scorer = MomentScorer()
        skill = scorer.score_one(self._make_candidate("Messi", MomentType.SKILL))
        analysis = scorer.score_one(self._make_candidate("Messi", MomentType.ANALYSIS))
        assert skill.total_score > analysis.total_score

    def test_known_player_scores_higher_than_unknown(self):
        scorer = MomentScorer()
        messi = scorer.score_one(self._make_candidate("Messi", MomentType.GOAL))
        unknown = scorer.score_one(self._make_candidate("Unknown Amateur", MomentType.GOAL))
        assert messi.total_score > unknown.total_score

    def test_score_breakdown_sums_to_total(self):
        scorer = MomentScorer()
        result = scorer.score_one(self._make_candidate())
        breakdown_sum = round(sum(result.score_breakdown.values()), 4)
        assert abs(breakdown_sum - result.total_score) < 0.01

    def test_score_returns_sorted_descending(self):
        scorer = MomentScorer()
        candidates = [
            self._make_candidate("Messi", MomentType.SKILL),
            self._make_candidate("Unknown", MomentType.ANALYSIS),
            self._make_candidate("Ronaldo", MomentType.GOAL),
        ]
        results = scorer.score(candidates)
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_relevance_override_affects_score(self):
        scorer = MomentScorer()
        c_low = MomentCandidate(
            player_name="Messi",
            moment_type=MomentType.SKILL,
            description="Test",
            current_relevance_override=0.1,
        )
        c_high = MomentCandidate(
            player_name="Messi",
            moment_type=MomentType.SKILL,
            description="Test",
            current_relevance_override=0.9,
        )
        low_score = scorer.score_one(c_low).total_score
        high_score = scorer.score_one(c_high).total_score
        assert high_score > low_score

    def test_update_weights_changes_scores(self):
        scorer = MomentScorer()
        c = self._make_candidate("Unknown", MomentType.SKILL)
        before = scorer.score_one(c).total_score
        # Increase player_recognition weight
        scorer.update_weights({
            "visual_wow_factor": 0.20,
            "rewatch_potential": 0.20,
            "player_recognition": 0.40,
            "music_compatibility": 0.10,
            "current_relevance": 0.10,
        })
        after = scorer.score_one(c).total_score
        # Unknown player score should drop (high player_recognition weight hurts unknowns)
        assert after < before

    def test_footage_rights_preserved_in_score(self):
        scorer = MomentScorer()
        c = MomentCandidate(
            player_name="Neymar",
            moment_type=MomentType.SKILL,
            description="Test",
            footage_rights_status="REQUIRES_LICENSE",
            footage_note="Match footage owned by CBF",
        )
        result = scorer.score_one(c)
        assert result.footage_rights_status == "REQUIRES_LICENSE"
        assert "CBF" in result.footage_note


class TestDefaultWeights:
    def test_weights_sum_to_1(self):
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_visual_wow_is_largest_weight(self):
        assert DEFAULT_WEIGHTS["visual_wow_factor"] == max(DEFAULT_WEIGHTS.values())


class TestLaunchMomentIdeas:
    def test_at_least_5_ideas(self):
        assert len(LAUNCH_MOMENT_IDEAS) >= 5

    def test_all_ideas_have_descriptions(self):
        for idea in LAUNCH_MOMENT_IDEAS:
            assert len(idea.description) > 10

    def test_all_ideas_have_footage_rights_status(self):
        for idea in LAUNCH_MOMENT_IDEAS:
            assert idea.footage_rights_status in (
                "REQUIRES_LICENSE", "CC0_TEXT_OVERLAY_READY", "UNKNOWN",
            ), f"Bad rights status for {idea.player_name}: {idea.footage_rights_status}"

    def test_rights_required_ideas_have_note(self):
        for idea in LAUNCH_MOMENT_IDEAS:
            if idea.footage_rights_status == "REQUIRES_LICENSE":
                assert len(idea.footage_note) > 10, f"No footage note for {idea.player_name}"

    def test_scorer_can_process_all_ideas(self):
        scorer = MomentScorer()
        results = scorer.score(LAUNCH_MOMENT_IDEAS)
        assert len(results) == len(LAUNCH_MOMENT_IDEAS)
        for r in results:
            assert 0.0 <= r.total_score <= 1.0
