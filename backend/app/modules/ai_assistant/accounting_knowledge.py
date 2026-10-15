from typing import Any, Dict, List, Optional, Tuple


class AccountingKnowledgeEngine:
    """Expert accountant knowledge base providing clear, professional, and standard accounting

    answers for conceptual questions when no specific client file or figures are provided.
    """

    RESPONSES: Dict[str, Dict[str, Any]] = {
        "debit_credit": {
            "keywords": [
                "debit and credit", "what is a debit", "what is debit", "what is a credit", "what is credit",
                "explain debit", "explain credit", "explain debit and credit", "golden rules",
                "debits and credits", "double entry"
            ],
            "title": "Principles of Debit and Credit (Double-Entry Accounting)",
            "message": (
                "### Debit and Credit Principles\n\n"
                "In double-entry bookkeeping, every financial transaction affects at least two accounts to maintain the fundamental accounting equation: **Assets = Liabilities + Equity**.\n\n"
                "#### Traditional Classification (Golden Rules):\n"
                "1. **Real Accounts (Assets & Properties):** Debit what comes in, Credit what goes out.\n"
                "2. **Personal Accounts (Persons, Firms, Entities):** Debit the receiver, Credit the giver.\n"
                "3. **Nominal Accounts (Expenses, Incomes, Gains, Losses):** Debit all expenses and losses, Credit all incomes and gains.\n\n"
                "#### Modern Classification:\n"
                "- **Debits Increase:** Assets, Expenses, and Dividends/Drawings.\n"
                "- **Credits Increase:** Liabilities, Revenues/Income, and Equity/Capital.\n\n"
                "Whenever you record an entry, the total debits must always balance the total credits."
            ),
            "evidence": ["Standard Double-Entry Bookkeeping Principles", "ICAI / GAAP Framework"],
            "recommended_actions": [
                "Verify that total debits equal total credits for every posted journal voucher.",
                "Review account classification (Asset vs Expense, Liability vs Income).",
            ],
        },
        "gst": {
            "keywords": [
                "what is gst", "explain gst", "gst", "goods and services tax",
                "input tax credit", "what is itc", "cgst", "sgst", "igst"
            ],
            "title": "Goods and Services Tax (GST) Framework",
            "message": (
                "### Understanding Goods and Services Tax (GST)\n\n"
                "GST is a destination-based, comprehensive indirect tax levied on the supply of goods and services in India.\n\n"
                "#### Dual GST Structure:\n"
                "- **Intra-State Supply (Within Same State):** Tax is split equally between **CGST** (Central GST) and **SGST/UTGST** (State/Union Territory GST).\n"
                "- **Inter-State Supply (Between Different States):** Levied as **IGST** (Integrated GST) collected by the Central Government.\n\n"
                "#### Input Tax Credit (ITC):\n"
                "- Businesses can offset GST paid on business purchases (Input Tax) against GST collected on outward sales (Output Tax).\n"
                "- **Reconciliation Rule:** ITC claimed in GSTR-3B must be reconciled against supplier invoices appearing in auto-drafted **GSTR-2B**.\n\n"
                "#### Core Compliance Cycle:\n"
                "1. **GSTR-1:** Outward supplies/sales return.\n"
                "2. **GSTR-2B:** Static auto-drafted buyer ITC statement.\n"
                "3. **GSTR-3B:** Monthly summary tax return and tax payment."
            ),
            "evidence": ["Central Goods and Services Tax Act, 2017", "CBIC GST Compliance Framework"],
            "recommended_actions": [
                "Reconcile Purchase Register with GSTR-2B before claiming Input Tax Credit.",
                "Verify supplier GSTIN validity and filing status.",
                "Ensure correct HSN/SAC codes and tax rate slabs (5%, 12%, 18%, 28%).",
            ],
        },
        "depreciation": {
            "keywords": [
                "what is depreciation", "explain depreciation", "depreciation",
                "methods of depreciation", "written down value", "straight line method",
                "wdv", "slm", "schedule ii"
            ],
            "title": "Depreciation Concepts and Methods",
            "message": (
                "### Understanding Depreciation in Accounting\n\n"
                "Depreciation is the systematic allocation of the depreciable amount of a tangible fixed asset over its estimated useful economic life.\n\n"
                "#### Primary Calculation Methods:\n"
                "1. **Straight Line Method (SLM):** Allocates an equal amount of depreciation each year.\n"
                "   $$\\text{Annual Depreciation} = \\frac{\\text{Cost} - \\text{Residual Value}}{\\text{Useful Life}}$$\n"
                "2. **Written Down Value Method (WDV / Diminishing Balance):** Applies a fixed percentage rate to the declining net book value of the asset each period, charging higher depreciation in earlier years.\n\n"
                "#### Regulatory Frameworks in India:\n"
                "- **Companies Act, 2013 (Schedule II):** Depreciation based on the useful life of the asset.\n"
                "- **Income Tax Act, 1961 (Section 32):** Mandatory WDV method applied on prescribed **Blocks of Assets**.\n\n"
                "#### Standard Accounting Entry:\n"
                "- **Debit:** Depreciation Expense Account (Nominal A/c)\n"
                "- **Credit:** Accumulated Depreciation / Fixed Asset Account"
            ),
            "evidence": ["AS 10 / Ind AS 16 (Property, Plant and Equipment)", "Companies Act 2013 Schedule II", "Income Tax Act 1961 Section 32"],
            "recommended_actions": [
                "Verify whether financial reporting uses SLM or WDV in the Fixed Asset Register.",
                "Compute deferred tax differences if book depreciation differs from Income Tax Act block depreciation.",
            ],
        },
        "reconciliation": {
            "keywords": [
                "what is reconciliation", "explain reconciliation", "why reconcile", "reconciliation meaning",
                "why is my bank reconciliation showing a mismatch", "why is reconciliation showing a mismatch",
                "why is there a reconciliation mismatch", "reconciliation mismatch", "bank reconciliation mismatch",
                "why is my reconciliation showing a mismatch"
            ],
            "title": "Bank and Ledger Reconciliation",
            "message": (
                "### Understanding Financial Reconciliation\n\n"
                "Reconciliation is an accounting control process that compares two sets of independent financial records to ensure accuracy, agreement, and completeness.\n\n"
                "#### Common Types of Reconciliation:\n"
                "- **Bank Reconciliation:** Matching internal cash book/ledger entries with official bank statements.\n"
                "- **Vendor / Customer Ledger Reconciliation:** Comparing statement of accounts between buyer and seller.\n"
                "- **Intercompany Reconciliation:** Balancing transactions across subsidiary and parent legal entities.\n\n"
                "#### Primary Objectives:\n"
                "1. Detect unrecorded entries (e.g., bank charges, direct debits, interest credits).\n"
                "2. Identify timing delays (unpresented cheques, outstation clearance in transit).\n"
                "3. Catch clerical transposition mistakes or unauthorized transactions."
            ),
            "evidence": ["Standard Accounting Internal Controls", "Audit & Assurance Standards"],
            "recommended_actions": [
                "Perform bank reconciliation at regular closing intervals (monthly/weekly).",
                "Investigate un-reconciled items outstanding beyond normal clearing cycles.",
            ],
        },
        "amount_mismatch": {
            "keywords": ["explain amount mismatch", "what is amount mismatch", "amount mismatch", "mismatch in amounts"],
            "title": "Causes and Investigation of Amount Mismatches",
            "message": (
                "### Amount Mismatches in Accounting\n\n"
                "An amount mismatch occurs when a transaction exists in both comparison sources (e.g., bank statement and accounting ledger), but the reported numerical values do not match.\n\n"
                "#### Frequent Causes:\n"
                "1. **Transposition Errors:** Reversing adjacent digits (e.g., typing ₹6,890 instead of ₹8,690; variance is divisible by 9).\n"
                "2. **Partial Settlements / Deductions:** A customer paid net of TDS, payment gateway fees, or bank exchange commissions.\n"
                "3. **Incorrect Rounding / Foreign Exchange:** Round-off discrepancies or fluctuating FX conversion rates.\n"
                "4. **Split Invoices / Multiple Line Items:** A single lump-sum bank clearance representing multiple individual ledger vouchers."
            ),
            "evidence": ["Reconciliation Variance Analysis", "Voucher Audit Best Practices"],
            "recommended_actions": [
                "Check whether the discrepancy is divisible by 9 to test for number transposition.",
                "Verify supporting invoices for tax deductions (TDS, TCS) or bank service fees.",
                "Review payment advice receipts and remittance notices.",
            ],
        },
        "ledger_difference": {
            "keywords": ["ledger difference", "what could cause a ledger difference", "difference in ledger"],
            "title": "Causes of General Ledger Variances",
            "message": (
                "### Common Causes of Ledger Differences\n\n"
                "When an accounting ledger does not reconcile with an external statement or sub-ledger schedule, accountants typically examine the following factors:\n\n"
                "1. **Timing Differences:** Checks issued but not yet cleared; deposits made on the cutoff date but settled next period.\n"
                "2. **Unposted Direct Entries:** Bank service charges, loan interest debits, or direct customer NEFT receipts not yet entered into accounting software.\n"
                "3. **Duplicate Bookings:** Accidental duplicate voucher entry for the same vendor invoice.\n"
                "4. **Posting to Wrong Account Head:** Debiting an expense under 'Office Supplies' instead of 'Repairs & Maintenance', or misallocating between accounts.\n"
                "5. **Cut-off Period Errors:** Recording an invoice in March 2026 when the delivery occurred in April 2026."
            ),
            "evidence": ["Standard Audit Verification Protocol"],
            "recommended_actions": [
                "Obtain bank confirmation certificates and external party statements.",
                "Inspect cutoff procedures around closing dates.",
            ],
        },
        "trial_balance": {
            "keywords": [
                "trial balance", "what is a trial balance", "what is trial balance", "trial balance difference",
                "why can a trial balance have equal debit and credit totals while errors still exist",
                "why can a trial balance have equal debit and credit",
                "why trial balance balances with errors",
                "errors not disclosed by trial balance",
                "errors in trial balance",
            ],
            "title": "Trial Balance Overview & Balancing",
            "message": (
                "### Understanding the Trial Balance\n\n"
                "A Trial Balance is an internal worksheet listing the debit and credit closing balances of all general ledger accounts at a specific cutoff date.\n\n"
                "#### Fundamental Rule:\n"
                "- Total Debit Balances must exactly equal Total Credit Balances.\n"
                "- When both sides balance, it proves arithmetical accuracy but does **not** guarantee the complete absence of accounting errors.\n\n"
                "#### Errors That Still Allow a Trial Balance to Agree:\n"
                "1. **Errors of Omission:** A transaction was completely omitted from both debit and credit sides (e.g., an unrecorded cash purchase).\n"
                "2. **Errors of Commission:** Posting the correct amount on the right side, but into the wrong subsidiary account (e.g., debiting Supplier A instead of Supplier B).\n"
                "3. **Errors of Principle:** Violating fundamental accounting concepts (e.g., capitalizing repairs expense into Fixed Assets, or treating revenue receipt as capital).\n"
                "4. **Compensating Errors:** Two or more unrelated errors of equal magnitude that inadvertently cancel each other out.\n"
                "5. **Errors of Original Entry:** An incorrect figure entered in the prime book and posted to both debit and credit equally."
            ),
            "evidence": ["Double-entry Trial Balance Mechanics", "ICAI Accounting Standards Framework"],
            "recommended_actions": [
                "Verify whether debit and credit totals agree.",
                "Review journal vouchers posted to temporary Suspense Accounts.",
                "Conduct bank reconciliation and sub-ledger schedule verification.",
            ],
        },
        "balance_sheet": {
            "keywords": [
                "what is a balance sheet", "what is balance sheet", "explain balance sheet",
                "balance sheet meaning", "purpose of a balance sheet", "components of balance sheet"
            ],
            "title": "Understanding the Balance Sheet",
            "message": (
                "### Understanding the Balance Sheet\n\n"
                "A Balance Sheet is a principal financial statement that provides a snapshot of a company's financial position at a specific point in time (as of a given date).\n\n"
                "#### The Fundamental Accounting Equation:\n"
                "$$\\mathbf{Total\\ Assets = Total\\ Liabilities + Equity}$$\n\n"
                "#### Key Components (Schedule III to Companies Act, 2013 / Ind AS 1):\n"
                "1. **Equity and Liabilities:**\n"
                "   - **Shareholders' Funds / Equity:** Share capital, retained earnings, reserves & surplus.\n"
                "   - **Non-Current Liabilities:** Long-term borrowings, deferred tax liabilities, long-term provisions.\n"
                "   - **Current Liabilities:** Short-term borrowings, Trade Payables (Sundry Creditors), statutory dues, and accruals.\n\n"
                "2. **Assets:**\n"
                "   - **Non-Current Assets:** Property, Plant & Equipment (PPE), capital work-in-progress, intangible assets, long-term investments.\n"
                "   - **Current Assets:** Inventories, Trade Receivables (Sundry Debtors), cash and cash equivalents, short-term loans & advances.\n\n"
                "#### Purpose & Importance:\n"
                "The Balance Sheet reveals solvency, liquidity, capital structure, and asset backing for investors, lenders, and regulatory authorities."
            ),
            "evidence": ["Schedule III Companies Act 2013", "Ind AS 1 / AS 1 Framework"],
            "recommended_actions": [
                "Verify that Total Assets strictly balance Total Liabilities and Equity.",
                "Cross-reference line items against detailed Notes to Accounts schedules.",
            ],
        },
        "receivables_payables": {
            "keywords": [
                "difference between receivables and payables", "receivables and payables",
                "what is the difference between receivables and payables",
                "trade receivables and payables", "debtors and creditors",
                "difference between debtors and creditors", "accounts receivable vs accounts payable"
            ],
            "title": "Difference Between Receivables and Payables",
            "message": (
                "### Difference Between Receivables and Payables\n\n"
                "Trade Receivables and Trade Payables represent opposite sides of commercial credit relationships in business operations.\n\n"
                "| Criteria | Trade Receivables (Sundry Debtors) | Trade Payables (Sundry Creditors) |\n"
                "|---|---|---|\n"
                "| **Definition** | Amounts owed **to** the business by customers for credit sales. | Amounts owed **by** the business to suppliers/vendors for credit purchases. |\n"
                "| **Balance Sheet Nature** | **Current Asset** (future cash inflow) | **Current Liability** (future cash outflow) |\n"
                "| **Normal Balance** | **Debit** balance | **Credit** balance |\n"
                "| **Key Control Metric** | Days Sales Outstanding (DSO) & Aging Analysis | Days Payable Outstanding (DPO) & Payment Terms |\n"
                "| **Risk Factors** | Bad debts, default, delayed client collections | Late payment interest, vendor supply disruption, lost cash discounts |\n\n"
                "#### Working Capital Impact:\n"
                "Effective working capital management balances timely collection of receivables against optimized settlement of payables to maintain positive operational cash flow."
            ),
            "evidence": ["Working Capital Cycle Management", "ICAI Balance Sheet Presentation"],
            "recommended_actions": [
                "Review aging schedules for debtors (>180 days) for expected credit loss (ECL) provisioning.",
                "Reconcile vendor statements of accounts against Trade Payables balances.",
            ],
        },
        "missing_transaction": {
            "keywords": ["missing transaction", "missing record", "what should i verify when there is a missing transaction"],
            "title": "Verifying Missing Transactions",
            "message": (
                "### Verification Protocol for Missing Transactions\n\n"
                "When a transaction appears on a bank statement or vendor record but is missing in the internal accounting ledger:\n\n"
                "1. **Trace Transaction Reference:** Search internal ERP / accounting software by UTR, cheque number, or invoice reference.\n"
                "2. **Check Date Thresholds:** Verify whether the transaction was posted in an adjacent accounting month or fiscal year.\n"
                "3. **Inspect Suspense / Unclassified Heads:** Review 'Suspense Account', 'Bank Clearing Account', or 'Unallocated Receipts'.\n"
                "4. **Confirm Authorization:** Determine whether the transaction was an automated debit (e.g., standing instructions, EMI, direct tax payment).\n"
                "5. **Pass Required Adjustment Voucher:** Once verified, enter a journal or payment voucher with proper supporting documentation."
            ),
            "evidence": ["Audit Trail Compliance", "Standard Accounting Procedures"],
            "recommended_actions": [
                "Search accounting records by reference number and exact transaction amount.",
                "Examine bank advice / payment receipts before posting an adjustment entry.",
            ],
        },
        "balance_sheet_mismatch": {
            "keywords": [
                "balance sheet not balancing", "balance sheet mismatch", "why balance sheet not balancing",
                "balance sheet difference", "schedule iii mismatch", "assets do not equal liabilities"
            ],
            "title": "Investigating Balance Sheet Mismatch",
            "message": (
                "### Balance Sheet Reconciliation Protocol\n\n"
                "Under Schedule III of the Companies Act and standard accounting principles, **Total Assets MUST equal Total Equity and Liabilities**.\n\n"
                "#### Diagnostic Checklist:\n"
                "1. **Retained Earnings / Current Year Profit:** Verify whether the current year's Profit/Loss from the P&L statement has been transferred to Reserves & Surplus under Equity.\n"
                "2. **Unclassified Line Items:** Evidence indicates that line items without explicit Schedule III classification may be omitted from asset or liability totals.\n"
                "3. **Single-Sided Adjustments:** Check for unilateral closing journal entries that altered one ledger account without an offsetting debit or credit.\n"
                "4. **Opening Balance Discrepancies:** Verify that previous fiscal year closing balances equal the current year opening balances.\n\n"
                "> [!NOTE]\n"
                "> AI Assistant cannot make final accounting decisions or silently modify balances. Requires accountant verification."
            ),
            "evidence": ["Schedule III, Companies Act 2013", "Ind AS 1 / AS 1 Presentation of Financial Statements"],
            "recommended_actions": [
                "Inspect the Trial Balance difference in the Review Center.",
                "Verify the Retained Earnings transfer from the Profit & Loss statement.",
                "Check for unclassified ledger accounts in the Balance Sheet schedule.",
            ],
        },
        "trial_balance_unbalanced": {
            "keywords": [
                "trial balance not balancing", "trial balance difference", "why trial balance unbalanced",
                "trial balance error", "debits not equal credits"
            ],
            "title": "Investigating Trial Balance Discrepancies",
            "message": (
                "### Trial Balance Verification Protocol\n\n"
                "A Trial Balance is mathematically sound only when **Total Debits = Total Credits**.\n\n"
                "#### Systematic Root-Cause Analysis:\n"
                "1. **Transposition Error:** If the variance is divisible by 9, digits may have been inverted during data entry (e.g. ₹54 entered as ₹45).\n"
                "2. **Single-Sided Posting:** If the variance equals an exact transaction amount, a journal entry was posted to only one ledger side.\n"
                "3. **Double Difference Error:** If the variance is divisible by 2, a debit entry may have been mistakenly recorded in the credit column, or vice-versa.\n"
                "4. **Omitted Opening Balance:** Verify bank, cash, or loan opening balances imported from the previous financial year.\n\n"
                "> [!IMPORTANT]\n"
                "> LiteBooks enforces immutable source files and will never automatically balance a Trial Balance. Requires accountant review and voucher adjustment."
            ),
            "evidence": ["Double-Entry Principles", "ICAI Guidance Note on Trial Balance Preparation"],
            "recommended_actions": [
                "Review the Review Center for 'TRIAL_BALANCE_UNBALANCED' findings.",
                "Trace the variance to individual ledger vouchers.",
                "Verify whether any imported rows lacked debit or credit amounts.",
            ],
        },
    }

    @classmethod
    def get_matched_explanation(cls, user_message: str) -> Optional[Tuple[str, List[str], List[str]]]:
        """Returns (formatted_message, evidence, recommended_actions) ONLY if a conceptual keyword match is found, else None."""
        import re
        msg = user_message.strip().lower()
        clean_msg = re.sub(r"[^\w\s]", " ", msg)
        clean_msg = " ".join(clean_msg.split())

        best_match = None
        longest_match_len = 0

        for key, data in cls.RESPONSES.items():
            for kw in data["keywords"]:
                if kw in msg or kw in clean_msg:
                    if len(kw) > longest_match_len:
                        longest_match_len = len(kw)
                        best_match = (data["message"], data["evidence"], data["recommended_actions"])
        return best_match

    @classmethod
    def get_explanation(cls, user_message: str) -> Optional[Tuple[str, List[str], List[str]]]:
        """Returns (formatted_message, evidence, recommended_actions) if a standard match is found."""
        matched = cls.get_matched_explanation(user_message)
        if matched:
            return matched

        # Default general professional response
        default_message = (
            "### Financial Assistant Guidance\n\n"
            "I can assist with your accounting questions, financial statement analysis, "
            "and reconciliation workflows.\n\n"
            "You can:\n"
            "- Ask conceptual accounting questions (e.g. *'What is a debit?'*, *'Explain amount mismatch'*)\n"
            "- Attach a financial workbook (XLSX, CSV) to analyze Balance Sheets, P&L, or Ledgers\n"
            "- Attach two files (e.g., Bank Statement and Ledger) to run deterministic reconciliation\n"
            "- Detect missing records, compute variances, and prepare audit correction proposals."
        )
        default_evidence = ["Finance AI Core Knowledge"]
        default_actions = [
            "Attach an Excel or CSV file to explore file-aware analysis.",
            "Ask specific questions about your financial records.",
        ]
        return default_message, default_evidence, default_actions
