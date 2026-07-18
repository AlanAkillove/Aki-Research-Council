"""Chair role — final decision combining all council outputs (Tech Spec §8.1 Stage G)."""

from __future__ import annotations

import logging

from arc.council.schemas import ChairOutput, LiaisonOutput, SkepticOutput, HistorianOutput
from arc.memory import write_claim
from arc.providers import ModelProvider
from arc.schemas import Paper

logger = logging.getLogger(__name__)


async def run_chair(
    paper: Paper,
    skeptic_out: SkepticOutput,
    historian_out: HistorianOutput,
    liaison_out: LiaisonOutput,
    provider: ModelProvider,
) -> ChairOutput:
    """Combine all role outputs into a single Chair decision.

    The LLM evaluates the aggregated evidence and produces a
    ``ChairOutput`` with verdict, rationale, and ≤3 actions.
    """
    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "skeptic": skeptic_out.model_dump(),
        "historian": historian_out.model_dump(),
        "liaison": liaison_out.model_dump(),
    }
    logger.info("Chair deciding on %s", paper.canonical_id)
    return await provider.generate("chair_decision", ChairOutput, context)


async def run_full_council(
    paper: Paper,
    provider: ModelProvider,
    skeptic_out: SkepticOutput,
    historian_out: HistorianOutput,
    liaison_out: LiaisonOutput,
) -> ChairOutput:
    """Run the full Chair decision and persist claims.

    Records key outputs as claims in the ledger.
    """
    chair_out = await run_chair(paper, skeptic_out, historian_out, liaison_out, provider)

    # Record chair decision as a claim for traceability
    write_claim(
        paper_id=paper.canonical_id,
        text=f"Chair verdict: {chair_out.verdict}. " + "; ".join(chair_out.rationale[:2]),
        type="recommendation",
        generated_by="chair",
    )

    return chair_out
