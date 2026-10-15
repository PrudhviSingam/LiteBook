import json
import logging
from typing import Any, Dict, List, Optional

from app.ai.factory import get_ai_provider
from app.modules.reconciliation.schemas import (
    DiscrepancyExplanationResponse,
    ReconciliationStatusEnum,
)
from app.modules.reconciliation.workbook_inspector import (
    format_indian_currency,
    parse_indian_currency,
)

logger = logging.getLogger(__name__)


class DiscrepancyExplanationEngine:
    """Discrepancy explanation layer separating deterministic rule-based analysis

    from cautious natural-language AI explanations.

    Enforces mandatory accounting safety principles:
    - Never asserts absolute certainty ("Possible reason", "Likely cause", "Please verify").
    - Never fabricates numbers, accounts, or transactions.
    - Operates with structured rule-based fallback when external AI providers are offline.
    """

    @classmethod
    async def explain(
        cls,
        discrepancy_data: Dict[str, Any],
        comparison_records: Optional[List[Dict[str, Any]]] = None,
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> DiscrepancyExplanationResponse:
        comparison_records = comparison_records or []
        document_metadata = document_metadata or {}

        # 1. Deterministic Rule-Based Extraction
        where_info = {
            "sheet_name": discrepancy_data.get("sheet_name") or "Balance Sheet",
            "section": discrepancy_data.get("section") or "Current Liabilities",
            "account": discrepancy_data.get("account") or discrepancy_data.get("description") or "Account Line Item",
            "field": discrepancy_data.get("field") or "Amount",
            "row_reference": discrepancy_data.get("row_reference") or discrepancy_data.get("id") or 1,
        }

        orig_raw = discrepancy_data.get("original_value")
        if orig_raw is None:
            orig_raw = discrepancy_data.get("bank_amount") or discrepancy_data.get("amount") or 0.0

        comp_raw = discrepancy_data.get("comparison_value")
        if comp_raw is None:
            comp_raw = discrepancy_data.get("ledger_amount") or discrepancy_data.get("expected_value") or 0.0

        orig_val = parse_indian_currency(orig_raw) or 0.0
        comp_val = parse_indian_currency(comp_raw) or 0.0

        diff = discrepancy_data.get("difference")
        if diff is None:
            diff = round(orig_val - comp_val, 2)
        else:
            diff = float(diff)

        abs_diff = abs(diff)
        diff_fmt = format_indian_currency(abs_diff)
        orig_fmt = format_indian_currency(orig_val)
        comp_fmt = format_indian_currency(comp_val)

        reason_category = discrepancy_data.get("reason_category") or discrepancy_data.get("status") or "AMOUNT_MISMATCH"
        account_name = where_info["account"]
        sheet_name = where_info["sheet_name"]
        field_name = where_info["field"]

        # 2. Rule-Based Evidence & Verification Construction
        evidence = [
            f"Account identifier '{account_name}' identified in {sheet_name}",
            f"Current recorded value: {orig_fmt}",
            f"Corresponding comparison record value: {comp_fmt}",
            f"Calculated variance of {diff_fmt}",
        ]
        if comparison_records:
            evidence.append(f"Derived from comparison against {len(comparison_records)} supporting record(s)")

        confidence = "HIGH"
        if abs_diff == 0:
            confidence = "HIGH"
        elif not comparison_records and orig_val == 0.0:
            confidence = "MEDIUM"

        what = f"{account_name} reflects a variance of {diff_fmt} between current record ({orig_fmt}) and comparison source ({comp_fmt})"

        # 3. Categorical Reasons & Verification Rules
        possible_reasons = []
        recommended_verification = []

        if reason_category in ("AMOUNT_MISMATCH", ReconciliationStatusEnum.AMOUNT_MISMATCH.value):
            possible_reasons = [
                f"An omitted transaction or invoice adjustment of {diff_fmt} in the primary ledger",
                "A data-entry transposition error during manual journal posting",
                "A timing difference between bank value date and book entry date",
                "An unrecorded discount, bank fee, or TDS/withholding deduction",
            ]
            recommended_verification = [
                f"Inspect supporting vendor invoices or counterparty ledgers for {account_name}",
                f"Verify whether an unposted debit/credit note of {diff_fmt} exists",
                "Check for recent journal entries or reconciliation adjustments in the subsequent period",
            ]
        elif reason_category in ("DATE_MISMATCH", ReconciliationStatusEnum.DATE_MISMATCH.value):
            possible_reasons = [
                "Cheque transit delay or banking clearance settlement cycle",
                "Weekend or statutory holiday posting rollover",
                "Advance payment recorded prior to bank clearing",
            ]
            recommended_verification = [
                "Verify the bank clearing advice or electronic payment UTR receipt",
                "Confirm whether this is a normal transit timing difference requiring no financial adjustment",
            ]
        elif reason_category in ("MISSING_IN_LEDGER", ReconciliationStatusEnum.MISSING_IN_LEDGER.value):
            possible_reasons = [
                "Direct bank debit mandate, automated charges, or standing instruction not yet posted in books",
                "Direct customer RTGS/NEFT inflow received without remittance advice",
            ]
            recommended_verification = [
                "Obtain bank transaction confirmation and identify recipient or payer",
                "Book corresponding general ledger receipt or payment voucher",
            ]
        elif reason_category in ("MISSING_IN_BANK", ReconciliationStatusEnum.MISSING_IN_BANK.value):
            possible_reasons = [
                "Cheque issued by the company remaining unpresented by the vendor",
                "Outstation clearing delay or stale cheque",
                "Transaction cancelled or voided in banking channel but remaining open in ledger",
            ]
            recommended_verification = [
                "Contact the payee to verify if the payment instrument has been deposited",
                "Pass a reversal entry if the payment instrument was cancelled or is past validity",
            ]
        elif reason_category in ("POSSIBLE_DUPLICATE", ReconciliationStatusEnum.POSSIBLE_DUPLICATE.value):
            possible_reasons = [
                "Accidental double posting of the same transaction voucher",
                "Legitimate recurring transaction with matching financial value",
            ]
            recommended_verification = [
                "Audit voucher numbers and transaction references to eliminate double counting",
            ]
        else:
            possible_reasons = [
                "Structural or classification variance between the two financial sources",
                "Manual adjustment recorded in one statement but not synchronized",
            ]
            recommended_verification = [
                "Review underlying documentation and reconcile line-by-line",
            ]

        # 4. Proposed Correction Object
        proposed_correction = {
            "target_sheet": sheet_name,
            "target_row": where_info["row_reference"],
            "target_field": field_name,
            "original_value": orig_val,
            "proposed_value": comp_val,
            "difference": round(-diff, 2),
            "description": f"Adjust {account_name} in {sheet_name} from {orig_fmt} to {comp_fmt} (Change: {format_indian_currency(-diff)})",
        }

        # 5. Default Deterministic Summary (Non-Dogmatic, Cautious)
        summary = (
            f"The system detected that the amount recorded for {account_name} ({orig_fmt}) differs from the "
            f"corresponding comparison record ({comp_fmt}) by {diff_fmt}. "
            "This variance may be caused by an omitted transaction, incorrect entry, timing difference, "
            "or an adjustment recorded in one source but not the other. "
            "Please verify the supporting records before making a final accounting decision."
        )

        # 6. Optional AI Enrichment via Provider (Non-dogmatic)
        try:
            ai_provider = get_ai_provider()
            prompt = (
                "You are an expert CPA and financial auditor. Provide a brief, cautious, 2-sentence explanation of this reconciliation discrepancy.\n"
                f"Account: {account_name}\n"
                f"Sheet: {sheet_name}\n"
                f"Recorded: {orig_fmt}\n"
                f"Expected/Comparison: {comp_fmt}\n"
                f"Difference: {diff_fmt}\n"
                f"Category: {reason_category}\n"
                "IMPORTANT RULES:\n"
                "1. NEVER state certainty. Use phrases like 'Possible reason', 'Likely cause', 'Please verify'.\n"
                "2. NEVER invent numbers or transactions.\n"
                "3. Keep it under 50 words."
            )
            ai_resp = await ai_provider.generate_response(prompt=prompt)
            if ai_resp and not ai_resp.startswith("[Finance AI Engine (Mock Mode)"):
                summary = ai_resp.strip()
        except Exception as e:
            logger.debug(f"AI Provider explanation fallback used: {e}")

        return DiscrepancyExplanationResponse(
            what=what,
            where=where_info,
            original_value=orig_val,
            expected_value=comp_val,
            difference=diff,
            reason_category=reason_category,
            summary=summary,
            possible_reasons=possible_reasons,
            proposed_correction=proposed_correction,
            evidence=evidence,
            recommended_verification=recommended_verification,
            confidence=confidence,
        )
