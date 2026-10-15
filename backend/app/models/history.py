from sqlalchemy import Column, String, Text, Integer, ForeignKey
from app.models.base import BaseModel


class HistoryRecord(BaseModel):
    __tablename__ = "history_records"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    # Module: "reconciliation", "gst", "itr", "financial_statements", "documents", "ai_assistant", "system"
    module = Column(String(50), nullable=False, index=True)

    # Action type: "reconciliation_completed", "gst_analysis_completed", "financial_statement_generated", "document_uploaded", etc.
    action = Column(String(100), nullable=False, index=True)

    # Human-readable title/name of the document, report, or batch
    target_name = Column(String(255), nullable=False)

    # Status: "completed", "pending", "in_progress", "failed"
    status = Column(String(50), default="completed", nullable=False, index=True)

    # Result summary (e.g. "Reconciled 142 items with 2 discrepancies flagged")
    result_summary = Column(Text, nullable=True)

    # User action description or trigger origin
    user_action = Column(String(255), default="Manual action by user", nullable=False)

    # Reference link or identifier for any generated report / file
    report_reference = Column(String(255), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
