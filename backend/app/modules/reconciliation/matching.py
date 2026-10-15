import difflib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from app.modules.reconciliation.schemas import (
    DifferenceTypeEnum,
    MatchingFactors,
    NormalizedTransaction,
    ReconciliationItem,
    ReconciliationRuleConfig,
    ReconciliationStatusEnum,
    ReconciliationSummary,
    SourceLocation,
)


def compute_string_similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_clean = " ".join(a.lower().split())
    b_clean = " ".join(b.lower().split())
    if a_clean == b_clean:
        return 1.0
    return round(difflib.SequenceMatcher(None, a_clean, b_clean).ratio(), 3)


def clean_reference(ref: Optional[str]) -> str:
    if not ref:
        return ""
    # Strip whitespace, dashes, leading zeroes for robust comparison
    s = str(ref).strip().upper()
    s = s.lstrip("0")
    return s


def calculate_date_difference(d1_str: str, d2_str: str) -> int:
    try:
        d1 = datetime.strptime(d1_str, "%Y-%m-%d").date()
        d2 = datetime.strptime(d2_str, "%Y-%m-%d").date()
        return abs((d1 - d2).days)
    except Exception:
        return 999


def find_duplicates(transactions: List[NormalizedTransaction]) -> Set[str]:
    """Identifies IDs of transactions that appear to be exact duplicates within the same source."""
    seen: Dict[Tuple[float, str, str], List[str]] = {}
    duplicate_ids: Set[str] = set()

    for tx in transactions:
        key = (tx.amount, tx.date, clean_reference(tx.reference))
        if key not in seen:
            seen[key] = [tx.id]
        else:
            seen[key].append(tx.id)

    for key, ids in seen.items():
        if len(ids) > 1 and key[0] > 0:  # Only if amount > 0
            duplicate_ids.update(ids)

    return duplicate_ids


def build_source_location(tx: Optional[NormalizedTransaction], field_name: str = "amount") -> Optional[SourceLocation]:
    if not tx:
        return None
    cell = tx.cell_addresses.get(field_name) or tx.cell_addresses.get("amount") or tx.cell_addresses.get("reference")
    return SourceLocation(
        file_name=tx.filename or "",
        sheet_name=tx.sheet_name or "",
        row_number=tx.original_row_number,
        cell_address=cell,
    )


