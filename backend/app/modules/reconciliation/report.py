import csv
import io
from datetime import datetime, timezone
from typing import List, Optional

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.modules.reconciliation.schemas import (
    ReconciliationItem,
    ReconciliationSessionResponse,
    ReconciliationSummary,
)


def generate_reconciliation_csv_report(
    bank_name: str,
    ledger_name: str,
    summary: ReconciliationSummary,
    items: List[ReconciliationItem],
) -> str:
    """Generates a structured, professional CSV reconciliation report string."""
    output = io.StringIO()
    writer = csv.writer(output)

    # 1. Header Metadata Section
    writer.writerow(["========================================================================="])
    writer.writerow(["FINANCE AI — BANK RECONCILIATION AUDIT REPORT"])
    writer.writerow(["========================================================================="])
    writer.writerow(["Generated At", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")])
    writer.writerow(["Source File A", bank_name])
    writer.writerow(["Source File B", ledger_name])
    writer.writerow([])

    # 2. Executive Summary Metrics
    writer.writerow(["RECONCILIATION SUMMARY"])
    writer.writerow(["Total Source A Records", summary.total_bank_transactions])
    writer.writerow(["Total Source B Records", summary.total_ledger_transactions])
    writer.writerow(["Matched Records", summary.matched_count])
    writer.writerow(["Total Differences Detected", summary.unmatched_count])
    writer.writerow(["- Changed Values", summary.changed_value_count or summary.amount_mismatch_count])
    writer.writerow(["- Missing in Source B", summary.missing_row_count or summary.missing_in_ledger_count])
    writer.writerow(["- Extra in Source B", summary.extra_row_count or summary.missing_in_bank_count])
    writer.writerow(["- Duplicate Entries", summary.duplicate_count or summary.possible_duplicate_count])
    writer.writerow(["- Unmatched Records", summary.unmatched_record_count or summary.unmatched_count])
    writer.writerow(["Alignment Rate (%)", f"{summary.reconciliation_rate:.1f}%"])
    writer.writerow(["Net Variance (INR)", f"{summary.total_variance:,.2f}"])
    writer.writerow([])

    # 3. Transaction-Level Detail Records
    writer.writerow([
        "Status",
        "Bank Date",
        "Ledger Date",
        "Description",
        "Reference",
        "Bank Amount",
        "Ledger Amount",
        "Difference",
        "Confidence",
        "Reason",
        "Suggested Action",
        "Difference Type",
        "Review Status",
    ])

    for item in items:
        diff_type_str = item.difference_type.value if item.difference_type else item.status.value
        val_a_str = f"{item.bank_amount:,.2f}" if item.bank_amount is not None else "—"
        val_b_str = f"{item.ledger_amount:,.2f}" if item.ledger_amount is not None else "—"
        diff_str = f"{abs(item.difference):,.2f}" if item.difference != 0 else "0.00"

        writer.writerow([
            item.status.value,
            item.bank_date or "—",
            item.ledger_date or "—",
            item.description,
            item.reference or "—",
            val_a_str,
            val_b_str,
            diff_str,
            item.confidence.upper(),
            item.reason,
            item.suggested_action,
            diff_type_str,
            item.review_status,
        ])

    return output.getvalue()


def generate_difference_excel_report(
    session: ReconciliationSessionResponse,
    file_a_name: Optional[str] = None,
    file_b_name: Optional[str] = None,
    sheet_a_name: Optional[str] = None,
    sheet_b_name: Optional[str] = None,
) -> bytes:
    """Generates a downloadable, professional Excel difference report (.xlsx).

    Worksheets:
    1. Summary: Metadata, compared files/sheets, difference statistics.
    2. Detected Differences: Detailed records with source provenance, rows, cells, and values.
    """
    wb = openpyxl.Workbook()
    # Sheet 1: Summary
    ws_summary = wb.active
    ws_summary.title = "Summary"

    # Styling Palettes
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    section_font = Font(name="Calibri", size=11, bold=True, color="0F172A")
    regular_font = Font(name="Calibri", size=10, color="334155")
    bold_cell_font = Font(name="Calibri", size=10, bold=True, color="1E293B")

    brand_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    subtle_fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    accent_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")

    thin_border = Border(
        left=Side(style="thin", color="E2E8F0"),
        right=Side(style="thin", color="E2E8F0"),
        top=Side(style="thin", color="E2E8F0"),
        bottom=Side(style="thin", color="E2E8F0"),
    )

    # 1. Summary Sheet Content
    ws_summary["A1"] = "FINANCE AI — DIFFERENCE DETECTION REPORT"
    ws_summary["A1"].font = title_font

    ws_summary["A2"] = f"Generated At: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    ws_summary["A2"].font = regular_font

    a_name = file_a_name or session.file_a_name or session.bank_statement_name
    b_name = file_b_name or session.file_b_name or session.ledger_file_name
    s_a = sheet_a_name or session.sheet_a_name or "Sheet1"
    s_b = sheet_b_name or session.sheet_b_name or "Sheet1"

    ws_summary["A4"] = "Source File A (Primary):"
    ws_summary["B4"] = f"{a_name} (Sheet: {s_a})"
    ws_summary["A5"] = "Source File B (Comparison):"
    ws_summary["B5"] = f"{b_name} (Sheet: {s_b})"
    ws_summary["A4"].font = bold_cell_font
    ws_summary["B4"].font = regular_font
    ws_summary["A5"].font = bold_cell_font
    ws_summary["B5"].font = regular_font

    ws_summary["A7"] = "DIFFERENCE SUMMARY METRICS"
    ws_summary["A7"].font = section_font

    summary = session.summary
    metrics = [
        ("Total Source A Records", summary.total_bank_transactions),
        ("Total Source B Records", summary.total_ledger_transactions),
        ("Matched Records", summary.matched_count),
        ("Total Differences Detected", summary.unmatched_count),
        ("— Changed Values", summary.changed_value_count or summary.amount_mismatch_count),
        ("— Missing in Comparison (File B)", summary.missing_row_count or summary.missing_in_ledger_count),
        ("— Extra in Comparison (File B)", summary.extra_row_count or summary.missing_in_bank_count),
        ("— Duplicate Entries", summary.duplicate_count or summary.possible_duplicate_count),
        ("— Unmatched Records", summary.unmatched_record_count or (summary.unmatched_count - (summary.changed_value_count or 0) - (summary.missing_row_count or 0) - (summary.extra_row_count or 0) - (summary.duplicate_count or 0))),
        ("Alignment Rate", f"{summary.reconciliation_rate:.1f}%"),
        ("Net Variance (INR)", f"₹{summary.total_variance:,.2f}" if summary.total_variance > 0 else "0.00"),
    ]

    ws_summary["A8"] = "Metric"
    ws_summary["B8"] = "Value"
    ws_summary["A8"].font = header_font
    ws_summary["B8"].font = header_font
    ws_summary["A8"].fill = brand_fill
    ws_summary["B8"].fill = brand_fill

    for r_idx, (m_label, m_val) in enumerate(metrics, start=9):
        ws_summary[f"A{r_idx}"] = m_label
        ws_summary[f"B{r_idx}"] = m_val
        ws_summary[f"A{r_idx}"].font = bold_cell_font if not m_label.startswith("—") else regular_font
        ws_summary[f"B{r_idx}"].font = regular_font
        ws_summary[f"A{r_idx}"].border = thin_border
        ws_summary[f"B{r_idx}"].border = thin_border
        if r_idx % 2 == 0:
            ws_summary[f"A{r_idx}"].fill = subtle_fill
            ws_summary[f"B{r_idx}"].fill = subtle_fill

    ws_summary.column_dimensions["A"].width = 38
    ws_summary.column_dimensions["B"].width = 38

    # Sheet 2: Detected Differences
    ws_diff = wb.create_sheet(title="Detected Differences")
    diff_headers = [
        "Difference ID",
        "Difference Type",
        "Status",
        "Voucher / Identifier",
        "Relevant Field",
        "Source File",
        "Sheet",
        "Source Row",
        "Cell",
        "File A Location",
        "File B Location",
        "File A Value",
        "File B Value",
        "Variance (INR)",
        "Confidence",
        "Reason / Evidence",
        "Review Status",
    ]

    for col_idx, h_text in enumerate(diff_headers, start=1):
        c_letter = get_column_letter(col_idx)
        cell = ws_diff[f"{c_letter}1"]
        cell.value = h_text
        cell.font = header_font
        cell.fill = brand_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row_num = 2
    for item in session.transactions:
        diff_type_val = item.difference_type.value if item.difference_type else item.status.value
        ref_val = item.reference or "—"
        field_val = item.relevant_field or ("Amount" if item.difference != 0 else "Record")

        # Primary source location provenance
        loc = item.source_a_location or item.source_b_location
        src_file = loc.file_name if loc and loc.file_name else (a_name if item.source_a_location else b_name)
        src_sheet = loc.sheet_name if loc and loc.sheet_name else (s_a if item.source_a_location else s_b)
        src_row = loc.row_number if loc and loc.row_number else "—"
        src_cell = loc.cell_address if loc and loc.cell_address else "—"

        # Provenance coordinates
        loc_a = "—"
        if item.source_a_location and item.source_a_location.row_number:
            cell_ref = f", Cell {item.source_a_location.cell_address}" if item.source_a_location.cell_address else ""
            loc_a = f"Row {item.source_a_location.row_number}{cell_ref}"

        loc_b = "—"
        if item.source_b_location and item.source_b_location.row_number:
            cell_ref = f", Cell {item.source_b_location.cell_address}" if item.source_b_location.cell_address else ""
            loc_b = f"Row {item.source_b_location.row_number}{cell_ref}"

        # Values
        val_a = f"₹{item.bank_amount:,.2f}" if item.bank_amount is not None else (str(item.source_a_value) if item.source_a_value is not None else "—")
        val_b = f"₹{item.ledger_amount:,.2f}" if item.ledger_amount is not None else (str(item.source_b_value) if item.source_b_value is not None else "—")
        diff_val = f"₹{abs(item.difference):,.2f}" if item.difference != 0 else ("0.00" if (item.bank_amount is not None or item.ledger_amount is not None) else "—")

        row_data = [
            item.id,
            diff_type_val,
            item.status.value,
            ref_val,
            field_val,
            src_file,
            src_sheet,
            src_row,
            src_cell,
            loc_a,
            loc_b,
            val_a,
            val_b,
            diff_val,
            item.confidence.upper(),
            item.reason,
            item.review_status,
        ]

        for c_idx, cell_value in enumerate(row_data, start=1):
            c_letter = get_column_letter(c_idx)
            cell = ws_diff[f"{c_letter}{row_num}"]
            cell.value = cell_value
            cell.font = regular_font
            cell.border = thin_border
            if row_num % 2 == 0:
                cell.fill = subtle_fill

        row_num += 1

    # Auto-fit column widths
    column_widths = {
        "A": 16,  # Difference ID
        "B": 20,  # Difference Type
        "C": 20,  # Status
        "D": 22,  # Voucher / Identifier
        "E": 20,  # Field Compared
        "F": 22,  # File A Location
        "G": 22,  # File B Location
        "H": 18,  # File A Value
        "I": 18,  # File B Value
        "J": 16,  # Variance
        "K": 14,  # Confidence
        "L": 45,  # Reason
        "M": 16,  # Review Status
    }
    for col_letter, width in column_widths.items():
        ws_diff.column_dimensions[col_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

