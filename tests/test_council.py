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


# ---------------------------------------------------------------------------
# Idea lifecycle
# ---------------------------------------------------------------------------


def test_idea_write_and_list(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")

    i1 = mem.write_idea(title="Test Idea", claim="A novel approach")
    assert i1.idea_id.startswith("IDEA-")
    assert i1.stage.value == "signal"

    i2 = mem.write_idea(title="Hypothesis Idea", claim="Better method", stage="hypothesis")
    assert i2.stage.value == "hypothesis"

    ideas = mem.list_ideas()
    assert len(ideas) == 2

    signals = mem.list_ideas(stage="signal")
    assert len(signals) == 1
    assert signals[0].title == "Test Idea"


def test_idea_transition(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")

    idea = mem.write_idea(title="Growing Idea")
    assert idea.stage.value == "signal"

    # Valid: signal -> hypothesis
    updated = mem.transition_idea(idea.idea_id, "hypothesis")
    assert updated is not None
    assert updated.stage.value == "hypothesis"

    # Valid: hypothesis -> candidate
    updated = mem.transition_idea(idea.idea_id, "candidate")
    assert updated is not None
    assert updated.stage.value == "candidate"


def test_idea_invalid_transition(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")

    idea = mem.write_idea(title="Skip")
    assert idea.stage.value == "signal"

    # Invalid: signal -> active_project
    import pytest

    with pytest.raises(ValueError, match="Cannot transition"):
        mem.transition_idea(idea.idea_id, "active_project")


def test_idea_rejected_is_terminal(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")

    idea = mem.write_idea(title="Doomed Idea")
    mem.transition_idea(idea.idea_id, "rejected")

    import pytest

    with pytest.raises(ValueError, match="Cannot transition"):
        mem.transition_idea(idea.idea_id, "signal")
