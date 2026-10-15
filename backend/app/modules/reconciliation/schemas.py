from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class ReconciliationStatusEnum(str, Enum):
    MATCHED = "MATCHED"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    MISSING_IN_LEDGER = "MISSING_IN_LEDGER"
    MISSING_IN_BANK = "MISSING_IN_BANK"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DifferenceTypeEnum(str, Enum):
    CHANGED_VALUE = "CHANGED_VALUE"
    MISSING_ROW = "MISSING_ROW"
    EXTRA_ROW = "EXTRA_ROW"
    DUPLICATE_ENTRY = "DUPLICATE_ENTRY"
    UNMATCHED = "UNMATCHED"
    MATCHED = "MATCHED"


class NormalizedTransaction(BaseModel):
    id: str
    date: str  # YYYY-MM-DD
    description: str
    reference: str = ""
    debit: float = 0.0
    credit: float = 0.0
    amount: float = 0.0
    direction: str = "debit"  # "debit" | "credit"
    source: str = "bank"  # "bank" | "ledger" | "source_a" | "source_b"
    raw_row: Dict[str, Any] = Field(default_factory=dict)
    # Complete Provenance (Phase 4)
    document_id: Optional[int] = None
    filename: Optional[str] = None
    sheet_name: Optional[str] = None
    source_type: Optional[str] = None
    original_row_number: Optional[int] = None
    cell_addresses: Dict[str, str] = Field(default_factory=dict)


class ColumnMappingPreview(BaseModel):
    filename: str
    total_rows: int
    detected_columns: List[str]
    column_mapping: Dict[str, Optional[str]]
    sample_rows: List[Dict[str, Any]]
    status: str = "ready"  # "ready" | "REVIEW_REQUIRED" | "AMBIGUOUS"
    message: Optional[str] = None
    sheet_names: List[str] = Field(default_factory=list)
    selected_sheet: Optional[str] = None
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    available_columns: List[str] = Field(default_factory=list)


class ReconciliationRuleConfig(BaseModel):
    date_tolerance_days: int = Field(default=1, ge=0, le=30)
    amount_tolerance: float = Field(default=0.0, ge=0.0)
    match_keys: List[str] = Field(default_factory=lambda: ["reference", "date", "amount"])


class MatchingFactors(BaseModel):
    amount_match: bool
    date_match: bool
    reference_match: bool
    description_similarity: float = 0.0


class SourceLocation(BaseModel):
    file_name: str = ""
    sheet_name: str = ""
    row_number: Optional[int] = None
    cell_address: Optional[str] = None


class ReconciliationItem(BaseModel):
    id: str
    item_id: Optional[str] = None
    status: ReconciliationStatusEnum
    difference_type: Optional[DifferenceTypeEnum] = None
    bank_transaction: Optional[NormalizedTransaction] = None
    ledger_transaction: Optional[NormalizedTransaction] = None
    bank_date: Optional[str] = None
    ledger_date: Optional[str] = None
    description: str = ""
    reference: Optional[str] = ""
    bank_amount: Optional[float] = None
    ledger_amount: Optional[float] = None
    difference: float = 0.0
    confidence: str = "high"  # "high" | "medium" | "low"
    matching_factors: MatchingFactors
    match_tier: Optional[int] = None
    reason: str
    suggested_action: str
    # Difference Detection Specific Fields
    relevant_field: Optional[str] = None
    source_a_location: Optional[SourceLocation] = None
    source_b_location: Optional[SourceLocation] = None
    source_a_value: Optional[Any] = None
    source_b_value: Optional[Any] = None
    source_a_entry: Optional[Dict[str, Any]] = None
    source_b_entry: Optional[Dict[str, Any]] = None
    review_status: str = "PENDING_REVIEW"

    @model_validator(mode="after")
    def populate_item_id(self):
        if not self.item_id:
            self.item_id = self.id
        return self


