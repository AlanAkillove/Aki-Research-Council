"""Editorial daily brief experiments."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from arc.providers import EchoModelProvider
from arc.reporting import render_editorial_html, render_editorial_markdown
from arc.reporting.editor import (
    brief_to_template_context,
    demo_candidates_packet,
    fallback_brief_from_packet,
    write_daily_brief,
)


def test_fallback_brief_has_project_links() -> None:
    brief = fallback_brief_from_packet(demo_candidates_packet())
    assert brief.quiet_day is False
    assert len(brief.headlines) >= 1
    assert any(h.question_id for h in brief.headlines)
    assert len(brief.actions) <= 3
    assert "摘要" not in brief.lede


def test_quiet_day_omits_filler() -> None:
    brief = fallback_brief_from_packet([], quiet=True)
    assert brief.quiet_day is True
    assert brief.headlines == []
    assert brief.state_changes is None
    ctx = brief_to_template_context(brief, day=date(2026, 7, 19))
    assert ctx["show_headlines"] is False
    assert ctx["show_state"] is False
    md = render_editorial_markdown(ctx)
    assert "安静日" in md or "没有足以改写" in md
    assert "## 今日判断" not in md


def test_echo_write_daily_brief() -> None:
    brief = asyncio.run(
        write_daily_brief(
            EchoModelProvider(),
            day=date(2026, 7, 19),
            candidates=demo_candidates_packet(),
        )
    )
    ctx = brief_to_template_context(brief, day=date(2026, 7, 19))
    html = render_editorial_html(ctx)
    assert "Q-CV-014" in html or "Q-MAT-001" in html
    assert "Cormorant" in html or "lede" in html
