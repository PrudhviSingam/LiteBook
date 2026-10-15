from sqlalchemy import Column, String, Integer, Text, Float
from app.models.base import BaseModel


class ProcessingJob(BaseModel):
    __tablename__ = "processing_jobs"

    job_type = Column(String(50), nullable=False)  # e.g., "reconciliation", "ocr_extraction", "gst_check"
    status = Column(String(50), default="pending", nullable=False)  # pending, processing, completed, failed
    progress = Column(Float, default=0.0, nullable=False)  # 0.0 to 100.0
    error_message = Column(Text, nullable=True)
    metadata_payload = Column(Text, nullable=True)  # JSON-encoded payload
