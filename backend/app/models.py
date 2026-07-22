from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class AnalyzeRequest(BaseModel):
    url: HttpUrl


Verdict = Literal["worth_it", "mixed", "skip"]
Label = Literal["real_value", "clickbait", "rage_bait", "mixed_signals"]


class AnalysisResult(BaseModel):
    video_id: str
    title: str | None = None
    channel: str | None = None
    duration_hint: str | None = None
    verdict: Verdict
    worth_score: int = Field(ge=0, le=100)
    labels: list[Label]
    confidence: Literal["high", "medium", "low"]
    summary_bullets: list[str] = Field(min_length=1, max_length=5)
    watch_if: str
    skip_if: str
    bait_risk: str
    evidence_quotes: list[str] = Field(default_factory=list, max_length=5)
    cached: bool = False


class AnalyzeResponse(BaseModel):
    ok: bool = True
    result: AnalysisResult


class ErrorResponse(BaseModel):
    ok: bool = False
    error: str
    detail: str | None = None
