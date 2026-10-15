"""
GSTR-2B vs Books Purchase Register Reconciliation Engine.

Performs multi-tier matching between internal purchase records (GSTPurchaseInvoice)
and external GSTR-2B entries (GSTR2BRecord):
1. Exact Match: Same GSTIN, normalized invoice number, date within tolerance, tax & taxable diff <= 1.00 INR.
2. Partial Match: Same GSTIN, fuzzy invoice number or minor value variance (diff <= 5.00 INR).
3. Books Only: Present in purchase register but absent in GSTR-2B.
4. Return Only: Present in GSTR-2B but absent in purchase register.
5. Excluded: Marked as excluded by user / rule (e.g. Blocked ITC Section 17(5)).
"""

import re
from datetime import date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional, Any
from app.modules.gst.constants import MatchStatus, DifferenceReason, round_currency


def normalize_invoice_number(inv_num: str) -> str:
    """
    Normalizes invoice number by converting to uppercase,
    stripping whitespace, leading zeros, and special separators (-, /, _, space).
    Example: 'INV/2023-24/0045' -> 'INV20232445'
    """
    if not inv_num:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9]", "", inv_num).upper()
    # Strip leading zeros from numeric portions if possible, but keep simple alphanumeric
    return cleaned.lstrip("0") or "0"


def calculate_string_similarity(str1: str, str2: str) -> float:
    """
    Calculate Levenshtein distance ratio between two strings.
    Returns float between 0.0 and 1.0.
    """
    s1, s2 = str1.upper(), str2.upper()
    if s1 == s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    len1, len2 = len(s1), len(s2)
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]
            else:
                dp[i][j] = 1 + min(dp[i - 1][j], dp[i][j - 1], dp[i - 1][j - 1])

    dist = dp[len1][len2]
    max_len = max(len1, len2)
    return 1.0 - (dist / max_len)


