"""
Pydantic schemas for Phase 6 — Resolution Orchestrator & Human Review Workflow
"""
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
import json as _json


# ---------------------------------------------------------------------------
# Resolution Response
# ---------------------------------------------------------------------------

class ResolutionResponse(BaseModel):
    resolution_id: str
    reconciliation_run_id: str
    order_id: str
    exception_id: int
    ai_investigation_id: Optional[str] = None

    deterministic_exception_type: str
    ai_classification: Optional[str] = None

    resolution_status: str
    resolution_reason: Optional[str] = None

    confidence: Optional[float] = None
    effective_confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    safety_flags: List[str] = []

    human_review_required: bool
    resolved_by: Optional[str] = None
    resolution_notes: Optional[str] = None

    priority: int = 50
    priority_reason: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("safety_flags", mode="before")
    @classmethod
    def _parse_flags(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return v if isinstance(v, list) else []


# ---------------------------------------------------------------------------
# Review Queue Item — enriched view for human reviewers
# ---------------------------------------------------------------------------

class ReviewQueueItem(BaseModel):
    resolution_id: str
    order_id: str
    deterministic_exception_type: str
    resolution_status: str
    confidence: Optional[float] = None
    effective_confidence: Optional[float] = None
    confidence_level: Optional[str] = None
    safety_flags: List[str] = []
    priority: int
    priority_reason: Optional[str] = None
    human_review_required: bool
    ai_investigation_id: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("safety_flags", mode="before")
    @classmethod
    def _parse_flags(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except Exception:
                return []
        return v if isinstance(v, list) else []


# ---------------------------------------------------------------------------
# Audit Event
# ---------------------------------------------------------------------------

class ResolutionEventResponse(BaseModel):
    event_id: str
    resolution_id: str
    previous_status: Optional[str] = None
    new_status: str
    actor_type: str
    actor_id: Optional[str] = None
    reason: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Human Decision Requests
# ---------------------------------------------------------------------------

class HumanDecisionRequest(BaseModel):
    notes: str = Field(..., min_length=1, description="Human reviewer notes")


class UnresolveRequest(BaseModel):
    reason: str = Field(..., min_length=1, description="Reason for reopening the case")


# ---------------------------------------------------------------------------
# Batch Resolution
# ---------------------------------------------------------------------------

class BatchResolutionRequest(BaseModel):
    reconciliation_run_id: str = Field(..., description="Reconciliation run to process")
    max_cases: int = Field(default=50, ge=1, le=500, description="Maximum cases to process")


class BatchResolutionResponse(BaseModel):
    total_eligible: int
    auto_resolved: int
    review_recommended: int
    human_review_required: int
    ai_failed: int
    unresolved: int


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class ResolutionSummaryResponse(BaseModel):
    total_exceptions: int
    investigated: int
    auto_resolved: int
    review_recommended: int
    human_review_required: int
    approved_by_human: int
    rejected_by_human: int
    unresolved: int
    ai_failed: int

    auto_resolution_rate: float
    human_review_rate: float
    unresolved_rate: float
