"""Liaison role — maps paper to research projects/questions (Tech Spec §8.1 Stage E)."""

from __future__ import annotations

import logging

import yaml

from arc.council.schemas import LiaisonOutput
from arc.memory import load_researcher_profile
from arc.paths import RESEARCH_STATE_DIR
from arc.providers import ModelProvider
from arc.schemas import Paper

logger = logging.getLogger(__name__)


async def run_liaison(
    paper: Paper,
    provider: ModelProvider,
) -> LiaisonOutput:
    """Determine which projects/questions a paper impacts.

    Loads projects and open questions from ``research_state/``,
    then asks the LLM to map the paper to relevant items.
    """
    # Load projects
    projects_dir = RESEARCH_STATE_DIR / "projects"
    projects_info = {}
    if projects_dir.exists():
        for path in sorted(projects_dir.glob("*.yaml")):
            with path.open() as f:
                pdata = yaml.safe_load(f) or {}
                projects_info[pdata.get("project_id", path.stem)] = {
                    "title": pdata.get("title", ""),
                    "core_question": pdata.get("core_question", ""),
                }

    # Load open questions
    questions_path = RESEARCH_STATE_DIR / "questions.yaml"
    questions = []
    if questions_path.exists():
        with questions_path.open() as f:
            questions = yaml.safe_load(f) or []

    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "projects": projects_info,
        "open_questions": [
            {"id": q.get("question_id"), "text": q.get("question")}
            for q in questions[:10]
        ],
    }
    logger.info("Liaison mapping %s to research state", paper.canonical_id)
    return await provider.generate("liaison_mapping", LiaisonOutput, context)
