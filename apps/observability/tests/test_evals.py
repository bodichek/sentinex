"""Tests for the eval helpers."""

from __future__ import annotations

from apps.observability.evals import (
    eval_hallucination_score,
    eval_relevance_score,
)


def test_hallucination_score_high_when_grounded() -> None:
    assert eval_hallucination_score(
        "users like dashboards",
        "Users in our pilot reported that dashboards make weekly reviews easier",
    ) > 0.6


def test_hallucination_score_low_when_ungrounded() -> None:
    assert eval_hallucination_score("zebras prefer cobalt", "the meeting is on Thursday") < 0.2


def test_relevance_score_for_overlapping_query() -> None:
    score = eval_relevance_score("the dashboard shows revenue", "show revenue dashboard")
    assert score > 0.5


def test_relevance_score_zero_when_no_query_tokens() -> None:
    assert eval_relevance_score("anything", "") == 0.0
