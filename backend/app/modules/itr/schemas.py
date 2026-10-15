from decimal import Decimal
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ITRProfileBase(BaseModel):
    pan: str = Field(..., min_length=10, max_length=10, description="10-character PAN")
    taxpayer_name: str = Field(..., min_length=1, max_length=255)
    taxpayer_category: str = Field(default="INDIVIDUAL", description="INDIVIDUAL, HUF, FIRM, COMPANY")
    assessment_year: str = Field(default="2024-25", description="Assessment Year e.g. 2024-25")
    financial_year: str = Field(default="2023-24", description="Financial Year e.g. 2023-24")
    selected_regime: str = Field(default="UNDECIDED", description="NEW, OLD, UNDECIDED")


class ITRProfileCreate(ITRProfileBase):
    pass


class ITRProfileUpdate(BaseModel):
    taxpayer_name: Optional[str] = None
    selected_regime: Optional[str] = None
    taxpayer_category: Optional[str] = None


class ITRIncomeEntryCreate(BaseModel):
    head_of_income: str = Field(..., description="SALARY, BUSINESS_PROFESSION, HOUSE_PROPERTY, CAPITAL_GAINS, OTHER_SOURCES")
    subcategory: str = Field(default="GENERAL")
    description: Optional[str] = None
    gross_amount: Decimal = Field(default=Decimal("0.00"))
    exemptions_allowances: Decimal = Field(default=Decimal("0.00"))
    net_taxable_amount: Decimal = Field(default=Decimal("0.00"))
    verification_status: str = Field(default="REVIEW_REQUIRED")
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    source_cell: Optional[str] = None
    provenance_notes: Optional[str] = None


class ITRIncomeEntryResponse(ITRIncomeEntryCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class ITRDeductionEntryCreate(BaseModel):
    section: str = Field(..., description="80C, 80D, 80CCD_1B, 80G, 80TTA, OTHER")
    description: str
    claimed_amount: Decimal = Field(default=Decimal("0.00"))
    eligible_amount: Decimal = Field(default=Decimal("0.00"))
    status: str = Field(default="REVIEW_REQUIRED", description="VERIFIED, REVIEW_REQUIRED, NOT_SUPPORTED, EXCLUDED")
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    provenance_notes: Optional[str] = None


class ITRDeductionEntryUpdate(BaseModel):
    eligible_amount: Optional[Decimal] = None
    status: Optional[str] = None
    provenance_notes: Optional[str] = None


class ITRDeductionEntryResponse(ITRDeductionEntryCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class ITRTaxCreditEntryCreate(BaseModel):
    credit_type: str = Field(..., description="TDS_SALARY, TDS_OTHER, TCS, ADVANCE_TAX, SELF_ASSESSMENT_TAX")
    deductor_or_bank: Optional[str] = None
    deductor_tan_pan: Optional[str] = None
    section_code: Optional[str] = None
    challan_or_cert_no: Optional[str] = None
    credit_amount: Decimal = Field(default=Decimal("0.00"))
    date_of_payment: Optional[str] = None
    verification_status: str = Field(default="REVIEW_REQUIRED")
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    provenance_notes: Optional[str] = None


class ITRTaxCreditEntryResponse(ITRTaxCreditEntryCreate):
    id: int
    profile_id: int
    created_at: Any
    model_config = ConfigDict(from_attributes=True)


class ITRComputationResponse(BaseModel):
    profile_id: int
    regime: str
    computation_hash: str
    gross_salary: Decimal
    standard_deduction: Decimal
    net_salary: Decimal
    house_property_income: Decimal
    business_profession_income: Decimal
    capital_gains: Decimal
    other_sources_income: Decimal
    gross_total_income: Decimal
    total_deductions: Decimal
    total_taxable_income: Decimal
    basic_tax: Decimal
    rebate_87a: Decimal
    tax_after_rebate: Decimal
    cess_4_pct: Decimal
    total_tax_liability: Decimal
    tds_total: Decimal
    tcs_total: Decimal
    advance_tax_total: Decimal
    self_assessment_tax_total: Decimal
    total_taxes_paid: Decimal
    net_payable_or_refund: Decimal
    breakdown: Dict[str, Any] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class ITRRegimeComparisonResponse(BaseModel):
    profile_id: int
    pan: str
    taxpayer_name: str
    assessment_year: str
    selected_regime: str
    old_regime: ITRComputationResponse
    new_regime: ITRComputationResponse
    difference_in_tax: Decimal
    unresolved_findings_count: int
    eligible_for_approval: bool


class ITRFindingResponse(BaseModel):
    id: int
    profile_id: int
    finding_type: str
    severity: str
    status: str
    title: str
    description: str
    category: str
    expected_value: Optional[Decimal] = None
    actual_value: Optional[Decimal] = None
    difference: Optional[Decimal] = None
    source_document: Optional[str] = None
    source_sheet: Optional[str] = None
    source_row: Optional[int] = None
    possible_causes: List[str] = Field(default_factory=list)
    recommended_actions: List[str] = Field(default_factory=list)
    accountant_decision: Optional[str] = None
    decision_notes: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class ITRFindingDecisionRequest(BaseModel):
    decision: str = Field(..., description="ACCEPTED, REJECTED, OVERRIDDEN")
    notes: Optional[str] = None


class ITRStatusTransitionRequest(BaseModel):
    target_status: str = Field(..., description="DRAFT, ANALYZED, REVIEW_REQUIRED, UNDER_REVIEW, APPROVED")
    notes: Optional[str] = None


class ITRProfileResponse(ITRProfileBase):
    id: int
    user_id: int
    status: str
    approved_at: Optional[Any] = None
    approved_by_user_id: Optional[int] = None
    approval_notes: Optional[str] = None
    created_at: Any
    income_count: int = 0
    deduction_count: int = 0
    tax_credit_count: int = 0
    findings_count: int = 0
    model_config = ConfigDict(from_attributes=True)
