"""
Pydantic Schemas for GST Returns Module (GSTR-1, GSTR-3B, GSTR-2B).
All monetary fields use Decimal for precision and compliance with Indian GST rules.
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================================
# GST Registration Schemas
# ============================================================================


class GSTRegistrationBase(BaseModel):
    gstin: str = Field(
        ..., min_length=15, max_length=15, description="15-character statutory GSTIN"
    )
    legal_name: str = Field(..., max_length=255)
    trade_name: Optional[str] = Field(None, max_length=255)
    state_code: str = Field(
        ..., min_length=2, max_length=2, description="2-digit state code"
    )
    registration_type: str = Field(
        "REGULAR", description="REGULAR, COMPOSITION, SEZ, ISD"
    )
    authorized_signatory: Optional[str] = None
    is_active: bool = True


class GSTRegistrationCreate(GSTRegistrationBase):
    pass


class GSTRegistrationUpdate(BaseModel):
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    authorized_signatory: Optional[str] = None
    is_active: Optional[bool] = None


class GSTRegistrationResponse(GSTRegistrationBase):
    id: Union[int, str]
    user_id: Union[int, str]
    organization_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# GST Filing Period Schemas
# ============================================================================


class GSTFilingPeriodCreate(BaseModel):
    registration_id: Union[int, str]
    period: str = Field(..., description="Format YYYY-MM (e.g. 2024-04)")
    financial_year: str = Field(..., description="Format YYYY-YY (e.g. 2024-25)")


class GSTFilingPeriodResponse(BaseModel):
    id: Union[int, str]
    registration_id: Union[int, str]
    period: str
    financial_year: str
    status: str
    gstr1_status: str
    gstr3b_status: str
    gstr2b_status: str
    filing_arn: Optional[str] = None
    filed_at: Optional[datetime] = None
    locked_at: Optional[datetime] = None
    filing_metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("filing_metadata", mode="before")
    @classmethod
    def parse_filing_metadata(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

    model_config = ConfigDict(from_attributes=True)


class GSTPeriodStatusTransition(BaseModel):
    new_status: str = Field(
        ..., description="draft, under_review, approved, filed, locked"
    )
    arn: Optional[str] = None
    reason: Optional[str] = None


# ============================================================================
# Sales Invoice Schemas (GSTR-1)
# ============================================================================


class GSTSalesInvoiceBase(BaseModel):
    invoice_number: str = Field(..., max_length=50)
    invoice_date: Union[date, str]
    customer_gstin: Optional[str] = Field(None, max_length=15)
    customer_name: str = Field(..., max_length=255)
    place_of_supply: str = Field(..., min_length=2, max_length=2)
    invoice_type: str = Field(
        ..., description="B2B, B2CL, B2CS, EXPORT, CDNR, CDNUR, NIL_EXEMPT"
    )
    taxable_value: Decimal = Field(..., ge=Decimal("0.00"))
    tax_rate: Decimal = Field(..., ge=Decimal("0.00"))
    cgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    sgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    igst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    cess_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    total_amount: Decimal = Field(..., ge=Decimal("0.00"))
    reverse_charge: bool = False
    is_ecommerce: bool = False
    ecommerce_gstin: Optional[str] = None
    original_invoice_number: Optional[str] = None
    original_invoice_date: Optional[Union[date, str]] = None
    note_type: Optional[str] = None
    hsn_code: Optional[str] = None
    description: Optional[str] = None


class GSTSalesInvoiceCreate(GSTSalesInvoiceBase):
    period_id: Optional[Union[int, str]] = None
    auto_calculate_tax: bool = Field(
        True,
        description="Automatically calculate tax splits from taxable_value and tax_rate",
    )


class GSTSalesInvoiceUpdate(BaseModel):
    customer_gstin: Optional[str] = None
    customer_name: Optional[str] = None
    place_of_supply: Optional[str] = None
    invoice_type: Optional[str] = None
    taxable_value: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    cgst_amount: Optional[Decimal] = None
    sgst_amount: Optional[Decimal] = None
    igst_amount: Optional[Decimal] = None
    cess_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    reverse_charge: Optional[bool] = None
    hsn_code: Optional[str] = None
    description: Optional[str] = None
    auto_calculate_tax: bool = False


class GSTValidationIssue(BaseModel):
    code: str
    severity: str  # ERROR, WARNING, INFO
    field: str
    message: str
    suggested_action: str


class GSTSalesInvoiceResponse(GSTSalesInvoiceBase):
    id: Union[int, str]
    registration_id: Union[int, str]
    period_id: Union[int, str]
    normalized_invoice_number: Optional[str] = None
    validation_status: str = "VALID"
    validation_errors: Optional[str] = None
    validation_issues: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    @field_validator("validation_issues", mode="before")
    @classmethod
    def parse_validation_issues(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return []
        return v

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Purchase Invoice Schemas (Books Register for ITC)
# ============================================================================


class GSTPurchaseInvoiceBase(BaseModel):
    invoice_number: str = Field(..., max_length=50)
    invoice_date: Union[date, str]
    supplier_gstin: str = Field(..., min_length=15, max_length=15)
    supplier_name: str = Field(..., max_length=255)
    place_of_supply: str = Field(..., min_length=2, max_length=2)
    taxable_value: Decimal = Field(..., ge=Decimal("0.00"))
    tax_rate: Decimal = Field(..., ge=Decimal("0.00"))
    cgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    sgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    igst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    cess_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    total_amount: Decimal = Field(..., ge=Decimal("0.00"))
    itc_eligibility: str = Field("ELIGIBLE", description="ELIGIBLE, INELIGIBLE")
    itc_category: str = Field(
        "ALL_OTHER_ITC", description="IMPG, IMPS, RCM, ISD, ALL_OTHER_ITC"
    )
    reverse_charge: bool = False
    hsn_code: Optional[str] = None
    notes: Optional[str] = None


class GSTPurchaseInvoiceCreate(GSTPurchaseInvoiceBase):
    period_id: Optional[Union[int, str]] = None
    auto_calculate_tax: bool = True


class GSTPurchaseInvoiceUpdate(BaseModel):
    supplier_gstin: Optional[str] = None
    supplier_name: Optional[str] = None
    taxable_value: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    cgst_amount: Optional[Decimal] = None
    sgst_amount: Optional[Decimal] = None
    igst_amount: Optional[Decimal] = None
    cess_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    itc_eligibility: Optional[str] = None
    itc_category: Optional[str] = None
    reverse_charge: Optional[bool] = None
    auto_calculate_tax: bool = False


class GSTPurchaseInvoiceResponse(GSTPurchaseInvoiceBase):
    id: Union[int, str]
    registration_id: Union[int, str]
    period_id: Union[int, str]
    normalized_invoice_number: Optional[str] = None
    match_status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# GSTR-2B External Record Schemas
# ============================================================================


class GSTR2BRecordCreate(BaseModel):
    period_id: Union[int, str]
    supplier_gstin: str = Field(..., min_length=15, max_length=15)
    supplier_name: str = Field(..., max_length=255)
    invoice_number: str = Field(..., max_length=50)
    invoice_type: str = "B2B"
    invoice_date: Union[date, str]
    taxable_value: Decimal = Field(..., ge=Decimal("0.00"))
    tax_rate: Decimal = Field(..., ge=Decimal("0.00"))
    cgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    sgst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    igst_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    cess_amount: Decimal = Field(Decimal("0.00"), ge=Decimal("0.00"))
    total_amount: Decimal = Field(..., ge=Decimal("0.00"))
    place_of_supply: str = Field(..., min_length=2, max_length=2)
    reverse_charge: bool = False
    itc_available: Union[str, bool] = "YES"
    itc_reason: Optional[str] = None
    supplier_filing_date: Optional[Union[date, str]] = None
    supplier_filing_status: str = "FILED"


class GSTR2BRecordResponse(BaseModel):
    id: Union[int, str]
    registration_id: Union[int, str]
    period_id: Union[int, str]
    supplier_gstin: str
    supplier_name: str
    invoice_number: str
    normalized_invoice_number: Optional[str] = None
    invoice_type: str
    invoice_date: str
    taxable_value: Decimal
    tax_rate: Decimal
    cgst_amount: Decimal
    sgst_amount: Decimal
    igst_amount: Decimal
    cess_amount: Decimal
    total_amount: Decimal
    place_of_supply: str
    reverse_charge: bool
    itc_available: bool
    itc_reason: Optional[str] = None
    supplier_filing_date: Optional[str] = None
    supplier_filing_status: str
    match_status: str
    import_checksum: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GSTR2BBulkImportRequest(BaseModel):
    period_id: Union[int, str]
    records: List[GSTR2BRecordCreate]
    checksum: Optional[str] = None


# ============================================================================
# Reconciliation Schemas
# ============================================================================


class ReconciliationRunRequest(BaseModel):
    date_tolerance_days: int = 30
    exact_tolerance_inr: Decimal = Decimal("1.00")
    partial_tolerance_inr: Decimal = Decimal("5.00")


class GSTReconciliationResultResponse(BaseModel):
    id: Union[int, str]
    period_id: Union[int, str]
    purchase_invoice_id: Optional[Union[int, str]] = None
    gstr2b_record_id: Optional[Union[int, str]] = None
    match_status: str
    matching_method: Optional[str] = None
    amount_tolerance: Optional[Decimal] = None
    date_tolerance_days: Optional[int] = None
    manual_decision_preserved: bool = False
    confidence_score: Decimal
    taxable_difference: Decimal
    tax_difference: Decimal
    mismatch_reasons: Optional[str] = None
    decision_status: str
    accountant_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReconciliationDecisionRequest(BaseModel):
    decision: str = Field(..., description="ACCEPTED, REJECTED, FORCE_MATCH, PENDING")
    notes: Optional[str] = None


class ReconciliationSummaryResponse(BaseModel):
    total_records: int
    exact_matches: int
    partial_matches: int
    books_only: int
    return_only: int
    excluded: int
    total_books_tax: Decimal
    total_2b_tax: Decimal
    matched_tax: Decimal
    mismatch_tax: Decimal
    books_only_tax: Decimal
    return_only_tax: Decimal


# ============================================================================
# GSTR-1 & GSTR-3B Summary Responses
# ============================================================================


class GSTR1SummaryResponse(BaseModel):
    period: str
    calculation_version: int = 1
    source_record_count: int = 0
    source_data_hash: Optional[str] = None
    is_stale: bool = False
    calculation_metadata: Optional[Dict[str, Any]] = None
    total_taxable_value: Decimal
    total_igst: Decimal
    total_cgst: Decimal
    total_sgst: Decimal
    total_cess: Decimal
    total_invoice_value: Decimal
    total_invoices_count: int
    b2b_summary: Optional[str] = None
    b2cl_summary: Optional[str] = None
    b2cs_summary: Optional[str] = None
    export_summary: Optional[str] = None
    cdnr_summary: Optional[str] = None
    nil_exempt_summary: Optional[str] = None
    calculated_at: Optional[datetime] = None

    @field_validator("calculation_metadata", mode="before")
    @classmethod
    def parse_gstr1_metadata(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

    model_config = ConfigDict(from_attributes=True)


class GSTR3BSummaryResponse(BaseModel):
    period: str
    calculation_version: int = 1
    source_record_count: int = 0
    source_data_hash: Optional[str] = None
    is_stale: bool = False
    set_off_details: Optional[Dict[str, Any]] = None
    calculation_metadata: Optional[Dict[str, Any]] = None
    outward_taxable_value: Decimal
    outward_igst: Decimal
    outward_cgst: Decimal
    outward_sgst: Decimal
    outward_cess: Decimal
    interstate_unregistered_taxable: Decimal
    interstate_unregistered_igst: Decimal
    itc_all_other_igst: Decimal
    itc_all_other_cgst: Decimal
    itc_all_other_sgst: Decimal
    itc_all_other_cess: Decimal
    itc_reversed_igst: Decimal
    itc_reversed_cgst: Decimal
    itc_reversed_sgst: Decimal
    itc_reversed_cess: Decimal
    net_itc_igst: Decimal
    net_itc_cgst: Decimal
    net_itc_sgst: Decimal
    net_itc_cess: Decimal
    inward_exempt_nil: Decimal
    net_tax_payable_igst: Decimal
    net_tax_payable_cgst: Decimal
    net_tax_payable_sgst: Decimal
    net_tax_payable_cess: Decimal
    total_net_tax_payable: Decimal
    calculated_at: Optional[datetime] = None

    @field_validator("calculation_metadata", "set_off_details", mode="before")
    @classmethod
    def parse_gstr3b_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v

    model_config = ConfigDict(from_attributes=True)
