"""Append-only JSONL helpers and Research State access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import yaml

from arc.paths import RESEARCH_STATE_DIR
from arc.schemas import FEEDBACK_FILE, FeedbackEntry, FeedbackLabel
from arc.schemas import CLAIMS_FILE, Claim, ClaimType
from arc.schemas import IDEAS_FILE, Idea, IdeaStage


FEEDBACK_PATH = RESEARCH_STATE_DIR / FEEDBACK_FILE
CLAIMS_PATH = RESEARCH_STATE_DIR / CLAIMS_FILE
IDEAS_PATH = RESEARCH_STATE_DIR / IDEAS_FILE


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
# Feedback (append-only JSONL, Tech Spec §10)
# ---------------------------------------------------------------------------


def write_feedback(
    paper_id: str,
    label: FeedbackLabel | str,
    comment: str = "",
    source: str = "cli",
) -> FeedbackEntry:
    """Record a user feedback entry (append-only). Returns the entry."""
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
    """Iterate feedback entries, newest first."""
    entries = [FeedbackEntry.model_validate(r) for r in iter_jsonl(FEEDBACK_PATH)]
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries[:limit]


# ---------------------------------------------------------------------------
# Claim Ledger (append-only JSONL, Tech Spec §6.2)
# ---------------------------------------------------------------------------


def write_claim(
    paper_id: str,
    text: str,
    type: ClaimType | str,
    evidence_ids: list[str] | None = None,
    generated_by: str = "system",
) -> Claim:
    """Record a claim in the ledger (append-only). Returns the claim."""
    if isinstance(type, str):
        type = ClaimType(type)
    claim = Claim(
        claim_id=f"CLM-{uuid4().hex[:12]}",
        paper_id=paper_id,
        text=text,
        type=type,
        evidence_for=evidence_ids or [],
        generated_by=generated_by,
    )
    append_jsonl(CLAIMS_PATH, claim.model_dump(mode="json"))
    return claim


def list_claims(
    paper_id: str | None = None,
    limit: int = 100,
) -> list[Claim]:
    """Iterate claims, optionally filtered by paper."""
    all_claims = [
        Claim.model_validate(r) for r in iter_jsonl(CLAIMS_PATH)
    ]
    all_claims.sort(key=lambda c: c.claim_id, reverse=True)
    if paper_id:
        all_claims = [c for c in all_claims if c.paper_id == paper_id]
    return all_claims[:limit]


def approve_claim(
    claim_id: str,
    approver: str = "chair",
) -> Claim | None:
    """Mark a claim as approved by the Chair.

    This rewrites the JSONL line in-place (the only mutation allowed
    on the ledger, and only for the ``approved_by`` field).
    """
    lines = []
    found = None
    if not CLAIMS_PATH.exists():
        return None
    with CLAIMS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("claim_id") == claim_id and not record.get("approved_by"):
                record["approved_by"] = approver
                found = Claim.model_validate(record)
            lines.append(json.dumps(record, ensure_ascii=False))
    if found:
        CLAIMS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found


# ---------------------------------------------------------------------------
# Idea lifecycle (append-only JSONL, Tech Spec §5.3 / §8.3)
# ---------------------------------------------------------------------------


VALID_TRANSITIONS: dict[str, list[str]] = {
    "signal": ["hypothesis", "rejected"],
    "hypothesis": ["candidate", "rejected"],
    "candidate": ["validated_candidate", "rejected"],
    "validated_candidate": ["active_project", "rejected"],
    "active_project": ["rejected"],
    "rejected": [],  # terminal
}


def write_idea(
    title: str,
    claim: str = "",
    stage: IdeaStage | str = IdeaStage.SIGNAL,
    derived_from: dict[str, list[str]] | None = None,
) -> Idea:
    """Create a new idea and append to the ledger."""
    if isinstance(stage, str):
        stage = IdeaStage(stage)
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
    """List ideas, optionally filtered by stage."""
    all_ideas = [Idea.model_validate(r) for r in iter_jsonl(IDEAS_PATH)]
    all_ideas.sort(key=lambda i: i.idea_id, reverse=True)
    if stage:
        all_ideas = [i for i in all_ideas if i.stage.value == stage]
    return all_ideas[:limit]


def transition_idea(
    idea_id: str,
    new_stage: IdeaStage | str,
) -> Idea | None:
    """Transition an idea to a new stage. Returns updated idea or None.

    Validates against ``VALID_TRANSITIONS``. Rejected is terminal.
    """
    if isinstance(new_stage, str):
        new_stage = IdeaStage(new_stage)

    lines = []
    found = None
    if not IDEAS_PATH.exists():
        return None

    with IDEAS_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("idea_id") == idea_id:
                current = IdeaStage(record["stage"])
                allowed = VALID_TRANSITIONS.get(current.value, [])
                if new_stage.value not in allowed:
                    raise ValueError(
                        f"Cannot transition from {current.value} to {new_stage.value}. "
                        f"Allowed: {allowed}"
                    )
                record["stage"] = new_stage.value
                found = Idea.model_validate(record)
            lines.append(json.dumps(record, ensure_ascii=False))

    if found:
        IDEAS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found
