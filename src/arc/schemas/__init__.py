"""Pydantic schemas — authority for structured I/O (Tech Spec)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PipelineStatus(StrEnum):
    INGESTED = "INGESTED"
    NORMALIZED = "NORMALIZED"
    SCREENED = "SCREENED"
    EVIDENCE_READY = "EVIDENCE_READY"
    REVIEWED = "REVIEWED"
    CHAIR_DECIDED = "CHAIR_DECIDED"
    PUBLISHED = "PUBLISHED"


class ClaimType(StrEnum):
    FACT = "fact"
    AUTHOR_CLAIM = "author_claim"
    EXTERNAL_CLAIM = "external_claim"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    RECOMMENDATION = "recommendation"


class Verdict(StrEnum):
    READ = "READ"
    TRY = "TRY"
    WATCH = "WATCH"
    ARCHIVE = "ARCHIVE"
    NO_GO = "NO-GO"
    UPDATE = "UPDATE"


class IdeaStage(StrEnum):
    SIGNAL = "signal"
    HYPOTHESIS = "hypothesis"
    CANDIDATE = "candidate"
    VALIDATED_CANDIDATE = "validated_candidate"
    ACTIVE_PROJECT = "active_project"
    REJECTED = "rejected"


class SourceTier(StrEnum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"


class EvidenceType(StrEnum):
    THEOREM = "theorem"
    EXPERIMENT = "experiment"
    ABLATION = "ablation"
    REVIEW = "review"
    CODE = "code"
    CLAIM = "claim"
    AUTHOR_CLAIM = "author_claim"
    LIMITATION = "limitation"
    OTHER = "other"


class FeedbackLabel(StrEnum):
    """Feedback taxonomy from Tech Spec §10."""

    WORTH_READING = "值得精读"
    DIRECTLY_RELEVANT = "与当前项目直接相关"
    METHOD_TRANSFERABLE = "方法可迁移"
    GENERAL_BACKGROUND = "只是一般背景"
    INSUFFICIENT_EVIDENCE = "证据不足"
    HYPE_OVER_CONTRIBUTION = "宣传大于贡献"
    RESOURCE_MISMATCH = "资源不适配"
    ALREADY_SEEN = "已经看过"
    CONTINUE_TRACKING = "持续跟踪"
    STOP_RECOMMENDING = "不再推荐"


class NoveltyLabel(StrEnum):
    NO_CLOSE_MATCH = "未发现高度相似工作"
    SIMILAR_MECHANISM_DIFF_OBJECT = "发现相似机制但应用对象不同"
    SAME_PROBLEM_DIFF_PROTOCOL = "发现相同问题但评价协议不同"
    LARGELY_COVERED = "已有工作基本覆盖该想法"
    INSUFFICIENT_EVIDENCE = "证据不足，不能判断"


class Paper(BaseModel):
    canonical_id: str
    doi: str | None = None
    arxiv_id: str | None = None
    openreview_id: str | None = None
    semantic_scholar_id: str | None = None
    openalex_id: str | None = None
    title: str
    authors: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    abstract: str = ""
    pdf_url: str | None = None
    source_url: str | None = None
    code_urls: list[str] = Field(default_factory=list)
    versions: list[str] = Field(default_factory=list)
    related_projects: list[str] = Field(default_factory=list)
    processing_status: str = "metadata_only"
    published_at: str | None = None  # ISO8601 from source when available


class Evidence(BaseModel):
    id: str
    paper_id: str
    content: str
    evidence_type: EvidenceType = EvidenceType.OTHER
    source_tier: SourceTier = SourceTier.A
    extraction_method: str = "api"
    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    location: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Claim(BaseModel):
    claim_id: str
    text: str
    type: ClaimType
    confidence: str = "medium"
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    generated_by: str = "system"
    approved_by: str | None = None
    paper_id: str | None = None


class Decision(BaseModel):
    object_id: str
    verdict: Verdict
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    rationale: list[str] = Field(default_factory=list)
    revisit_when: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)


class Idea(BaseModel):
    idea_id: str
    title: str
    stage: IdeaStage = IdeaStage.SIGNAL
    claim: str = ""
    difference_from_prior_work: str = ""
    minimum_test: str = ""
    kill_criteria: list[str] = Field(default_factory=list)
    derived_from: dict[str, list[str]] = Field(default_factory=dict)
    feasibility: dict[str, str] = Field(default_factory=dict)
    max_contribution: str = ""
    easiest_failure: str = ""
    # Rejection audit (Tech Spec §8.3)
    rejected_at: datetime | None = None
    rejection_reason: str = ""
    rejection_evidence: list[str] = Field(default_factory=list)
    revive_when: list[str] = Field(default_factory=list)


class ScreenScores(BaseModel):
    """Multi-dimensional triage — never a single opaque score only."""

    topic_relevance: float = Field(ge=0.0, le=1.0)
    project_relevance: float = Field(ge=0.0, le=1.0)
    method_transferability: float = Field(ge=0.0, le=1.0)
    novelty_signal: float = Field(ge=0.0, le=1.0)
    feasibility: float = Field(ge=0.0, le=1.0)
    evidence_quality: float = Field(ge=0.0, le=1.0)
    redundancy: float = Field(ge=0.0, le=1.0)
    recommended_action: str = "ignore"


class RunLog(BaseModel):
    run_id: str
    git_commit: str | None = None
    started_at: datetime
    finished_at: datetime | None = None
    mode: str
    model_versions: dict[str, str] = Field(default_factory=dict)
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    source_cursors: dict[str, Any] = Field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float = 0.0
    status: str = "success"
    failures: list[str] = Field(default_factory=list)


FEEDBACK_FILE = "feedback.jsonl"
CLAIMS_FILE = "claims.jsonl"
IDEAS_FILE = "ideas.jsonl"
VERIFICATION_FILE = "verifications.jsonl"


class FeedbackEntry(BaseModel):
    """Append-only user feedback on a paper or recommendation (Tech Spec §10)."""

    feedback_id: str
    paper_id: str
    label: FeedbackLabel
    comment: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: str = "cli"


class VerificationStep(BaseModel):
    """A single concrete step in a verification protocol."""

    order: int
    description: str
    expected: str = ""
    command: str = ""  # optional shell/python command hint


class VerificationProtocol(BaseModel):
    """Minimal verification protocol for an idea (P4).

    Tech Spec §8.3 (Idea lifecycle) + P4: from Idea generate a concrete,
    human-executable test plan.
    """

    protocol_id: str
    idea_id: str
    title: str
    hypothesis: str = ""
    steps: list[VerificationStep] = Field(default_factory=list)
    expected_outcomes: list[str] = Field(default_factory=list)
    kill_criteria: list[str] = Field(default_factory=list)
    minimum_success: str = ""
    status: str = "draft"  # draft | active | passed | failed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