def match_transactions(
    bank_txs: List[NormalizedTransaction],
    ledger_txs: List[NormalizedTransaction],
    rules: ReconciliationRuleConfig = ReconciliationRuleConfig(),
) -> Tuple[List[ReconciliationItem], ReconciliationSummary]:
    """Deterministic, multi-pass reconciliation engine comparing two financial files or sheets."""
    matched_bank_ids: Set[str] = set()
    matched_ledger_ids: Set[str] = set()
    results: List[ReconciliationItem] = []

    bank_duplicates = find_duplicates(bank_txs)
    ledger_duplicates = find_duplicates(ledger_txs)

    # ----------------------------------------------------
    # Pass 1: Exact Match (Exact Amount + Exact Ref + Date within tolerance)
    # ----------------------------------------------------
    for b in bank_txs:
        if b.id in matched_bank_ids:
            continue
        b_ref = clean_reference(b.reference)
        if not b_ref:
            continue

        for l in ledger_txs:
            if l.id in matched_ledger_ids:
                continue
            l_ref = clean_reference(l.reference)
            if not l_ref:
                continue

            amt_diff = abs(b.amount - l.amount)
            if amt_diff <= rules.amount_tolerance and b_ref == l_ref:
                date_diff = calculate_date_difference(b.date, l.date)
                if date_diff <= rules.date_tolerance_days:
                    # High confidence exact match
                    is_dup = b.id in bank_duplicates or l.id in ledger_duplicates
                    desc_sim = compute_string_similarity(b.description, l.description)

                    status = ReconciliationStatusEnum.POSSIBLE_DUPLICATE if is_dup else ReconciliationStatusEnum.MATCHED
                    diff_type = DifferenceTypeEnum.DUPLICATE_ENTRY if is_dup else DifferenceTypeEnum.MATCHED
                    reason = (
                        "Possible duplicate entry detected with identical reference and amount."
                        if is_dup
                        else "Transaction perfectly matched on amount, reference, and date."
                    )
                    action = (
                        "Verify both statements to ensure transaction was not recorded twice."
                        if is_dup
                        else "No action required. Reconciled."
                    )

                    results.append(
                        ReconciliationItem(
                            id=f"rec_{uuid.uuid4().hex[:8]}",
                            status=status,
                            difference_type=diff_type,
                            bank_transaction=b,
                            ledger_transaction=l,
                            bank_date=b.date,
                            ledger_date=l.date,
                            description=b.description or l.description,
                            reference=b.reference or l.reference,
                            bank_amount=b.amount,
                            ledger_amount=l.amount,
                            difference=round(b.amount - l.amount, 2),
                            confidence="high",
                            matching_factors=MatchingFactors(
                                amount_match=True,
                                date_match=True,
                                reference_match=True,
                                description_similarity=desc_sim,
                            ),
                            match_tier=1,
                            reason=reason,
                            suggested_action=action,
                            relevant_field="Amount / Reference / Date",
                            source_a_location=build_source_location(b, "amount"),
                            source_b_location=build_source_location(l, "amount"),
                            source_a_value=b.amount,
                            source_b_value=l.amount,
                            source_a_entry=b.raw_row,
                            source_b_entry=l.raw_row,
                            review_status="CONFIRMED" if not is_dup else "PENDING_REVIEW",
                        )
                    )
                    matched_bank_ids.add(b.id)
                    matched_ledger_ids.add(l.id)
                    break

    # ----------------------------------------------------
    # Pass 2: Amount & Reference Match, Date Mismatch (Beyond tolerance)
    # ----------------------------------------------------
    for b in bank_txs:
        if b.id in matched_bank_ids:
            continue
        b_ref = clean_reference(b.reference)
        if not b_ref:
            continue

        for l in ledger_txs:
            if l.id in matched_ledger_ids:
                continue
            l_ref = clean_reference(l.reference)
            if not l_ref:
                continue

            amt_diff = abs(b.amount - l.amount)
            if amt_diff <= rules.amount_tolerance and b_ref == l_ref:
                date_diff = calculate_date_difference(b.date, l.date)
                desc_sim = compute_string_similarity(b.description, l.description)

                results.append(
                    ReconciliationItem(
                        id=f"rec_{uuid.uuid4().hex[:8]}",
                        status=ReconciliationStatusEnum.DATE_MISMATCH,
                        difference_type=DifferenceTypeEnum.CHANGED_VALUE,
                        bank_transaction=b,
                        ledger_transaction=l,
                        bank_date=b.date,
                        ledger_date=l.date,
                        description=b.description or l.description,
                        reference=b.reference or l.reference,
                        bank_amount=b.amount,
                        ledger_amount=l.amount,
                        difference=round(b.amount - l.amount, 2),
                        confidence="medium",
                        matching_factors=MatchingFactors(
                            amount_match=True,
                            date_match=False,
                            reference_match=True,
                            description_similarity=desc_sim,
                        ),
                        match_tier=4,
                        reason=f"Amount and reference match, but bank cleared on {b.date} while ledger records {l.date} ({date_diff} days difference).",
                        suggested_action="Verify timing difference between bank clearance date and ledger voucher date.",
                        relevant_field="Date",
                        source_a_location=build_source_location(b, "date"),
                        source_b_location=build_source_location(l, "date"),
                        source_a_value=b.date,
                        source_b_value=l.date,
                        source_a_entry=b.raw_row,
                        source_b_entry=l.raw_row,
                        review_status="PENDING_REVIEW",
                    )
                )
                matched_bank_ids.add(b.id)
                matched_ledger_ids.add(l.id)
                break

    # ----------------------------------------------------
    # Pass 3: Reference & Date Match, Amount Mismatch
    # ----------------------------------------------------
    for b in bank_txs:
        if b.id in matched_bank_ids:
            continue
        b_ref = clean_reference(b.reference)
        if not b_ref:
            continue

        for l in ledger_txs:
            if l.id in matched_ledger_ids:
                continue
            l_ref = clean_reference(l.reference)
            if not l_ref:
                continue

            if b_ref == l_ref:
                date_diff = calculate_date_difference(b.date, l.date)
                if date_diff <= rules.date_tolerance_days + 3:
                    diff = round(b.amount - l.amount, 2)
                    desc_sim = compute_string_similarity(b.description, l.description)

                    results.append(
                        ReconciliationItem(
                            id=f"rec_{uuid.uuid4().hex[:8]}",
                            status=ReconciliationStatusEnum.AMOUNT_MISMATCH,
                            difference_type=DifferenceTypeEnum.CHANGED_VALUE,
                            bank_transaction=b,
                            ledger_transaction=l,
                            bank_date=b.date,
                            ledger_date=l.date,
                            description=b.description or l.description,
                            reference=b.reference or l.reference,
                            bank_amount=b.amount,
                            ledger_amount=l.amount,
                            difference=diff,
                            confidence="medium",
                            matching_factors=MatchingFactors(
                                amount_match=False,
                                date_match=(date_diff <= rules.date_tolerance_days),
                                reference_match=True,
                                description_similarity=desc_sim,
                            ),
                            match_tier=4,
                            reason=f"Bank transaction amount (₹{b.amount:,.2f}) differs from ledger amount (₹{l.amount:,.2f}) by ₹{abs(diff):,.2f}.",
                            suggested_action="Verify the original invoice/payment record and adjust the ledger voucher if required.",
                            relevant_field="Amount",
                            source_a_location=build_source_location(b, "amount"),
                            source_b_location=build_source_location(l, "amount"),
                            source_a_value=b.amount,
                            source_b_value=l.amount,
                            source_a_entry=b.raw_row,
                            source_b_entry=l.raw_row,
                            review_status="PENDING_REVIEW",
                        )
                    )
                    matched_bank_ids.add(b.id)
                    matched_ledger_ids.add(l.id)
                    break

    # ----------------------------------------------------
    # Pass 4: Amount & Date Match (Reference missing or differing)
    # ----------------------------------------------------
    for b in bank_txs:
        if b.id in matched_bank_ids:
            continue

        for l in ledger_txs:
            if l.id in matched_ledger_ids:
                continue

            amt_diff = abs(b.amount - l.amount)
            if amt_diff <= rules.amount_tolerance:
                date_diff = calculate_date_difference(b.date, l.date)
                if date_diff <= rules.date_tolerance_days:
                    b_ref = clean_reference(b.reference)
                    l_ref = clean_reference(l.reference)
                    desc_sim = compute_string_similarity(b.description, l.description)

                    if b_ref and l_ref and b_ref != l_ref:
                        # References conflict explicitly
                        results.append(
                            ReconciliationItem(
                                id=f"rec_{uuid.uuid4().hex[:8]}",
                                status=ReconciliationStatusEnum.REFERENCE_MISMATCH,
                                difference_type=DifferenceTypeEnum.CHANGED_VALUE,
                                bank_transaction=b,
                                ledger_transaction=l,
                                bank_date=b.date,
                                ledger_date=l.date,
                                description=b.description or l.description,
                                reference=f"{b.reference} (Bank) / {l.reference} (Ledger)",
                                bank_amount=b.amount,
                                ledger_amount=l.amount,
                                difference=0.0,
                                confidence="medium",
                                matching_factors=MatchingFactors(
                                    amount_match=True,
                                    date_match=True,
                                    reference_match=False,
                                    description_similarity=desc_sim,
                                ),
                                match_tier=4,
                                reason=f"Amount (₹{b.amount:,.2f}) and date match, but bank reference '{b.reference}' differs from ledger reference '{l.reference}'.",
                                suggested_action="Confirm whether the reference number was miskeyed during ledger entry.",
                                relevant_field="Reference",
                                source_a_location=build_source_location(b, "reference"),
                                source_b_location=build_source_location(l, "reference"),
                                source_a_value=b.reference,
                                source_b_value=l.reference,
                                source_a_entry=b.raw_row,
                                source_b_entry=l.raw_row,
                                review_status="PENDING_REVIEW",
                            )
                        )
                    else:
                        is_dup = b.id in bank_duplicates or l.id in ledger_duplicates
                        tier = 2 if (b_ref == l_ref and not is_dup) else 3
                        status = (
                            ReconciliationStatusEnum.POSSIBLE_DUPLICATE
                            if is_dup
                            else ReconciliationStatusEnum.MATCHED
                        )
                        diff_type = DifferenceTypeEnum.DUPLICATE_ENTRY if is_dup else DifferenceTypeEnum.MATCHED
                        reason = (
                            "Possible duplicate transaction with matching amount and date."
                            if is_dup
                            else "Matched on exact amount, date, and compatible narration."
                        )
                        action = (
                            "Review duplicate entries in ledger."
                            if is_dup
                            else "No action required. Reconciled."
                        )

                        results.append(
                            ReconciliationItem(
                                id=f"rec_{uuid.uuid4().hex[:8]}",
                                status=status,
                                difference_type=diff_type,
                                bank_transaction=b,
                                ledger_transaction=l,
                                bank_date=b.date,
                                ledger_date=l.date,
                                description=b.description or l.description,
                                reference=b.reference or l.reference or "",
                                bank_amount=b.amount,
                                ledger_amount=l.amount,
                                difference=0.0,
                                confidence="high" if desc_sim >= 0.5 else "medium",
                                matching_factors=MatchingFactors(
                                    amount_match=True,
                                    date_match=True,
                                    reference_match=bool(b_ref and l_ref and b_ref == l_ref),
                                    description_similarity=desc_sim,
                                ),
                                match_tier=tier,
                                reason=reason,
                                suggested_action=action,
                                relevant_field="Amount / Date",
                                source_a_location=build_source_location(b, "amount"),
                                source_b_location=build_source_location(l, "amount"),
                                source_a_value=b.amount,
                                source_b_value=l.amount,
                                source_a_entry=b.raw_row,
                                source_b_entry=l.raw_row,
                                review_status="CONFIRMED" if not is_dup else "PENDING_REVIEW",
                            )
                        )
                    matched_bank_ids.add(b.id)
                    matched_ledger_ids.add(l.id)
                    break

    # ----------------------------------------------------
    # Pass 5: Unmatched Bank Transactions (Missing in Ledger)
    # ----------------------------------------------------
    for b in bank_txs:
        if b.id not in matched_bank_ids:
            is_dup = b.id in bank_duplicates
            status = (
                ReconciliationStatusEnum.POSSIBLE_DUPLICATE
                if is_dup
                else ReconciliationStatusEnum.MISSING_IN_LEDGER
            )
            diff_type = DifferenceTypeEnum.DUPLICATE_ENTRY if is_dup else DifferenceTypeEnum.MISSING_ROW
            reason = (
                f"Duplicate bank transaction of ₹{b.amount:,.2f} on {b.date}."
                if is_dup
                else f"Bank transaction of ₹{b.amount:,.2f} on {b.date} has no corresponding entry in the accounting ledger."
            )
            action = (
                "Review bank statement for recurring duplicate debits/credits."
                if is_dup
                else "Post the missing bank transaction to the accounting ledger (e.g., bank charges, direct deposits, or automated standing instructions)."
            )

            results.append(
                ReconciliationItem(
                    id=f"rec_{uuid.uuid4().hex[:8]}",
                    status=status,
                    difference_type=diff_type,
                    bank_transaction=b,
                    ledger_transaction=None,
                    bank_date=b.date,
                    ledger_date=None,
                    description=b.description,
                    reference=b.reference,
                    bank_amount=b.amount,
                    ledger_amount=None,
                    difference=round(b.amount, 2),
                    confidence="high",
                    matching_factors=MatchingFactors(
                        amount_match=False,
                        date_match=False,
                        reference_match=False,
                        description_similarity=0.0,
                    ),
                    reason=reason,
                    suggested_action=action,
                    relevant_field="Record Missing in File B",
                    source_a_location=build_source_location(b, "amount"),
                    source_b_location=None,
                    source_a_value=b.amount,
                    source_b_value=None,
                    source_a_entry=b.raw_row,
                    source_b_entry=None,
                    review_status="PENDING_REVIEW",
                )
            )

    # ----------------------------------------------------
    # Pass 6: Unmatched Ledger Transactions (Missing in Bank)
    # ----------------------------------------------------
    for l in ledger_txs:
        if l.id not in matched_ledger_ids:
            is_dup = l.id in ledger_duplicates
            status = (
                ReconciliationStatusEnum.POSSIBLE_DUPLICATE
                if is_dup
                else ReconciliationStatusEnum.MISSING_IN_BANK
            )
            diff_type = DifferenceTypeEnum.DUPLICATE_ENTRY if is_dup else DifferenceTypeEnum.EXTRA_ROW
            reason = (
                f"Duplicate ledger entry of ₹{l.amount:,.2f} on {l.date}."
                if is_dup
                else f"Ledger entry of ₹{l.amount:,.2f} on {l.date} is not found in the bank statement."
            )
            action = (
                "Inspect ledger to remove or correct duplicate voucher."
                if is_dup
                else "Confirm if the payment/cheque is unpresented/uncredited, or if the transaction failed clearance."
            )

            results.append(
                ReconciliationItem(
                    id=f"rec_{uuid.uuid4().hex[:8]}",
                    status=status,
                    difference_type=diff_type,
                    bank_transaction=None,
                    ledger_transaction=l,
                    bank_date=None,
                    ledger_date=l.date,
                    description=l.description,
                    reference=l.reference,
                    bank_amount=None,
                    ledger_amount=l.amount,
                    difference=round(-l.amount, 2),
                    confidence="high",
                    matching_factors=MatchingFactors(
                        amount_match=False,
                        date_match=False,
                        reference_match=False,
                        description_similarity=0.0,
                    ),
                    reason=reason,
                    suggested_action=action,
                    relevant_field="Extra Record in File B",
                    source_a_location=None,
                    source_b_location=build_source_location(l, "amount"),
                    source_a_value=None,
                    source_b_value=l.amount,
                    source_a_entry=None,
                    source_b_entry=l.raw_row,
                    review_status="PENDING_REVIEW",
                )
            )

    # ----------------------------------------------------
    # Compute Summary Statistics
    # ----------------------------------------------------
    total_bank = len(bank_txs)
    total_ledger = len(ledger_txs)

    matched_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.MATCHED)
    amount_mismatch_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.AMOUNT_MISMATCH)
    date_mismatch_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.DATE_MISMATCH)
    ref_mismatch_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.REFERENCE_MISMATCH)
    missing_ledger_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.MISSING_IN_LEDGER)
    missing_bank_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.MISSING_IN_BANK)
    duplicate_cnt = sum(1 for r in results if r.status == ReconciliationStatusEnum.POSSIBLE_DUPLICATE)

    changed_val_cnt = sum(1 for r in results if r.difference_type == DifferenceTypeEnum.CHANGED_VALUE)
    missing_row_cnt = sum(1 for r in results if r.difference_type == DifferenceTypeEnum.MISSING_ROW)
    extra_row_cnt = sum(1 for r in results if r.difference_type == DifferenceTypeEnum.EXTRA_ROW)
    unmatched_record_cnt = sum(1 for r in results if r.difference_type == DifferenceTypeEnum.UNMATCHED)

    unmatched_cnt = (
        amount_mismatch_cnt
        + date_mismatch_cnt
        + ref_mismatch_cnt
        + missing_ledger_cnt
        + missing_bank_cnt
        + duplicate_cnt
    )

    base_denom = max(total_bank, total_ledger, 1)
    rate = round((matched_cnt / base_denom) * 100, 1)

    total_bank_amt = round(sum(b.amount for b in bank_txs), 2)
    total_ledger_amt = round(sum(l.amount for l in ledger_txs), 2)
    total_var = round(abs(total_bank_amt - total_ledger_amt), 2)

    summary = ReconciliationSummary(
        total_bank_transactions=total_bank,
        total_ledger_transactions=total_ledger,
        matched_count=matched_cnt,
        unmatched_count=unmatched_cnt,
        amount_mismatch_count=amount_mismatch_cnt,
        date_mismatch_count=date_mismatch_cnt,
        reference_mismatch_count=ref_mismatch_cnt,
        missing_in_ledger_count=missing_ledger_cnt,
        missing_in_bank_count=missing_bank_cnt,
        possible_duplicate_count=duplicate_cnt,
        reconciliation_rate=rate,
        total_bank_amount=total_bank_amt,
        total_ledger_amount=total_ledger_amt,
        total_variance=total_var,
        changed_value_count=changed_val_cnt,
        missing_row_count=missing_row_cnt,
        extra_row_count=extra_row_cnt,
        duplicate_count=duplicate_cnt,
        unmatched_record_count=unmatched_record_cnt,
        total_discrepancies=unmatched_cnt,
        matched_records=matched_cnt,
        match_rate_percentage=rate,
        missing_rows=missing_row_cnt,
        extra_rows=extra_row_cnt,
    )

    return results, summary
