"""Append-only JSONL helpers and Research State access."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

import yaml

from arc.paths import RESEARCH_STATE_DIR
from arc.schemas import FEEDBACK_FILE, FeedbackEntry, FeedbackLabel


FEEDBACK_PATH = RESEARCH_STATE_DIR / FEEDBACK_FILE


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
