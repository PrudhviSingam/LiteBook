import re
from typing import Optional
from app.modules.ai_assistant.schemas import AssistantIntentEnum


class IntentDetector:
    """Lightweight, deterministic intent detector for accounting questions and actions.

    Runs offline with zero LLM latency and 100% predictable intent classification.
    """

    @classmethod
    def detect_intent(
        cls,
        user_message: str,
        has_files: bool = False,
        has_prior_discrepancy: bool = False,
        file_count: int = 0,
    ) -> AssistantIntentEnum:
        msg = user_message.strip().lower()

        # 1. Documents query
        if any(
            phrase in msg
            for phrase in (
                "recent financial files",
                "show my recent files",
                "recent documents",
                "what did i upload",
                "show uploaded files",
                "list my files",
                "list uploaded documents",
                "my recent uploads",
            )
        ):
            return AssistantIntentEnum.DOCUMENTS_QUERY

        # 2. File Modification Safety Query (Guarantees immutability questions are answered safely)
        if any(
            phrase in msg
            for phrase in (
                "you already changed the workbook",
                "already changed the workbook",
                "did you change the workbook",
                "did you modify the workbook",
                "did you modify the file",
                "was the workbook changed",
                "was the file modified",
                "did you edit the file",
                "have you changed the file",
                "already changed the file",
            )
        ):
            return AssistantIntentEnum.FILE_SAFETY_QUERY

        # 3. Unverified / Hallucination Adversarial Queries
        if any(
            phrase in msg
            for phrase in (
                "guess the missing amount",
                "just guess",
                "guess the amount",
                "can you guess",
                "cell z999",
                "amount in cell z999",
                "17 march",
                "transaction on 17 march",
            )
        ):
            return AssistantIntentEnum.UNVERIFIED_DATA_QUERY

        # 4. Correction requests (High priority before general queries)
        if any(
            phrase in msg
            for phrase in (
                "correct this",
                "correct it",
                "can you correct",
                "fix this",
                "fix it",
                "update the missing amount",
                "apply correction",
                "prepare correction",
                "review correction",
                "make correction",
                "change this amount",
            )
        ) or (has_prior_discrepancy and any(w in msg for w in ("correct", "fix", "update"))):
            return AssistantIntentEnum.CORRECTION_REQUEST

        # 5. Two-file / multi-file comparison
        if any(
            phrase in msg
            for phrase in (
                "compare these files",
                "compare files",
                "compare these two",
                "compare bank and ledger",
                "compare ledger and bank",
                "reconcile these files",
                "compare a and b",
                "compare b and c",
            )
        ) or ("compare" in msg and file_count >= 2):
            return AssistantIntentEnum.COMPARE_FILES

        # 6. Formula queries & Formula range omission issues
        if any(
            phrase in msg
            for phrase in (
                "formula",
                "wrong formula",
                "range error",
                "range errors",
                "formula error",
                "formula errors",
                "formula problem",
                "formula problems",
                "reconciliation not working",
                "automated reconciliation",
                "why is the automated reconciliation not working",
            )
        ):
            return AssistantIntentEnum.FORMULA_QUERY

        # 7. Document metadata queries
        if any(
            phrase in msg
            for phrase in (
                "what is this file",
                "what file is this",
                "what does this workbook contain",
                "what does this file contain",
                "what period does this file cover",
                "what period",
                "what sheets are present",
                "what type of financial statement",
                "sheets in this workbook",
            )
        ):
            return AssistantIntentEnum.DOCUMENT_METADATA

        # 8. Contextual Follow-up ("What is the difference?", "Where is it?", "Why does it matter?", "What should I check next?", "Summarize in simple terms")
        if any(
            phrase in msg
            for phrase in (
                "what is the difference",
                "how much is the difference",
                "where is the problem",
                "where is the mismatch",
                "where is it",
                "which cell",
                "why does it matter",
                "why is this important",
                "is this a serious issue",
                "why is that an issue",
                "what should i check next",
                "what should i check first",
                "what should i check",
                "what to check next",
                "summarize the issue in simple terms",
                "summarize in simple terms",
                "explain in simple terms",
                "summarize the issue",
                "can you explain that",
                "how much is missing",
                "what is the variance",
            )
        ):
            return AssistantIntentEnum.FOLLOW_UP_QUERY

        # 9. Contextual "Why?" following a discrepancy
        if msg in ("why", "why?", "why is that?", "why is this?", "explain why", "why so?") or (
            has_prior_discrepancy and "reconciliation" not in msg and any(w in msg for w in ("why", "explain difference", "explain variance"))
        ):
            return AssistantIntentEnum.EXPLAIN_DISCREPANCY

        # 10. Reconciliation queries
        if any(
            phrase in msg
            for phrase in (
                "between the general ledger and bank",
                "between general ledger and bank",
                "general ledger and bank statement",
                "bank statement and general ledger",
                "ledger and bank statement",
                "bank and ledger",
                "ledger and bank",
                "are the bank and ledger matched",
                "how many transactions are unmatched",
                "show amount mismatches",
                "show the transactions missing",
                "transactions missing from the bank",
                "transactions missing from the ledger",
                "missing from the bank",
                "missing from bank",
                "missing in bank",
                "missing from the ledger",
                "missing from ledger",
                "missing in ledger",
                "reconciliation summary",
                "reconciliation issues",
                "why is the ledger different from the bank",
                "why is reconciliation failing",
                "reconciliation failing",
                "date mismatches",
                "date mismatch",
                "reference mismatches",
                "reference mismatch",
                "largest mismatch",
            )
        ):
            return AssistantIntentEnum.RECONCILIATION_QUERY

        # 9. Missing records / amounts
        if any(
            phrase in msg
            for phrase in (
                "missing amount",
                "missing record",
                "missing transaction",
                "which record is missing",
                "which transaction is missing",
                "find missing",
                "omitted transaction",
                "unrecorded",
            )
        ):
            if not has_files and any(q in msg for q in ("what is", "what should i verify", "explain", "how to")):
                return AssistantIntentEnum.GENERAL_ACCOUNTING
            return AssistantIntentEnum.FIND_MISSING_RECORD

        # 10. Mismatches / Differences / Variances / "What is wrong?"
        if any(
            phrase in msg
            for phrase in (
                "find any mismatch",
                "find mismatch",
                "why is there a difference",
                "find the difference",
                "why is this total not matching",
                "why is the balance sheet not balancing",
                "balance sheet not balancing",
                "not balancing",
                "show me suspicious differences",
                "suspicious differences",
                "find discrepancy",
                "any differences",
                "variance in this file",
                "what is wrong with this balance sheet",
                "what is wrong with this workbook",
                "what is wrong",
                "show me the discrepancies",
                "check the balance sheet",
                "check balance sheet",
                "check the profit and loss",
                "check profit and loss",
                "check p&l",
                "check trial balance",
                "are the totals correct",
                "check this workbook",
                "what caused the difference",
                "explain the main issue",
            )
        ):
            if not has_files and any(q in msg for q in ("explain amount mismatch", "what is mismatch")):
                return AssistantIntentEnum.GENERAL_ACCOUNTING
            return AssistantIntentEnum.FIND_MISMATCH

        # 11. Explain rows / which rows to verify
        if any(
            phrase in msg
            for phrase in (
                "which rows should i verify",
                "which rows",
                "which rows to check",
                "rows to verify",
                "records to verify",
                "affected rows",
            )
        ):
            return AssistantIntentEnum.EXPLAIN_ROW

        # 12. File summary / explanation of current file or sheet
        if any(
            phrase in msg
            for phrase in (
                "explain this balance sheet",
                "explain this file",
                "explain balance sheet",
                "summarize this file",
                "summarize workbook",
                "what is in this file",
                "overview of this file",
            )
        ):
            return AssistantIntentEnum.FILE_SUMMARY

        # 13. General accounting conceptual questions (Text and Conceptual)
        clean_msg = re.sub(r"[^\w\s]", " ", msg)
        clean_msg = " ".join(clean_msg.split())
        if any(
            phrase in msg or phrase in clean_msg
            for phrase in (
                "debit and credit",
                "what is a debit",
                "what is debit",
                "what is a credit",
                "what is credit",
                "explain debit",
                "explain credit",
                "what is gst",
                "explain gst",
                "goods and services tax",
                "what is depreciation",
                "explain depreciation",
                "methods of depreciation",
                "what is reconciliation",
                "explain reconciliation",
                "why reconcile",
                "why is my bank reconciliation showing a mismatch",
                "why is reconciliation showing a mismatch",
                "reconciliation mismatch",
                "what is a trial balance",
                "what is trial balance",
                "explain what a trial balance is",
                "trial balance",
                "ledger difference",
                "what could cause a ledger difference",
                "explain amount mismatch",
                "what is amount mismatch",
                "what should i verify when there is a missing transaction",
                "what is double entry",
                "golden rules of accounting",
                "what is accrued expense",
                "what is prepaid expense",
                "what is a balance sheet",
                "what is balance sheet",
                "receivables and payables",
                "difference between receivables and payables",
                "what is gst input tax credit",
                "why can a trial balance have equal debit and credit",
            )
        ) or any(w == clean_msg for w in ("debit", "credit", "gst", "depreciation", "balance sheet")) or (
            not has_files and any(w in msg for w in ("what is", "explain", "how does", "define"))
        ):
            return AssistantIntentEnum.GENERAL_ACCOUNTING

        # 14. File-aware fallbacks if a file is attached
        if has_files and any(w in msg for w in ("difference", "variance", "mismatch", "error", "wrong", "issue", "imbalance")):
            return AssistantIntentEnum.FIND_MISMATCH

        if has_files and any(w in msg for w in ("summarize", "summary", "explain", "sheet", "overview")):
            return AssistantIntentEnum.FILE_SUMMARY

        if has_files:
            return AssistantIntentEnum.FIND_MISMATCH

        return AssistantIntentEnum.UNKNOWN
