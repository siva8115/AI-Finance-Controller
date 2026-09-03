from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    customer_id = Column(String, index=True, nullable=False)
    merchant_id = Column(String, nullable=True, default="MERCHANT_001")
    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")
    status = Column(String, default="COMPLETED")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "order_id": self.order_id,
            "customer_id": self.customer_id,
            "merchant_id": self.merchant_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    payment_id = Column(String, unique=True, index=True, nullable=False)
    order_id = Column(String, index=True, nullable=False)
    gateway = Column(String, nullable=False, default="Stripe")
    amount = Column(Float, nullable=False)
    fee = Column(Float, nullable=False, default=0.0)
    currency = Column(String, default="USD")
    status = Column(String, default="CAPTURED")
    transaction_ref = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "payment_id": self.payment_id,
            "order_id": self.order_id,
            "gateway": self.gateway,
            "amount": self.amount,
            "fee": self.fee,
            "currency": self.currency,
            "status": self.status,
            "transaction_ref": self.transaction_ref,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(Integer, primary_key=True, index=True)
    settlement_id = Column(String, unique=True, index=True, nullable=False)
    payment_id = Column(String, index=True, nullable=False)
    payout_ref = Column(String, nullable=False)
    gross_amount = Column(Float, nullable=False)
    net_amount = Column(Float, nullable=False)
    fee_deducted = Column(Float, nullable=False, default=0.0)
    currency = Column(String, default="USD")
    settlement_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="SETTLED")

    def to_dict(self):
        return {
            "settlement_id": self.settlement_id,
            "payment_id": self.payment_id,
            "payout_ref": self.payout_ref,
            "gross_amount": self.gross_amount,
            "net_amount": self.net_amount,
            "fee_deducted": self.fee_deducted,
            "currency": self.currency,
            "settlement_date": self.settlement_date.isoformat() if self.settlement_date else None,
            "status": self.status,
        }


class ReconciliationRun(Base):
    __tablename__ = "reconciliation_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, unique=True, index=True, nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="RUNNING")
    total_records = Column(Integer, default=0)
    matched_count = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    processing_time_seconds = Column(Float, nullable=True, default=0.0)

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "status": self.status,
            "total_records": self.total_records,
            "matched_count": self.matched_count,
            "exception_count": self.exception_count,
            "processing_time_seconds": round(self.processing_time_seconds, 4) if self.processing_time_seconds else 0.0,
        }


class ExceptionRecord(Base):
    __tablename__ = "exception_records"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True, nullable=False)
    order_id = Column(String, nullable=True, index=True)
    payment_id = Column(String, nullable=True, index=True)
    settlement_id = Column(String, nullable=True, index=True)
    exception_type = Column(String, nullable=False)
    severity = Column(String, default="MEDIUM")
    status = Column(String, default="DETECTED")
    expected_value = Column(String, nullable=True)
    actual_value = Column(String, nullable=True)
    difference = Column(Float, nullable=True)
    ai_investigated = Column(Boolean, default=False)
    ai_confidence = Column(Float, nullable=True)
    ai_root_cause = Column(Text, nullable=True)
    ai_recommendation = Column(Text, nullable=True)
    details = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "order_id": self.order_id,
            "payment_id": self.payment_id,
            "settlement_id": self.settlement_id,
            "exception_type": self.exception_type,
            "severity": self.severity,
            "status": self.status,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "difference": self.difference,
            "ai_investigated": self.ai_investigated,
            "ai_confidence": self.ai_confidence,
            "ai_root_cause": self.ai_root_cause,
            "ai_recommendation": self.ai_recommendation,
            "details": self.details,
        }


