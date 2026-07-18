"""Ranking / triage utilities."""

from __future__ import annotations

from arc.config import RankingConfig
from arc.schemas import ScreenScores


def composite_score(scores: ScreenScores, ranking: RankingConfig) -> float:
    """S = wR*R + wL*L + ... - P*redundancy (Tech Spec prior)."""
    w = ranking.weights
    return (
        w.get("R", 0.25) * scores.project_relevance
        + w.get("L", 0.15) * scores.method_transferability
        + w.get("E", 0.15) * scores.evidence_quality
        + w.get("F", 0.15) * scores.feasibility
        + w.get("N", 0.10) * scores.novelty_signal
        + w.get("T", 0.10) * scores.topic_relevance
        - w.get("P", 0.20) * scores.redundancy
    )
