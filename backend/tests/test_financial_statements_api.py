import csv
import io
import random
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app.models.history import HistoryRecord
from app.core.database import SessionLocal

client = TestClient(app)


def test_financial_statements_api_e2e(default_test_user):
    rand_id = random.randint(1000, 9999)
    entity_name = f"Nexus Dynamics India Pvt Ltd {rand_id}"

    # 1. Create Profile
    res = client.post(
        "/api/financial-statements/profiles",
        json={
            "entity_name": entity_name,
            "cin_or_pan": f"U72200MH2024PTC{rand_id}",
            "financial_year": "2023-24",
            "reporting_period": "ANNUAL",
            "framework": "SCHEDULE_III",
        },
    )
    assert res.status_code == 201, res.text
    profile = res.json()
    profile_id = profile["id"]
    assert profile["entity_name"] == entity_name
    assert profile["status"] == "DRAFT"

    # 2. Add Trial Balance entries via API with strict provenance
    tb_payload = [
        {
            "account_code": "1001",
            "account_name": "Property, Plant & Equipment",
            "account_category": "ASSET",
            "debit_amount": "500000.00",
            "credit_amount": "0.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "TB",
            "source_row": 3,
            "source_cell": "D3",
            "source_value": "500000.00",
            "provenance_notes": "Audited fixed asset register",
        },
        {
            "account_code": "1002",
            "account_name": "Cash & Bank Balances",
            "account_category": "ASSET",
            "debit_amount": "200000.00",
            "credit_amount": "0.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "TB",
            "source_row": 4,
            "source_cell": "D4",
            "source_value": "200000.00",
        },
        {
            "account_code": "2001",
            "account_name": "Equity Share Capital",
            "account_category": "EQUITY",
            "debit_amount": "0.00",
            "credit_amount": "400000.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "TB",
            "source_row": 5,
            "source_cell": "E5",
            "source_value": "400000.00",
        },
        {
            "account_code": "2002",
            "account_name": "Long Term Borrowings (Bank)",
            "account_category": "LIABILITY",
            "debit_amount": "0.00",
            "credit_amount": "300000.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "TB",
            "source_row": 6,
            "source_cell": "E6",
            "source_value": "300000.00",
        },
    ]

    tb_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/trial-balance",
        json=tb_payload,
    )
    assert tb_res.status_code == 200, tb_res.text
    entries = tb_res.json()
    assert len(entries) == 4
    assert entries[0]["source_document"] == "Nexus_Trial_Balance_FY24.csv"
    assert entries[0]["source_cell"] == "D3"

    # 3. Auto-Classify from Trial Balance
    classify_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/auto-classify"
    )
    assert classify_res.status_code == 200, classify_res.text
    cls_data = classify_res.json()
    assert cls_data["balance_sheet_lines"] == 4

    # 4. Add Profit & Loss lines directly
    pl_payload = [
        {
            "category": "REVENUE",
            "line_item_name": "Revenue from Operations",
            "amount": "800000.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "P&L",
            "source_row": 10,
        },
        {
            "category": "EMPLOYEE_BENEFITS",
            "line_item_name": "Salaries & Wages",
            "amount": "300000.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "P&L",
            "source_row": 15,
        },
        {
            "category": "OTHER_EXPENSES",
            "line_item_name": "Administrative & Operating Expenses",
            "amount": "200000.00",
            "source_document": "Nexus_Trial_Balance_FY24.csv",
            "source_sheet": "P&L",
            "source_row": 18,
        },
    ]
    pl_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/profit-loss",
        json=pl_payload,
    )
    assert pl_res.status_code == 200, pl_res.text

    # 5. Add Cash Flow lines
    cf_payload = [
        {
            "activity_type": "OPERATING",
            "line_item_name": "Operating Cash Inflows",
            "amount": "300000.00",
            "source_document": "Cash_Flow_Annexure.xlsx",
        },
        {
            "activity_type": "INVESTING",
            "line_item_name": "Purchase of Equipment",
            "amount": "-100000.00",
            "source_document": "Cash_Flow_Annexure.xlsx",
        },
    ]
    cf_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/cash-flow",
        json=cf_payload,
    )
    assert cf_res.status_code == 200, cf_res.text

    # 6. Execute Deterministic Calculation & Snapshot Generation
    calc_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/calculate"
    )
    assert calc_res.status_code == 200, calc_res.text
    calc_data = calc_res.json()
    assert calc_data["snapshot_version"] == 1
    assert len(calc_data["snapshot_hash"]) == 64
    assert calc_data["trial_balance"]["is_balanced"] is True
    assert float(calc_data["trial_balance"]["total_debit"]) == 700000.00
    assert float(calc_data["trial_balance"]["total_credit"]) == 700000.00
    assert calc_data["balance_sheet"]["is_balanced"] is True
    assert float(calc_data["balance_sheet"]["total_assets"]) == 700000.00
    assert float(calc_data["balance_sheet"]["total_equity_and_liabilities"]) == 700000.00
    assert float(calc_data["profit_loss"]["total_revenue"]) == 800000.00
    assert float(calc_data["profit_loss"]["total_expenses"]) == 500000.00
    assert float(calc_data["profit_loss"]["profit_after_tax"]) == 300000.00

    # 7. Check Dashboard Overview Metrics
    ov_res = client.get(
        f"/api/financial-statements/profiles/{profile_id}/overview"
    )
    assert ov_res.status_code == 200, ov_res.text
    ov = ov_res.json()
    assert float(ov["total_assets"]) == 700000.00
    assert float(ov["total_revenue"]) == 800000.00
    assert float(ov["net_profit"]) == 300000.00
    assert ov["is_tb_balanced"] is True
    assert ov["is_bs_balanced"] is True

    # 8. Test Review Center Integration
    # Query Review Center
    rc_res = client.get("/api/v1/review-center/findings")
    assert rc_res.status_code == 200, rc_res.text
    rc_data = rc_res.json()
    findings = rc_data["findings"]

    # 9. Test Finding Decision directly on FS endpoint and Review Center endpoint
    # Get profile findings
    f_res = client.get(f"/api/financial-statements/profiles/{profile_id}/findings")
    assert f_res.status_code == 200, f_res.text
    fs_findings = f_res.json()
    if fs_findings:
        target_f = fs_findings[0]
        f_id = target_f["id"]
        # Apply decision via FS endpoint
        dec_res = client.post(
            f"/api/financial-statements/findings/{f_id}/decision",
            json={"decision": "ACCEPTED", "notes": "Accountant confirmed provenance link"},
        )
        assert dec_res.status_code == 200, dec_res.text
        assert dec_res.json()["accountant_decision"] == "ACCEPTED"
        assert dec_res.json()["status"] == "APPROVED"

        # Apply decision via Review Center generic endpoint with prefix fs_
        rc_dec_res = client.post(
            f"/api/v1/review-center/findings/fs_{f_id}/decision",
            json={"decision": "ACCEPT", "notes": "Reviewed in master Review Center"},
        )
        assert rc_dec_res.status_code == 200, rc_dec_res.text

    # 10. Status Transition and Approval Safety
    # Test valid approval since books balance and all critical items are resolved
    appr_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/status",
        json={"target_status": "APPROVED", "notes": "Signoff completed by Senior Partner"},
    )
    assert appr_res.status_code == 200, appr_res.text
    appr_data = appr_res.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["approved_at"] is not None

    # 11. Test Export Accountant Preparation Report
    exp_res = client.get(f"/api/financial-statements/profiles/{profile_id}/export")
    assert exp_res.status_code == 200, exp_res.text
    csv_content = exp_res.text
    assert "FINANCIAL STATEMENTS — ACCOUNTANT REVIEW REQUIRED" in csv_content
    assert "NOT A STATUTORY SUBMISSION" in csv_content
    assert entity_name in csv_content
    assert "Nexus_Trial_Balance_FY24.csv" in csv_content
    assert "Property, Plant & Equipment" in csv_content

    # 12. Verify Audit History Logging
    db = SessionLocal()
    try:
        hist_records = (
            db.query(HistoryRecord)
            .filter(HistoryRecord.module == "financial_statements")
            .all()
        )
        assert len(hist_records) >= 3
        actions = [h.action for h in hist_records]
        assert "create_profile" in actions
        assert "calculate_and_snapshot" in actions
        assert "approve_financial_statements" in actions
    finally:
        db.close()


