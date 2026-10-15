from sqlalchemy import Column, String, Integer, Text, Float, DateTime, ForeignKey
from app.models.base import BaseModel


class ReconciliationSession(BaseModel):
    __tablename__ = "reconciliation_sessions"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)

    bank_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    ledger_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    bank_statement_name = Column(String(255), nullable=False)
    ledger_file_name = Column(String(255), nullable=False)

    status = Column(String(50), default="completed", nullable=False, index=True)

    total_bank_entries = Column(Integer, default=0, nullable=False)
    total_ledger_entries = Column(Integer, default=0, nullable=False)

    matched_count = Column(Integer, default=0, nullable=False)
    mismatched_count = Column(Integer, default=0, nullable=False)
    unmatched_bank_count = Column(Integer, default=0, nullable=False)
    unmatched_ledger_count = Column(Integer, default=0, nullable=False)

    total_matched_amount = Column(Float, default=0.0, nullable=False)
    total_variance = Column(Float, default=0.0, nullable=False)

    # Detailed structured payload stored as JSON
    details_json = Column(Text, nullable=False)


class CorrectionProposal(BaseModel):
    __tablename__ = "reconciliation_corrections"

    correction_id = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(Integer, ForeignKey("reconciliation_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)

    sheet_name = Column(String(100), default="Sheet1", nullable=False)
    cell_address = Column(String(20), nullable=True)  # Exact cell coordinate e.g. "C12", "H42"
    row_reference = Column(String(50), nullable=False)
    field = Column(String(100), nullable=False)

    original_value = Column(Text, nullable=True)
    proposed_value = Column(Text, nullable=True)
    difference = Column(Float, default=0.0, nullable=False)

    reason_category = Column(String(50), default="AMOUNT_MISMATCH", nullable=False)
    explanation = Column(Text, nullable=False)
    evidence_json = Column(Text, default="[]", nullable=False)
    recommended_verification_json = Column(Text, default="[]", nullable=False)

    confidence = Column(String(20), default="HIGH", nullable=False)
    status = Column(String(50), default="PROPOSED", nullable=False, index=True)  # PROPOSED, CONFIRMED, REJECTED, GENERATED/APPLIED, FAILED
    accountant_decision = Column(String(50), nullable=True)
    decision_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    original_sha256 = Column(String(64), nullable=True)
    corrected_sha256 = Column(String(64), nullable=True)


