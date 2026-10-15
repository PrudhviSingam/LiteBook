import io
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import openpyxl
from openpyxl.utils import get_column_letter
import pandas as pd

from app.modules.reconciliation.financial_validator import FinancialValidator, format_currency_inr
from app.modules.reconciliation.normalization import (
    clean_header,
    deduplicate_columns,
    normalize_column_name,
    serialize_scalar,
)
from app.modules.reconciliation.schemas import (
    ClassificationEvidence,
    DiscrepancySeverityEnum,
    DiscrepancyTypeEnum,
    DocumentTypeEnum,
    FinancialCellProvenance,
    FinancialPeriod,
    FinancialRow,
    FinancialTable,
    SheetInspectionInfo,
    StandardDiscrepancy,
    WorkbookInspectionResult,
)

# Performance safeguards
MAX_ROWS = 50000
MAX_COLUMNS = 100
MAX_SHEETS = 50

INDIAN_CURRENCY_REGEX = re.compile(r"₹?\s*\(?-?[\d,]+(?:\.\d+)?\)?")
FINANCIAL_PERIOD_REGEX = re.compile(
    r"(?:\b(?:31|30|28|29)(?:st|nd|rd|th)?\s+(?:january|february|march|april|may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec)\b|\b\d{1,2}[-/](?:0?[1-9]|1[0-2])[-/]\d{2,4}\b|fy\s*\d{4}-\d{2,4}|fy\s*\d{2}-\d{2}|\b20\d{2}-20\d{2}\b|\b20\d{2}-\d{2}\b|as\s+at\s+31|for\s+the\s+year\s+ended)",
    re.IGNORECASE,
)


def parse_indian_currency(val: Any) -> Optional[float]:
    """Safely extracts a numeric float from Indian currency formatted strings or numbers.

    Handles ₹1,63,21,678.06, (1,678.00), -1,250, Rs. 1,250, 18%, Dr/Cr tags, and standard floats.
    """
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s:
        return None

    # Percentage support (e.g., 18% -> 0.18)
    if s.endswith("%"):
        clean_pct = re.sub(r"[^\d.-]", "", s[:-1])
        try:
            return round(float(clean_pct) / 100.0, 6)
        except ValueError:
            return None

    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()
    elif s.endswith("Dr") or s.endswith("dr") or s.endswith("DR"):
        is_negative = True
        s = s[:-2].strip()
    elif s.endswith("Cr") or s.endswith("cr") or s.endswith("CR"):
        is_negative = False
        s = s[:-2].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Clean out currency symbols, commas, and prefixes
    cleaned = re.sub(r"[₹$,\s]", "", s)
    cleaned = re.sub(r"^(?:rs\.?|inr)\s*", "", cleaned, flags=re.IGNORECASE)
    try:
        num = float(cleaned)
        return -num if is_negative else num
    except (ValueError, TypeError):
        return None


def parse_indian_number(val: Any) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """Returns (normalized_value, raw_str, unit).

    Preserves the raw value for audit/provenance while normalizing the float.
    """
    if val is None or pd.isna(val):
        return None, None, None
    raw_str = str(val).strip()
    num = parse_indian_currency(val)
    unit = "INR" if ("₹" in raw_str or "rs" in raw_str.lower() or "inr" in raw_str.lower()) else "ACTUAL"
    return num, raw_str, unit


def format_indian_currency(amount: Optional[float]) -> str:
    """Formats a float into standard Indian numbering system format (e.g. ₹1,63,21,678.06)."""
    return format_currency_inr(amount)


