"""YAML / settings loaders."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from arc.paths import CONFIG_DIR, load_env


class DailyLimits(BaseModel):
    initial_candidates: int = 200
    llm_screened: int = 30
    fulltext_analyzed: int = 5
    featured_papers: int = 3
    new_ideas: int = 1
    action_items: int = 3


class ExplorationMix(BaseModel):
    project_related: float = 0.70
    adjacent_methods: float = 0.20
    high_uncertainty: float = 0.10


class RankingConfig(BaseModel):
    daily_limits: DailyLimits = Field(default_factory=DailyLimits)
    exploration_mix: ExplorationMix = Field(default_factory=ExplorationMix)
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "R": 0.25,
            "L": 0.15,
            "E": 0.15,
            "F": 0.15,
            "N": 0.10,
            "T": 0.10,
            "P": 0.20,
        }
    )


class ModelRoleConfig(BaseModel):
    model: str
    base_url: str | None = None
    temperature: float = 0.2


class ModelsConfig(BaseModel):
    default_base_url: str | None = None
    embedding: ModelRoleConfig
    triage: ModelRoleConfig
    structured_analysis: ModelRoleConfig
    deep_review: ModelRoleConfig
    math_analysis: ModelRoleConfig | None = None


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}")
    return data


def load_ranking_config(path: Path | None = None) -> RankingConfig:
    load_env()
    cfg_path = path or (CONFIG_DIR / "ranking.yaml")
    return RankingConfig.model_validate(read_yaml(cfg_path))


def load_models_config(path: Path | None = None) -> ModelsConfig:
    load_env()
    cfg_path = path or (CONFIG_DIR / "models.yaml")
    return ModelsConfig.model_validate(read_yaml(cfg_path))


def load_sources_config(path: Path | None = None) -> dict[str, Any]:
    load_env()
    cfg_path = path or (CONFIG_DIR / "sources.yaml")
    return read_yaml(cfg_path)


def load_topics_config(path: Path | None = None) -> dict[str, Any]:
    """Load topic/channel configuration."""
    load_env()
    cfg_path = path or (CONFIG_DIR / "topics.yaml")
    return read_yaml(cfg_path)