class ReconciliationResult(Base):
    __tablename__ = "reconciliation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String, index=True, nullable=False)
    order_id = Column(String, index=True, nullable=False)
    payment_ids = Column(Text, nullable=True)
    settlement_ids = Column(Text, nullable=True)
    reconciliation_status = Column(String, nullable=False, default="MATCHED")
    exception_types = Column(Text, nullable=True)
    order_amount = Column(Float, nullable=True)
    payment_amount = Column(Float, nullable=True)
    settlement_gross_amount = Column(Float, nullable=True)
    settlement_net_amount = Column(Float, nullable=True)
    payment_fee = Column(Float, nullable=True)
    settlement_fee = Column(Float, nullable=True)
    amount_difference = Column(Float, nullable=True)
    settlement_difference = Column(Float, nullable=True)
    match_method = Column(String, default="DETERMINISTIC_3WAY")
    explanation = Column(Text, nullable=True)
    recommended_action = Column(Text, nullable=True)
    checked_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "run_id": self.run_id,
            "order_id": self.order_id,
            "payment_ids": json.loads(self.payment_ids) if self.payment_ids else [],
            "settlement_ids": json.loads(self.settlement_ids) if self.settlement_ids else [],
            "reconciliation_status": self.reconciliation_status,
            "exception_types": json.loads(self.exception_types) if self.exception_types else [],
            "order_amount": self.order_amount,
            "payment_amount": self.payment_amount,
            "settlement_gross_amount": self.settlement_gross_amount,
            "settlement_net_amount": self.settlement_net_amount,
            "payment_fee": self.payment_fee,
            "settlement_fee": self.settlement_fee,
            "amount_difference": self.amount_difference,
            "settlement_difference": self.settlement_difference,
            "match_method": self.match_method,
            "explanation": self.explanation,
            "recommended_action": self.recommended_action,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_run_id = Column(String, unique=True, index=True, nullable=False)
    reconciliation_run_id = Column(String, index=True, nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow)

    # Level 1 Metrics
    total_records = Column(Integer, default=0)
    correctly_classified_status = Column(Integer, default=0)
    incorrectly_classified_status = Column(Integer, default=0)
    status_accuracy = Column(Float, default=0.0)
    true_positives = Column(Integer, default=0)
    false_positives = Column(Integer, default=0)
    false_negatives = Column(Integer, default=0)
    true_negatives = Column(Integer, default=0)
    precision = Column(Float, default=0.0)
    recall = Column(Float, default=0.0)
    f1_score = Column(Float, default=0.0)

    # Level 2 Metrics
    total_ground_truth_anomalies = Column(Integer, default=0)
    correctly_classified_exceptions = Column(Integer, default=0)
    incorrectly_classified_exceptions = Column(Integer, default=0)
    exception_classification_accuracy = Column(Float, default=0.0)

    # Operational Metrics
    matched_count = Column(Integer, default=0)
    exception_count = Column(Integer, default=0)
    match_rate = Column(Float, default=0.0)
    exception_rate = Column(Float, default=0.0)
    processing_time_seconds = Column(Float, default=0.0)
    throughput_records_per_second = Column(Float, default=0.0)

    # JSON Reports
    confusion_matrix_json = Column(Text, nullable=True)
    mismatches_json = Column(Text, nullable=True)

    def to_dict(self):
        import json
        return {
            "evaluation_run_id": self.evaluation_run_id,
            "reconciliation_run_id": self.reconciliation_run_id,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
            "total_records": self.total_records,
            "correctly_classified_status": self.correctly_classified_status,
            "incorrectly_classified_status": self.incorrectly_classified_status,
            "status_accuracy": round(self.status_accuracy, 4),
            "true_positives": self.true_positives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "true_negatives": self.true_negatives,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1_score": round(self.f1_score, 4),
            "total_ground_truth_anomalies": self.total_ground_truth_anomalies,
            "correctly_classified_exceptions": self.correctly_classified_exceptions,
            "incorrectly_classified_exceptions": self.incorrectly_classified_exceptions,
            "exception_classification_accuracy": round(self.exception_classification_accuracy, 4),
            "matched_count": self.matched_count,
            "exception_count": self.exception_count,
            "match_rate": round(self.match_rate, 4),
            "exception_rate": round(self.exception_rate, 4),
            "processing_time_seconds": round(self.processing_time_seconds, 4),
            "throughput_records_per_second": round(self.throughput_records_per_second, 2),
            "confusion_matrix": json.loads(self.confusion_matrix_json) if self.confusion_matrix_json else {},
            "mismatches": json.loads(self.mismatches_json) if self.mismatches_json else [],
        }


