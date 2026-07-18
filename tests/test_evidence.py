"""Tests for evidence store and Evidence Pack Builder."""

from __future__ import annotations

from pathlib import Path

from arc.ingestion.store import PaperStore
from arc.schemas import Evidence, EvidenceType, Paper, SourceTier


def test_evidence_store_create_table(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    assert store.conn is not None
    store.close()


def test_evidence_crud(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    paper = Paper(
        canonical_id="arxiv:2607.evidence_test",
        arxiv_id="2607.evidence_test",
        title="Evidence Test Paper",
        authors=[],
        categories=[],
    )
    store.upsert_paper(paper)

    ev = Evidence(
        id="EV-test001",
        paper_id="arxiv:2607.evidence_test",
        content="The proposed method achieves 95% accuracy.",
        evidence_type=EvidenceType.EXPERIMENT,
        source_tier=SourceTier.A,
        extraction_method="api",
        confidence=0.9,
        location={"section": "4.2"},
    )
    eid = store.upsert_evidence(ev)
    assert eid == "EV-test001"

    fetched = store.get_evidence("EV-test001")
    assert fetched is not None
    assert fetched.content == ev.content
    assert fetched.evidence_type == EvidenceType.EXPERIMENT
    assert fetched.location == {"section": "4.2"}

    by_paper = store.get_evidence_by_paper("arxiv:2607.evidence_test")
    assert len(by_paper) == 1
    assert by_paper[0].id == "EV-test001"

    # Count
    assert store.count_evidence() == 1
    assert store.count_evidence("arxiv:2607.evidence_test") == 1
    assert store.count_evidence("nonexistent") == 0

    store.close()


def test_evidence_builder_with_echo(tmp_path: Path) -> None:
    """Verify build_evidence_pack works with EchoModelProvider."""
    import asyncio

    from arc.evidence import build_evidence_pack
    from arc.providers import EchoModelProvider

    store = PaperStore(tmp_path)
    paper = Paper(
        canonical_id="arxiv:2607.echo_ev",
        arxiv_id="2607.echo_ev",
        title="Echo Evidence Test",
        authors=[],
        categories=[],
        abstract="Testing evidence extraction.",
    )
    store.upsert_paper(paper)

    provider = EchoModelProvider()
    ev_list = asyncio.run(build_evidence_pack(store, paper, provider))
    assert len(ev_list) == 2
    assert ev_list[0].evidence_type == EvidenceType.CLAIM
    assert ev_list[1].evidence_type == EvidenceType.EXPERIMENT
    store.close()
