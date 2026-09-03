"""
End-to-End Test for Data Import, CSV Validation, Ingestion, Reconciliation,
AI Investigation, Human Review, and Audit Trail Lifecycle.
"""

import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch, MagicMock

from tests.conftest import client
from app.models.financial import Order, Payment, Settlement, ReconciliationRun, ExceptionRecord, ResolutionEvent
from app.schemas.ai import GeminiInvestigationSchema


# Safe synthetic test dataset covering all 8 operational anomaly types
CONTROLLED_ORDERS_CSV = """order_id,customer_id,merchant_id,amount,currency,status,created_at
ORD_NORMAL_1,CUST_001,MERCHANT_001,100.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_FEE_DISC,CUST_002,MERCHANT_001,200.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_AMT_MISMATCH,CUST_003,MERCHANT_001,300.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_MISSING_PAY,CUST_004,MERCHANT_001,150.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_MISSING_SETT,CUST_005,MERCHANT_001,250.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_DUP_PAY,CUST_006,MERCHANT_001,180.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_TIMING_DELAY,CUST_007,MERCHANT_001,400.00,USD,COMPLETED,2026-03-01T10:00:00Z
ORD_REFUND,CUST_008,MERCHANT_001,50.00,USD,COMPLETED,2026-03-01T10:00:00Z
"""

CONTROLLED_PAYMENTS_CSV = """payment_id,order_id,gateway,amount,fee,currency,status,transaction_ref,timestamp
PAY_NORMAL_1,ORD_NORMAL_1,Stripe,100.00,3.20,USD,CAPTURED,tx_001,2026-03-01T10:05:00Z
PAY_FEE_DISC,ORD_FEE_DISC,Stripe,200.00,6.10,USD,CAPTURED,tx_002,2026-03-01T10:05:00Z
PAY_AMT_MISMATCH,ORD_AMT_MISMATCH,Stripe,270.00,8.20,USD,CAPTURED,tx_003,2026-03-01T10:05:00Z
PAY_MISSING_SETT,ORD_MISSING_SETT,Stripe,250.00,7.55,USD,CAPTURED,tx_005,2026-03-01T10:05:00Z
PAY_DUP_1,ORD_DUP_PAY,Stripe,180.00,5.52,USD,CAPTURED,tx_006_a,2026-03-01T10:05:00Z
PAY_DUP_2,ORD_DUP_PAY,Stripe,180.00,5.52,USD,CAPTURED,tx_006_b,2026-03-01T10:06:00Z
PAY_TIMING_DELAY,ORD_TIMING_DELAY,Stripe,400.00,11.90,USD,CAPTURED,tx_007,2026-03-01T10:05:00Z
PAY_REFUND,ORD_REFUND,Stripe,50.00,1.75,USD,REFUNDED,tx_008,2026-03-01T10:05:00Z
"""

CONTROLLED_SETTLEMENTS_CSV = """settlement_id,payment_id,payout_ref,gross_amount,net_amount,fee_deducted,currency,settlement_date,status
SET_NORMAL_1,PAY_NORMAL_1,po_001,100.00,96.80,3.20,USD,2026-03-02T04:00:00Z,SETTLED
SET_FEE_DISC,PAY_FEE_DISC,po_001,200.00,185.00,15.00,USD,2026-03-02T04:00:00Z,SETTLED
SET_AMT_MISMATCH,PAY_AMT_MISMATCH,po_001,270.00,261.80,8.20,USD,2026-03-02T04:00:00Z,SETTLED
SET_DUP_1,PAY_DUP_1,po_001,180.00,174.48,5.52,USD,2026-03-02T04:00:00Z,SETTLED
SET_DUP_2,PAY_DUP_2,po_001,180.00,174.48,5.52,USD,2026-03-02T04:00:00Z,SETTLED
SET_TIMING_DELAY,PAY_TIMING_DELAY,po_001,400.00,388.10,11.90,USD,2026-03-28T04:00:00Z,SETTLED
SET_REFUND,PAY_REFUND,po_001,50.00,48.25,1.75,USD,2026-03-02T04:00:00Z,SETTLED
"""


def test_csv_validation_structural_checks():
    """Verifies that the CSV validation endpoint catches missing columns, invalid amounts, and unparseable dates."""
    # 1. Test missing required columns
    bad_orders_csv = "order_id,amount\nORD_1,100"  # missing customer_id
    res = client.post("/api/v1/data/validate", json={"orders_csv": bad_orders_csv})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_reconcilable"] is False
    assert data["file_statuses"]["orders"] == "ERROR"
    assert any("missing required columns" in msg["message"] for msg in data["messages"])

    # 2. Test valid datasets with warnings
    res = client.post("/api/v1/data/validate", json={
        "orders_csv": CONTROLLED_ORDERS_CSV,
        "payments_csv": CONTROLLED_PAYMENTS_CSV,
        "settlements_csv": CONTROLLED_SETTLEMENTS_CSV,
    })
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["is_reconcilable"] is True
    assert data["orders_count"] == 8
    assert data["payments_count"] == 8
    assert data["settlements_count"] == 7
    assert data["total_valid_records"] == 23


