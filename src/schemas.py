"""Pydantic v2 schemas for every data object in TAD.

Every LLM input/output is schema-validated; parse failures dead-letter with the raw response.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Category = Literal["F", "B", "I", "A", "E", "G", "H", "J"]
Verdict = Literal["RESOLVED", "PARTIALLY_RESOLVED", "UNRESOLVED"]
RewriteStatus = Literal["OK", "INSUFFICIENT_GROUNDING", "SKIPPED"]
JudgeDecision = Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "WRONG_CATEGORY", "UNCERTAIN"]


class Chunk(BaseModel):
    id: str
    doc_id: str
    page: int
    text: str
    clause_hint: Optional[str] = None
    char_start: int = 0
    char_end: int = 0


class DetectionPass(BaseModel):
    """Output of a single detection prompt variant (v1 / v2 / v3) for one chunk+category."""
    pass_id: str  # "v1" | "v2" | "v3"
    category: Category
    chunk_id: str
    span_text: str
    span_char_start: int
    span_char_end: int
    confidence: float = Field(ge=0.0, le=1.0)
    justification: str


class NegativeProbe(BaseModel):
    category: Category
    span_text: str
    disagrees: bool
    reason: str


class FlagCluster(BaseModel):
    """A confirmed or review-queue cluster of detection passes."""
    id: str
    chunk_id: str
    category: Category
    span_text: str
    span_char_start: int
    span_char_end: int
    mean_confidence: float
    agreement_rate: float  # fraction of v1/v2/v3 that voted this span
    passes: list[DetectionPass]
    negative_probe: Optional[NegativeProbe] = None
    status: Literal["CONFIRMED", "REVIEW_QUEUE"] = "CONFIRMED"

    @field_validator("agreement_rate")
    @classmethod
    def _clip_rate(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class RetrievedContext(BaseModel):
    context_id: str
    source: Literal["tender", "is_code", "graph"]
    text: str
    score: float = 0.0
    meta: dict[str, Any] = Field(default_factory=dict)


class Resolution(BaseModel):
    flag_id: str
    verdict: Verdict
    reasoning: str
    cited_context_ids: list[str] = Field(default_factory=list)
    retrieved: list[RetrievedContext] = Field(default_factory=list)
    needs_re_adjudication: bool = False
    judge_stripped: list[str] = Field(default_factory=list)


class Rewrite(BaseModel):
    flag_id: str
    status: RewriteStatus
    suggested_text: str = ""
    grounding: list[str] = Field(default_factory=list)  # IS-code refs present in cited grounding
    explanation: str = ""


class Entity(BaseModel):
    id: str
    surface_forms: list[str]
    canonical: str
    kind: Literal["DOCUMENT", "CLAUSE", "ENTITY", "QUANTITY", "PRIORITY_RULE"] = "ENTITY"
    sources: list[str] = Field(default_factory=list)  # chunk ids


class Quantity(BaseModel):
    id: str
    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    raw_text: str = ""
    source_chunk_id: str = ""


class PriorityRule(BaseModel):
    id: str
    dominant_doc: str
    subordinate_doc: str
    source_chunk_id: str
    raw_text: str


class Conflict(BaseModel):
    id: str
    kind: Literal["PRIORITY", "NUMERIC"]
    description: str
    involved_chunks: list[str]
    involved_quantities: list[str] = Field(default_factory=list)


class LLMCallRecord(BaseModel):
    call_id: str
    stage: str
    model: str
    prompt: str
    response_raw: str
    response_parsed: Optional[Any] = None
    parse_ok: bool = True
    elapsed_ms: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    error: Optional[str] = None


class AnnotationCandidate(BaseModel):
    candidate_id: str
    flag_id: str
    category: Category
    span_text: str
    chunk_text: str
    justification: str
    surrounding_context: str = ""


class JudgeVerdict(BaseModel):
    candidate_id: str
    decision: JudgeDecision
    corrected_category: Optional[Category] = None
    reason: str


class GoldFlag(BaseModel):
    flag_id: str
    category: Category
    chunk_id: str
    span_char_start: int
    span_char_end: int
    span_text: str
    source: Literal["protocol", "human", "recall_audit"]


class PipelineResult(BaseModel):
    run_id: str
    doc_ids: list[str]
    n_chunks: int
    n_flags_confirmed: int
    n_flags_review: int
    n_resolutions: int
    n_rewrites: int
    elapsed_seconds: float
    per_category_counts: dict[str, int] = Field(default_factory=dict)
    artifact_paths: dict[str, str] = Field(default_factory=dict)


class AblationRun(BaseModel):
    name: str
    description: str
    metrics: dict[str, float]
    delta_vs_baseline: dict[str, float] = Field(default_factory=dict)
