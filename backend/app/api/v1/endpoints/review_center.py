from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.review_center import FindingDecisionRequest, ReviewCenterSummary, ReviewFindingItem
from app.services.review_center_service import ReviewCenterService

router = APIRouter()


@router.get("/findings", response_model=ReviewCenterSummary)
def list_review_findings(
    severity: Optional[str] = Query(None, description="Filter by severity: HIGH, MEDIUM, LOW, ALL"),
    status: Optional[str] = Query(None, description="Filter by status: NEEDS_REVIEW, REVIEW_REQUIRED, UNDER_REVIEW, APPROVED, REJECTED, REVIEWED, ALL"),
    document_id: Optional[int] = Query(None, description="Filter by document ID"),
    search: Optional[str] = Query(None, description="Search term in title, document, description, or cell"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves all financial findings and discrepancies requiring accountant review for current user."""
    return ReviewCenterService.get_findings(
        db=db,
        user_id=current_user.id,
        severity_filter=severity,
        status_filter=status,
        document_id_filter=document_id,
        search_query=search,
    )


@router.post("/findings/{finding_id}/decision", response_model=ReviewFindingItem)
def update_finding_decision(
    finding_id: str,
    req: FindingDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates accountant decision (APPROVE, REJECT, IGNORE, UNDER_REVIEW) on a financial finding."""
    return ReviewCenterService.update_finding_decision(
        db=db,
        finding_id=finding_id,
        req=req,
        user_id=current_user.id,
    )
