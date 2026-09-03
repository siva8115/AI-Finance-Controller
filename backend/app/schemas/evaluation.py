from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class EvaluationRunRequest(BaseModel):
    reconciliation_run_id: Optional[str] = Field(default=None, description="Reconciliation run ID to evaluate (defaults to latest completed run)")


class ConfusionMatrixResponse(BaseModel):
    true_negatives: int = Field(description="Actual MATCHED, Predicted MATCHED (TN)")
    false_positives: int = Field(description="Actual MATCHED, Predicted EXCEPTION (FP)")
    false_negatives: int = Field(description="Actual EXCEPTION, Predicted MATCHED (FN)")
    true_positives: int = Field(description="Actual EXCEPTION, Predicted EXCEPTION (TP)")


class MismatchDetail(BaseModel):
    order_id: str
    ground_truth_status: str
    controller_status: str
    ground_truth_exception_type: str
    controller_exception_types: List[str] = []
    is_status_correct: bool
    is_category_correct: bool
    mismatch_type: str  # FALSE_POSITIVE, FALSE_NEGATIVE, CATEGORY_MISMATCH
    reason: str


class EvaluationSummary(BaseModel):
    evaluation_run_id: str
    reconciliation_run_id: str
    evaluated_at: Optional[datetime] = None

    # Level 1 Metrics
    total_records: int
    correctly_classified_status: int
    incorrectly_classified_status: int
    status_accuracy: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    precision: float
    recall: float
    f1_score: float

    # Level 2 Metrics
    total_ground_truth_anomalies: int
    correctly_classified_exceptions: int
    incorrectly_classified_exceptions: int
    exception_classification_accuracy: float

    # Operational Metrics
    matched_count: int
    exception_count: int
    match_rate: float
    exception_rate: float
    processing_time_seconds: float
    throughput_records_per_second: float

    confusion_matrix: Dict[str, int]
    mismatches: List[MismatchDetail] = []

    model_config = ConfigDict(from_attributes=True)
