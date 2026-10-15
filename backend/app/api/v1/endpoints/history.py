from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.history import HistoryRecordCreate, HistoryRecordResponse
from app.services.history_service import HistoryService

router = APIRouter()


@router.get("", response_model=List[HistoryRecordResponse])
def get_history(
    module: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves chronological activity log with module and status filters for current user."""
    return HistoryService.list_history(db, module=module, status=status, user_id=current_user.id, limit=limit)


@router.post("", response_model=HistoryRecordResponse, status_code=status.HTTP_201_CREATED)
def create_history_record(
    payload: HistoryRecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Registers a new action record in the history foundation for current user."""
    return HistoryService.record_activity(
        db=db,
        module=payload.module,
        action=payload.action,
        target_name=payload.target_name,
        status=payload.status,
        result_summary=payload.result_summary,
        user_action=payload.user_action,
        report_reference=payload.report_reference,
        document_id=payload.document_id,
        user_id=current_user.id,
    )