class ReconciliationSummary(BaseModel):
    total_bank_transactions: int
    total_ledger_transactions: int
    matched_count: int
    unmatched_count: int
    amount_mismatch_count: int
    date_mismatch_count: int
    reference_mismatch_count: int
    missing_in_ledger_count: int
    missing_in_bank_count: int
    possible_duplicate_count: int
    reconciliation_rate: float
    total_bank_amount: float
    total_ledger_amount: float
    total_variance: float
    # Difference Detection Counts
    changed_value_count: int = 0
    missing_row_count: int = 0
    extra_row_count: int = 0
    duplicate_count: int = 0
    unmatched_record_count: int = 0
    # Difference Detection Convenience Aliases
    total_discrepancies: int = 0
    matched_records: int = 0
    match_rate_percentage: float = 0.0
    missing_rows: int = 0
    extra_rows: int = 0

    @model_validator(mode="after")
    def populate_difference_aliases(self):
        if self.total_discrepancies == 0 and self.unmatched_count > 0:
            self.total_discrepancies = self.unmatched_count
        if self.matched_records == 0 and self.matched_count > 0:
            self.matched_records = self.matched_count
        if self.match_rate_percentage == 0.0 and self.reconciliation_rate > 0:
            self.match_rate_percentage = self.reconciliation_rate
        if self.missing_rows == 0 and self.missing_row_count > 0:
            self.missing_rows = self.missing_row_count
        if self.extra_rows == 0 and self.extra_row_count > 0:
            self.extra_rows = self.extra_row_count
        return self


class ReconciliationSessionResponse(BaseModel):
    id: int
    session_id: Optional[int] = None
    bank_statement_name: str
    ledger_file_name: str
    status: str
    summary: ReconciliationSummary
    transactions: List[ReconciliationItem]
    items: Optional[List[ReconciliationItem]] = None
    created_at: str
    file_a_name: Optional[str] = None
    file_b_name: Optional[str] = None
    sheet_a_name: Optional[str] = None
    sheet_b_name: Optional[str] = None
    excel_report_url: Optional[str] = None
    difference_summary: Optional[Dict[str, Any]] = None

    @model_validator(mode="after")
    def populate_session_id_and_items(self):
        if self.session_id is None:
            self.session_id = self.id
        if self.items is None:
            self.items = self.transactions
        return self


class DocumentTypeEnum(str, Enum):
    BANK_STATEMENT = "BANK_STATEMENT"
    ACCOUNTING_LEDGER = "ACCOUNTING_LEDGER"
    TRIAL_BALANCE = "TRIAL_BALANCE"
    BALANCE_SHEET = "BALANCE_SHEET"
    PROFIT_LOSS = "PROFIT_LOSS"
    CASH_FLOW = "CASH_FLOW"
    GENERAL_LEDGER = "GENERAL_LEDGER"
    FINANCIAL_STATEMENT = "FINANCIAL_STATEMENT"
    TAX_DOCUMENT = "TAX_DOCUMENT"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DiscrepancyTypeEnum(str, Enum):
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DATE_MISMATCH = "DATE_MISMATCH"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    MISSING_IN_BANK = "MISSING_IN_BANK"
    MISSING_IN_LEDGER = "MISSING_IN_LEDGER"
    DUPLICATE_TRANSACTION = "DUPLICATE_TRANSACTION"
    BALANCE_SHEET_IMBALANCE = "BALANCE_SHEET_IMBALANCE"
    TRIAL_BALANCE_IMBALANCE = "TRIAL_BALANCE_IMBALANCE"
    FORMULA_ERROR = "FORMULA_ERROR"
    MISSING_VALUE = "MISSING_VALUE"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    CLASSIFICATION_CONFLICT = "CLASSIFICATION_CONFLICT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class DiscrepancySeverityEnum(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FinancialPeriod(BaseModel):
    period_type: str = "FINANCIAL_YEAR"  # "FINANCIAL_YEAR" | "CALENDAR_YEAR" | "QUARTER" | "DATE_RANGE" | "UNKNOWN" | "CONFLICT"
    raw_text: str = ""
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None    # YYYY-MM-DD
    financial_year: Optional[str] = None  # e.g. "2025-26" or "FY 2025-26"
    confidence: str = "HIGH"
    source: str = "headers"
    status: str = "ready"  # "ready" | "REVIEW_REQUIRED"
    message: Optional[str] = None


class ClassificationEvidence(BaseModel):
    document_type: DocumentTypeEnum
    confidence: str = "HIGH"
    signals_found: List[str] = Field(default_factory=list)
    explanation: str = ""
    score: float = 1.0


class FinancialCellProvenance(BaseModel):
    sheet_name: str
    cell_address: str  # e.g. "H42", "C19"
    row_number: int
    column_number: int
    column_name: Optional[str] = None
    raw_value: Any = None
    normalized_value: Optional[float] = None
    formula: Optional[str] = None
    unit: Optional[str] = None  # "INR" | "LAKH" | "CRORE"


