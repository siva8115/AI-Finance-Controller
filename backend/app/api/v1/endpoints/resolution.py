from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.resolution import (
    ResolutionResponse,
    BatchResolutionRequest,
    BatchResolutionResponse,
    ResolutionSummaryResponse,
)
from app.models.financial import ExceptionRecord, AIInvestigation
from app.services.resolution import ResolutionOrchestrator

router = APIRouter(prefix="/resolution", tags=["Resolution Orchestrator"])


@router.post("/run/{order_id}", response_model=APIResponse[ResolutionResponse])
def run_resolution_for_order(
    order_id: str,
    db: Session = Depends(get_db),
):
    """Triggers the deterministic resolution policy for the latest unresolved exception of an order."""
    # 1. Find latest unresolved exception
    exc = (
        db.query(ExceptionRecord)
        .filter(ExceptionRecord.order_id == order_id, ExceptionRecord.status == "DETECTED")
        .order_by(ExceptionRecord.id.desc())
        .first()
    )
    if not exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No unresolved exception found for order {order_id}",
        )

    # 2. Find latest AI investigation
    inv = (
        db.query(AIInvestigation)
        .filter(AIInvestigation.exception_id == exc.id)
        .order_by(AIInvestigation.id.desc())
        .first()
    )
    # 3. If investigation doesn't exist, return error (do not auto-call Gemini)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No AI investigation found for exception {exc.id}. Run investigation first.",
        )

    # 4-6. Run policy, persist resolution & ResolutionEvent
    try:
        res = ResolutionOrchestrator.resolve_exception(
            db=db,
            exception_id=exc.id,
            investigation_id=inv.investigation_id,
        )
        return APIResponse(
            success=True,
            message="Deterministic resolution policy executed.",
            data=ResolutionResponse.model_validate(res),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Resolution execution failed: {str(e)}",
        )


@router.post("/run", response_model=APIResponse[BatchResolutionResponse])
def run_batch_resolution(
    payload: BatchResolutionRequest,
    db: Session = Depends(get_db),
):
    """Runs batch resolution for exceptions belonging to a run that have AI investigations."""
    try:
        result = ResolutionOrchestrator.resolve_batch(
            db=db,
            reconciliation_run_id=payload.reconciliation_run_id,
            max_cases=payload.max_cases,
        )
        return APIResponse(
            success=True,
            message="Batch resolution execution completed.",
            data=BatchResolutionResponse.model_validate(result),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch resolution execution failed: {str(e)}",
        )


@router.get("/summary", response_model=APIResponse[ResolutionSummaryResponse])
def get_resolution_summary(
    db: Session = Depends(get_db),
):
    """Returns dynamic resolution summary metrics from actual database records."""
    try:
        summary = ResolutionOrchestrator.get_summary(db)
        return APIResponse(
            success=True,
            message="Resolution summary retrieved.",
            data=ResolutionSummaryResponse.model_validate(summary),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve resolution summary: {str(e)}",
        )