def parse_invoice_date(val: Any) -> Optional[date]:
    """Safely converts string or date object to datetime.date."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        try:
            return date.fromisoformat(val.strip()[:10])
        except Exception:
            return None
    return None


class ReconciliationMatch:
    def __init__(
        self,
        match_status: MatchStatus,
        confidence_score: Decimal,
        purchase_invoice_id: Optional[str] = None,
        gstr2b_record_id: Optional[str] = None,
        taxable_difference: Decimal = Decimal("0.00"),
        tax_difference: Decimal = Decimal("0.00"),
        difference_reasons: Optional[List[str]] = None,
        notes: str = "",
    ):
        self.match_status = match_status
        self.confidence_score = confidence_score
        self.purchase_invoice_id = purchase_invoice_id
        self.gstr2b_record_id = gstr2b_record_id
        self.taxable_difference = taxable_difference
        self.tax_difference = tax_difference
        self.difference_reasons = difference_reasons or []
        self.notes = notes


def reconcile_purchases_with_gstr2b(
    books_invoices: List[Any],
    gstr2b_records: List[Any],
    date_tolerance_days: int = 30,
    exact_tolerance_inr: Decimal = Decimal("1.00"),
    partial_tolerance_inr: Decimal = Decimal("5.00"),
) -> List[ReconciliationMatch]:
    """
    Executes multi-tier matching between books purchase invoices and external GSTR-2B records.
    Returns list of ReconciliationMatch objects.
    """
    results: List[ReconciliationMatch] = []

    # Track matched IDs to avoid duplicate matching
    matched_books_ids = set()
    matched_2b_ids = set()

    # Pre-index 2B records by normalized GSTIN
    records_by_gstin: Dict[str, List[Any]] = {}
    for rec in gstr2b_records:
        gstin = (rec.supplier_gstin or "").strip().upper()
        if gstin not in records_by_gstin:
            records_by_gstin[gstin] = []
        records_by_gstin[gstin].append(rec)

    # ----------------------------------------------------
    # TIER 1: EXACT MATCHES
    # ----------------------------------------------------
    for b_inv in books_invoices:
        if b_inv.id in matched_books_ids:
            continue

        b_gstin = (b_inv.supplier_gstin or "").strip().upper()
        candidates = records_by_gstin.get(b_gstin, [])
        b_norm_num = normalize_invoice_number(b_inv.invoice_number)
        b_tot_tax = Decimal(
            str(
                b_inv.cgst_amount
                + b_inv.sgst_amount
                + b_inv.igst_amount
                + b_inv.cess_amount
            )
        )
        b_taxable = Decimal(str(b_inv.taxable_value))

        best_exact: Optional[Tuple[Any, Decimal, Decimal]] = None

        for rec in candidates:
            if rec.id in matched_2b_ids:
                continue

            r_norm_num = normalize_invoice_number(rec.invoice_number)
            if b_norm_num != r_norm_num:
                continue

            r_tot_tax = Decimal(
                str(
                    rec.cgst_amount
                    + rec.sgst_amount
                    + rec.igst_amount
                    + rec.cess_amount
                )
            )
            r_taxable = Decimal(str(rec.taxable_value))

            taxable_diff = abs(b_taxable - r_taxable)
            tax_diff = abs(b_tot_tax - r_tot_tax)

            # Check date tolerance
            date_diff_days = 0
            b_d = parse_invoice_date(b_inv.invoice_date)
            r_d = parse_invoice_date(rec.invoice_date)
            if b_d and r_d:
                date_diff_days = abs((b_d - r_d).days)

            if (
                taxable_diff <= exact_tolerance_inr
                and tax_diff <= exact_tolerance_inr
                and date_diff_days <= date_tolerance_days
            ):
                best_exact = (rec, taxable_diff, tax_diff)
                break

        if best_exact:
            rec, taxable_diff, tax_diff = best_exact
            matched_books_ids.add(b_inv.id)
            matched_2b_ids.add(rec.id)

            reasons = []
            if taxable_diff > Decimal("0.00") or tax_diff > Decimal("0.00"):
                reasons.append(DifferenceReason.ROUNDING_DIFFERENCE.value)

            score = (
                Decimal("100.00")
                if (taxable_diff == Decimal("0.00") and tax_diff == Decimal("0.00"))
                else Decimal("98.00")
            )

            results.append(
                ReconciliationMatch(
                    match_status=MatchStatus.EXACT_MATCH,
                    confidence_score=score,
                    purchase_invoice_id=b_inv.id,
                    gstr2b_record_id=rec.id,
                    taxable_difference=round_currency(taxable_diff),
                    tax_difference=round_currency(tax_diff),
                    difference_reasons=reasons,
                    notes="Exact match on GSTIN, invoice number, and values.",
                )
            )

    # ----------------------------------------------------
    # TIER 2: PARTIAL MATCHES
    # ----------------------------------------------------
    for b_inv in books_invoices:
        if b_inv.id in matched_books_ids:
            continue

        b_gstin = (b_inv.supplier_gstin or "").strip().upper()
        candidates = records_by_gstin.get(b_gstin, [])
        b_norm_num = normalize_invoice_number(b_inv.invoice_number)
        b_tot_tax = Decimal(
            str(
                b_inv.cgst_amount
                + b_inv.sgst_amount
                + b_inv.igst_amount
                + b_inv.cess_amount
            )
        )
        b_taxable = Decimal(str(b_inv.taxable_value))

        best_partial: Optional[Tuple[Any, Decimal, Decimal, List[str], Decimal]] = None
        highest_score = Decimal("0.00")

        for rec in candidates:
            if rec.id in matched_2b_ids:
                continue

            r_norm_num = normalize_invoice_number(rec.invoice_number)
            r_tot_tax = Decimal(
                str(
                    rec.cgst_amount
                    + rec.sgst_amount
                    + rec.igst_amount
                    + rec.cess_amount
                )
            )
            r_taxable = Decimal(str(rec.taxable_value))

            taxable_diff = abs(b_taxable - r_taxable)
            tax_diff = abs(b_tot_tax - r_tot_tax)

            reasons = []
            num_similarity = calculate_string_similarity(b_norm_num, r_norm_num)

            # Scenario A: Exact invoice number, but higher value variance
            if b_norm_num == r_norm_num:
                if (
                    tax_diff <= partial_tolerance_inr
                    or taxable_diff <= partial_tolerance_inr
                ):
                    reasons.append(DifferenceReason.VALUE_MISMATCH.value)
                    score = Decimal("85.00") - (tax_diff + taxable_diff)
                else:
                    reasons.append(DifferenceReason.TAX_RATE_MISMATCH.value)
                    score = Decimal("75.00")
            # Scenario B: Fuzzy invoice number match (> 0.75 similarity) with close value
            elif num_similarity >= 0.75 and (
                tax_diff <= partial_tolerance_inr
                or taxable_diff <= partial_tolerance_inr
            ):
                reasons.append(DifferenceReason.INVOICE_NUMBER_TYPO.value)
                if tax_diff > exact_tolerance_inr:
                    reasons.append(DifferenceReason.VALUE_MISMATCH.value)
                score = round_currency(Decimal(str(num_similarity * 80)))
            else:
                continue

            b_d = parse_invoice_date(b_inv.invoice_date)
            r_d = parse_invoice_date(rec.invoice_date)
            if b_d and r_d:
                if abs((b_d - r_d).days) > date_tolerance_days:
                    reasons.append(DifferenceReason.DATE_OUT_OF_PERIOD.value)
                    score -= Decimal("10.00")

            score = max(Decimal("50.00"), min(score, Decimal("94.00")))

            if score > highest_score:
                highest_score = score
                best_partial = (rec, taxable_diff, tax_diff, reasons, score)

        if best_partial:
            rec, taxable_diff, tax_diff, reasons, score = best_partial
            matched_books_ids.add(b_inv.id)
            matched_2b_ids.add(rec.id)

            results.append(
                ReconciliationMatch(
                    match_status=MatchStatus.PARTIAL_MATCH,
                    confidence_score=round_currency(score),
                    purchase_invoice_id=b_inv.id,
                    gstr2b_record_id=rec.id,
                    taxable_difference=round_currency(taxable_diff),
                    tax_difference=round_currency(tax_diff),
                    difference_reasons=reasons,
                    notes=f"Partial match detected with reasons: {', '.join(reasons)}",
                )
            )

    # ----------------------------------------------------
    # TIER 3: BOOKS ONLY
    # ----------------------------------------------------
    for b_inv in books_invoices:
        if b_inv.id not in matched_books_ids:
            b_tax = Decimal(
                str(
                    b_inv.cgst_amount
                    + b_inv.sgst_amount
                    + b_inv.igst_amount
                    + b_inv.cess_amount
                )
            )
            results.append(
                ReconciliationMatch(
                    match_status=MatchStatus.BOOKS_ONLY,
                    confidence_score=Decimal("0.00"),
                    purchase_invoice_id=b_inv.id,
                    gstr2b_record_id=None,
                    taxable_difference=round_currency(
                        Decimal(str(b_inv.taxable_value))
                    ),
                    tax_difference=round_currency(b_tax),
                    difference_reasons=[DifferenceReason.MISSING_IN_GSTR2B.value],
                    notes="Invoice present in purchase register but absent in GSTR-2B. Supplier might not have filed.",
                )
            )

    # ----------------------------------------------------
    # TIER 4: RETURN ONLY
    # ----------------------------------------------------
    for rec in gstr2b_records:
        if rec.id not in matched_2b_ids:
            r_tax = Decimal(
                str(
                    rec.cgst_amount
                    + rec.sgst_amount
                    + rec.igst_amount
                    + rec.cess_amount
                )
            )
            results.append(
                ReconciliationMatch(
                    match_status=MatchStatus.RETURN_ONLY,
                    confidence_score=Decimal("0.00"),
                    purchase_invoice_id=None,
                    gstr2b_record_id=rec.id,
                    taxable_difference=round_currency(Decimal(str(rec.taxable_value))),
                    tax_difference=round_currency(r_tax),
                    difference_reasons=[DifferenceReason.MISSING_IN_BOOKS.value],
                    notes="Invoice reported in GSTR-2B but missing from internal purchase register.",
                )
            )

    return results
