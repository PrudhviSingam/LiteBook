"""001_gst_module_complete_schema

Revision ID: 001_gst_module
Revises: None
Create Date: 2026-10-02 21:40:00.000000

Comprehensive, safe database migration for:
- Core tables (if initializing fresh database)
- GST Registrations, Filing Periods, Sales Invoices, Purchase Invoices
- GSTR-2B Records, Reconciliation Results, GSTR-1 Summaries, GSTR-3B Summaries
- Snapshot hashes, calculation versions, normalized invoice numbers, import checksums
"""
from typing import Sequence, Union
from decimal import Decimal
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision: str = '001_gst_module'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = set(inspector.get_table_names())

    # ------------------------------------------------------------------------
    # 1. Baseline Core Tables (Ensure they exist for fresh DB creation)
    # ------------------------------------------------------------------------
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("email", sa.String(255), unique=True, index=True, nullable=False),
            sa.Column("username", sa.String(100), unique=True, index=True, nullable=True),
            sa.Column("full_name", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
            sa.Column("is_superuser", sa.Boolean(), default=True, nullable=False),
            sa.Column("hashed_password", sa.String(255), nullable=True),
            sa.Column("role", sa.String(50), default="accountant", nullable=False),
            sa.Column("organization_id", sa.String(100), nullable=True),
        )

    # ------------------------------------------------------------------------
    # 2. GST Registrations
    # ------------------------------------------------------------------------
    if "gst_registrations" not in existing_tables:
        op.create_table(
            "gst_registrations",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("organization_id", sa.String(100), nullable=True, index=True),
            sa.Column("gstin", sa.String(15), nullable=False, index=True),
            sa.Column("legal_name", sa.String(255), nullable=False),
            sa.Column("trade_name", sa.String(255), nullable=True),
            sa.Column("state_code", sa.String(2), nullable=False),
            sa.Column("state_name", sa.String(100), nullable=True),
            sa.Column("registration_type", sa.String(50), default="REGULAR", nullable=False),
            sa.Column("authorized_signatory", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), default=True, nullable=False),
            sa.UniqueConstraint("user_id", "gstin", name="uq_user_gstin"),
        )
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gst_registrations")}
        with op.batch_alter_table("gst_registrations") as batch_op:
            if "authorized_signatory" not in existing_cols:
                batch_op.add_column(sa.Column("authorized_signatory", sa.String(255), nullable=True))

    # ------------------------------------------------------------------------
    # 3. GST Filing Periods
    # ------------------------------------------------------------------------
    if "gst_filing_periods" not in existing_tables:
        op.create_table(
            "gst_filing_periods",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("financial_year", sa.String(9), nullable=False, index=True),
            sa.Column("status", sa.String(30), default="draft", nullable=False, index=True),
            sa.Column("gstr1_status", sa.String(30), default="draft", nullable=False),
            sa.Column("gstr3b_status", sa.String(30), default="draft", nullable=False),
            sa.Column("gstr2b_status", sa.String(30), default="pending", nullable=False),
            sa.Column("locked_at", sa.DateTime(), nullable=True),
            sa.Column("locked_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("filed_at", sa.DateTime(), nullable=True),
            sa.Column("filing_arn", sa.String(50), nullable=True),
            sa.Column("filing_metadata", sa.Text(), nullable=True),
            sa.Column("gstr1_hash", sa.String(64), nullable=True),
            sa.Column("gstr3b_hash", sa.String(64), nullable=True),
            sa.Column("gstr2b_recon_hash", sa.String(64), nullable=True),
            sa.UniqueConstraint("gst_registration_id", "period", name="uq_gstin_period"),
        )
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gst_filing_periods")}
        with op.batch_alter_table("gst_filing_periods") as batch_op:
            if "filing_metadata" not in existing_cols:
                batch_op.add_column(sa.Column("filing_metadata", sa.Text(), nullable=True))
            if "gstr1_hash" not in existing_cols:
                batch_op.add_column(sa.Column("gstr1_hash", sa.String(64), nullable=True))
            if "gstr3b_hash" not in existing_cols:
                batch_op.add_column(sa.Column("gstr3b_hash", sa.String(64), nullable=True))
            if "gstr2b_recon_hash" not in existing_cols:
                batch_op.add_column(sa.Column("gstr2b_recon_hash", sa.String(64), nullable=True))

    # ------------------------------------------------------------------------
    # 4. GST Sales Invoices
    # ------------------------------------------------------------------------
    if "gst_sales_invoices" not in existing_tables:
        op.create_table(
            "gst_sales_invoices",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("invoice_number", sa.String(50), nullable=False, index=True),
            sa.Column("normalized_invoice_number", sa.String(50), nullable=True, index=True),
            sa.Column("invoice_date", sa.String(10), nullable=False),
            sa.Column("customer_gstin", sa.String(15), nullable=True, index=True),
            sa.Column("customer_name", sa.String(255), nullable=False),
            sa.Column("place_of_supply", sa.String(2), nullable=False),
            sa.Column("invoice_type", sa.String(20), default="B2B", nullable=False, index=True),
            sa.Column("supply_type", sa.String(20), default="INTRA_STATE", nullable=False),
            sa.Column("reverse_charge", sa.Boolean(), default=False, nullable=False),
            sa.Column("taxable_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("tax_rate", sa.Numeric(5, 2), default=Decimal("18.00"), nullable=False),
            sa.Column("igst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("sgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cess_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("original_invoice_number", sa.String(50), nullable=True),
            sa.Column("hsn_code", sa.String(20), nullable=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("validation_status", sa.String(20), default="VALID", nullable=False, index=True),
            sa.Column("validation_errors", sa.Text(), nullable=True),
            sa.Column("validation_issues", sa.Text(), nullable=True),
            sa.UniqueConstraint("gst_registration_id", "invoice_number", "period", name="uq_sales_inv_period"),
        )
        op.create_index("ix_sales_reg_period", "gst_sales_invoices", ["gst_registration_id", "period"])
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gst_sales_invoices")}
        with op.batch_alter_table("gst_sales_invoices") as batch_op:
            if "normalized_invoice_number" not in existing_cols:
                batch_op.add_column(sa.Column("normalized_invoice_number", sa.String(50), nullable=True))
                batch_op.create_index("ix_gst_sales_invoices_normalized", ["normalized_invoice_number"], unique=False)
            if "validation_issues" not in existing_cols:
                batch_op.add_column(sa.Column("validation_issues", sa.Text(), nullable=True))

    # ------------------------------------------------------------------------
    # 5. GST Purchase Invoices
    # ------------------------------------------------------------------------
    if "gst_purchase_invoices" not in existing_tables:
        op.create_table(
            "gst_purchase_invoices",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("invoice_number", sa.String(50), nullable=False, index=True),
            sa.Column("normalized_invoice_number", sa.String(50), nullable=True, index=True),
            sa.Column("invoice_date", sa.String(10), nullable=False),
            sa.Column("supplier_gstin", sa.String(15), nullable=False, index=True),
            sa.Column("supplier_name", sa.String(255), nullable=False),
            sa.Column("place_of_supply", sa.String(2), nullable=False),
            sa.Column("supply_type", sa.String(20), default="INTRA_STATE", nullable=False),
            sa.Column("invoice_type", sa.String(20), default="B2B", nullable=False),
            sa.Column("reverse_charge", sa.Boolean(), default=False, nullable=False),
            sa.Column("taxable_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("tax_rate", sa.Numeric(5, 2), default=Decimal("18.00"), nullable=False),
            sa.Column("igst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("sgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cess_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_eligibility", sa.String(20), default="ELIGIBLE", nullable=False),
            sa.Column("itc_category", sa.String(30), default="ALL_OTHER_ITC", nullable=False),
            sa.Column("hsn_code", sa.String(20), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("match_status", sa.String(30), default="PENDING", nullable=False, index=True),
            sa.UniqueConstraint("gst_registration_id", "supplier_gstin", "invoice_number", "period", name="uq_purch_inv_period"),
        )
        op.create_index("ix_purch_reg_period", "gst_purchase_invoices", ["gst_registration_id", "period"])
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gst_purchase_invoices")}
        with op.batch_alter_table("gst_purchase_invoices") as batch_op:
            if "normalized_invoice_number" not in existing_cols:
                batch_op.add_column(sa.Column("normalized_invoice_number", sa.String(50), nullable=True))
                batch_op.create_index("ix_gst_purchase_invoices_normalized", ["normalized_invoice_number"], unique=False)

    # ------------------------------------------------------------------------
    # 6. GSTR-2B Records
    # ------------------------------------------------------------------------
    if "gstr2b_records" not in existing_tables:
        op.create_table(
            "gstr2b_records",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("supplier_gstin", sa.String(15), nullable=False, index=True),
            sa.Column("supplier_name", sa.String(255), nullable=False),
            sa.Column("invoice_number", sa.String(50), nullable=False, index=True),
            sa.Column("normalized_invoice_number", sa.String(50), nullable=True, index=True),
            sa.Column("invoice_date", sa.String(10), nullable=False),
            sa.Column("invoice_type", sa.String(20), default="B2B", nullable=False),
            sa.Column("place_of_supply", sa.String(2), nullable=False),
            sa.Column("reverse_charge", sa.Boolean(), default=False, nullable=False),
            sa.Column("taxable_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("tax_rate", sa.Numeric(5, 2), default=Decimal("18.00"), nullable=False),
            sa.Column("igst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("sgst_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("cess_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_amount", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_available", sa.Boolean(), default=True, nullable=False),
            sa.Column("itc_reason", sa.String(255), nullable=True),
            sa.Column("gstr2b_filing_date", sa.String(10), nullable=True),
            sa.Column("supplier_filing_status", sa.String(20), default="Y", nullable=False),
            sa.Column("import_checksum", sa.String(64), nullable=True, index=True),
            sa.Column("raw_payload", sa.Text(), nullable=True),
            sa.Column("uploader_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("match_status", sa.String(30), default="PENDING", nullable=False, index=True),
            sa.UniqueConstraint("gst_registration_id", "supplier_gstin", "invoice_number", "period", name="uq_gstr2b_inv_period"),
        )
        op.create_index("ix_gstr2b_reg_period", "gstr2b_records", ["gst_registration_id", "period"])
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gstr2b_records")}
        with op.batch_alter_table("gstr2b_records") as batch_op:
            if "normalized_invoice_number" not in existing_cols:
                batch_op.add_column(sa.Column("normalized_invoice_number", sa.String(50), nullable=True))
                batch_op.create_index("ix_gstr2b_records_normalized", ["normalized_invoice_number"], unique=False)
            if "import_checksum" not in existing_cols:
                batch_op.add_column(sa.Column("import_checksum", sa.String(64), nullable=True))
                batch_op.create_index("ix_gstr2b_records_checksum", ["import_checksum"], unique=False)
            if "raw_payload" not in existing_cols:
                batch_op.add_column(sa.Column("raw_payload", sa.Text(), nullable=True))
            if "uploader_id" not in existing_cols:
                batch_op.add_column(sa.Column("uploader_id", sa.Integer(), nullable=True))

    # ------------------------------------------------------------------------
    # 7. GST Reconciliation Results
    # ------------------------------------------------------------------------
    if "gst_reconciliation_results" not in existing_tables:
        op.create_table(
            "gst_reconciliation_results",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("purchase_invoice_id", sa.Integer(), sa.ForeignKey("gst_purchase_invoices.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("gstr2b_record_id", sa.Integer(), sa.ForeignKey("gstr2b_records.id", ondelete="CASCADE"), nullable=True, index=True),
            sa.Column("match_type", sa.String(30), nullable=False, index=True),
            sa.Column("match_score", sa.Numeric(5, 2), default=Decimal("100.00"), nullable=False),
            sa.Column("matching_method", sa.String(50), default="AUTO_RULE_ENGINE", nullable=False),
            sa.Column("amount_tolerance", sa.Numeric(10, 2), default=Decimal("1.00"), nullable=False),
            sa.Column("date_tolerance_days", sa.Integer(), default=3, nullable=False),
            sa.Column("tax_difference", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("taxable_difference", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("date_difference_days", sa.Integer(), default=0, nullable=False),
            sa.Column("mismatch_reasons", sa.Text(), nullable=True),
            sa.Column("status", sa.String(30), default="UNREVIEWED", nullable=False, index=True),
            sa.Column("accountant_notes", sa.Text(), nullable=True),
            sa.Column("manual_decision_preserved", sa.Boolean(), default=False, nullable=False),
        )
        op.create_index("ix_recon_reg_period", "gst_reconciliation_results", ["gst_registration_id", "period"])
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gst_reconciliation_results")}
        with op.batch_alter_table("gst_reconciliation_results") as batch_op:
            if "matching_method" not in existing_cols:
                batch_op.add_column(sa.Column("matching_method", sa.String(50), server_default="AUTO_RULE_ENGINE", nullable=False))
            if "amount_tolerance" not in existing_cols:
                batch_op.add_column(sa.Column("amount_tolerance", sa.Numeric(10, 2), server_default="1.00", nullable=False))
            if "date_tolerance_days" not in existing_cols:
                batch_op.add_column(sa.Column("date_tolerance_days", sa.Integer(), server_default="3", nullable=False))
            if "manual_decision_preserved" not in existing_cols:
                batch_op.add_column(sa.Column("manual_decision_preserved", sa.Boolean(), server_default=sa.text("0"), nullable=False))
            if "user_id" not in existing_cols:
                batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    # ------------------------------------------------------------------------
    # 8. GSTR-1 Summaries
    # ------------------------------------------------------------------------
    if "gstr1_summaries" not in existing_tables:
        op.create_table(
            "gstr1_summaries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("calculation_version", sa.Integer(), default=1, nullable=False),
            sa.Column("source_record_count", sa.Integer(), default=0, nullable=False),
            sa.Column("source_data_hash", sa.String(64), nullable=True, index=True),
            sa.Column("calculation_metadata", sa.Text(), nullable=True),
            sa.Column("total_taxable_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_invoice_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_invoices_count", sa.Integer(), default=0, nullable=False),
            sa.Column("b2b_summary", sa.Text(), nullable=True),
            sa.Column("b2cl_summary", sa.Text(), nullable=True),
            sa.Column("b2cs_summary", sa.Text(), nullable=True),
            sa.Column("export_summary", sa.Text(), nullable=True),
            sa.Column("cdnr_summary", sa.Text(), nullable=True),
            sa.Column("nil_exempt_summary", sa.Text(), nullable=True),
            sa.Column("is_stale", sa.Boolean(), default=False, nullable=False),
            sa.UniqueConstraint("filing_period_id", "calculation_version", name="uq_gstr1_period_version"),
        )
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gstr1_summaries")}
        with op.batch_alter_table("gstr1_summaries") as batch_op:
            if "calculation_version" not in existing_cols:
                batch_op.add_column(sa.Column("calculation_version", sa.Integer(), server_default="1", nullable=False))
            if "source_record_count" not in existing_cols:
                batch_op.add_column(sa.Column("source_record_count", sa.Integer(), server_default="0", nullable=False))
            if "source_data_hash" not in existing_cols:
                batch_op.add_column(sa.Column("source_data_hash", sa.String(64), nullable=True))
                batch_op.create_index("ix_gstr1_summaries_hash", ["source_data_hash"], unique=False)
            if "calculation_metadata" not in existing_cols:
                batch_op.add_column(sa.Column("calculation_metadata", sa.Text(), nullable=True))

    # ------------------------------------------------------------------------
    # 9. GSTR-3B Summaries
    # ------------------------------------------------------------------------
    if "gstr3b_summaries" not in existing_tables:
        op.create_table(
            "gstr3b_summaries",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("gst_registration_id", sa.Integer(), sa.ForeignKey("gst_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("filing_period_id", sa.Integer(), sa.ForeignKey("gst_filing_periods.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("period", sa.String(7), nullable=False, index=True),
            sa.Column("calculation_version", sa.Integer(), default=1, nullable=False),
            sa.Column("source_record_count", sa.Integer(), default=0, nullable=False),
            sa.Column("source_data_hash", sa.String(64), nullable=True, index=True),
            sa.Column("set_off_details", sa.Text(), nullable=True),
            sa.Column("calculation_metadata", sa.Text(), nullable=True),
            sa.Column("outward_taxable_value", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("outward_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("outward_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("outward_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("outward_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("interstate_unregistered_taxable", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("interstate_unregistered_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_all_other_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_all_other_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_all_other_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_all_other_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_reversed_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_reversed_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_reversed_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("itc_reversed_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_itc_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_itc_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_itc_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_itc_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("inward_exempt_nil", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_tax_payable_igst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_tax_payable_cgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_tax_payable_sgst", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("net_tax_payable_cess", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("total_net_tax_payable", sa.Numeric(15, 2), default=Decimal("0.00"), nullable=False),
            sa.Column("is_stale", sa.Boolean(), default=False, nullable=False),
            sa.UniqueConstraint("filing_period_id", "calculation_version", name="uq_gstr3b_period_version"),
        )
    else:
        existing_cols = {c["name"] for c in inspector.get_columns("gstr3b_summaries")}
        with op.batch_alter_table("gstr3b_summaries") as batch_op:
            if "calculation_version" not in existing_cols:
                batch_op.add_column(sa.Column("calculation_version", sa.Integer(), server_default="1", nullable=False))
            if "source_record_count" not in existing_cols:
                batch_op.add_column(sa.Column("source_record_count", sa.Integer(), server_default="0", nullable=False))
            if "source_data_hash" not in existing_cols:
                batch_op.add_column(sa.Column("source_data_hash", sa.String(64), nullable=True))
                batch_op.create_index("ix_gstr3b_summaries_hash", ["source_data_hash"], unique=False)
            if "set_off_details" not in existing_cols:
                batch_op.add_column(sa.Column("set_off_details", sa.Text(), nullable=True))
            if "calculation_metadata" not in existing_cols:
                batch_op.add_column(sa.Column("calculation_metadata", sa.Text(), nullable=True))


def downgrade() -> None:
    # Drop in reverse topological order
    op.drop_table("gstr3b_summaries")
    op.drop_table("gstr1_summaries")
    op.drop_table("gst_reconciliation_results")
    op.drop_table("gstr2b_records")
    op.drop_table("gst_purchase_invoices")
    op.drop_table("gst_sales_invoices")
    op.drop_table("gst_filing_periods")
    op.drop_table("gst_registrations")
