from decimal import Decimal
from typing import List, Dict, Any, Optional
from app.modules.financial_statements.models import (
    FinancialStatementProfile,
    TrialBalanceEntry,
    BalanceSheetLine,
    ProfitLossLine,
    CashFlowLine,
    FinancialStatementFinding,
)
from app.modules.financial_statements.calculator import FSCalculator


class FSValidator:
    """
    Deterministic rule-based validator for Financial Statements.
    Generates structured findings with distinct possible_cause vs proven_cause,
    evidence, and provenance links for accountant Review Center.
    """

    @classmethod
    def validate_profile(
        cls,
        profile: FinancialStatementProfile,
        tb_entries: List[TrialBalanceEntry],
        bs_lines: List[BalanceSheetLine],
        pl_lines: List[ProfitLossLine],
        cf_lines: List[CashFlowLine],
        tb_calc: Dict[str, Any],
        bs_calc: Dict[str, Any],
        pl_calc: Dict[str, Any],
        cf_calc: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        findings: List[Dict[str, Any]] = []

        # 1. Check if source data is completely empty
        if not tb_entries and not bs_lines and not pl_lines:
            findings.append({
                "finding_type": "SOURCE_DATA_INCOMPLETE",
                "severity": "HIGH",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "No Financial Statement Source Data Found",
                "description": f"Profile for '{profile.entity_name}' ({profile.financial_year}) has no Trial Balance entries, Balance Sheet lines, or Profit & Loss lines.",
                "expected": Decimal("1.00"),
                "actual": Decimal("0.00"),
                "variance": Decimal("1.00"),
                "possible_cause": "No ledger or financial statements workbook has been ingested for this entity.",
                "proven_cause": "Zero entries found in trial balance, balance sheet, and profit & loss datasets.",
                "evidence": f"tb_entries={len(tb_entries)}, bs_lines={len(bs_lines)}, pl_lines={len(pl_lines)}",
                "source_document": None,
                "source_sheet": None,
                "source_row": None,
                "source_cell": None,
            })
            return findings

        # 2. Rule: TRIAL_BALANCE_UNBALANCED
        if tb_entries and not tb_calc.get("is_balanced", True):
            diff = tb_calc.get("difference", Decimal("0.00"))
            findings.append({
                "finding_type": "TRIAL_BALANCE_UNBALANCED",
                "severity": "CRITICAL",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "Trial Balance Unbalanced: Debits and Credits Mismatch",
                "description": (
                    f"Total debits (₹{tb_calc['total_debit']:,.2f}) do not equal total credits "
                    f"(₹{tb_calc['total_credit']:,.2f}). Difference: ₹{diff:,.2f}."
                ),
                "expected": tb_calc["total_debit"],
                "actual": tb_calc["total_credit"],
                "variance": abs(diff),
                "possible_cause": (
                    "Omitted opening balance, single-sided journal adjustment, or transcription "
                    "error in imported ledger."
                ),
                "proven_cause": (
                    f"Aggregate arithmetic mismatch of ₹{diff:,.2f} between debit sum and credit sum."
                ),
                "evidence": (
                    f"Total Debits: ₹{tb_calc['total_debit']:,.2f} | Total Credits: ₹{tb_calc['total_credit']:,.2f} "
                    f"across {tb_calc.get('entries_count', len(tb_entries))} ledger accounts."
                ),
                "source_document": tb_entries[0].source_document if tb_entries else None,
                "source_sheet": tb_entries[0].source_sheet if tb_entries else None,
                "source_row": None,
                "source_cell": None,
            })

        # 3. Rule: BALANCE_SHEET_MISMATCH
        if bs_lines and not bs_calc.get("is_balanced", True):
            bs_diff = bs_calc.get("balance_difference", Decimal("0.00"))
            findings.append({
                "finding_type": "BALANCE_SHEET_MISMATCH",
                "severity": "CRITICAL",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "Balance Sheet Schedule III Does Not Balance",
                "description": (
                    f"Total Assets (₹{bs_calc['total_assets']:,.2f}) do not equal Total Equity & Liabilities "
                    f"(₹{bs_calc['total_equity_and_liabilities']:,.2f}). Out of balance by ₹{bs_diff:,.2f}."
                ),
                "expected": bs_calc["total_assets"],
                "actual": bs_calc["total_equity_and_liabilities"],
                "variance": abs(bs_diff),
                "possible_cause": (
                    "Current year profit/loss has not been transferred to Reserves & Surplus, or an asset/liability "
                    "line item is missing classification under Schedule III."
                ),
                "proven_cause": (
                    f"Schedule III equality violated: Assets ₹{bs_calc['total_assets']:,.2f} != "
                    f"Equity & Liab ₹{bs_calc['total_equity_and_liabilities']:,.2f} (Delta: ₹{bs_diff:,.2f})."
                ),
                "evidence": (
                    f"Non-Current Assets: ₹{bs_calc['total_non_current_assets']:,.2f}, "
                    f"Current Assets: ₹{bs_calc['total_current_assets']:,.2f} | "
                    f"Equity: ₹{bs_calc['total_equity']:,.2f}, "
                    f"Non-Current Liab: ₹{bs_calc['total_non_current_liabilities']:,.2f}, "
                    f"Current Liab: ₹{bs_calc['total_current_liabilities']:,.2f}."
                ),
                "source_document": bs_lines[0].source_document if bs_lines else None,
                "source_sheet": bs_lines[0].source_sheet if bs_lines else None,
                "source_row": None,
                "source_cell": None,
            })

        # 4. Rule: MISSING_REVENUE
        if pl_lines and pl_calc.get("total_revenue", Decimal("0.00")) <= Decimal("0.00"):
            findings.append({
                "finding_type": "MISSING_REVENUE",
                "severity": "HIGH",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "No Revenue Recorded in Profit & Loss",
                "description": "Profit & Loss statement reports ₹0.00 in Revenue from Operations and Other Income.",
                "expected": Decimal("0.01"),
                "actual": Decimal("0.00"),
                "variance": Decimal("0.00"),
                "possible_cause": "Operating revenue accounts may be misclassified as liabilities or omitted from the trial balance.",
                "proven_cause": None,  # Not proven until verified by accountant
                "evidence": f"Total revenue evaluated as ₹0.00 across {len(pl_lines)} P&L line items.",
                "source_document": pl_lines[0].source_document if pl_lines else None,
                "source_sheet": pl_lines[0].source_sheet if pl_lines else None,
                "source_row": None,
                "source_cell": None,
            })

        # 5. Rule: MISSING_EXPENSE
        if pl_lines and pl_calc.get("total_revenue", Decimal("0.00")) > Decimal("0.00") and pl_calc.get("total_expenses", Decimal("0.00")) <= Decimal("0.00"):
            findings.append({
                "finding_type": "MISSING_EXPENSE",
                "severity": "HIGH",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "Revenue Reported Without Any Recorded Expenses",
                "description": (
                    f"Entity recorded revenue of ₹{pl_calc['total_revenue']:,.2f} but reports ₹0.00 in "
                    f"operating expenses, employee costs, or cost of materials."
                ),
                "expected": Decimal("0.01"),
                "actual": Decimal("0.00"),
                "variance": Decimal("0.00"),
                "possible_cause": "Expense accounts were not mapped or expense schedule was omitted from import.",
                "proven_cause": None,
                "evidence": f"Total Expenses: ₹0.00 vs Total Revenue: ₹{pl_calc['total_revenue']:,.2f}.",
                "source_document": pl_lines[0].source_document if pl_lines else None,
                "source_sheet": pl_lines[0].source_sheet if pl_lines else None,
                "source_row": None,
                "source_cell": None,
            })

        # 6. Rule: P_AND_L_FORMULA_MISMATCH
        if pl_lines:
            expected_pbt = pl_calc["total_revenue"] - pl_calc["total_expenses"]
            expected_pat = expected_pbt - pl_calc["tax_expense"]
            pbt_diff = abs(pl_calc["profit_before_tax"] - expected_pbt)
            pat_diff = abs(pl_calc["profit_after_tax"] - expected_pat)
            if pbt_diff > Decimal("0.01") or pat_diff > Decimal("0.01"):
                findings.append({
                    "finding_type": "P_AND_L_FORMULA_MISMATCH",
                    "severity": "HIGH",
                    "status": "REVIEW_REQUIRED",
                    "category": "FINANCIAL_STATEMENTS",
                    "title": "Profit & Loss Calculation Arithmetic Mismatch",
                    "description": (
                        f"Calculated PBT/PAT does not match Revenue minus Expenses minus Taxes. "
                        f"Expected PAT: ₹{expected_pat:,.2f}, Actual PAT: ₹{pl_calc['profit_after_tax']:,.2f}."
                    ),
                    "expected": expected_pat,
                    "actual": pl_calc["profit_after_tax"],
                    "variance": pat_diff,
                    "possible_cause": "Formulas or manual overrides in source P&L schedule contain mathematical inconsistencies.",
                    "proven_cause": f"Arithmetic divergence of ₹{pat_diff:,.2f} detected in P&L aggregation.",
                    "evidence": (
                        f"Revenue: ₹{pl_calc['total_revenue']:,.2f}, Expenses: ₹{pl_calc['total_expenses']:,.2f}, "
                        f"Tax: ₹{pl_calc['tax_expense']:,.2f}."
                    ),
                    "source_document": pl_lines[0].source_document if pl_lines else None,
                    "source_sheet": pl_lines[0].source_sheet if pl_lines else None,
                    "source_row": None,
                    "source_cell": None,
                })

        # 7. Rule: CASH_FLOW_MISMATCH
        if cf_lines and cf_calc.get("balance_sheet_cash") is not None and not cf_calc.get("cash_matches_balance_sheet", True):
            c_diff = cf_calc.get("cash_variance", Decimal("0.00"))
            findings.append({
                "finding_type": "CASH_FLOW_MISMATCH",
                "severity": "HIGH",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "Cash Flow Closing Cash Does Not Match Balance Sheet",
                "description": (
                    f"Cash Flow closing cash of ₹{cf_calc['closing_cash']:,.2f} diverges from Balance Sheet "
                    f"Cash & Bank of ₹{cf_calc['balance_sheet_cash']:,.2f}. Variance: ₹{c_diff:,.2f}."
                ),
                "expected": cf_calc["balance_sheet_cash"],
                "actual": cf_calc["closing_cash"],
                "variance": abs(c_diff),
                "possible_cause": (
                    "Unclassified cash movement, missing financing/investing activity, or non-cash "
                    "transactions improperly included in Cash Flow."
                ),
                "proven_cause": f"Difference of ₹{c_diff:,.2f} between Cash Flow closing position and Balance Sheet Cash & Bank.",
                "evidence": (
                    f"Opening Cash: ₹{cf_calc['opening_cash']:,.2f}, Operating: ₹{cf_calc['net_cash_operating']:,.2f}, "
                    f"Investing: ₹{cf_calc['net_cash_investing']:,.2f}, Financing: ₹{cf_calc['net_cash_financing']:,.2f}."
                ),
                "source_document": cf_lines[0].source_document if cf_lines else None,
                "source_sheet": cf_lines[0].source_sheet if cf_lines else None,
                "source_row": None,
                "source_cell": None,
            })

        # 8. Rule: MISSING_SUPPORTING_DOCUMENT
        # Check if lines have zero source document provenance
        unproven_tb = sum(1 for e in tb_entries if not e.source_document)
        unproven_bs = sum(1 for b in bs_lines if not b.source_document)
        unproven_pl = sum(1 for p in pl_lines if not p.source_document)
        total_unproven = unproven_tb + unproven_bs + unproven_pl

        if total_unproven > 0 and (len(tb_entries) + len(bs_lines) + len(pl_lines)) > 0:
            findings.append({
                "finding_type": "MISSING_SUPPORTING_DOCUMENT",
                "severity": "LOW",
                "status": "REVIEW_REQUIRED",
                "category": "FINANCIAL_STATEMENTS",
                "title": "Entries Detected Without Direct Source Document Link",
                "description": (
                    f"{total_unproven} financial statement entries lack direct reference to an immutable "
                    "uploaded document or file row."
                ),
                "expected": Decimal("0.00"),
                "actual": Decimal(str(total_unproven)),
                "variance": Decimal(str(total_unproven)),
                "possible_cause": "Manual journal adjustments or system-generated summary lines.",
                "proven_cause": None,
                "evidence": f"Unproven lines: TB ({unproven_tb}), BS ({unproven_bs}), PL ({unproven_pl}).",
                "source_document": None,
                "source_sheet": None,
                "source_row": None,
                "source_cell": None,
            })

        return findings
