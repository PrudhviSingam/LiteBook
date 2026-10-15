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


class FinancialStatementProfile(BaseModel):
    """Represents an entity's financial reporting period and framework."""

    __tablename__ = "fs_profiles"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_name = Column(String(255), nullable=False)
    cin_or_pan = Column(String(21), nullable=True, index=True)
    financial_year = Column(String(9), nullable=False, index=True)  # e.g., "2023-24"
    reporting_period = Column(String(20), default="ANNUAL", nullable=False)  # ANNUAL, Q1, Q2, Q3, Q4
    framework = Column(String(50), default="SCHEDULE_III", nullable=False)  # SCHEDULE_III, IND_AS

    # Status: DRAFT -> ANALYZED -> REVIEW_REQUIRED -> UNDER_REVIEW -> APPROVED
    status = Column(String(30), default="DRAFT", nullable=False, index=True)

    # Human sign-off / approval metadata
    approved_at = Column(DateTime, nullable=True)
    approved_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approval_notes = Column(Text, nullable=True)

    # Relationships
    trial_balance_entries = relationship(
        "TrialBalanceEntry", back_populates="profile", cascade="all, delete-orphan"
    )
    balance_sheet_lines = relationship(
        "BalanceSheetLine", back_populates="profile", cascade="all, delete-orphan"
    )
    profit_loss_lines = relationship(
        "ProfitLossLine", back_populates="profile", cascade="all, delete-orphan"
    )
    cash_flow_lines = relationship(
        "CashFlowLine", back_populates="profile", cascade="all, delete-orphan"
    )
    snapshots = relationship(
        "FinancialStatementSnapshot", back_populates="profile", cascade="all, delete-orphan"
    )
    findings = relationship(
        "FinancialStatementFinding", back_populates="profile", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "entity_name", "financial_year", "reporting_period", name="uq_fs_profile_period"),
    )


class TrialBalanceEntry(BaseModel):
    """A ledger account entry in the Trial Balance with exact provenance."""

    __tablename__ = "fs_trial_balance_entries"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_code = Column(String(50), nullable=True, index=True)
    account_name = Column(String(255), nullable=False)
    # Category: ASSET, LIABILITY, EQUITY, REVENUE, EXPENSE
    account_category = Column(String(30), default="ASSET", nullable=False, index=True)

    debit_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    credit_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_balance = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Strict provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    source_cell = Column(String(20), nullable=True)
    source_value = Column(String(100), nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="trial_balance_entries")


class BalanceSheetLine(BaseModel):
    """A classified line item on the Balance Sheet (Schedule III)."""

    __tablename__ = "fs_balance_sheet_lines"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Classification: NON_CURRENT_ASSETS, CURRENT_ASSETS, EQUITY, NON_CURRENT_LIABILITIES, CURRENT_LIABILITIES
    classification = Column(String(40), nullable=False, index=True)
    # Sub-category: PROPERTY_PLANT_EQUIPMENT, INTANGIBLE, INVENTORIES, TRADE_RECEIVABLES, CASH_BANK, SHARE_CAPITAL, RESERVES, BORROWINGS, TRADE_PAYABLES, PROVISIONS, etc.
    sub_category = Column(String(100), nullable=False)
    line_item_name = Column(String(255), nullable=False)
    amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    schedule_note_number = Column(String(20), nullable=True)

    # Provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    source_cell = Column(String(20), nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="balance_sheet_lines")


class ProfitLossLine(BaseModel):
    """A classified line item on the Profit & Loss statement."""

    __tablename__ = "fs_profit_loss_lines"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Category: REVENUE, OTHER_INCOME, COST_OF_MATERIALS, EMPLOYEE_BENEFITS, FINANCE_COSTS, DEPRECIATION, OTHER_EXPENSES, TAX_EXPENSE
    category = Column(String(40), nullable=False, index=True)
    line_item_name = Column(String(255), nullable=False)
    amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    schedule_note_number = Column(String(20), nullable=True)

    # Provenance
    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    source_cell = Column(String(20), nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="profit_loss_lines")


class CashFlowLine(BaseModel):
    """A classified line item on the Cash Flow Statement."""

    __tablename__ = "fs_cash_flow_lines"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Activity: OPERATING, INVESTING, FINANCING
    activity_type = Column(String(30), nullable=False, index=True)
    line_item_name = Column(String(255), nullable=False)
    amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    provenance_notes = Column(Text, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="cash_flow_lines")


class FinancialStatementSnapshot(BaseModel):
    """Immutable calculation snapshot of generated statements with SHA-256 hash."""

    __tablename__ = "fs_snapshots"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version = Column(Integer, default=1, nullable=False)
    snapshot_hash = Column(String(64), nullable=False, index=True)

    # Trial Balance totals
    tb_total_debit = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tb_total_credit = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tb_difference = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tb_is_balanced = Column(Boolean, default=True, nullable=False)

    # Balance Sheet totals
    total_non_current_assets = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_current_assets = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_assets = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    total_equity = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_non_current_liabilities = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_current_liabilities = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_equity_and_liabilities = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    balance_difference = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    is_balance_sheet_balanced = Column(Boolean, default=True, nullable=False)

    # Profit & Loss totals
    total_revenue = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_expenses = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    profit_before_tax = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tax_expense = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    profit_after_tax = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Cash Flow totals
    net_cash_operating = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_cash_investing = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_cash_financing = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_change_in_cash = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    opening_cash = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    closing_cash = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    statement_payload_json = Column(Text, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="snapshots")


class FinancialStatementFinding(BaseModel):
    """Accountant review findings and discrepancies for Review Center integration."""

    __tablename__ = "fs_findings"

    profile_id = Column(
        Integer, ForeignKey("fs_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Types: TRIAL_BALANCE_UNBALANCED, BALANCE_SHEET_MISMATCH, MISSING_REVENUE, MISSING_EXPENSE, P_AND_L_FORMULA_MISMATCH, CASH_FLOW_MISMATCH, MISSING_SUPPORTING_DOCUMENT, PERIOD_MISMATCH, SOURCE_DATA_INCOMPLETE
    finding_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default="MEDIUM", nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    status = Column(String(30), default="REVIEW_REQUIRED", nullable=False, index=True)

    category = Column(String(50), default="FINANCIAL_STATEMENTS", nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)

    expected = Column(Numeric(15, 2), nullable=True)
    actual = Column(Numeric(15, 2), nullable=True)
    variance = Column(Numeric(15, 2), nullable=True)

    possible_cause = Column(Text, nullable=True)
    proven_cause = Column(Text, nullable=True)
    evidence = Column(Text, nullable=True)

    source_document = Column(String(255), nullable=True)
    source_sheet = Column(String(100), nullable=True)
    source_row = Column(Integer, nullable=True)
    source_cell = Column(String(20), nullable=True)

    accountant_decision = Column(String(30), nullable=True)  # ACCEPTED, REJECTED, OVERRIDDEN
    decision_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    profile = relationship("FinancialStatementProfile", back_populates="findings")
