"""
Comprehensive Unit and Integration Tests for LiteBooks GST Module (Step 6).
Tests tax math, rounding, validations, GSTR-1 aggregation, GSTR-3B statutory set-off,
GSTR-2B reconciliation, company isolation, period locking, and audit events.
"""

from datetime import date
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal, engine
from app.models.user import User
from app.models.history import HistoryRecord
from app.core.security import create_access_token, hash_password
from app.modules.gst.models import (
    GSTRegistration,
)
from app.modules.gst.validators import (
    validate_gstin,
    calculate_tax_split,
)
from app.modules.gst.calculators import (
    aggregate_gstr1,
    calculate_gstr3b,
)
from app.modules.gst.reconciliation import (
    reconcile_purchases_with_gstr2b,
)
from app.modules.gst.constants import MatchStatus


# ============================================================================
# Unit Tests: Validators & Rounding
# ============================================================================


def test_gstin_validator():
    # Valid GSTIN (Maharashtra: 27)
    valid, err = validate_gstin("27AAPFU0939F1ZV")
    assert valid is True
    assert err is None

    # Invalid state code 00
    valid, err = validate_gstin("00AAPFU0939F1ZV")
    assert valid is False
    assert "Invalid state code" in err

    # Too short
    valid, err = validate_gstin("27AAPFU0939F1")
    assert valid is False

    # Bad format (14th char not Z)
    valid, err = validate_gstin("27AAPFU0939F19V")
    assert valid is False


def test_tax_split_calculation():
    # Intra-state: MH (27) to MH (27) at 18%
    intra = calculate_tax_split(
        place_of_supply="27",
        supplier_state="27",
        taxable_value=Decimal("10000.00"),
        tax_rate=Decimal("18.00"),
    )
    assert intra["is_interstate"] is False
    assert intra["cgst_amount"] == Decimal("900.00")
    assert intra["sgst_amount"] == Decimal("900.00")
    assert intra["igst_amount"] == Decimal("0.00")

    # Inter-state: MH (27) to KA (29) at 18%
    inter = calculate_tax_split(
        place_of_supply="29",
        supplier_state="27",
        taxable_value=Decimal("10000.00"),
        tax_rate=Decimal("18.00"),
    )
    assert inter["is_interstate"] is True
    assert inter["cgst_amount"] == Decimal("0.00")
    assert inter["sgst_amount"] == Decimal("0.00")
    assert inter["igst_amount"] == Decimal("1800.00")


# ============================================================================
# Unit Tests: GSTR-1 Aggregation
# ============================================================================


def test_gstr1_aggregation():
    class MockInvoice:
        def __init__(
            self,
            inv_type,
            pos,
            taxable,
            cgst,
            sgst,
            igst,
            cess,
            total,
            customer_gstin=None,
            supply_type="INTRA_STATE",
            tax_rate=Decimal("18.00"),
        ):
            self.invoice_number = "INV-001"
            self.invoice_date = "2024-04-01"
            self.customer_name = "Client"
            self.customer_gstin = customer_gstin
            self.invoice_type = inv_type
            self.place_of_supply = pos
            self.supply_type = supply_type
            self.tax_rate = Decimal(str(tax_rate))
            self.taxable_value = Decimal(str(taxable))
            self.cgst_amount = Decimal(str(cgst))
            self.sgst_amount = Decimal(str(sgst))
            self.igst_amount = Decimal(str(igst))
            self.cess_amount = Decimal(str(cess))
            self.total_amount = Decimal(str(total))
            self.original_invoice_number = None

    invoices = [
        # B2B Intra with valid 15-char GSTIN
        MockInvoice(
            "B2B",
            "27",
            "10000.00",
            "900.00",
            "900.00",
            "0.00",
            "0.00",
            "11800.00",
            customer_gstin="27AAPFU0939F1ZV",
        ),
        # B2CL Inter-state > 2.5L
        MockInvoice(
            "B2CL",
            "29",
            "300000.00",
            "0.00",
            "0.00",
            "54000.00",
            "0.00",
            "354000.00",
            supply_type="INTER_STATE",
        ),
        # B2CS Intra
        MockInvoice(
            "B2CS", "27", "5000.00", "450.00", "450.00", "0.00", "0.00", "5900.00"
        ),
        # Export Inter-state
        MockInvoice(
            "EXPORT",
            "97",
            "50000.00",
            "0.00",
            "0.00",
            "9000.00",
            "0.00",
            "59000.00",
            supply_type="INTER_STATE",
        ),
    ]

    summary = aggregate_gstr1(invoices)
    assert summary["total_taxable_value"] == Decimal("365000.00")
    assert summary["total_invoices_count"] == 4
    assert Decimal(summary["tables"]["b2b"]["taxable_value"]) == Decimal("10000.00")
    assert Decimal(summary["tables"]["b2b"]["cgst"]) == Decimal("900.00")
    assert Decimal(summary["tables"]["b2cl"]["taxable_value"]) == Decimal("300000.00")
    assert Decimal(summary["tables"]["b2cl"]["igst"]) == Decimal("54000.00")
    assert Decimal(summary["tables"]["b2cs"]["taxable_value"]) == Decimal("5000.00")
    assert Decimal(summary["tables"]["exports"]["taxable_value"]) == Decimal("50000.00")


