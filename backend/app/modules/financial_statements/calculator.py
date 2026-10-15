from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional


class FSCalculator:
    """
    Deterministic calculation engine for Indian Schedule III and Ind AS Financial Statements:
    - Trial Balance validation
    - Profit & Loss statement aggregation
    - Balance Sheet Schedule III tally verification
    - Cash Flow statement aggregation & reconciliation against Cash & Bank
    """

    @staticmethod
    def round_currency(val: Decimal) -> Decimal:
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @classmethod
    def calculate_trial_balance(cls, entries: List[Any]) -> Dict[str, Any]:
        total_debit = sum((Decimal(str(e.debit_amount or 0)) for e in entries), Decimal("0.00"))
        total_credit = sum((Decimal(str(e.credit_amount or 0)) for e in entries), Decimal("0.00"))

        total_debit = cls.round_currency(total_debit)
        total_credit = cls.round_currency(total_credit)
        diff = cls.round_currency(total_debit - total_credit)

        return {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "difference": diff,
            "is_balanced": (diff == Decimal("0.00")),
            "entries_count": len(entries),
        }

    @classmethod
    def calculate_profit_loss(cls, lines: List[Any]) -> Dict[str, Any]:
        revenue_ops = Decimal("0.00")
        other_income = Decimal("0.00")
        cost_materials = Decimal("0.00")
        employee_benefits = Decimal("0.00")
        finance_costs = Decimal("0.00")
        depreciation = Decimal("0.00")
        other_expenses = Decimal("0.00")
        tax_expense = Decimal("0.00")

        for line in lines:
            amt = Decimal(str(line.amount or 0))
            cat = (line.category or "").upper().strip()

            if cat in ("REVENUE", "REVENUE_FROM_OPERATIONS", "SALES"):
                revenue_ops += amt
            elif cat in ("OTHER_INCOME", "NON_OPERATING_INCOME"):
                other_income += amt
            elif cat in ("COST_OF_MATERIALS", "RAW_MATERIALS", "COGS", "PURCHASES"):
                cost_materials += amt
            elif cat in ("EMPLOYEE_BENEFITS", "SALARIES_WAGES", "EMPLOYEE_EXPENSES"):
                employee_benefits += amt
            elif cat in ("FINANCE_COSTS", "INTEREST_EXPENSE"):
                finance_costs += amt
            elif cat in ("DEPRECIATION", "AMORTIZATION", "DEPRECIATION_AMORTIZATION"):
                depreciation += amt
            elif cat in ("OTHER_EXPENSES", "ADMIN_EXPENSES", "SELLING_EXPENSES"):
                other_expenses += amt
            elif cat in ("TAX_EXPENSE", "CURRENT_TAX", "DEFERRED_TAX"):
                tax_expense += amt
            else:
                other_expenses += amt

        total_revenue = cls.round_currency(revenue_ops + other_income)
        total_expenses = cls.round_currency(
            cost_materials + employee_benefits + finance_costs + depreciation + other_expenses
        )

        operating_costs = cost_materials + employee_benefits + other_expenses
        ebitda = cls.round_currency(total_revenue - operating_costs)
        pbt = cls.round_currency(total_revenue - total_expenses)
        pat = cls.round_currency(pbt - tax_expense)

        return {
            "revenue_from_operations": cls.round_currency(revenue_ops),
            "other_income": cls.round_currency(other_income),
            "total_revenue": total_revenue,
            "cost_of_materials": cls.round_currency(cost_materials),
            "employee_benefits": cls.round_currency(employee_benefits),
            "finance_costs": cls.round_currency(finance_costs),
            "depreciation": cls.round_currency(depreciation),
            "other_expenses": cls.round_currency(other_expenses),
            "total_expenses": total_expenses,
            "ebitda": ebitda,
            "profit_before_tax": pbt,
            "tax_expense": cls.round_currency(tax_expense),
            "profit_after_tax": pat,
        }

    @classmethod
    def calculate_balance_sheet(cls, lines: List[Any]) -> Dict[str, Any]:
        non_current_assets = Decimal("0.00")
        current_assets = Decimal("0.00")
        equity = Decimal("0.00")
        non_current_liabilities = Decimal("0.00")
        current_liabilities = Decimal("0.00")

        for line in lines:
            amt = Decimal(str(line.amount or 0))
            classification = (line.classification or "").upper().strip()

            if classification == "NON_CURRENT_ASSETS":
                non_current_assets += amt
            elif classification == "CURRENT_ASSETS":
                current_assets += amt
            elif classification == "EQUITY":
                equity += amt
            elif classification == "NON_CURRENT_LIABILITIES":
                non_current_liabilities += amt
            elif classification == "CURRENT_LIABILITIES":
                current_liabilities += amt

        total_assets = cls.round_currency(non_current_assets + current_assets)
        total_equity = cls.round_currency(equity)
        total_liabilities = cls.round_currency(non_current_liabilities + current_liabilities)
        total_equity_and_liabilities = cls.round_currency(total_equity + total_liabilities)

        diff = cls.round_currency(total_assets - total_equity_and_liabilities)
        is_balanced = (diff == Decimal("0.00"))

        return {
            "total_non_current_assets": cls.round_currency(non_current_assets),
            "total_current_assets": cls.round_currency(current_assets),
            "total_assets": total_assets,
            "total_equity": total_equity,
            "total_non_current_liabilities": cls.round_currency(non_current_liabilities),
            "total_current_liabilities": cls.round_currency(current_liabilities),
            "total_liabilities": total_liabilities,
            "total_equity_and_liabilities": total_equity_and_liabilities,
            "balance_difference": diff,
            "is_balanced": is_balanced,
        }

    @classmethod
    def calculate_cash_flow(
        cls,
        lines: List[Any],
        opening_cash: Decimal = Decimal("0.00"),
        balance_sheet_cash: Optional[Decimal] = None,
    ) -> Dict[str, Any]:
        operating = Decimal("0.00")
        investing = Decimal("0.00")
        financing = Decimal("0.00")

        for line in lines:
            amt = Decimal(str(line.amount or 0))
            act = (line.activity_type or "").upper().strip()

            if act == "OPERATING":
                operating += amt
            elif act == "INVESTING":
                investing += amt
            elif act == "FINANCING":
                financing += amt

        net_operating = cls.round_currency(operating)
        net_investing = cls.round_currency(investing)
        net_financing = cls.round_currency(financing)
        net_change = cls.round_currency(net_operating + net_investing + net_financing)
        closing = cls.round_currency(opening_cash + net_change)

        cash_matches_bs = True
        bs_cash_diff = Decimal("0.00")
        if balance_sheet_cash is not None:
            bs_cash_diff = cls.round_currency(closing - balance_sheet_cash)
            cash_matches_bs = (bs_cash_diff == Decimal("0.00"))

        return {
            "net_cash_operating": net_operating,
            "net_cash_investing": net_investing,
            "net_cash_financing": net_financing,
            "net_change_in_cash": net_change,
            "opening_cash": cls.round_currency(opening_cash),
            "closing_cash": closing,
            "balance_sheet_cash": cls.round_currency(balance_sheet_cash) if balance_sheet_cash is not None else None,
            "cash_matches_balance_sheet": cash_matches_bs,
            "cash_variance": bs_cash_diff,
        }
