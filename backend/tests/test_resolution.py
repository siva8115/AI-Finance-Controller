import json
import pytest
from sqlalchemy.orm import Session
from tests.conftest import TestingSessionLocal, client
from app.models.financial import (
    Order, Payment, Settlement, ExceptionRecord, AIInvestigation,
    Resolution, ResolutionEvent, ReconciliationResult
)
from app.services.resolution import ResolutionOrchestrator


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_case(
    db: Session,
    order_id: str,
    exception_type: str = "AMOUNT_MISMATCH",
    ai_classification: str = "AMOUNT_MISMATCH",
    ai_confidence: float = 0.95,
    effective_confidence: float = 0.95,
    confidence_level: str = "HIGH",
    safety_flags: list = None,
    requires_human_review: bool = False,
    investigation_status: str = "AUTO_RESOLVED",
    payment_status: str = "CAPTURED",
    gross_amount: float = 100.0,
    net_amount: float = 95.0,
    payments_count: int = 1,
    settlements_count: int = 1,
) -> ExceptionRecord:
    # 1. Order
    order = Order(order_id=order_id, customer_id="CUST-999", amount=100.0, status="COMPLETED")
    db.add(order)

    # 2. Payments
    payments = []
    for idx in range(payments_count):
        payment_id = f"PAY-{order_id}-{idx}" if payments_count > 1 else f"PAY-{order_id}"
        payment = Payment(
            payment_id=payment_id,
            order_id=order_id,
            gateway="Stripe",
            amount=100.0,
            fee=5.0,
            status=payment_status,
        )
        db.add(payment)
        payments.append(payment)

    # 3. Settlements
    settlements = []
    if payments_count > 0:
        for idx in range(settlements_count):
            settlement_id = f"SET-{order_id}-{idx}" if settlements_count > 1 else f"SET-{order_id}"
            settlement = Settlement(
                settlement_id=settlement_id,
                payment_id=payments[0].payment_id,
                payout_ref="POUT-111",
                gross_amount=gross_amount,
                net_amount=net_amount,
                fee_deducted=5.0,
            )
            db.add(settlement)
            settlements.append(settlement)

    # 4. Exception
    exc = ExceptionRecord(
        run_id="RUN-TEST-123",
        order_id=order_id,
        payment_id=payments[0].payment_id if payments else None,
        settlement_id=settlements[0].settlement_id if settlements else None,
        exception_type=exception_type,
        severity="HIGH",
        status="DETECTED",
        expected_value="100.0",
        actual_value=str(gross_amount),
        difference=abs(100.0 - gross_amount),
    )
    db.add(exc)
    db.flush()

    # 5. AI Investigation
    flags = safety_flags if safety_flags is not None else []
    matches = (exception_type == ai_classification)
    inv = AIInvestigation(
        investigation_id=f"INV-{order_id}",
        reconciliation_run_id="RUN-TEST-123",
        order_id=order_id,
        exception_id=exc.id,
        exception_type=exception_type,
        summary="AI Summary",
        likely_cause="AI Cause",
        recommended_action="AI Action",
        ai_classification=ai_classification,
        ai_classification_matches_deterministic=matches,
        evidence_facts=json.dumps(["Evidence 1"]),
        possible_causes=json.dumps(["Cause 1"]),
        evidence_gaps=json.dumps([]),
        ai_confidence=ai_confidence,
        effective_confidence=effective_confidence,
        confidence_level=confidence_level,
        requires_human_review=requires_human_review,
        investigation_status=investigation_status,
        safety_flags=json.dumps(flags),
    )
    db.add(inv)
    db.commit()
    return exc


def test_auto_resolution(db):
    """Verify clean, high-confidence case routes to AUTO_RESOLVED."""
    exc = _seed_case(db, "ORD-AUTO", ai_confidence=0.95, effective_confidence=0.95, requires_human_review=False)
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "AUTO_RESOLVED"
    assert data["resolved_by"] == "SYSTEM"

    # Verify audit event
    events = db.query(ResolutionEvent).filter(ResolutionEvent.resolution_id == data["resolution_id"]).all()
    assert len(events) == 1
    assert events[0].new_status == "AUTO_RESOLVED"
    assert events[0].actor_type == "SYSTEM"


