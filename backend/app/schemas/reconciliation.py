from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class ReconciliationRunRequest(BaseModel):
    settlement_window_days: Optional[int] = Field(default=None, description="Max allowed days between payment and settlement")
    monetary_tolerance: Optional[float] = Field(default=None, description="Tolerance threshold for currency comparison")


class ReconciliationRunSummary(BaseModel):
    run_id: str
    status: str
    total_records: int
    matched: int
    exceptions: int
    processing_time_seconds: float
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ReconciliationResultResponse(BaseModel):
    id: int
    run_id: str
    order_id: str
    payment_ids: List[str] = []
    settlement_ids: List[str] = []
    reconciliation_status: str
    exception_types: List[str] = []
    order_amount: Optional[float] = None
    payment_amount: Optional[float] = None
    settlement_gross_amount: Optional[float] = None
    settlement_net_amount: Optional[float] = None
    payment_fee: Optional[float] = None
    settlement_fee: Optional[float] = None
    amount_difference: Optional[float] = None
    settlement_difference: Optional[float] = None
    match_method: str = "DETERMINISTIC_3WAY"
    explanation: Optional[str] = None
    recommended_action: Optional[str] = None
    checked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExceptionRecordResponse(BaseModel):
    id: int
    run_id: str
    order_id: Optional[str] = None
    payment_id: Optional[str] = None
    settlement_id: Optional[str] = None
    exception_type: str
    severity: str = "MEDIUM"
    status: str = "DETECTED"
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    difference: Optional[float] = None
    ai_investigated: bool = False
    ai_confidence: Optional[float] = None
    ai_root_cause: Optional[str] = None
    ai_recommendation: Optional[str] = None
    details: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
