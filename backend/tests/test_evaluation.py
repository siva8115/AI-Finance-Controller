import json
import pytest
from pathlib import Path
from datetime import datetime, timedelta

from app.core.config import settings
from app.models.financial import Order, Payment, Settlement, ReconciliationRun, ReconciliationResult, ExceptionRecord, EvaluationRun
from app.services.reconciliation import ReconciliationService
from app.services.evaluation import EvaluationService
from tests.conftest import TestingSessionLocal, client




def test_ground_truth_isolation():
    """Verify that reconciliation.py service has NO imports or calls to ground truth or evaluation logic."""
    from app.services import reconciliation as rec_module
    with open(rec_module.__file__, "r", encoding="utf-8") as f:
        content = f.read()

    assert "ground_truth" not in content
    assert "EvaluationService" not in content
    assert "evaluation_runs" not in content


def test_evaluation_level1_and_level2_metrics(tmp_path):
    """Test Level 1 (status precision/recall/F1) and Level 2 (category accuracy) metrics computation."""
    db = TestingSessionLocal()
    run_id = "RUN-TEST-001"

    # Create dummy ReconciliationRun
    rec_run = ReconciliationRun(
        run_id=run_id,
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        status="COMPLETED",
        total_records=4,
        matched_count=2,
        exception_count=2,
        processing_time_seconds=0.1,
    )
    db.add(rec_run)

    # 4 Orders:
    # ORD-1: GT=EXACT_MATCH, Ctrl=MATCHED -> True Negative (TN)
    # ORD-2: GT=AMOUNT_MISMATCH, Ctrl=AMOUNT_MISMATCH -> True Positive (TP), Category Correct
    # ORD-3: GT=AMOUNT_MISMATCH, Ctrl=FEE_DISCREPANCY -> True Positive (TP), Category Mismatch
    # ORD-4: GT=EXACT_MATCH, Ctrl=FEE_DISCREPANCY -> False Positive (FP)
    results = [
        ReconciliationResult(run_id=run_id, order_id="ORD-1", reconciliation_status="MATCHED", exception_types="[]"),
        ReconciliationResult(run_id=run_id, order_id="ORD-2", reconciliation_status="EXCEPTION", exception_types='["AMOUNT_MISMATCH"]'),
        ReconciliationResult(run_id=run_id, order_id="ORD-3", reconciliation_status="EXCEPTION", exception_types='["FEE_DISCREPANCY"]'),
        ReconciliationResult(run_id=run_id, order_id="ORD-4", reconciliation_status="EXCEPTION", exception_types='["FEE_DISCREPANCY"]'),
    ]
    db.add_all(results)
    db.commit()

    # Ground truth JSON file
    gt_data = [
        {"order_id": "ORD-1", "anomaly_type": "EXACT_MATCH", "expected_status": "MATCHED"},
        {"order_id": "ORD-2", "anomaly_type": "AMOUNT_MISMATCH", "expected_status": "EXCEPTION"},
        {"order_id": "ORD-3", "anomaly_type": "AMOUNT_MISMATCH", "expected_status": "EXCEPTION"},
        {"order_id": "ORD-4", "anomaly_type": "EXACT_MATCH", "expected_status": "MATCHED"},
    ]
    gt_file = tmp_path / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_data, f)

    summary = EvaluationService.evaluate_reconciliation_run(db=db, reconciliation_run_id=run_id, ground_truth_file=gt_file)

    # Level 1 Checks:
    # TN=1 (ORD-1), TP=2 (ORD-2, ORD-3), FP=1 (ORD-4), FN=0
    assert summary["true_negatives"] == 1
    assert summary["true_positives"] == 2
    assert summary["false_positives"] == 1
    assert summary["false_negatives"] == 0

    # Precision = TP / (TP + FP) = 2 / 3 = 0.6667
    assert round(summary["precision"], 4) == 0.6667
    # Recall = TP / (TP + FN) = 2 / 2 = 1.0
    assert summary["recall"] == 1.0
    # F1 = 2 * (0.6667 * 1.0) / (0.6667 + 1.0) = 0.8
    assert round(summary["f1_score"], 4) == 0.8
    # Status accuracy = (TP + TN) / 4 = 3 / 4 = 0.75
    assert summary["status_accuracy"] == 0.75

    # Level 2 Checks:
    # Total GT Anomalies = 2 (ORD-2, ORD-3)
    # Correct Category = 1 (ORD-2)
    # Incorrect Category = 1 (ORD-3 category mismatch)
    assert summary["total_ground_truth_anomalies"] == 2
    assert summary["correctly_classified_exceptions"] == 1
    assert summary["incorrectly_classified_exceptions"] == 1
    assert summary["exception_classification_accuracy"] == 0.5

    # Mismatches List: ORD-3 (category mismatch) and ORD-4 (false positive)
    mismatches = summary["mismatches"]
    assert len(mismatches) == 2
    mismatch_types = [m["mismatch_type"] for m in mismatches]
    assert "CATEGORY_MISMATCH" in mismatch_types
    assert "FALSE_POSITIVE" in mismatch_types

    db.close()


