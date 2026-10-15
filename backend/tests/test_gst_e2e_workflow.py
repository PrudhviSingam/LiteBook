import io
import json
import random
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import SessionLocal
from app.models.history import HistoryRecord


client = TestClient(app)


def test_gst_e2e_full_lifecycle(default_test_user):
    """
    End-to-end statutory GST lifecycle test:
    1. Create GST Registration & Filing Period
    2. File upload & import (Sales invoices via multipart/form-data upload)
    3. GSTR-1 calculation & verification (taxable value, IGST, CGST, SGST)
    4. Purchases & GSTR-2B import via statutory APIs
    5. GSTR-2B matching engine execution & discrepancy detection
    6. GSTR-3B calculation with statutory set-off
    7. Review Center integration (verify GST discrepancies appear in Review Center findings)
    8. Review Center decision execution (accept finding & verify audit history)
    9. Export reports (GSTR-1, GSTR-3B, Reconciliation CSV downloads)
    10. Period locking & write protection verification
    """
    # 1. Create GST Registration with valid 15-char Indian GSTIN
    digits = random.randint(1000, 9999)
    gstin = f"27AAAAA{digits}A1Z5"

    reg_res = client.post(
        "/api/gst/registrations",
        json={
            "gstin": gstin,
            "legal_name": "LiteBooks Enterprise India Pvt Ltd",
            "trade_name": "LiteBooks Solutions",
            "state_code": "27",
            "state_name": "Maharashtra",
            "registration_type": "REGULAR",
        },
    )
    assert reg_res.status_code in [200, 201], reg_res.text
    reg_id = reg_res.json()["id"]

    # Create Filing Period
    period_res = client.post(
        "/api/gst/periods",
        json={
            "registration_id": reg_id,
            "period": "2024-05",
            "financial_year": "2024-25",
        },
    )
    assert period_res.status_code in [200, 201], period_res.text
    period_id = period_res.json()["id"]

    # 2. Upload Sales File (JSON format)
    sales_data = [
        {
            "invoice_number": "INV-E2E-001",
            "invoice_date": "2024-05-10",
            "customer_gstin": "27ABCDE1234F1Z5",
            "customer_name": "Acme Mumbai Corp",
            "place_of_supply": "27",
            "invoice_type": "B2B",
            "taxable_value": 100000.0,
            "cgst_amount": 9000.0,
            "sgst_amount": 9000.0,
            "igst_amount": 0.0,
            "total_amount": 118000.0,
        },
        {
            "invoice_number": "INV-E2E-002",
            "invoice_date": "2024-05-15",
            "customer_gstin": "29XYZAB5678C1Z2",
            "customer_name": "Bangalore Tech Hub",
            "place_of_supply": "29",
            "invoice_type": "B2B",
            "taxable_value": 50000.0,
            "cgst_amount": 0.0,
            "sgst_amount": 0.0,
            "igst_amount": 9000.0,
            "total_amount": 59000.0,
        },
    ]

    sales_file_bytes = io.BytesIO(json.dumps(sales_data).encode("utf-8"))
    upload_res = client.post(
        f"/api/gst/periods/{period_id}/upload",
        files={"file": ("sales_may2024.json", sales_file_bytes, "application/json")},
        data={"file_type": "sales"},
    )
    assert upload_res.status_code == 200, upload_res.text
    upload_json = upload_res.json()
    assert upload_json["success"] is True
    assert upload_json["imported_count"] == 2

    # 3. Verify GSTR-1 calculation
    gstr1_res = client.get(f"/api/gst/periods/{period_id}/gstr1/summary?recalculate=true")
    assert gstr1_res.status_code == 200, gstr1_res.text
    g1 = gstr1_res.json()
    assert float(g1["total_taxable_value"]) == 150000.0
    assert float(g1["total_cgst"]) + float(g1["total_sgst"]) + float(g1["total_igst"]) == 27000.0
    assert float(g1["total_invoice_value"]) == 177000.0
    assert g1["total_invoices_count"] == 2
    assert g1["is_stale"] is False

    # 4. Upload Books Purchases and GSTR-2B records for reconciliation
    # Purchase 1 (Exact match with GSTR-2B)
    pur1_res = client.post(
        f"/api/gst/periods/{period_id}/purchases",
        json={
            "supplier_gstin": "27AAAAA1111A1Z5",
            "supplier_name": "Alpha Cloud Services",
            "invoice_number": "SUP-001",
            "invoice_date": "2024-05-12",
            "invoice_type": "B2B",
            "place_of_supply": "27",
            "taxable_value": "40000.00",
            "tax_rate": "18.00",
            "cgst_amount": "3600.00",
            "sgst_amount": "3600.00",
            "igst_amount": "0.00",
            "total_amount": "47200.00",
            "itc_eligibility": "ELIGIBLE",
        },
    )
    assert pur1_res.status_code in [200, 201], pur1_res.text

    # Purchase 2 (Will have a value mismatch with GSTR-2B)
    pur2_res = client.post(
        f"/api/gst/periods/{period_id}/purchases",
        json={
            "supplier_gstin": "27BBBBB2222B1Z5",
            "supplier_name": "Beta Logistics",
            "invoice_number": "SUP-002",
            "invoice_date": "2024-05-14",
            "invoice_type": "B2B",
            "place_of_supply": "27",
            "taxable_value": "20000.00",
            "tax_rate": "18.00",
            "cgst_amount": "1800.00",
            "sgst_amount": "1800.00",
            "igst_amount": "0.00",
            "total_amount": "23600.00",
            "itc_eligibility": "ELIGIBLE",
        },
    )
    assert pur2_res.status_code in [200, 201], pur2_res.text

    # Import GSTR-2B Records via portal statement import
    g2b_import = client.post(
        f"/api/gst/periods/{period_id}/gstr2b/import",
        json={
            "period_id": period_id,
            "records": [
                {
                    "period_id": period_id,
                    "supplier_gstin": "27AAAAA1111A1Z5",
                    "supplier_name": "Alpha Cloud Services",
                    "invoice_number": "SUP-001",
                    "invoice_date": "2024-05-12",
                    "invoice_type": "B2B",
                    "place_of_supply": "27",
                    "taxable_value": "40000.00",
                    "tax_rate": "18.00",
                    "cgst_amount": "3600.00",
                    "sgst_amount": "3600.00",
                    "igst_amount": "0.00",
                    "total_amount": "47200.00",
                    "itc_available": "YES",
                    "supplier_filing_status": "FILED",
                },
                {
                    "period_id": period_id,
                    "supplier_gstin": "27BBBBB2222B1Z5",
                    "supplier_name": "Beta Logistics",
                    "invoice_number": "SUP-002",
                    "invoice_date": "2024-05-14",
                    "invoice_type": "B2B",
                    "place_of_supply": "27",
                    "taxable_value": "15000.00",  # Variance of 5000 from books
                    "tax_rate": "18.00",
                    "cgst_amount": "1350.00",
                    "sgst_amount": "1350.00",
                    "igst_amount": "0.00",
                    "total_amount": "17700.00",
                    "itc_available": "YES",
                    "supplier_filing_status": "FILED",
                },
            ],
        },
    )
    assert g2b_import.status_code == 200, g2b_import.text

    # 5. Run Reconciliation Engine
    recon_res = client.post(f"/api/gst/periods/{period_id}/reconcile?amount_tolerance=1.0")
    assert recon_res.status_code == 200, recon_res.text
    results_list = recon_res.json()
    assert isinstance(results_list, list)
    assert len(results_list) >= 2

    # Fetch summary
    recon_sum_res = client.get(f"/api/gst/periods/{period_id}/reconciliation/summary")
    assert recon_sum_res.status_code == 200, recon_sum_res.text
    recon_summary = recon_sum_res.json()
    assert recon_summary["exact_matches"] >= 1
    assert recon_summary["partial_matches"] >= 1

    # 6. Verify GSTR-3B Calculation & Set-off
    gstr3b_res = client.get(f"/api/gst/periods/{period_id}/gstr3b/summary?recalculate=true")
    assert gstr3b_res.status_code == 200, gstr3b_res.text
    g3b = gstr3b_res.json()
    assert float(g3b["outward_taxable_value"]) == 150000.0
    assert float(g3b["outward_cgst"]) + float(g3b["outward_sgst"]) + float(g3b["outward_igst"]) == 27000.0
    assert "set_off_details" in g3b

    # 7. Verify Review Center integration
    findings_res = client.get("/api/v1/review-center/findings")
    assert findings_res.status_code == 200, findings_res.text
    findings_data = findings_res.json()
    findings_list = findings_data.get("findings", findings_data) if isinstance(findings_data, dict) else findings_data
    gst_findings = [f for f in findings_list if f.get("category") == "gst" or "GST" in str(f.get("type", ""))]
    assert len(gst_findings) >= 1
    target_finding = gst_findings[0]
    assert target_finding["severity"] in ["MEDIUM", "HIGH", "CRITICAL"]
    assert "SUP-002" in str(target_finding.get("document_name", "")) or "Beta Logistics" in str(target_finding.get("title", "")) or "SUP-002" in str(target_finding.get("cell_address", ""))
    assert "2024-05" in str(target_finding.get("financial_period", ""))
    assert target_finding["status"] in ["REVIEW_REQUIRED", "PENDING", "NEEDS_REVIEW"]
    assert len(target_finding.get("possible_causes", [])) > 0

    # 8. Accountant Decision via Review Center
    finding_id = target_finding["id"]
    decision_res = client.post(
        f"/api/v1/review-center/findings/{finding_id}/decision",
        json={"decision": "ACCEPTED", "notes": "Accountant verified timing difference with supplier."},
    )
    assert decision_res.status_code == 200, decision_res.text
    decision_json = decision_res.json()
    assert decision_json["status"] in ["APPROVED", "ACCEPTED"]

    # Verify audit activity recorded in HistoryRecord
    db = SessionLocal()
    hist_entries = db.query(HistoryRecord).filter(HistoryRecord.module.in_(["gst", "review_center"])).all()
    assert len(hist_entries) > 0
    db.close()

    # 9. Verify Statutory Export endpoints
    export_g1 = client.get(f"/api/gst/periods/{period_id}/export/gstr1?format=csv")
    assert export_g1.status_code == 200
    assert "GSTR-1 Statutory Outward Supplies Summary" in export_g1.text
    assert "150000" in export_g1.text

    export_g3b = client.get(f"/api/gst/periods/{period_id}/export/gstr3b?format=csv")
    assert export_g3b.status_code == 200
    assert "GSTR-3B Statutory Computation Report" in export_g3b.text

    export_recon = client.get(f"/api/gst/periods/{period_id}/export/reconciliation?format=csv")
    assert export_recon.status_code == 200
    assert "GSTR-2B vs Books ITC Reconciliation Report" in export_recon.text
    assert "Alpha Cloud Services" in export_recon.text

    # 10. Period Locking and Write Protection
    # Transition to under_review -> approved -> filed -> locked
    t1 = client.post(f"/api/gst/periods/{period_id}/transition", json={"new_status": "under_review"})
    assert t1.status_code == 200
    t2 = client.post(f"/api/gst/periods/{period_id}/transition", json={"new_status": "approved"})
    assert t2.status_code == 200
    t3 = client.post(f"/api/gst/periods/{period_id}/transition", json={"new_status": "filed", "arn": "AA2705240001234"})
    assert t3.status_code == 200
    t4 = client.post(f"/api/gst/periods/{period_id}/transition", json={"new_status": "locked"})
    assert t4.status_code == 200
    assert t4.json()["status"] == "locked"

    # Verify write protection: Attempting to upload new data to locked period must be rejected with 400
    dummy_file = io.BytesIO(json.dumps([{"invoice_number": "INV-FAIL"}]).encode("utf-8"))
    locked_upload_res = client.post(
        f"/api/gst/periods/{period_id}/upload",
        files={"file": ("fail.json", dummy_file, "application/json")},
        data={"file_type": "sales"},
    )
    assert locked_upload_res.status_code == 400
    assert "locked" in locked_upload_res.text.lower() or "read-only" in locked_upload_res.text.lower()
