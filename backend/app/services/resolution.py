"""
Resolution Orchestrator — Phase 6
Deterministic service that translates an AI investigation into a final Resolution record.

Architecture:
    ExceptionRecord + AIInvestigation
            ↓
    ResolutionOrchestrator.resolve()
            ↓
    Deterministic Policy (safety gates re-evaluated independently)
            ↓
    Resolution  +  ResolutionEvent (audit)
            ↓
    Human Review Queue  OR  AUTO_RESOLVED

Rules:
  - The orchestrator never trusts AI output blindly.
  - It re-evaluates every safety condition from the AIInvestigation snapshot.
  - Financial records (Order, Payment, Settlement, ReconciliationResult) are NEVER modified.
  - Resolution status is operational metadata only.
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.financial import (
    ExceptionRecord, AIInvestigation, Resolution, ResolutionEvent,
    Order, Payment, Settlement, ReconciliationResult,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Resolution statuses
# ---------------------------------------------------------------------------
STATUS_PENDING       = "PENDING_INVESTIGATION"
STATUS_AUTO          = "AUTO_RESOLVED"
STATUS_REVIEW        = "REVIEW_RECOMMENDED"
STATUS_HUMAN         = "HUMAN_REVIEW_REQUIRED"
STATUS_APPROVED      = "APPROVED_BY_HUMAN"
STATUS_REJECTED      = "REJECTED_BY_HUMAN"
STATUS_UNRESOLVED    = "UNRESOLVED"
STATUS_AI_FAILED     = "AI_FAILED"

# Actor types for the audit trail
ACTOR_SYSTEM  = "SYSTEM"
ACTOR_HUMAN   = "HUMAN"

# ---------------------------------------------------------------------------
# Priority scoring (lower number = shown first in review queue)
# ---------------------------------------------------------------------------
PRIORITY_VERY_HIGH = 10   # Large monetary impact
PRIORITY_HIGH      = 20   # Refund / negative settlement
PRIORITY_MEDIUM    = 40   # Low AI confidence / disagreement
PRIORITY_LOW       = 60   # Medium confidence
PRIORITY_DEFAULT   = 80   # Everything else


class ResolutionOrchestrator:
    """
    Deterministic policy engine.  Reads from AI investigation + evidence, writes Resolution.
    Never modifies financial records.
    """

    # -------------------------------------------------------------------
    # Priority Scorer
    # -------------------------------------------------------------------
    @staticmethod
    def _compute_priority(
        investigation: AIInvestigation,
        amount_diff: Optional[float],
        exception_type: str,
        payments: List[Payment],
        settlements: List[Settlement],
    ) -> Tuple[int, str]:
        """Returns (priority_score, priority_reason)."""
        flags = json.loads(investigation.safety_flags) if investigation.safety_flags else []

        if amount_diff is not None and abs(amount_diff) >= 100.0:
            return 10, f"High financial impact (${abs(amount_diff):.2f} difference)"

        if investigation.confidence_level == "LOW" or investigation.effective_confidence < 0.60:
            return 20, "Low confidence"

        has_refund = any(p.status == "REFUNDED" for p in payments) or exception_type == "UNACCOUNTED_REFUND" or "REFUND_PRESENT" in flags
        if has_refund:
            return 30, "Refund present"

        has_neg_settlement = any(s.gross_amount < 0 or s.net_amount < 0 for s in settlements) or "NEGATIVE_SETTLEMENT" in flags
        if has_neg_settlement:
            return 40, "Negative settlement"

        if not investigation.ai_classification_matches_deterministic or "AI_DETERMINISTIC_DISAGREEMENT" in flags:
            return 50, "AI/deterministic disagreement"

        has_missing_records = len(payments) == 0 or len(settlements) == 0 or exception_type in ("MISSING_PAYMENT", "UNMATCHED_SETTLEMENT") or "MISSING_PAYMENT_RECORD" in flags or "MISSING_SETTLEMENT_RECORD" in flags
        if has_missing_records:
            return 60, "Missing records"

        return 70, f"Other exception: {exception_type}"

    # -------------------------------------------------------------------
    # Safety Policy — re-evaluated independently from investigation status
    # -------------------------------------------------------------------
    @staticmethod
    def _determine_resolution_status(
        investigation: AIInvestigation,
        exception_type: str,
        payments: List[Payment],
        settlements: List[Settlement],
    ) -> Tuple[str, str]:
        """
        Returns (resolution_status, resolution_reason).

        AUTO_RESOLVED is only permitted when ALL conditions are met:
          1. AI investigation succeeded (not AI_FAILED)
          2. AI confidence (raw) >= HIGH threshold
          3. effective_confidence >= HIGH threshold
          4. No safety flags
          5. AI classification matches deterministic type
          6. requires_human_review == False
          7. no refund ambiguity, negative settlement, missing payments/settlements, duplicate payments
        """
        flags = json.loads(investigation.safety_flags) if investigation.safety_flags else []
        inv_status = investigation.investigation_status

        # AI failed — cannot auto-resolve
        if inv_status == "AI_FAILED" or "AI_FAILED" in flags:
            return STATUS_AI_FAILED, "AI investigation failed — routing to human review."

        # Independent Safety Gate Checks on actual DB records
        has_refund = any(p.status == "REFUNDED" for p in payments) or exception_type == "UNACCOUNTED_REFUND"
        has_neg_settlement = any(s.gross_amount < 0 or s.net_amount < 0 for s in settlements)
        has_missing_pay = len(payments) == 0 or exception_type == "MISSING_PAYMENT"
        has_missing_set = (len(payments) > 0 and len(settlements) == 0) or exception_type == "UNMATCHED_SETTLEMENT"
        has_dup_payment = len(payments) > 1 or exception_type == "DUPLICATE_PAYMENT"

        evidence_gaps = json.loads(investigation.evidence_gaps) if investigation.evidence_gaps else []
        evidence_facts = json.loads(investigation.evidence_facts) if investigation.evidence_facts else []
        has_evidence_gaps = len(evidence_gaps) > 0 or len(evidence_facts) == 0

        safety_blocks = []
        if has_refund:
            safety_blocks.append("Refund present or unaccounted refund")
        if has_neg_settlement:
            safety_blocks.append("Negative settlement present")
        if has_missing_pay:
            safety_blocks.append("Missing payment record")
        if has_missing_set:
            safety_blocks.append("Missing settlement record")
        if has_dup_payment:
            safety_blocks.append("Duplicate payment present")
        if has_evidence_gaps:
            safety_blocks.append("Missing evidence or evidence gaps present")

        # Any independent safety block forced to HUMAN_REVIEW_REQUIRED
        if safety_blocks:
            return STATUS_HUMAN, f"Human review required due to: {', '.join(safety_blocks)}"

        # Any safety flag present from AI investigation → human review
        if flags:
            return STATUS_HUMAN, f"Safety flags present: {', '.join(flags)}"

        # AI disagrees with deterministic type
        if not investigation.ai_classification_matches_deterministic:
            return STATUS_HUMAN, "AI classification does not match deterministic exception type."

        # Human review explicitly required by AI
        if investigation.requires_human_review:
            eff = investigation.effective_confidence or 0.0
            if eff >= settings.CONFIDENCE_MEDIUM_THRESHOLD:
                return STATUS_REVIEW, "AI recommends human review; medium confidence."
            return STATUS_HUMAN, "AI recommends human review; low confidence."

        # Check effective confidence thresholds
        eff = investigation.effective_confidence or 0.0
        raw = investigation.ai_confidence or 0.0

        if (
            eff >= settings.CONFIDENCE_HIGH_THRESHOLD
            and raw >= settings.CONFIDENCE_HIGH_THRESHOLD
            and not flags
            and investigation.ai_classification_matches_deterministic
            and not investigation.requires_human_review
        ):
            return STATUS_AUTO, "High confidence, no safety flags, AI/deterministic agreement."

        if eff >= settings.CONFIDENCE_MEDIUM_THRESHOLD:
            return STATUS_REVIEW, "Medium effective confidence — review recommended."

        return STATUS_HUMAN, "Low effective confidence — human review required."

    # -------------------------------------------------------------------
    # Audit Event Emitter
    # -------------------------------------------------------------------
    @staticmethod
    def _emit_event(
        db: Session,
        resolution: Resolution,
        previous_status: Optional[str],
        new_status: str,
        actor_type: str,
        actor_id: str,
        reason: Optional[str],
    ) -> ResolutionEvent:
        event = ResolutionEvent(
            event_id=f"EVT-{uuid.uuid4().hex[:8].upper()}",
            resolution_id=resolution.resolution_id,
            previous_status=previous_status,
            new_status=new_status,
            actor_type=actor_type,
            actor_id=actor_id,
            reason=reason,
            created_at=datetime.utcnow(),
        )
        db.add(event)
        return event

    # -------------------------------------------------------------------
    # Resolve a Single Exception
    # -------------------------------------------------------------------
    @staticmethod
    def resolve_exception(
        db: Session,
        exception_id: int,
        investigation_id: Optional[str] = None,
    ) -> Resolution:
        """
        Creates (or returns existing) Resolution for a given ExceptionRecord.

        Idempotent: if a resolution already exists for this exception_id +
        reconciliation_run_id, it is returned without creating a duplicate.

        Financial records are NEVER modified.
        """
        exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == exception_id).first()
        if not exc:
            raise ValueError(f"ExceptionRecord {exception_id} not found.")

        # Idempotency check
        existing = (
            db.query(Resolution)
            .filter(
                Resolution.exception_id == exception_id,
                Resolution.reconciliation_run_id == exc.run_id,
            )
            .first()
        )
        if existing:
            return existing

        # Find the AI investigation to use
        if investigation_id:
            inv = (
                db.query(AIInvestigation)
                .filter(AIInvestigation.investigation_id == investigation_id)
                .first()
            )
        else:
            inv = (
                db.query(AIInvestigation)
                .filter(AIInvestigation.exception_id == exception_id)
                .order_by(AIInvestigation.id.desc())
                .first()
            )

        if not inv:
            raise ValueError(
                f"No AI investigation found for exception {exception_id}. "
                "Run AI investigation first."
            )

        # Find order/payments/settlements to independently verify safety conditions
        payments = db.query(Payment).filter(Payment.order_id == exc.order_id).all()
        payment_ids = [p.payment_id for p in payments]
        settlements = db.query(Settlement).filter(Settlement.payment_id.in_(payment_ids)).all() if payment_ids else []

        # Determine resolution status via policy
        resolution_status, resolution_reason = ResolutionOrchestrator._determine_resolution_status(
            inv, exc.exception_type, payments, settlements
        )

        # Gather monetary diff for priority calculation
        exc_diff = exc.difference

        # Compute priority
        priority, priority_reason = ResolutionOrchestrator._compute_priority(
            inv, exc_diff, exc.exception_type, payments, settlements
        )

        # human_review_required derived from status
        human_review = resolution_status not in (STATUS_AUTO,)

        resolved_by = None if human_review else ACTOR_SYSTEM

        resolution = Resolution(
            resolution_id=f"RES-{uuid.uuid4().hex[:8].upper()}",
            reconciliation_run_id=exc.run_id,
            order_id=exc.order_id,
            exception_id=exc.id,
            ai_investigation_id=inv.investigation_id,
            deterministic_exception_type=exc.exception_type,   # authoritative — never AI
            ai_classification=inv.ai_classification,
            resolution_status=resolution_status,
            resolution_reason=resolution_reason,
            confidence=inv.ai_confidence,
            effective_confidence=inv.effective_confidence,
            confidence_level=inv.confidence_level,
            safety_flags=inv.safety_flags,   # already a JSON string
            human_review_required=human_review,
            resolved_by=resolved_by,
            priority=priority,
            priority_reason=priority_reason,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(resolution)
        db.flush()  # get the resolution persisted so we can reference it in the event

        ResolutionOrchestrator._emit_event(
            db=db,
            resolution=resolution,
            previous_status=None,
            new_status=resolution_status,
            actor_type=ACTOR_SYSTEM,
            actor_id="ORCHESTRATOR",
            reason=resolution_reason,
        )
        db.commit()
        return resolution

    # -------------------------------------------------------------------
    # Human Approval
    # -------------------------------------------------------------------
    @staticmethod
    def approve(db: Session, resolution_id: str, notes: str) -> Resolution:
        res = db.query(Resolution).filter(Resolution.resolution_id == resolution_id).first()
        if not res:
            raise ValueError(f"Resolution {resolution_id} not found.")

        prev_status = res.resolution_status
        res.resolution_status = STATUS_APPROVED
        res.resolved_by = ACTOR_HUMAN
        res.resolution_notes = notes
        res.updated_at = datetime.utcnow()

        ResolutionOrchestrator._emit_event(
            db=db,
            resolution=res,
            previous_status=prev_status,
            new_status=STATUS_APPROVED,
            actor_type=ACTOR_HUMAN,
            actor_id="HUMAN_REVIEWER",
            reason=notes,
        )
        db.commit()
        return res

    # -------------------------------------------------------------------
    # Human Rejection
    # -------------------------------------------------------------------
    @staticmethod
    def reject(db: Session, resolution_id: str, notes: str) -> Resolution:
        res = db.query(Resolution).filter(Resolution.resolution_id == resolution_id).first()
        if not res:
            raise ValueError(f"Resolution {resolution_id} not found.")

        prev_status = res.resolution_status
        res.resolution_status = STATUS_REJECTED
        res.resolved_by = ACTOR_HUMAN
        res.resolution_notes = notes
        res.updated_at = datetime.utcnow()

        ResolutionOrchestrator._emit_event(
            db=db,
            resolution=res,
            previous_status=prev_status,
            new_status=STATUS_REJECTED,
            actor_type=ACTOR_HUMAN,
            actor_id="HUMAN_REVIEWER",
            reason=notes,
        )
        db.commit()
        return res

    # -------------------------------------------------------------------
    # Reopen / Unresolve
    # -------------------------------------------------------------------
    @staticmethod
    def unresolve(db: Session, resolution_id: str, reason: str) -> Resolution:
        res = db.query(Resolution).filter(Resolution.resolution_id == resolution_id).first()
        if not res:
            raise ValueError(f"Resolution {resolution_id} not found.")

        prev_status = res.resolution_status
        res.resolution_status = STATUS_UNRESOLVED
        res.resolved_by = None
        res.resolution_notes = reason
        res.updated_at = datetime.utcnow()

        ResolutionOrchestrator._emit_event(
            db=db,
            resolution=res,
            previous_status=prev_status,
            new_status=STATUS_UNRESOLVED,
            actor_type=ACTOR_HUMAN,
            actor_id="HUMAN_REVIEWER",
            reason=reason,
        )
        db.commit()
        return res

    # -------------------------------------------------------------------
    # Batch Resolution
    # -------------------------------------------------------------------
    @staticmethod
    def resolve_batch(
        db: Session,
        reconciliation_run_id: str,
        max_cases: int = 50,
    ) -> Dict[str, Any]:
        """
        Resolves up to max_cases exceptions that already have AI investigations.
        Skips exceptions that already have a Resolution (idempotency).
        """
        # Exceptions that have been AI investigated
        investigated_ids = {
            row.exception_id
            for row in db.query(AIInvestigation.exception_id)
            .filter(AIInvestigation.reconciliation_run_id == reconciliation_run_id)
            .all()
        }

        # Exceptions already resolved
        resolved_ids = {
            row.exception_id
            for row in db.query(Resolution.exception_id)
            .filter(Resolution.reconciliation_run_id == reconciliation_run_id)
            .all()
        }

        eligible_ids = list(investigated_ids - resolved_ids)[:max_cases]

        counts = {
            STATUS_AUTO: 0,
            STATUS_REVIEW: 0,
            STATUS_HUMAN: 0,
            STATUS_AI_FAILED: 0,
            STATUS_UNRESOLVED: 0,
        }

        for exc_id in eligible_ids:
            try:
                res = ResolutionOrchestrator.resolve_exception(db, exc_id)
                bucket = res.resolution_status
                if bucket in counts:
                    counts[bucket] += 1
                else:
                    counts[STATUS_UNRESOLVED] += 1
            except Exception as e:
                logger.error(f"Batch resolution failed for exception {exc_id}: {e}")
                counts[STATUS_UNRESOLVED] += 1

        return {
            "total_eligible": len(eligible_ids),
            "auto_resolved": counts[STATUS_AUTO],
            "review_recommended": counts[STATUS_REVIEW],
            "human_review_required": counts[STATUS_HUMAN],
            "ai_failed": counts[STATUS_AI_FAILED],
            "unresolved": counts[STATUS_UNRESOLVED],
        }

    # -------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------
    @staticmethod
    def get_summary(db: Session) -> Dict[str, Any]:
        from app.models.financial import ExceptionRecord, AIInvestigation, Resolution
        from sqlalchemy import func

        total_exceptions = db.query(func.count(ExceptionRecord.id)).scalar() or 0
        investigated = db.query(func.count(AIInvestigation.id)).scalar() or 0

        def _count(status: str) -> int:
            return (
                db.query(func.count(Resolution.id))
                .filter(Resolution.resolution_status == status)
                .scalar()
                or 0
            )

        auto_resolved       = _count(STATUS_AUTO)
        review_recommended  = _count(STATUS_REVIEW)
        human_review_req    = _count(STATUS_HUMAN)
        approved            = _count(STATUS_APPROVED)
        rejected            = _count(STATUS_REJECTED)
        unresolved          = _count(STATUS_UNRESOLVED)
        ai_failed           = _count(STATUS_AI_FAILED)

        total_resolved = auto_resolved + approved
        denom = total_exceptions or 1

        return {
            "total_exceptions": total_exceptions,
            "investigated": investigated,
            "auto_resolved": auto_resolved,
            "review_recommended": review_recommended,
            "human_review_required": human_review_req,
            "approved_by_human": approved,
            "rejected_by_human": rejected,
            "unresolved": unresolved,
            "ai_failed": ai_failed,
            "auto_resolution_rate": round(auto_resolved / denom, 4),
            "human_review_rate": round((human_review_req + review_recommended) / denom, 4),
            "unresolved_rate": round((unresolved + rejected) / denom, 4),
        }

    # -------------------------------------------------------------------
    # Review Queue
    # -------------------------------------------------------------------
    @staticmethod
    def get_review_queue(
        db: Session,
        resolution_status: Optional[str] = None,
        exception_type: Optional[str] = None,
        confidence_level: Optional[str] = None,
        reconciliation_run_id: Optional[str] = None,
    ) -> List[Resolution]:
        query = db.query(Resolution)

        if resolution_status:
            query = query.filter(Resolution.resolution_status == resolution_status)
        else:
            # Default: cases needing attention
            query = query.filter(
                Resolution.resolution_status.in_([
                    STATUS_HUMAN, STATUS_REVIEW, STATUS_UNRESOLVED, STATUS_AI_FAILED
                ])
            )

        if exception_type:
            query = query.filter(Resolution.deterministic_exception_type == exception_type)
        if confidence_level:
            query = query.filter(Resolution.confidence_level == confidence_level)
        if reconciliation_run_id:
            query = query.filter(Resolution.reconciliation_run_id == reconciliation_run_id)

        return query.order_by(Resolution.priority.asc(), Resolution.created_at.asc()).all()

    # -------------------------------------------------------------------
    # Enriched Queue Item (full context for review)
    # -------------------------------------------------------------------
    @staticmethod
    def get_queue_detail(db: Session, resolution_id: str) -> Dict[str, Any]:
        res = db.query(Resolution).filter(Resolution.resolution_id == resolution_id).first()
        if not res:
            raise ValueError(f"Resolution {resolution_id} not found.")

        exc = db.query(ExceptionRecord).filter(ExceptionRecord.id == res.exception_id).first()
        order = db.query(Order).filter(Order.order_id == res.order_id).first()
        payments = db.query(Payment).filter(Payment.order_id == res.order_id).all()
        payment_ids = [p.payment_id for p in payments]
        settlements = (
            db.query(Settlement).filter(Settlement.payment_id.in_(payment_ids)).all()
            if payment_ids else []
        )
        inv = (
            db.query(AIInvestigation)
            .filter(AIInvestigation.investigation_id == res.ai_investigation_id)
            .first()
            if res.ai_investigation_id else None
        )

        import json as _j
        return {
            "resolution": res.to_dict(),
            "order": order.to_dict() if order else None,
            "payments": [p.to_dict() for p in payments],
            "settlements": [s.to_dict() for s in settlements],
            "exception": exc.to_dict() if exc else None,
            "ai_investigation": inv.to_dict() if inv else None,
        }

    # -------------------------------------------------------------------
    # Audit Trail
    # -------------------------------------------------------------------
    @staticmethod
    def get_events(db: Session, resolution_id: str) -> List[ResolutionEvent]:
        return (
            db.query(ResolutionEvent)
            .filter(ResolutionEvent.resolution_id == resolution_id)
            .order_by(ResolutionEvent.created_at.asc())
            .all()
        )
