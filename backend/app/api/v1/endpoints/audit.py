"""
Audit Trail — read-only endpoint for ResolutionEvent records.

This endpoint exposes the immutable audit trail that is written by the
ResolutionOrchestrator every time a resolution status changes (SYSTEM or HUMAN).

Rules:
  - GET only. No mutations.
  - Financial records are never returned here.
  - Filtering is optional and additive.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.resolution import ResolutionEventResponse
from app.models.financial import ResolutionEvent, Resolution

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


@router.get("/events", response_model=APIResponse[List[ResolutionEventResponse]])
def get_audit_events(
    resolution_id: Optional[str] = Query(None, description="Filter by resolution ID"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (SYSTEM, HUMAN)"),
    new_status: Optional[str] = Query(None, description="Filter by new status after transition"),
    limit: int = Query(default=500, ge=1, le=2000, description="Maximum events to return"),
    db: Session = Depends(get_db),
):
    """
    Returns the immutable audit trail of all resolution status transitions.

    Events are ordered newest-first. Each event captures:
      - Which resolution was affected
      - Previous and new status
      - Who triggered the change (SYSTEM or HUMAN)
      - The reason or reviewer notes
      - Timestamp

    Audit events are immutable — they are never modified after creation.
    Financial transaction records (Order, Payment, Settlement) are never
    modified by the resolution workflow.
    """
    try:
        query = db.query(ResolutionEvent)

        if resolution_id:
            query = query.filter(ResolutionEvent.resolution_id == resolution_id)
        if actor_type:
            query = query.filter(ResolutionEvent.actor_type == actor_type.upper())
        if new_status:
            query = query.filter(ResolutionEvent.new_status == new_status.upper())

        events = (
            query
            .order_by(ResolutionEvent.created_at.desc())
            .limit(limit)
            .all()
        )

        return APIResponse(
            success=True,
            message=f"{len(events)} audit event(s) retrieved.",
            data=[ResolutionEventResponse.model_validate(e) for e in events],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve audit events: {str(e)}",
        )


@router.get(
    "/events/resolution/{resolution_id}",
    response_model=APIResponse[List[ResolutionEventResponse]],
)
def get_events_for_resolution(
    resolution_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns all audit events for a specific resolution, ordered chronologically.
    This shows the full status-transition history of one case.
    """
    try:
        # Verify resolution exists
        res = db.query(Resolution).filter(Resolution.resolution_id == resolution_id).first()
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resolution {resolution_id} not found.",
            )

        events = (
            db.query(ResolutionEvent)
            .filter(ResolutionEvent.resolution_id == resolution_id)
            .order_by(ResolutionEvent.created_at.asc())
            .all()
        )

        return APIResponse(
            success=True,
            message=f"{len(events)} event(s) for resolution {resolution_id}.",
            data=[ResolutionEventResponse.model_validate(e) for e in events],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve events: {str(e)}",
        )
