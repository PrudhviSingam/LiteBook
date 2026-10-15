import csv
import io
import math
import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from app.modules.reconciliation.schemas import (
    ColumnMappingPreview,
    NormalizedTransaction,
)


DATE_SYNONYMS = [
    "date",
    "transaction date",
    "txn date",
    "value date",
    "posting date",
    "booking date",
    "entry date",
    "voucher date",
    "doc date",
    "bill date",
    "invoice date",
    "txn_date",
    "period date",
    "effective date",
]

DESC_SYNONYMS = [
    "description",
    "narration",
    "particulars",
    "remarks",
    "details",
    "transaction remarks",
    "notes",
    "memo",
    "payee",
    "party",
    "party name",
    "account",
    "account name",
    "item",
    "product",
    "vendor",
    "customer",
    "narrative",
]

REF_SYNONYMS = [
    "reference",
    "ref no",
    "ref",
    "ref no.",
    "transaction id",
    "txn id",
    "cheque no",
    "cheque",
    "chq no",
    "utr",
    "utr number",
    "reference number",
    "voucher no",
    "voucher",
    "voucher number",
    "vch no",
    "vch",
    "inv no",
    "invoice no",
    "invoice number",
    "bill no",
    "doc no",
    "document no",
    "txn ref",
    "order id",
    "identifier",
    "id",
]

AMOUNT_SYNONYMS = [
    "amount",
    "transaction amount",
    "net amount",
    "total",
    "value",
    "balance",
    "gross amount",
    "gross",
    "net",
    "line total",
    "price",
]

DEBIT_SYNONYMS = [
    "debit",
    "withdrawal",
    "withdrawals",
    "dr",
    "dr.",
    "debit amount",
    "payment",
    "payments",
]

CREDIT_SYNONYMS = [
    "credit",
    "deposit",
    "deposits",
    "cr",
    "cr.",
    "credit amount",
    "receipt",
    "receipts",
]


class NormalizationError(Exception):
    pass


def clean_header(header: Any) -> str:
    if not isinstance(header, str):
        header = str(header)
    # Strip whitespace, lowercase, normalize spaces and underscores
    cleaned = header.strip().lower()
    cleaned = re.sub(r"[\s_-]+", " ", cleaned)
    return cleaned


def find_matching_column(columns: List[str], synonyms: List[str]) -> Optional[str]:
    cleaned_map = {col: clean_header(col) for col in columns}
    # 1. Exact match with synonyms
    for syn in synonyms:
        for original, cleaned in cleaned_map.items():
            if cleaned == syn:
                return original

    # 2. Word boundary / whole token match
    for syn in synonyms:
        pattern = r"\b" + re.escape(syn) + r"\b"
        for original, cleaned in cleaned_map.items():
            if re.search(pattern, cleaned):
                return original

    # 3. Substring match for phrases with len > 3
    for syn in synonyms:
        if len(syn) > 3:
            for original, cleaned in cleaned_map.items():
                if syn in cleaned:
                    return original

    return None


