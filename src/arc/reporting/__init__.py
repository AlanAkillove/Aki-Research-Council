"""Report rendering (Markdown / HTML)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from arc.paths import REPORTS_DIR, TEMPLATES_DIR


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "htm", "xml")),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_daily_markdown(context: dict[str, Any]) -> str:
    return _env().get_template("daily/report.md.j2").render(**context)


def render_daily_html(context: dict[str, Any]) -> str:
    return _env().get_template("daily/report.html.j2").render(**context)


def write_daily_reports(date_str: str, context: dict[str, Any]) -> tuple[Path, Path]:
    out_dir = REPORTS_DIR / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f"{date_str}.md"
    html_path = out_dir / f"{date_str}.html"
    md_path.write_text(render_daily_markdown(context), encoding="utf-8")
    html_path.write_text(render_daily_html(context), encoding="utf-8")
    return md_path, html_path