class FinancialPeriodDetector:
    """Detects and normalizes financial periods from filenames, sheet names, and headers.

    Supports Indian Financial Year (April 1 -> March 31).
    """

    @classmethod
    def detect_period(
        cls,
        text_corpus: List[str],
        filename: Optional[str] = None,
        sheet_names: Optional[List[str]] = None,
    ) -> FinancialPeriod:
        corpus_combined = " ".join(text_corpus)
        if filename:
            corpus_combined += " " + filename
        if sheet_names:
            corpus_combined += " " + " ".join(sheet_names)

        found_fys: Set[str] = set()

        # 1. Look for explicit FY patterns: FY 2025-26, 2025-26, FY 25-26, FY2025-26
        fy_matches = re.findall(r"(?:^|[^a-zA-Z0-9])fy\s*(\d{4})-(\d{2,4})\b", corpus_combined, re.IGNORECASE)
        for m in fy_matches:
            y1, y2 = m
            if len(y2) == 2:
                y2 = str(int(y1[:2]) * 100 + int(y2))
            found_fys.add(f"{y1}-{y2[-2:]}")

        # Short FY format: FY 25-26
        fy_short = re.findall(r"(?:^|[^a-zA-Z0-9])fy\s*(\d{2})-(\d{2})\b", corpus_combined, re.IGNORECASE)
        for m in fy_short:
            y1, y2 = m
            full_y1 = f"20{y1}"
            found_fys.add(f"{full_y1}-{y2}")

        # Year-range format without FY prefix: 2025-26 or 2025-2026
        yr_matches = re.findall(r"\b(20\d{2})-(20\d{2}|\d{2})\b", corpus_combined)
        for m in yr_matches:
            y1, y2 = m
            if len(y2) == 2:
                y2 = str(int(y1[:2]) * 100 + int(y2))
            if int(y2) == int(y1) + 1:
                found_fys.add(f"{y1}-{y2[-2:]}")

        # Date range format: 01/04/2025 - 31/03/2026 or 01-04-2025 to 31-03-2026
        dt_range = re.findall(
            r"01[-/.]04[-/.](20\d{2})\s*(?:to|-)\s*31[-/.]03[-/.](20\d{2})",
            corpus_combined,
            re.IGNORECASE,
        )
        for m in dt_range:
            y1, y2 = m
            found_fys.add(f"{y1}-{y2[-2:]}")

        # Month text format: Apr 2025 - Mar 2026
        month_range = re.findall(
            r"apr(?:il)?\s*(20\d{2})\s*(?:to|-)\s*mar(?:ch)?\s*(20\d{2})",
            corpus_combined,
            re.IGNORECASE,
        )
        for m in month_range:
            y1, y2 = m
            found_fys.add(f"{y1}-{y2[-2:]}")

        # As at 31 March 2026 or For the year ended 31 March 2026
        as_at = re.findall(
            r"(?:as\s+at|ended|ending)\s+31(?:st)?\s+march\s+(20\d{2})",
            corpus_combined,
            re.IGNORECASE,
        )
        for y2 in as_at:
            y1 = str(int(y2) - 1)
            found_fys.add(f"{y1}-{y2[-2:]}")

        # Check for conflict: multiple distinct FYs without comparative schedule context
        if len(found_fys) > 1:
            # Check if this is a standard 2-year comparative financial statement
            sorted_fys = sorted(list(found_fys))
            # If consecutive, it is likely a standard comparative statement (e.g. FY 24-25 and FY 25-26)
            # We pick the latest period as primary, but note both
            latest_fy = sorted_fys[-1]
            y1, y2_short = latest_fy.split("-")
            y2 = f"{y1[:2]}{y2_short}"
            return FinancialPeriod(
                period_type="FINANCIAL_YEAR",
                raw_text=f"FY {latest_fy} (Comparative: {', '.join(sorted_fys)})",
                start_date=f"{y1}-04-01",
                end_date=f"{y2}-03-31",
                financial_year=latest_fy,
                confidence="HIGH",
                source="corpus",
                status="ready",
            )
        elif len(found_fys) == 1:
            fy = list(found_fys)[0]
            y1, y2_short = fy.split("-")
            y2 = f"{y1[:2]}{y2_short}"
            return FinancialPeriod(
                period_type="FINANCIAL_YEAR",
                raw_text=f"FY {fy}",
                start_date=f"{y1}-04-01",
                end_date=f"{y2}-03-31",
                financial_year=fy,
                confidence="HIGH",
                source="headers",
                status="ready",
            )

        return FinancialPeriod(
            period_type="UNKNOWN",
            raw_text="Unspecified Period",
            confidence="LOW",
            source="none",
            status="ready",
        )


