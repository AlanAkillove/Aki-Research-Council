"""OpenAI-compatible chat provider (optional network)."""

from __future__ import annotations

import json
import os
from typing import TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from arc.config import ModelRoleConfig
from arc.providers import ModelProvider

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleProvider(ModelProvider):
    def __init__(self, role: ModelRoleConfig, api_key: str | None = None) -> None:
        self.role = role
        key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ARC_API_KEY")
        if not key:
            raise ValueError("Missing OPENAI_API_KEY (or ARC_API_KEY)")
        base_url = role.base_url or os.getenv("OPENAI_BASE_URL")
        self.client = AsyncOpenAI(api_key=key, base_url=base_url)

    async def generate(self, task: str, schema: type[T], context: dict) -> T:
        system = (
            "You are a research assistant for ARC. "
            "Return ONLY valid JSON matching the requested schema. "
            "Never claim absolute novelty (no 首创/全新). "
            "Distinguish facts, author claims, and inferences."
        )
        user = json.dumps({"task": task, "context": context}, ensure_ascii=False)
        response = await self.client.chat.completions.create(
            model=self.role.model,
            temperature=self.role.temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        content = response.choices[0].message.content or "{}"
        return schema.model_validate_json(content)
