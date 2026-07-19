"""Daily editorial brief schemas — prose constrained by evidence IDs."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BriefHeadline(BaseModel):
    """Front-page judgment (not a raw paper title dump)."""

    title: str = Field(description="Editorial headline, ≤40 chars preferred")
    why_it_matters: str = Field(description="Why this changes (or doesn't) my research stance")
    paper_id: str | None = None
    question_id: str | None = None
    confidence: str = Field(default="medium", description="low|medium|high")
    suggested_move: str = Field(default="", description="Concrete next move")


class BriefFeatured(BaseModel):
    paper_id: str
    paper_title: str
    one_line_judgment: str
    actual_delta: str = Field(description="Real increment vs prior work, not author hype")
    link_to_project: str = Field(description="Which project/question it touches, or 'radar only'")
    verdict: str = Field(description="READ|TRY|WATCH|ARCHIVE|NO-GO")
    source_url: str = ""


class BriefAction(BaseModel):
    text: str = Field(description="Executable action, not 'continue researching'")
    paper_id: str | None = None


class DailyBrief(BaseModel):
    """Chair/Editor output: living core of the morning brief."""

    lede: str = Field(
        description="1–3 sentences: what mattered today for MY research state"
    )
    quiet_day: bool = False
    headlines: list[BriefHeadline] = Field(default_factory=list, max_length=3)
    state_changes: str | None = Field(
        default=None,
        description="None → omit section. Else short prose on judgment updates.",
    )
    featured: list[BriefFeatured] = Field(default_factory=list, max_length=4)
    radar: list[str] = Field(default_factory=list)
    idea_notes: list[str] = Field(default_factory=list)
    actions: list[BriefAction] = Field(default_factory=list, max_length=3)
    reading_minutes_hint: int = Field(default=8, ge=3, le=20)
