import csv
import io
import pytest
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.financial_statements.calculator import FSCalculator
from app.modules.financial_statements.models import (
    FinancialStatementProfile,
    TrialBalanceEntry,
    BalanceSheetLine,
    ProfitLossLine,
    CashFlowLine,
    FinancialStatementSnapshot,
    FinancialStatementFinding,
)
from app.modules.financial_statements.schemas import (
    FSProfileCreate,
    TrialBalanceEntryCreate,
    BalanceSheetLineCreate,
    ProfitLossLineCreate,
    CashFlowLineCreate,
)
from app.modules.financial_statements.service import FSService
from app.modules.financial_statements.validator import FSValidator


class DummyEntry:
    def __init__(self, debit=0, credit=0, category="ASSET"):
        self.debit_amount = Decimal(str(debit))
        self.credit_amount = Decimal(str(credit))
        self.account_category = category


class DummyBSLine:
    def __init__(self, classification, amount, sub_cat="OTHER"):
        self.classification = classification
        self.amount = Decimal(str(amount))
        self.sub_category = sub_cat
        self.source_document = "test.xlsx"


class DummyPLLine:
    def __init__(self, category, amount):
        self.category = category
        self.amount = Decimal(str(amount))
        self.source_document = "test.xlsx"


class DummyCFLine:
    def __init__(self, activity, amount):
        self.activity_type = activity
        self.amount = Decimal(str(amount))
        self.source_document = "test.xlsx"


# ============================================================================
# 1. Calculator Engine Tests
# ============================================================================

def test_trial_balance_balanced():
    entries = [
        DummyEntry(debit=150000, credit=0),
        DummyEntry(debit=50000, credit=0),
        DummyEntry(debit=0, credit=200000),
    ]
    calc = FSCalculator.calculate_trial_balance(entries)
    assert calc["total_debit"] == Decimal("200000.00")
    assert calc["total_credit"] == Decimal("200000.00")
    assert calc["difference"] == Decimal("0.00")
    assert calc["is_balanced"] is True


def test_trial_balance_unbalanced():
    entries = [
        DummyEntry(debit=150000, credit=0),
        DummyEntry(debit=0, credit=140000),
    ]
    calc = FSCalculator.calculate_trial_balance(entries)
    assert calc["total_debit"] == Decimal("150000.00")
    assert calc["total_credit"] == Decimal("140000.00")
    assert calc["difference"] == Decimal("10000.00")
    assert calc["is_balanced"] is False


def test_profit_loss_calculation():
    lines = [
        DummyPLLine("REVENUE", 1000000),
        DummyPLLine("OTHER_INCOME", 50000),
        DummyPLLine("COST_OF_MATERIALS", 300000),
        DummyPLLine("EMPLOYEE_BENEFITS", 200000),
        DummyPLLine("FINANCE_COSTS", 40000),
        DummyPLLine("DEPRECIATION", 60000),
        DummyPLLine("OTHER_EXPENSES", 100000),
        DummyPLLine("TAX_EXPENSE", 87500),
    ]
    calc = FSCalculator.calculate_profit_loss(lines)
    assert calc["total_revenue"] == Decimal("1050000.00")
    assert calc["cost_of_materials"] == Decimal("300000.00")
    assert calc["total_expenses"] == Decimal("700000.00")
    # EBITDA = Total Revenue - (Cost of materials + Employee benefits + Other expenses)
    # 1050000 - 600000 = 450000
    assert calc["ebitda"] == Decimal("450000.00")
    # PBT = Total Revenue - Total Expenses = 1050000 - 700000 = 350000
    assert calc["profit_before_tax"] == Decimal("350000.00")
    # PAT = PBT - Tax Expense = 350000 - 87500 = 262500
    assert calc["profit_after_tax"] == Decimal("262500.00")


