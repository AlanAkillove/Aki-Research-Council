"""Typer CLI entrypoint: `arc`."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Optional

import typer

from arc import __version__
from arc.config import load_models_config, load_ranking_config, load_sources_config
from arc.evidence import build_evidence_pack
from arc.ingestion import ArxivClient, PaperStore
from arc.memory import (
    approve_claim as _approve_claim,
    list_claims as _list_claims,
    list_ideas as _list_ideas,
    list_projects,
    load_researcher_profile,
    transition_idea as _transition_idea,
    write_claim as _write_claim,
    write_idea as _write_idea,
)
from arc.memory import list_feedback as _list_feedback
from arc.memory import write_feedback as _write_feedback
from arc.normalization import run_normalization as normalize_papers
from arc.paths import DATA_DIR, REPO_ROOT, ensure_runtime_dirs, load_env
from arc.pipeline import run_daily_full, run_daily_skeleton, run_normalize_step, run_screening_step

app = typer.Typer(
    name="arc",
    help="ARC — Aki Research Council",
    no_args_is_help=True,
)

_ingest_app = typer.Typer(help="Ingest papers from external sources")
app.add_typer(_ingest_app, name="ingest")


@app.callback()
def main() -> None:
    load_env()


@app.command("version")
def version_cmd() -> None:
    """Print package version."""
    typer.echo(__version__)


@app.command("doctor")
def doctor() -> None:
    """Check repo layout and config load."""
    ensure_runtime_dirs()
    typer.echo(f"repo: {REPO_ROOT}")
    sources = load_sources_config()
    ranking = load_ranking_config()
    models = load_models_config()
    projects = list_projects()
    typer.echo(f"channels: {list(sources.get('channels', {}).keys())}")
    typer.echo(f"daily featured limit: {ranking.daily_limits.featured_papers}")
    typer.echo(f"triage model: {models.triage.model}")
    typer.echo(f"projects: {projects or '(none)'}")
    typer.echo("doctor: ok")


@app.command("daily")
def daily(
    day: Optional[str] = typer.Option(
        None,
        "--date",
        help="YYYY-MM-DD (default: today)",
    ),
    skeleton: bool = typer.Option(
        True,
        "--skeleton/--no-skeleton",
        help="Skeleton mode vs full ingest→normalize→screen→report pipeline",
    ),
    force_all: bool = typer.Option(
        False,
        "--all",
        help="Force re-fetch all arXiv categories (only with --no-skeleton)",
    ),
) -> None:
    """Run daily brief pipeline.

    Default (--skeleton) generates a placeholder report with no network calls.
    Use --no-skeleton to run the full pipeline: ingest → normalize → screen → report.
    """
    run_day = date.fromisoformat(day) if day else date.today()
    if skeleton:
        run = run_daily_skeleton(run_day)
        typer.echo(f"run_id={run.run_id} status={run.status} mode={run.mode}")
        typer.echo(f"wrote reports/daily/{run_day.isoformat()}.md|.html")
        return

    typer.secho("Full daily pipeline: ingest → normalize → screen → report", fg=typer.colors.GREEN)
    run = asyncio.run(run_daily_full(run_day, force_ingest_all=force_all))
    typer.echo(f"run_id={run.run_id} status={run.status} mode={run.mode}")
    if run.failures:
        for f in run.failures:
            typer.secho(f"  failure: {f}", fg=typer.colors.RED)
    typer.echo(f"wrote reports/daily/{run_day.isoformat()}.md|.html")


@app.command("smoke")
def smoke() -> None:
    """Offline smoke: config + store + normalize + rank + evidence + council + feedback + report."""
    from arc.config import load_ranking_config
    from arc.normalization import pick_canonical_id, title_fingerprint
    from arc.providers import EchoModelProvider
    from arc.ranking import composite_score, HardFilterConfig, passes_hard_filter
    from arc.schemas import ScreenScores

    ensure_runtime_dirs()

    # 1. Config
    load_sources_config()
    ranking = load_ranking_config()
    assert ranking.daily_limits.featured_papers == 3

    # 2. Fingerprint & canonical ID
    fp = title_fingerprint("Hello, World!")
    assert fp == "hello world"
    cid = pick_canonical_id(arxiv_id="2607.12345")
    assert cid == "arxiv:2607.12345"

    # 3. LLM screening (echo)
    import asyncio

    scores = asyncio.run(EchoModelProvider().generate("screen", ScreenScores, {}))
    s = composite_score(scores, ranking)
    assert isinstance(s, float)

    # 4. Hard filter
    cfg = HardFilterConfig(
        topic_keywords={"ai_for_math": ["theorem"]},
        allowed_categories={"cs.AI"},
    )
    from arc.schemas import Paper

    paper = Paper(
        canonical_id="arxiv:2607.smoke",
        arxiv_id="2607.smoke",
        title="Theorem Proving with AI",
        authors=["Smoke"],
        categories=["cs.AI"],
        abstract="A theorem proving approach.",
    )
    ok, reason = passes_hard_filter(paper, cfg)
    assert ok, f"expected pass, got {reason}"

    # 5. Feedback round-trip
    from arc.memory import list_feedback, write_feedback
    from arc.schemas import FeedbackLabel

    entry = write_feedback("arxiv:2607.smoke", "值得精读", comment="smoke test")
    assert entry.paper_id == "arxiv:2607.smoke"
    entries = list_feedback(limit=5)
    matched = [e for e in entries if e.paper_id == "arxiv:2607.smoke"]
    assert len(matched) >= 1, "feedback not found"

    # 6. PaperStore round-trip
    from arc.ingestion import PaperStore
    from arc.paths import DATA_DIR

    store = PaperStore(DATA_DIR / "indexes")
    store.upsert_paper(paper)
    fetched = store.get_paper("arxiv:2607.smoke")
    assert fetched is not None and fetched.title == paper.title
    store.close()

    # 7. Evidence store round-trip
    from arc.schemas import Evidence, EvidenceType, SourceTier

    store = PaperStore(DATA_DIR / "indexes")
    ev = Evidence(
        id="EV-smoke",
        paper_id="arxiv:2607.smoke",
        content="Smoke evidence item.",
        evidence_type=EvidenceType.CLAIM,
    )
    store.upsert_evidence(ev)
    fetched_ev = store.get_evidence("EV-smoke")
    assert fetched_ev is not None and fetched_ev.content == ev.content
    store.close()

    # 8. Council role schema round-trip
    from arc.council.schemas import ChairOutput, SkepticOutput

    so = SkepticOutput(verdict="sound", attack_points=["Minor issue"])
    assert so.verdict == "sound"
    co = ChairOutput(verdict="READ", confidence=0.7)
    assert co.verdict == "READ"

    # 9. Skeleton report
    run = run_daily_skeleton()
    assert run.status == "partial"

    typer.echo("smoke: ok")


@_ingest_app.command("arxiv")
def ingest_arxiv(
    all_categories: bool = typer.Option(
        False,
        "--all",
        help="Force re-fetch all categories, ignoring cursors",
    ),
    max_results: int = typer.Option(
        200,
        "--max",
        help="Max results per category",
    ),
) -> None:
    """Fetch papers from arXiv and store locally."""
    ensure_runtime_dirs()
    store = PaperStore(DATA_DIR / "indexes")
    client = ArxivClient(store)
    try:
        results = asyncio.run(
            client.ingest_all_categories(
                max_results=max_results,
                force_all=all_categories,
            )
        )
        total_new = sum(v[0] for v in results.values())
        total_fetched = sum(v[1] for v in results.values())
        typer.echo(f"arXiv ingest complete: {total_new} new / {total_fetched} fetched")
        for cat, (n, t) in sorted(results.items()):
            if t > 0:
                typer.echo(f"  {cat}: {n} new / {t} fetched")
    finally:
        asyncio.run(client.close())


@_ingest_app.command("status")
def ingest_status() -> None:
    """Show paper store statistics."""
    ensure_runtime_dirs()
    store = PaperStore(DATA_DIR / "indexes")
    total = store.count_papers()
    typer.echo(f"Papers in store: {total}")
    by_status = {}
    for s in ("metadata_only", "NORMALIZED", "SCREENED", "EVIDENCE_READY"):
        c = store.count_papers(s)
        if c:
            by_status[s] = c
    if by_status:
        typer.echo("By status:")
        for s, c in by_status.items():
            typer.echo(f"  {s}: {c}")
    cursors = store.list_cursors()
    if cursors:
        typer.echo("Source cursors:")
        for c in cursors:
            typer.echo(f"  {c['source']}: {c['cursor_value']} (fetched {c['fetched_at']})")
    else:
        typer.echo("Source cursors: (none)")
    store.close()


@_ingest_app.command("normalize")
def ingest_normalize() -> None:
    """Normalize all unprocessed papers (metadata_only → NORMALIZED)."""
    ensure_runtime_dirs()
    store = PaperStore(DATA_DIR / "indexes")
    try:
        report = normalize_papers(store)
        typer.echo(
            f"Normalize: processed={report.processed} "
            f"normalized={report.normalized} "
            f"duplicates={report.duplicates} "
            f"errors={len(report.errors)}"
        )
        for err in report.errors[:5]:
            typer.secho(f"  error: {err}", fg=typer.colors.RED)
    finally:
        store.close()


@_ingest_app.command("screen")
def ingest_screen(
    echo_provider: bool = typer.Option(
        True,
        "--echo/--no-echo",
        help="Use EchoModelProvider (offline) vs real LLM",
    ),
) -> None:
    """Run two-stage screening on NORMALIZED papers."""
    ensure_runtime_dirs()
    if echo_provider:
        from arc.providers import EchoModelProvider

        provider = EchoModelProvider()
    else:
        from arc.config import load_models_config
        from arc.providers.openai_compatible import OpenAICompatibleProvider

        models = load_models_config()
        provider = OpenAICompatibleProvider(models.triage)

    report = asyncio.run(run_screening_step(provider))
    typer.echo(
        f"Screen: stage1_passed={report['stage1_passed']} "
        f"stage2_screened={report['stage2_screened']} "
        f"featured={report['featured']}"
    )
    for c in report.get("top_candidates", []):
        typer.echo(f"  [{c['composite']}] {c['title']}")
    for err in report.get("errors", [])[:5]:
        typer.secho(f"  error: {err}", fg=typer.colors.RED)
    if not report["stage1_passed"]:
        typer.secho("  (no candidates — run 'arc ingest arxiv' then 'arc ingest normalize' first)", fg=typer.colors.YELLOW)


_feedback_app = typer.Typer(help="Record and browse feedback on papers")
app.add_typer(_feedback_app, name="feedback")


@_feedback_app.command("add")
def feedback_add(
    paper_id: str = typer.Argument(..., help="Paper canonical_id or arXiv ID"),
    label: str = typer.Argument(..., help="Feedback label (see --help for list)"),
    comment: str = typer.Option("", "--comment", "-m", help="Optional comment"),
) -> None:
    """Record feedback on a paper.

    Labels:\n"""
    from arc.schemas import FeedbackLabel

    valid = [f"  {l.value}" for l in FeedbackLabel]
    typer.echo("Available labels:\n" + "\n".join(valid))
    try:
        entry = _write_feedback(paper_id, label, comment=comment)
        typer.echo(f"Feedback recorded: {entry.feedback_id}")
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@_feedback_app.command("list")
def feedback_list(
    limit: int = typer.Option(10, "--limit", "-n", help="Max entries"),
) -> None:
    """Show recent feedback entries."""
    entries = _list_feedback(limit=limit)
    if not entries:
        typer.echo("No feedback entries yet.")
        return
    for e in entries:
        ts = e.created_at.strftime("%Y-%m-%d %H:%M")
        typer.echo(f"[{ts}] {e.label.value:12s}  {e.paper_id}")
        if e.comment:
            typer.echo(f"          comment: {e.comment}")


# ---------------------------------------------------------------------------
# arc evidence
# ---------------------------------------------------------------------------

_evidence_app = typer.Typer(help="Build and inspect evidence packs")
app.add_typer(_evidence_app, name="evidence")


@_evidence_app.command("build")
def evidence_build(
    paper_id: str = typer.Argument(..., help="Paper canonical_id"),
    echo_provider: bool = typer.Option(
        True, "--echo/--no-echo", help="Use EchoModelProvider (offline)",
    ),
) -> None:
    """Extract evidence from a paper's abstract via LLM."""
    ensure_runtime_dirs()
    store = PaperStore(DATA_DIR / "indexes")
    paper = store.get_paper(paper_id)
    if not paper:
        typer.secho(f"Paper not found: {paper_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    if echo_provider:
        from arc.providers import EchoModelProvider
        provider = EchoModelProvider()
    else:
        models = load_models_config()
        from arc.providers.openai_compatible import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(models.structured_analysis)
    ev_list = asyncio.run(build_evidence_pack(store, paper, provider))
    typer.echo(f"Evidence pack built: {len(ev_list)} items for {paper_id}")
    for ev in ev_list:
        typer.echo(f"  {ev.id} [{ev.evidence_type.value}] {ev.content[:80]}")
    store.close()


# ---------------------------------------------------------------------------
# arc claim
# ---------------------------------------------------------------------------

_claim_app = typer.Typer(help="Manage the Claim Ledger")
app.add_typer(_claim_app, name="claim")


@_claim_app.command("add")
def claim_add(
    paper_id: str = typer.Argument(..., help="Paper canonical_id"),
    text: str = typer.Argument(..., help="Claim text"),
    type: str = typer.Option("inference", "--type", "-t",
        help="Claim type: fact|author_claim|inference|hypothesis|recommendation"),
    generated_by: str = typer.Option("cli", "--by", help="Generator role"),
) -> None:
    """Add a claim to the ledger (append-only)."""
    claim = _write_claim(paper_id, text, type, generated_by=generated_by)
    typer.echo(f"Claim recorded: {claim.claim_id}")


@_claim_app.command("list")
def claim_list(
    paper_id: str | None = typer.Option(None, "--paper", "-p", help="Filter by paper"),
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """List claims in the ledger."""
    claims = _list_claims(paper_id=paper_id, limit=limit)
    if not claims:
        typer.echo("No claims found.")
        return
    for c in claims:
        approved = "✓" if c.approved_by else "○"
        typer.echo(f"{approved} {c.claim_id} [{c.type.value:16s}] {c.text[:80]}")


@_claim_app.command("approve")
def claim_approve(
    claim_id: str = typer.Argument(..., help="Claim ID (CLM-...)"),
) -> None:
    """Approve a claim as Chair (sets approved_by)."""
    result = _approve_claim(claim_id)
    if result:
        typer.echo(f"Claim {claim_id} approved by {result.approved_by}")
    else:
        typer.secho(f"Claim not found or already approved: {claim_id}", fg=typer.colors.RED)


# ---------------------------------------------------------------------------
# arc idea
# ---------------------------------------------------------------------------

_idea_app = typer.Typer(help="Manage Idea lifecycle")
app.add_typer(_idea_app, name="idea")


@_idea_app.command("add")
def idea_add(
    title: str = typer.Argument(..., help="Idea title"),
    claim: str = typer.Option("", "--claim", "-c", help="Core claim"),
    stage: str = typer.Option("signal", "--stage", "-s",
        help="signal|hypothesis|candidate|validated_candidate|active_project"),
) -> None:
    """Add a new idea to the ledger."""
    idea = _write_idea(title=title, claim=claim, stage=stage)
    typer.echo(f"Idea created: {idea.idea_id} [{idea.stage.value}]")


@_idea_app.command("list")
def idea_list(
    stage: str | None = typer.Option(None, "--stage", "-s", help="Filter by stage"),
    limit: int = typer.Option(20, "--limit", "-n"),
) -> None:
    """List ideas."""
    ideas = _list_ideas(stage=stage, limit=limit)
    if not ideas:
        typer.echo("No ideas found.")
        return
    for i in ideas:
        typer.echo(f"{i.idea_id} [{i.stage.value:20s}] {i.title[:80]}")


@_idea_app.command("transition")
def idea_transition(
    idea_id: str = typer.Argument(..., help="Idea ID (IDEA-...)"),
    stage: str = typer.Argument(...,
        help="Target stage: signal|hypothesis|candidate|validated_candidate|active_project|rejected"),
) -> None:
    """Transition an idea to a new stage."""
    try:
        result = _transition_idea(idea_id, stage)
        if result:
            typer.echo(f"Idea {idea_id} transitioned to {result.stage.value}")
        else:
            typer.secho(f"Idea not found: {idea_id}", fg=typer.colors.RED)
    except ValueError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# arc weekly (enhanced with --pptx)
# ---------------------------------------------------------------------------


@app.command("weekly")
def weekly(
    week: str | None = typer.Option(None, "--week", help="YYYY-Www (default: current)"),
    pptx: bool = typer.Option(False, "--pptx", help="Generate PPTX slides"),
) -> None:
    """Generate weekly report (Markdown + optional PPTX)."""
    ensure_runtime_dirs()
    from datetime import date as dt_date

    week_str = week or dt_date.today().strftime("%Y-W%W")
    from arc.reporting import write_weekly_report

    profile = load_researcher_profile()
    projects = list_projects()
    context = {
        "date": week_str,
        "mode": "weekly_skeleton",
        "brand": "ARC",
        "subtitle": "Aki Research Council",
        "profile_name": profile.get("name", "researcher"),
        "projects": projects,
        "headlines": [],
        "featured_papers": [],
        "council_outputs": {},
        "decisions": [],
        "actions": ["周报管线将在 P3 完整实现后填充数据。"],
        "partial": True,
    }
    md_path = write_weekly_report(week_str, context)
    typer.echo(f"Wrote weekly report: {md_path}")

    if pptx:
        try:
            from arc.reporting.pptx import write_weekly_pptx

            pptx_path = write_weekly_pptx(week_str, context)
            typer.echo(f"Wrote weekly slides: {pptx_path}")
        except Exception as exc:
            typer.secho(f"PPTX generation failed: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# arc council
# ---------------------------------------------------------------------------

_council_app = typer.Typer(help="Run virtual council on papers")
app.add_typer(_council_app, name="council")


@_council_app.command("review")
def council_review(
    paper_id: str = typer.Argument(..., help="Paper canonical_id"),
    echo_provider: bool = typer.Option(
        True, "--echo/--no-echo", help="Use EchoModelProvider (offline)",
    ),
) -> None:
    """Run full council: Evidence → Skeptic → Historian → Liaison → Chair."""
    ensure_runtime_dirs()
    store = PaperStore(DATA_DIR / "indexes")
    paper = store.get_paper(paper_id)
    if not paper:
        typer.secho(f"Paper not found: {paper_id}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    if echo_provider:
        from arc.providers import EchoModelProvider
        provider = EchoModelProvider()
    else:
        models = load_models_config()
        from arc.providers.openai_compatible import OpenAICompatibleProvider
        provider = OpenAICompatibleProvider(models.deep_review)

    from arc.council import (
        run_chair,
        run_full_council,
        run_historian,
        run_liaison,
        run_skeptic,
    )

    async def _run() -> dict:
        # 1. Evidence
        ev_list = await build_evidence_pack(store, paper, provider)
        # 2. Skeptic
        skeptic = await run_skeptic(store, paper, provider)
        # 3. Historian
        historian = await run_historian(store, paper, provider)
        # 4. Liaison
        liaison = await run_liaison(paper, provider)
        # 5. Chair
        chair = await run_full_council(paper, provider, skeptic, historian, liaison)
        return {
            "evidence_count": len(ev_list),
            "skeptic_verdict": skeptic.verdict,
            "skeptic_attack_points": len(skeptic.attack_points),
            "historian_novelty": historian.novelty_label[:40],
            "liaison_projects": liaison.relevant_projects,
            "chair_verdict": chair.verdict,
            "chair_confidence": chair.confidence,
            "chair_actions": chair.actions,
        }

    result = asyncio.run(_run())
    typer.echo(f"Council review for {paper_id}:")
    typer.echo(f"  Evidence: {result['evidence_count']} items")
    typer.echo(f"  Skeptic: {result['skeptic_verdict']} ({result['skeptic_attack_points']} attack points)")
    typer.echo(f"  Historian: {result['historian_novelty']}")
    typer.echo(f"  Liaison: projects={result['liaison_projects']}")
    typer.echo(f"  Chair: {result['chair_verdict']} (conf={result['chair_confidence']})")
    for a in result['chair_actions']:
        typer.echo(f"    action: {a}")
    store.close()


def main() -> None:
    """Console script entry (setuptools/uv)."""
    app()


if __name__ == "__main__":
    main()
