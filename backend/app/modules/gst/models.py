from decimal import Decimal
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
    text,
)
from sqlalchemy.orm import relationship, synonym
from app.models.base import BaseModel


class GSTRegistration(BaseModel):
    """Represents a business's GST Registration (GSTIN)."""

    __tablename__ = "gst_registrations"

    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    organization_id = Column(String(100), nullable=True, index=True)

    gstin = Column(String(15), nullable=False, index=True)
    legal_name = Column(String(255), nullable=False)
    trade_name = Column(String(255), nullable=True)
    state_code = Column(
        String(2), nullable=False
    )  # 2-digit Indian State Code, e.g. "27" for Maharashtra
    state_name = Column(String(100), nullable=True)
    registration_type = Column(
        String(50), default="REGULAR", nullable=False
    )  # REGULAR, COMPOSITION, SEZ
    authorized_signatory = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships
    filing_periods = relationship(
        "GSTFilingPeriod", back_populates="registration", cascade="all, delete-orphan"
    )
    sales_invoices = relationship(
        "GSTSalesInvoice", back_populates="registration", cascade="all, delete-orphan"
    )
    purchase_invoices = relationship(
        "GSTPurchaseInvoice",
        back_populates="registration",
        cascade="all, delete-orphan",
    )
    gstr2b_records = relationship(
        "GSTR2BRecord", back_populates="registration", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("user_id", "gstin", name="uq_user_gstin"),)


class GSTFilingPeriod(BaseModel):
    """Represents a monthly or quarterly tax filing period for a GSTIN."""

    __tablename__ = "gst_filing_periods"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period = Column(
        String(7), nullable=False, index=True
    )  # Format: "YYYY-MM", e.g., "2026-09"
    financial_year = Column(
        String(9), nullable=False, index=True
    )  # Format: "YYYY-YY", e.g., "2026-27"

    # Status workflow: "draft" -> "under_review" -> "approved" -> "filed" -> "locked"
    status = Column(String(30), default="draft", nullable=False, index=True)
    gstr1_status = Column(String(30), default="draft", nullable=False)
    gstr3b_status = Column(String(30), default="draft", nullable=False)
    gstr2b_status = Column(String(30), default="pending", nullable=False)

    # Locking and filing metadata
    locked_at = Column(DateTime, nullable=True)
    locked_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filed_at = Column(DateTime, nullable=True)
    filing_arn = Column(String(50), nullable=True)  # Application Reference Number
    filing_metadata = Column(Text, nullable=True)  # JSON-encoded filing details

    # Stored computation hashes for integrity / staleness detection
    gstr1_hash = Column(String(64), nullable=True)
    gstr3b_hash = Column(String(64), nullable=True)
    gstr2b_recon_hash = Column(String(64), nullable=True)

    registration_id = synonym("gst_registration_id")

    registration = relationship("GSTRegistration", back_populates="filing_periods")
    sales_invoices = relationship("GSTSalesInvoice", back_populates="filing_period")
    purchase_invoices = relationship(
        "GSTPurchaseInvoice", back_populates="filing_period"
    )
    gstr2b_records = relationship("GSTR2BRecord", back_populates="filing_period")
    reconciliation_results = relationship(
        "GSTReconciliationResult",
        back_populates="filing_period",
        cascade="all, delete-orphan",
    )
    gstr1_summaries = relationship(
        "GSTR1Summary", back_populates="filing_period", cascade="all, delete-orphan"
    )
    gstr3b_summaries = relationship(
        "GSTR3BSummary", back_populates="filing_period", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("gst_registration_id", "period", name="uq_gstin_period"),
    )


