"""LLM provider abstraction (openai-compatible; no LiteLLM hard dependency)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelProvider(ABC):
    @abstractmethod
    async def generate(self, task: str, schema: type[T], context: dict) -> T:
        """Generate a structured response validated against `schema`."""


class EchoModelProvider(ModelProvider):
    """Deterministic stub for offline smoke tests — does not call the network."""

    async def generate(self, task: str, schema: type[T], context: dict) -> T:
        name = schema.__name__
        if name == "ScreenScores":
            return schema.model_validate(  # type: ignore[return-value]
                {
                    "topic_relevance": 0.5,
                    "project_relevance": 0.5,
                    "method_transferability": 0.4,
                    "novelty_signal": 0.3,
                    "feasibility": 0.7,
                    "evidence_quality": 0.5,
                    "redundancy": 0.2,
                    "recommended_action": "watch",
                }
            )
        if name == "_EvidenceResponse":
            return schema.model_validate(  # type: ignore[return-value]
                {
                    "evidence": [
                        {
                            "content": "The paper claims a novel approach.",
                            "evidence_type": "claim",
                            "confidence": 0.7,
                        },
                        {
                            "content": "Experimental results show improvement.",
                            "evidence_type": "experiment",
                            "confidence": 0.8,
                        },
                    ]
                }
            )
        if name == "SkepticOutput":
            return schema.model_validate({"verdict": "sound", "attack_points": []})  # type: ignore[return-value]
        if name == "HistorianOutput":
            return schema.model_validate({  # type: ignore[return-value]
                "novelty_label": "未发现高度相似工作",
                "context_summary": "No closely related prior work found.",
            })
        if name == "LiaisonOutput":
            return schema.model_validate({  # type: ignore[return-value]
                "relevant_projects": ["ai_for_math"],
                "impact": "supports",
                "rationale": "The method applies to mathematical reasoning.",
            })
        if name == "ChairOutput":
            return schema.model_validate({  # type: ignore[return-value]
                "verdict": "WATCH",
                "confidence": 0.6,
                "rationale": ["Interesting but needs more evidence."],
                "actions": ["Monitor future versions."],
            })
        if name == "_SkepticScore":
            return schema.model_validate({"score": 0.7, "weakness": "Limited empirical validation"})  # type: ignore[return-value]
        if name == "_FeasibilityScore":
            return schema.model_validate({"score": 0.8, "notes": "Single GPU sufficient"})  # type: ignore[return-value]
        if name == "TournamentOutput":
            return schema.model_validate({  # type: ignore[return-value]
                "entries": [{"idea_id": "IDEA-echo", "title": "Echo Idea", "claim": "Test", "composite": 0.75}],
                "winner_id": "IDEA-echo",
            })
        raise NotImplementedError(f"EchoModelProvider has no fixture for {name} ({task})")
