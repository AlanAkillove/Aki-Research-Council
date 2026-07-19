"""Ranking / triage — two-stage screening (Tech Spec §7).

Stage 1 — Hard filter (no LLM):
    category overlap, topic keywords, negative keywords, date recency.

Stage 2 — Structured LLM ranking:
    multi-dim JSON scores → composite_score → top-N selection.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from arc.config import RankingConfig, load_sources_config, load_topics_config
from arc.ingestion.store import PaperStore
from arc.memory import load_researcher_profile
from arc.providers import ModelProvider
from arc.schemas import Paper, PipelineStatus, ScreenScores

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Composite score (Tech Spec §7.2 formula)
# ---------------------------------------------------------------------------


def composite_score(scores: ScreenScores, ranking: RankingConfig) -> float:
    """S = wR*R + wL*L + wE*E + wF*F + wN*N + wT*T - wP*P."""
    w = ranking.weights
    return (
        w.get("R", 0.25) * scores.project_relevance
        + w.get("L", 0.15) * scores.method_transferability
        + w.get("E", 0.15) * scores.evidence_quality
        + w.get("F", 0.15) * scores.feasibility
        + w.get("N", 0.10) * scores.novelty_signal
        + w.get("T", 0.10) * scores.topic_relevance
        - w.get("P", 0.20) * scores.redundancy
    )

# ---------------------------------------------------------------------------
# Stage 1 — Hard filter
# ---------------------------------------------------------------------------


@dataclass
class HardFilterConfig:
    """Rules applied without LLM."""

    max_age_days: int = 30
    topic_keywords: dict[str, list[str]] = field(default_factory=dict)
    negative_keywords: list[str] = field(default_factory=list)
    allowed_categories: set[str] = field(default_factory=set)
    enabled_channels: set[str] = field(default_factory=set)


def load_hard_filter_config() -> HardFilterConfig:
    """Build config from YAML configs + researcher profile."""
    cfg = HardFilterConfig()

    # Topic keywords per channel
    topics = load_topics_config()
    cfg.topic_keywords = topics.get("topic_keywords", {})

    # Enabled channels
    channels = topics.get("channels", [])
    cfg.enabled_channels = set(channels)

    # Allowed arxiv categories from sources config
    sources = load_sources_config()
    for group in sources.get("arxiv", {}).get("categories", {}).values():
        if isinstance(group, list):
            cfg.allowed_categories.update(group)

    # Negative keywords from researcher profile
    try:
        profile = load_researcher_profile()
        cfg.negative_keywords = profile.get("avoid", [])
    except FileNotFoundError:
        pass

    return cfg


def _tokenize(text: str) -> set[str]:
    """Lowercase, split on non-alpha, return set of tokens ≥3 chars."""
    tokens = re.findall(r"[a-z]{3,}", text.lower())
    return set(tokens)


def passes_hard_filter(
    paper: Paper,
    cfg: HardFilterConfig,
    today: date | None = None,
) -> tuple[bool, str]:
    """Check if *paper* passes the hard-filter gate.

    Returns ``(passed, reason)`` — reason is empty when passed.
    """
    today = today or date.today()
    paper_cats = set(paper.categories)

    # 1. Category overlap
    if paper_cats and cfg.allowed_categories:
        if not paper_cats & cfg.allowed_categories:
            return False, "category_not_in_allowed"

    # 2. Topic keyword match (at least one keyword in title or abstract)
    if cfg.topic_keywords:
        all_keywords = set()
        for kw_list in cfg.topic_keywords.values():
            all_keywords.update(k.lower() for k in kw_list)
        text = _tokenize(paper.title + " " + paper.abstract)
        if not all_keywords & text:
            return False, "no_topic_keyword_match"

    # 3. Negative keyword exclusion
    if cfg.negative_keywords:
        combined = (paper.title + " " + paper.abstract).lower()
        for neg in cfg.negative_keywords:
            if neg.lower() in combined:
                return False, f"negative_keyword:{neg}"

    # 4. Date recency
    if cfg.max_age_days:
        paper_date = _paper_date(paper)
        if paper_date and (today - paper_date).days > cfg.max_age_days:
            return False, f"older_than_{cfg.max_age_days}_days"

    return True, ""


def _paper_date(paper: Paper) -> date | None:
    """Best-effort publication date from ``published_at`` or arXiv YYMM id."""
    if paper.published_at:
        raw = paper.published_at.strip()
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
        except ValueError:
            if len(raw) >= 10 and raw[4] == "-" and raw[7] == "-":
                try:
                    return date.fromisoformat(raw[:10])
                except ValueError:
                    pass

    # arXiv ids look like YYMM.NNNNN — NOT a four-digit year.
    if paper.arxiv_id and len(paper.arxiv_id) >= 4 and paper.arxiv_id[:4].isdigit():
        yymm = paper.arxiv_id[:4]
        yy, mm = int(yymm[:2]), int(yymm[2:4])
        if 1 <= mm <= 12:
            year = 2000 + yy if yy < 70 else 1900 + yy
            try:
                return date(year, mm, 1)
            except ValueError:
                return None
    return None


# ---------------------------------------------------------------------------
# Stage 2 — LLM screening
# ---------------------------------------------------------------------------


@dataclass
class ScoredPaper:
    """A paper that passed Stage 1 and received Stage 2 scores."""

    paper: Paper
    scores: ScreenScores
    composite: float
    passed: bool
    rejection_reason: str = ""


SCREENING_SYSTEM_PROMPT = (
    "You are a research triage assistant. "
    "Evaluate the paper below for a researcher working on:\n"
    "- AI for mathematical reasoning\n"
    "- Structured and reliable vision (calibration, self-critique)\n"
    "- Combinatorics and matroids\n\n"
    "Return ONLY valid JSON matching the requested schema. "
    "Never claim absolute novelty (no 首创/全新). "
    "Distinguish facts, author claims, and inferences."
)


async def screen_paper(
    provider: ModelProvider,
    paper: Paper,
) -> ScreenScores:
    """Run LLM screen on a single paper — async."""
    context = {
        "title": paper.title,
        "abstract": paper.abstract,
        "categories": paper.categories,
        "authors": paper.authors[:5],
    }
    return await provider.generate(
        task="screen_paper",
        schema=ScreenScores,
        context=context,
    )


# ---------------------------------------------------------------------------
# Full two-stage screening pipeline
# ---------------------------------------------------------------------------


@dataclass
class ScreeningReport:
    stage1_input: int = 0
    stage1_passed: int = 0
    stage2_screened: int = 0
    featured: int = 0
    candidates: list[ScoredPaper] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_stage1(
    store: PaperStore,
    cfg: HardFilterConfig | None = None,
) -> list[Paper]:
    """Run hard-filter on all NORMALIZED papers.

    Returns papers that pass.
    """
    if cfg is None:
        cfg = load_hard_filter_config()

    papers = store.get_papers(status=PipelineStatus.NORMALIZED.value, limit=300)
    passed: list[Paper] = []

    for paper in papers:
        ok, reason = passes_hard_filter(paper, cfg)
        if ok:
            passed.append(paper)
        else:
            logger.debug("Hard-filter rejected %s: %s", paper.canonical_id, reason)

    logger.info(
        "Stage 1 hard filter: %d input → %d passed",
        len(papers),
        len(passed),
    )
    return passed


async def run_stage2(
    candidates: list[Paper],
    provider: ModelProvider,
    ranking: RankingConfig,
    max_screen: int = 30,
    store: PaperStore | None = None,
) -> ScreeningReport:
    """LLM screen candidates, compute scores, return ranking.

    Respects ``ranking.daily_limits`` to bound LLM calls.
    Papers that are screened (pass or ignore) are marked ``SCREENED``.
    """
    report = ScreeningReport(stage1_passed=len(candidates))
    max_s = min(max_screen, ranking.daily_limits.llm_screened)
    screen_batch = candidates[:max_s]
    report.stage2_screened = len(screen_batch)

    scored: list[ScoredPaper] = []
    for paper in screen_batch:
        try:
            scores = await screen_paper(provider, paper)
            comp = composite_score(scores, ranking)
            action = scores.recommended_action
            passed = action != "ignore"

            scored.append(
                ScoredPaper(
                    paper=paper,
                    scores=scores,
                    composite=comp,
                    passed=passed,
                    rejection_reason="" if passed else "llm_recommend_ignore",
                )
            )
            if store is not None:
                paper.processing_status = PipelineStatus.SCREENED.value
                store.upsert_paper(paper)
        except Exception as exc:
            report.errors.append(f"{paper.canonical_id}: {exc}")
            logger.warning("Screen error %s: %s", paper.canonical_id, exc)

    # Sort by composite score descending, only passed papers
    passed_scored = [s for s in scored if s.passed]
    passed_scored.sort(key=lambda s: s.composite, reverse=True)

    report.candidates = passed_scored
    report.featured = min(
        ranking.daily_limits.featured_papers,
        len(passed_scored),
    )

    logger.info(
        "Stage 2 LLM screen: %d candidates → %d scored, %d passed, %d featured",
        len(screen_batch),
        len(scored),
        len(passed_scored),
        report.featured,
    )
    return report


async def run_screening(
    store: PaperStore,
    provider: ModelProvider,
    ranking: RankingConfig | None = None,
) -> ScreeningReport:
    """Run the full two-stage screening pipeline."""
    from arc.config import load_ranking_config

    ranking = ranking or load_ranking_config()
    cfg = load_hard_filter_config()
    papers = store.get_papers(status=PipelineStatus.NORMALIZED.value, limit=300)
    candidates = run_stage1(store, cfg)

    if not candidates:
        logger.info("Screening: no candidates after stage 1")
        return ScreeningReport(stage1_input=len(papers), stage1_passed=0)

    report = await run_stage2(candidates, provider, ranking, store=store)
    report.stage1_input = len(papers)
    return report


# ---------------------------------------------------------------------------
# Feedback calibration (Tech Spec §10.2)
# ---------------------------------------------------------------------------


def calibrate_weights_from_feedback(
    ranking: RankingConfig | None = None,
    *,
    min_samples: int = 20,
) -> dict[str, dict]:
    """Suggest weight adjustments from feedback.jsonl.

    Requires ``min_samples`` labeled positive+negative entries before suggesting
    non-identity changes. Loads ``config/ranking.yaml`` by default.
    """
    from arc.config import load_ranking_config
    from arc.memory import list_feedback
    from arc.schemas import FeedbackLabel

    ranking = ranking or load_ranking_config()
    entries = list_feedback(limit=500)

    positive_count = sum(
        1
        for e in entries
        if e.label
        in (
            FeedbackLabel.WORTH_READING,
            FeedbackLabel.DIRECTLY_RELEVANT,
            FeedbackLabel.METHOD_TRANSFERABLE,
        )
    )
    negative_count = sum(
        1
        for e in entries
        if e.label
        in (
            FeedbackLabel.INSUFFICIENT_EVIDENCE,
            FeedbackLabel.HYPE_OVER_CONTRIBUTION,
            FeedbackLabel.STOP_RECOMMENDING,
        )
    )
    total_relevant = positive_count + negative_count

    result: dict[str, dict] = {}
    if total_relevant < min_samples:
        for k, v in ranking.weights.items():
            result[k] = {
                "current": v,
                "suggested": v,
                "reason": f"insufficient_samples ({total_relevant}<{min_samples})",
            }
        return result

    ratio = positive_count / total_relevant
    # Only nudge relevance-like weights; leave penalty P alone.
    nudge_keys = {"R", "L", "E", "F", "N", "T"}
    adjustment = (ratio - 0.5) * 0.1  # max ±0.05

    for k, v in ranking.weights.items():
        if k in nudge_keys:
            suggested = round(max(0.05, min(0.40, v + adjustment)), 3)
            reason = f"feedback_ratio={ratio:.2f} ({positive_count}+/{total_relevant})"
        else:
            suggested = v
            reason = "penalty_or_fixed_weight"
        result[k] = {"current": v, "suggested": suggested, "reason": reason}

    return result


def audit_exploration_mix(store: PaperStore | None = None) -> dict:
    """Audit the 70/20/10 exploration mix from stored papers.

    Categorizes papers by topic keywords into:
    - project_related: matches configured topic keywords
    - adjacent_methods: shares categories with enabled channels
    - high_uncertainty: neither of the above
    """
    cfg = load_hard_filter_config()

    # Collect all topic keywords
    all_keywords: set[str] = set()
    for kw_list in cfg.topic_keywords.values():
        all_keywords.update(k.lower() for k in kw_list)

    project_related = 0
    adjacent = 0
    uncertain = 0
    total = 0

    if store:
        papers = store.get_papers(limit=500)
        for p in papers:
            total += 1
            text = (p.title + " " + p.abstract).lower()
            if any(kw in text for kw in all_keywords):
                project_related += 1
            elif set(p.categories) & cfg.allowed_categories:
                adjacent += 1
            else:
                uncertain += 1

    if total == 0:
        return {"project_related": 0, "adjacent_methods": 0, "high_uncertainty": 0,
                "note": "no_papers_in_store"}

    return {
        "project_related": round(project_related / total * 100, 1),
        "adjacent_methods": round(adjacent / total * 100, 1),
        "high_uncertainty": round(uncertain / total * 100, 1),
        "sample_size": total,
    }