class GSTSalesInvoice(BaseModel):
    """Sales invoice representing outward supply for GSTR-1 preparation."""

    __tablename__ = "gst_sales_invoices"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    period = Column(String(7), nullable=False, index=True)  # "2026-09"
    invoice_number = Column(String(50), nullable=False, index=True)
    invoice_date = Column(String(10), nullable=False)  # "YYYY-MM-DD"

    # Recipient details
    customer_gstin = Column(String(15), nullable=True, index=True)
    customer_name = Column(String(255), nullable=False)
    place_of_supply = Column(String(2), nullable=False)  # 2-digit state code, e.g. "27"

    # Classification: B2B, B2CL (Interstate > 2.5L), B2CS, EXPORT, CDNR, CDNUR, NIL_EXEMPT
    invoice_type = Column(String(20), default="B2B", nullable=False, index=True)
    supply_type = Column(
        String(20), default="INTRA_STATE", nullable=False
    )  # INTRA_STATE, INTER_STATE
    reverse_charge = Column(Boolean, default=False, nullable=False)

    # Monetary fields using Decimal
    taxable_value = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tax_rate = Column(
        Numeric(5, 2), default=Decimal("18.00"), nullable=False
    )  # 0, 5, 12, 18, 28
    igst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    sgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cess_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    # Optional / e-invoice / note metadata
    original_invoice_number = Column(String(50), nullable=True)
    normalized_invoice_number = Column(String(50), nullable=True, index=True)
    hsn_code = Column(String(20), nullable=True)
    description = Column(String(255), nullable=True)

    # Validation
    validation_status = Column(
        String(20), default="VALID", nullable=False, index=True
    )  # VALID, WARNING, ERROR
    validation_errors = Column(
        Text, nullable=True
    )  # JSON-encoded array of issue strings
    validation_issues = Column(
        Text, nullable=True
    )  # JSON-encoded array of structured issue dicts

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")

    registration = relationship("GSTRegistration", back_populates="sales_invoices")
    filing_period = relationship("GSTFilingPeriod", back_populates="sales_invoices")

    __table_args__ = (
        UniqueConstraint(
            "gst_registration_id",
            "invoice_number",
            "period",
            name="uq_sales_inv_period",
        ),
        Index("ix_sales_reg_period", "gst_registration_id", "period"),
    )


class GSTPurchaseInvoice(BaseModel):
    """Purchase invoice from books (Purchase Register) for ITC and GSTR-2B reconciliation."""

    __tablename__ = "gst_purchase_invoices"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    period = Column(String(7), nullable=False, index=True)  # "2026-09"
    invoice_number = Column(String(50), nullable=False, index=True)
    invoice_date = Column(String(10), nullable=False)  # "YYYY-MM-DD"

    supplier_gstin = Column(String(15), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=False)
    place_of_supply = Column(String(2), nullable=False)
    supply_type = Column(String(20), default="INTRA_STATE", nullable=False)
    invoice_type = Column(String(20), default="B2B", nullable=False)
    reverse_charge = Column(Boolean, default=False, nullable=False)

    # Monetary fields using Decimal
    taxable_value = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=Decimal("18.00"), nullable=False)
    igst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    sgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cess_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # ITC Classification: ELIGIBLE, INELIGIBLE
    itc_eligibility = Column(String(20), default="ELIGIBLE", nullable=False)
    # Categories: ALL_OTHER_ITC, IMPORT_GOODS, IMPORT_SERVICES, RCM
    itc_category = Column(String(30), default="ALL_OTHER_ITC", nullable=False)

    hsn_code = Column(String(20), nullable=True)
    normalized_invoice_number = Column(String(50), nullable=True, index=True)
    notes = Column(Text, nullable=True)

    # Reconciliation status: PENDING, EXACT_MATCH, PARTIAL_MATCH, BOOKS_ONLY, EXCLUDED
    match_status = Column(String(30), default="PENDING", nullable=False, index=True)

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")

    registration = relationship("GSTRegistration", back_populates="purchase_invoices")
    filing_period = relationship("GSTFilingPeriod", back_populates="purchase_invoices")
    reconciliation_results = relationship(
        "GSTReconciliationResult", back_populates="purchase_invoice"
    )

    __table_args__ = (
        UniqueConstraint(
            "gst_registration_id",
            "supplier_gstin",
            "invoice_number",
            "period",
            name="uq_purch_inv_period",
        ),
        Index("ix_purch_reg_period", "gst_registration_id", "period"),
    )


