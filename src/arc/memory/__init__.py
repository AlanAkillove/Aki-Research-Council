"""Append-only JSONL helpers and Research State access.

Hard rules (Tech Spec / AGENTS):
- Event logs are append-only; updates append a new snapshot (latest-wins on read).
- ``fact`` claims require at least one evidence id.
- New ideas may only start at ``signal`` (promote via ``transition_idea``).
- Chair approval appends an approved snapshot; it never rewrites history.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import yaml

from arc.paths import RESEARCH_STATE_DIR
from arc.schemas import CLAIMS_FILE, Claim, ClaimType
from arc.schemas import FEEDBACK_FILE, FeedbackEntry, FeedbackLabel
from arc.schemas import IDEAS_FILE, Idea, IdeaStage


FEEDBACK_PATH = RESEARCH_STATE_DIR / FEEDBACK_FILE
CLAIMS_PATH = RESEARCH_STATE_DIR / CLAIMS_FILE
IDEAS_PATH = RESEARCH_STATE_DIR / IDEAS_FILE

CREATE_IDEA_STAGES = frozenset({IdeaStage.SIGNAL})


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def iter_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _latest_by_key(records: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    """Keep the last snapshot for each id (file order = chronological)."""
    latest: dict[str, dict[str, Any]] = {}
    for record in records:
        kid = record.get(key)
        if kid:
            latest[str(kid)] = record
    return list(latest.values())


def load_researcher_profile(path: Path | None = None) -> dict[str, Any]:
    cfg = path or (RESEARCH_STATE_DIR / "researcher_profile.yaml")
    with cfg.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_project(project_id: str) -> dict[str, Any]:
    path = RESEARCH_STATE_DIR / "projects" / f"{project_id}.yaml"
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_projects() -> list[str]:
    projects_dir = RESEARCH_STATE_DIR / "projects"
    if not projects_dir.exists():
        return []
    return sorted(p.stem for p in projects_dir.glob("*.yaml"))


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


def write_feedback(
    paper_id: str,
    label: FeedbackLabel | str,
    comment: str = "",
    source: str = "cli",
) -> FeedbackEntry:
    if isinstance(label, str):
        label = FeedbackLabel(label)
    entry = FeedbackEntry(
        feedback_id=str(uuid4()),
        paper_id=paper_id,
        label=label,
        comment=comment,
        source=source,
    )
    append_jsonl(FEEDBACK_PATH, entry.model_dump(mode="json"))
    return entry


def list_feedback(limit: int = 50) -> list[FeedbackEntry]:
    entries = [FeedbackEntry.model_validate(r) for r in iter_jsonl(FEEDBACK_PATH)]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


# ---------------------------------------------------------------------------
# Claim Ledger
# ---------------------------------------------------------------------------


def write_claim(
    paper_id: str,
    text: str,
    type: ClaimType | str,
    evidence_ids: list[str] | None = None,
    generated_by: str = "system",
) -> Claim:
    """Append a claim. ``fact`` requires non-empty evidence_ids."""
    if isinstance(type, str):
        type = ClaimType(type)
    evidence_ids = evidence_ids or []
    if type == ClaimType.FACT and not evidence_ids:
        raise ValueError("fact claims require at least one evidence id (Tech Spec §6.2)")
    claim = Claim(
        claim_id=f"CLM-{uuid4().hex[:12]}",
        paper_id=paper_id,
        text=text,
        type=type,
        evidence_for=evidence_ids,
        generated_by=generated_by,
        approved_by=None,
    )
    append_jsonl(CLAIMS_PATH, claim.model_dump(mode="json"))
    return claim


def list_claims(
    paper_id: str | None = None,
    limit: int = 100,
    *,
    approved_only: bool = False,
) -> list[Claim]:
    raw = _latest_by_key(list(iter_jsonl(CLAIMS_PATH)), "claim_id")
    claims = [Claim.model_validate(r) for r in raw]
    claims.sort(key=lambda c: c.claim_id, reverse=True)
    if paper_id:
        claims = [c for c in claims if c.paper_id == paper_id]
    if approved_only:
        claims = [c for c in claims if c.approved_by]
    return claims[:limit]


def get_claim(claim_id: str) -> Claim | None:
    for claim in list_claims(limit=10_000):
        if claim.claim_id == claim_id:
            return claim
    return None


def approve_claim(
    claim_id: str,
    approver: str = "chair",
) -> Claim | None:
    """Append an approved snapshot for *claim_id* (append-only)."""
    if approver != "chair":
        raise ValueError("Only approver='chair' may approve formal claims")
    current = get_claim(claim_id)
    if current is None:
        return None
    if current.approved_by:
        return None
    approved = current.model_copy(update={"approved_by": approver})
    append_jsonl(CLAIMS_PATH, approved.model_dump(mode="json"))
    return approved


# ---------------------------------------------------------------------------
# Idea lifecycle
# ---------------------------------------------------------------------------


VALID_TRANSITIONS: dict[str, list[str]] = {
    "signal": ["hypothesis", "rejected"],
    "hypothesis": ["candidate", "rejected"],
    "candidate": ["validated_candidate", "rejected"],
    "validated_candidate": ["active_project", "rejected"],
    "active_project": ["rejected"],
    "rejected": [],
}


def write_idea(
    title: str,
    claim: str = "",
    stage: IdeaStage | str = IdeaStage.SIGNAL,
    derived_from: dict[str, list[str]] | None = None,
) -> Idea:
    """Create a new idea at ``signal`` only."""
    if isinstance(stage, str):
        stage = IdeaStage(stage)
    if stage not in CREATE_IDEA_STAGES:
        raise ValueError(
            f"New ideas must start at 'signal' (got {stage.value}); "
            "use transition_idea to promote"
        )
    idea = Idea(
        idea_id=f"IDEA-{uuid4().hex[:12]}",
        title=title,
        stage=stage,
        claim=claim,
        derived_from=derived_from or {},
    )
    append_jsonl(IDEAS_PATH, idea.model_dump(mode="json"))
    return idea


def list_ideas(
    stage: str | None = None,
    limit: int = 50,
) -> list[Idea]:
    raw = _latest_by_key(list(iter_jsonl(IDEAS_PATH)), "idea_id")
    ideas = [Idea.model_validate(r) for r in raw]
    ideas.sort(key=lambda i: i.idea_id, reverse=True)
    if stage:
        ideas = [i for i in ideas if i.stage.value == stage]
    return ideas[:limit]


def get_idea(idea_id: str) -> Idea | None:
    for idea in list_ideas(limit=10_000):
        if idea.idea_id == idea_id:
            return idea
    return None


def transition_idea(
    idea_id: str,
    new_stage: IdeaStage | str,
    *,
    rejection_reason: str = "",
    rejection_evidence: list[str] | None = None,
    revive_when: list[str] | None = None,
) -> Idea | None:
    """Append a stage-transition snapshot. Rejected requires audit fields."""
    if isinstance(new_stage, str):
        new_stage = IdeaStage(new_stage)

    current = get_idea(idea_id)
    if current is None:
        return None

    allowed = VALID_TRANSITIONS.get(current.stage.value, [])
    if new_stage.value not in allowed:
        raise ValueError(
            f"Cannot transition from {current.stage.value} to {new_stage.value}. "
            f"Allowed: {allowed}"
        )

    updates: dict[str, Any] = {"stage": new_stage}
    if new_stage == IdeaStage.REJECTED:
        if not rejection_reason:
            raise ValueError("rejected transitions require rejection_reason")
        updates.update(
            {
                "rejected_at": datetime.now(timezone.utc),
                "rejection_reason": rejection_reason,
                "rejection_evidence": rejection_evidence or [],
                "revive_when": revive_when or [],
            }
        )

    updated = current.model_copy(update=updates)
    append_jsonl(IDEAS_PATH, updated.model_dump(mode="json"))
    return updated
