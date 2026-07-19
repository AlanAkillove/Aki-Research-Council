"""Regression tests for audit findings (date parse, DOI key, tournament, verify)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from arc.ingestion.store import PaperStore
from arc.normalization import check_dedup, pick_canonical_id
from arc.ranking import _paper_date
from arc.schemas import Paper
from arc.verify import list_protocols, update_protocol_status


def test_arxiv_yymm_date_parse() -> None:
    p = Paper(canonical_id="arxiv:2607.1", title="t", arxiv_id="2607.12345")
    d = _paper_date(p)
    assert d == date(2026, 7, 1)


def test_published_at_preferred() -> None:
    p = Paper(
        canonical_id="arxiv:2607.1",
        title="t",
        arxiv_id="2607.12345",
        published_at="2026-01-15T12:00:00Z",
    )
    assert _paper_date(p) == date(2026, 1, 15)


def test_doi_dedup_uses_canonical_key(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    existing = Paper(
        canonical_id=pick_canonical_id(doi="10.1234/foo"),
        doi="10.1234/foo",
        title="Existing",
    )
    store.upsert_paper(existing)
    dup = Paper(
        canonical_id="arxiv:2607.9",
        arxiv_id="2607.9",
        doi="10.1234/foo",
        title="Other title",
    )
    result = check_dedup(store, dup)
    assert result.is_duplicate
    assert result.match_reason == "doi"
    store.close()


def test_upsert_preserve_status(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    p = Paper(
        canonical_id="arxiv:2607.1",
        arxiv_id="2607.1",
        title="T",
        processing_status="SCREENED",
    )
    store.upsert_paper(p)
    p2 = Paper(
        canonical_id="arxiv:2607.1",
        arxiv_id="2607.1",
        title="T updated",
        abstract="new",
        processing_status="metadata_only",
        versions=["v1", "v2"],
    )
    store.upsert_paper(p2, preserve_status=True)
    got = store.get_paper("arxiv:2607.1")
    assert got is not None
    assert got.processing_status == "SCREENED"
    assert got.versions == ["v1", "v2"]
    store.close()


def test_verify_status_append_only(tmp_path: Path, monkeypatch) -> None:
    import arc.verify as ver
    from arc.schemas import VerificationProtocol

    path = tmp_path / "verifications.jsonl"
    monkeypatch.setattr(ver, "VERIFICATION_PATH", path)

    proto = VerificationProtocol(
        protocol_id="VER-test",
        idea_id="IDEA-1",
        title="t",
        status="draft",
    )
    from arc.memory import append_jsonl

    append_jsonl(path, proto.model_dump(mode="json"))
    updated = update_protocol_status("VER-test", "active")
    assert updated is not None
    assert updated.status == "active"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) == 2
    assert list_protocols()[0].status == "active"
    with pytest.raises(ValueError):
        update_protocol_status("VER-test", "bogus")


def test_tournament_no_false_promote(tmp_path: Path, monkeypatch) -> None:
    import asyncio

    import arc.memory as mem
    from arc.council.tournament import run_tournament
    from arc.providers import EchoModelProvider

    monkeypatch.setattr(mem, "IDEAS_PATH", tmp_path / "ideas.jsonl")
    idea = mem.write_idea(title="Candidate", claim="c")
    mem.transition_idea(idea.idea_id, "hypothesis")
    mem.transition_idea(idea.idea_id, "candidate")

    out = asyncio.run(run_tournament(EchoModelProvider(), auto_promote=False))
    assert out.winner_id == idea.idea_id
    assert out.advanced_to == ""
    assert mem.get_idea(idea.idea_id).stage.value == "candidate"

    out2 = asyncio.run(run_tournament(EchoModelProvider(), auto_promote=True))
    assert out2.advanced_to == "validated_candidate"
    assert mem.get_idea(idea.idea_id).stage.value == "validated_candidate"