# ============================================================================
# Unit Tests: GSTR-3B Computation & Set-off Order
# ============================================================================


def test_gstr3b_statutory_set_off():
    class MockSales:
        def __init__(
            self,
            taxable,
            cgst,
            sgst,
            igst,
            cess=Decimal("0.00"),
            rcm=False,
            supply_type="INTRA_STATE",
        ):
            self.taxable_value = Decimal(str(taxable))
            self.cgst_amount = Decimal(str(cgst))
            self.sgst_amount = Decimal(str(sgst))
            self.igst_amount = Decimal(str(igst))
            self.cess_amount = Decimal(str(cess))
            self.reverse_charge = rcm
            self.customer_gstin = None
            self.supply_type = supply_type

    class MockPurchase:
        def __init__(
            self,
            taxable,
            cgst,
            sgst,
            igst,
            elig="ELIGIBLE",
            cat="ALL_OTHER_ITC",
            rcm=False,
            invoice_type="B2B",
        ):
            self.taxable_value = Decimal(str(taxable))
            self.cgst_amount = Decimal(str(cgst))
            self.sgst_amount = Decimal(str(sgst))
            self.igst_amount = Decimal(str(igst))
            self.cess_amount = Decimal("0.00")
            self.itc_eligibility = elig
            self.itc_category = cat
            self.reverse_charge = rcm
            self.invoice_type = invoice_type

    # Scenario: Outward IGST = 5000, CGST = 2000, SGST = 2000
    # ITC Available: IGST = 6000, CGST = 1000, SGST = 1000
    # Statutory rule:
    # 1. IGST ITC (6000) clears Outward IGST (5000) -> 1000 IGST ITC left
    # 2. IGST ITC remainder (1000) clears CGST liability (2000) -> CGST liability 1000 left
    # 3. CGST ITC (1000) clears remaining CGST liability (1000) -> CGST liability 0
    # 4. SGST ITC (1000) clears SGST liability (2000) -> SGST payable 1000
    # 5. Note: CGST & SGST never cross-utilize!
    sales = [MockSales("50000.00", "2000.00", "2000.00", "5000.00")]
    purchases = [MockPurchase("60000.00", "1000.00", "1000.00", "6000.00")]

    gstr3b = calculate_gstr3b(sales, purchases)

    assert gstr3b["outward_igst"] == Decimal("5000.00")
    assert gstr3b["outward_cgst"] == Decimal("2000.00")
    assert gstr3b["outward_sgst"] == Decimal("2000.00")

    assert gstr3b["net_tax_payable_igst"] == Decimal("0.00")
    assert gstr3b["net_tax_payable_cgst"] == Decimal("0.00")
    assert gstr3b["net_tax_payable_sgst"] == Decimal("1000.00")


# ============================================================================
# Unit Tests: GSTR-2B Reconciliation Engine
# ============================================================================


