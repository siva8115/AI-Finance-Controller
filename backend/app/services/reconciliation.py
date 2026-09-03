import json
import time
import uuid
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.config import settings
from app.models.base import Base
from app.models.financial import Order, Payment, Settlement, ReconciliationRun, ExceptionRecord, ReconciliationResult


def to_decimal(val: Optional[float]) -> Decimal:
    """Converts a float or int value safely to a 2-decimal Decimal."""
    if val is None:
        return Decimal("0.00")
    return Decimal(str(val)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def monetary_equals(val1: Optional[float], val2: Optional[float], tolerance: float = 0.01) -> bool:
    """Safely compares two monetary values within a given tolerance threshold."""
    if val1 is None or val2 is None:
        return False
    d1 = to_decimal(val1)
    d2 = to_decimal(val2)
    tol = Decimal(str(tolerance))
    return abs(d1 - d2) <= tol


def monetary_diff(val1: Optional[float], val2: Optional[float]) -> float:
    """Calculates difference (val1 - val2) as a float rounded to 2 decimals."""
    d1 = to_decimal(val1)
    d2 = to_decimal(val2)
    return float(d1 - d2)


def calculate_contracted_fee(amount: float, gateway: str) -> float:
    """Calculates contracted gateway fees based on gateway specific pricing schedules."""
    if gateway == "Stripe":
        fee = amount * 0.029 + 0.30
    elif gateway == "PayPal":
        fee = amount * 0.034 + 0.49
    elif gateway == "Adyen":
        fee = amount * 0.025 + 0.20
    else:
        fee = 0.0
    return round(fee, 2)



class MultiWayReconciliationEngine:
    """Deterministic 3-Way Reconciliation Engine (Order -> Payment -> Settlement)."""

    def __init__(self, settlement_window_days: Optional[int] = None, monetary_tolerance: Optional[float] = None):
        self.settlement_window_days = settlement_window_days if settlement_window_days is not None else settings.SETTLEMENT_WINDOW_DAYS
        self.monetary_tolerance = monetary_tolerance if monetary_tolerance is not None else settings.MONETARY_TOLERANCE

    def reconcile_single_order(
        self,
        run_id: str,
        order: Order,
        payments: List[Payment],
        settlements_by_payment: Dict[str, List[Settlement]],
    ) -> Tuple[ReconciliationResult, List[ExceptionRecord]]:
        """Reconciles a single order against its payments and settlements."""
        exception_types: List[str] = []
        exception_records: List[ExceptionRecord] = []
        explanations: List[str] = []
        recommended_actions: List[str] = []

        payment_ids = [p.payment_id for p in payments]
        all_settlements: List[Settlement] = []
        for p_id in payment_ids:
            all_settlements.extend(settlements_by_payment.get(p_id, []))
        settlement_ids = [s.settlement_id for s in all_settlements]

        # Calculate aggregations / reference amounts
        order_amount = order.amount
        payment_amount = sum(p.amount for p in payments) if payments else 0.0
        payment_fee = sum(p.fee for p in payments) if payments else 0.0

        settlement_gross = sum(s.gross_amount for s in all_settlements) if all_settlements else 0.0
        settlement_net = sum(s.net_amount for s in all_settlements) if all_settlements else 0.0
        settlement_fee = sum(s.fee_deducted for s in all_settlements) if all_settlements else 0.0

        amount_difference = monetary_diff(order_amount, payment_amount)
        settlement_difference = monetary_diff(payment_amount, settlement_gross)

        # Priority Rule 1: Missing Payment Detection
        if not payments:
            exc_type = "MISSING_PAYMENT"
            exception_types.append(exc_type)
            explanations.append(f"Order {order.order_id} has no corresponding payment gateway record.")
            recommended_actions.append("Verify payment gateway logs or check for incomplete customer checkout.")
            exception_records.append(
                ExceptionRecord(
                    run_id=run_id,
                    order_id=order.order_id,
                    payment_id=None,
                    settlement_id=None,
                    exception_type=exc_type,
                    severity="HIGH",
                    status="DETECTED",
                    expected_value=f"${order_amount:.2f}",
                    actual_value="NO_PAYMENT",
                    difference=order_amount,
                    details=f"Order {order.order_id} recorded in internal system for ${order_amount:.2f}, but missing from gateway payments.",
                )
            )

        # Priority Rule 2: Duplicate Payment Detection
        if len(payments) > 1:
            exc_type = "DUPLICATE_PAYMENT"
            exception_types.append(exc_type)
            dup_ids = ", ".join(payment_ids)
            explanations.append(f"Order {order.order_id} has {len(payments)} payment transactions recorded: {dup_ids}.")
            recommended_actions.append("Inspect gateway logs for duplicate charge and process refund if customer was double charged.")
            for p in payments[1:]:
                exception_records.append(
                    ExceptionRecord(
                        run_id=run_id,
                        order_id=order.order_id,
                        payment_id=p.payment_id,
                        settlement_id=None,
                        exception_type=exc_type,
                        severity="HIGH",
                        status="DETECTED",
                        expected_value="1 payment record",
                        actual_value=f"{len(payments)} payment records ({dup_ids})",
                        difference=p.amount,
                        details=f"Duplicate payment transaction {p.payment_id} recorded for order {order.order_id}.",
                    )
                )

        # Priority Rule 3: Payment Status & Refund Consistency Validation
        for p in payments:
            if p.status == "REFUNDED" and order.status == "COMPLETED":
                exc_type = "UNACCOUNTED_REFUND"
                if exc_type not in exception_types:
                    exception_types.append(exc_type)
                    explanations.append(f"Payment {p.payment_id} is REFUNDED on gateway, but order {order.order_id} remains COMPLETED.")
                    recommended_actions.append("Update internal order status to REFUNDED or trigger accounting adjustment.")
                exception_records.append(
                    ExceptionRecord(
                        run_id=run_id,
                        order_id=order.order_id,
                        payment_id=p.payment_id,
                        settlement_id=None,
                        exception_type=exc_type,
                        severity="HIGH",
                        status="DETECTED",
                        expected_value="REFUNDED (or cancelled order)",
                        actual_value=f"Order: {order.status}, Payment: {p.status}",
                        difference=p.amount,
                        details=f"Gateway payment {p.payment_id} was refunded, but internal order {order.order_id} status is {order.status}.",
                    )
                )

        # Priority Rule 4: Payment Amount Validation
        if payments and not monetary_equals(order_amount, payment_amount, self.monetary_tolerance):
            exc_type = "AMOUNT_MISMATCH"
            if exc_type not in exception_types:
                exception_types.append(exc_type)
                diff = monetary_diff(order_amount, payment_amount)
                explanations.append(f"Order amount ${order_amount:.2f} does not match captured payment amount ${payment_amount:.2f} (diff: ${diff:+.2f}).")
                recommended_actions.append("Verify applied promo codes, partial charges, or manual price adjustments.")
            for p in payments:
                exception_records.append(
                    ExceptionRecord(
                        run_id=run_id,
                        order_id=order.order_id,
                        payment_id=p.payment_id,
                        settlement_id=None,
                        exception_type=exc_type,
                        severity="HIGH",
                        status="DETECTED",
                        expected_value=f"${order_amount:.2f}",
                        actual_value=f"${p.amount:.2f}",
                        difference=monetary_diff(order_amount, p.amount),
                        details=f"Order amount ${order_amount:.2f} differs from payment {p.payment_id} amount ${p.amount:.2f}.",
                    )
                )

        # Priority Rule 5: Settlement Existence Validation
        if payments:
            for p in payments:
                p_settlements = settlements_by_payment.get(p.payment_id, [])
                if p.status != "REFUNDED" and not p_settlements:
                    exc_type = "UNMATCHED_SETTLEMENT"
                    if exc_type not in exception_types:
                        exception_types.append(exc_type)
                        explanations.append(f"Payment {p.payment_id} was captured, but no bank settlement record was found.")
                        recommended_actions.append("Contact payment gateway support to confirm payout processing status.")
                    exception_records.append(
                        ExceptionRecord(
                            run_id=run_id,
                            order_id=order.order_id,
                            payment_id=p.payment_id,
                            settlement_id=None,
                            exception_type=exc_type,
                            severity="HIGH",
                            status="DETECTED",
                            expected_value="Settlement record present",
                            actual_value="NO_SETTLEMENT",
                            difference=p.amount,
                            details=f"Payment {p.payment_id} captured for ${p.amount:.2f} has no corresponding bank payout settlement.",
                        )
                    )

        # Priority Rule 6: Settlement Fee Validation
        if payments:
            for p in payments:
                contracted_fee = calculate_contracted_fee(p.amount, p.gateway)
                p_settlements = settlements_by_payment.get(p.payment_id, [])
                
                # Check payment fee against contracted fee rate
                if not monetary_equals(p.fee, contracted_fee, self.monetary_tolerance):
                    exc_type = "FEE_DISCREPANCY"
                    fee_diff = monetary_diff(p.fee, contracted_fee)
                    if exc_type not in exception_types:
                        exception_types.append(exc_type)
                        explanations.append(f"Gateway fee ${p.fee:.2f} differs from contracted fee ${contracted_fee:.2f} (diff: ${fee_diff:+.2f}).")
                        recommended_actions.append("Audit payment gateway fee schedule and contract rates for potential overcharge.")
                    exception_records.append(
                        ExceptionRecord(
                            run_id=run_id,
                            order_id=order.order_id,
                            payment_id=p.payment_id,
                            settlement_id=None,
                            exception_type=exc_type,
                            severity="MEDIUM",
                            status="DETECTED",
                            expected_value=f"${contracted_fee:.2f}",
                            actual_value=f"${p.fee:.2f}",
                            difference=fee_diff,
                            details=f"Contracted fee is ${contracted_fee:.2f}, but gateway {p.gateway} charged ${p.fee:.2f}.",
                        )
                    )
                
                # Check settlement fee against payment fee
                for s in p_settlements:
                    if not monetary_equals(p.fee, s.fee_deducted, self.monetary_tolerance):
                        exc_type = "FEE_DISCREPANCY"
                        fee_diff = monetary_diff(s.fee_deducted, p.fee)
                        if exc_type not in exception_types:
                            exception_types.append(exc_type)
                            explanations.append(f"Settlement fee ${s.fee_deducted:.2f} differs from expected gateway fee ${p.fee:.2f} (diff: ${fee_diff:+.2f}).")
                            recommended_actions.append("Audit payment gateway fee schedule and contract rates for potential overcharge.")
                        exception_records.append(
                            ExceptionRecord(
                                run_id=run_id,
                                order_id=order.order_id,
                                payment_id=p.payment_id,
                                settlement_id=s.settlement_id,
                                exception_type=exc_type,
                                severity="MEDIUM",
                                status="DETECTED",
                                expected_value=f"${p.fee:.2f}",
                                actual_value=f"${s.fee_deducted:.2f}",
                                difference=fee_diff,
                                details=f"Gateway expected fee ${p.fee:.2f}, but settlement {s.settlement_id} deducted ${s.fee_deducted:.2f}.",
                            )
                        )


        # Priority Rule 7: Settlement Timing Validation
        if payments and all_settlements:
            for p in payments:
                p_settlements = settlements_by_payment.get(p.payment_id, [])
                for s in p_settlements:
                    if p.timestamp and s.settlement_date:
                        delay_days = (s.settlement_date - p.timestamp).days
                        if delay_days > self.settlement_window_days:
                            exc_type = "TIMING_DELAY"
                            if exc_type not in exception_types:
                                exception_types.append(exc_type)
                                explanations.append(f"Settlement {s.settlement_id} took {delay_days} days (exceeds max window of {self.settlement_window_days} days).")
                                recommended_actions.append("Review payment provider payout schedules and holding periods.")
                            exception_records.append(
                                ExceptionRecord(
                                    run_id=run_id,
                                    order_id=order.order_id,
                                    payment_id=p.payment_id,
                                    settlement_id=s.settlement_id,
                                    exception_type=exc_type,
                                    severity="MEDIUM",
                                    status="DETECTED",
                                    expected_value=f"<= {self.settlement_window_days} days",
                                    actual_value=f"{delay_days} days",
                                    difference=float(delay_days),
                                    details=f"Settlement {s.settlement_id} processed {delay_days} days after payment timestamp.",
                                )
                            )

        # Final Match Determination
        reconciliation_status = "EXCEPTION" if exception_types else "MATCHED"
        if reconciliation_status == "MATCHED":
            explanations.append("Order, payment, and bank settlement records are fully reconciled with 0 anomalies.")
            recommended_actions.append("No action required. Reconciled successfully.")

        result = ReconciliationResult(
            run_id=run_id,
            order_id=order.order_id,
            payment_ids=json.dumps(payment_ids),
            settlement_ids=json.dumps(settlement_ids),
            reconciliation_status=reconciliation_status,
            exception_types=json.dumps(exception_types),
            order_amount=order_amount,
            payment_amount=payment_amount,
            settlement_gross_amount=settlement_gross,
            settlement_net_amount=settlement_net,
            payment_fee=payment_fee,
            settlement_fee=settlement_fee,
            amount_difference=amount_difference,
            settlement_difference=settlement_difference,
            match_method="DETERMINISTIC_3WAY",
            explanation=" | ".join(explanations),
            recommended_action=" | ".join(recommended_actions),
            checked_at=datetime.utcnow(),
        )

        return result, exception_records


class ReconciliationService:
    """Service orchestrator for running multi-way reconciliation jobs."""

    @staticmethod
    def run_reconciliation(
        db: Session,
        settlement_window_days: Optional[int] = None,
        monetary_tolerance: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Runs deterministic reconciliation across all orders in database."""
        # Ensure database tables exist
        Base.metadata.create_all(bind=db.get_bind())

        start_time = time.time()
        run_id = f"RUN-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        # Initialize ReconciliationRun record
        rec_run = ReconciliationRun(
            run_id=run_id,
            started_at=datetime.utcnow(),
            status="RUNNING",
            total_records=0,
            matched_count=0,
            exception_count=0,
            processing_time_seconds=0.0,
        )
        db.add(rec_run)
        db.commit()

        # Fetch all orders
        orders = db.query(Order).all()
        if not orders:
            rec_run.completed_at = datetime.utcnow()
            rec_run.status = "COMPLETED"
            rec_run.processing_time_seconds = time.time() - start_time
            db.commit()
            return {
                "run_id": run_id,
                "status": "COMPLETED",
                "total_records": 0,
                "matched": 0,
                "exceptions": 0,
                "processing_time_seconds": round(time.time() - start_time, 4),
                "started_at": rec_run.started_at.isoformat() if rec_run.started_at else None,
                "completed_at": rec_run.completed_at.isoformat() if rec_run.completed_at else None,
            }

        # Fetch all payments and settlements in memory for efficient lookup
        payments = db.query(Payment).all()
        payments_by_order: Dict[str, List[Payment]] = {}
        for p in payments:
            payments_by_order.setdefault(p.order_id, []).append(p)

        settlements = db.query(Settlement).all()
        settlements_by_payment: Dict[str, List[Settlement]] = {}
        for s in settlements:
            settlements_by_payment.setdefault(s.payment_id, []).append(s)

        engine = MultiWayReconciliationEngine(
            settlement_window_days=settlement_window_days,
            monetary_tolerance=monetary_tolerance,
        )

        matched_count = 0
        exception_count = 0
        all_results: List[ReconciliationResult] = []
        all_exceptions: List[ExceptionRecord] = []

        for order in orders:
            order_payments = payments_by_order.get(order.order_id, [])
            res, exc_records = engine.reconcile_single_order(
                run_id=run_id,
                order=order,
                payments=order_payments,
                settlements_by_payment=settlements_by_payment,
            )
            all_results.append(res)
            all_exceptions.extend(exc_records)

            if res.reconciliation_status == "MATCHED":
                matched_count += 1
            else:
                exception_count += 1

        # Bulk save results and exceptions
        db.add_all(all_results)
        db.add_all(all_exceptions)

        # Update run stats
        end_time = time.time()
        elapsed_seconds = end_time - start_time

        rec_run.completed_at = datetime.utcnow()
        rec_run.status = "COMPLETED"
        rec_run.total_records = len(orders)
        rec_run.matched_count = matched_count
        rec_run.exception_count = exception_count
        rec_run.processing_time_seconds = elapsed_seconds
        db.commit()

        return {
            "run_id": run_id,
            "status": "COMPLETED",
            "total_records": len(orders),
            "matched": matched_count,
            "exceptions": exception_count,
            "processing_time_seconds": round(elapsed_seconds, 4),
            "started_at": rec_run.started_at.isoformat() if rec_run.started_at else None,
            "completed_at": rec_run.completed_at.isoformat() if rec_run.completed_at else None,
        }

    @staticmethod
    def get_latest_summary(db: Session) -> Optional[Dict[str, Any]]:
        """Retrieves summary of the most recent reconciliation run."""
        latest_run = db.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()
        if not latest_run:
            return None
        return {
            "run_id": latest_run.run_id,
            "status": latest_run.status,
            "total_records": latest_run.total_records,
            "matched": latest_run.matched_count,
            "exceptions": latest_run.exception_count,
            "processing_time_seconds": round(latest_run.processing_time_seconds or 0.0, 4),
            "started_at": latest_run.started_at.isoformat() if latest_run.started_at else None,
            "completed_at": latest_run.completed_at.isoformat() if latest_run.completed_at else None,
        }

    @staticmethod
    def get_results(
        db: Session,
        run_id: Optional[str] = None,
        status: Optional[str] = None,
        exception_type: Optional[str] = None,
        order_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries reconciliation results with optional filters."""
        query = db.query(ReconciliationResult)

        if run_id:
            query = query.filter(ReconciliationResult.run_id == run_id)
        else:
            # Default to latest run if no run_id specified
            latest_run = db.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()
            if latest_run:
                query = query.filter(ReconciliationResult.run_id == latest_run.run_id)

        if status:
            query = query.filter(ReconciliationResult.reconciliation_status == status.upper())

        if order_id:
            query = query.filter(ReconciliationResult.order_id == order_id)

        results = query.all()

        output = []
        for r in results:
            item = r.to_dict()
            if exception_type:
                if exception_type.upper() not in item.get("exception_types", []):
                    continue
            output.append(item)
        return output

    @staticmethod
    def get_exceptions(
        db: Session,
        run_id: Optional[str] = None,
        exception_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Queries exception records with optional filters."""
        query = db.query(ExceptionRecord)

        if run_id:
            query = query.filter(ExceptionRecord.run_id == run_id)
        else:
            latest_run = db.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()
            if latest_run:
                query = query.filter(ExceptionRecord.run_id == latest_run.run_id)

        if exception_type:
            query = query.filter(ExceptionRecord.exception_type == exception_type.upper())

        if status:
            query = query.filter(ExceptionRecord.status == status.upper())

        exceptions = query.all()
        return [e.to_dict() for e in exceptions]
