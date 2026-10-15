from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class FSProfileBase(BaseModel):
    entity_name: str = Field(..., min_length=1, max_length=255)
    cin_or_pan: Optional[str] = None
    financial_year: str = Field(..., description="Financial Year e.g. 2023-24")
    reporting_period: str = Field(default="ANNUAL", description="ANNUAL, Q1, Q2, Q3, Q4")
    framework: str = Field(default="SCHEDULE_III", description="SCHEDULE_III, IND_AS")


class FSProfileCreate(FSProfileBase):
    pass


class FSProfileUpdate(BaseModel):
    entity_name: Optional[str] = None
    cin_or_pan: Optional[str] = None
    framework: Optional[str] = None


class TrialBalanceEntryCreate(BaseModel):
    account_code: Optional[str] = None
    account_name: str
    account_category: str = Field(default="ASSET", description="ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE")
    debit_amount: Decimal = Field(default=Decimal("0.00"))
    credit_amount: Decimal = Field(default=Decimal("0.00"))
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_cell: Optional[str] = None
    source_value: Optional[str] = None
    provenance_notes: Optional[str] = None


class TrialBalanceEntryResponse(TrialBalanceEntryCreate):
    id: int
    profile_id: int
    net_balance: Decimal
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class BalanceSheetLineCreate(BaseModel):
    classification: str = Field(..., description="NON_CURRENT_ASSETS, CURRENT_ASSETS, EQUITY, NON_CURRENT_LIABILITIES, CURRENT_LIABILITIES")
    sub_category: str
    line_item_name: str
    amount: Decimal = Field(default=Decimal("0.00"))
    schedule_note_number: Optional[str] = None
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_cell: Optional[str] = None
    provenance_notes: Optional[str] = None


class BalanceSheetLineResponse(BalanceSheetLineCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class ProfitLossLineCreate(BaseModel):
    category: str = Field(..., description="REVENUE, OTHER_INCOME, COST_OF_MATERIALS, EMPLOYEE_BENEFITS, FINANCE_COSTS, DEPRECIATION, OTHER_EXPENSES, TAX_EXPENSE")
    line_item_name: str
    amount: Decimal = Field(default=Decimal("0.00"))
    schedule_note_number: Optional[str] = None
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_cell: Optional[str] = None
    provenance_notes: Optional[str] = None


class ProfitLossLineResponse(ProfitLossLineCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class CashFlowLineCreate(BaseModel):
    activity_type: str = Field(..., description="OPERATING, INVESTING, FINANCING")
    line_item_name: str
    amount: Decimal = Field(default=Decimal("0.00"))
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    provenance_notes: Optional[str] = None


class CashFlowLineResponse(CashFlowLineCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class TrialBalanceValidationResponse(BaseModel):
    total_debit: Decimal
    total_credit: Decimal
    difference: Decimal
    is_balanced: bool = False
    entries_count: int = 0
    model_config = ConfigDict(from_attributes=True)


# Fix boolean type to bool
TrialBalanceValidationResponse.model_rebuild()


class BalanceSheetSummaryResponse(BaseModel):
    total_non_current_assets: Decimal
    total_current_assets: Decimal
    total_assets: Decimal
    total_equity: Decimal
    total_non_current_liabilities: Decimal
    total_current_liabilities: Decimal
    total_equity_and_liabilities: Decimal
    balance_difference: Decimal
    is_balanced: bool
    model_config = ConfigDict(from_attributes=True)


class ProfitLossSummaryResponse(BaseModel):
    total_revenue: Decimal
    total_expenses: Decimal
    ebitda: Decimal
    profit_before_tax: Decimal
    tax_expense: Decimal
    profit_after_tax: Decimal
    model_config = ConfigDict(from_attributes=True)


class CashFlowSummaryResponse(BaseModel):
    net_cash_operating: Decimal
    net_cash_investing: Decimal
    net_cash_financing: Decimal
    net_change_in_cash: Decimal
    opening_cash: Decimal
    closing_cash: Decimal
    balance_sheet_cash: Optional[Decimal] = None
    cash_matches_balance_sheet: bool = True
    model_config = ConfigDict(from_attributes=True)


class FSSnapshotResponse(BaseModel):
    id: int
    profile_id: int
    version: int
    snapshot_hash: str
    tb_total_debit: Decimal
    tb_total_credit: Decimal
    tb_difference: Decimal
    tb_is_balanced: bool
    total_assets: Decimal
    total_equity_and_liabilities: Decimal
    balance_difference: Decimal
    is_balance_sheet_balanced: bool
    total_revenue: Decimal
    total_expenses: Decimal
    profit_after_tax: Decimal
    closing_cash: Decimal
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class FSFindingResponse(BaseModel):
    id: int
    profile_id: int
    finding_type: str
    severity: str
    status: str
    category: str
    title: str
    description: str
    expected: Optional[Decimal] = None
    actual: Optional[Decimal] = None
    variance: Optional[Decimal] = None
    possible_cause: Optional[str] = None
    proven_cause: Optional[str] = None
    evidence: Optional[str] = None
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_cell: Optional[str] = None
    accountant_decision: Optional[str] = None
    decision_notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class FSFindingDecisionRequest(BaseModel):
    decision: str = Field(..., description="ACCEPTED, REJECTED, OVERRIDDEN")
    notes: Optional[str] = None


class FSStatusTransitionRequest(BaseModel):
    target_status: str = Field(..., description="DRAFT, ANALYZED, REVIEW_REQUIRED, UNDER_REVIEW, APPROVED")
    notes: Optional[str] = None


class FSOverviewResponse(BaseModel):
    profile_id: int
    entity_name: str
    financial_year: str
    reporting_period: str
    framework: str
    status: str
    total_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    total_equity: Optional[Decimal] = None
    total_revenue: Optional[Decimal] = None
    total_expenses: Optional[Decimal] = None
    net_profit: Optional[Decimal] = None
    closing_cash: Optional[Decimal] = None
    trial_balance_difference: Optional[Decimal] = None
    is_tb_balanced: bool = True
    is_bs_balanced: bool = True
    unresolved_findings_count: int = 0
    eligible_for_approval: bool = False
    latest_snapshot_hash: Optional[str] = None


class FSProfileResponse(FSProfileBase):
    id: int
    user_id: int
    status: str
    approved_at: Optional[Any] = None
    approved_by_user_id: Optional[int] = None
    approval_notes: Optional[str] = None
    created_at: Any
    tb_entries_count: int = 0
    bs_lines_count: int = 0
    pl_lines_count: int = 0
    cf_lines_count: int = 0
    findings_count: int = 0
    model_config = ConfigDict(from_attributes=True)
