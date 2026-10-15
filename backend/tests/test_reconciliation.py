import io
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.modules.reconciliation.normalization import (
    NormalizationError,
    normalize_transactions,
    parse_clean_amount,
    parse_clean_date,
    preview_file,
)
from app.modules.reconciliation.matching import match_transactions
from app.modules.reconciliation.report import generate_reconciliation_csv_report
from app.modules.reconciliation.schemas import (
    NormalizedTransaction,
    ReconciliationRuleConfig,
    ReconciliationStatusEnum,
)
from app.core.database import Base, engine
import app.models  # Register all models
Base.metadata.create_all(bind=engine)

client = TestClient(fastapi_app)


def test_parse_clean_amount():
    assert parse_clean_amount("₹25,000.00") == 25000.0
    assert parse_clean_amount("$1,234.56") == 1234.56
    assert parse_clean_amount("(500.00)") == -500.0
    assert parse_clean_amount("750.50 Dr") == -750.50
    assert parse_clean_amount("1,000 Cr") == 1000.0
    assert parse_clean_amount("-250.00") == -250.0
    assert parse_clean_amount("") == 0.0
    assert parse_clean_amount(None) == 0.0


def test_parse_clean_date():
    assert parse_clean_date("2026-09-10") == "2026-09-10"
    assert parse_clean_date("10/09/2026") == "2026-09-10"
    assert parse_clean_date("10-09-2026") == "2026-09-10"
    assert parse_clean_date("10 Sep 2026") == "2026-09-10"


def test_normalization_with_sample_files():
    sample_bank = Path("sample_data/sample_bank_statement.csv")
    sample_ledger = Path("sample_data/sample_ledger.csv")

    assert sample_bank.exists(), "Sample bank file should exist"
    assert sample_ledger.exists(), "Sample ledger file should exist"

    bank_txs = normalize_transactions(sample_bank, "sample_bank_statement.csv", source="bank")
    ledger_txs = normalize_transactions(sample_ledger, "sample_ledger.csv", source="ledger")

    assert len(bank_txs) == 10
    assert len(ledger_txs) == 9

    # Check first bank tx
    first_b = bank_txs[0]
    assert first_b.date == "2026-09-02"
    assert first_b.amount == 14500.0
    assert first_b.reference == "TXN901021"


def test_deterministic_matching_categories():
    sample_bank = Path("sample_data/sample_bank_statement.csv")
    sample_ledger = Path("sample_data/sample_ledger.csv")

    bank_txs = normalize_transactions(sample_bank, "sample_bank_statement.csv", source="bank")
    ledger_txs = normalize_transactions(sample_ledger, "sample_ledger.csv", source="ledger")

    results, summary = match_transactions(bank_txs, ledger_txs, rules=ReconciliationRuleConfig(date_tolerance_days=1))

    # We should have matches
    matched = [r for r in results if r.status == ReconciliationStatusEnum.MATCHED]
    assert len(matched) >= 3, "Should have at least 3 exact matches (AWS, Lease, Retainer)"

    # We should have amount mismatch for Utility bill (25000 vs 24500)
    amt_mismatches = [r for r in results if r.status == ReconciliationStatusEnum.AMOUNT_MISMATCH]
    assert len(amt_mismatches) == 1
    assert amt_mismatches[0].reference == "TXN901024"
    assert amt_mismatches[0].difference == 500.0

    # We should have date mismatch for Vendor Hardware (2026-09-16 vs 2026-09-09 = 7 days diff)
    date_mismatches = [r for r in results if r.status == ReconciliationStatusEnum.DATE_MISMATCH]
    assert len(date_mismatches) == 1
    assert date_mismatches[0].reference == "TXN901025"

    # We should have reference mismatch or review for Audit fee (UTR789201 vs CHQ554011)
    ref_mismatches = [r for r in results if r.status == ReconciliationStatusEnum.REFERENCE_MISMATCH]
    assert len(ref_mismatches) == 1

    # Missing in ledger: Bank charges (CHG202609) and Interest (INT202609)
    missing_ledger = [r for r in results if r.status == ReconciliationStatusEnum.MISSING_IN_LEDGER]
    assert len(missing_ledger) >= 2

    # Missing in bank: Apex Logistics (CHQ991001) and Petty Cash (VCH402)
    missing_bank = [r for r in results if r.status == ReconciliationStatusEnum.MISSING_IN_BANK]
    assert len(missing_bank) >= 2

    # Duplicate detection: SaaS subscription SUB88102
    dups = [r for r in results if r.status == ReconciliationStatusEnum.POSSIBLE_DUPLICATE]
    assert len(dups) >= 1

    assert summary.total_bank_transactions == 10
    assert summary.total_ledger_transactions == 9
    assert summary.reconciliation_rate > 0.0


