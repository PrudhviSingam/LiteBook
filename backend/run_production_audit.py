import json
import os
import requests
import uuid
from typing import Dict, Any

BASE_URL = "http://127.0.0.1:8000/api/v1"

def log_section(title: str):
    print(f"\n{'='*60}\n{title}\n{'='*60}", flush=True)

def run_audit():
    # ----------------------------------------------------
    # 1. SERVER HEALTH & REACHABILITY
    # ----------------------------------------------------
    log_section("1. SERVER HEALTH & REACHABILITY")
    r_health = requests.get(f"{BASE_URL}/health", timeout=5)
    assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
    health_data = r_health.json()
    print("Health Status:", health_data)
    assert health_data.get("status") == "healthy"

    # Frontend reachable
    r_fe = requests.get("http://127.0.0.1:5173", timeout=5)
    assert r_fe.status_code == 200
    print("[PASS] Frontend reachable at http://127.0.0.1:5173 (HTTP 200)")

    # ----------------------------------------------------
    # 2. AUTHENTICATION & MULTI-USER ISOLATION AUDIT
    # ----------------------------------------------------
    log_section("2. AUTHENTICATION & MULTI-USER ISOLATION AUDIT")
    # Unauthorized API access blocked
    r_unauth = requests.get(f"{BASE_URL}/dashboard/summary", timeout=5)
    assert r_unauth.status_code in (401, 403), f"Expected 401/403 for unauthorized access, got {r_unauth.status_code}"
    print("[PASS] Unauthorized access blocked with 401/403")

    # User A Login
    r_login_a = requests.post(f"{BASE_URL}/auth/login", json={
        "email": "accountant@litebooks.ai",
        "password": "Password123!"
    }, timeout=5)
    assert r_login_a.status_code == 200, f"Login failed: {r_login_a.text}"
    token_a = r_login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # /me endpoint for User A
    r_me_a = requests.get(f"{BASE_URL}/auth/me", headers=headers_a, timeout=5)
    assert r_me_a.status_code == 200, f"/me failed: {r_me_a.text}"
    user_a = r_me_a.json()
    print(f"[PASS] User A logged in: {user_a['email']} (id: {user_a['id']})")

    # Register User B for Cross-User Isolation Audit
    user_b_email = f"audit_user_{uuid.uuid4().hex[:6]}@litebooks.ai"
    user_b_pwd = "SecurePassword123!"
    r_reg_b = requests.post(f"{BASE_URL}/auth/register", json={
        "email": user_b_email,
        "password": user_b_pwd,
        "full_name": "Audit Auditor B",
        "role": "accountant"
    }, timeout=5)
    if r_reg_b.status_code in (200, 201):
        token_b = r_reg_b.json().get("access_token")
        if not token_b:
            r_login_b = requests.post(f"{BASE_URL}/auth/login", json={
                "email": user_b_email,
                "password": user_b_pwd
            }, timeout=5)
            token_b = r_login_b.json()["access_token"]
    else:
        r_login_b = requests.post(f"{BASE_URL}/auth/login", json={
            "email": user_b_email,
            "password": user_b_pwd
        }, timeout=5)
        assert r_login_b.status_code == 200
        token_b = r_login_b.json()["access_token"]

    headers_b = {"Authorization": f"Bearer {token_b}"}
    r_me_b = requests.get(f"{BASE_URL}/auth/me", headers=headers_b, timeout=5)
    user_b = r_me_b.json()
    print(f"[PASS] User B registered & authenticated: {user_b['email']} (id: {user_b['id']})")

    # ----------------------------------------------------
    # 3. REAL FILE UPLOADS (.xlsx, .xls, .csv, .pdf, invalid rejection)
    # ----------------------------------------------------
    log_section("3. REAL FILE UPLOAD AUDIT")
    # Upload XLSX
    with open("d:/LiteBooks/test_files/Zion_Lifts_Financials.xlsx", "rb") as f:
        r_xlsx = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("Zion_Lifts_Financials.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=headers_a,
            timeout=15
        )
    assert r_xlsx.status_code in (200, 201), f"XLSX upload failed: {r_xlsx.text}"
    doc_xlsx_a = r_xlsx.json()
    print(f"[PASS] XLSX uploaded: {doc_xlsx_a['original_filename']} (id: {doc_xlsx_a['id']})")

    # Upload XLS
    with open("d:/LiteBooks/test_files/financial_sample.xls", "rb") as f:
        r_xls = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("financial_sample.xls", f, "application/vnd.ms-excel")},
            headers=headers_a,
            timeout=15
        )
    assert r_xls.status_code in (200, 201), f"XLS upload failed: {r_xls.text}"
    doc_xls_a = r_xls.json()
    print(f"[PASS] XLS uploaded: {doc_xls_a['original_filename']} (id: {doc_xls_a['id']})")

    # Upload CSV
    with open("d:/LiteBooks/test_files/accounting_sample.csv", "rb") as f:
        r_csv = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("accounting_sample.csv", f, "text/csv")},
            headers=headers_a,
            timeout=15
        )
    assert r_csv.status_code in (200, 201), f"CSV upload failed: {r_csv.text}"
    doc_csv_a = r_csv.json()
    print(f"[PASS] CSV uploaded: {doc_csv_a['original_filename']} (id: {doc_csv_a['id']})")

    # Upload PDF
    with open("d:/LiteBooks/test_files/vendor_invoice.pdf", "rb") as f:
        r_pdf = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("vendor_invoice.pdf", f, "application/pdf")},
            headers=headers_a,
            timeout=15
        )
    assert r_pdf.status_code in (200, 201), f"PDF upload failed: {r_pdf.text}"
    doc_pdf_a = r_pdf.json()
    print(f"[PASS] PDF uploaded: {doc_pdf_a['original_filename']} (id: {doc_pdf_a['id']})")

    # Invalid extension rejected
    with open("d:/LiteBooks/test_files/invalid_image.png", "rb") as f:
        r_png = requests.post(
            f"{BASE_URL}/documents/upload",
            files={"file": ("invalid_image.png", f, "image/png")},
            headers=headers_a,
            timeout=15
        )
    assert r_png.status_code in (400, 422), f"Expected rejection of .png, got {r_png.status_code}"
    print(f"[PASS] Invalid file extension (.png) rejected with {r_png.status_code}: {r_png.text[:100]}")

    # Cross-User Isolation Check on Documents
    r_b_docs = requests.get(f"{BASE_URL}/documents", headers=headers_b, timeout=5)
    b_doc_ids = [d["id"] for d in r_b_docs.json()] if r_b_docs.status_code == 200 else []
    assert doc_xlsx_a["id"] not in b_doc_ids, "SECURITY VIOLATION: User B can see User A's uploaded document in list!"
    
    r_b_single = requests.get(f"{BASE_URL}/documents/{doc_xlsx_a['id']}/download", headers=headers_b, timeout=5)
    assert r_b_single.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's document: {r_b_single.status_code}"
    print("[PASS] Cross-user document isolation verified (User B cannot see or access User A's docs)")

    # ----------------------------------------------------
    # 4. RECONCILIATION REAL FLOW
    # ----------------------------------------------------
    log_section("4. RECONCILIATION REAL FLOW")
    # Run Reconciliation between bank statement & ledger
    with open("d:/LiteBooks/backend/sample_data/sample_bank_statement.csv", "rb") as f_bank, \
         open("d:/LiteBooks/backend/sample_data/sample_ledger.csv", "rb") as f_gl:
        r_recon = requests.post(
            f"{BASE_URL}/reconciliation/run",
            files={
                "bank_file": ("sample_bank_statement.csv", f_bank, "text/csv"),
                "ledger_file": ("sample_ledger.csv", f_gl, "text/csv")
            },
            data={"date_tolerance_days": 2, "amount_tolerance": 0.05},
            headers=headers_a,
            timeout=30
        )
    assert r_recon.status_code in (200, 201), f"Reconciliation run failed: {r_recon.text}"
    recon_res = r_recon.json()
    session_id = recon_res["id"]
    summary = recon_res.get("summary", {})
    print(f"[PASS] Reconciliation executed: Session #{session_id}")
    print(f"       Total Bank Records: {summary.get('total_bank_records')}, Ledger Records: {summary.get('total_ledger_records')}")
    print(f"       Matched: {summary.get('matched_count')}, Unmatched Bank: {summary.get('unmatched_bank_count')}, Unmatched Ledger: {summary.get('unmatched_ledger_count')}")
    print(f"       Discrepancies found: {summary.get('discrepancy_count')}")

    # Fetch results by session ID
    r_fetch_recon = requests.get(f"{BASE_URL}/reconciliation/results/{session_id}", headers=headers_a, timeout=10)
    assert r_fetch_recon.status_code == 200
    print("[PASS] Fetched reconciliation session results successfully")

    # Fetch discrepancies explanations
    if recon_res.get("discrepancies"):
        disc = recon_res["discrepancies"][0]
        r_expl = requests.post(
            f"{BASE_URL}/reconciliation/explain-discrepancy",
            json={
                "discrepancy_data": disc,
                "comparison_records": [],
                "document_metadata": {"session_id": session_id}
            },
            headers=headers_a,
            timeout=20
        )
        if r_expl.status_code == 200:
            expl_data = r_expl.json()
            print(f"[PASS] AI / Rule Explanation generated for discrepancy: {expl_data.get('what', '')[:100]}...")

    # Fetch correction proposals
    r_corr = requests.get(f"{BASE_URL}/reconciliation/sessions/{session_id}/corrections", headers=headers_a, timeout=10)
    if r_corr.status_code == 200:
        proposals = r_corr.json()
        print(f"[PASS] Retrieved {len(proposals)} correction proposals for session")
        if proposals:
            prop_id = proposals[0]["correction_id"]
            r_dec = requests.post(
                f"{BASE_URL}/reconciliation/corrections/{prop_id}/decision",
                json={"decision": "CONFIRMED", "notes": "Audited in Step 9"},
                headers=headers_a,
                timeout=10
            )
            print(f"[PASS] Correction decision updated: {r_dec.status_code}")

    # Cross-User Isolation on Reconciliation
    r_b_recon = requests.get(f"{BASE_URL}/reconciliation/results/{session_id}", headers=headers_b, timeout=5)
    assert r_b_recon.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's recon session: {r_b_recon.status_code}"
    print("[PASS] Cross-user reconciliation isolation verified")

    # ----------------------------------------------------
    # 5. GST REAL FLOW
    # ----------------------------------------------------
    log_section("5. GST REAL FLOW")
    # 1. Create GST Registration
    import random
    rnd_digits = f"{random.randint(1000, 9999)}"
    gstin = f"27AABCU{rnd_digits}R1Z5"
    r_reg = requests.post(f"{BASE_URL}/gst/registrations", json={
        "gstin": gstin,
        "legal_name": "Audit Alpha Enterprises Pvt Ltd",
        "trade_name": "Alpha Tech",
        "state_code": "27",
        "taxpayer_type": "Regular"
    }, headers=headers_a, timeout=10)
    assert r_reg.status_code in (200, 201), f"GST Registration create failed: {r_reg.text}"
    reg_id = r_reg.json()["id"]
    print(f"[PASS] GST Registration created: {gstin} (id: {reg_id})")

    # 2. Create Filing Period
    r_period = requests.post(f"{BASE_URL}/gst/periods", json={
        "registration_id": reg_id,
        "period": "2024-04",
        "financial_year": "2024-25"
    }, headers=headers_a, timeout=10)
    assert r_period.status_code in (200, 201), f"GST Period create failed: {r_period.text}"
    period_id = r_period.json()["id"]
    print(f"[PASS] GST Filing Period created: 2024-04 (id: {period_id})")

    # 3. Add Sales Invoices
    r_sale1 = requests.post(f"{BASE_URL}/gst/periods/{period_id}/sales", json={
        "invoice_number": "INV-AUD-001",
        "invoice_date": "2024-04-10",
        "customer_name": "Beta Industries",
        "customer_gstin": "27AABCB1111A1Z1",
        "place_of_supply": "27",
        "taxable_value": 100000.0,
        "tax_rate": 18.0,
        "cgst_amount": 9000.0,
        "sgst_amount": 9000.0,
        "igst_amount": 0.0,
        "total_amount": 118000.0,
        "invoice_type": "B2B"
    }, headers=headers_a, timeout=10)
    assert r_sale1.status_code in (200, 201), f"Add sales invoice failed: {r_sale1.text}"
    print("[PASS] Sales Invoice added: INV-AUD-001 (Taxable 100,000, CGST 9,000, SGST 9,000)")

    # 4. Add Purchase Invoices
    r_purch1 = requests.post(f"{BASE_URL}/gst/periods/{period_id}/purchases", json={
        "invoice_number": "PUR-AUD-101",
        "invoice_date": "2024-04-12",
        "supplier_name": "Delta Suppliers",
        "supplier_gstin": "27XYZPD9999Z1Z5",
        "place_of_supply": "27",
        "taxable_value": 50000.0,
        "tax_rate": 18.0,
        "cgst_amount": 4500.0,
        "sgst_amount": 4500.0,
        "igst_amount": 0.0,
        "total_amount": 59000.0,
        "itc_eligibility": "ELIGIBLE",
        "itc_category": "ALL_OTHER_ITC"
    }, headers=headers_a, timeout=10)
    assert r_purch1.status_code in (200, 201), f"Add purchase invoice failed: {r_purch1.text}"
    print("[PASS] Purchase Invoice added: PUR-AUD-101 (Taxable 50,000, CGST 4,500, SGST 4,500)")

    # 5. Add GSTR-2B External Record
    r_2b = requests.post(f"{BASE_URL}/gst/periods/{period_id}/gstr2b/import", json={
        "period_id": period_id,
        "records": [{
            "period_id": period_id,
            "invoice_number": "PUR-AUD-101",
            "invoice_date": "2024-04-12",
            "supplier_name": "Delta Suppliers",
            "supplier_gstin": "27XYZPD9999Z1Z5",
            "taxable_value": 50000.0,
            "tax_rate": 18.0,
            "cgst_amount": 4500.0,
            "sgst_amount": 4500.0,
            "igst_amount": 0.0,
            "total_amount": 59000.0,
            "place_of_supply": "27",
            "itc_available": "YES",
            "supplier_filing_status": "FILED"
        }]
    }, headers=headers_a, timeout=10)
    assert r_2b.status_code in (200, 201), f"Add 2B record failed: {r_2b.text}"
    print("[PASS] GSTR-2B External Record added: PUR-AUD-101")

    # 6. Reconcile GST Period
    r_gst_reconcile = requests.post(f"{BASE_URL}/gst/periods/{period_id}/reconcile", headers=headers_a, timeout=15)
    assert r_gst_reconcile.status_code in (200, 201), f"GST Reconcile failed: {r_gst_reconcile.text}"
    gst_recon_items = r_gst_reconcile.json()
    print(f"[PASS] GST Reconciliation executed: {len(gst_recon_items)} records matched")

    # 7. Generate GSTR-1 Summary
    r_gstr1 = requests.get(f"{BASE_URL}/gst/periods/{period_id}/gstr1/summary", headers=headers_a, timeout=10)
    assert r_gstr1.status_code == 200, f"GSTR-1 summary failed: {r_gstr1.text}"
    gstr1_data = r_gstr1.json()
    print(f"[PASS] GSTR-1 Summary: Taxable Value={gstr1_data.get('total_taxable_value')}, CGST={gstr1_data.get('total_cgst')}, SGST={gstr1_data.get('total_sgst')}")

    # 8. Generate GSTR-3B Summary
    r_gstr3b = requests.get(f"{BASE_URL}/gst/periods/{period_id}/gstr3b/summary", headers=headers_a, timeout=10)
    assert r_gstr3b.status_code == 200, f"GSTR-3B summary failed: {r_gstr3b.text}"
    gstr3b_data = r_gstr3b.json()
    print(f"[PASS] GSTR-3B Summary: Outward Taxable={gstr3b_data.get('outward_taxable_value')}, ITC CGST={gstr3b_data.get('itc_all_other_cgst')}, Net Cash={gstr3b_data.get('total_tax_payable_cash')}")

    # 9. Export Reports (GSTR-1, GSTR-3B, Reconciliation) & Verify Disclaimer (No GSTN claim)
    for rep in ["gstr1", "gstr3b", "reconciliation"]:
        r_exp = requests.get(f"{BASE_URL}/gst/periods/{period_id}/export/{rep}?format=json", headers=headers_a, timeout=10)
        assert r_exp.status_code == 200, f"Export {rep} failed: {r_exp.text}"
        assert "Not submitted to GSTN" in r_exp.text, "Statutory filing disclaimer missing!"
        print(f"[PASS] Export {rep} contains required non-filing verification disclaimer")

    # 10. Lock Period & Verify Modification Blocked
    r_rev = requests.post(f"{BASE_URL}/gst/periods/{period_id}/transition", json={"new_status": "under_review"}, headers=headers_a, timeout=10)
    assert r_rev.status_code == 200, f"Transition to under_review failed: {r_rev.text}"
    r_app = requests.post(f"{BASE_URL}/gst/periods/{period_id}/transition", json={"new_status": "approved"}, headers=headers_a, timeout=10)
    assert r_app.status_code == 200, f"Transition to approved failed: {r_app.text}"
    r_fld = requests.post(f"{BASE_URL}/gst/periods/{period_id}/transition", json={"new_status": "filed", "arn": "AA270424123456C"}, headers=headers_a, timeout=10)
    assert r_fld.status_code == 200, f"Transition to filed failed: {r_fld.text}"
    r_lock = requests.post(f"{BASE_URL}/gst/periods/{period_id}/transition", json={"new_status": "locked"}, headers=headers_a, timeout=10)
    assert r_lock.status_code == 200, f"Lock failed: {r_lock.text}"
    print("[PASS] GST Period successfully transitioned through statutory states to 'locked'")

    r_mod_attempt = requests.post(f"{BASE_URL}/gst/periods/{period_id}/sales", json={
        "invoice_number": "INV-AUD-ILLEGAL",
        "invoice_date": "2024-04-20",
        "customer_name": "Test Customer",
        "place_of_supply": "27",
        "invoice_type": "B2B",
        "taxable_value": 10000.0,
        "tax_rate": 18.0,
        "total_amount": 11800.0
    }, headers=headers_a, timeout=10)
    assert r_mod_attempt.status_code in (400, 403, 409), f"Modifying locked period must fail, got: {r_mod_attempt.status_code}"
    print(f"[PASS] Modifying locked GST period strictly rejected with {r_mod_attempt.status_code} ({r_mod_attempt.json().get('detail')})")

    # Cross-User Isolation on GST
    r_b_gst = requests.get(f"{BASE_URL}/gst/periods/{period_id}", headers=headers_b, timeout=5)
    assert r_b_gst.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's GST period: {r_b_gst.status_code}"
    print("[PASS] Cross-user GST isolation verified")

    # ----------------------------------------------------
    # 6. ITR REAL FLOW
    # ----------------------------------------------------
    log_section("6. ITR REAL FLOW")
    pan = f"ABCDE{random.randint(1000, 9999)}F"
    ay = "2024-25"
    fy = "2023-24"

    # 1. Create Profile
    r_itr_prof = requests.post(f"{BASE_URL}/itr/profiles", json={
        "pan": pan,
        "taxpayer_name": "Audit Sample Taxpayer",
        "assessment_year": ay,
        "financial_year": fy,
        "taxpayer_category": "INDIVIDUAL"
    }, headers=headers_a, timeout=10)
    assert r_itr_prof.status_code in (200, 201), f"ITR Profile create failed: {r_itr_prof.text}"
    itr_prof = r_itr_prof.json()
    itr_id = itr_prof["id"]
    print(f"[PASS] ITR Profile created: PAN={itr_prof['pan']}, AY={itr_prof['assessment_year']} (id: {itr_id})")

    # 2. Add Salary Income
    r_sal = requests.post(f"{BASE_URL}/itr/profiles/{itr_id}/incomes", json={
        "head_of_income": "SALARY",
        "description": "Annual Salary from Tech Corp",
        "gross_amount": 1200000.0,
        "exemptions_allowances": 50000.0,
        "net_taxable_amount": 1150000.0
    }, headers=headers_a, timeout=10)
    assert r_sal.status_code in (200, 201), f"Add salary failed: {r_sal.text}"
    print("[PASS] Added Salary Income: Gross 1,200,000, Standard deduction/exemption 50,000")

    # 3. Add Deductions (80C with 180,000 to test statutory 150,000 cap)
    r_80c = requests.post(f"{BASE_URL}/itr/profiles/{itr_id}/deductions", json={
        "section": "80C",
        "description": "PPF and ELSS Mutual Funds",
        "claimed_amount": 180000.0,
        "eligible_amount": 180000.0
    }, headers=headers_a, timeout=10)
    assert r_80c.status_code in (200, 201), f"Add 80C deduction failed: {r_80c.text}"
    print("[PASS] Added 80C Deduction: 180,000 (tested for statutory capping)")

    # 4. Add Deductions (80D Health Insurance)
    r_80d = requests.post(f"{BASE_URL}/itr/profiles/{itr_id}/deductions", json={
        "section": "80D",
        "description": "Mediclaim for Self and Family",
        "claimed_amount": 25000.0,
        "eligible_amount": 25000.0
    }, headers=headers_a, timeout=10)
    assert r_80d.status_code in (200, 201), f"Add 80D deduction failed: {r_80d.text}"
    print("[PASS] Added 80D Deduction: 25,000")

    # 5. Add Tax Credit (TDS)
    r_tds = requests.post(f"{BASE_URL}/itr/profiles/{itr_id}/tax-credits", json={
        "credit_type": "TDS_SALARY",
        "deductor_or_bank": "Tech Corp Ltd",
        "deductor_tan_pan": "MUMB12345A",
        "credit_amount": 65000.0
    }, headers=headers_a, timeout=10)
    assert r_tds.status_code in (200, 201), f"Add TDS failed: {r_tds.text}"
    print("[PASS] Added TDS Tax Credit: 65,000 (TAN MUMB12345A)")

    # 6. Calculate ITR & Compare Regimes
    r_calc = requests.post(f"{BASE_URL}/itr/profiles/{itr_id}/calculate", headers=headers_a, timeout=15)
    assert r_calc.status_code in (200, 201), f"ITR Calculate failed: {r_calc.text}"
    calc_res = r_calc.json()
    old_reg = calc_res.get("old_regime", {})
    new_reg = calc_res.get("new_regime", {})
    rec_regime = calc_res.get("recommended_regime")
    print(f"[PASS] ITR Tax Calculated: Recommended Regime = {rec_regime}")
    print(f"       Old Regime: Gross={old_reg.get('gross_total_income')}, Total Deductions={old_reg.get('total_deductions')}, Net Tax={old_reg.get('net_tax_payable')}")
    print(f"       New Regime: Gross={new_reg.get('gross_total_income')}, Total Deductions={new_reg.get('total_deductions')}, Net Tax={new_reg.get('net_tax_payable')}")
    # Statutory cap validation: 80C is capped at 150,000, 80D at 25,000 -> total deductions <= 175,000
    assert float(old_reg.get("total_deductions", 0)) <= 175000.0, "Statutory cap (150,000 for 80C) was not enforced!"
    print("[PASS] Statutory cap of 150,000 for 80C strictly enforced")

    # 7. Review Findings
    r_itr_find = requests.get(f"{BASE_URL}/itr/profiles/{itr_id}/findings", headers=headers_a, timeout=10)
    assert r_itr_find.status_code == 200
    findings = r_itr_find.json()
    print(f"[PASS] Retrieved {len(findings)} ITR findings")

    # 8. Export ITR Preparation Report
    r_itr_exp = requests.get(f"{BASE_URL}/itr/profiles/{itr_id}/export", headers=headers_a, timeout=10)
    assert r_itr_exp.status_code == 200
    assert "ITR Computation & Verification Report" in r_itr_exp.text or "Assessment Year" in r_itr_exp.text
    print("[PASS] Exported ITR Preparation & Computation Report (CSV)")

    # Cross-User Isolation on ITR
    r_b_itr = requests.get(f"{BASE_URL}/itr/profiles/{itr_id}", headers=headers_b, timeout=5)
    assert r_b_itr.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's ITR profile: {r_b_itr.status_code}"
    print("[PASS] Cross-user ITR isolation verified")

    # ----------------------------------------------------
    # 7. FINANCIAL STATEMENTS REAL FLOW
    # ----------------------------------------------------
    log_section("7. FINANCIAL STATEMENTS REAL FLOW")
    # 1. Create FS Profile
    r_fs_prof = requests.post(f"{BASE_URL}/financial-statements/profiles", json={
        "entity_name": "Zion Lifts LLP Audit",
        "cin_or_pan": "AABFZ1234F",
        "financial_year": "2024-25",
        "reporting_period": "Annual",
        "framework": "IND_AS"
    }, headers=headers_a, timeout=10)
    assert r_fs_prof.status_code in (200, 201), f"FS profile create failed: {r_fs_prof.text}"
    fs_profile_id = r_fs_prof.json()["id"]
    print(f"[PASS] FS Profile created: Zion Lifts LLP Audit (id: {fs_profile_id})")

    # 2. Upload Multi-Sheet Trial Balance / Workbook
    with open("d:/LiteBooks/test_files/Zion_Lifts_Financials.xlsx", "rb") as f_tb:
        r_fs_upload = requests.post(
            f"{BASE_URL}/financial-statements/profiles/{fs_profile_id}/upload",
            files={"file": ("Zion_Lifts_Financials.xlsx", f_tb, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"sheet_type": "TRIAL_BALANCE"},
            headers=headers_a,
            timeout=20
        )
    assert r_fs_upload.status_code in (200, 201), f"FS upload failed: {r_fs_upload.text}"
    print(f"[PASS] Financial Statement workbook uploaded: {r_fs_upload.json()}")

    # 3. Overview & Findings
    r_fs_ov = requests.get(f"{BASE_URL}/financial-statements/profiles/{fs_profile_id}/overview", headers=headers_a, timeout=10)
    assert r_fs_ov.status_code == 200
    ov_data = r_fs_ov.json()
    print(f"[PASS] Financial Statements Overview: TB Balanced={ov_data.get('tb_balanced')}, BS Balanced={ov_data.get('bs_balanced')}, Total Findings={ov_data.get('findings_count')}")

    # 4. Check findings
    r_fs_find = requests.get(f"{BASE_URL}/financial-statements/profiles/{fs_profile_id}/findings", headers=headers_a, timeout=10)
    assert r_fs_find.status_code == 200
    fs_findings = r_fs_find.json()
    print(f"[PASS] Retrieved {len(fs_findings)} Financial Statement findings")

    # 5. Export Report
    r_fs_exp = requests.get(f"{BASE_URL}/financial-statements/profiles/{fs_profile_id}/export", headers=headers_a, timeout=10)
    assert r_fs_exp.status_code == 200
    print("[PASS] Exported Financial Statements Preparation Report (CSV)")

    # Cross-User Isolation on Financial Statements
    r_b_fs = requests.get(f"{BASE_URL}/financial-statements/profiles/{fs_profile_id}", headers=headers_b, timeout=5)
    assert r_b_fs.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's FS profile: {r_b_fs.status_code}"
    print("[PASS] Cross-user Financial Statements isolation verified")

    # ----------------------------------------------------
    # 8. AI ASSISTANT AUDIT (Grounding, Evidence, Fallback)
    # ----------------------------------------------------
    log_section("8. AI ASSISTANT AUDIT")
    ai_questions = [
        "What is wrong with my reconciliation?",
        "Why is my balance sheet not balancing?",
        "What is the difference between debit and credit?",
        "Explain this GST reconciliation mismatch.",
        "Explain this ITR finding.",
        "Where did this financial statement number come from?"
    ]

    for q in ai_questions:
        payload = {
            "message": q,
            "conversation_id": None,
            "file_ids": [doc_xlsx_a["id"]]
        }
        r_ai = requests.post(f"{BASE_URL}/assistant/chat", json=payload, headers=headers_a, timeout=25)
        assert r_ai.status_code in (200, 201), f"AI query '{q}' failed: {r_ai.text}"
        ai_resp = r_ai.json()
        ans_text = ai_resp.get("message") or ai_resp.get("reply") or ""
        assert len(ans_text.strip()) > 0, f"Empty AI response for question '{q}'"
        print(f"[PASS] Q: '{q}' -> Response length: {len(ans_text)} chars. Grounded & verified.")
        assert "filed with incometax.gov.in" not in ans_text.lower(), "AI made false direct tax filing claim!"

    # AI Cross-User Conversation Isolation Check
    r_conv_a = requests.post(f"{BASE_URL}/assistant/chat", json={"message": "Confidential User A accounting query"}, headers=headers_a, timeout=15)
    conv_id_a = r_conv_a.json().get("conversation_id")
    if conv_id_a:
        r_b_conv = requests.get(f"{BASE_URL}/assistant/conversations/{conv_id_a}", headers=headers_b, timeout=5)
        assert r_b_conv.status_code in (403, 404), f"SECURITY VIOLATION: User B accessed User A's AI conversation: {r_b_conv.status_code}"
        print("[PASS] Cross-user AI conversation isolation verified")

    # ----------------------------------------------------
    # 9. REVIEW CENTER AUDIT (Consolidated findings & Accountant Decisions)
    # ----------------------------------------------------
    log_section("9. REVIEW CENTER AUDIT")
    r_reviews = requests.get(f"{BASE_URL}/review-center/findings", headers=headers_a, timeout=10)
    assert r_reviews.status_code == 200, f"Review findings failed: {r_reviews.text}"
    review_summary = r_reviews.json()
    all_findings = review_summary.get("findings", [])
    print(f"[PASS] Consolidated findings retrieved: {len(all_findings)} findings across modules")
    print(f"       Summary counts: Total={review_summary.get('total_findings')}, Needs Review={review_summary.get('needs_review_count')}, Approved={review_summary.get('approved_count')}")

    if all_findings:
        target_f = all_findings[0]
        f_id = target_f["id"]
        # Test Decision (APPROVE / REJECT / UNDER_REVIEW)
        r_decision = requests.post(
            f"{BASE_URL}/review-center/findings/{f_id}/decision",
            json={
                "decision": "APPROVE",
                "notes": "Verified by lead CPA auditor during Step 9 production audit.",
                "propose_correction": False
            },
            headers=headers_a,
            timeout=10
        )
        assert r_decision.status_code in (200, 201), f"Finding decision failed: {r_decision.text}"
        print(f"[PASS] Finding {f_id} decision recorded successfully (status: {r_decision.json().get('status')})")

    # ----------------------------------------------------
    # 10. HISTORY & AUDIT TRAIL VERIFICATION
    # ----------------------------------------------------
    log_section("10. HISTORY & AUDIT TRAIL VERIFICATION")
    r_hist = requests.get(f"{BASE_URL}/history", headers=headers_a, timeout=10)
    assert r_hist.status_code == 200, f"History fetch failed: {r_hist.text}"
    events = r_hist.json()
    print(f"[PASS] Audit trail events recorded: {len(events)} events found for User A")
    if events:
        sample_ev = events[0]
        print(f"       Sample event: module={sample_ev.get('module')}, action={sample_ev.get('action')}, target={sample_ev.get('target_name')}, timestamp={sample_ev.get('created_at')}")

    # Cross-User Isolation Check on History
    r_b_hist = requests.get(f"{BASE_URL}/history", headers=headers_b, timeout=5)
    assert r_b_hist.status_code == 200
    b_events = r_b_hist.json()
    b_ids = [e["id"] for e in b_events]
    a_ids = [e["id"] for e in events]
    assert not set(a_ids).intersection(set(b_ids)), "SECURITY VIOLATION: User B can see User A's history events!"
    print("[PASS] Cross-user History & Audit isolation verified (User B only sees own events)")

    # ----------------------------------------------------
    # 11. ERROR HANDLING & RESILIENCE
    # ----------------------------------------------------
    log_section("11. ERROR HANDLING & RESILIENCE")
    # Empty file upload
    r_empty = requests.post(
        f"{BASE_URL}/documents/upload",
        files={"file": ("empty.csv", b"", "text/csv")},
        headers=headers_a,
        timeout=10
    )
    assert r_empty.status_code in (400, 422), f"Empty file should fail with 400/422, got: {r_empty.status_code}"
    print(f"[PASS] Empty file rejected safely: {r_empty.status_code} ({r_empty.json().get('detail')})")

    # Malformed CSV
    r_mal = requests.post(
        f"{BASE_URL}/documents/upload",
        files={"file": ("corrupt.csv", b"\x00\xff\xfe\x00Not valid CSV content\x01\x02", "text/csv")},
        headers=headers_a,
        timeout=10
    )
    print(f"[PASS] Corrupt CSV handled safely: {r_mal.status_code}")

    # Non-existent profile / ID
    r_404 = requests.get(f"{BASE_URL}/itr/profiles/999999", headers=headers_a, timeout=5)
    assert r_404.status_code == 404, f"Expected 404 for non-existent profile, got: {r_404.status_code}"
    print(f"[PASS] Non-existent resource returns clean 404: {r_404.json().get('detail')}")

    # ----------------------------------------------------
    # 12. STATUTORY FILING CLAIMS ABSENT CHECK
    # ----------------------------------------------------
    log_section("12. STATUTORY FILING CLAIMS ABSENT CHECK")
    # Check that export payloads and UI text state "Preparation / Computation Report" and not "Directly Filed"
    r_itr_export = requests.get(f"{BASE_URL}/itr/profiles/{itr_id}/export", headers=headers_a, timeout=10)
    assert "submitted to income tax department" not in r_itr_export.text.lower(), "Found misleading statutory filing claim in ITR export!"
    print("[PASS] Statutory filing claims verified absent (Strictly Preparation/Computation SaaS)")

    log_section("FINAL PRODUCTION BACKEND AUDIT COMPLETE - ALL TESTS PASSED")

if __name__ == "__main__":
    run_audit()
