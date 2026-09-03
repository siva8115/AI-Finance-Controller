from typing import List, Optional, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.evaluation import (
    EvaluationRunRequest,
    EvaluationSummary,
    ConfusionMatrixResponse,
    MismatchDetail,
)
from app.services.evaluation import EvaluationService

router = APIRouter(prefix="/evaluation", tags=["Evaluation Engine"])


@router.post("/run", response_model=APIResponse[EvaluationSummary])
def run_evaluation(
    payload: Optional[EvaluationRunRequest] = Body(None),
    db: Session = Depends(get_db),
):
    """Triggers an evaluation of a reconciliation run against ground truth."""
    try:
        rec_run_id = payload.reconciliation_run_id if payload else None
        summary = EvaluationService.evaluate_reconciliation_run(
            db=db,
            reconciliation_run_id=rec_run_id,
        )
        return APIResponse(
            success=True,
            message=f"Evaluation completed for run {summary['reconciliation_run_id']}: status accuracy = {summary['status_accuracy'] * 100:.2f}%, F1 = {summary['f1_score']:.4f}.",
            data=EvaluationSummary(**summary),
        )
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}",
        )


@router.get("/results", response_model=APIResponse[Optional[EvaluationSummary]])
def get_latest_evaluation_summary(db: Session = Depends(get_db)):
    """Gets the summary metrics of the latest evaluation run."""
    try:
        summary = EvaluationService.get_latest_evaluation(db=db)
        if not summary:
            return APIResponse(
                success=True,
                message="No evaluation runs have been executed yet.",
                data=None,
            )
        return APIResponse(
            success=True,
            message="Latest evaluation summary retrieved successfully.",
            data=EvaluationSummary(**summary),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch evaluation summary: {str(e)}",
        )


@router.get("/results/{evaluation_id}", response_model=APIResponse[EvaluationSummary])
def get_evaluation_by_id(evaluation_id: str, db: Session = Depends(get_db)):
    """Gets summary metrics for a specific evaluation run."""
    try:
        summary = EvaluationService.get_evaluation_by_id(db=db, evaluation_run_id=evaluation_id)
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evaluation run {evaluation_id} not found.",
            )
        return APIResponse(
            success=True,
            message=f"Evaluation run {evaluation_id} retrieved successfully.",
            data=EvaluationSummary(**summary),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch evaluation run {evaluation_id}: {str(e)}",
        )


@router.get("/mismatches", response_model=APIResponse[List[MismatchDetail]])
def get_evaluation_mismatches(
    evaluation_id: Optional[str] = Query(None, description="Evaluation run ID (defaults to latest run)"),
    db: Session = Depends(get_db),
):
    """Gets classification mismatches/incorrect decisions for an evaluation run."""
    try:
        mismatches = EvaluationService.get_mismatches(db=db, evaluation_run_id=evaluation_id)
        return APIResponse(
            success=True,
            message=f"Retrieved {len(mismatches)} mismatch details.",
            data=[MismatchDetail(**m) for m in mismatches],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch mismatches: {str(e)}",
        )


@router.get("/confusion-matrix", response_model=APIResponse[ConfusionMatrixResponse])
def get_evaluation_confusion_matrix(
    evaluation_id: Optional[str] = Query(None, description="Evaluation run ID (defaults to latest run)"),
    db: Session = Depends(get_db),
):
    """Gets the 2x2 confusion matrix (MATCHED vs EXCEPTION) for an evaluation run."""
    try:
        matrix = EvaluationService.get_confusion_matrix(db=db, evaluation_run_id=evaluation_id)
        return APIResponse(
            success=True,
            message="Confusion matrix retrieved successfully.",
            data=ConfusionMatrixResponse(**matrix),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch confusion matrix: {str(e)}",
        )