def test_balance_sheet_schedule_iii_tally():
    lines = [
        # Assets (Total: 800,000)
        DummyBSLine("NON_CURRENT_ASSETS", 500000),
        DummyBSLine("CURRENT_ASSETS", 300000),
        # Equity & Liabilities (Total: 800,000)
        DummyBSLine("EQUITY", 400000),
        DummyBSLine("NON_CURRENT_LIABILITIES", 250000),
        DummyBSLine("CURRENT_LIABILITIES", 150000),
    ]
    calc = FSCalculator.calculate_balance_sheet(lines)
    assert calc["total_assets"] == Decimal("800000.00")
    assert calc["total_equity_and_liabilities"] == Decimal("800000.00")
    assert calc["balance_difference"] == Decimal("0.00")
    assert calc["is_balanced"] is True


def test_balance_sheet_mismatch():
    lines = [
        DummyBSLine("NON_CURRENT_ASSETS", 500000),
        DummyBSLine("CURRENT_ASSETS", 300000),  # Assets = 800,000
        DummyBSLine("EQUITY", 400000),
        DummyBSLine("NON_CURRENT_LIABILITIES", 200000),  # Equity & Liab = 600,000
    ]
    calc = FSCalculator.calculate_balance_sheet(lines)
    assert calc["total_assets"] == Decimal("800000.00")
    assert calc["total_equity_and_liabilities"] == Decimal("600000.00")
    assert calc["balance_difference"] == Decimal("200000.00")
    assert calc["is_balanced"] is False


def test_cash_flow_reconciliation():
    lines = [
        DummyCFLine("OPERATING", 180000),
        DummyCFLine("INVESTING", -60000),
        DummyCFLine("FINANCING", -40000),
    ]
    # Net change = 80,000. Opening cash = 20,000. Closing = 100,000
    calc = FSCalculator.calculate_cash_flow(
        lines, opening_cash=Decimal("20000.00"), balance_sheet_cash=Decimal("100000.00")
    )
    assert calc["net_change_in_cash"] == Decimal("80000.00")
    assert calc["closing_cash"] == Decimal("100000.00")
    assert calc["cash_matches_balance_sheet"] is True
    assert calc["cash_variance"] == Decimal("0.00")

    # Mismatch case
    calc_mismatch = FSCalculator.calculate_cash_flow(
        lines, opening_cash=Decimal("20000.00"), balance_sheet_cash=Decimal("95000.00")
    )
    assert calc_mismatch["cash_matches_balance_sheet"] is False
    assert calc_mismatch["cash_variance"] == Decimal("5000.00")


# ============================================================================
# 2. Validation Engine Tests
# ============================================================================

def test_validator_detects_unbalanced_trial_balance():
    profile = FinancialStatementProfile(
        id=1, entity_name="Alpha Tech LLP", financial_year="2023-24", reporting_period="ANNUAL"
    )
    tb_entry = TrialBalanceEntry(
        profile_id=1,
        account_name="Cash",
        debit_amount=Decimal("100.00"),
        credit_amount=Decimal("0.00"),
        source_document="TB.csv",
    )
    tb_calc = {"total_debit": Decimal("100.00"), "total_credit": Decimal("90.00"), "difference": Decimal("10.00"), "is_balanced": False}
    bs_calc = {"total_assets": Decimal("0.00"), "total_equity_and_liabilities": Decimal("0.00"), "balance_difference": Decimal("0.00"), "is_balanced": True}
    pl_calc = {"total_revenue": Decimal("0.00"), "total_expenses": Decimal("0.00"), "profit_before_tax": Decimal("0.00"), "tax_expense": Decimal("0.00"), "profit_after_tax": Decimal("0.00")}
    cf_calc = {"closing_cash": Decimal("0.00"), "cash_matches_balance_sheet": True}

    findings = FSValidator.validate_profile(
        profile=profile,
        tb_entries=[tb_entry],
        bs_lines=[],
        pl_lines=[],
        cf_lines=[],
        tb_calc=tb_calc,
        bs_calc=bs_calc,
        pl_calc=pl_calc,
        cf_calc=cf_calc,
    )
    types = [f["finding_type"] for f in findings]
    assert "TRIAL_BALANCE_UNBALANCED" in types
    tb_finding = next(f for f in findings if f["finding_type"] == "TRIAL_BALANCE_UNBALANCED")
    assert tb_finding["severity"] == "CRITICAL"
    assert tb_finding["variance"] == Decimal("10.00")
    # Verify possible_cause != proven_cause
    assert tb_finding["possible_cause"] is not None
    assert tb_finding["proven_cause"] is not None
    assert tb_finding["possible_cause"] != tb_finding["proven_cause"]


