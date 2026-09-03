"""
Evidence Extractor Service — Progressive Evidence Escalation Architecture

Responsibilities:
1. Exception-aware targeted evidence collection.
2. Progressive evidence levels (LEVEL 1: Minimal, LEVEL 2: Related, LEVEL 3: Extended).
3. Payload budgeting, field pruning, string truncation, and metadata logging.
4. Deterministic evidence hashing for investigation caching.
"""

import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.financial import Order, Payment, Settlement, ExceptionRecord

logger = logging.getLogger(__name__)


def _sanitize_record(obj: Any) -> Dict[str, Any]:
    """Helper to convert ORM model to dictionary while excluding internal DB PKs & system fields."""
    if obj is None:
        return {}
    
    d = obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)
    # Remove internal primary keys and non-auditable metadata if present
    for internal_key in ["id", "ground_truth_path", "internal_id", "_sa_instance_state"]:
        d.pop(internal_key, None)
    return d


def _truncate_text(text: Optional[str], max_len: int = 200) -> str:
    if not text:
        return ""
    if len(text) > max_len:
        return text[:max_len] + "...[truncated]"
    return text


class EvidenceExtractor:
    """
    Extracts structured, exception-specific evidence packages across progressive levels.
    Enforces record limits and token budgets before passing evidence to the LLM.
    """

    @staticmethod
    def extract_level_1(db: Session, exception_record: ExceptionRecord) -> Dict[str, Any]:
        """
        LEVEL 1 — MINIMAL EVIDENCE:
        Extracts only directly linked transaction records for the exception.
        """
        order_id = exception_record.order_id
        payment_id = exception_record.payment_id
        settlement_id = exception_record.settlement_id
        exc_type = exception_record.exception_type

        order = db.query(Order).filter(Order.order_id == order_id).first() if order_id else None
        
        # Payment lookup (by order_id if available, or direct payment_id)
        if order_id:
            payments = db.query(Payment).filter(Payment.order_id == order_id).all()
        elif payment_id:
            payments = db.query(Payment).filter(Payment.payment_id == payment_id).all()
        else:
            payments = []

        payment_ids = [p.payment_id for p in payments if p.payment_id]

        # Settlement lookup (by payment_ids or direct settlement_id)
        if payment_ids:
            settlements = db.query(Settlement).filter(Settlement.payment_id.in_(payment_ids)).all()
        elif settlement_id:
            settlements = db.query(Settlement).filter(Settlement.settlement_id == settlement_id).all()
        else:
            settlements = []

        # Exception-specific tailored payload construction
        payload: Dict[str, Any] = {
            "evidence_level": "LEVEL 1",
            "exception_type": exc_type,
            "order_id": order_id,
            "payment_id": payment_ids[0] if payment_ids else payment_id,
            "settlement_id": settlements[0].settlement_id if settlements else settlement_id,
            "order": _sanitize_record(order) if order else None,
            "payments": [_sanitize_record(p) for p in payments],
            "settlements": [_sanitize_record(s) for s in settlements],
            "summary_metrics": {
                "order_amount": order.amount if order else 0.0,
                "payment_total_amount": sum(p.amount for p in payments),
                "payment_total_fee": sum(p.fee for p in payments),
                "settlement_total_gross": sum(s.gross_amount for s in settlements),
                "settlement_total_net": sum(s.net_amount for s in settlements),
                "settlement_total_fee": sum(s.fee_deducted for s in settlements),
                "deterministic_difference": exception_record.difference or 0.0,
            },
            "exception_specific_context": EvidenceExtractor._build_exception_context(
                exc_type=exc_type,
                order=order,
                payments=payments,
                settlements=settlements,
                exception_record=exception_record,
            ),
        }

        return EvidenceExtractor.apply_payload_budget(payload)

    @staticmethod
    def _build_exception_context(
        exc_type: str,
        order: Optional[Order],
        payments: List[Payment],
        settlements: List[Settlement],
        exception_record: ExceptionRecord,
    ) -> Dict[str, Any]:
        """Builds exception-specific context based on deterministic exception type."""
        ctx: Dict[str, Any] = {"exception_type": exc_type}

        if exc_type == "MISSING_PAYMENT":
            ctx.update({
                "payment_found": len(payments) > 0,
                "settlement_found": len(settlements) > 0,
                "order_status": order.status if order else "UNKNOWN",
                "order_amount": order.amount if order else 0.0,
                "expected_payment_id": f"PAY-{order.order_id}" if order else None,
            })

        elif exc_type == "AMOUNT_MISMATCH":
            order_amt = order.amount if order else 0.0
            pay_amt = sum(p.amount for p in payments)
            settle_gross = sum(s.gross_amount for s in settlements)
            ctx.update({
                "order_amount": order_amt,
                "payment_amount": pay_amt,
                "settlement_gross": settle_gross,
                "order_vs_payment_diff": round(order_amt - pay_amt, 4),
                "payment_vs_settlement_diff": round(pay_amt - settle_gross, 4),
                "payment_status": payments[0].status if payments else None,
            })

        elif exc_type == "FEE_DISCREPANCY":
            pay_fee = sum(p.fee for p in payments)
            settle_fee = sum(s.fee_deducted for s in settlements)
            ctx.update({
                "payment_amount": sum(p.amount for p in payments),
                "payment_fee": pay_fee,
                "settlement_fee": settle_fee,
                "fee_difference": round(pay_fee - settle_fee, 4),
                "gateway": payments[0].gateway if payments else None,
                "settlement_net": sum(s.net_amount for s in settlements),
            })

        elif exc_type == "DUPLICATE_PAYMENT":
            ctx.update({
                "payment_count": len(payments),
                "payments": [
                    {
                        "payment_id": p.payment_id,
                        "amount": p.amount,
                        "timestamp": p.created_at.isoformat() if p.created_at else None,
                        "gateway": p.gateway,
                        "status": p.status,
                    }
                    for p in payments
                ],
                "duplicate_detected": len(payments) > 1,
            })

        elif exc_type == "TIMING_DELAY":
            order_time = order.created_at if order else None
            payment_time = payments[0].created_at if payments else None
            settlement_time = settlements[0].settlement_date if settlements else None

            delay_days = None
            if payment_time and settlement_time:
                p_date = payment_time.date() if isinstance(payment_time, datetime) else payment_time
                s_date = settlement_time.date() if isinstance(settlement_time, datetime) else settlement_time
                delay_days = (s_date - p_date).days

            ctx.update({
                "order_time": order_time.isoformat() if order_time else None,
                "payment_time": payment_time.isoformat() if payment_time else None,
                "settlement_date": settlement_time.isoformat() if settlement_time else None,
                "delay_days": delay_days,
                "threshold_window_days": settings.SETTLEMENT_WINDOW_DAYS,
            })

        elif exc_type == "UNMATCHED_SETTLEMENT":
            settle = settlements[0] if settlements else None
            ctx.update({
                "settlement_id": settle.settlement_id if settle else exception_record.settlement_id,
                "payout_reference": settle.payout_reference if settle else None,
                "gross_amount": settle.gross_amount if settle else 0.0,
                "net_amount": settle.net_amount if settle else 0.0,
                "matched_payment": len(payments) > 0,
                "matched_order": order is not None,
            })

        elif exc_type == "UNACCOUNTED_REFUND":
            refunded_payments = [p for p in payments if (p.status or "").upper() == "REFUNDED"]
            ctx.update({
                "order_amount": order.amount if order else 0.0,
                "refunded_payment_count": len(refunded_payments),
                "total_refunded_amount": sum(p.amount for p in refunded_payments),
                "refund_details": [
                    {"payment_id": p.payment_id, "amount": p.amount, "status": p.status}
                    for p in refunded_payments
                ],
            })

        else:
            ctx.update({
                "details": _truncate_text(exception_record.details),
                "expected_value": exception_record.expected_value,
                "actual_value": exception_record.actual_value,
            })

        return ctx

    @staticmethod
    def extract_level_2(db: Session, exception_record: ExceptionRecord, level1_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        LEVEL 2 — RELATED EVIDENCE:
        Adds merchant transaction history, nearby transactions (±3 days), and related gateway records.
        Bounded by MAX_RELATED_RECORDS.
        """
        evidence = dict(level1_evidence)
        evidence["evidence_level"] = "LEVEL 2"
        order_id = exception_record.order_id

        order = db.query(Order).filter(Order.order_id == order_id).first() if order_id else None
        related_orders = []
        related_payments = []

        if order and order.merchant_id:
            window_start = (order.created_at or datetime.utcnow()) - timedelta(days=3)
            window_end = (order.created_at or datetime.utcnow()) + timedelta(days=3)

            merchant_orders = (
                db.query(Order)
                .filter(
                    Order.merchant_id == order.merchant_id,
                    Order.order_id != order.order_id,
                    Order.created_at >= window_start,
                    Order.created_at <= window_end,
                )
                .limit(settings.MAX_RELATED_RECORDS)
                .all()
            )
            related_orders = [_sanitize_record(o) for o in merchant_orders]

            order_ids = [o.order_id for o in merchant_orders]
            if order_ids:
                merchant_payments = (
                    db.query(Payment)
                    .filter(Payment.order_id.in_(order_ids))
                    .limit(settings.MAX_RELATED_RECORDS)
                    .all()
                )
                related_payments = [_sanitize_record(p) for p in merchant_payments]

        evidence["related_context"] = {
            "merchant_id": order.merchant_id if order else None,
            "nearby_orders_count": len(related_orders),
            "nearby_orders": related_orders[:settings.MAX_RELATED_RECORDS],
            "nearby_payments": related_payments[:settings.MAX_RELATED_RECORDS],
        }

        return EvidenceExtractor.apply_payload_budget(evidence)

    @staticmethod
    def extract_level_3(db: Session, exception_record: ExceptionRecord, level2_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        LEVEL 3 — EXTENDED EVIDENCE:
        Adds historical exception patterns for same merchant/customer and settlement batch history.
        Bounded by MAX_EXTENDED_RECORDS.
        """
        evidence = dict(level2_evidence)
        evidence["evidence_level"] = "LEVEL 3"

        order_id = exception_record.order_id
        order = db.query(Order).filter(Order.order_id == order_id).first() if order_id else None

        historical_exceptions = []
        if order and order.merchant_id:
            past_excs = (
                db.query(ExceptionRecord)
                .join(Order, ExceptionRecord.order_id == Order.order_id)
                .filter(
                    Order.merchant_id == order.merchant_id,
                    ExceptionRecord.id != exception_record.id,
                )
                .limit(settings.MAX_EXTENDED_RECORDS)
                .all()
            )
            historical_exceptions = [
                {
                    "exception_type": e.exception_type,
                    "severity": e.severity,
                    "status": e.status,
                    "order_id": e.order_id,
                }
                for e in past_excs
            ]

        evidence["extended_context"] = {
            "historical_exceptions_count": len(historical_exceptions),
            "historical_merchant_exceptions": historical_exceptions[:settings.MAX_EXTENDED_RECORDS],
        }

        return EvidenceExtractor.apply_payload_budget(evidence)

    @staticmethod
    def apply_payload_budget(evidence: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates payload size, truncates excessive fields, caps records count,
        and ensures prompt budget is respected.
        """
        records_count = 0
        if evidence.get("order"):
            records_count += 1
        records_count += len(evidence.get("payments", []))
        records_count += len(evidence.get("settlements", []))
        
        rel_ctx = evidence.get("related_context", {})
        records_count += len(rel_ctx.get("nearby_orders", []))
        records_count += len(rel_ctx.get("nearby_payments", []))

        ext_ctx = evidence.get("extended_context", {})
        records_count += len(ext_ctx.get("historical_merchant_exceptions", []))

        evidence["evidence_records_count"] = records_count

        serialized = json.dumps(evidence)
        if len(serialized) > settings.MAX_PROMPT_LENGTH:
            logger.warning(
                f"Evidence payload size ({len(serialized)} chars) exceeds MAX_PROMPT_LENGTH ({settings.MAX_PROMPT_LENGTH}). Truncating."
            )
            if "extended_context" in evidence:
                evidence["extended_context"] = {"truncated": True, "notice": "Extended context removed due to size budget."}
            elif "related_context" in evidence:
                evidence["related_context"] = {"truncated": True, "notice": "Related context truncated due to size budget."}

        return evidence

    @staticmethod
    def compute_evidence_hash(evidence: Dict[str, Any]) -> str:
        """Computes deterministic SHA256 hash of key evidence fields for caching."""
        relevant = {
            "exception_type": evidence.get("exception_type"),
            "order_id": evidence.get("order_id"),
            "summary_metrics": evidence.get("summary_metrics"),
            "exception_specific_context": evidence.get("exception_specific_context"),
        }
        raw_bytes = json.dumps(relevant, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()
