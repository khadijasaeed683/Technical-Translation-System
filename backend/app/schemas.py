from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: str
    email: EmailStr
    is_admin: bool

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Translation ----------
class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    # "auto" lets the preprocessing/detection stage pick the direction (FR-08)
    source_lang: str = Field(default="auto")
    target_lang: Optional[str] = None  # required only if source_lang != "auto"


class DiffOp(BaseModel):
    op: str  # "equal" | "insert" | "delete" | "replace"
    raw: str
    validated: str


class TraceStep(BaseModel):
    """One entry in the step-by-step pipeline log shown in the UI."""

    step: int
    name: str
    status: str  # "ok" | "skipped" | "fallback" | "failed"
    duration_ms: int
    summary: str
    details: Dict[str, Any] = Field(default_factory=dict)


class TranslateResponse(BaseModel):
    id: str
    source_text: str
    source_lang: str
    target_lang: str
    raw_output: str
    validated_output: str
    final_output: str
    confidence: Optional[float]
    alternates: Optional[List[str]]
    is_validated: bool
    diff: List[DiffOp]
    correction_reason: Optional[List[str]]
    trace: List[TraceStep] = Field(default_factory=list)
    total_ms: int = 0
    timestamp: datetime

    class Config:
        from_attributes = True


class TraceResponse(BaseModel):
    id: str
    trace: List[TraceStep]


class HistoryItem(BaseModel):
    id: str
    source_text: str
    source_lang: str
    target_lang: str
    validated_output: str
    final_output: str
    confidence: Optional[float]
    is_validated: bool
    timestamp: datetime

    class Config:
        from_attributes = True


class TranslationOutputUpdate(BaseModel):
    final_output: str = Field(min_length=1)


class TranslationOutputOut(BaseModel):
    id: str
    final_output: str

    class Config:
        from_attributes = True


# ---------- Feedback ----------
class FeedbackCreate(BaseModel):
    translation_id: str
    rating: str = Field(pattern="^(up|down)$")
    comment: Optional[str] = None


class FeedbackOut(BaseModel):
    id: str
    translation_id: str
    rating: str
    comment: Optional[str]
    timestamp: datetime

    class Config:
        from_attributes = True


# ---------- Glossary ----------
class GlossaryTermCreate(BaseModel):
    term: str
    domain: str = "general"
    canonical_translation: str
    aliases: Optional[List[str]] = None
    roman_urdu_variants: Optional[List[str]] = None


class GlossaryTermOut(GlossaryTermCreate):
    id: str

    class Config:
        from_attributes = True


# ---------- Admin ----------
class AdminAnalytics(BaseModel):
    total_translations: int
    total_feedback: int
    thumbs_up: int
    thumbs_down: int
    thumbs_up_rate: float
    correction_rate: float  # % of translations where validation changed the raw output
    unvalidated_fallback_rate: float  # % served via UC-09 fallback
    top_correction_reasons: List[dict]


# ---------- Evaluation ----------
class EvaluationTriggerRequest(BaseModel):
    sample_size: Optional[int] = None  # None = full seed dataset


class EvaluationMetricRow(BaseModel):
    metric: str
    google_translate: Optional[float]
    raw_base_model: Optional[float]
    our_system: Optional[float]


class EvaluationResult(BaseModel):
    id: str
    dataset_size: int
    metrics: List[EvaluationMetricRow]
    timestamp: datetime