from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class HistoryRecordBase(BaseModel):
    module: str
    action: str
    target_name: str
    status: str = "completed"
    result_summary: Optional[str] = None
    user_action: str = "Manual action by user"
    report_reference: Optional[str] = None
    document_id: Optional[int] = None


class HistoryRecordCreate(HistoryRecordBase):
    pass


class HistoryRecordResponse(HistoryRecordBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
