from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.common import APIResponse
from app.schemas.ai import (
    AIInvestigationResponse,
    BatchAIInvestigationRequest,
    BatchAIInvestigationResponse,
)
from app.models.financial import ExceptionRecord, AIInvestigation
from app.services.ai_investigator import AIExceptionInvestigator

router = APIRouter(prefix="/ai", tags=["AI Exception Investigator"])


@router.post("/investigate/{order_id}", response_model=APIResponse[AIInvestigationResponse])
def investigate_order_exception(
    order_id: str,
    db: Session = Depends(get_db),
):
    """Investigates the latest unresolved exception for the specified order."""
    try:
        # Find the latest unresolved exception
        exception_record = (
            db.query(ExceptionRecord)
            .filter(ExceptionRecord.order_id == order_id, ExceptionRecord.status == "DETECTED")
            .order_by(ExceptionRecord.id.desc())
            .first()
        )

        if not exception_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No unresolved exception found for order {order_id}",
            )

        investigation = AIExceptionInvestigator.investigate_exception(db, exception_record.id)
        
        return APIResponse(
            success=True,
            message="AI Exception investigation completed.",
            data=AIInvestigationResponse.model_validate(investigation),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Investigation failed: {str(e)}",
        )


@router.post("/investigate", response_model=APIResponse[BatchAIInvestigationResponse])
def investigate_batch_exceptions(
    payload: BatchAIInvestigationRequest,
    db: Session = Depends(get_db),
):
    """Investigates unresolved exceptions from a reconciliation run up to max_cases."""
    try:
        # Get all unresolved exceptions for this run
        exceptions = (
            db.query(ExceptionRecord)
            .filter(
                ExceptionRecord.run_id == payload.reconciliation_run_id,
                ExceptionRecord.status == "DETECTED",
            )
            .order_by(ExceptionRecord.id.asc())
            .all()
        )

        total_exceptions = len(exceptions)
        cases_to_investigate = exceptions[: payload.max_cases]
        investigated_cases = len(cases_to_investigate)

        successful_investigations = 0
        failed_investigations = 0
        human_review_required = 0

        for exc in cases_to_investigate:
            try:
                investigation = AIExceptionInvestigator.investigate_exception(db, exc.id)
                if investigation.investigation_status == "AI_FAILED":
                    failed_investigations += 1
                else:
                    successful_investigations += 1

                if investigation.requires_human_review:
                    human_review_required += 1
            except Exception:
                failed_investigations += 1
                human_review_required += 1

        batch_result = BatchAIInvestigationResponse(
            total_exceptions=total_exceptions,
            investigated_cases=investigated_cases,
            successful_investigations=successful_investigations,
            failed_investigations=failed_investigations,
            human_review_required=human_review_required,
        )

        return APIResponse(
            success=True,
            message=f"Batch investigation complete. Processed {investigated_cases}/{total_exceptions} exceptions.",
            data=batch_result,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch investigation run failed: {str(e)}",
        )


@router.get("/investigations", response_model=APIResponse[List[AIInvestigationResponse]])
def get_ai_investigations(
    investigation_status: Optional[str] = Query(None, description="Filter by status"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    confidence_level: Optional[str] = Query(None, description="Filter by confidence level"),
    requires_human_review: Optional[bool] = Query(None, description="Filter by whether human review is required"),
    db: Session = Depends(get_db),
):
    """Retrieves list of all AI investigations with optional filters."""
    try:
        query = db.query(AIInvestigation)

        if investigation_status:
            query = query.filter(AIInvestigation.investigation_status == investigation_status)
        if exception_type:
            query = query.filter(AIInvestigation.exception_type == exception_type)
        if confidence_level:
            query = query.filter(AIInvestigation.confidence_level == confidence_level)
        if requires_human_review is not None:
            query = query.filter(AIInvestigation.requires_human_review == requires_human_review)

        investigations = query.all()
        data_list = [AIInvestigationResponse.model_validate(inv) for inv in investigations]

        return APIResponse(
            success=True,
            message=f"Retrieved {len(investigations)} AI investigation records.",
            data=data_list,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch investigations: {str(e)}",
        )


@router.get("/investigations/{investigation_id}", response_model=APIResponse[AIInvestigationResponse])
def get_ai_investigation_by_id(
    investigation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves details of a specific AI investigation by its unique ID."""
    try:
        investigation = (
            db.query(AIInvestigation)
            .filter(AIInvestigation.investigation_id == investigation_id)
            .first()
        )

        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"AI Investigation with ID {investigation_id} not found.",
            )

        return APIResponse(
            success=True,
            message=f"AI Investigation {investigation_id} retrieved successfully.",
            data=AIInvestigationResponse.model_validate(investigation),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch investigation {investigation_id}: {str(e)}",
        )
