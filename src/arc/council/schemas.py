"""Council role output schemas — structured I/O per Tech Spec §8."""

from __future__ import annotations

from pydantic import BaseModel, Field

from arc.schemas import NoveltyLabel, Verdict


class SkepticOutput(BaseModel):
    """Stage D — Skeptical Review."""

    attack_points: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    verdict: str = "insufficient_evidence"


class HistorianOutput(BaseModel):
    """Stage B — Literature Positioning."""

    top_prior_works: list[dict] = Field(default_factory=list)
    novelty_label: NoveltyLabel = NoveltyLabel.INSUFFICIENT_EVIDENCE
    context_summary: str = ""


class LiaisonOutput(BaseModel):
    """Stage E — Project Connector."""

    relevant_projects: list[str] = Field(default_factory=list)
    relevant_questions: list[str] = Field(default_factory=list)
    impact: str = "neutral"
    rationale: str = ""


class ChairOutput(BaseModel):
    """Stage G — Chair Decision."""

    verdict: Verdict = Verdict.WATCH
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: list[str] = Field(default_factory=list)
    revisit_when: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list, max_length=3)
    claim_ids: list[str] = Field(default_factory=list)


class TournamentEntry(BaseModel):
    idea_id: str
    title: str
    claim: str
    skeptic_score: float = Field(ge=0.0, le=1.0, default=0.5)
    feasibility_score: float = Field(ge=0.0, le=1.0, default=0.5)
    composite: float = Field(ge=0.0, le=1.0, default=0.0)
    weakness: str = ""
    feasibility_notes: str = ""


class TournamentOutput(BaseModel):
    entries: list[TournamentEntry] = Field(default_factory=list)
    winner_id: str | None = None
    winner_reason: str = ""
    advanced_to: str = ""