def parse_clean_amount(val: Any) -> float:
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null", "-", ""):
        return 0.0

    # Check for accounting parentheses for negative: e.g. (1,234.50)
    is_negative = False
    if s.startswith("(") and s.endswith(")"):
        is_negative = True
        s = s[1:-1].strip()

    # Clean out currency prefixes (Rs., INR) and symbols (₹, $, €, £) and spaces
    s = re.sub(r"^(?:rs\.?|inr)\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"[₹\$€£\s,]", "", s)
    s = re.sub(r"^(?:rs\.?|inr)\s*", "", s, flags=re.IGNORECASE)

    # Check for trailing or leading minus
    if s.endswith("-"):
        is_negative = True
        s = s[:-1].strip()
    elif s.startswith("-"):
        is_negative = True
        s = s[1:].strip()

    # Check for Dr / Cr suffix
    if s.lower().endswith("dr"):
        is_negative = True
        s = s[:-2].strip()
    elif s.lower().endswith("cr"):
        is_negative = False
        s = s[:-2].strip()

    try:
        val_float = float(s)
        return -val_float if is_negative else val_float
    except ValueError:
        return 0.0


def parse_clean_date(val: Any) -> str:
    """Standardizes date to YYYY-MM-DD string format."""
    if val is None or (isinstance(val, float) and math.isnan(val)):
        return date.today().isoformat()

    # Handle Excel numeric serial dates: e.g. 46266 -> 2026-09-01
    if isinstance(val, (int, float)) and not math.isnan(val):
        if 20000 <= val <= 80000:
            try:
                return pd.to_datetime(val, unit="D", origin="1899-12-30").strftime("%Y-%m-%d")
            except Exception:
                pass

    if isinstance(val, (datetime, pd.Timestamp)):
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()

    s = str(val).strip()
    if not s or s.lower() in ("nan", "none", "null"):
        return date.today().isoformat()

    # Handle string serial numbers
    if s.isdigit() and 20000 <= int(s) <= 80000:
        try:
            return pd.to_datetime(int(s), unit="D", origin="1899-12-30").strftime("%Y-%m-%d")
        except Exception:
            pass

    # Common formats
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d-%b-%Y",
        "%d %B %Y",
        "%d-%b-%y",
        "%Y/%m/%d",
    ]

    for fmt in date_formats:
        try:
            parsed = datetime.strptime(s, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Fallback to pandas date parser
    try:
        ts = pd.to_datetime(s, errors="coerce")
        if pd.notna(ts):
            return ts.strftime("%Y-%m-%d")
    except Exception:
        pass

    return date.today().isoformat()


def normalize_column_name(column: Any, index: int = 0) -> str:
    """Safely converts a column identifier to a non-empty, clean string.

    Handles None, NaN, float, int, datetime, and default pandas Unnamed
    columns.
    """
    if column is None or pd.isna(column):
        return f"Unnamed_Column_{index + 1}"

    col_str = str(column).strip()
    if not col_str or col_str.lower() in ("nan", "none", "null", "unnamed"):
        return f"Unnamed_Column_{index + 1}"

    # Handle pandas default Unnamed: 0, Unnamed: 1 pattern
    if re.match(r"^unnamed:\s*\d+", col_str, flags=re.IGNORECASE):
        return f"Unnamed_Column_{index + 1}"

    return col_str


def deduplicate_columns(columns: List[str]) -> List[str]:
    """Ensures that all column names in the list are unique.

    E.g., ['Amount', 'Amount'] -> ['Amount', 'Amount_2']. Does not silently
    overwrite any column.
    """
    used_names: set[str] = set()
    result: List[str] = []
    for col in columns:
        candidate = col
        counter = 2
        while candidate in used_names:
            candidate = f"{col}_{counter}"
            counter += 1
        used_names.add(candidate)
        result.append(candidate)
    return result


def normalize_dataframe_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizes all DataFrame columns to clean, unique strings safely.

    Preserves all original data in the DataFrame.
    """
    raw_cols = list(df.columns)
    normalized = [normalize_column_name(c, idx) for idx, c in enumerate(raw_cols)]
    unique_cols = deduplicate_columns(normalized)
    df = df.copy()
    df.columns = unique_cols
    return df


def serialize_scalar(val: Any) -> Any:
    """Safely converts pandas/numpy values into JSON/Pydantic-compatible native Python types.

    - Preserves numeric transaction amounts as floats or ints.
    - Converts NaN, inf, NaT, None to None (JSON null).
    - Serializes dates/timestamps safely to ISO string.
    """
    if val is None:
        return None
    if pd.isna(val):
        return None
    if isinstance(val, (float, np.floating)):
        if math.isnan(val) or math.isinf(val):
            return None
        return float(val)
    if isinstance(val, (int, np.integer)):
        return int(val)
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if isinstance(val, (datetime, pd.Timestamp)):
        if pd.isna(val):
            return None
        return val.strftime("%Y-%m-%d")
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, (bytes, bytearray)):
        return val.decode("utf-8", errors="replace")
    return str(val)


def serialize_sample_rows(df: pd.DataFrame, limit: int = 5) -> List[Dict[str, Any]]:
    """Serializes top rows into Pydantic/JSON-safe dictionaries.

    Ensures every dictionary key is a string and values are JSON-compatible
    scalars.
    """
    sample_df = df.head(limit)
    rows: List[Dict[str, Any]] = []
    for _, row in sample_df.iterrows():
        row_dict: Dict[str, Any] = {}
        for col_name, val in row.items():
            row_dict[str(col_name)] = serialize_scalar(val)
        rows.append(row_dict)
    return rows


def score_header_candidate(row_values: List[Any]) -> Tuple[int, bool, bool]:
    """Scores how likely a row of cell values is to be a transaction header row.

    Returns (score, has_date, has_amount).
    """
    cleaned_cells = [clean_header(c) for c in row_values if c is not None and not pd.isna(c)]
    has_date = any(syn in cleaned_cells for syn in DATE_SYNONYMS) or any(
        any(syn in cell for syn in DATE_SYNONYMS) for cell in cleaned_cells
    )
    has_amount = (
        any(syn in cleaned_cells for syn in AMOUNT_SYNONYMS)
        or any(syn in cleaned_cells for syn in DEBIT_SYNONYMS)
        or any(syn in cleaned_cells for syn in CREDIT_SYNONYMS)
        or any(any(syn in cell for syn in AMOUNT_SYNONYMS + DEBIT_SYNONYMS + CREDIT_SYNONYMS) for cell in cleaned_cells)
    )
    has_desc = any(syn in cleaned_cells for syn in DESC_SYNONYMS) or any(
        any(syn in cell for syn in DESC_SYNONYMS) for cell in cleaned_cells
    )
    has_ref = any(syn in cleaned_cells for syn in REF_SYNONYMS) or any(
        any(syn in cell for syn in REF_SYNONYMS) for cell in cleaned_cells
    )

    score = 0
    if has_date:
        score += 20
    if has_amount:
        score += 20
    if has_desc:
        score += 10
    if has_ref:
        score += 10
    if has_date and has_amount:
        score += 30

    return score, has_date, has_amount


def read_file_to_dataframe(
    file_path_or_bytes: Union[Path, str, bytes],
    filename: str,
    sheet_name: Optional[Union[str, int]] = None,
) -> pd.DataFrame:
    """Reads a CSV or Excel file safely into a pandas DataFrame with smart header detection and normalized columns."""
    ext = Path(filename).suffix.lower()

    if isinstance(file_path_or_bytes, bytes):
        raw_bytes = file_path_or_bytes
        buffer = io.BytesIO(file_path_or_bytes)
    else:
        path = Path(file_path_or_bytes)
        raw_bytes = path.read_bytes()
        buffer = io.BytesIO(raw_bytes)

    best_header_idx = -1

    if ext in (".xlsx", ".xls"):
        try:
            target_sheet = sheet_name if sheet_name is not None else 0
            df_raw = pd.read_excel(buffer, sheet_name=target_sheet, header=None)
        except Exception as e:
            raise NormalizationError(f"Failed to read Excel file '{filename}': {str(e)}")

        if df_raw.empty:
            raise NormalizationError(f"The uploaded file '{filename}' contains no rows or data.")

        # Drop rows that are completely NaN
        df_raw = df_raw.dropna(how="all").reset_index(drop=True)
        if df_raw.empty:
            raise NormalizationError(f"The uploaded file '{filename}' contains only empty rows.")

        # Inspect first rows (up to 25) for header candidate
        max_scan = min(25, len(df_raw))
        best_header_idx = -1
        best_score = 0

        for r_idx in range(max_scan):
            row_vals = df_raw.iloc[r_idx].tolist()
            score, has_date, has_amount = score_header_candidate(row_vals)
            if has_date and has_amount and score > best_score:
                best_score = score
                best_header_idx = r_idx

        if best_header_idx >= 0 and best_header_idx < len(df_raw) - 1:
            header_row = df_raw.iloc[best_header_idx].tolist()
            df = df_raw.iloc[best_header_idx + 1:].copy()
            df.columns = header_row
        elif best_header_idx == len(df_raw) - 1:
            header_row = df_raw.iloc[best_header_idx].tolist()
            df = df_raw.iloc[0:0].copy()
            df.columns = header_row
        else:
            # Fallback to row 0 if no confident header row found
            header_row = df_raw.iloc[0].tolist()
            df = df_raw.iloc[1:].copy()
            df.columns = header_row
            best_header_idx = 0

        df.attrs["header_row_index"] = best_header_idx

    elif ext in (".csv", ".txt"):
        # For CSV, scan text lines for header row index if there are title lines
        text_content = ""
        for encoding in ("utf-8", "latin-1"):
            try:
                text_content = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if not text_content:
            raise NormalizationError(f"The uploaded file '{filename}' contains no valid text encoding.")

        lines = text_content.splitlines()
        best_header_idx = 0
        best_score = 0
        max_scan = min(25, len(lines))

        for r_idx in range(max_scan):
            line = lines[r_idx].strip()
            if not line:
                continue
            try:
                row_vals = next(csv.reader([line]))
            except Exception:
                continue
            score, has_date, has_amount = score_header_candidate(row_vals)
            if has_date and has_amount and score > best_score:
                best_score = score
                best_header_idx = r_idx

        try:
            buffer.seek(0)
            df = pd.read_csv(
                buffer,
                skiprows=best_header_idx,
                encoding="utf-8",
                on_bad_lines="skip",
            )
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            raise NormalizationError(f"The uploaded file '{filename}' contains no rows or has an invalid format.")
        except UnicodeDecodeError:
            buffer.seek(0)
            try:
                df = pd.read_csv(
                    buffer,
                    skiprows=best_header_idx,
                    encoding="latin-1",
                    on_bad_lines="skip",
                )
            except (pd.errors.EmptyDataError, pd.errors.ParserError):
                raise NormalizationError(f"The uploaded file '{filename}' contains no rows or has an invalid format.")
    else:
        raise NormalizationError(f"Unsupported file format '{ext}'. Supported formats: CSV, XLSX.")

    if df.empty and len(df.columns) == 0:
        raise NormalizationError(f"The uploaded file '{filename}' contains no rows or data.")

    # Drop fully empty rows
    df = df.dropna(how="all").reset_index(drop=True)
    if df.empty and len(df.columns) == 0:
        raise NormalizationError(f"The uploaded file '{filename}' contains only empty rows.")

    # Always normalize columns to clean, unique strings
    df = normalize_dataframe_columns(df)
    return df


def find_all_matching_columns(columns: List[str], synonyms: List[str]) -> List[str]:
    cleaned_map = {col: clean_header(col) for col in columns}
    matched: List[str] = []
    # 1. Exact match with synonyms
    for syn in synonyms:
        for original, cleaned in cleaned_map.items():
            if cleaned == syn and original not in matched:
                matched.append(original)
    # 2. Word boundary match
    for syn in synonyms:
        pattern = r"\b" + re.escape(syn) + r"\b"
        for original, cleaned in cleaned_map.items():
            if re.search(pattern, cleaned) and original not in matched:
                matched.append(original)
    # 3. Substring match for phrases with len > 3
    for syn in synonyms:
        if len(syn) > 3:
            for original, cleaned in cleaned_map.items():
                if syn in cleaned and original not in matched:
                    matched.append(original)
    return matched


def get_file_sheet_names(file_path_or_bytes: Union[Path, str, bytes], filename: str) -> List[str]:
    ext = Path(filename).suffix.lower()
    if ext in (".xlsx", ".xls"):
        try:
            if isinstance(file_path_or_bytes, bytes):
                buf = io.BytesIO(file_path_or_bytes)
            else:
                buf = io.BytesIO(Path(file_path_or_bytes).read_bytes())
            import openpyxl
            wb = openpyxl.load_workbook(buf, read_only=True)
            names = list(wb.sheetnames)
            wb.close()
            return names if names else ["Sheet1"]
        except Exception:
            return ["Sheet1"]
    return ["Sheet1"]


def detect_columns_with_ambiguity(columns: List[str]) -> Tuple[Dict[str, Optional[str]], bool, Optional[str]]:
    date_matches = find_all_matching_columns(columns, DATE_SYNONYMS)
    desc_matches = find_all_matching_columns(columns, DESC_SYNONYMS)
    ref_matches = find_all_matching_columns(columns, REF_SYNONYMS)
    amount_matches = find_all_matching_columns(columns, AMOUNT_SYNONYMS)
    debit_matches = find_all_matching_columns(columns, DEBIT_SYNONYMS)
    credit_matches = find_all_matching_columns(columns, CREDIT_SYNONYMS)

    mapping = {
        "date": date_matches[0] if date_matches else None,
        "description": desc_matches[0] if desc_matches else None,
        "reference": ref_matches[0] if ref_matches else None,
        "amount": amount_matches[0] if amount_matches else None,
        "debit": debit_matches[0] if debit_matches else None,
        "credit": credit_matches[0] if credit_matches else None,
    }

    is_ambiguous = False
    ambiguity_reasons = []

    if len(amount_matches) > 1 and not (debit_matches or credit_matches):
        is_ambiguous = True
        ambiguity_reasons.append(f"Multiple candidate amount columns found: {', '.join(amount_matches[:3])}")
    if len(date_matches) > 1:
        is_ambiguous = True
        ambiguity_reasons.append(f"Multiple candidate date columns found: {', '.join(date_matches[:3])}")
    if not mapping["date"]:
        is_ambiguous = True
        ambiguity_reasons.append("No date column was automatically identified")
    if not (mapping["amount"] or mapping["debit"] or mapping["credit"]):
        is_ambiguous = True
        ambiguity_reasons.append("No amount or debit/credit column was automatically identified")

    reason = "; ".join(ambiguity_reasons) if ambiguity_reasons else None
    return mapping, is_ambiguous, reason


def detect_columns(columns: List[str]) -> Dict[str, Optional[str]]:
    """Automatically maps detected column headers to standardized fields."""
    mapping, _, _ = detect_columns_with_ambiguity(columns)
    return mapping


def preview_dataframe(
    df: pd.DataFrame,
    filename: str = "uploaded_file",
    sheet_names: Optional[List[str]] = None,
    selected_sheet: Optional[str] = None,
) -> ColumnMappingPreview:
    """Generates column mapping preview and sample rows from an existing DataFrame."""
    df = normalize_dataframe_columns(df)
    cols = list(df.columns)
    mapping, is_ambiguous, amb_reason = detect_columns_with_ambiguity(cols)

    has_date = bool(mapping.get("date"))
    has_amount_or_split = bool(mapping.get("amount") or mapping.get("debit") or mapping.get("credit"))

    if is_ambiguous or not has_date or not has_amount_or_split:
        status_val = "REVIEW_REQUIRED"
        if not has_date and not has_amount_or_split:
            message_val = (
                "Unable to confidently determine the transaction header row or column mappings automatically. "
                + (amb_reason or "Please review and select the correct columns.")
            )
        else:
            message_val = amb_reason or (
                "Unable to confidently determine column mappings automatically. "
                "Please review and select the correct columns."
            )
    else:
        status_val = "ready"
        message_val = None

    sample_rows = serialize_sample_rows(df, limit=5)

    return ColumnMappingPreview(
        filename=filename,
        total_rows=len(df),
        detected_columns=cols,
        column_mapping=mapping,
        sample_rows=sample_rows,
        status=status_val,
        message=message_val,
        sheet_names=sheet_names or ["Sheet1"],
        selected_sheet=selected_sheet or (sheet_names[0] if sheet_names else "Sheet1"),
        is_ambiguous=is_ambiguous,
        ambiguity_reason=amb_reason,
        available_columns=cols,
    )


def preview_file(
    file_path_or_bytes: Union[Path, str, bytes],
    filename: str,
    sheet_name: Optional[str] = None,
) -> ColumnMappingPreview:
    """Generates column mapping preview and sample rows without processing the entire dataset."""
    sheet_names = get_file_sheet_names(file_path_or_bytes, filename)
    target_sheet = sheet_name if sheet_name and sheet_name in sheet_names else (sheet_names[0] if sheet_names else 0)
    df = read_file_to_dataframe(file_path_or_bytes, filename, sheet_name=target_sheet)
    return preview_dataframe(
        df,
        filename,
        sheet_names=sheet_names,
        selected_sheet=target_sheet if isinstance(target_sheet, str) else sheet_names[0],
    )


def normalize_transactions(
    file_path_or_bytes: Union[Path, str, bytes],
    filename: str,
    source: str = "bank",
    sheet_name: Optional[str] = None,
    document_id: Optional[int] = None,
    source_type: Optional[str] = None,
    user_mapping: Optional[Dict[str, Optional[str]]] = None,
) -> List[NormalizedTransaction]:
    """Normalizes any CSV or Excel file into a standard List[NormalizedTransaction]."""
    df = read_file_to_dataframe(file_path_or_bytes, filename, sheet_name=sheet_name)
    cols = [str(c) for c in df.columns]

    mapping = detect_columns(cols)
    if user_mapping:
        mapping.update({k: v for k, v in user_mapping.items() if v})

    # Validate that minimum required columns exist
    date_col = mapping.get("date")
    has_amount_col = bool(mapping.get("amount"))
    has_split_cols = bool(mapping.get("debit") or mapping.get("credit"))

    if not date_col:
        raise NormalizationError(
            f"Unable to detect a Date column in '{filename}'. Please ensure your file has a 'Date' header."
        )

    if not (has_amount_col or has_split_cols):
        raise NormalizationError(
            f"Unable to detect Amount or Debit/Credit columns in '{filename}'. "
            "Please ensure headers for Amount, Debit, or Credit exist."
        )

    desc_col = mapping.get("description")
    ref_col = mapping.get("reference")
    amount_col = mapping.get("amount")
    debit_col = mapping.get("debit")
    credit_col = mapping.get("credit")

    normalized: List[NormalizedTransaction] = []
    header_idx = df.attrs.get("header_row_index", 0)

    for idx, row in df.iterrows():
        # Parse Date
        row_date = parse_clean_date(row[date_col]) if date_col in row else date.today().isoformat()

        # Parse Description
        desc = ""
        if desc_col and desc_col in row and pd.notna(row[desc_col]):
            desc = str(row[desc_col]).strip()
        if not desc:
            desc = f"Transaction #{idx + 1}"

        # Parse Reference
        ref = ""
        if ref_col and ref_col in row and pd.notna(row[ref_col]):
            ref = str(row[ref_col]).strip()

        # Determine Amount, Debit, Credit, and Direction
        debit_val = 0.0
        credit_val = 0.0
        direction = "debit"
        final_amount = 0.0

        if debit_col and debit_col in row and pd.notna(row[debit_col]):
            debit_val = abs(parse_clean_amount(row[debit_col]))
        if credit_col and credit_col in row and pd.notna(row[credit_col]):
            credit_val = abs(parse_clean_amount(row[credit_col]))

        if debit_val > 0 and credit_val == 0:
            final_amount = debit_val
            direction = "debit"
        elif credit_val > 0 and debit_val == 0:
            final_amount = credit_val
            direction = "credit"
        elif debit_val > 0 and credit_val > 0:
            # If both are populated, take the net
            if debit_val >= credit_val:
                final_amount = debit_val - credit_val
                direction = "debit"
            else:
                final_amount = credit_val - debit_val
                direction = "credit"
        elif amount_col and amount_col in row and pd.notna(row[amount_col]):
            raw_amt = parse_clean_amount(row[amount_col])
            final_amount = abs(raw_amt)
            direction = "debit" if raw_amt < 0 else "credit"
            if direction == "debit":
                debit_val = final_amount
            else:
                credit_val = final_amount
        else:
            final_amount = 0.0

        # Skip rows with 0 amount unless there's a description
        if final_amount == 0.0 and not ref and desc == f"Transaction #{idx + 1}":
            continue

        raw_row_clean = {str(k): ("" if pd.isna(v) else str(v)) for k, v in row.to_dict().items()}
        orig_row = (header_idx + 1 + idx + 1) if isinstance(idx, int) else None

        cell_addrs: Dict[str, str] = {}
        if orig_row:
            for fld, cname in mapping.items():
                if cname and cname in cols:
                    c_idx = cols.index(cname) + 1
                    col_letter = chr(64 + c_idx) if c_idx <= 26 else f"{chr(64 + (c_idx - 1) // 26)}{chr(65 + (c_idx - 1) % 26)}"
                    cell_addrs[fld] = f"{col_letter}{orig_row}"

        tx = NormalizedTransaction(
            id=f"{source}_{idx}_{uuid.uuid4().hex[:6]}",
            date=row_date,
            description=desc,
            reference=ref,
            debit=round(debit_val, 2),
            credit=round(credit_val, 2),
            amount=round(final_amount, 2),
            direction=direction,
            source=source,
            raw_row=raw_row_clean,
            document_id=document_id,
            filename=filename,
            sheet_name=sheet_name or "Sheet1",
            source_type=source_type or ("BANK_STATEMENT" if source == "bank" else "GENERAL_LEDGER"),
            original_row_number=orig_row,
            cell_addresses=cell_addrs,
        )
        normalized.append(tx)

    if not normalized:
        raise NormalizationError(f"No valid transaction rows could be extracted from '{filename}'.")

    return normalized
