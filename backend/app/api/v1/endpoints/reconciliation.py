from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.reconciliation import (
    ReconciliationRunRequest,
    ReconciliationRunSummary,
    ReconciliationResultResponse,
    ExceptionRecordResponse,
)
from app.services.reconciliation import ReconciliationService

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation Engine"])


@router.post("/run", response_model=APIResponse[ReconciliationRunSummary])
def run_reconciliation(
    payload: Optional[ReconciliationRunRequest] = None,
    db: Session = Depends(get_db),
):
    """Executes deterministic 3-way financial reconciliation across all orders."""
    try:
        settlement_window = payload.settlement_window_days if payload else None
        monetary_tolerance = payload.monetary_tolerance if payload else None

        summary = ReconciliationService.run_reconciliation(
            db=db,
            settlement_window_days=settlement_window,
            monetary_tolerance=monetary_tolerance,
        )
        return APIResponse(
            success=True,
            message=f"Reconciliation completed for {summary['total_records']} orders: {summary['matched']} matched, {summary['exceptions']} exceptions.",
            data=ReconciliationRunSummary(**summary),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation run failed: {str(e)}",
        )


@router.get("/summary", response_model=APIResponse[Optional[ReconciliationRunSummary]])
def get_reconciliation_summary(db: Session = Depends(get_db)):
    """Gets the summary of the latest reconciliation run."""
    try:
        summary = ReconciliationService.get_latest_summary(db=db)
        if not summary:
            return APIResponse(
                success=True,
                message="No reconciliation runs have been executed yet.",
                data=None,
            )
        return APIResponse(
            success=True,
            message="Latest reconciliation summary retrieved successfully.",
            data=ReconciliationRunSummary(**summary),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch summary: {str(e)}",
        )


@router.get("/results", response_model=APIResponse[List[ReconciliationResultResponse]])
def get_reconciliation_results(
    run_id: Optional[str] = Query(None, description="Reconciliation run ID (defaults to latest run)"),
    status: Optional[str] = Query(None, description="Filter by status: MATCHED or EXCEPTION"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    order_id: Optional[str] = Query(None, description="Filter by order ID"),
    db: Session = Depends(get_db),
):
    """Gets reconciliation results with optional filters."""
    try:
        results = ReconciliationService.get_results(
            db=db,
            run_id=run_id,
            status=status,
            exception_type=exception_type,
            order_id=order_id,
        )
        return APIResponse(
            success=True,
            message=f"Retrieved {len(results)} reconciliation result records.",
            data=[ReconciliationResultResponse(**r) for r in results],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch results: {str(e)}",
        )


@router.get("/results/{order_id}", response_model=APIResponse[ReconciliationResultResponse])
def get_reconciliation_result_by_order(
    order_id: str,
    run_id: Optional[str] = Query(None, description="Reconciliation run ID (defaults to latest run)"),
    db: Session = Depends(get_db),
):
    """Gets reconciliation result details for a specific order."""
    try:
        results = ReconciliationService.get_results(
            db=db,
            run_id=run_id,
            order_id=order_id,
        )
        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reconciliation result for order {order_id} not found.",
            )
        return APIResponse(
            success=True,
            message=f"Reconciliation result for order {order_id} retrieved.",
            data=ReconciliationResultResponse(**results[0]),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch result for order {order_id}: {str(e)}",
        )


@router.get("/exceptions", response_model=APIResponse[List[ExceptionRecordResponse]])
def get_reconciliation_exceptions(
    run_id: Optional[str] = Query(None, description="Reconciliation run ID (defaults to latest run)"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    status: Optional[str] = Query(None, description="Filter by status (default: DETECTED)"),
    db: Session = Depends(get_db),
):
    """Gets all detected exception records from reconciliation."""
    try:
        exceptions = ReconciliationService.get_exceptions(
            db=db,
            run_id=run_id,
            exception_type=exception_type,
            status=status,
        )
        return APIResponse(
            success=True,
            message=f"Retrieved {len(exceptions)} exception records.",
            data=[ExceptionRecordResponse(**e) for e in exceptions],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch exceptions: {str(e)}",
        )
