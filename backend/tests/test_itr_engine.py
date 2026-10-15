from decimal import Decimal
import pytest
from app.modules.itr.calculator import ITRCalculator
from app.modules.itr.service import ITRService
from app.modules.itr.schemas import (
    ITRProfileCreate,
    ITRIncomeEntryCreate,
    ITRDeductionEntryCreate,
    ITRTaxCreditEntryCreate,
    ITRStatusTransitionRequest,
    ITRFindingDecisionRequest,
)
from app.models.history import HistoryRecord


def test_itr_calculator_old_regime_rebate_87a():
    """Old Regime: Taxable income <= ₹5,00,000 gets full 87A rebate resulting in 0 net tax liability."""
    res = ITRCalculator.calculate_tax(
        regime="OLD",
        assessment_year="2024-25",
        gross_salary=Decimal("550000.00"),  # Less standard deduction ₹50k = ₹5,00,000 net
        house_property=Decimal("0.00"),
        business_profession=Decimal("0.00"),
        capital_gains=Decimal("0.00"),
        other_sources=Decimal("0.00"),
        verified_deductions_80c=Decimal("0.00"),
        verified_deductions_80d=Decimal("0.00"),
        verified_deductions_80ccd_1b=Decimal("0.00"),
        other_verified_deductions=Decimal("0.00"),
        tds_total=Decimal("0.00"),
        tcs_total=Decimal("0.00"),
        advance_tax_total=Decimal("0.00"),
        self_assessment_tax_total=Decimal("0.00"),
    )
    assert res["gross_salary"] == Decimal("550000.00")
    assert res["standard_deduction"] == Decimal("50000.00")
    assert res["net_salary"] == Decimal("500000.00")
    assert res["total_taxable_income"] == Decimal("500000.00")
    # Basic tax on ₹5,00,000 in Old Regime = 5% of (500000 - 250000) = ₹12,500
    assert res["basic_tax"] == Decimal("12500.00")
    assert res["rebate_87a"] == Decimal("12500.00")
    assert res["total_tax_liability"] == Decimal("0.00")
    assert res["net_payable_or_refund"] == Decimal("0.00")


def test_itr_calculator_new_regime_rebate_87a():
    """New Regime: Taxable income <= ₹7,00,000 gets full 87A rebate up to ₹25,000."""
    res = ITRCalculator.calculate_tax(
        regime="NEW",
        assessment_year="2024-25",
        gross_salary=Decimal("750000.00"),  # Less standard deduction ₹50k = ₹7,00,000 net
        house_property=Decimal("0.00"),
        business_profession=Decimal("0.00"),
        capital_gains=Decimal("0.00"),
        other_sources=Decimal("0.00"),
        verified_deductions_80c=Decimal("150000.00"),  # Disallowed under 115BAC
        verified_deductions_80d=Decimal("25000.00"),
        verified_deductions_80ccd_1b=Decimal("0.00"),
        other_verified_deductions=Decimal("0.00"),
        tds_total=Decimal("10000.00"),
        tcs_total=Decimal("0.00"),
        advance_tax_total=Decimal("0.00"),
        self_assessment_tax_total=Decimal("0.00"),
    )
    assert res["standard_deduction"] == Decimal("50000.00")
    assert res["net_salary"] == Decimal("700000.00")
    assert res["total_deductions"] == Decimal("0.00")  # Disallowed
    assert res["total_taxable_income"] == Decimal("700000.00")
    # New Regime Slabs:
    # 0-3L: Nil
    # 3-6L: 5% of 3L = 15,000
    # 6-7L: 10% of 1L = 10,000
    # Total Basic Tax = 25,000
    assert res["basic_tax"] == Decimal("25000.00")
    assert res["rebate_87a"] == Decimal("25000.00")
    assert res["total_tax_liability"] == Decimal("0.00")
    # TDS of ₹10,000 paid leads to a ₹10,000 refund
    assert res["net_payable_or_refund"] == Decimal("-10000.00")


def test_itr_calculator_80c_cap_and_cess():
    """80C deductions above ₹1,50,000 are capped to ₹1,50,000 under Old Regime, and 4% cess is applied."""
    res = ITRCalculator.calculate_tax(
        regime="OLD",
        assessment_year="2024-25",
        gross_salary=Decimal("1200000.00"),  # Net salary = ₹11,50,000
        house_property=Decimal("0.00"),
        business_profession=Decimal("0.00"),
        capital_gains=Decimal("0.00"),
        other_sources=Decimal("0.00"),
        verified_deductions_80c=Decimal("250000.00"),  # Capped at ₹1,50,000
        verified_deductions_80d=Decimal("25000.00"),
        verified_deductions_80ccd_1b=Decimal("50000.00"),
        other_verified_deductions=Decimal("0.00"),
        tds_total=Decimal("80000.00"),
        tcs_total=Decimal("0.00"),
        advance_tax_total=Decimal("10000.00"),
        self_assessment_tax_total=Decimal("0.00"),
    )
    # Deductions: 1,50,000 (80C) + 50,000 (80CCD) + 25,000 (80D) = 2,25,000
    assert res["total_deductions"] == Decimal("225000.00")
    # Taxable Income = 11,50,000 - 2,25,000 = 9,25,000
    assert res["total_taxable_income"] == Decimal("925000.00")
    # Tax under Old Regime for ₹9,25,000:
    # 0 - 2.5L: Nil
    # 2.5L - 5L: 12,500
    # 5L - 9.25L: 20% of 4,25,000 = 85,000
    # Basic Tax = 97,500
    assert res["basic_tax"] == Decimal("97500.00")
    # Cess @ 4% = 97,500 * 0.04 = 3,900
    assert res["cess_4_pct"] == Decimal("3900.00")
    assert res["total_tax_liability"] == Decimal("101400.00")
    # Taxes paid = 80,000 + 10,000 = 90,000
    # Net payable = 101,400 - 90,000 = 11,400
    assert res["net_payable_or_refund"] == Decimal("11400.00")


