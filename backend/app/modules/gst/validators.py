import re
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Tuple, Optional, Dict
from app.modules.gst.constants import INDIAN_STATE_CODES, VALID_GST_RATES

# Official GSTIN structure: 2 digits state code + 10 chars PAN + 1 entity num + 1 'Z' + 1 check digit
GSTIN_REGEX = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$")
PERIOD_REGEX = re.compile(r"^(20[1-9][0-9])-(0[1-9]|1[0-2])$")
FINANCIAL_YEAR_REGEX = re.compile(r"^(20[1-9][0-9])-([0-9]{2})$")


def round_currency(val: Decimal) -> Decimal:
    """Rounds a monetary value to two decimal places using standard Indian financial rounding."""
    if not isinstance(val, Decimal):
        val = Decimal(str(val))
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def derive_financial_year(period: str) -> str:
    """Derives standard Indian Financial Year (e.g., '2026-27') from a 'YYYY-MM' period."""
    clean = period.strip()
    year = int(clean[:4])
    month = int(clean[5:7])
    if month >= 4:
        fy_start = year
    else:
        fy_start = year - 1
    fy_end = (fy_start + 1) % 100
    return f"{fy_start}-{fy_end:02d}"


def validate_financial_year_mapping(
    period: str, financial_year: str
) -> Tuple[bool, Optional[str]]:
    """Validates that a filing period matches the statutory Indian Financial Year."""
    is_valid_p, p_err = validate_period_format(period)
    if not is_valid_p:
        return False, p_err

    expected_fy = derive_financial_year(period)
    fy_clean = financial_year.strip()
    if fy_clean != expected_fy:
        return (
            False,
            f"Period '{period}' belongs to FY '{expected_fy}', but '{fy_clean}' was provided.",
        )
    return True, None