def test_medium_confidence(db):
    """Verify medium confidence routes to REVIEW_RECOMMENDED."""
    exc = _seed_case(
        db, "ORD-MED",
        ai_confidence=0.75,
        effective_confidence=0.75,
        confidence_level="MEDIUM",
        requires_human_review=True,
        investigation_status="REVIEW_RECOMMENDED"
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "REVIEW_RECOMMENDED"
    assert data["resolved_by"] is None


def test_low_confidence(db):
    """Verify low confidence routes to HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-LOW",
        ai_confidence=0.50,
        effective_confidence=0.50,
        confidence_level="LOW",
        requires_human_review=True,
        investigation_status="HUMAN_REVIEW_REQUIRED"
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"
    assert data["resolved_by"] is None


def test_refund_case(db):
    """Verify presence of a refund forces HUMAN_REVIEW_REQUIRED even if confidence is 0.99."""
    exc = _seed_case(
        db, "ORD-REFUND",
        ai_confidence=0.99,
        effective_confidence=0.99,
        payment_status="REFUNDED",
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_negative_settlement(db):
    """Verify negative settlement forces HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-NEG-SETTLEMENT",
        ai_confidence=0.95,
        effective_confidence=0.95,
        gross_amount=-10.0,
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_missing_payment(db):
    """Verify missing payment forces HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-MISSING-PAY",
        exception_type="MISSING_PAYMENT",
        ai_classification="MISSING_PAYMENT",
        payments_count=0,
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_missing_settlement(db):
    """Verify missing settlement forces HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-MISSING-SETTLEMENT",
        exception_type="UNMATCHED_SETTLEMENT",
        ai_classification="UNMATCHED_SETTLEMENT",
        settlements_count=0,
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_duplicate_payment(db):
    """Verify duplicate payment forces HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-DUP-PAYMENT",
        exception_type="DUPLICATE_PAYMENT",
        ai_classification="DUPLICATE_PAYMENT",
        payments_count=2,
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_ai_disagreement(db):
    """Verify AI disagreement forces HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-DISAGREE",
        exception_type="AMOUNT_MISMATCH",
        ai_classification="FEE_DISCREPANCY",
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"


def test_ai_failure(db):
    """Verify AI failure status routes to AI_FAILED/HUMAN_REVIEW_REQUIRED."""
    exc = _seed_case(
        db, "ORD-FAIL",
        investigation_status="AI_FAILED",
        safety_flags=["AI_FAILED"],
    )
    
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["resolution_status"] == "AI_FAILED"


def test_human_lifecycle(db):
    """Verify Human approval, rejection, and reopen (unresolve) lifecycle."""
    exc = _seed_case(
        db, "ORD-LIFECYCLE",
        ai_confidence=0.5,
        effective_confidence=0.5,
        confidence_level="LOW",
        requires_human_review=True,
        investigation_status="HUMAN_REVIEW_REQUIRED"
    )
    
    # Trigger resolution
    response = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    res_data = response.json()["data"]
    res_id = res_data["resolution_id"]
    assert res_data["resolution_status"] == "HUMAN_REVIEW_REQUIRED"

    # 1. Approve
    app_resp = client.post(f"/api/v1/review/{res_id}/approve", json={"notes": "Approve this!"})
    assert app_resp.status_code == 200
    app_data = app_resp.json()["data"]
    assert app_data["resolution_status"] == "APPROVED_BY_HUMAN"
    assert app_data["resolved_by"] == "HUMAN"
    assert app_data["resolution_notes"] == "Approve this!"

    # 2. Reopen (unresolve)
    unr_resp = client.post(f"/api/v1/review/{res_id}/unresolve", json={"reason": "Need extra info"})
    assert unr_resp.status_code == 200
    unr_data = unr_resp.json()["data"]
    assert unr_data["resolution_status"] == "UNRESOLVED"
    assert unr_data["resolved_by"] is None

    # 3. Reject
    rej_resp = client.post(f"/api/v1/review/{res_id}/reject", json={"notes": "Not correct facts"})
    assert rej_resp.status_code == 200
    rej_data = rej_resp.json()["data"]
    assert rej_data["resolution_status"] == "REJECTED_BY_HUMAN"
    assert rej_data["resolved_by"] == "HUMAN"

    # Verify audit events exist for transitions
    events = db.query(ResolutionEvent).filter(ResolutionEvent.resolution_id == res_id).all()
    assert len(events) == 4  # Start, Approve, Unresolve, Reject
    assert events[1].new_status == "APPROVED_BY_HUMAN"
    assert events[2].new_status == "UNRESOLVED"
    assert events[3].new_status == "REJECTED_BY_HUMAN"


def test_idempotency(db):
    """Verify running resolution twice does not create duplicate resolution records."""
    exc = _seed_case(db, "ORD-IDEMPOTENT")
    
    resp1 = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert resp1.status_code == 200
    res_id = resp1.json()["data"]["resolution_id"]

    resp2 = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    assert resp2.status_code == 200
    assert resp2.json()["data"]["resolution_id"] == res_id

    # Verify only one Resolution in DB
    resolutions = db.query(Resolution).filter(Resolution.order_id == exc.order_id).all()
    assert len(resolutions) == 1


def test_financial_immutability(db):
    """Verify resolution workflow cannot modify financial records or reconciliation results."""
    exc = _seed_case(db, "ORD-IMMUTABLE")
    
    # Store initial values
    order = db.query(Order).filter(Order.order_id == exc.order_id).first()
    pay = db.query(Payment).filter(Payment.order_id == exc.order_id).first()
    settle = db.query(Settlement).filter(Settlement.payment_id == pay.payment_id).first()
    
    orig_order_amt = order.amount
    orig_pay_amt = pay.amount
    orig_settle_gross = settle.gross_amount

    # Run resolution
    resp = client.post(f"/api/v1/resolution/run/{exc.order_id}")
    res_id = resp.json()["data"]["resolution_id"]
    client.post(f"/api/v1/review/{res_id}/approve", json={"notes": "Approve immutability check"})

    # Refresh
    db.refresh(order)
    db.refresh(pay)
    db.refresh(settle)

    assert order.amount == orig_order_amt
    assert pay.amount == orig_pay_amt
    assert settle.gross_amount == orig_settle_gross


def test_batch_limit(db):
    """Verify max_cases is respected in batch run."""
    _seed_case(db, "ORD-BATCH-1")
    _seed_case(db, "ORD-BATCH-2")
    _seed_case(db, "ORD-BATCH-3")

    resp = client.post("/api/v1/resolution/run", json={
        "reconciliation_run_id": "RUN-TEST-123",
        "max_cases": 2
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    # Should resolve exactly 2, not all 3
    assert data["total_eligible"] == 2


def test_review_queue_and_prioritization(db):
    """Verify review queue and prioritization logic."""
    # Seed 3 different priority cases
    # Case 1: High financial impact ($150 diff) -> Priority 10
    _seed_case(
        db, "ORD-PRIO-1",
        ai_confidence=0.95,
        effective_confidence=0.95,
        requires_human_review=True,
        gross_amount=250.0,
    ) # Diff is 150.0
    
    # Case 2: Low confidence -> Priority 20
    _seed_case(
        db, "ORD-PRIO-2",
        ai_confidence=0.45,
        effective_confidence=0.45,
        confidence_level="LOW",
        requires_human_review=True,
        investigation_status="HUMAN_REVIEW_REQUIRED",
    )
    
    # Case 3: Refund -> Priority 30
    _seed_case(
        db, "ORD-PRIO-3",
        ai_confidence=0.95,
        effective_confidence=0.95,
        payment_status="REFUNDED",
    )

    # Run resolution on all
    client.post("/api/v1/resolution/run/ORD-PRIO-1")
    client.post("/api/v1/resolution/run/ORD-PRIO-2")
    client.post("/api/v1/resolution/run/ORD-PRIO-3")

    # Fetch review queue
    resp = client.get("/api/v1/review/queue")
    assert resp.status_code == 200
    queue = resp.json()["data"]

    # Verify order of priority: 10, 20, 30
    assert queue[0]["order_id"] == "ORD-PRIO-1"
    assert queue[1]["order_id"] == "ORD-PRIO-2"
    assert queue[2]["order_id"] == "ORD-PRIO-3"


def test_ground_truth_isolation():
    """Verify resolution code never references ground_truth.json."""
    with open("app/services/resolution.py", "r", encoding="utf-8") as f:
        content = f.read()
    assert "ground_truth.json" not in content