class DocumentClassifier:
    """Deterministic, evidence-based document classifier.

    Evaluates 11 discrete classifications with explicit signals and explanations.
    Never relies on an LLM for authoritative classification.
    """

    @classmethod
    def classify(
        cls,
        corpus: str,
        sheet_name: str,
        has_withdrawal_deposit: bool = False,
    ) -> Tuple[DocumentTypeEnum, ClassificationEvidence]:
        corpus_lower = (corpus + " " + sheet_name).lower()
        signals: List[str] = []

        # 1. CASH FLOW
        cf_signals = []
        if "cash flow" in corpus_lower or "cash flows" in corpus_lower:
            cf_signals.append("contains 'cash flow'")
        if "operating activities" in corpus_lower:
            cf_signals.append("contains 'operating activities'")
        if "investing activities" in corpus_lower:
            cf_signals.append("contains 'investing activities'")
        if "financing activities" in corpus_lower:
            cf_signals.append("contains 'financing activities'")
        if len(cf_signals) >= 2 or "cash flow" in sheet_name.lower():
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.CASH_FLOW,
                confidence="HIGH" if len(cf_signals) >= 2 else "MEDIUM",
                signals_found=cf_signals or ["sheet title indicates Cash Flow"],
                explanation=f"Identified Cash Flow statement based on: {', '.join(cf_signals)}.",
                score=0.9,
            )
            return DocumentTypeEnum.CASH_FLOW, evidence

        # 2. TAX DOCUMENT
        tax_signals = []
        for kw in ("gstr-1", "gstr-3b", "gstin", "26as", "tax invoice", "income tax return", "itr-", "tds certificate"):
            if kw in corpus_lower:
                tax_signals.append(f"contains '{kw}'")
        if len(tax_signals) >= 1:
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.TAX_DOCUMENT,
                confidence="HIGH" if len(tax_signals) >= 2 else "MEDIUM",
                signals_found=tax_signals,
                explanation=f"Identified Tax Document based on: {', '.join(tax_signals)}.",
                score=0.85,
            )
            return DocumentTypeEnum.TAX_DOCUMENT, evidence

        # 3. BALANCE SHEET
        bs_signals = []
        if "balance sheet" in corpus_lower:
            bs_signals.append("contains 'balance sheet'")
        if "statement of assets and liabilities" in corpus_lower:
            bs_signals.append("contains 'statement of assets and liabilities'")
        if "equity and liabilities" in corpus_lower or "equity & liabilities" in corpus_lower:
            bs_signals.append("contains 'equity and liabilities'")
        if "current liabilities" in corpus_lower or "trade payables" in corpus_lower:
            bs_signals.append("contains 'liabilities line items'")
        if "fixed assets" in corpus_lower or "tangible fixed assets" in corpus_lower:
            bs_signals.append("contains 'fixed assets'")
        if "total assets" in corpus_lower:
            bs_signals.append("contains 'total assets'")
        if "total liabilities" in corpus_lower:
            bs_signals.append("contains 'total liabilities'")

        if len(bs_signals) >= 2 or "balance sheet" in sheet_name.lower():
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.BALANCE_SHEET,
                confidence="HIGH" if ("balance sheet" in corpus_lower or len(bs_signals) >= 3) else "MEDIUM",
                signals_found=bs_signals or ["sheet title indicates Balance Sheet"],
                explanation=f"Identified Balance Sheet based on: {', '.join(bs_signals)}.",
                score=0.95,
            )
            return DocumentTypeEnum.BALANCE_SHEET, evidence

        # 4. PROFIT & LOSS
        pl_signals = []
        if "profit and loss" in corpus_lower or "profit & loss" in corpus_lower or "p&l" in corpus_lower:
            pl_signals.append("contains 'profit and loss'")
        if "statement of profit and loss" in corpus_lower:
            pl_signals.append("contains 'statement of profit and loss'")
        if "revenue from operations" in corpus_lower:
            pl_signals.append("contains 'revenue from operations'")
        if "other income" in corpus_lower:
            pl_signals.append("contains 'other income'")
        if "total expenses" in corpus_lower:
            pl_signals.append("contains 'total expenses'")
        if "net profit" in corpus_lower or "ebitda" in corpus_lower:
            pl_signals.append("contains 'net profit / ebitda'")

        if len(pl_signals) >= 2 or any(k in sheet_name.lower() for k in ("profit", "p&l", "income statement")):
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.PROFIT_LOSS,
                confidence="HIGH" if len(pl_signals) >= 2 else "MEDIUM",
                signals_found=pl_signals or ["sheet title indicates Profit & Loss"],
                explanation=f"Identified Profit & Loss statement based on: {', '.join(pl_signals)}.",
                score=0.92,
            )
            return DocumentTypeEnum.PROFIT_LOSS, evidence

        # 5. TRIAL BALANCE
        tb_signals = []
        if "trial balance" in corpus_lower or "trial balance" in sheet_name.lower():
            tb_signals.append("contains 'trial balance'")
        if "opening balance" in corpus_lower and "closing balance" in corpus_lower and not has_withdrawal_deposit:
            tb_signals.append("contains opening and closing balances across accounts")
        if "debit" in corpus_lower and "credit" in corpus_lower and "ledger account" in corpus_lower:
            tb_signals.append("contains debit/credit ledger accounts")

        if len(tb_signals) >= 1:
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.TRIAL_BALANCE,
                confidence="HIGH" if "trial balance" in corpus_lower else "MEDIUM",
                signals_found=tb_signals,
                explanation=f"Identified Trial Balance based on: {', '.join(tb_signals)}.",
                score=0.9,
            )
            return DocumentTypeEnum.TRIAL_BALANCE, evidence

        # 6. BANK STATEMENT
        bank_signals = []
        if has_withdrawal_deposit or ("withdrawal" in corpus_lower and "deposit" in corpus_lower):
            bank_signals.append("contains withdrawal and deposit columns")
        if "bank statement" in corpus_lower or "bank statement" in sheet_name.lower():
            bank_signals.append("contains 'bank statement'")
        if "cheque no" in corpus_lower or "chq no" in corpus_lower:
            bank_signals.append("contains cheque number column")
        if "value date" in corpus_lower:
            bank_signals.append("contains value date column")

        if len(bank_signals) >= 1 or "bank" in sheet_name.lower():
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.BANK_STATEMENT,
                confidence="HIGH" if len(bank_signals) >= 2 else "MEDIUM",
                signals_found=bank_signals or ["sheet title indicates Bank Statement"],
                explanation=f"Identified Bank Statement based on: {', '.join(bank_signals)}.",
                score=0.9,
            )
            return DocumentTypeEnum.BANK_STATEMENT, evidence

        # 7. GENERAL LEDGER / ACCOUNTING LEDGER
        gl_signals = []
        if "general ledger" in corpus_lower:
            gl_signals.append("contains 'general ledger'")
        if "chart of accounts" in corpus_lower or "gl code" in corpus_lower:
            gl_signals.append("contains chart of accounts / GL codes")
        if gl_signals:
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.GENERAL_LEDGER,
                confidence="HIGH",
                signals_found=gl_signals,
                explanation=f"Identified General Ledger based on: {', '.join(gl_signals)}.",
                score=0.88,
            )
            return DocumentTypeEnum.GENERAL_LEDGER, evidence

        ledger_signals = []
        if "voucher" in corpus_lower or "vch no" in corpus_lower or "vch" in corpus_lower:
            ledger_signals.append("contains voucher reference")
        if "particulars" in corpus_lower and ("debit" in corpus_lower or "credit" in corpus_lower):
            ledger_signals.append("contains particulars with debit/credit columns")
        if ledger_signals:
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.ACCOUNTING_LEDGER,
                confidence="HIGH" if len(ledger_signals) >= 2 else "MEDIUM",
                signals_found=ledger_signals,
                explanation=f"Identified Accounting Ledger based on: {', '.join(ledger_signals)}.",
                score=0.85,
            )
            return DocumentTypeEnum.ACCOUNTING_LEDGER, evidence

        # Fallback date + amount columns
        if "date" in corpus_lower and ("amount" in corpus_lower or "debit" in corpus_lower or "credit" in corpus_lower):
            evidence = ClassificationEvidence(
                document_type=DocumentTypeEnum.ACCOUNTING_LEDGER,
                confidence="MEDIUM",
                signals_found=["contains date and transaction amount columns"],
                explanation="Classified as Accounting Ledger due to transaction date and amount columns.",
                score=0.7,
            )
            return DocumentTypeEnum.ACCOUNTING_LEDGER, evidence

        # UNKNOWN
        evidence = ClassificationEvidence(
            document_type=DocumentTypeEnum.UNKNOWN,
            confidence="LOW",
            signals_found=["insufficient accounting terminology"],
            explanation="Unrecognized document structure. Requires manual accountant review.",
            score=0.2,
        )
        return DocumentTypeEnum.UNKNOWN, evidence


