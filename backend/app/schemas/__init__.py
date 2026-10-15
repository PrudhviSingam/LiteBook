from app.schemas.common import APIResponse, PaginatedResponse
from app.schemas.document import DocumentBase, DocumentCreate, DocumentResponse
from app.schemas.history import HistoryRecordBase, HistoryRecordCreate, HistoryRecordResponse
from app.schemas.dashboard import DashboardSummary

__all__ = [
    "APIResponse",
    "PaginatedResponse",
    "DocumentBase",
    "DocumentCreate",
    "DocumentResponse",
    "HistoryRecordBase",
    "HistoryRecordCreate",
    "HistoryRecordResponse",
    "DashboardSummary",
]
