"""High-level pipeline orchestration stubs."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime
from uuid import uuid4

from arc.ingestion import ArxivClient, PaperStore
from arc.memory import list_projects, load_researcher_profile
from arc.normalization import run_normalization
from arc.paths import DATA_DIR, ensure_runtime_dirs
from arc.ranking import run_screening, ScreeningReport
from arc.reporting import write_daily_reports
from arc.schemas import RunLog, PipelineStatus


async def run_ingest_step(
    day: date | None = None,
    force_all: bool = False,
) -> dict[str, tuple[int, int]]:
    """Run the daily arXiv ingestion step.

    Returns per-category ``(new_count, total_count)`` dict.
    """
    store = PaperStore(DATA_DIR / "indexes")
    client = ArxivClient(store)
    try:
        results = await client.ingest_all_categories(
            max_results=200,
            force_all=force_all,
        )
        return results
    finally:
        await client.close()


def run_normalize_step() -> dict:
    """Run the paper normalisation step (synchronous).

    Returns a dict with keys from ``NormalizationReport``.
    """
    store = PaperStore(DATA_DIR / "indexes")
    try:
        report = run_normalization(store)
        return {
            "processed": report.processed,
            "normalized": report.normalized,
            "duplicates": report.duplicates,
            "errors": report.errors,
        }
    finally:
        store.close()


async def run_screening_step(
    provider: ModelProvider | None = None,
) -> dict:
    """Run the two-stage screening pipeline (async).

    Returns a serialisable report dict.
    """
    from arc.config import load_models_config
    from arc.providers.openai_compatible import OpenAICompatibleProvider

    store = PaperStore(DATA_DIR / "indexes")
    try:
        if provider is None:
            models = load_models_config()
            provider = OpenAICompatibleProvider(models.triage)

        report = await run_screening(store, provider)
        return {
            "stage1_passed": report.stage1_passed,
            "stage2_screened": report.stage2_screened,
            "featured": report.featured,
            "errors": report.errors,
            "top_candidates": [
                {
                    "canonical_id": c.paper.canonical_id,
                    "title": c.paper.title[:80],
                    "composite": round(c.composite, 3),
                }
                for c in report.candidates[: report.featured]
            ],
        }
    finally:
        store.close()


# ---------------------------------------------------------------------------
# Daily context builder (real data)
# ---------------------------------------------------------------------------


def _score_to_confidence(composite: float) -> str:
    """Map composite score to human-readable confidence."""
    if composite >= 0.7:
        return "high"
    if composite >= 0.4:
        return "medium"
    return "low"


def build_daily_context(
    day: date,
    screen_report: ScreeningReport,
    ingest_results: dict[str, tuple[int, int]] | None = None,
) -> dict:
    """Build Jinja2 context from real screening results and research state.

    Template fields (see ``templates/daily/``):
    - headlines, state_changes, featured_papers, radar, ideas, actions
    """
    profile = {}
    try:
        profile = load_researcher_profile()
    except FileNotFoundError:
        pass
    projects = list_projects()

    # --- Headlines: top scored candidates ---
    headlines = []
    for sp in screen_report.candidates[:3]:
        p = sp.paper
        headlines.append({
            "title": p.title[:100],
            "why": (p.abstract[:200] + "…") if len(p.abstract) > 200 else p.abstract,
            "confidence": _score_to_confidence(sp.composite),
            "composite": round(sp.composite, 3),
            "action": sp.scores.recommended_action,
            "source": p.source_url or f"https://arxiv.org/abs/{p.arxiv_id}" if p.arxiv_id else "",
        })

    if not headlines:
        headlines.append({
            "title": "今日没有显著新信号",
            "why": "筛选后无足够证据改变当前研究判断。",
            "confidence": "high",
            "action": "continue_monitoring",
        })

    # --- Featured papers: all passed candidates ---
    featured_papers = []
    for sp in screen_report.candidates[:5]:
        p = sp.paper
        featured_papers.append({
            "title": p.title[:120],
            "canonical_id": p.canonical_id,
            "verdict": sp.scores.recommended_action.upper(),
            "score": round(sp.composite, 3),
            "authors": ", ".join(p.authors[:3]) + ("…" if len(p.authors) > 3 else ""),
            "source": p.source_url or f"https://arxiv.org/abs/{p.arxiv_id}" if p.arxiv_id else "",
        })

    # --- Radar: weak signals from stage 1 candidates not stage-2-screened ---
    radar = []
    if screen_report.stage1_passed > screen_report.stage2_screened:
        radar.append(f"{screen_report.stage1_passed - screen_report.stage2_screened} 篇通过硬过滤但未进入 LLM 评审")
    if ingest_results:
        total_new = sum(v[0] for v in ingest_results.values())
        if total_new:
            radar.append(f"arXiv 新抓取 {total_new} 篇论文待处理")

    # --- Actions ---
    actions = []
    for sp in screen_report.candidates[:3]:
        action_label = sp.scores.recommended_action
        if action_label == "read":
            actions.append(f"精读：{sp.paper.title[:80]}")
        elif action_label == "watch":
            actions.append(f"跟踪：{sp.paper.title[:80]}")
    if screen_report.errors:
        actions.append(f"处理 {len(screen_report.errors)} 个筛选错误")
    if not actions:
        actions.append("继续监测 arXiv 新论文。")

    # --- State changes ---
    if screen_report.featured > 0:
        state_changes = (
            f"今日 {screen_report.featured} 篇论文进入候选。"
            f"Stage 1 硬过滤通过 {screen_report.stage1_passed} 篇，"
            f"Stage 2 LLM 评审 {screen_report.stage2_screened} 篇。"
        )
    else:
        state_changes = "今日没有足以改变现有研究判断的新证据。"

    return {
        "date": day.isoformat(),
        "mode": "daily_lite",
        "brand": "ARC",
        "subtitle": "Aki Research Council",
        "profile_name": profile.get("name", "researcher"),
        "projects": projects,
        "headlines": headlines,
        "state_changes": state_changes,
        "featured_papers": featured_papers,
        "radar": radar,
        "ideas": [],
        "actions": actions,
        "partial": bool(screen_report.errors),
    }


# ---------------------------------------------------------------------------
# Skeleton (legacy — used when no ingest/real data available)
# ---------------------------------------------------------------------------


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


async def run_daily_full(
    day: date | None = None,
    force_ingest_all: bool = False,
) -> RunLog:
    """Full daily pipeline: ingest → normalize → screen → report.

    Returns ``RunLog`` with status and metrics.
    """
    from arc.config import load_models_config
    from arc.providers.openai_compatible import OpenAICompatibleProvider

    ensure_runtime_dirs()
    day = day or date.today()
    started = datetime.now(UTC)
    failures: list[str] = []

    # Step 1 — Ingest
    ingest_results: dict[str, tuple[int, int]] = {}
    try:
        store = PaperStore(DATA_DIR / "indexes")
        client = ArxivClient(store)
        try:
            ingest_results = await client.ingest_all_categories(
                max_results=200, force_all=force_ingest_all
            )
        finally:
            await client.close()
            store.close()
    except Exception as exc:
        failures.append(f"ingest: {exc}")

    # Step 2 — Normalize
    try:
        store = PaperStore(DATA_DIR / "indexes")
        try:
            run_normalization(store)
        finally:
            store.close()
    except Exception as exc:
        failures.append(f"normalize: {exc}")

    # Step 3 — Screen
    screen_report = ScreeningReport()
    try:
        store = PaperStore(DATA_DIR / "indexes")
        models = load_models_config()
        provider = OpenAICompatibleProvider(models.triage)
        try:
            screen_report = await run_screening(store, provider)
        finally:
            store.close()
    except Exception as exc:
        failures.append(f"screen: {exc}")

    # Step 4 — Build context & render
    try:
        context = build_daily_context(day, screen_report, ingest_results)
        write_daily_reports(day.isoformat(), context)
    except Exception as exc:
        failures.append(f"report: {exc}")

    finished = datetime.now(UTC)
    status = "partial" if failures else "success"
    return RunLog(
        run_id=str(uuid4()),
        started_at=started,
        finished_at=finished,
        mode="daily_lite",
        status=status,
        failures=failures,
    )
