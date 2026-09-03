from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.resolution import (
    ReviewQueueItem,
    ResolutionResponse,
    HumanDecisionRequest,
    UnresolveRequest,
)
from app.services.resolution import ResolutionOrchestrator

router = APIRouter(prefix="/review", tags=["Human Review Workflow"])


@router.get("/queue", response_model=APIResponse[List[ReviewQueueItem]])
def get_review_queue(
    resolution_status: Optional[str] = Query(None, description="Filter by resolution status"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    confidence_level: Optional[str] = Query(None, description="Filter by confidence level"),
    reconciliation_run_id: Optional[str] = Query(None, description="Filter by reconciliation run ID"),
    db: Session = Depends(get_db),
):
    """Returns cases requiring human review, ordered by priority score."""
    try:
        items = ResolutionOrchestrator.get_review_queue(
            db=db,
            resolution_status=resolution_status,
            exception_type=exception_type,
            confidence_level=confidence_level,
            reconciliation_run_id=reconciliation_run_id,
        )
        return APIResponse(
            success=True,
            message="Review queue retrieved.",
            data=[ReviewQueueItem.model_validate(item) for item in items],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve review queue: {str(e)}",
        )


@router.get("/queue/{resolution_id}", response_model=APIResponse[dict])
def get_queue_detail(
    resolution_id: str,
    db: Session = Depends(get_db),
):
    """Returns complete case information for a given resolution record."""
    try:
        detail = ResolutionOrchestrator.get_queue_detail(db, resolution_id)
        res = detail.get("resolution")
        ai_inv = detail.get("ai_investigation") or {}

        response_data = {
            "order": detail.get("order"),
            "payments": detail.get("payments"),
            "settlements": detail.get("settlements"),
            "exception": detail.get("exception"),
            "ai_investigation": detail.get("ai_investigation"),
            "confidence": res.get("effective_confidence") if res else None,
            "safety_flags": res.get("safety_flags") if res else [],
            "evidence_facts": ai_inv.get("evidence_facts", []) if ai_inv else [],
            "possible_causes": ai_inv.get("possible_causes", []) if ai_inv else [],
            "evidence_gaps": ai_inv.get("evidence_gaps", []) if ai_inv else [],
            "recommended_action": ai_inv.get("recommended_action") if ai_inv else None,
            "current_resolution_status": res.get("resolution_status") if res else None,
        }
        return APIResponse(
            success=True,
            message="Case detail retrieved.",
            data=response_data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve case detail: {str(e)}",
        )


@router.post("/{resolution_id}/approve", response_model=APIResponse[ResolutionResponse])
def approve_case(
    resolution_id: str,
    payload: HumanDecisionRequest,
    db: Session = Depends(get_db),
):
    """Approve a proposed resolution."""
    try:
        updated = ResolutionOrchestrator.approve(
            db=db,
            resolution_id=resolution_id,
            notes=payload.notes,
        )
        return APIResponse(
            success=True,
            message="Case resolution approved by human.",
            data=ResolutionResponse.model_validate(updated),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve case: {str(e)}",
        )


@router.post("/{resolution_id}/reject", response_model=APIResponse[ResolutionResponse])
def reject_case(
    resolution_id: str,
    payload: HumanDecisionRequest,
    db: Session = Depends(get_db),
):
    """Reject a proposed resolution. The case remains unresolved."""
    try:
        updated = ResolutionOrchestrator.reject(
            db=db,
            resolution_id=resolution_id,
            notes=payload.notes,
        )
        return APIResponse(
            success=True,
            message="Case resolution rejected by human.",
            data=ResolutionResponse.model_validate(updated),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject case: {str(e)}",
        )


@router.post("/{resolution_id}/unresolve", response_model=APIResponse[ResolutionResponse])
def unresolve_case(
    resolution_id: str,
    payload: UnresolveRequest,
    db: Session = Depends(get_db),
):
    """Reopen a previously resolved case, setting status back to UNRESOLVED."""
    try:
        updated = ResolutionOrchestrator.unresolve(
            db=db,
            resolution_id=resolution_id,
            reason=payload.reason,
        )
        return APIResponse(
            success=True,
            message="Case reopened / marked unresolved.",
            data=ResolutionResponse.model_validate(updated),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reopen case: {str(e)}",
        )