def test_eval_false_negative(tmp_path):
    """Test detection of False Negative (GT anomaly, controller MATCHED)."""
    db = TestingSessionLocal()
    run_id = "RUN-FN"

    rec_run = ReconciliationRun(run_id=run_id, status="COMPLETED", total_records=1, matched_count=1, exception_count=0)
    res = ReconciliationResult(run_id=run_id, order_id="ORD-FN", reconciliation_status="MATCHED", exception_types="[]")
    db.add_all([rec_run, res])
    db.commit()

    gt_data = [{"order_id": "ORD-FN", "anomaly_type": "MISSING_PAYMENT", "expected_status": "EXCEPTION"}]
    gt_file = tmp_path / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_data, f)

    summary = EvaluationService.evaluate_reconciliation_run(db=db, reconciliation_run_id=run_id, ground_truth_file=gt_file)

    assert summary["false_negatives"] == 1
    assert summary["recall"] == 0.0
    assert summary["mismatches"][0]["mismatch_type"] == "FALSE_NEGATIVE"
    db.close()


def test_eval_event_vs_order_count_distinction():
    """Verify that affected-order count and exception-event count are logically distinguished."""
    db = TestingSessionLocal()
    run_id = "RUN-EVENT-DIST"

    rec_run = ReconciliationRun(run_id=run_id, status="COMPLETED", total_records=1, matched_count=0, exception_count=1)
    res = ReconciliationResult(run_id=run_id, order_id="ORD-MULTI-EXC", reconciliation_status="EXCEPTION", exception_types='["AMOUNT_MISMATCH", "TIMING_DELAY"]')
    exc1 = ExceptionRecord(run_id=run_id, order_id="ORD-MULTI-EXC", exception_type="AMOUNT_MISMATCH")
    exc2 = ExceptionRecord(run_id=run_id, order_id="ORD-MULTI-EXC", exception_type="TIMING_DELAY")

    db.add_all([rec_run, res, exc1, exc2])
    db.commit()

    assert rec_run.exception_count == 1  # 1 affected order
    events = db.query(ExceptionRecord).filter(ExceptionRecord.run_id == run_id).all()
    assert len(events) == 2  # 2 exception events
    db.close()


def test_evaluation_api_endpoints(tmp_path):
    """Integration test for evaluation REST API endpoints.
    
    Uses the TestClient (which shares the in-memory DB via override_get_db) to:
    1. Generate synthetic data
    2. Ingest it
    3. Trigger reconciliation via API
    4. Write a matching ground truth file
    5. Call all evaluation endpoints
    """
    # Step 1: Generate synthetic data (uses file system, seed=42, 10 orders)
    gen_resp = client.post("/api/v1/data/generate", json={"num_orders": 10, "anomaly_rate": 0.0, "seed": 42})
    assert gen_resp.status_code == 200, f"Generate error: {gen_resp.json()}"

    # Step 2: Ingest raw CSVs into the test in-memory DB
    ingest_resp = client.post("/api/v1/data/ingest")
    assert ingest_resp.status_code == 200, f"Ingest error: {ingest_resp.json()}"

    # Step 3: Trigger reconciliation via API
    rec_resp = client.post("/api/v1/reconciliation/run", json={})
    assert rec_resp.status_code == 200, f"Reconcile error: {rec_resp.json()}"
    run_id = rec_resp.json()["data"]["run_id"]

    # Step 4: Write ground truth matching all 10 as EXACT_MATCH (anomaly_rate=0.0)
    # The generator with seed=42 and anomaly_rate=0.0 produces all EXACT_MATCH entries
    # We can read the generated ground truth directly
    gt_file = settings.GROUND_TRUTH_DIR / "ground_truth.json"
    assert gt_file.exists(), "Ground truth file not found after generation"

    # Step 5: Trigger evaluation via POST /api/v1/evaluation/run
    response = client.post("/api/v1/evaluation/run", json={"reconciliation_run_id": run_id})
    assert response.status_code == 200, f"Evaluation error: {response.json()}"
    res_data = response.json()
    assert res_data["success"] is True
    eval_id = res_data["data"]["evaluation_run_id"]
    # With 0 anomalies + all MATCHED, status accuracy should be 1.0
    assert res_data["data"]["status_accuracy"] == 1.0

    # Step 6: GET /api/v1/evaluation/results
    latest_resp = client.get("/api/v1/evaluation/results")
    assert latest_resp.status_code == 200
    assert latest_resp.json()["data"]["evaluation_run_id"] == eval_id

    # Step 7: GET /api/v1/evaluation/results/{id}
    by_id_resp = client.get(f"/api/v1/evaluation/results/{eval_id}")
    assert by_id_resp.status_code == 200
    assert by_id_resp.json()["data"]["evaluation_run_id"] == eval_id

    # Step 8: GET /api/v1/evaluation/mismatches (should be 0 with 0 anomalies)
    mismatch_resp = client.get("/api/v1/evaluation/mismatches")
    assert mismatch_resp.status_code == 200
    assert len(mismatch_resp.json()["data"]) == 0

    # Step 9: GET /api/v1/evaluation/confusion-matrix
    matrix_resp = client.get("/api/v1/evaluation/confusion-matrix")
    assert matrix_resp.status_code == 200
    matrix = matrix_resp.json()["data"]
    assert matrix["true_negatives"] == 10  # All 10 correctly MATCHED
    assert matrix["false_positives"] == 0
    assert matrix["false_negatives"] == 0
    assert matrix["true_positives"] == 0