def test_gstr2b_reconciliation_matching():
    class MockBooks:
        def __init__(self, id_val, gstin, inv_num, inv_date, taxable, cgst, sgst, igst):
            self.id = id_val
            self.supplier_gstin = gstin
            self.invoice_number = inv_num
            self.invoice_date = inv_date
            self.taxable_value = Decimal(str(taxable))
            self.cgst_amount = Decimal(str(cgst))
            self.sgst_amount = Decimal(str(sgst))
            self.igst_amount = Decimal(str(igst))
            self.cess_amount = Decimal("0.00")

    class Mock2B:
        def __init__(self, id_val, gstin, inv_num, inv_date, taxable, cgst, sgst, igst):
            self.id = id_val
            self.supplier_gstin = gstin
            self.invoice_number = inv_num
            self.invoice_date = inv_date
            self.taxable_value = Decimal(str(taxable))
            self.cgst_amount = Decimal(str(cgst))
            self.sgst_amount = Decimal(str(sgst))
            self.igst_amount = Decimal(str(igst))
            self.cess_amount = Decimal("0.00")

    d0 = date(2024, 4, 15)

    # 1. Exact match candidate (same GSTIN, normalized inv num, same amounts)
    b1 = MockBooks(
        "b1",
        "27AAPFU0939F1ZV",
        "INV/2024/001",
        d0,
        "10000.00",
        "900.00",
        "900.00",
        "0.00",
    )
    r1 = Mock2B(
        "r1",
        "27AAPFU0939F1ZV",
        "INV-2024-001",
        d0,
        "10000.00",
        "900.00",
        "900.00",
        "0.00",
    )

    # 2. Books only (supplier hasn't filed)
    b2 = MockBooks(
        "b2",
        "27AAPFU0939F1ZV",
        "INV/2024/002",
        d0,
        "5000.00",
        "450.00",
        "450.00",
        "0.00",
    )

    # 3. Return only (not recorded in books yet)
    r3 = Mock2B(
        "r3", "29AABCU9603R1ZM", "KA-999", d0, "20000.00", "0.00", "0.00", "3600.00"
    )

    matches = reconcile_purchases_with_gstr2b(
        books_invoices=[b1, b2],
        gstr2b_records=[r1, r3],
    )

    status_map = {
        m.purchase_invoice_id or m.gstr2b_record_id: m.match_status for m in matches
    }
    assert status_map["b1"] == MatchStatus.EXACT_MATCH
    assert status_map["b2"] == MatchStatus.BOOKS_ONLY
    assert status_map["r3"] == MatchStatus.RETURN_ONLY


# ============================================================================
# Integration Tests: Endpoints, Scoping, Locking, and Audit Events
# ============================================================================