class GSTR2BRecord(BaseModel):
    """External GSTR-2B data imported from GST portal or auto-drafted statement."""

    __tablename__ = "gstr2b_records"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    period = Column(String(7), nullable=False, index=True)
    supplier_gstin = Column(String(15), nullable=False, index=True)
    supplier_name = Column(String(255), nullable=False)
    invoice_number = Column(String(50), nullable=False, index=True)
    normalized_invoice_number = Column(String(50), nullable=True, index=True)
    invoice_date = Column(String(10), nullable=False)
    invoice_type = Column(String(20), default="B2B", nullable=False)
    place_of_supply = Column(String(2), nullable=False)
    reverse_charge = Column(Boolean, default=False, nullable=False)

    taxable_value = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    tax_rate = Column(Numeric(5, 2), default=Decimal("18.00"), nullable=False)
    igst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    sgst_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    cess_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_amount = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    itc_available = Column(Boolean, default=True, nullable=False)
    itc_reason = Column(String(255), nullable=True)
    gstr2b_filing_date = Column(String(10), nullable=True)
    supplier_filing_status = Column(String(20), default="Y", nullable=False)

    # Import Tracking & Raw Data Preservation
    import_checksum = Column(String(64), nullable=True, index=True)
    raw_payload = Column(Text, nullable=True)
    uploader_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Reconciliation status
    match_status = Column(String(30), default="PENDING", nullable=False, index=True)

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")
    supplier_filing_date = synonym("gstr2b_filing_date")

    registration = relationship("GSTRegistration", back_populates="gstr2b_records")
    filing_period = relationship("GSTFilingPeriod", back_populates="gstr2b_records")
    reconciliation_results = relationship(
        "GSTReconciliationResult", back_populates="gstr2b_record"
    )

    __table_args__ = (
        UniqueConstraint(
            "gst_registration_id",
            "supplier_gstin",
            "invoice_number",
            "period",
            name="uq_gstr2b_inv_period",
        ),
        Index("ix_gstr2b_reg_period", "gst_registration_id", "period"),
    )