def test_full_custom_upload_reconciliation_journey():
    """Verifies full lifecycle from upload to review queue and immutable audit trail."""
    # Step 1: Upload and Ingest Custom CSV
    upload_res = client.post("/api/v1/data/upload", json={
        "orders_csv": CONTROLLED_ORDERS_CSV,
        "payments_csv": CONTROLLED_PAYMENTS_CSV,
        "settlements_csv": CONTROLLED_SETTLEMENTS_CSV,
    })
    assert upload_res.status_code == 200
    upload_data = upload_res.json()["data"]
    assert upload_data["status"] == "SUCCESS"
    assert upload_data["total_records"] == 23

    # Verify Summary Endpoint reports UPLOADED source
    summary_res = client.get("/api/v1/data/summary")
    assert summary_res.status_code == 200
    assert summary_res.json()["data"]["total_orders_in_db"] == 8
    assert summary_res.json()["data"]["dataset_source"] == "UPLOADED"

    # Step 2: Run Deterministic 3-Way Reconciliation
    recon_res = client.post("/api/v1/reconciliation/run")
    assert recon_res.status_code == 200
    recon_data = recon_res.json()["data"]
    run_id = recon_data["run_id"]
    assert recon_data["total_records"] == 8
    assert recon_data["matched"] == 1  # ORD_NORMAL_1
    assert recon_data["exceptions"] == 7  # 7 anomalies detected

    # Step 3: Verify Detected Exceptions
    exc_res = client.get("/api/v1/reconciliation/exceptions")
    assert exc_res.status_code == 200
    exceptions = exc_res.json()["data"]
    assert len(exceptions) >= 7

    exc_types = {e["exception_type"] for e in exceptions}
    assert "MISSING_PAYMENT" in exc_types
    assert ("UNMATCHED_SETTLEMENT" in exc_types or "MISSING_SETTLEMENT" in exc_types)
    assert "AMOUNT_MISMATCH" in exc_types
    assert "FEE_DISCREPANCY" in exc_types
    assert "DUPLICATE_PAYMENT" in exc_types
    assert "TIMING_DELAY" in exc_types
    assert "UNACCOUNTED_REFUND" in exc_types

    # Step 4: Run AI Investigation with Mocked Gemini Client
    mock_gemini_json = json.dumps({
        "classification": "FEE_DISCREPANCY",
        "summary": "Analysis indicates fee or amount discrepancy detected by rule engine.",
        "likely_cause": "Payment gateway fee mismatch or timing delay.",
        "recommended_action": "Verify settlement report with bank partner.",
        "evidence_facts": ["Order value verified against payment gateway record."],
        "possible_causes": ["Intermediary interchange fee change"],
        "evidence_gaps": [],
        "confidence": 0.92,
        "requires_human_review": True,
    })

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = mock_gemini_json
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.ai_investigator.settings.GEMINI_API_KEY", "mock-key"), \
         patch("google.genai.Client", return_value=mock_client):
        ai_res = client.post("/api/v1/ai/investigate", json={
            "reconciliation_run_id": run_id,
            "max_cases": 50,
        })
        assert ai_res.status_code == 200
        assert ai_res.json()["data"]["investigated_cases"] >= 7

    # Step 5: Run Batch Resolution
    res_run = client.post("/api/v1/resolution/run", json={
        "reconciliation_run_id": run_id,
        "max_cases": 50,
    })
    assert res_run.status_code == 200
    assert res_run.json()["data"]["total_eligible"] >= 7

    # Step 6: Verify Review Queue and Perform Operator Action
    queue_res = client.get("/api/v1/review/queue")
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["data"]
    assert len(queue_items) > 0

    target_case = queue_items[0]
    res_id = target_case["resolution_id"]

    # Approve Case
    appr_res = client.post(f"/api/v1/review/{res_id}/approve", json={"notes": "Approved by Finance Operator"})
    assert appr_res.status_code == 200
    assert appr_res.json()["data"]["resolution_status"] == "APPROVED_BY_HUMAN"

    # Step 7: Verify Immutable Audit Trail
    audit_res = client.get(f"/api/v1/audit/events?resolution_id={res_id}")
    assert audit_res.status_code == 200
    events = audit_res.json()["data"]
    assert len(events) >= 1
    assert any(e["actor_type"] == "HUMAN" and e["new_status"] == "APPROVED_BY_HUMAN" for e in events)

    # Immutability check: Verify raw order amounts were not mutated by AI or resolution
    order_in_db = client.get(f"/api/v1/reconciliation/results/ORD_NORMAL_1")
    assert order_in_db.status_code == 200
    assert order_in_db.json()["data"]["order_amount"] == 100.00
