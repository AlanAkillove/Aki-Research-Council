"""Historian role — prior work retrieval and novelty assessment (Tech Spec §8.1 Stage B)."""

from __future__ import annotations

import logging

from arc.council.schemas import HistorianOutput
from arc.ingestion.store import PaperStore
from arc.normalization import title_fingerprint
from arc.providers import ModelProvider
from arc.schemas import Paper

logger = logging.getLogger(__name__)


async def run_historian(
    store: PaperStore,
    paper: Paper,
    provider: ModelProvider,
) -> HistorianOutput:
    """Assess prior work: fingerprint search + LLM novelty analysis.

    First searches the local store for similar papers (title fingerprint),
    then uses the LLM to assess novelty against the closest matches.
    """
    fp = title_fingerprint(paper.title)
    candidates = store.get_papers(status=None, limit=200)

    # Find papers with overlapping title tokens
    fp_tokens = set(fp.split())
    scored = []
    for p in candidates:
        if p.canonical_id == paper.canonical_id:
            continue
        p_fp = title_fingerprint(p.title)
        p_tokens = set(p_fp.split())
        overlap = len(fp_tokens & p_tokens)
        if overlap >= 2:  # at least 2 significant tokens match
            scored.append((overlap, p))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_prior = [
        {
            "title": p.title[:100],
            "canonical_id": p.canonical_id,
            "token_overlap": score,
        }
        for score, p in scored[:5]
    ]

    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "prior_works": top_prior or [{"title": "(none found in local store)"}],
    }
    logger.info("Historian analyzing %s (found %d prior candidates)", paper.canonical_id, len(top_prior))
    return await provider.generate("historian_analysis", HistorianOutput, context)
