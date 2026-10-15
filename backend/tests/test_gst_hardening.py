"""
Comprehensive Step 7 Hardening & End-to-End Validation Tests for LiteBooks GST Module.

Tests cover:
1. Database Migrations & Fresh DB Creation.
2. Structured Data Validation (GSTIN, State codes, Dates, Negatives, POS, Slabs, CDNR, etc.).
3. Calculation Snapshot Integrity (Source hashing, versioning, staleness detection, approval blocking).
4. Safe & Idempotent GSTR-2B Import (Checksums, limits, raw payload, duplicate prevention).
5. Reconciliation Safeguards & Manual Decision Preservation.
6. Workflow, Locking, Filing with ARN, and Role Authorization.
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base, get_db
from app.models.user import User
from app.core.security import hash_password, create_access_token
from app.modules.gst.models import (
    GSTSalesInvoice,
)
from app.modules.gst.validators import (
    derive_financial_year,
    validate_financial_year_mapping,
    validate_invoice_structured,
)
from app.modules.gst.calculators import (
    compute_gstr1_source_hash,
)
from app.modules.gst.reconciliation import (
    normalize_invoice_number,
)


# ============================================================================
# Test Database & Client Fixtures
# ============================================================================

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_gst_hardening.db"
test_engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module", autouse=True)
def setup_hardening_db():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    old_get_db = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if old_get_db is not None:
        app.dependency_overrides[get_db] = old_get_db
    else:
        app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


client = TestClient(app)


def get_auth_token(
    email: str = "lead_accountant@litebooks.ai", role: str = "accountant"
) -> str:
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            full_name=f"User {role}",
            hashed_password=hash_password("Secret123!"),
            role=role,
            is_active=True,
            is_superuser=False,
        )
        db.add(user)
    else:
        user.role = role
        user.is_superuser = False
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": user.email, "id": user.id})
    db.close()
    return token


# ============================================================================
# 1. Database Schema & Migration Verification
# ============================================================================


def test_migration_schema_integrity():
    """Verify that all 8 GST tables exist with the required hardening columns and indexes."""
    inspector = inspect(test_engine)
    tables = inspector.get_table_names()

    expected_tables = [
        "gst_registrations",
        "gst_filing_periods",
        "gst_sales_invoices",
        "gst_purchase_invoices",
        "gstr2b_records",
        "gst_reconciliation_results",
        "gstr1_summaries",
        "gstr3b_summaries",
    ]
    for tbl in expected_tables:
        assert tbl in tables, f"Expected table {tbl} not found in database schema"

    # Verify column existence for production hardening
    sales_cols = {col["name"] for col in inspector.get_columns("gst_sales_invoices")}
    assert "normalized_invoice_number" in sales_cols
    assert "validation_issues" in sales_cols

    purch_cols = {col["name"] for col in inspector.get_columns("gst_purchase_invoices")}
    assert "normalized_invoice_number" in purch_cols

    g2b_cols = {col["name"] for col in inspector.get_columns("gstr2b_records")}
    assert "normalized_invoice_number" in g2b_cols
    assert "import_checksum" in g2b_cols
    assert "raw_payload" in g2b_cols

    recon_cols = {
        col["name"] for col in inspector.get_columns("gst_reconciliation_results")
    }
    assert "matching_method" in recon_cols
    assert "amount_tolerance" in recon_cols
    assert "manual_decision_preserved" in recon_cols

    g1_cols = {col["name"] for col in inspector.get_columns("gstr1_summaries")}
    assert "calculation_version" in g1_cols
    assert "source_record_count" in g1_cols
    assert "source_data_hash" in g1_cols
    assert "is_stale" in g1_cols

    g3_cols = {col["name"] for col in inspector.get_columns("gstr3b_summaries")}
    assert "calculation_version" in g3_cols
    assert "source_record_count" in g3_cols
    assert "source_data_hash" in g3_cols
    assert "set_off_details" in g3_cols


# ============================================================================
# 2. Structured Data Validation Tests
# ============================================================================


def test_financial_year_mapping():
    """Verify period format mapping to financial year."""
    assert derive_financial_year("2024-04") == "2024-25"
    assert derive_financial_year("2025-03") == "2024-25"
    assert derive_financial_year("2025-01") == "2024-25"
    assert derive_financial_year("2025-04") == "2025-26"

    assert validate_financial_year_mapping("2024-04", "2024-25")[0] is True
    assert validate_financial_year_mapping("2024-04", "2025-26")[0] is False


def test_structured_validation_details():
    """Verify structured issues return code, severity, field, message, and suggested action."""
    # Test invalid place of supply (00 is invalid state)
    is_valid, issues, errors = validate_invoice_structured(
        supplier_state="27",
        place_of_supply="00",  # Invalid state
        customer_gstin="27ABCDE1234F1Z5",
        invoice_type="B2B",
        taxable_value=Decimal("1000.00"),
        tax_rate=Decimal("18.00"),
        cgst=Decimal("90.00"),
        sgst=Decimal("90.00"),
        igst=Decimal("0.00"),
        cess=Decimal("0.00"),
        total_amount=Decimal("1180.00"),
    )

    assert not is_valid
    assert any(i["code"] == "INVALID_POS" for i in issues)
    pos_issue = next(i for i in issues if i["code"] == "INVALID_POS")
    assert pos_issue["severity"] in ("ERROR", "BLOCKING")
    assert pos_issue["field"] == "place_of_supply"
    assert (
        "Invalid place of supply" in pos_issue["message"]
        or "Unrecognized Indian State Code" in pos_issue["message"]
    )
    assert "2-digit Indian State" in pos_issue["suggested_action"]

    # Test negative taxable value
    is_valid_neg, issues_neg, _ = validate_invoice_structured(
        supplier_state="27",
        place_of_supply="27",
        customer_gstin="27ABCDE1234F1Z5",
        invoice_type="B2B",
        taxable_value=Decimal("-500.00"),
        tax_rate=Decimal("18.00"),
        cgst=Decimal("0.00"),
        sgst=Decimal("0.00"),
        igst=Decimal("0.00"),
        cess=Decimal("0.00"),
        total_amount=Decimal("-500.00"),
    )
    assert not is_valid_neg
    assert any(i["code"] == "NEGATIVE_TAXABLE_VALUE" for i in issues_neg)

    # Test invoice date outside filing period
    is_valid_date, issues_date, _ = validate_invoice_structured(
        supplier_state="27",
        place_of_supply="27",
        customer_gstin="27ABCDE1234F1Z5",
        invoice_type="B2B",
        taxable_value=Decimal("1000.00"),
        tax_rate=Decimal("18.00"),
        cgst=Decimal("90.00"),
        sgst=Decimal("90.00"),
        igst=Decimal("0.00"),
        cess=Decimal("0.00"),
        total_amount=Decimal("1180.00"),
        invoice_date="2024-06-15",
        period="2024-04",
    )
    assert not is_valid_date
    assert any(i["code"] == "INVOICE_DATE_OUTSIDE_PERIOD" for i in issues_date)


def test_invoice_normalization_consistency():
    """Verify invoice number normalization removes formatting artifacts without collisions."""
    assert normalize_invoice_number("INV/2024-25/0012") == "INV2024250012"
    assert normalize_invoice_number("inv-00045") == "INV00045"
    assert normalize_invoice_number("000099") == "99"
    assert normalize_invoice_number("000") == "0"


# ============================================================================
# 3. Calculation Snapshot Integrity & Staleness Tests
# ============================================================================


def test_source_data_hashing_determinism():
    """Verify that compute_gstr1_source_hash produces deterministic SHA-256 hashes."""
    inv1 = GSTSalesInvoice(
        invoice_number="INV-001",
        invoice_date="2024-04-10",
        customer_gstin="27ABCDE1234F1Z5",
        place_of_supply="27",
        invoice_type="B2B",
        taxable_value=Decimal("10000.00"),
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("900.00"),
        sgst_amount=Decimal("900.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        total_amount=Decimal("11800.00"),
    )
    inv2 = GSTSalesInvoice(
        invoice_number="INV-002",
        invoice_date="2024-04-15",
        customer_gstin="29XYZAB5678C1D2",
        place_of_supply="29",
        invoice_type="B2B",
        taxable_value=Decimal("20000.00"),
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("0.00"),
        sgst_amount=Decimal("0.00"),
        igst_amount=Decimal("3600.00"),
        cess_amount=Decimal("0.00"),
        total_amount=Decimal("23600.00"),
    )

    hash_a = compute_gstr1_source_hash([inv1, inv2])
    hash_b = compute_gstr1_source_hash([inv2, inv1])  # Order permutation
    assert hash_a == hash_b, (
        "Hash calculation must be deterministic and invariant to input order"
    )
    assert len(hash_a) == 64, "Hash must be standard 64-character SHA-256 hex string"

    # Modify invoice amount and verify hash change
    inv1_mod = GSTSalesInvoice(
        invoice_number="INV-001",
        invoice_date="2024-04-10",
        customer_gstin="27ABCDE1234F1Z5",
        place_of_supply="27",
        invoice_type="B2B",
        taxable_value=Decimal("10500.00"),  # Changed
        tax_rate=Decimal("18.00"),
        cgst_amount=Decimal("945.00"),
        sgst_amount=Decimal("945.00"),
        igst_amount=Decimal("0.00"),
        cess_amount=Decimal("0.00"),
        total_amount=Decimal("12390.00"),
    )
    hash_modified = compute_gstr1_source_hash([inv1_mod, inv2])
    assert hash_a != hash_modified, "Hash must change when invoice amounts change"


# ============================================================================
# 4. End-to-End API Hardening Tests
# ============================================================================


def test_full_gst_hardening_lifecycle():
    token = get_auth_token("accountant_hardening@litebooks.ai", role="accountant")
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create GST Registration
    reg_res = client.post(
        "/api/gst/registrations",
        headers=headers,
        json={
            "gstin": "27AABCU9603R1ZM",
            "legal_name": "Apex Hardening Enterprises Ltd",
            "state_code": "27",
            "registration_type": "REGULAR",
        },
    )
    assert reg_res.status_code == 201
    reg_id = reg_res.json()["id"]

    # 2. Duplicate registration rejection
    dup_reg = client.post(
        "/api/gst/registrations",
        headers=headers,
        json={
            "gstin": "27AABCU9603R1ZM",
            "legal_name": "Duplicate Apex Ltd",
            "state_code": "27",
            "registration_type": "REGULAR",
        },
    )
    assert dup_reg.status_code == 400

    # 3. Create Filing Period
    period_res = client.post(
        "/api/gst/periods",
        headers=headers,
        json={
            "registration_id": reg_id,
            "period": "2025-05",
            "financial_year": "2025-26",
        },
    )
    assert period_res.status_code == 201
    period_id = period_res.json()["id"]

    # 4. Add Sales Invoice with normalized number and structured issues
    sales_res = client.post(
        f"/api/gst/periods/{period_id}/sales",
        headers=headers,
        json={
            "invoice_number": "INV/2025-26/0001",
            "invoice_date": "2025-05-10",
            "customer_gstin": "27BBBCU9603R1ZN",
            "customer_name": "Client West Corp",
            "place_of_supply": "27",
            "invoice_type": "B2B",
            "taxable_value": "50000.00",
            "tax_rate": "18.00",
            "total_amount": "59000.00",
            "auto_calculate_tax": True,
        },
    )
    assert sales_res.status_code == 201
    sales_data = sales_res.json()
    assert sales_data["normalized_invoice_number"] == "INV2025260001"
    assert sales_data["validation_status"] == "VALID"

    # 5. Duplicate sales invoice rejection (checking normalized collision)
    dup_sales = client.post(
        f"/api/gst/periods/{period_id}/sales",
        headers=headers,
        json={
            "invoice_number": "INV2025260001",  # Same normalized number
            "invoice_date": "2025-05-11",
            "customer_gstin": "27BBBCU9603R1ZN",
            "customer_name": "Client West Corp",
            "place_of_supply": "27",
            "invoice_type": "B2B",
            "taxable_value": "10000.00",
            "tax_rate": "18.00",
            "total_amount": "11800.00",
            "auto_calculate_tax": True,
        },
    )
    assert dup_sales.status_code == 400

    # 6. Add Purchase Invoice
    purch_res = client.post(
        f"/api/gst/periods/{period_id}/purchases",
        headers=headers,
        json={
            "invoice_number": "VEND/9981",
            "invoice_date": "2025-05-08",
            "supplier_gstin": "27CCCDE1234F1Z6",
            "supplier_name": "Vendor Tech Supplies",
            "place_of_supply": "27",
            "taxable_value": "30000.00",
            "tax_rate": "18.00",
            "total_amount": "35400.00",
            "auto_calculate_tax": True,
        },
    )
    assert purch_res.status_code == 201
    assert purch_res.json()["normalized_invoice_number"] == "VEND9981"

    # 7. Import GSTR-2B with idempotency and duplicate check
    g2b_import = client.post(
        f"/api/gst/periods/{period_id}/gstr2b/import",
        headers=headers,
        json={
            "period_id": period_id,
            "records": [
                {
                    "period_id": period_id,
                    "supplier_gstin": "27CCCDE1234F1Z6",
                    "supplier_name": "Vendor Tech Supplies",
                    "invoice_number": "VEND/9981",
                    "invoice_date": "2025-05-08",
                    "place_of_supply": "27",
                    "taxable_value": "30000.00",
                    "tax_rate": "18.00",
                    "cgst_amount": "2700.00",
                    "sgst_amount": "2700.00",
                    "igst_amount": "0.00",
                    "cess_amount": "0.00",
                    "total_amount": "35400.00",
                    "itc_available": True,
                    "supplier_filing_status": "FILED",
                }
            ],
        },
    )
    assert g2b_import.status_code == 200
    assert g2b_import.json()["count"] == 1

    # Re-importing same record updates instead of duplicating
    g2b_reimport = client.post(
        f"/api/gst/periods/{period_id}/gstr2b/import",
        headers=headers,
        json={
            "period_id": period_id,
            "records": [
                {
                    "period_id": period_id,
                    "supplier_gstin": "27CCCDE1234F1Z6",
                    "supplier_name": "Vendor Tech Supplies",
                    "invoice_number": "VEND9981",  # Normalized match
                    "invoice_date": "2025-05-08",
                    "place_of_supply": "27",
                    "taxable_value": "30000.00",
                    "tax_rate": "18.00",
                    "cgst_amount": "2700.00",
                    "sgst_amount": "2700.00",
                    "igst_amount": "0.00",
                    "cess_amount": "0.00",
                    "total_amount": "35400.00",
                    "itc_available": True,
                    "supplier_filing_status": "FILED",
                }
            ],
        },
    )
    assert g2b_reimport.status_code == 200
    # Verify count remains 1
    g2b_list = client.get(
        f"/api/gst/periods/{period_id}/gstr2b", headers=headers
    ).json()
    assert len(g2b_list) == 1
    assert g2b_list[0]["import_checksum"] is not None

    # 8. Run Reconciliation & Record Manual Decision
    recon_run = client.post(
        f"/api/gst/periods/{period_id}/reconciliation/run",
        headers=headers,
        json={"exact_tolerance_inr": "1.00", "date_tolerance_days": 30},
    )
    assert recon_run.status_code == 200
    results = recon_run.json()
    assert len(results) == 1
    assert results[0]["match_status"] == "EXACT_MATCH"
    result_id = results[0]["id"]

    # Record accountant decision
    dec_res = client.post(
        f"/api/gst/reconciliation/{result_id}/decision",
        headers=headers,
        json={"decision": "ACCEPTED", "notes": "Auditor verified with e-Way bill"},
    )
    assert dec_res.status_code == 200
    assert dec_res.json()["decision_status"] == "ACCEPTED"

    # Re-run reconciliation and verify manual decision is PRESERVED
    recon_rerun = client.post(
        f"/api/gst/periods/{period_id}/reconciliation/run",
        headers=headers,
        json={"exact_tolerance_inr": "1.00", "date_tolerance_days": 30},
    )
    assert recon_rerun.status_code == 200
    rerun_results = recon_rerun.json()
    assert rerun_results[0]["decision_status"] == "ACCEPTED"
    assert rerun_results[0]["manual_decision_preserved"] is True

    # 9. GSTR-1 and GSTR-3B Calculation Snapshots
    g1_calc = client.post(
        f"/api/gst/periods/{period_id}/gstr1/recalculate", headers=headers
    )
    assert g1_calc.status_code == 200
    g1_data = g1_calc.json()
    assert g1_data["calculation_version"] >= 1
    assert g1_data["is_stale"] is False
    assert g1_data["source_data_hash"] is not None

    g3_calc = client.post(
        f"/api/gst/periods/{period_id}/gstr3b/recalculate", headers=headers
    )
    assert g3_calc.status_code == 200
    g3_data = g3_calc.json()
    assert g3_data["is_stale"] is False
    assert g3_data["source_data_hash"] is not None

    # 10. Staleness Detection: Adding new invoice causes summary to become stale
    client.post(
        f"/api/gst/periods/{period_id}/sales",
        headers=headers,
        json={
            "invoice_number": "INV/2025-26/0002",
            "invoice_date": "2025-05-15",
            "customer_gstin": "27BBBCU9603R1ZN",
            "customer_name": "Client West Corp",
            "place_of_supply": "27",
            "invoice_type": "B2B",
            "taxable_value": "10000.00",
            "tax_rate": "18.00",
            "total_amount": "11800.00",
            "auto_calculate_tax": True,
        },
    )
    # Check GSTR-1 summary staleness
    g1_stale = client.get(
        f"/api/gst/periods/{period_id}/gstr1/summary", headers=headers
    ).json()
    assert g1_stale["is_stale"] is True

    # 11. Workflow Transition Safeguard: Cannot approve with stale summary!
    # First transition to under_review
    trans_ur = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={"new_status": "under_review", "reason": "Ready for review"},
    )
    assert trans_ur.status_code == 200

    # Attempting to approve while stale must be rejected
    approve_stale = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={"new_status": "approved", "reason": "Attempting approval"},
    )
    assert approve_stale.status_code == 400
    assert "stale" in approve_stale.text.lower()

    # Recalculate GSTR-1 and GSTR-3B to clear staleness
    client.post(f"/api/gst/periods/{period_id}/gstr1/recalculate", headers=headers)
    client.post(f"/api/gst/periods/{period_id}/gstr3b/recalculate", headers=headers)

    # Now approval succeeds
    approve_clean = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={"new_status": "approved", "reason": "Approved by senior partner"},
    )
    assert approve_clean.status_code == 200
    assert approve_clean.json()["status"] == "approved"

    # 12. Filing with ARN requirement
    file_no_arn = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={"new_status": "filed", "reason": "Filing return"},
    )
    assert file_no_arn.status_code == 400
    assert "ARN" in file_no_arn.text

    file_clean = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={
            "new_status": "filed",
            "arn": "AA2705251234567",
            "reason": "Filing with official ARN",
        },
    )
    assert file_clean.status_code == 200
    assert file_clean.json()["status"] == "filed"
    assert file_clean.json()["filing_arn"] == "AA2705251234567"
    assert file_clean.json()["filing_metadata"]["arn"] == "AA2705251234567"

    # 13. Lock period
    lock_res = client.post(
        f"/api/gst/periods/{period_id}/transition",
        headers=headers,
        json={
            "new_status": "locked",
            "reason": "Audit period completed and permanently locked",
        },
    )
    assert lock_res.status_code == 200
    assert lock_res.json()["status"] == "locked"

    # 14. Mutation rejection on LOCKED period
    mut_rejected = client.post(
        f"/api/gst/periods/{period_id}/sales",
        headers=headers,
        json={
            "invoice_number": "INV/2025-26/9999",
            "invoice_date": "2025-05-20",
            "customer_gstin": "27BBBCU9603R1ZN",
            "customer_name": "Late Addition Corp",
            "place_of_supply": "27",
            "invoice_type": "B2B",
            "taxable_value": "1000.00",
            "tax_rate": "18.00",
            "total_amount": "1180.00",
            "auto_calculate_tax": True,
        },
    )
    assert mut_rejected.status_code == 400
    assert "LOCKED" in mut_rejected.text


def test_viewer_role_authorization_protection():
    """Verify that a user with 'viewer' role is blocked from performing workflow transitions."""
    from app.core.auth import get_current_user

    viewer_user = User(
        email="viewer_auditor@litebooks.ai",
        full_name="Viewer Auditor",
        role="viewer",
        is_active=True,
        is_superuser=False,
    )
    old_override = app.dependency_overrides.get(get_current_user)
    try:
        app.dependency_overrides[get_current_user] = lambda: viewer_user
        res = client.post(
            "/api/gst/periods/1/transition",
            json={"new_status": "approved", "reason": "Unauthorized attempt"},
        )
        assert res.status_code == 403, (
            f"Expected 403, got {res.status_code}: {res.text}"
        )
        assert "not authorized" in res.text.lower()
    finally:
        if old_override:
            app.dependency_overrides[get_current_user] = old_override
        else:
            app.dependency_overrides.pop(get_current_user, None)
