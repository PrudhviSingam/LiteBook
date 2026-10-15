from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AssistantIntentEnum(str, Enum):
    GENERAL_ACCOUNTING = "GENERAL_ACCOUNTING"
    FILE_SUMMARY = "FILE_SUMMARY"
    FIND_MISMATCH = "FIND_MISMATCH"
    FIND_MISSING_RECORD = "FIND_MISSING_RECORD"
    COMPARE_FILES = "COMPARE_FILES"
    EXPLAIN_DISCREPANCY = "EXPLAIN_DISCREPANCY"
    EXPLAIN_ROW = "EXPLAIN_ROW"
    RECONCILIATION_HELP = "RECONCILIATION_HELP"
    CORRECTION_REQUEST = "CORRECTION_REQUEST"
    DOCUMENTS_QUERY = "DOCUMENTS_QUERY"
    DOCUMENT_METADATA = "DOCUMENT_METADATA"
    FORMULA_QUERY = "FORMULA_QUERY"
    RECONCILIATION_QUERY = "RECONCILIATION_QUERY"
    EXPLANATION_QUERY = "EXPLANATION_QUERY"
    FOLLOW_UP_QUERY = "FOLLOW_UP_QUERY"
    FILE_SAFETY_QUERY = "FILE_SAFETY_QUERY"
    UNVERIFIED_DATA_QUERY = "UNVERIFIED_DATA_QUERY"
    UNKNOWN = "UNKNOWN"


class FileContextInfo(BaseModel):
    document_id: int
    filename: str
    document_type: str
    sheet_name: str
    period: Optional[str] = None
    status: str = "ready"
    row_count: int = 0
    columns: List[str] = Field(default_factory=list)
    sample_data: List[Dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None


class DiscrepancyFinding(BaseModel):
    title: str
    location: str
    sheet: str
    cell_address: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    difference: Optional[str] = None
    reason_category: str
    summary: str
    possible_reasons: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    recommended_verification: List[str] = Field(default_factory=list)
    confidence: str = "HIGH"
    # Phase 13 & 14 Provenance and Finding Model
    finding_id: Optional[str] = None
    finding_type: Optional[str] = None
    severity: Optional[str] = "MEDIUM"
    status: Optional[str] = "VERIFIED"
    ledger_evidence: Optional[Dict[str, Any]] = None
    bank_evidence: Optional[Dict[str, Any]] = None
    possible_cause: Optional[str] = None
    proven_cause: Optional[str] = None


class CorrectionProposalInfo(BaseModel):
    correction_id: str
    document_id: Optional[int] = None
    sheet_name: str
    cell_address: Optional[str] = None
    row_reference: Any
    field: str
    original_value: Any
    proposed_value: Any
    difference: float
    reason_category: str
    explanation: str
    evidence: List[str] = Field(default_factory=list)
    recommended_verification: List[str] = Field(default_factory=list)
    confidence: str = "HIGH"
    status: str = "PROPOSED"



class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    file_ids: List[int] = Field(default_factory=list)


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    intent: AssistantIntentEnum
    files: List[FileContextInfo] = Field(default_factory=list)
    findings: List[DiscrepancyFinding] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    correction_available: bool = False
    correction_id: Optional[str] = None
    proposal: Optional[CorrectionProposalInfo] = None
    confidence: str = "HIGH"


class AnalyzeRequest(BaseModel):
    document_id: int
    conversation_id: Optional[str] = None
    prompt: Optional[str] = "Analyze this file for accounting discrepancies."


class CompareRequest(BaseModel):
    file_a_id: int
    file_b_id: int
    conversation_id: Optional[str] = None
    prompt: Optional[str] = None


class CorrectionReviewDecisionRequest(BaseModel):
    decision: str  # CONFIRMED | REJECTED | MANUAL_REVIEW
    notes: Optional[str] = None


class GenerateCorrectedCopyRequest(BaseModel):
    correction_id: str
    accountant_name: str = "Partner Accountant"
