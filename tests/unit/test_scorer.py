"""Tests for the scoring engine."""

from sia.analyzer.scorer import compute_total_score, determine_priority, _is_higher_priority


class TestScoring:
    def test_total_score_with_defaults(self):
        scores = {
            "relevance": 8.0,
            "severity": 9.0,
            "timeliness": 7.0,
            "actionability": 6.0,
            "quality": 8.0,
        }
        total = compute_total_score(scores)
        assert 7.0 < total < 9.0

    def test_total_score_with_custom_weights(self):
        scores = {
            "relevance": 10.0,
            "severity": 10.0,
            "timeliness": 10.0,
            "actionability": 10.0,
            "quality": 10.0,
        }
        total = compute_total_score(scores)
        assert total == 10.0

    def test_total_score_all_zeros(self):
        scores = {
            "relevance": 0.0,
            "severity": 0.0,
            "timeliness": 0.0,
            "actionability": 0.0,
            "quality": 0.0,
        }
        total = compute_total_score(scores)
        assert total == 0.0


class TestPriority:
    def test_p0_threshold(self):
        assert determine_priority(8.5) == "P0"
        assert determine_priority(8.0) == "P0"

    def test_p1_threshold(self):
        assert determine_priority(7.0) == "P1"
        assert determine_priority(6.0) == "P1"

    def test_p2_threshold(self):
        assert determine_priority(5.0) == "P2"
        assert determine_priority(4.0) == "P2"

    def test_p3_below_all(self):
        assert determine_priority(3.0) == "P3"
        assert determine_priority(0.0) == "P3"


class TestPriorityComparison:
    def test_p0_higher_than_p1(self):
        assert _is_higher_priority("P0", "P1")

    def test_p1_not_higher_than_p0(self):
        assert not _is_higher_priority("P1", "P0")

    def test_same_priority(self):
        assert not _is_higher_priority("P1", "P1")
