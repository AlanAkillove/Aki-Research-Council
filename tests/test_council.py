"""Tests for council roles and claim ledger."""

from __future__ import annotations

import json
from pathlib import Path

from arc.council.schemas import (
    ChairOutput,
    HistorianOutput,
    LiaisonOutput,
    SkepticOutput,
)
from arc.memory import approve_claim, list_claims, write_claim


# ---------------------------------------------------------------------------
# Council output schemas
# ---------------------------------------------------------------------------


def test_skeptic_output_defaults() -> None:
    s = SkepticOutput()
    assert s.verdict == "insufficient_evidence"
    assert s.attack_points == []


def test_historian_output_defaults() -> None:
    h = HistorianOutput()
    assert h.novelty_label == "证据不足，不能判断"


def test_liaison_output_defaults() -> None:
    l = LiaisonOutput()
    assert l.impact == "neutral"


def test_chair_output_actions_limit() -> None:
    c = ChairOutput(verdict="READ", actions=["a", "b", "c"])
    assert len(c.actions) == 3
    # Pydantic max_length on list is enforced during validation


def test_chair_output_serialize() -> None:
    c = ChairOutput(
        verdict="NO-GO",
        confidence=0.8,
        rationale=["Not novel enough", "Requires too much compute"],
        actions=["Archive"],
    )
    data = c.model_dump(mode="json")
    assert data["verdict"] == "NO-GO"
    assert len(data["rationale"]) == 2
    # Round-trip
    c2 = ChairOutput.model_validate(data)
    assert c2.verdict == c.verdict


# ---------------------------------------------------------------------------
# Claim ledger
# ---------------------------------------------------------------------------


def test_claim_write_and_list(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")

    c1 = write_claim("arxiv:2607.100", "This method is novel", "fact", generated_by="historian")
    assert c1.claim_id.startswith("CLM-")
    assert c1.paper_id == "arxiv:2607.100"
    assert c1.type.value == "fact"

    c2 = write_claim("arxiv:2607.100", "Evidence is insufficient", "inference", generated_by="skeptic")
    assert c2.generated_by == "skeptic"

    claims = list_claims(paper_id="arxiv:2607.100")
    assert len(claims) == 2
    # Both claims should be for the same paper regardless of order
    assert all(c.paper_id == "arxiv:2607.100" for c in claims)


def test_claim_approve(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")

    c = write_claim("arxiv:2607.200", "Chair decision", "recommendation", generated_by="chair")
    assert c.approved_by is None

    approved = approve_claim(c.claim_id)
    assert approved is not None
    assert approved.approved_by == "chair"

    # Verify re-read shows approved
    claims = list_claims()
    assert claims[0].approved_by == "chair"


def test_claim_approve_idempotent(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")

    c = write_claim("arxiv:2607.300", "Test", "hypothesis")
    approve_claim(c.claim_id)
    # Second approve should return None (already approved)
    result = approve_claim(c.claim_id)
    assert result is None
