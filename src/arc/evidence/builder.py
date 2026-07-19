"""Evidence Pack Builder — currently abstract-level extraction only.

Honest labeling: source_tier=B, extraction_method=abstract_llm.
Fulltext/TeX is NOT implemented yet — do not claim P2 fulltext acceptance.
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


async def build_evidence_pack(
    store: PaperStore,
    paper: Paper,
    provider: ModelProvider,
) -> list[Evidence]:
    """Extract evidence-like items from title/abstract via LLM.

    Does **not** parse PDF/TeX. Empty extractions do not advance status.
    """
    logger.info("Building abstract evidence pack for %s", paper.canonical_id)

    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "authors": paper.authors[:5],
        "note": "Source is abstract only; do not invent page/section locations.",
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
            evidence_type=(
                EvidenceType(item.evidence_type)
                if item.evidence_type in EvidenceType._value2member_map_
                else EvidenceType.OTHER
            ),
            source_tier=SourceTier.B,
            extraction_method="abstract_llm",
            confidence=item.confidence,
            location={"source": "abstract"},
        )
        store.upsert_evidence(ev)
        evidence_list.append(ev)

    if evidence_list:
        paper.processing_status = PipelineStatus.EVIDENCE_READY.value
        store.upsert_paper(paper)
    else:
        logger.warning("No evidence extracted for %s; status unchanged", paper.canonical_id)

    logger.info(
        "Evidence pack for %s: %d abstract items",
        paper.canonical_id,
        len(evidence_list),
    )
    return evidence_list