def validate_gstin(gstin: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validates the structure and state code of an Indian GSTIN."""
    if not gstin:
        return False, "GSTIN cannot be empty"

    normalized = gstin.strip().upper()
    if len(normalized) != 15:
        return False, f"GSTIN must be exactly 15 characters, got {len(normalized)}"

    if not GSTIN_REGEX.match(normalized):
        return False, "Invalid GSTIN format. Expected format: 22AAAAA0000A1Z5"

    state_code = normalized[:2]
    if state_code not in INDIAN_STATE_CODES:
        return (
            False,
            f"Invalid state code '{state_code}' in GSTIN. Must be between 01-38, 97, 99",
        )

    return True, None


def validate_state_code(state_code: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validates if a 2-digit state code is recognized under Indian GST rules."""
    if not state_code:
        return False, "State code cannot be empty"
    code = state_code.strip().zfill(2)
    if code not in INDIAN_STATE_CODES:
        return False, f"Unrecognized Indian State Code '{code}'"
    return True, None


def validate_tax_rate(rate: Decimal) -> Tuple[bool, Optional[str]]:
    """Validates that the tax rate is an approved GST slab (0, 0.1, 0.25, 1.5, 3, 5, 6, 12, 18, 28)."""
    rate_dec = round_currency(rate)
    # Check if rate matches any standard rate within penny tolerance
    matched = any(
        abs(rate_dec - valid_rate) < Decimal("0.01") for valid_rate in VALID_GST_RATES
    )
    if not matched:
        valid_rates_str = ", ".join(f"{r}%" for r in VALID_GST_RATES)
        return False, f"Invalid GST rate {rate}%. Allowed slabs are: {valid_rates_str}"
    return True, None


def validate_period_format(period: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validates filing period format (YYYY-MM)."""
    if not period:
        return False, "Period cannot be empty"
    period_clean = period.strip()
    if not PERIOD_REGEX.match(period_clean):
        return (
            False,
            f"Invalid period '{period_clean}'. Expected format YYYY-MM (e.g. '2026-09')",
        )
    year = int(period_clean[:4])
    if year < 2017:
        return False, "GST was enacted in July 2017; periods prior to 2017 are invalid."
    return True, None


def calculate_tax_split(
    place_of_supply: str,
    supplier_state_code: Optional[str] = None,
    taxable_value: Decimal = Decimal("0.00"),
    tax_rate: Decimal = Decimal("0.00"),
    cess: Decimal = Decimal("0.00"),
    supplier_state: Optional[str] = None,
) -> dict:
    """Computes exact CGST/SGST (intra-state) or IGST (inter-state) according to GST rules."""
    effective_sup = (supplier_state or supplier_state_code or "").strip().zfill(2)
    taxable = round_currency(taxable_value)
    rate = round_currency(tax_rate)
    cess_amt = round_currency(cess)

    pos = place_of_supply.strip().zfill(2)

    is_intra_state = pos == effective_sup

    if is_intra_state:
        # Half rate for CGST, half for SGST
        half_rate = rate / Decimal("2")
        cgst = round_currency(taxable * (half_rate / Decimal("100")))
        sgst = round_currency(taxable * (half_rate / Decimal("100")))
        igst = Decimal("0.00")
        supply_type = "INTRA_STATE"
    else:
        # Full rate for IGST
        igst = round_currency(taxable * (rate / Decimal("100")))
        cgst = Decimal("0.00")
        sgst = Decimal("0.00")
        supply_type = "INTER_STATE"

    total = taxable + cgst + sgst + igst + cess_amt

    return {
        "supply_type": supply_type,
        "is_interstate": not is_intra_state,
        "cgst_amount": cgst,
        "sgst_amount": sgst,
        "igst_amount": igst,
        "cess_amount": cess_amt,
        "total_amount": total,
    }


def make_issue(
    code: str,
    severity: str,
    field: str,
    message: str,
    suggested_action: str,
) -> Dict[str, str]:
    """Helper to construct structured validation issues."""
    return {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
        "suggested_action": suggested_action,
    }


def validate_invoice_structured(
    place_of_supply: str,
    taxable_value: Decimal,
    tax_rate: Decimal,
    total_amount: Decimal,
    supplier_state_code: Optional[str] = None,
    supplier_state: Optional[str] = None,
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
    igst_amount: Optional[Decimal] = None,
    cgst_amount: Optional[Decimal] = None,
    sgst_amount: Optional[Decimal] = None,
    cess_amount: Optional[Decimal] = None,
    igst: Optional[Decimal] = None,
    cgst: Optional[Decimal] = None,
    sgst: Optional[Decimal] = None,
    cess: Optional[Decimal] = None,
    customer_or_supplier_gstin: Optional[str] = None,
    customer_gstin: Optional[str] = None,
    invoice_type: str = "B2B",
    period: Optional[str] = None,
    original_invoice_number: Optional[str] = None,
    reverse_charge: bool = False,
    **kwargs,
) -> Tuple[bool, List[Dict[str, str]], List[str]]:
    """Comprehensive statutory validation returning (is_valid, structured_issues, error_strings).

    Status values: is_valid (True if zero blocking/error issues)
    Severities: 'BLOCKING', 'ERROR', 'WARNING', 'INFO'
    """
    supplier_state_code = (supplier_state_code or supplier_state or "").strip()
    customer_or_supplier_gstin = (
        customer_or_supplier_gstin or customer_gstin or ""
    ).strip()
    cgst_amount = (
        cgst
        if cgst is not None
        else (cgst_amount if cgst_amount is not None else Decimal("0.00"))
    )
    sgst_amount = (
        sgst
        if sgst is not None
        else (sgst_amount if sgst_amount is not None else Decimal("0.00"))
    )
    igst_amount = (
        igst
        if igst is not None
        else (igst_amount if igst_amount is not None else Decimal("0.00"))
    )
    cess_amount = (
        cess
        if cess is not None
        else (cess_amount if cess_amount is not None else Decimal("0.00"))
    )
    invoice_number = (invoice_number or "").strip()
    invoice_date = (invoice_date or "").strip()

    issues: List[Dict[str, str]] = []
    error_strings: List[str] = []

    # 1. Missing mandatory fields
    if not invoice_number or not invoice_number.strip():
        issue = make_issue(
            code="MISSING_INVOICE_NUMBER",
            severity="BLOCKING",
            field="invoice_number",
            message="Invoice number is mandatory.",
            suggested_action="Provide a unique statutory invoice identifier.",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    if not invoice_date or not invoice_date.strip():
        issue = make_issue(
            code="MISSING_INVOICE_DATE",
            severity="BLOCKING",
            field="invoice_date",
            message="Invoice date is mandatory.",
            suggested_action="Specify invoice issue date in YYYY-MM-DD format.",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    # 2. Date within filing period check
    if period and invoice_date and len(invoice_date) >= 7:
        inv_period = invoice_date[:7]
        if inv_period != period:
            issue = make_issue(
                code="INVOICE_DATE_OUTSIDE_PERIOD",
                severity="WARNING",
                field="invoice_date",
                message=f"Invoice date '{invoice_date}' belongs to period '{inv_period}', not filing period '{period}'.",
                suggested_action="Verify if this invoice belongs to a prior period amendment or current month return.",
            )
            issues.append(issue)

    # 3. Negative values check
    taxable_dec = round_currency(taxable_value)
    if taxable_dec < Decimal("0.00") and invoice_type not in ("CDNR", "CDNUR"):
        issue = make_issue(
            code="NEGATIVE_TAXABLE_VALUE",
            severity="ERROR",
            field="taxable_value",
            message=f"Taxable value ₹{taxable_value} cannot be negative for regular invoices.",
            suggested_action="Use Credit/Debit Note (CDNR) classification for downward adjustments.",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    if (
        round_currency(cgst_amount) < Decimal("0.00")
        or round_currency(sgst_amount) < Decimal("0.00")
        or round_currency(igst_amount) < Decimal("0.00")
        or round_currency(cess_amount) < Decimal("0.00")
    ) and invoice_type not in ("CDNR", "CDNUR"):
        issue = make_issue(
            code="NEGATIVE_TAX_AMOUNT",
            severity="ERROR",
            field="tax_amount",
            message="Tax amounts cannot be negative.",
            suggested_action="Ensure non-negative tax amounts or classify as a credit note.",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    # 4. Place of Supply check
    valid_pos, pos_err = validate_state_code(place_of_supply)
    if not valid_pos:
        issue = make_issue(
            code="INVALID_POS",
            severity="BLOCKING",
            field="place_of_supply",
            message=pos_err or "Invalid Place of Supply code.",
            suggested_action="Select a recognized 2-digit Indian State/UT code (01-38, 97, 99).",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    # 5. Tax rate check
    valid_rate, rate_err = validate_tax_rate(tax_rate)
    if not valid_rate:
        issue = make_issue(
            code="INVALID_TAX_RATE",
            severity="ERROR",
            field="tax_rate",
            message=rate_err or f"Invalid tax rate {tax_rate}%.",
            suggested_action="Use a standard statutory GST slab (0%, 5%, 12%, 18%, 28%).",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    # 6. Nil/Exempt supply rate check
    if invoice_type == "NIL_EXEMPT" and round_currency(tax_rate) != Decimal("0.00"):
        issue = make_issue(
            code="NIL_EXEMPT_NONZERO_RATE",
            severity="ERROR",
            field="tax_rate",
            message=f"Nil-rated / Exempt supplies must have 0% tax rate, found {tax_rate}%.",
            suggested_action="Set tax rate to 0.00% for exempt supplies.",
        )
        issues.append(issue)
        error_strings.append(issue["message"])

    # 7. Counterparty GSTIN verification for B2B supplies
    if invoice_type in ("B2B", "CDNR"):
        valid_g, g_err = validate_gstin(customer_or_supplier_gstin)
        if not valid_g:
            issue = make_issue(
                code="INVALID_RECIPIENT_GSTIN",
                severity="ERROR",
                field="customer_gstin",
                message=f"Counterparty GSTIN error: {g_err}",
                suggested_action="Ensure registered recipient has a valid 15-character GSTIN.",
            )
            issues.append(issue)
            error_strings.append(issue["message"])
        elif customer_or_supplier_gstin:
            gstin_state = customer_or_supplier_gstin[:2]
            pos_clean = place_of_supply.strip().zfill(2)
            if gstin_state != pos_clean and invoice_type == "B2B":
                issue = make_issue(
                    code="GSTIN_POS_STATE_MISMATCH",
                    severity="WARNING",
                    field="place_of_supply",
                    message=f"Recipient GSTIN state ({gstin_state}) differs from POS ({pos_clean}).",
                    suggested_action="Confirm bill-to vs ship-to location for supply.",
                )
                issues.append(issue)

    # 8. Credit/Debit note checks
    if invoice_type in ("CDNR", "CDNUR") and not original_invoice_number:
        issue = make_issue(
            code="CDNR_ORIGINAL_INVOICE_MISSING",
            severity="WARNING",
            field="original_invoice_number",
            message="Credit/Debit note should reference the original statutory tax invoice.",
            suggested_action="Provide original invoice number to facilitate reconciliation.",
        )
        issues.append(issue)

    # 9. Tax split consistency check
    expected = calculate_tax_split(
        place_of_supply=place_of_supply,
        supplier_state_code=supplier_state_code,
        taxable_value=taxable_value,
        tax_rate=tax_rate,
        cess=cess_amount,
    )

    tolerance = Decimal("1.00")

    if expected["supply_type"] == "INTRA_STATE":
        if round_currency(igst_amount) > Decimal("0.00"):
            issue = make_issue(
                code="IGST_IN_INTRA_STATE",
                severity="ERROR",
                field="igst_amount",
                message=f"Intra-state supply (POS {place_of_supply} == Supplier {supplier_state_code}) cannot carry IGST.",
                suggested_action="Reallocate IGST equally into CGST and SGST.",
            )
            issues.append(issue)
            error_strings.append(issue["message"])
        if abs(round_currency(cgst_amount) - expected["cgst_amount"]) > tolerance:
            msg = f"CGST mismatch: Stated ₹{cgst_amount}, Expected ₹{expected['cgst_amount']}"
            issues.append(
                make_issue(
                    "CGST_MISMATCH", "ERROR", "cgst_amount", msg, "Update CGST amount."
                )
            )
            error_strings.append(msg)
        if abs(round_currency(sgst_amount) - expected["sgst_amount"]) > tolerance:
            msg = f"SGST mismatch: Stated ₹{sgst_amount}, Expected ₹{expected['sgst_amount']}"
            issues.append(
                make_issue(
                    "SGST_MISMATCH", "ERROR", "sgst_amount", msg, "Update SGST amount."
                )
            )
            error_strings.append(msg)
    else:
        if round_currency(cgst_amount) > Decimal("0.00") or round_currency(
            sgst_amount
        ) > Decimal("0.00"):
            issue = make_issue(
                code="CGST_SGST_IN_INTER_STATE",
                severity="ERROR",
                field="cgst_amount",
                message=f"Inter-state supply (POS {place_of_supply} != Supplier {supplier_state_code}) cannot carry CGST or SGST.",
                suggested_action="Reallocate CGST and SGST into IGST.",
            )
            issues.append(issue)
            error_strings.append(issue["message"])
        if abs(round_currency(igst_amount) - expected["igst_amount"]) > tolerance:
            msg = f"IGST mismatch: Stated ₹{igst_amount}, Expected ₹{expected['igst_amount']}"
            issues.append(
                make_issue(
                    "IGST_MISMATCH", "ERROR", "igst_amount", msg, "Update IGST amount."
                )
            )
            error_strings.append(msg)

    # 10. Total amount component sum verification
    calc_total = taxable_value + cgst_amount + sgst_amount + igst_amount + cess_amount
    if abs(round_currency(total_amount) - round_currency(calc_total)) > tolerance:
        msg = f"Total invoice amount ₹{total_amount} does not match sum of components ₹{calc_total}"
        issues.append(
            make_issue(
                "TOTAL_AMOUNT_MISMATCH",
                "ERROR",
                "total_amount",
                msg,
                "Recalculate invoice total.",
            )
        )
        error_strings.append(msg)

    # Determine overall status: invalid if any blocking/error severity issues
    has_blocking = any(i["severity"] in ("BLOCKING", "ERROR") for i in issues)
    is_valid = not has_blocking
    return is_valid, issues, error_strings


def validate_invoice(
    invoice_number: str,
    invoice_date: str,
    place_of_supply: str,
    supplier_state_code: str,
    taxable_value: Decimal,
    tax_rate: Decimal,
    igst_amount: Decimal,
    cgst_amount: Decimal,
    sgst_amount: Decimal,
    cess_amount: Decimal,
    total_amount: Decimal,
    customer_or_supplier_gstin: Optional[str] = None,
    is_b2b: bool = True,
) -> Tuple[str, List[str]]:
    """Backwards-compatible wrapper returning (status, error_messages)."""
    inv_type = "B2B" if is_b2b else "B2CS"
    is_valid, _, errors = validate_invoice_structured(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        place_of_supply=place_of_supply,
        supplier_state_code=supplier_state_code,
        taxable_value=taxable_value,
        tax_rate=tax_rate,
        igst_amount=igst_amount,
        cgst_amount=cgst_amount,
        sgst_amount=sgst_amount,
        cess_amount=cess_amount,
        total_amount=total_amount,
        customer_or_supplier_gstin=customer_or_supplier_gstin,
        invoice_type=inv_type,
    )
    return ("VALID" if is_valid else "ERROR"), errors


def validate_sales_invoice(
    supplier_state: str,
    place_of_supply: str,
    customer_gstin: Optional[str],
    invoice_type: str,
    taxable_value: Decimal,
    tax_rate: Decimal,
    cgst: Decimal,
    sgst: Decimal,
    igst: Decimal,
    cess: Decimal,
    total_amount: Decimal,
) -> Tuple[bool, List[str]]:
    """Backwards-compatible wrapper for sales invoice validation."""
    status, errors = validate_invoice(
        invoice_number="DUMMY",
        invoice_date="2024-01-01",
        place_of_supply=place_of_supply,
        supplier_state_code=supplier_state,
        taxable_value=taxable_value,
        tax_rate=tax_rate,
        igst_amount=igst,
        cgst_amount=cgst,
        sgst_amount=sgst,
        cess_amount=cess,
        total_amount=total_amount,
        customer_or_supplier_gstin=customer_gstin,
        is_b2b=(invoice_type == "B2B"),
    )
    return (status == "VALID", errors)
