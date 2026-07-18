"""High-level pipeline orchestration stubs."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from arc.memory import list_projects, load_researcher_profile
from arc.paths import ensure_runtime_dirs
from arc.reporting import write_daily_reports
from arc.schemas import RunLog


def build_skeleton_daily_context(day: date | None = None) -> dict:
    """Minimal context so templates and CLI can smoke without ingest."""
    day = day or date.today()
    profile = {}
    try:
        profile = load_researcher_profile()
    except FileNotFoundError:
        pass
    projects = list_projects()
    return {
        "date": day.isoformat(),
        "mode": "daily_lite",
        "brand": "ARC",
        "subtitle": "Aki Research Council",
        "profile_name": profile.get("name", "researcher"),
        "projects": projects,
        "headlines": [
            {
                "title": "管线尚未接入实时抓取",
                "why": "当前为骨架阶段：配置、状态与渲染已就位。",
                "confidence": "high",
                "action": "继续实现 P1 ingest",
            }
        ],
        "state_changes": "今日没有足以改变现有研究判断的新证据。（骨架占位）",
        "featured_papers": [],
        "radar": [],
        "ideas": [],
        "actions": [
            "完善 arXiv 增量抓取",
            "接通两阶段筛选",
            "用真实论文填充晨报",
        ],
        "partial": True,
    }


def run_daily_skeleton(day: date | None = None) -> RunLog:
    ensure_runtime_dirs()
    day = day or date.today()
    started = datetime.now(UTC)
    context = build_skeleton_daily_context(day)
    write_daily_reports(day.isoformat(), context)
    finished = datetime.now(UTC)
    return RunLog(
        run_id=str(uuid4()),
        started_at=started,
        finished_at=finished,
        mode="daily_lite",
        status="partial",
        failures=["ingest_not_implemented"],
    )
