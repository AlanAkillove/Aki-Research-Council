"""Idea Tournament — Generation / Skeptic / Feasibility (Tech Spec §8.3).

每周至多 1 个方向进入「待验证」。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from arc.council.schemas import TournamentEntry, TournamentOutput
from arc.memory import list_ideas, transition_idea
from arc.providers import ModelProvider

logger = logging.getLogger(__name__)


class _SkepticScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="How robust is the idea against criticism")
    weakness: str = Field(default="", description="Key weakness identified")


class _FeasibilityScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="How feasible is the idea (compute/data/theory)")
    notes: str = Field(default="", description="Feasibility assessment notes")


async def run_tournament(
    provider: ModelProvider,
    max_ideas: int = 5,
    auto_promote: bool = True,
) -> TournamentOutput:
    """Run the weekly idea tournament.

    1. Load active ideas (signal / hypothesis / candidate stages)
    2. For each, run LLM-based Skeptic review + Feasibility assessment
    3. Score and rank entries
    4. Select ≤1 winner and (if auto_promote) transition to validated_candidate

    Returns ``TournamentOutput`` with all entries and winner info.
    """
    candidates = []
    for stage in ("signal", "hypothesis", "candidate"):
        candidates.extend(list_ideas(stage=stage, limit=max_ideas))

    if not candidates:
        logger.info("Tournament: no ideas to evaluate")
        return TournamentOutput()

    candidates = candidates[:max_ideas]
    entries: list[TournamentEntry] = []

    for idea in candidates:
        context = {
            "title": idea.title,
            "claim": idea.claim,
            "stage": idea.stage.value,
            "derived_from": idea.derived_from,
        }

        skeptic = await provider.generate("tournament_skeptic", _SkepticScore, context)
        feasibility = await provider.generate("tournament_feasibility", _FeasibilityScore, context)

        composite = (skeptic.score + feasibility.score) / 2.0
        entry = TournamentEntry(
            idea_id=idea.idea_id,
            title=idea.title,
            claim=idea.claim[:100],
            skeptic_score=skeptic.score,
            feasibility_score=feasibility.score,
            composite=round(composite, 3),
            weakness=skeptic.weakness,
            feasibility_notes=feasibility.notes,
        )
        entries.append(entry)
        logger.info(
            "Tournament [%s] %s: skeptic=%.2f feasibility=%.2f composite=%.2f",
            idea.idea_id, idea.title[:50],
            skeptic.score, feasibility.score, composite,
        )

    entries.sort(key=lambda e: e.composite, reverse=True)

    winner = None
    for e in entries:
        if e.skeptic_score > 0.3:
            winner = e
            break

    output = TournamentOutput(entries=entries)

    if winner and auto_promote:
        try:
            # Walk through required intermediate stages
            w = winner
            current = None
            for idea in list_ideas():
                if idea.idea_id == w.idea_id:
                    current = idea.stage.value
                    break

            target = "validated_candidate"
            _path = {
                "signal": ["hypothesis", "candidate", target],
                "hypothesis": ["candidate", target],
                "candidate": [target],
            }
            stages = _path.get(current, [target])
            for s in stages:
                try:
                    transition_idea(w.idea_id, s)
                except ValueError:
                    break

            output.winner_id = w.idea_id
            output.winner_reason = (
                f"Highest composite score ({w.composite}) "
                f"with acceptable skeptic evaluation."
            )
            output.advanced_to = target
            logger.info(
                "Tournament winner: %s (%s) promoted to validated_candidate",
                w.idea_id, w.title[:50],
            )
        except Exception as exc:
            logger.warning("Tournament: could not promote %s: %s", w.idea_id, exc)

    return output
