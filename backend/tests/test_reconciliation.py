from datetime import datetime, timedelta
import pytest
from app.models.financial import Order, Payment, Settlement, ReconciliationRun, ExceptionRecord, ReconciliationResult
from app.services.reconciliation import ReconciliationService, monetary_equals, monetary_diff
from tests.conftest import TestingSessionLocal, client




def test_monetary_precision_tolerance():
    """Verify monetary comparison tolerance helpers."""
    assert monetary_equals(100.00, 100.001, tolerance=0.01) is True
    assert monetary_equals(100.00, 100.009, tolerance=0.01) is True
    assert monetary_equals(100.00, 100.02, tolerance=0.01) is False
    assert monetary_diff(100.00, 95.50) == 4.50


def test_reconcile_normal_matched_transaction():
    """Verify an exact 3-way match across order, payment, and settlement yields MATCHED."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-NORMAL", customer_id="C1", amount=150.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-NORMAL", order_id="ORD-NORMAL", gateway="Stripe", amount=150.00, fee=4.65, currency="USD", status="CAPTURED", timestamp=now)
    settlement = Settlement(settlement_id="SET-NORMAL", payment_id="PAY-NORMAL", payout_ref="PO-1", gross_amount=150.00, net_amount=145.35, fee_deducted=4.65, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["total_records"] == 1
    assert summary["matched"] == 1
    assert summary["exceptions"] == 0

    results = ReconciliationService.get_results(db, order_id="ORD-NORMAL")
    assert len(results) == 1
    assert results[0]["reconciliation_status"] == "MATCHED"
    assert results[0]["exception_types"] == []
    db.close()


def test_reconcile_amount_mismatch():
    """Verify order amount != payment amount yields AMOUNT_MISMATCH exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-MISMATCH", customer_id="C1", amount=200.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-MISMATCH", order_id="ORD-MISMATCH", gateway="Stripe", amount=180.00, fee=5.00, currency="USD", status="CAPTURED", timestamp=now)
    settlement = Settlement(settlement_id="SET-MISMATCH", payment_id="PAY-MISMATCH", payout_ref="PO-1", gross_amount=180.00, net_amount=175.00, fee_deducted=5.00, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["matched"] == 0
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="AMOUNT_MISMATCH")
    assert len(exceptions) == 1
    assert exceptions[0]["order_id"] == "ORD-MISMATCH"
    assert exceptions[0]["difference"] == 20.00
    db.close()


def test_reconcile_missing_payment():
    """Verify order with no payment yields MISSING_PAYMENT exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-NOPAY", customer_id="C1", amount=100.00, currency="USD", status="COMPLETED", created_at=now)
    db.add(order)
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="MISSING_PAYMENT")
    assert len(exceptions) == 1
    assert exceptions[0]["order_id"] == "ORD-NOPAY"
    assert exceptions[0]["payment_id"] is None
    db.close()


def test_reconcile_unmatched_settlement():
    """Verify payment with no settlement yields UNMATCHED_SETTLEMENT exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-NOSET", customer_id="C1", amount=75.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-NOSET", order_id="ORD-NOSET", gateway="PayPal", amount=75.00, fee=2.50, currency="USD", status="CAPTURED", timestamp=now)

    db.add_all([order, payment])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="UNMATCHED_SETTLEMENT")
    assert len(exceptions) == 1
    assert exceptions[0]["order_id"] == "ORD-NOSET"
    assert exceptions[0]["payment_id"] == "PAY-NOSET"
    db.close()


def test_reconcile_duplicate_payment():
    """Verify multiple payments for 1 order yields DUPLICATE_PAYMENT exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-DUP", customer_id="C1", amount=50.00, currency="USD", status="COMPLETED", created_at=now)
    pay1 = Payment(payment_id="PAY-DUP-1", order_id="ORD-DUP", gateway="Stripe", amount=50.00, fee=1.75, currency="USD", status="CAPTURED", timestamp=now)
    pay2 = Payment(payment_id="PAY-DUP-2", order_id="ORD-DUP", gateway="Stripe", amount=50.00, fee=1.75, currency="USD", status="CAPTURED", timestamp=now + timedelta(seconds=2))
    settle1 = Settlement(settlement_id="SET-DUP-1", payment_id="PAY-DUP-1", payout_ref="PO-1", gross_amount=50.00, net_amount=48.25, fee_deducted=1.75, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, pay1, pay2, settle1])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["exceptions"] == 1

    results = ReconciliationService.get_results(db, order_id="ORD-DUP")
    assert len(results) == 1
    assert "PAY-DUP-1" in results[0]["payment_ids"]
    assert "PAY-DUP-2" in results[0]["payment_ids"]

    exceptions = ReconciliationService.get_exceptions(db, exception_type="DUPLICATE_PAYMENT")
    assert len(exceptions) == 1
    assert exceptions[0]["payment_id"] == "PAY-DUP-2"
    db.close()


def test_reconcile_fee_discrepancy():
    """Verify settlement fee != payment fee yields FEE_DISCREPANCY exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-FEE", customer_id="C1", amount=100.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-FEE", order_id="ORD-FEE", gateway="Adyen", amount=100.00, fee=2.70, currency="USD", status="CAPTURED", timestamp=now)
    settlement = Settlement(settlement_id="SET-FEE", payment_id="PAY-FEE", payout_ref="PO-1", gross_amount=100.00, net_amount=92.00, fee_deducted=8.00, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="FEE_DISCREPANCY")
    assert len(exceptions) == 1
    assert exceptions[0]["order_id"] == "ORD-FEE"
    assert exceptions[0]["difference"] == 5.30
    db.close()


