"""Ingestion adapters (stubs for P1)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass
class FetchCursor:
    source: str
    as_of: date


async def fetch_arxiv_stub(categories: list[str], as_of: date | None = None) -> list[dict]:
    """Placeholder — real arXiv client lands in Next P1."""
    _ = categories, as_of
    return []
