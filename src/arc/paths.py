"""Shared paths and environment loading."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# repo root: src/arc/paths.py → parents[2]
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
RESEARCH_STATE_DIR = REPO_ROOT / "research_state"
DATA_DIR = REPO_ROOT / "data"
REPORTS_DIR = REPO_ROOT / "reports"
TEMPLATES_DIR = REPO_ROOT / "templates"
PROMPTS_DIR = REPO_ROOT / "prompts"
DOT_ENV = REPO_ROOT / ".env"


def load_env() -> None:
    """Load `.env` from repo root if present (never commit secrets)."""
    load_dotenv(REPO_ROOT / ".env", override=False)


def ensure_runtime_dirs() -> None:
    """Create writable runtime directories used by the pipeline."""
    for path in (
        DATA_DIR / "raw",
        DATA_DIR / "normalized",
        DATA_DIR / "evidence",
        DATA_DIR / "indexes",
        REPORTS_DIR / "daily",
        REPORTS_DIR / "weekly",
        REPORTS_DIR / "monthly",
        REPORTS_DIR / "topic",
        RESEARCH_STATE_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
