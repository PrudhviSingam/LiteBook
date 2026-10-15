from typing import Dict, Any, Optional
from app.ai.factory import get_ai_provider
from app.modules.reconciliation.schemas import ReconciliationItem, ReconciliationStatusEnum


class ReconciliationAIExplainer:
    """Enriches deterministic reconciliation results with natural language explanations and suggested actions.

    Follows the principle: AI explains and assists; deterministic code calculates and decides.
    """

    @classmethod
    async def generate_explanation(cls, item: ReconciliationItem) -> Dict[str, str]:
        provider = get_ai_provider()

        if item.status == ReconciliationStatusEnum.MATCHED:
            return {
                "explanation": (
                    f"Verified Match: The bank statement entry of ₹{item.bank_amount:,.2f} on {item.bank_date} "
                    f"perfectly aligns with the accounting ledger entry on {item.ledger_date}. "
                    "All core verification factors (amount, date, reference) confirm a clean reconciliation."
                ),
                "suggested_action": "No adjustment necessary. This item is fully cleared and verified.",
            }

        elif item.status == ReconciliationStatusEnum.AMOUNT_MISMATCH:
            diff = abs(item.difference)
            higher = "bank statement" if (item.bank_amount or 0) > (item.ledger_amount or 0) else "ledger"
            return {
                "explanation": (
                    f"Amount Discrepancy Flagged: The bank statement records ₹{item.bank_amount:,.2f}, while the "
                    f"ledger reflects ₹{item.ledger_amount:,.2f}, resulting in a variance of ₹{diff:,.2f} (higher in {higher}). "
                    f"Reference '{item.reference}' matches across both records."
                ),
                "suggested_action": (
                    "Inspect the underlying tax invoice or bank voucher. If bank charges, discounts, or withholding taxes "
                    "were deducted, record an adjustment entry in the general ledger."
                ),
            }

        elif item.status == ReconciliationStatusEnum.DATE_MISMATCH:
            return {
                "explanation": (
                    f"Timing Difference: The transaction reference '{item.reference}' and amount (₹{item.bank_amount:,.2f}) "
                    f"match, but the bank clearance date ({item.bank_date}) differs significantly from the ledger posting date ({item.ledger_date})."
                ),
                "suggested_action": (
                    "Confirm the clearance cycle (e.g. cheque transit period or NEFT/RTGS settlement window). "
                    "No financial adjustment is required if this is an ordinary timing difference."
                ),
            }

        elif item.status == ReconciliationStatusEnum.REFERENCE_MISMATCH:
            return {
                "explanation": (
                    f"Reference Number Conflict: The amounts (₹{item.bank_amount:,.2f}) and dates align, but the bank UTR/reference "
                    f"does not match the ledger reference identifier ({item.reference})."
                ),
                "suggested_action": (
                    "Cross-check the payment counterfoil or bank remittance advice. Update the reference / cheque number "
                    "in the accounting ledger to maintain an accurate audit trail."
                ),
            }

        elif item.status == ReconciliationStatusEnum.MISSING_IN_LEDGER:
            return {
                "explanation": (
                    f"Unrecorded Bank Activity: A transaction of ₹{item.bank_amount:,.2f} on {item.bank_date} "
                    f"('{item.description}') exists on the bank statement with no corresponding entry in the books."
                ),
                "suggested_action": (
                    "Create a corresponding journal or payment voucher in the ledger. Typical sources include direct debit mandates, "
                    "quarterly bank charges, or automated client payments."
                ),
            }

        elif item.status == ReconciliationStatusEnum.MISSING_IN_BANK:
            return {
                "explanation": (
                    f"Outstanding Ledger Entry: A recorded ledger transaction of ₹{item.ledger_amount:,.2f} on {item.ledger_date} "
                    f"('{item.description}') has not yet cleared or appeared in the bank statement."
                ),
                "suggested_action": (
                    "Confirm whether an issued cheque remains unpresented or if a direct credit is in transit. "
                    "If the payment was cancelled or dishonoured, pass a reversal entry in the ledger."
                ),
            }

        elif item.status == ReconciliationStatusEnum.POSSIBLE_DUPLICATE:
            return {
                "explanation": (
                    f"Potential Duplicate Posting: Multiple records with identical amount (₹{item.bank_amount or item.ledger_amount:,.2f}) "
                    f"and dates were detected."
                ),
                "suggested_action": (
                    "Audit both the bank feed and ledger register to verify whether this is an intentional recurring transaction "
                    "or an accidental double-entry."
                ),
            }

        return {
            "explanation": item.reason,
            "suggested_action": item.suggested_action,
        }