class GSTReconciliationResult(BaseModel):
    """Granular reconciliation pairing between Books Purchase Invoice and GSTR-2B entry."""

    __tablename__ = "gst_reconciliation_results"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period = Column(String(7), nullable=False, index=True)

    purchase_invoice_id = Column(
        Integer,
        ForeignKey("gst_purchase_invoices.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    gstr2b_record_id = Column(
        Integer,
        ForeignKey("gstr2b_records.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    # EXACT_MATCH, PARTIAL_MATCH, BOOKS_ONLY, RETURN_ONLY, EXCLUDED
    match_type = Column(String(30), nullable=False, index=True)
    match_score = Column(Numeric(5, 2), default=Decimal("100.00"), nullable=False)

    # Variances
    tax_difference = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    taxable_difference = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    date_difference_days = Column(Integer, default=0, nullable=False)

    # Detailed discrepancies e.g. ["TAX_DIFFERENCE", "DATE_VARIANCE", "INVOICE_NUMBER_FUZZY"]
    mismatch_reasons = Column(Text, nullable=True)  # JSON-encoded array

    # Accountant decision: UNREVIEWED, ACCEPTED, REJECTED, MANUAL_MATCHED, EXCLUDED
    status = Column(String(30), default="UNREVIEWED", nullable=False, index=True)
    accountant_notes = Column(Text, nullable=True)

    # Reconciliation Safeguards & Matching Metadata
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    matching_method = Column(String(50), default="AUTO_RULE_ENGINE", nullable=False)
    amount_tolerance = Column(Numeric(10, 2), default=Decimal("1.00"), nullable=False)
    date_tolerance_days = Column(Integer, default=3, nullable=False)
    manual_decision_preserved = Column(Boolean, default=False, nullable=False)

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")
    match_status = synonym("match_type")
    confidence_score = synonym("match_score")
    decision_status = synonym("status")

    filing_period = relationship(
        "GSTFilingPeriod", back_populates="reconciliation_results"
    )
    purchase_invoice = relationship(
        "GSTPurchaseInvoice", back_populates="reconciliation_results"
    )
    gstr2b_record = relationship(
        "GSTR2BRecord", back_populates="reconciliation_results"
    )

    __table_args__ = (Index("ix_recon_reg_period", "gst_registration_id", "period"),)


class GSTR1Summary(BaseModel):
    """Snapshot of aggregated GSTR-1 return tables for a filing period."""

    __tablename__ = "gstr1_summaries"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period = Column(String(7), nullable=False, index=True)

    # Calculation Snapshot Integrity
    calculation_version = Column(Integer, default=1, nullable=False)
    source_record_count = Column(Integer, default=0, nullable=False)
    source_data_hash = Column(String(64), nullable=True, index=True)
    calculation_metadata = Column(Text, nullable=True)

    # Aggregates across all sales invoices
    total_taxable_value = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    total_igst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_cgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_sgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_cess = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    total_invoice_value = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    total_invoices_count = Column(Integer, default=0, nullable=False)

    # Specific table summaries stored as detailed JSON
    b2b_summary = Column(Text, nullable=True)  # Table 4A, 4B, 4C, 6B, 6C
    b2cl_summary = Column(
        Text, nullable=True
    )  # Table 5A, 5B (Large invoices > 2.5L Interstate)
    b2cs_summary = Column(Text, nullable=True)  # Table 7 (Small retail supplies)
    export_summary = Column(Text, nullable=True)  # Table 6A
    cdnr_summary = Column(Text, nullable=True)  # Table 9B Credit/Debit Notes Registered
    nil_exempt_summary = Column(Text, nullable=True)  # Table 8 Nil, Exempt, Non-GST

    is_stale = Column(Boolean, default=False, nullable=False)

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")
    calculated_at = synonym("updated_at")

    filing_period = relationship("GSTFilingPeriod", back_populates="gstr1_summaries")

    __table_args__ = (
        UniqueConstraint(
            "filing_period_id", "calculation_version", name="uq_gstr1_period_version"
        ),
    )


class GSTR3BSummary(BaseModel):
    """Snapshot of aggregated GSTR-3B tax computation for a filing period."""

    __tablename__ = "gstr3b_summaries"

    gst_registration_id = Column(
        Integer,
        ForeignKey("gst_registrations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filing_period_id = Column(
        Integer,
        ForeignKey("gst_filing_periods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period = Column(String(7), nullable=False, index=True)

    # Calculation Snapshot Integrity
    calculation_version = Column(Integer, default=1, nullable=False)
    source_record_count = Column(Integer, default=0, nullable=False)
    source_data_hash = Column(String(64), nullable=True, index=True)
    set_off_details = Column(Text, nullable=True)
    calculation_metadata = Column(Text, nullable=True)

    registration_id = synonym("gst_registration_id")
    period_id = synonym("filing_period_id")
    calculated_at = synonym("updated_at")

    # 3.1 Outward supplies and inward supplies liable to reverse charge
    outward_taxable_value = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    outward_igst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    outward_cgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    outward_sgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    outward_cess = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # 3.2 Inter-state supplies to unregistered persons
    interstate_unregistered_taxable = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    interstate_unregistered_igst = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )

    # 4 Eligible ITC
    itc_all_other_igst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_all_other_cgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_all_other_sgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_all_other_cess = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # ITC Reversals (Rule 42/43, Others)
    itc_reversed_igst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_reversed_cgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_reversed_sgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    itc_reversed_cess = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # Net ITC Available (Eligible - Reversals)
    net_itc_igst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_itc_cgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_itc_sgst = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)
    net_itc_cess = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # 5 Values of exempt, nil-rated, and non-GST inward supplies
    inward_exempt_nil = Column(Numeric(15, 2), default=Decimal("0.00"), nullable=False)

    # 6.1 Net Tax Payable (Output Tax minus Net ITC)
    net_tax_payable_igst = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    net_tax_payable_cgst = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    net_tax_payable_sgst = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    net_tax_payable_cess = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )
    total_net_tax_payable = Column(
        Numeric(15, 2), default=Decimal("0.00"), nullable=False
    )

    is_stale = Column(Boolean, default=False, nullable=False)

    filing_period = relationship("GSTFilingPeriod", back_populates="gstr3b_summaries")

    __table_args__ = (
        UniqueConstraint(
            "filing_period_id", "calculation_version", name="uq_gstr3b_period_version"
        ),
    )


def sync_gst_table_columns(bind_engine):
    """Safely adds missing columns to existing SQLite / PostgreSQL database tables without breaking existing data."""
    cols_to_add = [
        ("gst_registrations", "authorized_signatory", "VARCHAR(255)"),
        ("gst_filing_periods", "gstr1_status", "VARCHAR(30) DEFAULT 'draft'"),
        ("gst_filing_periods", "gstr3b_status", "VARCHAR(30) DEFAULT 'draft'"),
        ("gst_filing_periods", "gstr2b_status", "VARCHAR(30) DEFAULT 'pending'"),
        ("gst_sales_invoices", "original_invoice_number", "VARCHAR(50)"),
        ("gst_sales_invoices", "hsn_code", "VARCHAR(20)"),
        ("gst_sales_invoices", "description", "VARCHAR(255)"),
        ("gst_purchase_invoices", "hsn_code", "VARCHAR(20)"),
        ("gst_purchase_invoices", "notes", "TEXT"),
        ("gstr2b_records", "itc_reason", "VARCHAR(255)"),
    ]
    with bind_engine.connect() as conn:
        for tbl, col, col_type in cols_to_add:
            try:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {col_type}"))
                conn.commit()
            except Exception:
                pass
