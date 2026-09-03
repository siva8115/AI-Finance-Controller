from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
import json as _json


class AIInvestigationResponse(BaseModel):
    investigation_id: str
    order_id: str

    # Deterministic exception type (authoritative)
    exception_type: str

    # AI investigation narrative
    summary: str
    likely_cause: str
    recommended_action: str

    # Structured AI reasoning (stored as JSON strings in DB; deserialized here)
    evidence_facts: List[str] = []
    possible_causes: List[str] = []
    evidence_gaps: List[str] = []

    # AI raw classification (audit only — does not override exception_type)
    ai_classification: Optional[str] = None
    ai_classification_matches_deterministic: bool = True

    # Dual confidence
    ai_confidence: Optional[float] = None
    effective_confidence: Optional[float] = None
    confidence: Optional[float] = None           # alias for effective_confidence
    confidence_level: str

    # Safety outcome
    investigation_status: str
    requires_human_review: bool
    safety_flags: List[str] = []

    # Evidence Escalation Metadata
    evidence_level: str = "LEVEL 1"
    evidence_records_count: int = 0
    ai_attempts: int = 1
    escalation_history: List[Any] = []

    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    # Deserialize any field that the ORM returns as a JSON string
    @field_validator("evidence_facts", "possible_causes", "evidence_gaps", "safety_flags", "escalation_history", mode="before")
    @classmethod
    def _parse_json_list(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                parsed = _json.loads(v)
                return parsed if isinstance(parsed, list) else []
            except (_json.JSONDecodeError, TypeError):
                return []
        return v if isinstance(v, list) else []



class BatchAIInvestigationRequest(BaseModel):
    reconciliation_run_id: str = Field(..., description="ID of the reconciliation run to investigate")
    max_cases: int = Field(default=20, ge=1, le=100, description="Max number of cases to process")


class BatchAIInvestigationResponse(BaseModel):
    total_exceptions: int
    investigated_cases: int
    successful_investigations: int
    failed_investigations: int
    human_review_required: int


# ---------------------------------------------------------------------------
# Internal schema used only to validate what Gemini returns
# ---------------------------------------------------------------------------
class GeminiInvestigationSchema(BaseModel):
    classification: Literal[
        "AMOUNT_MISMATCH",
        "MISSING_PAYMENT",
        "UNMATCHED_SETTLEMENT",
        "FEE_DISCREPANCY",
        "TIMING_DELAY",
        "DUPLICATE_PAYMENT",
        "UNACCOUNTED_REFUND",
        "UNKNOWN_EXCEPTION",
    ]
    summary: str
    likely_cause: str
    recommended_action: str
    evidence_facts: List[str] = []
    possible_causes: List[str] = []
    evidence_gaps: List[str] = []
    confidence: float
    requires_human_review: bool
