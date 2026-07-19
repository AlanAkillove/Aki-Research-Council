"""P4 — Minimal Verification Protocol generator.

From an Idea, generate a concrete, human-executable verification plan.
Status updates are append-only snapshots (latest-wins on read).
Auto-execution remains OFF by default.
"""

from __future__ import annotations

import logging
import os
from uuid import uuid4

from pydantic import BaseModel

from arc.memory import append_jsonl, iter_jsonl, _latest_by_key
from arc.paths import RESEARCH_STATE_DIR, load_env
from arc.providers import ModelProvider
from arc.schemas import VERIFICATION_FILE, VerificationProtocol, VerificationStep

logger = logging.getLogger(__name__)

VERIFICATION_PATH = RESEARCH_STATE_DIR / VERIFICATION_FILE
_AUTO_EXEC_KEY = "ARC_AUTO_EXECUTION"
ALLOWED_STATUSES = frozenset({"draft", "active", "passed", "failed"})


def is_auto_execution_enabled() -> bool:
    load_env()
    val = os.environ.get(_AUTO_EXEC_KEY, "0").strip().lower()
    return val in ("1", "true")


def require_auto_execution() -> None:
    """Guard: raise if auto-execution not enabled. Call before any executor."""
    if not is_auto_execution_enabled():
        raise RuntimeError(
            f"Auto-execution is DISABLED. Set {_AUTO_EXEC_KEY}=1 or "
            f"run 'arc config set auto_execution true' to enable."
        )


class _ProtocolResponse(BaseModel):
    steps: list[dict]
    expected_outcomes: list[str]
    kill_criteria: list[str]
    minimum_success: str


async def generate_protocol(
    idea_id: str,
    title: str,
    claim: str,
    stage: str,
    provider: ModelProvider,
) -> VerificationProtocol:
    context = {
        "idea_id": idea_id,
        "title": title,
        "claim": claim,
        "current_stage": stage,
    }

    raw = await provider.generate("generate_protocol", _ProtocolResponse, context)

    steps = [
        VerificationStep(
            order=i + 1,
            description=s.get("description", ""),
            expected=s.get("expected", ""),
            command=s.get("command", ""),
        )
        for i, s in enumerate(raw.steps)
    ]

    protocol = VerificationProtocol(
        protocol_id=f"VER-{uuid4().hex[:12]}",
        idea_id=idea_id,
        title=title,
        hypothesis=claim,
        steps=steps,
        expected_outcomes=raw.expected_outcomes,
        kill_criteria=raw.kill_criteria,
        minimum_success=raw.minimum_success,
    )

    append_jsonl(VERIFICATION_PATH, protocol.model_dump(mode="json"))
    logger.info("Protocol %s generated for idea %s", protocol.protocol_id, idea_id)
    return protocol


def list_protocols(idea_id: str | None = None, limit: int = 20) -> list[VerificationProtocol]:
    raw = _latest_by_key(list(iter_jsonl(VERIFICATION_PATH)), "protocol_id")
    all_protos = [VerificationProtocol.model_validate(r) for r in raw]
    all_protos.sort(key=lambda p: p.created_at, reverse=True)
    if idea_id:
        all_protos = [p for p in all_protos if p.idea_id == idea_id]
    return all_protos[:limit]


def get_protocol(protocol_id: str) -> VerificationProtocol | None:
    for proto in list_protocols(limit=10_000):
        if proto.protocol_id == protocol_id:
            return proto
    return None


def update_protocol_status(protocol_id: str, status: str) -> VerificationProtocol | None:
    """Append a status-update snapshot (append-only)."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"invalid status {status!r}; allowed={sorted(ALLOWED_STATUSES)}")
    current = get_protocol(protocol_id)
    if current is None:
        return None
    updated = current.model_copy(update={"status": status})
    append_jsonl(VERIFICATION_PATH, updated.model_dump(mode="json"))
    return updated