def test_validator_detects_balance_sheet_mismatch():
    profile = FinancialStatementProfile(
        id=1, entity_name="Alpha Tech LLP", financial_year="2023-24", reporting_period="ANNUAL"
    )
    bs_line = BalanceSheetLine(
        profile_id=1,
        classification="CURRENT_ASSETS",
        sub_category="CASH",
        line_item_name="Bank",
        amount=Decimal("50000.00"),
        source_document="BS.xlsx",
    )
    tb_calc = {"total_debit": Decimal("0.00"), "total_credit": Decimal("0.00"), "difference": Decimal("0.00"), "is_balanced": True}
    bs_calc = {
        "total_non_current_assets": Decimal("0.00"),
        "total_current_assets": Decimal("50000.00"),
        "total_assets": Decimal("50000.00"),
        "total_equity": Decimal("20000.00"),
        "total_non_current_liabilities": Decimal("0.00"),
        "total_current_liabilities": Decimal("10000.00"),
        "total_equity_and_liabilities": Decimal("30000.00"),
        "balance_difference": Decimal("20000.00"),
        "is_balanced": False,
    }
    pl_calc = {"total_revenue": Decimal("0.00"), "total_expenses": Decimal("0.00"), "profit_before_tax": Decimal("0.00"), "tax_expense": Decimal("0.00"), "profit_after_tax": Decimal("0.00")}
    cf_calc = {"closing_cash": Decimal("0.00"), "cash_matches_balance_sheet": True}

    findings = FSValidator.validate_profile(
        profile=profile,
        tb_entries=[],
        bs_lines=[bs_line],
        pl_lines=[],
        cf_lines=[],
        tb_calc=tb_calc,
        bs_calc=bs_calc,
        pl_calc=pl_calc,
        cf_calc=cf_calc,
    )
    types = [f["finding_type"] for f in findings]
    assert "BALANCE_SHEET_MISMATCH" in types
    bs_finding = next(f for f in findings if f["finding_type"] == "BALANCE_SHEET_MISMATCH")
    assert bs_finding["severity"] == "CRITICAL"
    assert bs_finding["variance"] == Decimal("20000.00")


# ============================================================================
# 3. Service Lifecycle & Snapshot Hash Tests
# ============================================================================

import random


