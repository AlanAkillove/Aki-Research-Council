"""Editorial layer: turn structured candidates into a DailyBrief.

Template shells stay fixed; this module writes the living core.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from arc.memory import list_projects, load_researcher_profile
from arc.providers import ModelProvider
from arc.ranking import ScreeningReport
from arc.reporting.brief import BriefAction, BriefFeatured, BriefHeadline, DailyBrief

logger = logging.getLogger(__name__)


def _load_open_questions() -> list[dict[str, Any]]:
    from pathlib import Path

    import yaml

    from arc.paths import RESEARCH_STATE_DIR

    path = RESEARCH_STATE_DIR / "questions.yaml"
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return data if isinstance(data, list) else []


def candidates_packet_from_screening(report: ScreeningReport) -> list[dict[str, Any]]:
    """Serialize scored papers for the editor prompt."""
    packet: list[dict[str, Any]] = []
    for sp in report.candidates[:5]:
        p = sp.paper
        packet.append(
            {
                "paper_id": p.canonical_id,
                "title": p.title,
                "abstract": p.abstract[:600],
                "categories": p.categories[:6],
                "composite": round(sp.composite, 3),
                "recommended_action": sp.scores.recommended_action,
                "scores": sp.scores.model_dump(),
                "source_url": p.source_url
                or (f"https://arxiv.org/abs/{p.arxiv_id}" if p.arxiv_id else ""),
            }
        )
    return packet


def demo_candidates_packet() -> list[dict[str, Any]]:
    """Offline sample papers so we can taste the editorial voice without ingest."""
    return [
        {
            "paper_id": "arxiv:2607.04201",
            "title": "Utility-Aware Self-Challenge Routing for Vision Models",
            "abstract": (
                "We train a lightweight router that predicts the net utility of "
                "running a counterevidence pass, rather than predicting misclassification "
                "probability alone. On three backbones, routing by predicted net gain "
                "improves correction of hard errors while reducing harm to already-correct "
                "high-confidence samples."
            ),
            "categories": ["cs.CV", "cs.LG"],
            "composite": 0.78,
            "recommended_action": "read",
            "scores": {
                "project_relevance": 0.9,
                "method_transferability": 0.7,
                "novelty_signal": 0.6,
                "feasibility": 0.85,
                "evidence_quality": 0.65,
                "redundancy": 0.2,
            },
            "source_url": "https://arxiv.org/abs/2607.04201",
        },
        {
            "paper_id": "arxiv:2607.03312",
            "title": "Log-Concave Sequences via Combinatorial Injections, Revisited",
            "abstract": (
                "We unify several ad-hoc partition arguments for flat-count sequences "
                "into a single injection schema, covering a larger parameter range. "
                "One remaining corner case still relies on a computer-assisted check "
                "for n ≤ 12."
            ),
            "categories": ["math.CO"],
            "composite": 0.71,
            "recommended_action": "read",
            "scores": {
                "project_relevance": 0.88,
                "method_transferability": 0.75,
                "novelty_signal": 0.55,
                "feasibility": 0.9,
                "evidence_quality": 0.7,
                "redundancy": 0.25,
            },
            "source_url": "https://arxiv.org/abs/2607.03312",
        },
        {
            "paper_id": "arxiv:2607.05108",
            "title": "Scaling Test-Time Compute for Contest Math with Verifiable Rewards",
            "abstract": (
                "Larger search budgets with process rewards lift contest-bench scores. "
                "Gains shrink on open research problems without a checker. Code released."
            ),
            "categories": ["cs.AI", "cs.LG"],
            "composite": 0.52,
            "recommended_action": "watch",
            "scores": {
                "project_relevance": 0.55,
                "method_transferability": 0.4,
                "novelty_signal": 0.35,
                "feasibility": 0.5,
                "evidence_quality": 0.6,
                "redundancy": 0.45,
            },
            "source_url": "https://arxiv.org/abs/2607.05108",
        },
    ]


async def write_daily_brief(
    provider: ModelProvider,
    *,
    day: date,
    candidates: list[dict[str, Any]],
    ingest_note: str = "",
) -> DailyBrief:
    """Ask the editor model for a constrained DailyBrief."""
    profile: dict[str, Any] = {}
    try:
        profile = load_researcher_profile()
    except FileNotFoundError:
        pass

    context = {
        "date": day.isoformat(),
        "researcher": profile.get("name", "researcher"),
        "avoid": profile.get("avoid", []),
        "projects": list_projects(),
        "open_questions": _load_open_questions(),
        "candidates": candidates,
        "ingest_note": ingest_note,
        "rules": [
            "Write in Chinese (简体).",
            "Shell structure is fixed; you write judgment, not hype.",
            "Headlines ≤3; actions ≤3 and must be executable.",
            "Every featured item needs paper_id; link to a question_id when possible.",
            "If nothing changes research judgments, set quiet_day=true and omit filler.",
            "Never claim 首创/全新; use relative novelty only.",
            "Do not paste abstracts as why_it_matters.",
            "state_changes may be null to omit the section.",
        ],
    }
    brief = await provider.generate("write_daily_brief", DailyBrief, context)
    # Hard clip limits in case the model ignores max_length
    brief.headlines = brief.headlines[:3]
    brief.featured = brief.featured[:4]
    brief.actions = brief.actions[:3]
    return brief


def brief_to_template_context(
    brief: DailyBrief,
    *,
    day: date,
    partial: bool = False,
) -> dict[str, Any]:
    """Map DailyBrief → Jinja context (optional sections via None/empty)."""
    profile_name = "researcher"
    try:
        profile_name = load_researcher_profile().get("name", profile_name)
    except FileNotFoundError:
        pass

    return {
        "date": day.isoformat(),
        "mode": "daily_editorial",
        "brand": "ARC",
        "subtitle": "Aki Research Council",
        "profile_name": profile_name,
        "projects": list_projects(),
        "partial": partial,
        "reading_minutes_hint": brief.reading_minutes_hint,
        "lede": brief.lede,
        "quiet_day": brief.quiet_day,
        "headlines": [h.model_dump() for h in brief.headlines],
        "state_changes": brief.state_changes,
        "featured": [f.model_dump() for f in brief.featured],
        "radar": brief.radar,
        "idea_notes": brief.idea_notes,
        "actions": [a.model_dump() for a in brief.actions],
        "show_headlines": bool(brief.headlines) and not (
            brief.quiet_day and not brief.headlines
        ),
        "show_state": brief.state_changes is not None and bool(brief.state_changes.strip()),
        "show_featured": bool(brief.featured),
        "show_radar": bool(brief.radar),
        "show_ideas": bool(brief.idea_notes),
        "show_actions": bool(brief.actions),
    }


def fallback_brief_from_packet(
    candidates: list[dict[str, Any]],
    *,
    quiet: bool = False,
) -> DailyBrief:
    """Deterministic editorial sample used by Echo / offline demo."""
    questions = _load_open_questions()
    q_cv = next((q for q in questions if q.get("question_id") == "Q-CV-014"), None)
    q_mat = next((q for q in questions if q.get("question_id") == "Q-MAT-001"), None)
    q_aim = next((q for q in questions if q.get("question_id") == "Q-AIM-001"), None)

    if quiet or not candidates:
        return DailyBrief(
            lede="今天没有足以改写现有研究判断的新证据；保持观察即可，不必扩散注意力。",
            quiet_day=True,
            headlines=[],
            state_changes=None,
            featured=[],
            radar=[],
            idea_notes=[],
            actions=[
                BriefAction(text="把时间留给当前拟阵证明的统一注入草稿，而不是新开方向。")
            ],
            reading_minutes_hint=5,
        )

    # Heuristic mapping for demo voice
    headlines: list[BriefHeadline] = []
    featured: list[BriefFeatured] = []
    actions: list[BriefAction] = []
    radar: list[str] = []

    for c in candidates:
        pid = c["paper_id"]
        title = c["title"]
        action = c.get("recommended_action", "watch")
        cats = c.get("categories") or []

        if "cs.CV" in cats and q_cv:
            headlines.append(
                BriefHeadline(
                    title="视觉自质疑：路由目标从「会不会错」转向「净收益」",
                    why_it_matters=(
                        "这直接碰到 Q-CV-014：用预测净收益而不是置信度本身决定是否反证，"
                        "和你已知的「naive disconfirm 伤害正确样本」失败经验同向。"
                    ),
                    paper_id=pid,
                    question_id="Q-CV-014",
                    confidence="high",
                    suggested_move="精读路由目标与消融，确认增益是否只来自额外算力。",
                )
            )
            featured.append(
                BriefFeatured(
                    paper_id=pid,
                    paper_title=title,
                    one_line_judgment="机制对齐你的开放问题，值得精读而非跟风实现。",
                    actual_delta="把 challenge 决策建成 utility 预测，而不是误差概率阈值。",
                    link_to_project="structured_and_reliable_vision / Q-CV-014",
                    verdict="READ",
                    source_url=c.get("source_url", ""),
                )
            )
            actions.append(
                BriefAction(
                    text="精读 arXiv:2607.04201 中 routing objective 与「伤害正确样本」相关消融表。",
                    paper_id=pid,
                )
            )
        elif "math.CO" in cats and q_mat:
            headlines.append(
                BriefHeadline(
                    title="拟阵/对数凹：注入图式证明被再次统一，但仍留计算角点",
                    why_it_matters=(
                        "若其注入图式覆盖你卡住的参数段，可能缩短统一证明；"
                        "若角点仍靠 n≤12 机验，则不能当作最终闭环。"
                    ),
                    paper_id=pid,
                    question_id="Q-MAT-001",
                    confidence="medium",
                    suggested_move="对照主定理假设，标出与你手稿重叠的注入步骤。",
                )
            )
            featured.append(
                BriefFeatured(
                    paper_id=pid,
                    paper_title=title,
                    one_line_judgment="证明技术可迁移，但死亡条件（纯有限验证）仍要警惕。",
                    actual_delta="把多处 ad-hoc partition 收成一种注入图式，扩大参数覆盖。",
                    link_to_project="combinatorics_and_matroids / Q-MAT-001",
                    verdict="READ",
                    source_url=c.get("source_url", ""),
                )
            )
            actions.append(
                BriefAction(
                    text="把该文注入图式与手稿未闭合情形列成对照表（一页纸即可）。",
                    paper_id=pid,
                )
            )
        elif action == "watch" or "cs.AI" in cats:
            radar.append(
                f"{pid}: 竞赛/可验证奖励路线升温，但对研究级开放题的迁移仍弱"
                + (f"（关 Q-AIM-001）" if q_aim else "")
            )
            featured.append(
                BriefFeatured(
                    paper_id=pid,
                    paper_title=title,
                    one_line_judgment="作雷达即可：算力换分，不是你的主战场。",
                    actual_delta="测试时计算扩展带来榜点；无 checker 时增益收缩。",
                    link_to_project="radar only（ai_for_math 外围）",
                    verdict="WATCH",
                    source_url=c.get("source_url", ""),
                )
            )

    if not headlines and featured:
        # generic fallback headline from top featured
        top = featured[0]
        headlines.append(
            BriefHeadline(
                title=top.one_line_judgment[:40],
                why_it_matters=top.actual_delta,
                paper_id=top.paper_id,
                confidence="medium",
                suggested_move=f"按决议 {top.verdict} 处理该文。",
            )
        )

    if len(actions) < 3 and featured:
        actions.append(
            BriefAction(
                text="今日不新开 Idea；先把上述精读笔记写回对应 open question。"
            )
        )

    return DailyBrief(
        lede=(
            "两条线索值得占用注意力：视觉自质疑的目标函数，以及拟阵对数凹证明的注入统一；"
            "AI-for-math 的测试时扩展只进雷达，避免被榜点叙事带走。"
        ),
        quiet_day=False,
        headlines=headlines[:3],
        state_changes=(
            "Q-CV-014 与 Q-MAT-001 各获得一条可对齐的外部证据线索；"
            "尚无足以改写死亡条件或核心假设的结果。项目状态建议维持 exploring / proving。"
        ),
        featured=featured[:4],
        radar=radar,
        idea_notes=[],
        actions=actions[:3],
        reading_minutes_hint=12,
    )
