from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List


class ITRCalculator:
    """
    Deterministic Indian Income Tax Calculation Engine.
    Implements statutory rules for:
    - Chapter IV Heads of Income
    - Chapter VI-A Deductions
    - Old Regime vs New Regime (Section 115BAC)
    - Section 87A Rebate
    - Section 288A Rounding
    - Health & Education Cess @ 4%
    - Tax Credits (TDS, TCS, Advance Tax, Self Assessment)
    """

    @staticmethod
    def round_currency(val: Decimal) -> Decimal:
        return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def round_to_nearest_10(val: Decimal) -> Decimal:
        """Section 288A: Total income rounded to the nearest multiple of ten rupees."""
        remainder = val % Decimal("10")
        if remainder >= Decimal("5"):
            return (val - remainder + Decimal("10")).quantize(Decimal("0.01"))
        return (val - remainder).quantize(Decimal("0.01"))

    @classmethod
    def calculate_tax(
        cls,
        regime: str,
        assessment_year: str,
        gross_salary: Decimal,
        house_property: Decimal,
        business_profession: Decimal,
        capital_gains: Decimal,
        other_sources: Decimal,
        verified_deductions_80c: Decimal,
        verified_deductions_80d: Decimal,
        verified_deductions_80ccd_1b: Decimal,
        other_verified_deductions: Decimal,
        tds_total: Decimal,
        tcs_total: Decimal,
        advance_tax_total: Decimal,
        self_assessment_tax_total: Decimal,
    ) -> Dict[str, Any]:
        regime_norm = regime.upper().strip()
        is_new_regime = regime_norm == "NEW"

        # 1. Salary Standard Deduction
        standard_deduction = Decimal("0.00")
        if gross_salary > Decimal("0.00"):
            if is_new_regime:
                # AY 2025-26 enhanced standard deduction is ₹75,000; AY 2024-25 is ₹50,000
                cap = Decimal("75000.00") if assessment_year == "2025-26" else Decimal("50000.00")
                standard_deduction = min(gross_salary, cap)
            else:
                standard_deduction = min(gross_salary, Decimal("50000.00"))

        net_salary = max(Decimal("0.00"), gross_salary - standard_deduction)

        # 2. House Property Income (Loss capped under Old Regime at ₹2L; 0 for self-occupied in New Regime)
        hp_income = house_property
        if hp_income < Decimal("0.00"):
            if is_new_regime:
                hp_income = Decimal("0.00")  # No loss set-off against other heads under 115BAC
            else:
                hp_income = max(hp_income, Decimal("-200000.00"))

        # 3. Gross Total Income
        gross_total_income = (
            net_salary
            + hp_income
            + max(Decimal("0.00"), business_profession)
            + max(Decimal("0.00"), capital_gains)
            + max(Decimal("0.00"), other_sources)
        )
        gross_total_income = cls.round_currency(max(Decimal("0.00"), gross_total_income))

        # 4. Chapter VI-A Deductions
        total_deductions = Decimal("0.00")
        deduction_breakdown = {}

        if not is_new_regime:
            # 80C capped at ₹1,50,000
            eligible_80c = min(verified_deductions_80c, Decimal("150000.00"))
            # 80CCD(1B) additional NPS capped at ₹50,000
            eligible_80ccd = min(verified_deductions_80ccd_1b, Decimal("50000.00"))
            # 80D capped at ₹25,000 (general non-senior)
            eligible_80d = min(verified_deductions_80d, Decimal("25000.00"))
            eligible_other = max(Decimal("0.00"), other_verified_deductions)

            subtotal_deductions = eligible_80c + eligible_80ccd + eligible_80d + eligible_other
            total_deductions = min(subtotal_deductions, gross_total_income)

            deduction_breakdown = {
                "section_80c": eligible_80c,
                "section_80ccd_1b": eligible_80ccd,
                "section_80d": eligible_80d,
                "other_sections": eligible_other,
                "total_claimed_eligible": total_deductions,
            }
        else:
            # Under Section 115BAC, Chapter VI-A deductions (except 80CCD(2) employer NPS) are disallowed
            total_deductions = Decimal("0.00")
            deduction_breakdown = {
                "disallowed_under_115bac": True,
                "total_claimed_eligible": Decimal("0.00"),
            }

        # 5. Total Taxable Income
        total_taxable_income = max(Decimal("0.00"), gross_total_income - total_deductions)
        total_taxable_income = cls.round_to_nearest_10(total_taxable_income)

        # 6. Basic Tax by Regime Slabs
        basic_tax = Decimal("0.00")
        slab_breakdown: List[Dict[str, Any]] = []

        if is_new_regime:
            # Section 115BAC Slabs (AY 2024-25 / 2025-26)
            # 0 to 3,00,000: Nil
            # 3,00,001 to 6,00,000: 5%
            # 6,00,001 to 9,00,000: 10%
            # 9,00,001 to 12,00,000: 15%
            # 12,00,001 to 15,00,000: 20%
            # Above 15,00,000: 30%
            rem = total_taxable_income

            # Slab 1: Up to 3L
            s1 = min(rem, Decimal("300000.00"))
            slab_breakdown.append({"slab": "Up to ₹3,00,000", "rate": "0%", "taxable": s1, "tax": Decimal("0.00")})
            rem = max(Decimal("0.00"), rem - Decimal("300000.00"))

            # Slab 2: 3L to 6L (5%)
            if rem > Decimal("0.00"):
                s2 = min(rem, Decimal("300000.00"))
                t2 = s2 * Decimal("0.05")
                basic_tax += t2
                slab_breakdown.append({"slab": "₹3,00,001 to ₹6,00,000", "rate": "5%", "taxable": s2, "tax": t2})
                rem = max(Decimal("0.00"), rem - Decimal("300000.00"))

            # Slab 3: 6L to 9L (10%)
            if rem > Decimal("0.00"):
                s3 = min(rem, Decimal("300000.00"))
                t3 = s3 * Decimal("0.10")
                basic_tax += t3
                slab_breakdown.append({"slab": "₹6,00,001 to ₹9,00,000", "rate": "10%", "taxable": s3, "tax": t3})
                rem = max(Decimal("0.00"), rem - Decimal("300000.00"))

            # Slab 4: 9L to 12L (15%)
            if rem > Decimal("0.00"):
                s4 = min(rem, Decimal("300000.00"))
                t4 = s4 * Decimal("0.15")
                basic_tax += t4
                slab_breakdown.append({"slab": "₹9,00,001 to ₹12,00,000", "rate": "15%", "taxable": s4, "tax": t4})
                rem = max(Decimal("0.00"), rem - Decimal("300000.00"))

            # Slab 5: 12L to 15L (20%)
            if rem > Decimal("0.00"):
                s5 = min(rem, Decimal("300000.00"))
                t5 = s5 * Decimal("0.20")
                basic_tax += t5
                slab_breakdown.append({"slab": "₹12,00,001 to ₹15,00,000", "rate": "20%", "taxable": s5, "tax": t5})
                rem = max(Decimal("0.00"), rem - Decimal("300000.00"))

            # Slab 6: Above 15L (30%)
            if rem > Decimal("0.00"):
                t6 = rem * Decimal("0.30")
                basic_tax += t6
                slab_breakdown.append({"slab": "Above ₹15,00,000", "rate": "30%", "taxable": rem, "tax": t6})

            # Section 87A Rebate for New Regime: If taxable income <= ₹7,00,000, 100% tax rebate up to ₹25,000
            rebate_87a = Decimal("0.00")
            if total_taxable_income <= Decimal("700000.00"):
                rebate_87a = min(basic_tax, Decimal("25000.00"))
            elif total_taxable_income > Decimal("700000.00"):
                # Marginal relief under Sec 87A: Tax payable cannot exceed income exceeding ₹7,00,000
                excess_income = total_taxable_income - Decimal("700000.00")
                if basic_tax > excess_income:
                    rebate_87a = basic_tax - excess_income

        else:
            # Old Regime Slabs (Individual < 60 years)
            # 0 to 2,50,000: Nil
            # 2,50,001 to 5,00,000: 5%
            # 5,00,001 to 10,00,000: 20%
            # Above 10,00,000: 30%
            rem = total_taxable_income

            # Slab 1: Up to 2.5L
            s1 = min(rem, Decimal("250000.00"))
            slab_breakdown.append({"slab": "Up to ₹2,50,000", "rate": "0%", "taxable": s1, "tax": Decimal("0.00")})
            rem = max(Decimal("0.00"), rem - Decimal("250000.00"))

            # Slab 2: 2.5L to 5L (5%)
            if rem > Decimal("0.00"):
                s2 = min(rem, Decimal("250000.00"))
                t2 = s2 * Decimal("0.05")
                basic_tax += t2
                slab_breakdown.append({"slab": "₹2,50,001 to ₹5,00,000", "rate": "5%", "taxable": s2, "tax": t2})
                rem = max(Decimal("0.00"), rem - Decimal("250000.00"))

            # Slab 3: 5L to 10L (20%)
            if rem > Decimal("0.00"):
                s3 = min(rem, Decimal("500000.00"))
                t3 = s3 * Decimal("0.20")
                basic_tax += t3
                slab_breakdown.append({"slab": "₹5,00,001 to ₹10,00,000", "rate": "20%", "taxable": s3, "tax": t3})
                rem = max(Decimal("0.00"), rem - Decimal("500000.00"))

            # Slab 4: Above 10L (30%)
            if rem > Decimal("0.00"):
                t4 = rem * Decimal("0.30")
                basic_tax += t4
                slab_breakdown.append({"slab": "Above ₹10,00,000", "rate": "30%", "taxable": rem, "tax": t4})

            # Section 87A Rebate for Old Regime: If taxable income <= ₹5,00,000, 100% tax rebate up to ₹12,500
            rebate_87a = Decimal("0.00")
            if total_taxable_income <= Decimal("500000.00"):
                rebate_87a = min(basic_tax, Decimal("12500.00"))

        basic_tax = cls.round_currency(basic_tax)
        rebate_87a = cls.round_currency(rebate_87a)
        tax_after_rebate = cls.round_currency(max(Decimal("0.00"), basic_tax - rebate_87a))

        # 7. Health & Education Cess @ 4%
        cess_4_pct = cls.round_currency(tax_after_rebate * Decimal("0.04"))
        total_tax_liability = cls.round_to_nearest_10(tax_after_rebate + cess_4_pct)

        # 8. Tax Credits & Net Payable / Refund
        total_taxes_paid = cls.round_currency(
            tds_total + tcs_total + advance_tax_total + self_assessment_tax_total
        )
        net_payable_or_refund = cls.round_currency(total_tax_liability - total_taxes_paid)

        return {
            "regime": regime_norm,
            "gross_salary": cls.round_currency(gross_salary),
            "standard_deduction": cls.round_currency(standard_deduction),
            "net_salary": cls.round_currency(net_salary),
            "house_property_income": cls.round_currency(hp_income),
            "business_profession_income": cls.round_currency(business_profession),
            "capital_gains": cls.round_currency(capital_gains),
            "other_sources_income": cls.round_currency(other_sources),
            "gross_total_income": gross_total_income,
            "total_deductions": cls.round_currency(total_deductions),
            "total_taxable_income": total_taxable_income,
            "basic_tax": basic_tax,
            "rebate_87a": rebate_87a,
            "tax_after_rebate": tax_after_rebate,
            "cess_4_pct": cess_4_pct,
            "total_tax_liability": total_tax_liability,
            "tds_total": cls.round_currency(tds_total),
            "tcs_total": cls.round_currency(tcs_total),
            "advance_tax_total": cls.round_currency(advance_tax_total),
            "self_assessment_tax_total": cls.round_currency(self_assessment_tax_total),
            "total_taxes_paid": total_taxes_paid,
            "net_payable_or_refund": net_payable_or_refund,
            "breakdown": {
                "slab_details": slab_breakdown,
                "deduction_details": deduction_breakdown,
            },
        }
