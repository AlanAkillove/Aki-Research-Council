"""Skeptic role — fixed checklist critique (Tech Spec §8.1 Stage D)."""

from __future__ import annotations

import logging

from arc.council.schemas import SkepticOutput
from arc.ingestion.store import PaperStore
from arc.providers import ModelProvider
from arc.schemas import Paper

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a skeptical research reviewer. "
    "Given a paper's title, abstract, and extracted evidence, "
    "produce a critique. Identify: attack points, missing controls, "
    "overclaimed conclusions, and any evidence against the claims. "
    "If the paper appears sound with no major issues, you may say so. "
    "If evidence is insufficient to judge, output 'insufficient_evidence'. "
    "Never invent flaws for the sake of debate."
)


async def run_skeptic(
    store: PaperStore,
    paper: Paper,
    provider: ModelProvider,
) -> SkepticOutput:
    """Run Skeptic review on a paper using its abstract + evidence."""
    evidence_items = store.get_evidence_by_paper(paper.canonical_id)
    evidence_text = "\n".join(
        f"- [{e.evidence_type.value}] {e.content}" for e in evidence_items
    )
    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "evidence": evidence_text or "(no evidence extracted)",
    }
    logger.info("Skeptic reviewing %s", paper.canonical_id)
    return await provider.generate("skeptic_review", SkepticOutput, context)
