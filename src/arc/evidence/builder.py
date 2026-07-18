"""Evidence Pack Builder — LLM extraction from paper abstracts.

Tech Spec §6: Evidence Pack structure with typed evidence items.
Each evidence item gets an EV-{uuid} ID and is stored in PaperStore.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from pydantic import BaseModel, Field

from arc.ingestion.store import PaperStore
from arc.providers import ModelProvider
from arc.schemas import (
    Evidence,
    EvidenceType,
    Paper,
    PipelineStatus,
    SourceTier,
)

logger = logging.getLogger(__name__)


class _EvidenceItem(BaseModel):
    content: str
    evidence_type: str
    confidence: float = Field(ge=0.0, le=1.0)


class _EvidenceResponse(BaseModel):
    evidence: list[_EvidenceItem]


EVIDENCE_SCHEMA_PROMPT = """You are extracting structured evidence from a research paper abstract.
Return a JSON object with an "evidence" array. Each item must have:
- content: string (exact claim or finding from the abstract)
- evidence_type: one of "theorem", "experiment", "ablation", "claim", "limitation", "other"
- confidence: float 0.0-1.0

Extract up to 5 distinct pieces of evidence. Include limitations if mentioned."""


async def build_evidence_pack(
    store: PaperStore,
    paper: Paper,
    provider: ModelProvider,
) -> list[Evidence]:
    """Use LLM to extract evidence items from a paper's abstract.

    Stores each item via ``store.upsert_evidence`` and transitions the
    paper's status to ``EVIDENCE_READY``.

    Returns the list of created ``Evidence`` objects.
    """
    logger.info("Building evidence pack for %s", paper.canonical_id)

    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "authors": paper.authors[:5],
    }

    raw = await provider.generate(
        task="extract_evidence",
        schema=_EvidenceResponse,
        context=context,
    )

    evidence_list: list[Evidence] = []
    for item in raw.evidence:
        ev = Evidence(
            id=f"EV-{uuid4().hex[:12]}",
            paper_id=paper.canonical_id,
            content=item.content,
            evidence_type=EvidenceType(item.evidence_type),
            source_tier=SourceTier.A,
            extraction_method="api",
            confidence=item.confidence,
        )
        store.upsert_evidence(ev)
        evidence_list.append(ev)

    # Update paper status
    paper.processing_status = PipelineStatus.EVIDENCE_READY.value
    store.upsert_paper(paper)

    logger.info(
        "Evidence pack for %s: %d items extracted",
        paper.canonical_id,
        len(evidence_list),
    )
    return evidence_list
