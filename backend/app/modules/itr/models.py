from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ITRProfile(BaseModel):
    """Represents a taxpayer's ITR profile for a specific Assessment Year."""

    __tablename__ = "itr_profiles"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pan = Column(String(10), nullable=False, index=True)
    taxpayer_name = Column(String(255), nullable=False)
    taxpayer_category = Column(
        String(50), default="INDIVIDUAL", nullable=False
    )  # INDIVIDUAL, HUF, FIRM, COMPANY
    assessment_year = Column(String(7), nullable=False, index=True)  # e.g., "2024-25"
    financial_year = Column(String(7), nullable=False, index=True)   # e.g., "2023-24"

    # Regime selection: NEW (Section 115BAC), OLD, or UNDECIDED (user must select)
    selected_regime = Column(String(20), default="UNDECIDED", nullable=False)

    # Workflow Status: DRAFT -> ANALYZED -> REVIEW_REQUIRED -> UNDER_REVIEW -> APPROVED
    status = Column(String(30), default="DRAFT", nullable=False, index=True)

    # Safety & Approval Tracking
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approval_notes = Column(Text, nullable=True)

    # Relationships
    income_entries = relationship(
        "ITRIncomeEntry", back_populates="profile", cascade="all, delete-orphan"
    )
    deduction_entries = relationship(
        "ITRDeductionEntry", back_populates="profile", cascade="all, delete-orphan"
    )
    tax_credits = relationship(
        "ITRTaxCreditEntry", back_populates="profile", cascade="all, delete-orphan"
    )
    computation_snapshots = relationship(
        "ITRComputationSnapshot", back_populates="profile", cascade="all, delete-orphan"
    )
    findings = relationship(
        "ITRFinding", back_populates="profile", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "pan", "assessment_year", name="uq_user_pan_ay"),
    )


class ITRIncomeEntry(BaseModel):
    """Granular income entry classified into the 5 Indian statutory heads."""

    __tablename__ = "itr_income_entries"

    profile_id = Column(
        Integer, ForeignKey("itr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Head of income: SALARY, BUSINESS_PROFESSION, HOUSE_PROPERTY, CAPITAL_GAINS, OTHER_SOURCES
    head_of_income = Column(String(40), nullable=False, index=True)
    subcategory = Column(String(100), nullable=False)  # BASIC_SALARY, HRA, COMMISSION, INTEREST, DIVIDEND, LTCG, STCG, etc.
    description = Column(String(255), nullable=True)

    gross_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    exemptions_allowances = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_taxable_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Verification status: VERIFIED, REVIEW_REQUIRED, UNVERIFIED
    verification_status = Column(String(30), default="REVIEW_REQUIRED", nullable=False)

    # Document Provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    source_cell = Column(String(20), nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("ITRProfile", back_populates="income_entries")


class ITRDeductionEntry(BaseModel):
    """Chapter VI-A deduction entry (80C, 80D, 80CCD, 80G, etc.)."""

    __tablename__ = "itr_deduction_entries"

    profile_id = Column(
        Integer, ForeignKey("itr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section = Column(String(30), nullable=False, index=True)  # 80C, 80D, 80CCD_1B, 80G, 80TTA, OTHER
    description = Column(String(255), nullable=False)

    claimed_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    eligible_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Status: VERIFIED, REVIEW_REQUIRED, NOT_SUPPORTED, EXCLUDED
    status = Column(String(30), default="REVIEW_REQUIRED", nullable=False)

    # Document Provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("ITRProfile", back_populates="deduction_entries")


class ITRTaxCreditEntry(BaseModel):
    """TDS, TCS, Advance Tax, and Self Assessment Tax records."""

    __tablename__ = "itr_tax_credit_entries"

    profile_id = Column(
        Integer, ForeignKey("itr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Credit type: TDS_SALARY, TDS_OTHER, TCS, ADVANCE_TAX, SELF_ASSESSMENT_TAX
    credit_type = Column(String(30), nullable=False, index=True)
    deductor_or_bank = Column(String(255), nullable=True)
    deductor_tan_pan = Column(String(20), nullable=True)
    section_code = Column(String(20), nullable=True)  # 192, 194J, 194C, 206C, etc.
    challan_or_cert_no = Column(String(100), nullable=True)
    credit_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    date_of_payment = Column(String(10), nullable=True)  # YYYY-MM-DD

    # Status: VERIFIED, REVIEW_REQUIRED, UNVERIFIED
    verification_status = Column(String(30), default="REVIEW_REQUIRED", nullable=False)

    # Document Provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("ITRProfile", back_populates="tax_credits")


class ITRComputationSnapshot(BaseModel):
    """Deterministic calculation snapshot for audit, review, and regime comparison."""

    __tablename__ = "itr_computation_snapshots"

    profile_id = Column(
        Integer, ForeignKey("itr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regime = Column(String(20), nullable=False)  # NEW or OLD
    computation_hash = Column(String(64), nullable=False, index=True)

    # Income Components
    gross_salary = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    standard_deduction = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_salary = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    house_property_income = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    business_profession_income = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    capital_gains = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    other_sources_income = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    gross_total_income = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_deductions = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_taxable_income = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Tax & Liability
    basic_tax = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    rebate_87a = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tax_after_rebate = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cess_4_pct = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_tax_liability = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Taxes Paid
    tds_total = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tcs_total = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    advance_tax_total = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    self_assessment_tax_total = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_taxes_paid = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Net Result: Positive = Payable, Negative = Refund
    net_payable_or_refund = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    calculation_breakdown_json = Column(Text, nullable=True)

    profile = relationship("ITRProfile", back_populates="computation_snapshots")


class ITRFinding(BaseModel):
    """Accountant review findings and discrepancies for Review Center integration."""

    __tablename__ = "itr_findings"

    profile_id = Column(
        Integer, ForeignKey("itr_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Types: MISSING_TDS, INCOME_MISMATCH, UNSUPPORTED_DEDUCTION, MISSING_DOCUMENT, TAX_CREDIT_MISMATCH, CALCULATION_VERIFICATION
    finding_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default="MEDIUM", nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW

    # Status: REVIEW_REQUIRED, UNDER_REVIEW, APPROVED, REJECTED, RESOLVED
    status = Column(String(30), default="REVIEW_REQUIRED", nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    category = Column(String(50), default="ITR_TAX", nullable=False)
    expected_value = Column(Numeric(15, 2), nullable=True)
    actual_value = Column(Numeric(15, 2), nullable=True)
    difference = Column(Numeric(15, 2), nullable=True)

    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)

    possible_causes = Column(Text, nullable=True)  # JSON array string
    recommended_actions = Column(Text, nullable=True)  # JSON array string

    accountant_decision = Column(String(30), nullable=True)  # ACCEPTED, REJECTED, OVERRIDDEN
    decision_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    profile = relationship("ITRProfile", back_populates="findings")
