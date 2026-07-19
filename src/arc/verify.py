"""P4 — Minimal Verification Protocol generator.

From an Idea, generate a concrete, human-executable verification plan
with steps, expected outcomes, and kill criteria.

Tech Spec P4: results writeback is append-only, auto-execution OFF by default.
"""

from __future__ import annotations

import json
import logging
import os
from uuid import uuid4

from pydantic import BaseModel

from arc.memory import append_jsonl
from arc.paths import RESEARCH_STATE_DIR
from arc.providers import ModelProvider
from arc.schemas import VERIFICATION_FILE, VerificationProtocol, VerificationStep

logger = logging.getLogger(__name__)

VERIFICATION_PATH = RESEARCH_STATE_DIR / VERIFICATION_FILE

# P4 safety switch — OFF by default (Tech Spec P4.2)
_AUTO_EXEC_KEY = "ARC_AUTO_EXECUTION"


def is_auto_execution_enabled() -> bool:
    """Check whether auto-execution is explicitly enabled.

    Reads from environment variable ARC_AUTO_EXECUTION.
    Must be "1" or "true" to enable. Default: OFF.
    """
    val = os.environ.get(_AUTO_EXEC_KEY, "0").strip().lower()
    return val in ("1", "true")


def require_auto_execution() -> None:
    """Guard: raise if auto-execution not enabled."""
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
    """Generate a verification protocol from an Idea using LLM.

    Returns a ``VerificationProtocol`` with concrete steps and criteria.
    The protocol is appended to ``verifications.jsonl``.
    """
    context = {
        "idea_id": idea_id,
        "title": title,
        "claim": claim,
        "current_stage": stage,
    }

    raw = await provider.generate("generate_protocol", _ProtocolResponse, context)

    steps = [
        VerificationStep(order=i + 1, description=s.get("description", ""),
                         expected=s.get("expected", ""), command=s.get("command", ""))
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
    """List stored verification protocols."""
    from arc.memory import iter_jsonl

    all_protos = [VerificationProtocol.model_validate(r) for r in iter_jsonl(VERIFICATION_PATH)]
    all_protos.sort(key=lambda p: p.created_at, reverse=True)
    if idea_id:
        all_protos = [p for p in all_protos if p.idea_id == idea_id]
    return all_protos[:limit]


def update_protocol_status(protocol_id: str, status: str) -> VerificationProtocol | None:
    """Update protocol status (draft|active|passed|failed)."""
    lines = []
    found = None
    if not VERIFICATION_PATH.exists():
        return None

    with VERIFICATION_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("protocol_id") == protocol_id:
                record["status"] = status
                found = VerificationProtocol.model_validate(record)
            lines.append(json.dumps(record, ensure_ascii=False))

    if found:
        VERIFICATION_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return found
