from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from app.schemas.history import HistoryRecordResponse


class AttentionItem(BaseModel):
    id: str
    severity: str
    finding_type: str
    title: str
    document_name: str
    document_id: Optional[int] = None
    financial_period: Optional[str] = None
    difference: Optional[float] = None
    status: str
    cell_address: Optional[str] = None


class RecentDocumentItem(BaseModel):
    id: int
    original_filename: str
    category: str
    document_type: str
    financial_period: Optional[str] = None
    created_at: str
    status: str
    findings_count: int = 0
    needs_review_count: int = 0
    file_size: int = 0


class DashboardSummary(BaseModel):
    # Backward compatible fields
    total_reports: int = 0
    pending_items: int = 0
    recent_documents: int = 0
    reconciliations: int = 0
    user_name: str
    is_demo_data: bool = False
    recent_activities: List[HistoryRecordResponse] = []

    # Phase 3 Real Accounting Fields
    total_documents: int = 0
    analyzed_documents: int = 0
    needs_review_count: int = 0
    high_severity_count: int = 0
    reconciliation_needs_review: int = 0
    needs_attention_items: List[AttentionItem] = Field(default_factory=list)
    recent_documents_list: List[RecentDocumentItem] = Field(default_factory=list)
