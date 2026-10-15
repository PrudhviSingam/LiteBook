from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    category: str = "general"
    notes: Optional[str] = None


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: int
    original_filename: str
    stored_filename: str
    file_size: int
    mime_type: str
    status: str
    checksum: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentResetResponse(BaseModel):
    success: bool = True
    documents_deleted: int = 0
    derived_records_deleted: int = 0
    files_deleted: int = 0