class FinancialRow(BaseModel):
    table_id: str
    row_number: int
    label: str
    row_type: str = "LINE_ITEM"  # "HEADER" | "SECTION" | "LINE_ITEM" | "SUBTOTAL" | "TOTAL"
    values: Dict[str, Any] = Field(default_factory=dict)
    normalized_values: Dict[str, Optional[float]] = Field(default_factory=dict)
    source_cells: Dict[str, FinancialCellProvenance] = Field(default_factory=dict)


class FinancialTable(BaseModel):
    table_id: str
    document_id: Optional[int] = None
    sheet_name: str
    table_range: Optional[str] = None
    header_row: int
    data_start_row: int
    data_end_row: int
    table_type: DocumentTypeEnum
    period: Optional[FinancialPeriod] = None
    currency: str = "INR"
    unit: str = "ACTUAL"  # "ACTUAL" | "LAKH" | "CRORE"
    confidence: str = "HIGH"
    rows: List[FinancialRow] = Field(default_factory=list)
    totals: Dict[str, float] = Field(default_factory=dict)


class StandardDiscrepancy(BaseModel):
    id: str
    document_id: Optional[int] = None
    type: DiscrepancyTypeEnum
    severity: DiscrepancySeverityEnum
    status: str = "DETECTED"
    description: str
    expected_value: Optional[Any] = None
    actual_value: Optional[Any] = None
    difference: Optional[float] = None
    currency: str = "INR"
    sheet_name: Optional[str] = None
    cell_address: Optional[str] = None
    source_reference: Optional[str] = None
    confidence: str = "HIGH"
    evidence: List[str] = Field(default_factory=list)
    possible_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    created_at: Optional[str] = None


class SheetInspectionInfo(BaseModel):
    sheet_name: str
    row_count: int
    col_count: int
    detected_columns: List[str]
    classification: DocumentTypeEnum
    header_row_index: int
    period_columns: List[str] = []
    has_merged_cells: bool = False
    confidence: str = "HIGH"
    is_recommended: bool = False
    classification_evidence: Optional[ClassificationEvidence] = None
    period_info: Optional[FinancialPeriod] = None
    unit: Optional[str] = "ACTUAL"
    tables: List[FinancialTable] = Field(default_factory=list)


class WorkbookInspectionResult(BaseModel):
    filename: str
    total_sheets: int
    sheets: List[SheetInspectionInfo]
    recommended_sheet: str
    document_type: DocumentTypeEnum
    header_row_index: int
    period_columns: List[str] = []
    confidence: str = "HIGH"
    status: str = "ready"  # "ready" | "REVIEW_REQUIRED"
    message: Optional[str] = None
    sample_data: List[Dict[str, Any]] = []
    period_info: Optional[FinancialPeriod] = None
    classification_evidence: Optional[ClassificationEvidence] = None
    tables: List[FinancialTable] = Field(default_factory=list)
    discrepancies: List[StandardDiscrepancy] = Field(default_factory=list)


class DiscrepancyExplainRequest(BaseModel):
    discrepancy_data: Dict[str, Any]
    comparison_records: List[Dict[str, Any]] = Field(default_factory=list)
    document_metadata: Dict[str, Any] = Field(default_factory=dict)


class DiscrepancyExplanationResponse(BaseModel):
    what: str
    where: Dict[str, Any]
    original_value: Any
    expected_value: Any
    difference: float
    reason_category: str
    summary: str
    possible_reasons: List[str]
    proposed_correction: Optional[Dict[str, Any]] = None
    evidence: List[str]
    recommended_verification: List[str]
    confidence: str = "HIGH"


class CorrectionStatusEnum(str, Enum):
    PROPOSED = "PROPOSED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    GENERATED = "GENERATED"
    FAILED = "FAILED"


class CorrectionProposalSchema(BaseModel):
    correction_id: str
    session_id: Optional[int] = None
    document_id: Optional[int] = None
    sheet_name: str = "Sheet1"
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
    accountant_decision: Optional[str] = None
    decision_notes: Optional[str] = None
    created_at: Optional[str] = None



class CorrectionDecisionRequest(BaseModel):
    decision: str  # "CONFIRMED" | "REJECTED" | "MANUAL_REVIEW"
    notes: Optional[str] = None


class GenerateCorrectedWorkbookResponse(BaseModel):
    success: bool
    original_filename: str
    generated_filename: str
    download_url: str
    document_id: Optional[int] = None
    applied_corrections_count: int
    corrections_sheet_name: str = "AI Correction Log"
    message: str