def test_empty_and_invalid_file_handling():
    empty_csv = b""
    with pytest.raises(NormalizationError):
        normalize_transactions(empty_csv, "empty.csv", source="bank")

    invalid_csv = b"Col1,Col2\nVal1,Val2"
    with pytest.raises(NormalizationError):
        normalize_transactions(invalid_csv, "invalid.csv", source="bank")


def test_csv_report_generation():
    sample_bank = Path("sample_data/sample_bank_statement.csv")
    sample_ledger = Path("sample_data/sample_ledger.csv")

    bank_txs = normalize_transactions(sample_bank, "sample_bank_statement.csv", source="bank")
    ledger_txs = normalize_transactions(sample_ledger, "sample_ledger.csv", source="ledger")

    results, summary = match_transactions(bank_txs, ledger_txs)
    report_csv = generate_reconciliation_csv_report("Bank Statement", "Ledger", summary, results)

    assert "FINANCE AI — BANK RECONCILIATION AUDIT REPORT" in report_csv
    assert "RECONCILIATION SUMMARY" in report_csv
    assert "Status,Bank Date,Ledger Date" in report_csv
    assert "MATCHED" in report_csv
    assert "AMOUNT_MISMATCH" in report_csv


def test_api_reconciliation_workflow():
    sample_bank_content = Path("sample_data/sample_bank_statement.csv").read_bytes()
    sample_ledger_content = Path("sample_data/sample_ledger.csv").read_bytes()

    # 1. Test preview-file endpoint
    preview_res = client.post(
        "/api/v1/reconciliation/preview-file",
        files={"file": ("bank.csv", io.BytesIO(sample_bank_content), "text/csv")},
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["total_rows"] == 10
    assert "date" in preview_data["column_mapping"]

    # 2. Test run reconciliation endpoint
    run_res = client.post(
        "/api/v1/reconciliation/run",
        files={
            "bank_file": ("test_bank.csv", io.BytesIO(sample_bank_content), "text/csv"),
            "ledger_file": ("test_ledger.csv", io.BytesIO(sample_ledger_content), "text/csv"),
        },
        data={"date_tolerance_days": 1, "amount_tolerance": 0.0},
    )
    assert run_res.status_code == 201
    run_data = run_res.json()
    session_id = run_data["id"]
    assert session_id > 0
    assert run_data["summary"]["total_bank_transactions"] == 10
    assert len(run_data["transactions"]) > 0

    # 3. Test get results endpoint
    get_res = client.get(f"/api/v1/reconciliation/results/{session_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == session_id

    # 4. Test download report endpoint
    rep_res = client.get(f"/api/v1/reconciliation/results/{session_id}/report")
    assert rep_res.status_code == 200
    assert "text/csv" in rep_res.headers["content-type"]
    assert "FINANCE AI — BANK RECONCILIATION AUDIT REPORT" in rep_res.text

    # 5. Verify history record was automatically logged
    history_res = client.get("/api/v1/history?module=reconciliation")
    assert history_res.status_code == 200
    histories = history_res.json()
    assert any("reconciliation_completed" in h["action"] for h in histories)


# =========================================================================
# REGRESSION TESTS: NUMERIC COLUMN NAMES & REAL-WORLD EXCEL HANDLING
# =========================================================================

import numpy as np
import pandas as pd
from app.modules.reconciliation.normalization import (
    deduplicate_columns,
    normalize_column_name,
    normalize_dataframe_columns,
    preview_dataframe,
    serialize_scalar,
)


def test_exact_bug_numeric_column_name_float():
    """
    Exact regression test for the reported bug:
    DataFrame column name is float 7397632.427999999.
    Expected: dict key normalized to string '7397632.427999999', numeric values preserved,
    and NO Pydantic validation error.
    """
    columns = [7397632.427999999, "Date", "Description", "Amount"]
    data = [
        {
            7397632.427999999: 1000.0,
            "Date": "2026-09-01",
            "Description": "Cloud Hosting",
            "Amount": 14500.50,
        },
        {
            7397632.427999999: 2000.0,
            "Date": "2026-09-02",
            "Description": "Office Rent",
            "Amount": 45000.00,
        },
    ]
    df = pd.DataFrame(data)

    preview = preview_dataframe(df, "statement.xlsx")

    # 1. Validation succeeds
    assert preview.total_rows == 2
    assert "7397632.427999999" in preview.detected_columns
    assert preview.column_mapping["date"] == "Date"
    assert preview.column_mapping["amount"] == "Amount"
    assert preview.status == "ready"

    # 2. Key is string, NOT float
    sample_row = preview.sample_rows[0]
    assert "7397632.427999999" in sample_row
    assert not any(isinstance(k, float) for k in sample_row.keys())

    # 3. Numeric values remain numeric
    assert isinstance(sample_row["Amount"], (int, float))
    assert sample_row["Amount"] == 14500.50
    assert isinstance(sample_row["7397632.427999999"], (int, float))
    assert sample_row["7397632.427999999"] == 1000.0

    # 4. Model dump produces valid dict
    dumped = preview.model_dump()
    assert isinstance(dumped["sample_rows"][0]["7397632.427999999"], float)


def test_column_normalization_various_types():
    """
    Tests column normalization handles int, float, None, NaN, duplicates, and normal strings safely.
    """
    raw_cols = [
        2024,
        7397632.427999999,
        None,
        float("nan"),
        "Amount",
        "Amount",
        "Date",
        "Description",
    ]
    df = pd.DataFrame(columns=raw_cols)
    norm_df = normalize_dataframe_columns(df)
    cols = list(norm_df.columns)

    # All column names must be strings
    assert all(isinstance(c, str) for c in cols)
    # Check specific normalizations
    assert cols[0] == "2024"
    assert cols[1] == "7397632.427999999"
    assert cols[2] == "Unnamed_Column_3"
    assert cols[3] == "Unnamed_Column_4"
    assert cols[4] == "Amount"
    assert cols[5] == "Amount_2"
    assert cols[6] == "Date"
    assert cols[7] == "Description"

    # Ensure uniqueness
    assert len(cols) == len(set(cols))


def test_sample_row_scalar_serialization():
    """
    Tests serialize_scalar converts NaN and inf to None, preserves ints and floats, and formats dates.
    """
    assert serialize_scalar(1000) == 1000
    assert serialize_scalar(1450.50) == 1450.50
    assert serialize_scalar(np.int64(42)) == 42
    assert serialize_scalar(np.float64(7397632.428)) == 7397632.428
    assert serialize_scalar(np.nan) is None
    assert serialize_scalar(float("nan")) is None
    assert serialize_scalar(float("inf")) is None
    assert serialize_scalar(float("-inf")) is None
    assert serialize_scalar(None) is None
    assert serialize_scalar(pd.Timestamp("2026-09-02")) == "2026-09-02"
    assert serialize_scalar("Vendor Payment") == "Vendor Payment"


def test_preview_file_endpoint_with_float_column_csv():
    """
    Tests preview endpoint with a CSV containing float column header.
    """
    csv_content = (
        "7397632.427999999,Date,Description,Amount\n"
        "1000,2026-09-01,Cloud Hosting,14500.50\n"
        "2000,2026-09-02,Office Rent,45000.00\n"
    ).encode("utf-8")

    res = client.post(
        "/api/v1/reconciliation/preview-file",
        files={"file": ("float_header.csv", io.BytesIO(csv_content), "text/csv")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"] == 2
    assert "7397632.427999999" in data["detected_columns"]
    assert data["column_mapping"]["amount"] == "Amount"
    assert data["sample_rows"][0]["Amount"] == 14500.50


def test_preview_file_endpoint_with_float_column_xlsx():
    """
    Tests preview endpoint with an XLSX containing float column header.
    """
    df = pd.DataFrame([
        {7397632.427999999: 1000.0, "Date": "2026-09-01", "Description": "Cloud Hosting", "Amount": 14500.50},
        {7397632.427999999: 2000.0, "Date": "2026-09-02", "Description": "Office Rent", "Amount": 45000.00},
    ])
    xlsx_buf = io.BytesIO()
    df.to_excel(xlsx_buf, index=False)
    xlsx_buf.seek(0)

    res = client.post(
        "/api/v1/reconciliation/preview-file",
        files={
            "file": (
                "float_header.xlsx",
                xlsx_buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_rows"] == 2
    assert "7397632.427999999" in data["detected_columns"]
    assert data["sample_rows"][0]["Amount"] == 14500.50
    assert data["sample_rows"][0]["7397632.427999999"] == 1000.0


def test_realistic_accounting_workbook_with_title_and_blank_rows():
    """
    Real-world accounting workbook containing:
    - title rows
    - blank rows
    - opening balance metadata with float numbers
    - header row with transaction columns (Date, Particulars, Chq No, Debit, Credit)
    - financial data rows
    Verify preview detects the header, maps columns, and does not crash.
    """
    raw_sheet_data = [
        ["ACME GLOBAL ENTERPRISES PVT LTD", None, None, None, None, None],
        ["BANK ACCOUNT STATEMENT: 01-SEP-2026 TO 30-SEP-2026", None, None, None, None, None],
        ["Account: 9988776655", "Currency: INR", None, "Opening Balance:", 7397632.427999999, None],
        [None, None, None, None, None, None],  # blank row
        ["Date", "Particulars", "Cheque / Ref No", "Debit", "Credit", "Balance"],
        ["2026-09-01", "Opening Balance", "", None, None, 7397632.43],
        ["2026-09-02", "AWS Cloud Infrastructure Hosting", "TXN901021", 14500.00, None, 7383132.43],
        ["2026-09-05", "Commercial Office Lease September", "TXN901022", 45000.00, None, 7338132.43],
        ["2026-09-08", "Client Retainer Inflow - Acme Corp", "TXN901023", None, 120000.00, 7458132.43],
    ]
    wb_df = pd.DataFrame(raw_sheet_data)
    xlsx_buf = io.BytesIO()
    wb_df.to_excel(xlsx_buf, header=False, index=False)
    xlsx_buf.seek(0)

    res = client.post(
        "/api/v1/reconciliation/preview-file",
        files={
            "file": (
                "realistic_bank_statement.xlsx",
                xlsx_buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ready"
    assert data["column_mapping"]["date"] == "Date"
    assert data["column_mapping"]["description"] == "Particulars"
    assert data["column_mapping"]["debit"] == "Debit"
    assert data["column_mapping"]["credit"] == "Credit"
    assert data["total_rows"] >= 4
    # Verify transaction debit amount remains numeric
    assert data["sample_rows"][1]["Debit"] == 14500.00


def test_ambiguous_workbook_returns_review_required():
    """
    Tests that an ambiguous workbook with no recognizable financial header row
    gracefully returns status: REVIEW_REQUIRED with descriptive message,
    and does NOT crash with a Pydantic validation error.
    """
    ambiguous_data = [
        ["Notes and Observations", "Department", "Score"],
        ["Review ongoing", "Finance", 85.5],
        ["Pending sign-off", "Audit", 92.0],
    ]
    df = pd.DataFrame(ambiguous_data[1:], columns=ambiguous_data[0])
    xlsx_buf = io.BytesIO()
    df.to_excel(xlsx_buf, index=False)
    xlsx_buf.seek(0)

    res = client.post(
        "/api/v1/reconciliation/preview-file",
        files={
            "file": (
                "ambiguous_notes.xlsx",
                xlsx_buf,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "REVIEW_REQUIRED"
    assert "Unable to confidently determine the transaction header row" in data["message"]
    assert len(data["sample_rows"]) == 2


def test_full_reconciliation_with_xlsx_bank_and_ledger():
    """
    Tests running end-to-end reconciliation using both Bank Statement XLSX
    and Accounting Ledger XLSX containing numeric columns.
    """
    bank_rows = [
        {7397632.427999999: "REF_A", "Date": "2026-09-02", "Description": "AWS Cloud", "Reference": "TXN901", "Withdrawal": 14500.00, "Deposit": 0.0},
        {7397632.427999999: "REF_B", "Date": "2026-09-05", "Description": "Office Lease", "Reference": "TXN902", "Withdrawal": 45000.00, "Deposit": 0.0},
    ]
    ledger_rows = [
        {99999.99: "LED_A", "Date": "2026-09-02", "Particulars": "AWS Cloud", "Voucher No": "TXN901", "Debit": 14500.00, "Credit": 0.0},
        {99999.99: "LED_B", "Date": "2026-09-05", "Particulars": "Office Lease", "Voucher No": "TXN902", "Debit": 45000.00, "Credit": 0.0},
    ]

    bank_buf = io.BytesIO()
    pd.DataFrame(bank_rows).to_excel(bank_buf, index=False)
    bank_buf.seek(0)

    ledger_buf = io.BytesIO()
    pd.DataFrame(ledger_rows).to_excel(ledger_buf, index=False)
    ledger_buf.seek(0)

    res = client.post(
        "/api/v1/reconciliation/run",
        files={
            "bank_file": ("bank.xlsx", bank_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
            "ledger_file": ("ledger.xlsx", ledger_buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        },
        data={"date_tolerance_days": 1, "amount_tolerance": 0.0},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["summary"]["total_bank_transactions"] == 2
    assert data["summary"]["total_ledger_transactions"] == 2
    assert data["summary"]["matched_count"] == 2
    assert data["status"] == "completed"
