"""Unit tests for skeleton utilities."""

from __future__ import annotations

import asyncio
from datetime import date

from arc.config import load_ranking_config, load_sources_config
from arc.normalization import pick_canonical_id, title_fingerprint
from arc.pipeline import build_skeleton_daily_context, run_daily_skeleton
from arc.providers import EchoModelProvider
from arc.ranking import composite_score
from arc.reporting import render_daily_html, render_daily_markdown
from arc.schemas import ScreenScores, Verdict


def test_title_fingerprint() -> None:
    assert title_fingerprint("Hello, World!") == "hello world"


def test_canonical_id_priority() -> None:
    assert pick_canonical_id(doi="10.1/x", arxiv_id="2607.1") == "doi:10.1/x"
    assert pick_canonical_id(arxiv_id="2607.1") == "arxiv:2607.1"


def test_configs_load() -> None:
    sources = load_sources_config()
    assert "arxiv" in sources
    ranking = load_ranking_config()
    assert ranking.daily_limits.featured_papers == 3


def test_echo_screen_and_score() -> None:
    scores = asyncio.run(EchoModelProvider().generate("screen", ScreenScores, {}))
    s = composite_score(scores, load_ranking_config())
    assert isinstance(s, float)


def test_verdict_enum() -> None:
    assert Verdict.NO_GO.value == "NO-GO"


def test_skeleton_report_renders(tmp_path, monkeypatch) -> None:
    from arc import paths, reporting

    monkeypatch.setattr(paths, "REPORTS_DIR", tmp_path / "reports")
    monkeypatch.setattr(reporting, "REPORTS_DIR", tmp_path / "reports")
    ctx = build_skeleton_daily_context(date(2026, 7, 18))
    md = render_daily_markdown(ctx)
    html = render_daily_html(ctx)
    assert "ARC" in md and "今日结论" in md
    assert "ARC" in html and "--arc-canvas" in html
    run = run_daily_skeleton(date(2026, 7, 18))
    assert run.status == "partial"
    assert (tmp_path / "reports" / "daily" / "2026-07-18.md").exists()
