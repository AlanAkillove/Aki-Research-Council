"""Paper identity normalization, dedup, and pipeline orchestration.

Tech Spec §5: identity priority (DOI > arXiv > …), title fingerprint dedup,
version merge, and processing_status transitions.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from arc.ingestion.store import PaperStore
from arc.schemas import Paper, PipelineStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def title_fingerprint(title: str) -> str:
    """Normalise title to a canonical fingerprint for dedup.

    - NFKC normalise
    - lowercase
    - strip punctuation (keep word chars and spaces)
    - collapse whitespace
    """
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def pick_canonical_id(
    *,
    doi: str | None = None,
    arxiv_id: str | None = None,
    openreview_id: str | None = None,
    semantic_scholar_id: str | None = None,
    title: str | None = None,
) -> str:
    """Priority: DOI > arXiv > OpenReview > S2 > title fingerprint."""
    if doi:
        return f"doi:{doi.strip().lower()}"
    if arxiv_id:
        return f"arxiv:{arxiv_id.strip()}"
    if openreview_id:
        return f"openreview:{openreview_id.strip()}"
    if semantic_scholar_id:
        return f"s2:{semantic_scholar_id.strip()}"
    if title:
        return f"title:{title_fingerprint(title)}"
    raise ValueError("No identity fields available for canonical_id")


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


@dataclass
class DedupResult:
    is_duplicate: bool = False
    existing_canonical_id: str | None = None
    match_reason: str | None = None  # 'arxiv_id' | 'doi' | 'title_fingerprint'


def check_dedup(
    store: PaperStore,
    paper: Paper,
    fp_index: dict[str, set[str]] | None = None,
) -> DedupResult:
    """Check whether *paper* already exists in the store.

    Strategy order:
    1. arXiv ID exact match
    2. DOI exact match
    3. Title fingerprint match (using an optional pre-built index)
    """
    # 1. arXiv ID
    if paper.arxiv_id:
        existing = store.get_paper_by_arxiv(paper.arxiv_id)
        if existing and existing.canonical_id != paper.canonical_id:
            return DedupResult(
                is_duplicate=True,
                existing_canonical_id=existing.canonical_id,
                match_reason="arxiv_id",
            )

    # 2. DOI
    if paper.doi:
        existing = store.get_paper_by_doi(paper.doi)
        if existing and existing.canonical_id != paper.canonical_id:
            return DedupResult(
                is_duplicate=True,
                existing_canonical_id=existing.canonical_id,
                match_reason="doi",
            )

    # 3. Title fingerprint
    if fp_index is not None:
        fp = title_fingerprint(paper.title)
        matches = fp_index.get(fp)
        if matches:
            others = [cid for cid in matches if cid != paper.canonical_id]
            if others:
                return DedupResult(
                    is_duplicate=True,
                    existing_canonical_id=others[0],
                    match_reason="title_fingerprint",
                )

    return DedupResult()


# ---------------------------------------------------------------------------
# Full pipeline step
# ---------------------------------------------------------------------------


@dataclass
class NormalizationReport:
    processed: int = 0
    normalized: int = 0
    duplicates: int = 0
    version_updates: int = 0
    errors: list[str] = field(default_factory=list)


def _build_fp_index(
    store: PaperStore, status: str | None = None
) -> dict[str, set[str]]:
    """Build an in-memory title fingerprint index."""
    index: dict[str, set[str]] = {}
    papers = store.get_papers(status=status, limit=10000)
    for p in papers:
        fp = title_fingerprint(p.title)
        index.setdefault(fp, set()).add(p.canonical_id)
    return index


def run_normalization(
    store: PaperStore,
    batch_size: int = 200,
) -> NormalizationReport:
    """Normalise **all** papers whose ``processing_status`` is ``metadata_only``.

    Steps:
    - Build a title-fingerprint index from already-normalised papers.
    - For each raw paper check arXiv-ID / DOI / fingerprint dedup.
    - Transition status to ``NORMALIZED``.
    """
    papers = store.get_papers(status="metadata_only", limit=batch_size)
    report = NormalizationReport(processed=len(papers))

    if not papers:
        logger.info("Normalization: no papers to process")
        return report

    logger.info(
        "Normalization: processing %d papers (batch_size=%d)",
        len(papers),
        batch_size,
    )

    fp_index = _build_fp_index(store, status=PipelineStatus.NORMALIZED.value)
    logger.debug("Normalization: built fp_index with %d entries", len(fp_index))

    for paper in papers:
        try:
            dedup = check_dedup(store, paper, fp_index)
            if dedup.is_duplicate:
                logger.info(
                    "Duplicate %s (reason=%s, existing=%s)",
                    paper.canonical_id,
                    dedup.match_reason,
                    dedup.existing_canonical_id,
                )
                paper.processing_status = "DUPLICATE"
                store.upsert_paper(paper)
                report.duplicates += 1
                continue

            paper.processing_status = PipelineStatus.NORMALIZED.value
            store.upsert_paper(paper)

            fp_index.setdefault(
                title_fingerprint(paper.title), set()
            ).add(paper.canonical_id)
            report.normalized += 1

        except Exception as exc:
            msg = f"{paper.canonical_id}: {exc}"
            logger.warning(msg)
            report.errors.append(msg)

    logger.info(
        "Normalization done: processed=%d normalized=%d duplicates=%d errors=%d",
        report.processed,
        report.normalized,
        report.duplicates,
        len(report.errors),
    )
    return report