def test_service_snapshot_immutability_and_hash(default_test_user):
    db: Session = SessionLocal()
    try:
        # Create profile
        p_in = FSProfileCreate(
            entity_name=f"Zion Robotics Ltd {random.randint(10000, 99999)}",
            financial_year="2023-24",
            reporting_period="ANNUAL",
            framework="SCHEDULE_III",
        )
        profile = FSService.get_or_create_profile(db=db, user_id=default_test_user.id, profile_in=p_in)

        # Add balanced TB entries
        entries = [
            TrialBalanceEntryCreate(
                account_code="1001",
                account_name="Cash & Bank Balances",
                account_category="ASSET",
                debit_amount=Decimal("150000.00"),
                credit_amount=Decimal("0.00"),
                source_document="Zion_TB_2024.xlsx",
                source_sheet="TB",
                source_row=5,
                source_cell="D5",
                source_value="150000.00",
            ),
            TrialBalanceEntryCreate(
                account_code="2001",
                account_name="Paid Up Share Capital",
                account_category="EQUITY",
                debit_amount=Decimal("0.00"),
                credit_amount=Decimal("150000.00"),
                source_document="Zion_TB_2024.xlsx",
                source_sheet="TB",
                source_row=12,
                source_cell="E12",
                source_value="150000.00",
            ),
        ]
        FSService.add_trial_balance_entries(
            db=db, user_id=default_test_user.id, profile_id=profile.id, entries=entries
        )

        # Auto classify to BS and P&L
        classify_res = FSService.auto_classify_from_trial_balance(
            db=db, user_id=default_test_user.id, profile_id=profile.id
        )
        assert classify_res["balance_sheet_lines"] == 2

        # 1st Calculation and Snapshot
        snap1_res = FSService.calculate_and_snapshot(
            db=db, user_id=default_test_user.id, profile_id=profile.id
        )
        assert snap1_res["snapshot_version"] == 1
        hash1 = snap1_res["snapshot_hash"]
        assert len(hash1) == 64  # SHA-256 length

        # Verify TB balanced
        assert snap1_res["trial_balance"]["is_balanced"] is True
        assert snap1_res["balance_sheet"]["is_balanced"] is True

        # 2nd Calculation should generate Snapshot v2, leaving v1 intact
        snap2_res = FSService.calculate_and_snapshot(
            db=db, user_id=default_test_user.id, profile_id=profile.id
        )
        assert snap2_res["snapshot_version"] == 2
        assert snap2_res["snapshot_hash"] is not None

        # Verify snapshots in DB
        snaps = (
            db.query(FinancialStatementSnapshot)
            .filter(FinancialStatementSnapshot.profile_id == profile.id)
            .order_by(FinancialStatementSnapshot.version.asc())
            .all()
        )
        assert len(snaps) == 2
        assert snaps[0].version == 1
        assert snaps[1].version == 2
        assert snaps[0].snapshot_hash == hash1

        # Test Export CSV
        csv_report = FSService.generate_export_report_csv(
            db=db, user_id=default_test_user.id, profile_id=profile.id
        )
        assert "FINANCIAL STATEMENTS — ACCOUNTANT REVIEW REQUIRED" in csv_report
        assert "NOT A STATUTORY SUBMISSION" in csv_report
        assert "Zion_TB_2024.xlsx" in csv_report
        assert hash1 in csv_report or snaps[1].snapshot_hash in csv_report

    finally:
        db.close()


def test_approval_safety_blocked_when_unbalanced(default_test_user):
    db: Session = SessionLocal()
    try:
        p_in = FSProfileCreate(
            entity_name=f"Flawed Entity {random.randint(10000, 99999)}",
            financial_year="2023-24",
            reporting_period="ANNUAL",
            framework="SCHEDULE_III",
        )
        profile = FSService.get_or_create_profile(db=db, user_id=default_test_user.id, profile_in=p_in)

        # Add unbalanced TB entry
        FSService.add_trial_balance_entries(
            db=db,
            user_id=default_test_user.id,
            profile_id=profile.id,
            entries=[
                TrialBalanceEntryCreate(
                    account_code="1001",
                    account_name="Asset One",
                    account_category="ASSET",
                    debit_amount=Decimal("100000.00"),
                    credit_amount=Decimal("0.00"),
                ),
                TrialBalanceEntryCreate(
                    account_code="2001",
                    account_name="Liability One",
                    account_category="LIABILITY",
                    debit_amount=Decimal("0.00"),
                    credit_amount=Decimal("60000.00"),  # Out of balance by 40,000!
                ),
            ],
        )

        # Run calculation
        FSService.calculate_and_snapshot(
            db=db, user_id=default_test_user.id, profile_id=profile.id
        )

        # Attempt to transition to APPROVED - MUST FAIL with 400
        with pytest.raises(Exception) as exc_info:
            FSService.transition_status(
                db=db,
                user_id=default_test_user.id,
                profile_id=profile.id,
                target_status="APPROVED",
                notes="Attempting signoff without balancing",
            )
        err_msg = str(exc_info.value).lower()
        assert "cannot approve" in err_msg or "unbalanced" in err_msg or "critical" in err_msg

    finally:
        db.close()