class WorkbookInspector:
    """Inspects complex real-world accounting workbooks, detecting sheets, titles,

    periods, merged cells, units (INR, Lakhs, Crores), extracting structured financial
    tables with cell provenance, and running deterministic financial validations.
    """

    @classmethod
    def inspect(
        cls,
        file_bytes_or_path: Union[Path, str, bytes],
        filename: str,
        upload_category: Optional[str] = None,
    ) -> WorkbookInspectionResult:
        ext = Path(filename).suffix.lower()

        if ext in (".xlsx", ".xls", ".xlsm"):
            return cls._inspect_excel(file_bytes_or_path, filename, upload_category)
        elif ext in (".csv", ".txt"):
            return cls._inspect_csv(file_bytes_or_path, filename, upload_category)
        elif ext == ".pdf":
            return WorkbookInspectionResult(
                filename=filename,
                total_sheets=0,
                sheets=[],
                recommended_sheet="None",
                document_type=DocumentTypeEnum.UNKNOWN,
                header_row_index=0,
                confidence="LOW",
                status="ready",
                message="PDF uploaded successfully. Detailed financial extraction is not yet available.",
            )
        else:
            return WorkbookInspectionResult(
                filename=filename,
                total_sheets=0,
                sheets=[],
                recommended_sheet="None",
                document_type=DocumentTypeEnum.UNKNOWN,
                header_row_index=0,
                confidence="LOW",
                status="REVIEW_REQUIRED",
                message=f"Unsupported file format '{ext}'. Supported formats: XLSX, XLS, CSV, PDF.",
            )

    @classmethod
    def _inspect_excel(
        cls,
        file_bytes_or_path: Union[Path, str, bytes],
        filename: str,
        upload_category: Optional[str] = None,
    ) -> WorkbookInspectionResult:
        if isinstance(file_bytes_or_path, (str, Path)):
            with open(file_bytes_or_path, "rb") as f:
                content = f.read()
        else:
            content = file_bytes_or_path

        buffer_data = io.BytesIO(content)
        buffer_form = io.BytesIO(content)

        wb_data = None
        wb_form = None
        sheet_names: List[str] = []
        merged_sheets: Dict[str, bool] = {}

        try:
            wb_data = openpyxl.load_workbook(buffer_data, read_only=False, data_only=True)
            sheet_names = wb_data.sheetnames
            for name in sheet_names:
                ws = wb_data[name]
                merged_sheets[name] = bool(len(ws.merged_cells.ranges) > 0)
        except Exception:
            buffer_data.seek(0)
            try:
                engine = "xlrd" if filename.lower().endswith(".xls") else None
                xl = pd.ExcelFile(buffer_data, engine=engine) if engine else pd.ExcelFile(buffer_data)
                sheet_names = xl.sheet_names
                merged_sheets = {s: False for s in sheet_names}
            except Exception:
                sheet_names = []

        try:
            wb_form = openpyxl.load_workbook(buffer_form, read_only=False, data_only=False)
        except Exception:
            wb_form = None

        csv_df = None
        if not sheet_names:
            buffer_data.seek(0)
            try:
                csv_df = pd.read_csv(buffer_data, header=None)
                sheet_names = ["Sheet1"]
                merged_sheets = {"Sheet1": False}
            except Exception:
                sheet_names = []

        # Performance safeguard: sheet count
        if len(sheet_names) > MAX_SHEETS:
            return WorkbookInspectionResult(
                filename=filename,
                total_sheets=len(sheet_names),
                sheets=[],
                recommended_sheet="None",
                document_type=DocumentTypeEnum.REVIEW_REQUIRED,
                header_row_index=0,
                confidence="LOW",
                status="REVIEW_REQUIRED",
                message=f"Workbook contains {len(sheet_names)} sheets, exceeding safe limit of {MAX_SHEETS}.",
            )

        if not sheet_names:
            return WorkbookInspectionResult(
                filename=filename,
                total_sheets=0,
                sheets=[],
                recommended_sheet="None",
                document_type=DocumentTypeEnum.UNKNOWN,
                header_row_index=0,
                confidence="LOW",
                status="REVIEW_REQUIRED",
                message="No readable worksheets found in workbook.",
            )

        sheets_info: List[SheetInspectionInfo] = []
        all_tables: List[FinancialTable] = []
        corpus_texts: List[str] = []
        has_balance_sheet = False
        has_pl = False
        has_ledger = False
        has_bank = False

        for s_name in sheet_names:
            if csv_df is not None:
                raw_df = csv_df
            else:
                buffer_data.seek(0)
                try:
                    engine = "xlrd" if filename.lower().endswith(".xls") else None
                    raw_df = pd.read_excel(buffer_data, sheet_name=s_name, header=None, engine=engine) if engine else pd.read_excel(buffer_data, sheet_name=s_name, header=None)
                except Exception:
                    continue

            # Performance safeguard: rows / columns
            if len(raw_df) > MAX_ROWS or len(raw_df.columns) > MAX_COLUMNS:
                info = SheetInspectionInfo(
                    sheet_name=s_name,
                    row_count=len(raw_df),
                    col_count=len(raw_df.columns),
                    detected_columns=[],
                    classification=DocumentTypeEnum.REVIEW_REQUIRED,
                    header_row_index=0,
                    confidence="LOW",
                )
                sheets_info.append(info)
                continue

            ws_raw = wb_data[s_name] if (wb_data and s_name in wb_data.sheetnames) else None
            ws_f = wb_form[s_name] if (wb_form and s_name in wb_form.sheetnames) else None

            info, sheet_table = cls._analyze_sheet(
                raw_df,
                s_name,
                merged_sheets.get(s_name, False),
                ws_data=ws_raw,
                ws_form=ws_f,
            )
            sheets_info.append(info)
            if sheet_table:
                all_tables.append(sheet_table)
            corpus_texts.append(" ".join(info.detected_columns) + " " + " ".join(info.period_columns))

            if info.classification == DocumentTypeEnum.BALANCE_SHEET:
                has_balance_sheet = True
            elif info.classification == DocumentTypeEnum.PROFIT_LOSS:
                has_pl = True
            elif info.classification in (DocumentTypeEnum.ACCOUNTING_LEDGER, DocumentTypeEnum.GENERAL_LEDGER):
                has_ledger = True
            elif info.classification == DocumentTypeEnum.BANK_STATEMENT:
                has_bank = True

        if not sheets_info:
            return WorkbookInspectionResult(
                filename=filename,
                total_sheets=0,
                sheets=[],
                recommended_sheet="None",
                document_type=DocumentTypeEnum.UNKNOWN,
                header_row_index=0,
                confidence="LOW",
                status="REVIEW_REQUIRED",
                message="No valid tabular data found in workbook worksheets.",
            )

        # Detect overall financial period
        overall_period = FinancialPeriodDetector.detect_period(
            text_corpus=corpus_texts,
            filename=filename,
            sheet_names=sheet_names,
        )

        # Determine overall document type
        overall_doc_type = DocumentTypeEnum.UNKNOWN
        if has_balance_sheet and has_pl:
            overall_doc_type = DocumentTypeEnum.FINANCIAL_STATEMENT
        elif has_balance_sheet:
            overall_doc_type = DocumentTypeEnum.BALANCE_SHEET
        elif has_pl:
            overall_doc_type = DocumentTypeEnum.PROFIT_LOSS
        elif has_ledger:
            overall_doc_type = DocumentTypeEnum.ACCOUNTING_LEDGER
        elif has_bank:
            overall_doc_type = DocumentTypeEnum.BANK_STATEMENT
        else:
            sorted_by_conf = sorted(sheets_info, key=lambda x: (x.confidence == "HIGH", x.row_count), reverse=True)
            overall_doc_type = sorted_by_conf[0].classification

        # Pick recommended sheet
        rec_sheet = sheets_info[0].sheet_name
        if upload_category == "bank_statement":
            bank_sheets = [s for s in sheets_info if s.classification == DocumentTypeEnum.BANK_STATEMENT]
            rec_sheet = bank_sheets[0].sheet_name if bank_sheets else sheets_info[0].sheet_name
        elif upload_category == "ledger":
            ledger_sheets = [s for s in sheets_info if s.classification in (DocumentTypeEnum.ACCOUNTING_LEDGER, DocumentTypeEnum.GENERAL_LEDGER)]
            rec_sheet = ledger_sheets[0].sheet_name if ledger_sheets else sheets_info[0].sheet_name
        else:
            bs_sheets = [
                s for s in sheets_info
                if s.classification in (DocumentTypeEnum.BALANCE_SHEET, DocumentTypeEnum.ACCOUNTING_LEDGER, DocumentTypeEnum.BANK_STATEMENT)
            ]
            if bs_sheets:
                rec_sheet = bs_sheets[0].sheet_name

        for s in sheets_info:
            s.is_recommended = (s.sheet_name == rec_sheet)

        target_sheet_info = next((s for s in sheets_info if s.sheet_name == rec_sheet), sheets_info[0])

        status = "ready"
        message: Optional[str] = None

        # Check for category mismatch
        if upload_category == "bank_statement" and overall_doc_type in (
            DocumentTypeEnum.BALANCE_SHEET,
            DocumentTypeEnum.PROFIT_LOSS,
            DocumentTypeEnum.FINANCIAL_STATEMENT,
            DocumentTypeEnum.TRIAL_BALANCE,
        ):
            status = "REVIEW_REQUIRED"
            type_label = overall_doc_type.value.replace("_", " ").title()
            message = (
                f"This workbook appears to be a {type_label} rather than a Bank Statement. "
                "Please review detected worksheets or select a transaction statement sheet."
            )
        elif upload_category == "ledger" and overall_doc_type in (
            DocumentTypeEnum.BALANCE_SHEET,
            DocumentTypeEnum.PROFIT_LOSS,
            DocumentTypeEnum.FINANCIAL_STATEMENT,
        ):
            status = "REVIEW_REQUIRED"
            type_label = overall_doc_type.value.replace("_", " ").title()
            message = (
                f"This workbook appears to be a {type_label} rather than an Accounting Ledger. "
                "Please review detected worksheets or confirm the active accounting schedule."
            )
        elif target_sheet_info.confidence == "LOW":
            status = "REVIEW_REQUIRED"
            message = "Unable to confidently determine the sheet structure. Please verify the detected columns."

        # Fetch sample rows
        sample_data: List[Dict[str, Any]] = []
        try:
            buffer_data.seek(0)
            sample_df = pd.read_excel(buffer_data, sheet_name=rec_sheet, header=target_sheet_info.header_row_index)
            sample_df = sample_df.dropna(how="all")
            raw_cols = [normalize_column_name(c, idx) for idx, c in enumerate(sample_df.columns)]
            sample_df.columns = deduplicate_columns(raw_cols)
            for _, r in sample_df.head(5).iterrows():
                sample_data.append({str(k): serialize_scalar(v) for k, v in r.items()})
        except Exception:
            sample_data = []

        # Run Deterministic Financial Validation Engine
        discrepancies: List[StandardDiscrepancy] = []
        if wb_data is not None:
            try:
                discrepancies = FinancialValidator.validate_workbook(wb_data, wb_form, all_tables)
            except Exception:
                discrepancies = []

        overall_evidence = ClassificationEvidence(
            document_type=overall_doc_type,
            confidence=target_sheet_info.confidence,
            signals_found=[f"Sheet '{rec_sheet}' classified as {target_sheet_info.classification.value}"],
            explanation=f"Workbook identified as {overall_doc_type.value} with {len(sheet_names)} sheets.",
            score=0.9 if target_sheet_info.confidence == "HIGH" else 0.6,
        )

        return WorkbookInspectionResult(
            filename=filename,
            total_sheets=len(sheet_names),
            sheets=sheets_info,
            recommended_sheet=rec_sheet,
            document_type=overall_doc_type,
            header_row_index=target_sheet_info.header_row_index,
            period_columns=target_sheet_info.period_columns,
            confidence=target_sheet_info.confidence,
            status=status,
            message=message,
            sample_data=sample_data,
            period_info=overall_period,
            classification_evidence=overall_evidence,
            tables=all_tables,
            discrepancies=discrepancies,
        )

    @classmethod
    def _inspect_csv(
        cls,
        file_bytes_or_path: Union[Path, str, bytes],
        filename: str,
        upload_category: Optional[str] = None,
    ) -> WorkbookInspectionResult:
        if isinstance(file_bytes_or_path, (str, Path)):
            with open(file_bytes_or_path, "rb") as f:
                content = f.read()
        else:
            content = file_bytes_or_path

        buffer = io.BytesIO(content)
        try:
            raw_df = pd.read_csv(buffer, header=None, encoding="utf-8")
        except UnicodeDecodeError:
            buffer.seek(0)
            raw_df = pd.read_csv(buffer, header=None, encoding="latin-1")

        info, sheet_table = cls._analyze_sheet(raw_df, "Sheet1", False)
        info.is_recommended = True

        period_info = FinancialPeriodDetector.detect_period(
            text_corpus=[" ".join(info.detected_columns), " ".join(info.period_columns)],
            filename=filename,
        )

        status = "ready"
        message: Optional[str] = None
        if upload_category == "bank_statement" and info.classification in (
            DocumentTypeEnum.BALANCE_SHEET,
            DocumentTypeEnum.PROFIT_LOSS,
        ):
            status = "REVIEW_REQUIRED"
            message = f"This file appears to be a {info.classification.value} rather than a Bank Statement."
        elif upload_category == "ledger" and info.classification in (
            DocumentTypeEnum.BALANCE_SHEET,
            DocumentTypeEnum.PROFIT_LOSS,
        ):
            status = "REVIEW_REQUIRED"
            message = f"This file appears to be a {info.classification.value} rather than an Accounting Ledger."
        elif info.confidence == "LOW":
            status = "REVIEW_REQUIRED"
            message = "Unable to confidently determine the sheet structure."

        sample_data = []
        try:
            buffer.seek(0)
            sample_df = pd.read_csv(buffer, header=info.header_row_index)
            sample_df = sample_df.dropna(how="all")
            raw_cols = [normalize_column_name(c, idx) for idx, c in enumerate(sample_df.columns)]
            sample_df.columns = deduplicate_columns(raw_cols)
            for _, r in sample_df.head(5).iterrows():
                sample_data.append({str(k): serialize_scalar(v) for k, v in r.items()})
        except Exception:
            sample_data = []

        return WorkbookInspectionResult(
            filename=filename,
            total_sheets=1,
            sheets=[info],
            recommended_sheet="Sheet1",
            document_type=info.classification,
            header_row_index=info.header_row_index,
            period_columns=info.period_columns,
            confidence=info.confidence,
            status=status,
            message=message,
            sample_data=sample_data,
            period_info=period_info,
            classification_evidence=info.classification_evidence,
            tables=[sheet_table] if sheet_table else [],
            discrepancies=[],
        )

    @classmethod
    def _analyze_sheet(
        cls,
        df: pd.DataFrame,
        sheet_name: str,
        has_merged: bool,
        ws_data: Optional[Any] = None,
        ws_form: Optional[Any] = None,
    ) -> Tuple[SheetInspectionInfo, Optional[FinancialTable]]:
        cleaned_df = df.dropna(how="all").dropna(axis=1, how="all")
        row_count = len(cleaned_df)
        col_count = len(cleaned_df.columns) if row_count > 0 else 0

        if row_count == 0:
            info = SheetInspectionInfo(
                sheet_name=sheet_name,
                row_count=0,
                col_count=0,
                detected_columns=[],
                classification=DocumentTypeEnum.UNKNOWN,
                header_row_index=0,
                period_columns=[],
                has_merged_cells=has_merged,
                confidence="LOW",
                is_recommended=False,
            )
            return info, None

        # Unit detection (e.g. ₹ Lakhs, in Crores)
        unit = "ACTUAL"
        top_25_df = cleaned_df.head(25)
        text_corpus: List[str] = []
        period_columns: List[str] = []
        header_row_index = 0
        best_header_score = -1

        for idx, row in top_25_df.iterrows():
            row_vals = [str(v).strip() for v in row if v is not None and not pd.isna(v)]
            row_text = " ".join(row_vals).lower()
            text_corpus.append(row_text)

            if "lakh" in row_text or "lacs" in row_text:
                unit = "LAKH"
            elif "crore" in row_text or "cr." in row_text:
                unit = "CRORE"

            for val in row_vals:
                if FINANCIAL_PERIOD_REGEX.search(val) and val not in period_columns:
                    period_columns.append(val)

            score = 0
            has_date = any("date" in v.lower() for v in row_vals)
            has_desc = any(w in row_text for w in ("description", "particulars", "narration", "account", "details"))
            has_money = any(w in row_text for w in ("amount", "debit", "credit", "withdrawal", "deposit", "balance"))

            if has_date:
                score += 3
            if has_desc:
                score += 3
            if has_money:
                score += 3
            score += min(len(row_vals), 5)

            if score > best_header_score and (has_desc or has_money or has_date):
                best_header_score = score
                header_row_index = int(idx)

        full_corpus = " ".join(text_corpus) + " " + sheet_name.lower()
        has_wd = "withdrawal" in full_corpus and "deposit" in full_corpus

        # Deterministic classification with evidence
        classification, evidence = DocumentClassifier.classify(full_corpus, sheet_name, has_withdrawal_deposit=has_wd)

        # Detect headers from the chosen header row
        detected_cols: List[str] = []
        if header_row_index in cleaned_df.index:
            header_row = cleaned_df.loc[header_row_index]
            raw_cols = [normalize_column_name(c, i) for i, c in enumerate(header_row)]
            detected_cols = deduplicate_columns(raw_cols)

        # Detect period info for this sheet
        sheet_period = FinancialPeriodDetector.detect_period([full_corpus], sheet_names=[sheet_name])

        # Extract structured FinancialTable with exact cell provenance
        table = None
        if ws_data is not None:
            try:
                table = cls._extract_financial_table(
                    ws_data=ws_data,
                    ws_form=ws_form,
                    sheet_name=sheet_name,
                    header_row=header_row_index + 1,  # 1-indexed for Excel
                    classification=classification,
                    period=sheet_period,
                    unit=unit,
                )
            except Exception:
                table = None

        info = SheetInspectionInfo(
            sheet_name=sheet_name,
            row_count=row_count,
            col_count=col_count,
            detected_columns=detected_cols[:15],
            classification=classification,
            header_row_index=header_row_index,
            period_columns=period_columns[:5],
            has_merged_cells=has_merged,
            confidence=evidence.confidence,
            is_recommended=False,
            classification_evidence=evidence,
            period_info=sheet_period,
            unit=unit,
            tables=[table] if table else [],
        )

        return info, table

    @classmethod
    def _extract_financial_table(
        cls,
        ws_data: Any,
        ws_form: Optional[Any],
        sheet_name: str,
        header_row: int,
        classification: DocumentTypeEnum,
        period: FinancialPeriod,
        unit: str,
    ) -> FinancialTable:
        """Extracts structured financial rows with exact cell coordinates and provenance."""
        rows: List[FinancialRow] = []
        data_start_row = header_row + 1
        data_end_row = ws_data.max_row
        col_names: Dict[int, str] = {}

        # Capture column headers
        for c in range(1, ws_data.max_column + 1):
            val = ws_data.cell(header_row, c).value
            col_names[c] = str(val).strip() if val else f"Col_{get_column_letter(c)}"

        totals: Dict[str, float] = {}

        for r in range(data_start_row, data_end_row + 1):
            label_cell = ws_data.cell(r, 1).value or ws_data.cell(r, 2).value or ""
            label_str = str(label_cell).strip()
            if not label_str:
                continue

            # Classify row type
            label_lower = label_str.lower()
            if "total" in label_lower or "subtotal" in label_lower:
                row_type = "TOTAL"
            elif label_str.startswith("I.") or label_str.startswith("II.") or label_str.isupper() and len(label_str) > 10:
                row_type = "SECTION"
            else:
                row_type = "LINE_ITEM"

            row_values: Dict[str, Any] = {}
            norm_values: Dict[str, Optional[float]] = {}
            source_cells: Dict[str, FinancialCellProvenance] = {}

            for c in range(1, ws_data.max_column + 1):
                col_name = col_names.get(c, f"Col_{c}")
                val_data = ws_data.cell(r, c).value
                formula_val = str(ws_form.cell(r, c).value or "") if ws_form else None

                parsed_num, raw_val, cell_unit = parse_indian_number(val_data)
                cell_address = f"{get_column_letter(c)}{r}"

                row_values[col_name] = val_data
                norm_values[col_name] = parsed_num

                if parsed_num is not None:
                    if row_type == "TOTAL":
                        totals[f"{label_str}_{col_name}"] = parsed_num

                source_cells[col_name] = FinancialCellProvenance(
                    sheet_name=sheet_name,
                    cell_address=cell_address,
                    row_number=r,
                    column_number=c,
                    column_name=col_name,
                    raw_value=val_data,
                    normalized_value=parsed_num,
                    formula=formula_val if (formula_val and formula_val.startswith("=")) else None,
                    unit=cell_unit or unit,
                )

            rows.append(
                FinancialRow(
                    table_id=f"tab_{sheet_name}",
                    row_number=r,
                    label=label_str,
                    row_type=row_type,
                    values=row_values,
                    normalized_values=norm_values,
                    source_cells=source_cells,
                )
            )

        return FinancialTable(
            table_id=f"tbl_{sheet_name}_{header_row}",
            sheet_name=sheet_name,
            table_range=f"A{header_row}:{get_column_letter(ws_data.max_column)}{data_end_row}",
            header_row=header_row,
            data_start_row=data_start_row,
            data_end_row=data_end_row,
            table_type=classification,
            period=period,
            currency="INR",
            unit=unit,
            confidence="HIGH",
            rows=rows,
            totals=totals,
        )
