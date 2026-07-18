"""Council role output schemas — structured I/O per Tech Spec §8."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkepticOutput(BaseModel):
    """Stage D — Skeptical Review. Critique points against the paper."""

    attack_points: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    confidence: str = "medium"  # high | medium | low
    verdict: str = "insufficient_evidence"  # sound | weak | insufficient_evidence


class HistorianOutput(BaseModel):
    """Stage B — Literature Positioning. Prior work and novelty assessment."""

    top_prior_works: list[dict] = Field(default_factory=list)
    novelty_label: str = "证据不足，不能判断"
    context_summary: str = ""


class LiaisonOutput(BaseModel):
    """Stage E — Project Connector. Maps paper to research state."""

    relevant_projects: list[str] = Field(default_factory=list)
    relevant_questions: list[str] = Field(default_factory=list)
    impact: str = "neutral"  # supports | weakens | neutral | unknown
    rationale: str = ""


class ChairOutput(BaseModel):
    """Stage G — Chair Decision. Combines all roles into a decision."""

    verdict: str = "WATCH"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: list[str] = Field(default_factory=list)
    revisit_when: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list, max_length=3)
    claim_ids: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Tournament schemas (Tech Spec §8.3 idea lifecycle + weekly tournament)
# ---------------------------------------------------------------------------


class TournamentEntry(BaseModel):
    """A single idea in the tournament with evaluation scores."""

    idea_id: str
    title: str
    claim: str
    skeptic_score: float = Field(ge=0.0, le=1.0, default=0.5)
    feasibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    composite: float = Field(ge=0.0, le=1.0, default=0.0)
    weakness: str = ""
    feasibility_notes: str = ""


class TournamentOutput(BaseModel):
    """Result of a weekly idea tournament."""

    entries: list[TournamentEntry] = Field(default_factory=list)
    winner_id: str | None = None
    winner_reason: str = ""
    advanced_to: str = ""  # validated_candidate if promoted
