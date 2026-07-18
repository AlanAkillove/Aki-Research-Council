"""Tests for normalization and two-stage screening."""

from __future__ import annotations

import json
from pathlib import Path

from arc.ingestion.store import PaperStore
from arc.normalization import (
    DedupResult,
    check_dedup,
    run_normalization,
    title_fingerprint,
)
from arc.ranking import (
    HardFilterConfig,
    composite_score,
    load_hard_filter_config,
    passes_hard_filter,
)
from arc.schemas import Paper, ScreenScores, PipelineStatus


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def test_title_fingerprint_consistency() -> None:
    assert title_fingerprint("Hello, World!") == "hello world"
    assert title_fingerprint("  Hello--World!!  ") == "hello world"
    assert title_fingerprint("A Novel Method") == "a novel method"
    assert title_fingerprint("A Novel Method 2.0") == "a novel method 2 0"


def test_dedup_no_match(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    p1 = Paper(
        canonical_id="arxiv:2607.10001",
        arxiv_id="2607.10001",
        title="Unique Paper",
        authors=[],
        categories=[],
    )
    store.upsert_paper(p1)
    store.get_papers(status=None)  # ensure commited

    p2 = Paper(
        canonical_id="arxiv:2607.10002",
        arxiv_id="2607.10002",
        title="Another Unique Paper",
        authors=[],
        categories=[],
    )
    result = check_dedup(store, p2)
    assert not result.is_duplicate
    store.close()


def test_dedup_by_arxiv_id(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    p1 = Paper(
        canonical_id="arxiv:2607.99999",
        arxiv_id="2607.99999",
        title="Original",
        authors=[],
        categories=[],
    )
    store.upsert_paper(p1)

    # Same arxiv_id, different canonical_id (shouldn't happen in practice
    # but tests the dedup logic)
    p2 = Paper(
        canonical_id="doi:10.1/xyz",
        arxiv_id="2607.99999",
        title="Original",
        authors=[],
        categories=[],
    )
    result = check_dedup(store, p2)
    assert result.is_duplicate
    assert result.match_reason == "arxiv_id"
    store.close()


def test_dedup_by_title_fingerprint(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    p1 = Paper(
        canonical_id="arxiv:2607.11111",
        arxiv_id="2607.11111",
        title="A Novel Method for Math Reasoning",
        authors=[],
        categories=[],
        processing_status=PipelineStatus.NORMALIZED.value,
    )
    store.upsert_paper(p1)

    # Build fp_index like run_normalization would
    from arc.normalization import _build_fp_index

    fp_index = _build_fp_index(store)

    # Same title, different source
    p2 = Paper(
        canonical_id="doi:10.2/abc",
        title="A Novel Method for Math Reasoning",
        authors=[],
        categories=[],
    )
    result = check_dedup(store, p2, fp_index)
    assert result.is_duplicate
    assert result.match_reason == "title_fingerprint"
    store.close()


def test_run_normalization_empty(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    report = run_normalization(store)
    assert report.processed == 0
    assert report.normalized == 0
    store.close()


def test_run_normalization_processes_papers(tmp_path: Path) -> None:
    store = PaperStore(tmp_path)
    p1 = Paper(
        canonical_id="arxiv:2607.20001",
        arxiv_id="2607.20001",
        title="First Real Paper",
        authors=["Alice"],
        categories=["cs.AI"],
    )
    store.upsert_paper(p1)

    report = run_normalization(store)
    assert report.processed == 1
    assert report.normalized == 1
    assert report.duplicates == 0
    assert len(report.errors) == 0

    # Paper should now be NORMALIZED
    updated = store.get_paper("arxiv:2607.20001")
    assert updated is not None
    assert updated.processing_status == PipelineStatus.NORMALIZED.value
    store.close()


# ---------------------------------------------------------------------------
# Hard filter
# ---------------------------------------------------------------------------


def test_passes_hard_filter_topic_match() -> None:
    cfg = HardFilterConfig(
        topic_keywords={"ai_for_math": ["theorem", "proving", "lean"]},
        allowed_categories={"cs.AI", "cs.LG"},
    )
    paper = Paper(
        canonical_id="arxiv:2607.30001",
        arxiv_id="2607.30001",
        title="Theorem Proving with Lean",
        authors=[],
        categories=["cs.AI"],
        abstract="We present a new method for theorem proving.",
    )
    ok, reason = passes_hard_filter(paper, cfg)
    assert ok, f"expected pass, got: {reason}"


def test_passes_hard_filter_no_match() -> None:
    cfg = HardFilterConfig(
        topic_keywords={"ai_for_math": ["theorem", "proving"]},
        allowed_categories={"cs.AI"},
    )
    paper = Paper(
        canonical_id="arxiv:2607.30002",
        arxiv_id="2607.30002",
        title="Image Classification Benchmarks",
        authors=[],
        categories=["cs.CV"],
        abstract="Benchmarking image classifiers.",
    )
    ok, reason = passes_hard_filter(paper, cfg)
    # Category cs.CV not in allowed_categories
    assert not ok


def test_passes_hard_filter_negative_keyword() -> None:
    cfg = HardFilterConfig(
        topic_keywords={"ai_for_math": ["theorem"]},
        allowed_categories={"cs.AI"},
        negative_keywords=["large-scale pretraining"],
    )
    paper = Paper(
        canonical_id="arxiv:2607.30003",
        arxiv_id="2607.30003",
        title="Large-Scale Pretraining for Theorem Proving",
        authors=[],
        categories=["cs.AI"],
        abstract="Using large-scale pretraining.",
    )
    ok, reason = passes_hard_filter(paper, cfg)
    assert not ok
    assert "large-scale pretraining" in reason


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------


def test_composite_score_default_weights() -> None:
    from arc.config import RankingConfig

    scores = ScreenScores(
        topic_relevance=0.8,
        project_relevance=0.9,
        method_transferability=0.3,
        novelty_signal=0.6,
        feasibility=0.7,
        evidence_quality=0.5,
        redundancy=0.1,
    )
    ranking = RankingConfig()
    s = composite_score(scores, ranking)
    # Expected: 0.25*0.9 + 0.15*0.3 + 0.15*0.5 + 0.15*0.7 + 0.10*0.6 + 0.10*0.8 - 0.20*0.1
    expected = (
        0.25 * 0.9 + 0.15 * 0.3 + 0.15 * 0.5 + 0.15 * 0.7 + 0.10 * 0.6 + 0.10 * 0.8 - 0.20 * 0.1
    )
    assert abs(s - expected) < 1e-10


# ---------------------------------------------------------------------------
# Daily context builder
# ---------------------------------------------------------------------------


def test_build_daily_context_no_candidates():
    """Verify context builder produces valid output with empty report."""
    from datetime import date
    from arc.ranking import ScreeningReport
    from arc.pipeline import build_daily_context

    report = ScreeningReport(stage1_passed=0, stage2_screened=0, featured=0)
    ctx = build_daily_context(date(2026, 7, 18), report)

    assert ctx["date"] == "2026-07-18"
    assert ctx["headlines"][0]["title"] == "今日没有显著新信号"
    assert "没有足以改变" in ctx["state_changes"]
    assert ctx["featured_papers"] == []
    assert ctx["actions"] == ["继续监测 arXiv 新论文。"]
    assert ctx["partial"] is False