class AIInvestigation(Base):
    __tablename__ = "ai_investigations"

    id = Column(Integer, primary_key=True, index=True)
    investigation_id = Column(String, unique=True, index=True, nullable=False)
    reconciliation_run_id = Column(String, index=True, nullable=False)
    order_id = Column(String, index=True, nullable=False)
    exception_id = Column(Integer, ForeignKey("exception_records.id"), nullable=False)

    # Deterministic exception type (authoritative — never changed by AI)
    exception_type = Column(String, nullable=False)

    # AI investigation content
    summary = Column(Text, nullable=False)
    likely_cause = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)

    # AI raw classification (stored for audit — does NOT override exception_type)
    ai_classification = Column(String, nullable=True)
    ai_classification_matches_deterministic = Column(Boolean, nullable=False, default=True)

    # Structured AI reasoning (JSON arrays stored as Text)
    evidence_facts = Column(Text, nullable=True)    # JSON list of confirmed facts
    possible_causes = Column(Text, nullable=True)   # JSON list of hypotheses
    evidence_gaps = Column(Text, nullable=True)     # JSON list of missing info

    # Dual confidence: raw AI score preserved separately from backend-controlled score
    ai_confidence = Column(Float, nullable=False)
    effective_confidence = Column(Float, nullable=False)
    confidence_level = Column(String, nullable=False)   # HIGH, MEDIUM, LOW

    # Safety outcome
    requires_human_review = Column(Boolean, nullable=False, default=True)
    investigation_status = Column(String, nullable=False)   # AUTO_RESOLVED, REVIEW_RECOMMENDED, HUMAN_REVIEW_REQUIRED, AI_FAILED
    safety_flags = Column(Text, nullable=True)              # JSON list of flag strings

    # Evidence Escalation Metadata
    evidence_level = Column(String, nullable=False, default="LEVEL 1")
    evidence_records_count = Column(Integer, nullable=False, default=0)
    ai_attempts = Column(Integer, nullable=False, default=1)
    escalation_history = Column(Text, nullable=True)        # JSON list of escalation step dicts

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    exception_record = relationship("ExceptionRecord", backref="ai_investigations")

    def to_dict(self):
        import json as _json
        return {
            "id": self.id,
            "investigation_id": self.investigation_id,
            "reconciliation_run_id": self.reconciliation_run_id,
            "order_id": self.order_id,
            "exception_id": self.exception_id,
            "exception_type": self.exception_type,
            "summary": self.summary,
            "likely_cause": self.likely_cause,
            "recommended_action": self.recommended_action,
            "ai_classification": self.ai_classification,
            "ai_classification_matches_deterministic": self.ai_classification_matches_deterministic,
            "evidence_facts": _json.loads(self.evidence_facts) if self.evidence_facts else [],
            "possible_causes": _json.loads(self.possible_causes) if self.possible_causes else [],
            "evidence_gaps": _json.loads(self.evidence_gaps) if self.evidence_gaps else [],
            "ai_confidence": self.ai_confidence,
            "effective_confidence": self.effective_confidence,
            "confidence": self.effective_confidence,   # alias for backward compat
            "confidence_level": self.confidence_level,
            "requires_human_review": self.requires_human_review,
            "investigation_status": self.investigation_status,
            "safety_flags": _json.loads(self.safety_flags) if self.safety_flags else [],
            "evidence_level": self.evidence_level or "LEVEL 1",
            "evidence_records_count": self.evidence_records_count or 0,
            "ai_attempts": self.ai_attempts or 1,
            "escalation_history": _json.loads(self.escalation_history) if self.escalation_history else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# ---------------------------------------------------------------------------
# Resolution — final operational decision record for an exception
# ---------------------------------------------------------------------------
class Resolution(Base):
    __tablename__ = "resolutions"

    id = Column(Integer, primary_key=True, index=True)
    resolution_id = Column(String, unique=True, index=True, nullable=False)
    reconciliation_run_id = Column(String, index=True, nullable=False)
    order_id = Column(String, index=True, nullable=False)
    exception_id = Column(Integer, ForeignKey("exception_records.id"), nullable=False)
    ai_investigation_id = Column(String, nullable=True)          # investigation_id (string FK to AIInvestigation)

    # Authoritative exception type (never changed)
    deterministic_exception_type = Column(String, nullable=False)
    # AI classification at time of resolution (audit)
    ai_classification = Column(String, nullable=True)

    # Resolution outcome
    resolution_status = Column(String, nullable=False, default="PENDING_INVESTIGATION")
    resolution_reason = Column(Text, nullable=True)

    # Snapshot of investigation metrics at resolution time
    confidence = Column(Float, nullable=True)
    effective_confidence = Column(Float, nullable=True)
    confidence_level = Column(String, nullable=True)
    safety_flags = Column(Text, nullable=True)          # JSON array

    # Human-review outcome
    human_review_required = Column(Boolean, nullable=False, default=True)
    resolved_by = Column(String, nullable=True)         # SYSTEM | AI | HUMAN
    resolution_notes = Column(Text, nullable=True)

    # Priority for review queue
    priority = Column(Integer, nullable=False, default=50)       # Lower = higher priority
    priority_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    exception_record = relationship("ExceptionRecord", backref="resolutions")

    def to_dict(self):
        import json as _j
        return {
            "id": self.id,
            "resolution_id": self.resolution_id,
            "reconciliation_run_id": self.reconciliation_run_id,
            "order_id": self.order_id,
            "exception_id": self.exception_id,
            "ai_investigation_id": self.ai_investigation_id,
            "deterministic_exception_type": self.deterministic_exception_type,
            "ai_classification": self.ai_classification,
            "resolution_status": self.resolution_status,
            "resolution_reason": self.resolution_reason,
            "confidence": self.confidence,
            "effective_confidence": self.effective_confidence,
            "confidence_level": self.confidence_level,
            "safety_flags": _j.loads(self.safety_flags) if self.safety_flags else [],
            "human_review_required": self.human_review_required,
            "resolved_by": self.resolved_by,
            "resolution_notes": self.resolution_notes,
            "priority": self.priority,
            "priority_reason": self.priority_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


# ---------------------------------------------------------------------------
# ResolutionEvent — immutable audit trail for every status transition
# ---------------------------------------------------------------------------
class ResolutionEvent(Base):
    __tablename__ = "resolution_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String, unique=True, index=True, nullable=False)
    resolution_id = Column(String, index=True, nullable=False)
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)     # SYSTEM | AI | HUMAN
    actor_id = Column(String, nullable=True)        # e.g. "SYSTEM" / "ORCHESTRATOR" / user id
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "event_id": self.event_id,
            "resolution_id": self.resolution_id,
            "previous_status": self.previous_status,
            "new_status": self.new_status,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "reason": self.reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


