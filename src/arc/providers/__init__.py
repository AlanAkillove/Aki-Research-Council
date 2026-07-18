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
        if schema.__name__ == "ScreenScores":
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
        raise NotImplementedError(f"EchoModelProvider has no fixture for {schema.__name__} ({task})")
