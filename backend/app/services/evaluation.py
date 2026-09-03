import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.base import Base
from app.models.financial import ReconciliationRun, ReconciliationResult, EvaluationRun


class EvaluationService:
    """Service to evaluate reconciliation run results against hidden ground truth annotations."""

    @staticmethod
    def evaluate_reconciliation_run(
        db: Session,
        reconciliation_run_id: Optional[str] = None,
        ground_truth_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Evaluates a reconciliation run against ground truth."""
        # Ensure evaluation table exists
        Base.metadata.create_all(bind=db.get_bind())

        start_time = time.time()

        # Find target reconciliation run
        if reconciliation_run_id:
            rec_run = db.query(ReconciliationRun).filter(ReconciliationRun.run_id == reconciliation_run_id).first()
        else:
            rec_run = db.query(ReconciliationRun).order_by(ReconciliationRun.id.desc()).first()

        if not rec_run:
            raise ValueError("No reconciliation run found to evaluate. Execute a reconciliation run first.")

        # Fetch stored results for this run
        results = db.query(ReconciliationResult).filter(ReconciliationResult.run_id == rec_run.run_id).all()
        if not results:
            raise ValueError(f"No reconciliation results found for run {rec_run.run_id}.")

        # Load ground truth file
        gt_path = ground_truth_file or (settings.GROUND_TRUTH_DIR / "ground_truth.json")
        if not gt_path.exists():
            raise FileNotFoundError(f"Ground truth file not found at {gt_path}. Generate dataset first.")

        with open(gt_path, "r", encoding="utf-8") as f:
            gt_data = json.load(f)

        gt_by_order: Dict[str, Dict[str, Any]] = {item["order_id"]: item for item in gt_data}

        # Metric counters
        tp = 0  # Actual Anomaly, Predicted EXCEPTION
        fp = 0  # Actual MATCHED, Predicted EXCEPTION
        fn = 0  # Actual Anomaly, Predicted MATCHED
        tn = 0  # Actual MATCHED, Predicted MATCHED

        total_gt_anomalies = 0
        correctly_classified_exceptions = 0
        incorrectly_classified_exceptions = 0

        mismatches: List[Dict[str, Any]] = []

        for r in results:
            gt_item = gt_by_order.get(r.order_id)
            if not gt_item:
                continue

            gt_anomaly_type = gt_item.get("anomaly_type", "EXACT_MATCH")
            gt_expected_status = "MATCHED" if gt_anomaly_type == "EXACT_MATCH" else "EXCEPTION"

            ctrl_status = r.reconciliation_status
            ctrl_exception_types = json.loads(r.exception_types) if r.exception_types else []

            is_status_correct = False
            is_category_correct = False
            mismatch_type = None
            reason = None

            # Level 1 Status Evaluation
            if gt_expected_status == "EXCEPTION" and ctrl_status == "EXCEPTION":
                tp += 1
                is_status_correct = True
            elif gt_expected_status == "MATCHED" and ctrl_status == "EXCEPTION":
                fp += 1
                is_status_correct = False
                mismatch_type = "FALSE_POSITIVE"
                reason = f"Ground truth is EXACT_MATCH, but controller reported EXCEPTION ({ctrl_exception_types})."
            elif gt_expected_status == "EXCEPTION" and ctrl_status == "MATCHED":
                fn += 1
                is_status_correct = False
                mismatch_type = "FALSE_NEGATIVE"
                reason = f"Ground truth is anomaly '{gt_anomaly_type}', but controller reported MATCHED."
            else:  # MATCHED & MATCHED
                tn += 1
                is_status_correct = True

            # Level 2 Exception Category Evaluation
            if gt_anomaly_type != "EXACT_MATCH":
                total_gt_anomalies += 1
                if gt_anomaly_type in ctrl_exception_types:
                    correctly_classified_exceptions += 1
                    is_category_correct = True
                else:
                    incorrectly_classified_exceptions += 1
                    is_category_correct = False
                    if is_status_correct:  # Category mismatch on an exception order
                        mismatch_type = "CATEGORY_MISMATCH"
                        reason = f"Ground truth anomaly type '{gt_anomaly_type}' missing from controller detected exception types {ctrl_exception_types}."

            if mismatch_type:
                mismatches.append({
                    "order_id": r.order_id,
                    "ground_truth_status": gt_expected_status,
                    "controller_status": ctrl_status,
                    "ground_truth_exception_type": gt_anomaly_type,
                    "controller_exception_types": ctrl_exception_types,
                    "is_status_correct": is_status_correct,
                    "is_category_correct": is_category_correct,
                    "mismatch_type": mismatch_type,
                    "reason": reason,
                })

        # Calculate metrics with zero division safety
        total_records = len(results)
        correctly_classified_status = tp + tn
        incorrectly_classified_status = fp + fn

        status_accuracy = (correctly_classified_status / total_records) if total_records > 0 else 0.0

        precision = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1_score = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

        exception_classification_accuracy = (
            (correctly_classified_exceptions / total_gt_anomalies) if total_gt_anomalies > 0 else 0.0
        )

        matched_count = tn + fn
        exception_count = tp + fp

        match_rate = (matched_count / total_records) if total_records > 0 else 0.0
        exception_rate = (exception_count / total_records) if total_records > 0 else 0.0

        elapsed_seconds = max(time.time() - start_time, 0.0001)
        throughput = total_records / elapsed_seconds

        eval_run_id = f"EVAL-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6].upper()}"

        confusion_matrix = {
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "true_positives": tp,
        }

        eval_run = EvaluationRun(
            evaluation_run_id=eval_run_id,
            reconciliation_run_id=rec_run.run_id,
            evaluated_at=datetime.utcnow(),
            total_records=total_records,
            correctly_classified_status=correctly_classified_status,
            incorrectly_classified_status=incorrectly_classified_status,
            status_accuracy=status_accuracy,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            total_ground_truth_anomalies=total_gt_anomalies,
            correctly_classified_exceptions=correctly_classified_exceptions,
            incorrectly_classified_exceptions=incorrectly_classified_exceptions,
            exception_classification_accuracy=exception_classification_accuracy,
            matched_count=matched_count,
            exception_count=exception_count,
            match_rate=match_rate,
            exception_rate=exception_rate,
            processing_time_seconds=elapsed_seconds,
            throughput_records_per_second=throughput,
            confusion_matrix_json=json.dumps(confusion_matrix),
            mismatches_json=json.dumps(mismatches),
        )

        db.add(eval_run)
        db.commit()

        return eval_run.to_dict()

    @staticmethod
    def get_latest_evaluation(db: Session) -> Optional[Dict[str, Any]]:
        """Gets summary metrics of the latest evaluation run."""
        latest_eval = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).first()
        if not latest_eval:
            return None
        return latest_eval.to_dict()

    @staticmethod
    def get_evaluation_by_id(db: Session, evaluation_run_id: str) -> Optional[Dict[str, Any]]:
        """Gets summary metrics of a specific evaluation run."""
        eval_run = db.query(EvaluationRun).filter(EvaluationRun.evaluation_run_id == evaluation_run_id).first()
        if not eval_run:
            return None
        return eval_run.to_dict()

    @staticmethod
    def get_mismatches(db: Session, evaluation_run_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Gets mismatch classification records for an evaluation run."""
        if evaluation_run_id:
            eval_run = db.query(EvaluationRun).filter(EvaluationRun.evaluation_run_id == evaluation_run_id).first()
        else:
            eval_run = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).first()

        if not eval_run or not eval_run.mismatches_json:
            return []
        return json.loads(eval_run.mismatches_json)

    @staticmethod
    def get_confusion_matrix(db: Session, evaluation_run_id: Optional[str] = None) -> Dict[str, int]:
        """Gets the confusion matrix dictionary for an evaluation run."""
        if evaluation_run_id:
            eval_run = db.query(EvaluationRun).filter(EvaluationRun.evaluation_run_id == evaluation_run_id).first()
        else:
            eval_run = db.query(EvaluationRun).order_by(EvaluationRun.id.desc()).first()

        if not eval_run or not eval_run.confusion_matrix_json:
            return {"true_negatives": 0, "false_positives": 0, "false_negatives": 0, "true_positives": 0}
        return json.loads(eval_run.confusion_matrix_json)