def test_file_upload_csv(default_test_user):
    rand_id = random.randint(1000, 9999)
    res = client.post(
        "/api/financial-statements/profiles",
        json={
            "entity_name": f"CSV Import Co {rand_id}",
            "financial_year": "2023-24",
            "reporting_period": "ANNUAL",
            "framework": "SCHEDULE_III",
        },
    )
    profile_id = res.json()["id"]

    csv_data = (
        "Account Code,Account Name,Category,Debit,Credit\n"
        "101,Office Equipment,ASSET,75000.00,0.00\n"
        "102,Bank Account,ASSET,25000.00,0.00\n"
        "201,Capital Account,EQUITY,0.00,100000.00\n"
    )

    upload_res = client.post(
        f"/api/financial-statements/profiles/{profile_id}/upload",
        files={"file": ("trial_balance.csv", io.BytesIO(csv_data.encode("utf-8")), "text/csv")},
    )
    assert upload_res.status_code == 200, upload_res.text
    up_json = upload_res.json()
    assert up_json["imported_entries"] == 3

    # Verify provenance was saved
    tb_res = client.get(f"/api/financial-statements/profiles/{profile_id}/trial-balance")
    entries = tb_res.json()
    assert len(entries) == 3
    assert entries[0]["source_document"] == "trial_balance.csv"
    assert entries[0]["source_row"] == 2
