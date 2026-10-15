from sqlalchemy import Column, String, Text, BigInteger
from app.models.base import BaseModel


class GeneratedReport(BaseModel):
    __tablename__ = "generated_reports"

    title = Column(String(255), nullable=False)
    report_type = Column(String(50), nullable=False)  # "reconciliation", "gst_return", "itr_summary", "pnl", "balance_sheet"
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, default=0, nullable=False)
    mime_type = Column(String(100), default="application/pdf", nullable=False)
    summary = Column(Text, nullable=True)