@pytest.fixture
def auth_client():
    from app.modules.gst.models import sync_gst_table_columns

    sync_gst_table_columns(engine)
    client = TestClient(app)
    db = SessionLocal()
    try:
        # Create test user
        user = db.query(User).filter(User.email == "gst_tester@litebooks.ai").first()
        if not user:
            user = User(
                email="gst_tester@litebooks.ai",
                full_name="GST Test Accountant",
                hashed_password=hash_password("Password123!"),
                role="accountant",
                is_active=True,
                is_superuser=False,
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        token = create_access_token({"sub": user.email, "id": user.id})
        headers = {"Authorization": f"Bearer {token}"}
        return client, headers, user.id
    finally:
        db.close()


def test_gst_workflow_integration(auth_client):
    client, headers, user_id = auth_client

    # 1. Create GST Registration with dedicated GSTIN
    gstin_val = "27AABCT8888Q1ZV"
    reg_payload = {
        "gstin": gstin_val,
        "legal_name": "Acme Industrial Tech Ltd",
        "trade_name": "Acme Tech",
        "state_code": "27",
        "registration_type": "REGULAR",
        "authorized_signatory": "Rajesh Kumar",
        "is_active": True,
    }
    res = client.post("/api/gst/registrations", json=reg_payload, headers=headers)
    assert res.status_code in (201, 400)
    if res.status_code == 201:
        reg_id = res.json()["id"]
    else:
        list_res = client.get("/api/gst/registrations", headers=headers)
        reg_id = next(r["id"] for r in list_res.json() if r["gstin"] == gstin_val)

    # 2. Create Filing Period
    period_payload = {
        "registration_id": reg_id,
        "period": "2024-05",
        "financial_year": "2024-25",
    }
    p_res = client.post("/api/gst/periods", json=period_payload, headers=headers)
    if p_res.status_code == 201:
        period_id = p_res.json()["id"]
    else:
        list_p = client.get(f"/api/gst/registrations/{reg_id}/periods", headers=headers)
        period_id = next(p["id"] for p in list_p.json() if p["period"] == "2024-05")

    # 3. Add Sales Invoice (GSTR-1) with auto-tax calculation
    sale_payload = {
        "period_id": period_id,
        "invoice_number": "INV-WF-001",
        "invoice_date": "2024-05-10",
        "customer_gstin": "27AAPFU0939F1ZV",
        "customer_name": "Pune Systems Pvt Ltd",
        "place_of_supply": "27",
        "invoice_type": "B2B",
        "taxable_value": "50000.00",
        "tax_rate": "18.00",
        "cgst_amount": "0.00",
        "sgst_amount": "0.00",
        "igst_amount": "0.00",
        "cess_amount": "0.00",
        "total_amount": "0.00",
        "auto_calculate_tax": True,
    }
    s_res = client.post(
        f"/api/gst/periods/{period_id}/sales", json=sale_payload, headers=headers
    )
    assert s_res.status_code in (201, 400)
    if s_res.status_code == 201:
        sale_data = s_res.json()
        assert float(sale_data["cgst_amount"]) == 4500.0
        assert float(sale_data["sgst_amount"]) == 4500.0
        assert float(sale_data["total_amount"]) == 59000.0

    # 4. Add Purchase Invoice
    purch_payload = {
        "period_id": period_id,
        "invoice_number": "BILL-WF-88",
        "invoice_date": "2024-05-12",
        "supplier_gstin": "29AABCU9603R1ZM",
        "supplier_name": "Bangalore Cloud Services",
        "place_of_supply": "27",
        "taxable_value": "30000.00",
        "tax_rate": "18.00",
        "cgst_amount": "0.00",
        "sgst_amount": "0.00",
        "igst_amount": "0.00",
        "cess_amount": "0.00",
        "total_amount": "0.00",
        "itc_eligibility": "INPUT_SERVICES",
        "itc_category": "ALL_OTHER_ITC",
        "auto_calculate_tax": True,
    }
    pur_res = client.post(
        f"/api/gst/periods/{period_id}/purchases", json=purch_payload, headers=headers
    )
    assert pur_res.status_code in (201, 400)

    # 5. GSTR-1 & GSTR-3B Recalculations
    r1_res = client.post(
        f"/api/gst/periods/{period_id}/gstr1/recalculate", headers=headers
    )
    assert r1_res.status_code == 200

    r3_res = client.post(
        f"/api/gst/periods/{period_id}/gstr3b/recalculate", headers=headers
    )
    assert r3_res.status_code == 200

    # 6. GSTR-2B Import & Reconciliation Run
    import_payload = {
        "period_id": period_id,
        "records": [
            {
                "period_id": period_id,
                "supplier_gstin": "29AABCU9603R1ZM",
                "supplier_name": "Bangalore Cloud Services",
                "invoice_number": "BILL-WF-88",
                "invoice_type": "B2B",
                "invoice_date": "2024-05-12",
                "taxable_value": "30000.00",
                "tax_rate": "18.00",
                "cgst_amount": "0.00",
                "sgst_amount": "0.00",
                "igst_amount": "5400.00",
                "cess_amount": "0.00",
                "total_amount": "35400.00",
                "place_of_supply": "27",
                "reverse_charge": False,
                "itc_available": "YES",
                "supplier_filing_status": "FILED",
            }
        ],
    }
    imp_res = client.post(
        f"/api/gst/periods/{period_id}/gstr2b/import",
        json=import_payload,
        headers=headers,
    )
    assert imp_res.status_code == 200

    recon_res = client.post(
        f"/api/gst/periods/{period_id}/reconciliation/run", json={}, headers=headers
    )
    assert recon_res.status_code == 200

    summary_res = client.get(
        f"/api/gst/periods/{period_id}/reconciliation/summary", headers=headers
    )
    assert summary_res.status_code == 200

    # 7. Workflow Transition: draft -> under_review
    trans_res = client.post(
        f"/api/gst/periods/{period_id}/transition",
        json={"new_status": "under_review", "reason": "Ready for senior auditor check"},
        headers=headers,
    )
    assert trans_res.status_code == 200
    assert trans_res.json()["status"] == "under_review"

    # 8. Check audit records were generated
    db = SessionLocal()
    try:
        audit_records = (
            db.query(HistoryRecord).filter(HistoryRecord.module == "gst").all()
        )
        assert len(audit_records) > 0
    finally:
        db.close()


def test_gst_locking_enforcement(auth_client):
    client, headers, user_id = auth_client

    # 1. Create a dedicated period to lock
    reg_res = client.get("/api/gst/registrations", headers=headers)
    reg_id = reg_res.json()[0]["id"]

    period_payload = {
        "registration_id": reg_id,
        "period": "2024-07",
        "financial_year": "2024-25",
    }
    p_res = client.post("/api/gst/periods", json=period_payload, headers=headers)
    assert p_res.status_code in (201, 400)
    if p_res.status_code == 201:
        period_id = p_res.json()["id"]
    else:
        list_p = client.get(f"/api/gst/registrations/{reg_id}/periods", headers=headers)
        period_id = next(p["id"] for p in list_p.json() if p["period"] == "2024-07")

    # Workflow: draft -> under_review -> approved -> filed -> locked
    t1 = client.post(
        f"/api/gst/periods/{period_id}/transition",
        json={"new_status": "under_review"},
        headers=headers,
    )
    assert t1.status_code in (200, 400)

    t2 = client.post(
        f"/api/gst/periods/{period_id}/transition",
        json={"new_status": "approved"},
        headers=headers,
    )
    assert t2.status_code in (200, 400)

    t3 = client.post(
        f"/api/gst/periods/{period_id}/transition",
        json={"new_status": "filed", "arn": "AA2705240019284"},
        headers=headers,
    )
    assert t3.status_code in (200, 400)

    t4 = client.post(
        f"/api/gst/periods/{period_id}/transition",
        json={"new_status": "locked"},
        headers=headers,
    )
    assert t4.status_code in (200, 400)

    # Attempt to add a sales invoice to locked period -> MUST BE REJECTED with 400
    sale_payload = {
        "period_id": period_id,
        "invoice_number": "INV-LOCKED-001",
        "invoice_date": "2024-07-15",
        "customer_name": "Late Buyer",
        "place_of_supply": "27",
        "invoice_type": "B2CS",
        "taxable_value": "1000.00",
        "tax_rate": "18.00",
        "cgst_amount": "90.00",
        "sgst_amount": "90.00",
        "igst_amount": "0.00",
        "cess_amount": "0.00",
        "total_amount": "1180.00",
        "auto_calculate_tax": False,
    }
    blocked_res = client.post(
        f"/api/gst/periods/{period_id}/sales", json=sale_payload, headers=headers
    )
    assert blocked_res.status_code == 400
    assert (
        "cannot be modified" in blocked_res.json()["detail"].lower()
        or "locked" in blocked_res.json()["detail"].lower()
    )


def test_gst_company_isolation():
    from app.core.auth import get_current_user

    client = TestClient(app)
    db = SessionLocal()
    old_override = app.dependency_overrides.pop(get_current_user, None)
    try:
        # User A
        user_a = db.query(User).filter(User.email == "user_a@litebooks.ai").first()
        if not user_a:
            user_a = User(
                email="user_a@litebooks.ai",
                full_name="User Alpha",
                hashed_password=hash_password("Pass123!"),
                role="accountant",
                is_active=True,
                is_superuser=False,
            )
            db.add(user_a)
            db.commit()
            db.refresh(user_a)

        # User B
        user_b = db.query(User).filter(User.email == "user_b@litebooks.ai").first()
        if not user_b:
            user_b = User(
                email="user_b@litebooks.ai",
                full_name="User Beta",
                hashed_password=hash_password("Pass123!"),
                role="accountant",
                is_active=True,
                is_superuser=False,
            )
            db.add(user_b)
            db.commit()
            db.refresh(user_b)

        user_a.is_superuser = False
        user_b.is_superuser = False
        user_a.organization_id = "org_alpha"
        user_b.organization_id = "org_beta"
        db.commit()

        headers_a = {
            "Authorization": f"Bearer {create_access_token({'sub': user_a.email, 'id': user_a.id})}"
        }
        headers_b = {
            "Authorization": f"Bearer {create_access_token({'sub': user_b.email, 'id': user_b.id})}"
        }

        # User A creates a registration
        gstin_a = "29AABCS6666B1ZB"
        # Ensure it belongs to User A
        existing_reg = (
            db.query(GSTRegistration).filter(GSTRegistration.gstin == gstin_a).first()
        )
        if existing_reg:
            existing_reg.user_id = user_a.id
            existing_reg.organization_id = user_a.organization_id
            db.commit()
            reg_id = existing_reg.id
        else:
            reg_payload = {
                "gstin": gstin_a,
                "legal_name": "Alpha Tech Bangalore",
                "state_code": "29",
                "registration_type": "REGULAR",
            }
            res_a = client.post(
                "/api/gst/registrations", json=reg_payload, headers=headers_a
            )
            assert res_a.status_code in (201, 400)
            if res_a.status_code == 201:
                reg_id = res_a.json()["id"]
            else:
                list_res = client.get("/api/gst/registrations", headers=headers_a)
                reg_id = next(r["id"] for r in list_res.json() if r["gstin"] == gstin_a)

        # User B tries to view User A's registration -> MUST RETURN 404 (Not Found or Access Denied)
        res_b = client.get(f"/api/gst/registrations/{reg_id}", headers=headers_b)
        assert res_b.status_code == 404
        assert (
            "not found" in res_b.json()["detail"].lower()
            or "access denied" in res_b.json()["detail"].lower()
        )
    finally:
        if old_override:
            app.dependency_overrides[get_current_user] = old_override
        db.close()