def test_reconcile_timing_delay():
    """Verify settlement > 3 days after payment yields TIMING_DELAY exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-TIME", customer_id="C1", amount=300.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-TIME", order_id="ORD-TIME", gateway="Stripe", amount=300.00, fee=9.00, currency="USD", status="CAPTURED", timestamp=now)
    settlement = Settlement(settlement_id="SET-TIME", payment_id="PAY-TIME", payout_ref="PO-1", gross_amount=300.00, net_amount=291.00, fee_deducted=9.00, currency="USD", settlement_date=now + timedelta(days=15), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db, settlement_window_days=3)
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="TIMING_DELAY")
    assert len(exceptions) == 1
    assert exceptions[0]["actual_value"] == "15 days"
    db.close()


def test_reconcile_unaccounted_refund():
    """Verify REFUNDED payment for COMPLETED order yields UNACCOUNTED_REFUND exception."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-REFUND", customer_id="C1", amount=80.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-REFUND", order_id="ORD-REFUND", gateway="Stripe", amount=80.00, fee=0.0, currency="USD", status="REFUNDED", timestamp=now)
    settlement = Settlement(settlement_id="SET-REFUND", payment_id="PAY-REFUND", payout_ref="PO-1", gross_amount=0.0, net_amount=-80.00, fee_deducted=0.0, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    summary = ReconciliationService.run_reconciliation(db)
    assert summary["exceptions"] == 1

    exceptions = ReconciliationService.get_exceptions(db, exception_type="UNACCOUNTED_REFUND")
    assert len(exceptions) == 1
    assert exceptions[0]["order_id"] == "ORD-REFUND"
    db.close()


def test_reconciliation_api_endpoints():
    """Integration test for POST /run, GET /summary, GET /results, GET /results/{order_id}, and GET /exceptions."""
    db = TestingSessionLocal()
    now = datetime.utcnow()

    order = Order(order_id="ORD-API", customer_id="C1", amount=100.00, currency="USD", status="COMPLETED", created_at=now)
    payment = Payment(payment_id="PAY-API", order_id="ORD-API", gateway="Stripe", amount=100.00, fee=3.20, currency="USD", status="CAPTURED", timestamp=now)
    settlement = Settlement(settlement_id="SET-API", payment_id="PAY-API", payout_ref="PO-1", gross_amount=100.00, net_amount=96.80, fee_deducted=3.20, currency="USD", settlement_date=now + timedelta(days=1), status="SETTLED")

    db.add_all([order, payment, settlement])
    db.commit()

    # 1. Trigger reconciliation run via POST /api/v1/reconciliation/run
    response = client.post("/api/v1/reconciliation/run", json={"settlement_window_days": 3})
    assert response.status_code == 200, f"Error: {response.json()}"
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["data"]["total_records"] == 1
    assert res_data["data"]["matched"] == 1
    run_id = res_data["data"]["run_id"]

    # 2. Get summary via GET /api/v1/reconciliation/summary
    sum_resp = client.get("/api/v1/reconciliation/summary")
    assert sum_resp.status_code == 200
    sum_data = sum_resp.json()
    assert sum_data["data"]["run_id"] == run_id

    # 3. Get results via GET /api/v1/reconciliation/results
    results_resp = client.get("/api/v1/reconciliation/results")
    assert results_resp.status_code == 200
    results_data = results_resp.json()["data"]
    assert len(results_data) == 1
    assert results_data[0]["order_id"] == "ORD-API"

    # 4. Get single result via GET /api/v1/reconciliation/results/ORD-API
    single_resp = client.get("/api/v1/reconciliation/results/ORD-API")
    assert single_resp.status_code == 200
    assert single_resp.json()["data"]["reconciliation_status"] == "MATCHED"

    # 5. Get exceptions via GET /api/v1/reconciliation/exceptions
    exc_resp = client.get("/api/v1/reconciliation/exceptions")
    assert exc_resp.status_code == 200
    assert len(exc_resp.json()["data"]) == 0
    db.close()
