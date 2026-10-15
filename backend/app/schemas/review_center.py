from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReviewFindingItem(BaseModel):
    id: str
    document_id: Optional[int] = None
    document_name: str
    session_id: Optional[int] = None
    category: str = "general"
    financial_period: Optional[str] = None
    type: str
    severity: str  # HIGH, MEDIUM, LOW, CRITICAL, INFO
    status: str  # NEEDS_REVIEW, UNDER_REVIEW, APPROVED, REJECTED, IGNORED, CORRECTED, REVIEW_REQUIRED
    title: str
    description: str
    expected_value: Optional[float] = None
    actual_value: Optional[float] = None
    difference: Optional[float] = None
    currency: str = "INR"
    sheet_name: Optional[str] = None
    cell_address: Optional[str] = None
    row_reference: Optional[str] = None
    column_reference: Optional[str] = None
    formula: Optional[str] = None
    confidence: str = "Deterministic"  # Deterministic, HIGH, MEDIUM, LOW, REVIEW_REQUIRED
    proven_cause: Optional[str] = None
    possible_causes: List[str] = Field(default_factory=list)
    ai_explanation: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    correction_id: Optional[str] = None
    original_value_display: Optional[str] = None
    proposed_value_display: Optional[str] = None
    created_at: Optional[str] = None
    reviewed_at: Optional[str] = None
    accountant_decision: Optional[str] = None
    decision_notes: Optional[str] = None


class ReviewCenterSummary(BaseModel):
    all_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    review_required_count: int = 0
    reviewed_count: int = 0
    findings: List[ReviewFindingItem] = Field(default_factory=list)


class FindingDecisionRequest(BaseModel):
    decision: str  # APPROVE, REJECT, IGNORE, UNDER_REVIEW
    notes: Optional[str] = None
    propose_correction: bool = False
    proposed_value: Optional[str] = None
