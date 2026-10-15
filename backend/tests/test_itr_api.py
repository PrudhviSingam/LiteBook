import json
import random
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_itr_api_full_lifecycle(default_test_user):
    # 1. Create Profile
    digits = random.randint(1000, 9999)
    pan = f"AAAPA{digits}K"

    res = client.post(
        "/api/itr/profiles",
        json={
            "pan": pan,
            "taxpayer_name": "Meera Venkat",
            "taxpayer_category": "INDIVIDUAL",
            "assessment_year": "2024-25",
            "financial_year": "2023-24",
            "selected_regime": "UNDECIDED",
        },
    )
    assert res.status_code == 201, res.text
    profile = res.json()
    p_id = profile["id"]
    assert profile["pan"] == pan

    # 2. Add Incomes via API
    inc_res = client.post(
        f"/api/itr/profiles/{p_id}/incomes",
        json={
            "head_of_income": "SALARY",
            "subcategory": "BASIC",
            "description": "Annual CTC Salary",
            "gross_amount": "1200000.00",
            "source_document": "Form16_Meera.pdf",
            "source_sheet": "Salary_Annexure",
            "source_row": 15,
        },
    )
    assert inc_res.status_code == 200, inc_res.text

    # Add House Property Income
    hp_res = client.post(
        f"/api/itr/profiles/{p_id}/incomes",
        json={
            "head_of_income": "HOUSE_PROPERTY",
            "subcategory": "RENTAL",
            "description": "Residential Rental Income",
            "gross_amount": "180000.00",
            "source_document": "Rental_Agreement.pdf",
            "source_row": 4,
        },
    )
    assert hp_res.status_code == 200, hp_res.text

    # 3. Add Deductions via API
    ded_res = client.post(
        f"/api/itr/profiles/{p_id}/deductions",
        json={
            "section": "80C",
            "description": "LIC and Sukanya Samriddhi",
            "claimed_amount": "150000.00",
            "eligible_amount": "150000.00",
            "status": "VERIFIED",
            "source_document": "Receipts.pdf",
        },
    )
    assert ded_res.status_code == 200, ded_res.text

    # Add Tax Credit
    cred_res = client.post(
        f"/api/itr/profiles/{p_id}/tax-credits",
        json={
            "credit_type": "TDS_SALARY",
            "deductor_or_bank": "Tech Services LLP",
            "deductor_tan_pan": "DELT12345B",
            "credit_amount": "95000.00",
            "source_document": "Form26AS.pdf",
        },
    )
    assert cred_res.status_code == 200, cred_res.text

    # 4. Trigger Calculation via API
    calc_res = client.post(f"/api/itr/profiles/{p_id}/calculate")
    assert calc_res.status_code == 200, calc_res.text
    comparison = calc_res.json()
    assert comparison["profile_id"] == p_id
    assert float(comparison["old_regime"]["gross_total_income"]) > 0
    assert float(comparison["new_regime"]["gross_total_income"]) > 0

    # 5. Check Findings via Review Center
    rc_res = client.get("/api/v1/review-center/findings")
    assert rc_res.status_code == 200, rc_res.text
    rc_data = rc_res.json()
    itr_findings = [f for f in rc_data["findings"] if f["id"].startswith("itr_")]
    assert len(itr_findings) >= 1  # Undecided regime finding

    # 6. Resolve finding via Review Center Decision endpoint
    target_finding = itr_findings[0]
    dec_res = client.post(
        f"/api/v1/review-center/findings/{target_finding['id']}/decision",
        json={"decision": "APPROVE", "notes": "Regime explicitly agreed with taxpayer."},
    )
    assert dec_res.status_code == 200, dec_res.text

    # 7. Select Explicit Regime and Transition Status to APPROVED
    up_res = client.put(f"/api/itr/profiles/{p_id}", json={"selected_regime": "NEW"})
    assert up_res.status_code == 200, up_res.text

    status_res = client.post(
        f"/api/itr/profiles/{p_id}/status",
        json={"target_status": "APPROVED", "notes": "Approved by senior tax partner."},
    )
    assert status_res.status_code == 200, status_res.text
    assert status_res.json()["status"] == "APPROVED"

    # 8. Export Preparation Report
    exp_res = client.get(f"/api/itr/profiles/{p_id}/export")
    assert exp_res.status_code == 200, exp_res.text
    assert "ITR Preparation Report — Accountant Review Required" in exp_res.text
    assert pan in exp_res.text