def test_itr_full_e2e_workflow(default_test_user):
    """
    End-to-End statutory ITR workflow test:
    1. Create Profile
    2. Add Incomes, Deductions, and Tax Credits with provenance
    3. Run deterministic calculation and verify snapshots & regime comparison
    4. Verify Review Center findings generation (e.g. 80C excess, regime selection)
    5. Test Approval Safety Rule (blocks approval while critical/high findings exist)
    6. Accountant review and resolution of findings
    7. Select explicit tax regime and approve return
    8. Verify audit history records
    9. Verify export preparation report with statutory disclaimer
    """
    import random
    from app.core.database import SessionLocal
    from app.modules.itr.models import ITRProfile
    db = SessionLocal()
    user = default_test_user

    # Clean up previous run if any
    digits = random.randint(1000, 9999)
    pan = f"ABCDE{digits}F"

    # 1. Create Profile
    profile = ITRService.create_profile(
        db=db,
        user=user,
        data=ITRProfileCreate(
            pan=pan,
            taxpayer_name="Rohan Sharma",
            taxpayer_category="INDIVIDUAL",
            assessment_year="2024-25",
            financial_year="2023-24",
            selected_regime="UNDECIDED",
        ),
    )
    assert profile.id is not None
    assert profile.status == "DRAFT"

    # 2. Add Salary Income
    inc = ITRService.add_income_entry(
        db=db,
        user=user,
        profile_id=profile.id,
        data=ITRIncomeEntryCreate(
            head_of_income="SALARY",
            subcategory="BASIC_SALARY",
            description="Software Engineering Salary",
            gross_amount=Decimal("1500000.00"),
            source_document="Form16_Rohan_2023_24.pdf",
            source_sheet="Part_B",
            source_row=12,
            source_cell="B12",
        ),
    )
    assert inc.net_taxable_amount == Decimal("1500000.00")

    # Add 80C deduction with intentional excess to trigger a review finding
    ded = ITRService.add_deduction_entry(
        db=db,
        user=user,
        profile_id=profile.id,
        data=ITRDeductionEntryCreate(
            section="80C",
            description="EPF and PPF contribution",
            claimed_amount=Decimal("180000.00"),  # > 1.5L triggers finding
            eligible_amount=Decimal("150000.00"),
            source_document="PPF_Statement_2023_24.pdf",
        ),
    )
    assert ded.id is not None

    # Add TDS Credit
    cred = ITRService.add_tax_credit_entry(
        db=db,
        user=user,
        profile_id=profile.id,
        data=ITRTaxCreditEntryCreate(
            credit_type="TDS_SALARY",
            deductor_or_bank="Tech Corp India Pvt Ltd",
            deductor_tan_pan="BLRT12345A",
            credit_amount=Decimal("120000.00"),
            date_of_payment="2024-03-31",
            source_document="Form26AS_2023_24.pdf",
        ),
    )
    assert cred.id is not None

    # 3. Calculate ITR & Verify Regime Comparison
    comp = ITRService.calculate_itr(db=db, user=user, profile_id=profile.id)
    assert comp.old_regime.gross_total_income == Decimal("1450000.00")  # 15L - 50k standard deduction
    assert comp.new_regime.gross_total_income == Decimal("1450000.00")
    assert comp.difference_in_tax >= Decimal("0.00")

    # 4. Verify Findings Generated
    findings = ITRService.get_findings(db=db, user=user, profile_id=profile.id)
    finding_types = [f.finding_type for f in findings]
    assert "UNSUPPORTED_DEDUCTION" in finding_types  # 80C exceeded
    assert "CALCULATION_VERIFICATION" in finding_types  # Undecided regime

    # 5. Safety Rule: Cannot approve while regime is UNDECIDED
    with pytest.raises(Exception) as exc:
        ITRService.transition_status(db=db, user=user, profile_id=profile.id, target_status="APPROVED")
    assert "Safety Block" in str(exc.value)

    # 6. Resolve findings
    for f in findings:
        ITRService.update_finding_decision(
            db=db,
            user=user,
            profile_id=profile.id,
            finding_id=f.id,
            req=ITRFindingDecisionRequest(decision="ACCEPTED", notes="Verified by accountant"),
        )

    # Select explicit regime
    ITRService.update_profile(
        db=db,
        user=user,
        profile_id=profile.id,
        data={"selected_regime": "NEW"},
    )

    # 7. Approve return
    approved_prof = ITRService.transition_status(
        db=db,
        user=user,
        profile_id=profile.id,
        target_status="APPROVED",
        notes="Final sign-off by Partner Accountant",
    )
    assert approved_prof.status == "APPROVED"
    assert approved_prof.approved_at is not None

    # 8. Verify audit history
    hist = db.query(HistoryRecord).filter(HistoryRecord.user_id == user.id, HistoryRecord.module == "itr").all()
    actions = [h.action for h in hist]
    assert "create_profile" in actions
    assert "add_income" in actions
    assert "calculate_tax" in actions
    assert "transition_status" in actions

    # 9. Verify Export Preparation Report
    report = ITRService.export_report(db=db, user=user, profile_id=profile.id)
    assert "ITR Preparation Report — Accountant Review Required" in report
    assert "This return has NOT been submitted to the Income Tax Department." in report
    assert "Rohan Sharma" in report
    assert pan in report
