"""Typer CLI entrypoint: `arc`."""

from __future__ import annotations

from datetime import date
from typing import Optional

import typer

from arc import __version__
from arc.config import load_models_config, load_ranking_config, load_sources_config
from arc.memory import list_projects
from arc.paths import REPO_ROOT, ensure_runtime_dirs, load_env
from arc.pipeline import run_daily_skeleton

app = typer.Typer(
    name="arc",
    help="ARC — Aki Research Council",
    no_args_is_help=True,
)


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
        help="Skeleton mode until ingest is implemented",
    ),
) -> None:
    """Run daily brief pipeline (skeleton until ingest lands)."""
    run_day = date.fromisoformat(day) if day else date.today()
    if not skeleton:
        typer.secho("Full daily pipeline not implemented yet; use --skeleton", fg=typer.colors.RED)
        raise typer.Exit(code=2)
    run = run_daily_skeleton(run_day)
    typer.echo(f"run_id={run.run_id} status={run.status} mode={run.mode}")
    typer.echo(f"wrote reports/daily/{run_day.isoformat()}.md|.html")


@app.command("smoke")
def smoke() -> None:
    """Offline smoke: config + normalize + ranking + skeleton report."""
    from arc.config import load_ranking_config
    from arc.normalization import pick_canonical_id, title_fingerprint
    from arc.providers import EchoModelProvider
    from arc.ranking import composite_score
    from arc.schemas import ScreenScores

    ensure_runtime_dirs()
    load_sources_config()
    ranking = load_ranking_config()
    assert title_fingerprint("Hello, World!") == "hello world"
    cid = pick_canonical_id(arxiv_id="2607.12345")
    assert cid == "arxiv:2607.12345"

    import asyncio

    scores = asyncio.run(EchoModelProvider().generate("screen", ScreenScores, {}))
    _ = composite_score(scores, ranking)
    run = run_daily_skeleton(date.today())
    assert run.status == "partial"
    typer.echo("smoke: ok")


def main() -> None:
    """Console script entry (setuptools/uv)."""
    app()


if __name__ == "__main__":
    main()
