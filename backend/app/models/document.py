from sqlalchemy import Column, String, Integer, Text, BigInteger, Boolean, ForeignKey
from app.models.base import BaseModel


class Document(BaseModel):
    __tablename__ = "documents"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), unique=True, nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(BigInteger, default=0, nullable=False)  # Size in bytes
    mime_type = Column(String(100), default="application/octet-stream", nullable=False)

    # Category: "bank_statement", "ledger", "sales_data", "purchase_data", "gst", "itr", "financial", "general"
    category = Column(String(50), default="general", nullable=False, index=True)

    # Status: "uploaded", "ready", "processing", "archived", "error"
    status = Column(String(50), default="uploaded", nullable=False, index=True)

    checksum = Column(String(64), nullable=True)  # SHA-256 hash for document integrity
    original_sha256 = Column(String(64), nullable=True)  # Baseline hash for immutability verification
    is_corrected_copy = Column(Boolean, default=False, nullable=False)

    notes = Column(Text, nullable=True)

