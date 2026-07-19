"""Idea Tournament — Generation / Skeptic / Feasibility (Tech Spec §8.3).

每周至多 1 个方向进入「待验证」。默认不自动晋升（须显式 auto_promote）。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from arc.council.schemas import TournamentEntry, TournamentOutput
from arc.memory import get_idea, list_ideas, transition_idea
from arc.providers import ModelProvider

logger = logging.getLogger(__name__)


class _SkepticScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="How robust is the idea against criticism")
    weakness: str = Field(default="", description="Key weakness identified")


class _FeasibilityScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0, description="How feasible is the idea (compute/data/theory)")
    notes: str = Field(default="", description="Feasibility assessment notes")


def _promote_to_validated(idea_id: str) -> str:
    """Walk legal transitions to validated_candidate. Returns final stage."""
    path = {
        "signal": ["hypothesis", "candidate", "validated_candidate"],
        "hypothesis": ["candidate", "validated_candidate"],
        "candidate": ["validated_candidate"],
    }
    idea = get_idea(idea_id)
    if idea is None:
        raise ValueError(f"idea not found: {idea_id}")
    stages = path.get(idea.stage.value)
    if not stages:
        raise ValueError(f"cannot promote from stage {idea.stage.value}")
    current = idea.stage.value
    for stage in stages:
        transition_idea(idea_id, stage)
        current = stage
    final = get_idea(idea_id)
    if final is None or final.stage.value != "validated_candidate":
        raise ValueError(
            f"promotion incomplete for {idea_id}: expected validated_candidate, got "
            f"{final.stage.value if final else None}"
        )
    return current


async def run_tournament(
    provider: ModelProvider,
    max_ideas: int = 5,
    auto_promote: bool = False,
) -> TournamentOutput:
    """Run the weekly idea tournament.

    ``auto_promote`` defaults to False: Chair/human should confirm before
    advancing Research State. When True, promotes at most one winner and only
    reports ``advanced_to`` if disk state matches.
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
        feasibility = await provider.generate(
            "tournament_feasibility", _FeasibilityScore, context
        )

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

    entries.sort(key=lambda e: e.composite, reverse=True)

    winner = None
    for e in entries:
        if e.skeptic_score > 0.3:
            winner = e
            break

    output = TournamentOutput(entries=entries)
    if not winner:
        return output

    output.winner_id = winner.idea_id
    output.winner_reason = (
        f"Highest composite score ({winner.composite}) "
        f"with acceptable skeptic evaluation."
    )

    if not auto_promote:
        output.advanced_to = ""
        logger.info(
            "Tournament winner %s selected (auto_promote=False; not advanced)",
            winner.idea_id,
        )
        return output

    try:
        final_stage = _promote_to_validated(winner.idea_id)
        output.advanced_to = final_stage
        logger.info("Tournament winner %s promoted to %s", winner.idea_id, final_stage)
    except Exception as exc:
        output.advanced_to = ""
        output.winner_reason += f" Promotion failed: {exc}"
        logger.warning("Tournament: could not promote %s: %s", winner.idea_id, exc)

    return output
