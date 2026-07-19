"""Tests for council roles, claim ledger gates, and idea lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest

from arc.council.schemas import (
    ChairOutput,
    HistorianOutput,
    LiaisonOutput,
    SkepticOutput,
)
from arc.memory import approve_claim, list_claims, write_claim
from arc.schemas import NoveltyLabel, Verdict


def test_skeptic_output_defaults() -> None:
    s = SkepticOutput()
    assert s.verdict == "insufficient_evidence"


def test_historian_output_defaults() -> None:
    h = HistorianOutput()
    assert h.novelty_label == NoveltyLabel.INSUFFICIENT_EVIDENCE


def test_liaison_output_defaults() -> None:
    assert LiaisonOutput().impact == "neutral"


def test_chair_output_actions_limit() -> None:
    c = ChairOutput(verdict=Verdict.READ, actions=["a", "b", "c"])
    assert len(c.actions) == 3


def test_chair_output_serialize() -> None:
    c = ChairOutput(
        verdict=Verdict.NO_GO,
        confidence=0.8,
        rationale=["Not novel enough", "Requires too much compute"],
        actions=["Archive"],
    )
    data = c.model_dump(mode="json")
    assert data["verdict"] == "NO-GO"
    c2 = ChairOutput.model_validate(data)
    assert c2.verdict == c.verdict


def test_fact_requires_evidence(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")
    with pytest.raises(ValueError, match="evidence"):
        write_claim("arxiv:2607.100", "This method is novel", "fact")


def test_claim_write_and_list(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")

    c1 = write_claim(
        "arxiv:2607.100",
        "Authors claim novelty",
        "author_claim",
        evidence_ids=["EV-1"],
        generated_by="historian",
    )
    assert c1.claim_id.startswith("CLM-")

    c2 = write_claim(
        "arxiv:2607.100",
        "Evidence is insufficient",
        "inference",
        generated_by="skeptic",
    )
    claims = list_claims(paper_id="arxiv:2607.100")
    assert len(claims) == 2
    assert {c.claim_id for c in claims} == {c1.claim_id, c2.claim_id}


def test_claim_approve_append_only(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    path = tmp_path / "claims.jsonl"
    monkeypatch.setattr(mem, "CLAIMS_PATH", path)

    c = write_claim("arxiv:2607.200", "Chair decision", "recommendation", generated_by="chair")
    approved = approve_claim(c.claim_id)
    assert approved is not None
    assert approved.approved_by == "chair"

    # File grew (append), not rewritten to a single line
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2

    claims = list_claims()
    assert len(claims) == 1
    assert claims[0].approved_by == "chair"
    assert list_claims(approved_only=True)[0].claim_id == c.claim_id


def test_claim_approve_idempotent(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "CLAIMS_PATH", tmp_path / "claims.jsonl")
    c = write_claim("arxiv:2607.300", "Test", "hypothesis")
    approve_claim(c.claim_id)
    assert approve_claim(c.claim_id) is None


def test_idea_write_only_signal(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")
    i1 = mem.write_idea(title="Test Idea", claim="A novel approach")
    assert i1.stage.value == "signal"
    with pytest.raises(ValueError, match="signal"):
        mem.write_idea(title="Skip", stage="hypothesis")


def test_idea_transition_append_only(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    path = tmp_path / "ideas.jsonl"
    monkeypatch.setattr(mem, "IDEAS_PATH", path)

    idea = mem.write_idea(title="Growing Idea")
    updated = mem.transition_idea(idea.idea_id, "hypothesis")
    assert updated is not None
    assert updated.stage.value == "hypothesis"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert mem.list_ideas()[0].stage.value == "hypothesis"


def test_idea_invalid_transition(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")
    idea = mem.write_idea(title="Skip")
    with pytest.raises(ValueError, match="Cannot transition"):
        mem.transition_idea(idea.idea_id, "active_project")


def test_idea_rejected_requires_reason(tmp_path: Path, monkeypatch) -> None:
    import arc.memory as mem

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")
    idea = mem.write_idea(title="Doomed Idea")
    with pytest.raises(ValueError, match="rejection_reason"):
        mem.transition_idea(idea.idea_id, "rejected")
    updated = mem.transition_idea(
        idea.idea_id,
        "rejected",
        rejection_reason="covered by prior work",
        revive_when=["new formalization"],
    )
    assert updated is not None
    assert updated.rejection_reason == "covered by prior work"
    with pytest.raises(ValueError, match="Cannot transition"):
        mem.transition_idea(idea.idea_id, "signal")
