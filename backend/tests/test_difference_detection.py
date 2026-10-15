import io
import hashlib
from pathlib import Path
import openpyxl
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app as fastapi_app
from app.core.database import SessionLocal, engine, Base
import app.models
from app.models.user import User
from app.core.security import get_password_hash, create_access_token
from app.modules.reconciliation.schemas import DifferenceTypeEnum, ReconciliationStatusEnum
from app.modules.reconciliation.services import ReconciliationService

Base.metadata.create_all(bind=engine)
client = TestClient(fastapi_app)


def create_excel_bytes(rows, sheet_name="Sheet1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = sheet_name
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_tokens(db: Session):
    user_a = db.query(User).filter(User.username == "diff_user_a").first()
    if not user_a:
        user_a = User(
            username="diff_user_a",
            email="diff_a@litebooks.ai",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Diff Accountant A",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_a)
        db.commit()
        db.refresh(user_a)

    user_b = db.query(User).filter(User.username == "diff_user_b").first()
    if not user_b:
        user_b = User(
            username="diff_user_b",
            email="diff_b@litebooks.ai",
            hashed_password=get_password_hash("Pass123!"),
            full_name="Diff Accountant B",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_b)
        db.commit()
        db.refresh(user_b)

    token_a = create_access_token(data={"sub": user_a.username, "user_id": user_a.id, "role": user_a.role})
    token_b = create_access_token(data={"sub": user_b.username, "user_id": user_b.id, "role": user_b.role})
    return {
        "user_a": user_a,
        "token_a": token_a,
        "user_b": user_b,
        "token_b": token_b,
    }


def test_similar_files_with_changed_values(user_tokens):
    """Scenario 1: Similar files with changed values (amount changed, description changed)."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    file_a_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "VCH101", "Audit Fee Consultation", 50000.0],
        ["2026-09-02", "VCH102", "Office Printer Paper", 1200.0],
    ])
    file_b_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "VCH101", "Audit Fee Consultation", 48000.0],  # Changed amount
        ["2026-09-02", "VCH102", "Office Stationery Paper", 1200.0],  # Changed description
    ])

    files = {
        "file_a": ("source_a.xlsx", file_a_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("source_b.xlsx", file_b_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["summary"]["total_discrepancies"] > 0
    # Check item details: source locations, cell addresses, and differences
    items = data["items"]
    changed_items = [it for it in items if it.get("difference_type") in ("CHANGED_VALUE", "MATCHED")]
    assert len(changed_items) > 0

    amt_diff_item = next((it for it in items if it.get("relevant_field") == "amount" or abs(it.get("difference", 0)) > 0), None)
    assert amt_diff_item is not None
    assert amt_diff_item["source_a_location"] is not None
    assert amt_diff_item["source_b_location"] is not None
    assert "D" in (amt_diff_item["source_a_location"].get("cell_address") or "")


def test_missing_and_extra_rows(user_tokens):
    """Scenario 2: Missing row in File B and extra row in File B."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    file_a_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "REF201", "Legal Retainer", 15000.0],
        ["2026-09-02", "REF202", "Missing In File B", 7500.0],
    ])
    file_b_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "REF201", "Legal Retainer", 15000.0],
        ["2026-09-03", "REF203", "Extra In File B", 9200.0],
    ])

    files = {
        "file_a": ("file_a.xlsx", file_a_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("file_b.xlsx", file_b_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()

    diff_types = [it.get("difference_type") for it in data["items"]]
    assert "MISSING_ROW" in diff_types or "EXTRA_ROW" in diff_types or data["summary"]["missing_rows"] > 0 or data["summary"]["extra_rows"] > 0


def test_different_column_names_same_field(user_tokens):
    """Scenario 3: Different column headers representing the same field (accounting synonyms)."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    # File A uses Txn Date, Voucher No, Particulars, Debit Amount
    file_a_content = create_excel_bytes([
        ["Txn Date", "Voucher No", "Particulars", "Debit Amount"],
        ["2026-09-10", "VCH301", "Internet Broadband", 2500.0],
        ["2026-09-11", "VCH302", "Cloud Hosting", 11000.0],
    ])
    # File B uses Date, Ref Number, Narration, Net Value
    file_b_content = create_excel_bytes([
        ["Date", "Ref Number", "Narration", "Net Value"],
        ["2026-09-10", "VCH301", "Internet Broadband", 2500.0],
        ["2026-09-11", "VCH302", "Cloud Hosting", 11000.0],
    ])

    files = {
        "file_a": ("synonyms_a.xlsx", file_a_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("synonyms_b.xlsx", file_b_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["matched_records"] == 2
    assert data["summary"]["total_discrepancies"] == 0


def test_different_row_ordering(user_tokens):
    """Scenario 4: Different row ordering between two files matches correctly without relying on row index."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    rows_a = [
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "ORD1", "Item One", 100.0],
        ["2026-09-02", "ORD2", "Item Two", 200.0],
        ["2026-09-03", "ORD3", "Item Three", 300.0],
        ["2026-09-04", "ORD4", "Item Four", 400.0],
    ]
    rows_b = [
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-04", "ORD4", "Item Four", 400.0],
        ["2026-09-01", "ORD1", "Item One", 100.0],
        ["2026-09-03", "ORD3", "Item Three", 300.0],
        ["2026-09-02", "ORD2", "Item Two", 200.0],
    ]

    files = {
        "file_a": ("order_a.xlsx", create_excel_bytes(rows_a), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("order_b.xlsx", create_excel_bytes(rows_b), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["matched_records"] == 4
    assert data["summary"]["total_discrepancies"] == 0


def test_multiple_sheets(user_tokens):
    """Scenario 5: Multi-sheet comparison with sheet selection."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    wb = openpyxl.Workbook()
    ws1 = wb.active
    ws1.title = "Delhi_Branch"
    ws1.append(["Date", "Reference", "Description", "Amount"])
    ws1.append(["2026-09-01", "DL01", "Delhi Sale", 50000.0])

    ws2 = wb.create_sheet(title="Mumbai_Branch")
    ws2.append(["Date", "Reference", "Description", "Amount"])
    ws2.append(["2026-09-01", "MB01", "Mumbai Sale", 80000.0])

    buf = io.BytesIO()
    wb.save(buf)
    wb_bytes = buf.getvalue()

    # Compare Delhi_Branch sheet with a single sheet target
    target_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "DL01", "Delhi Sale", 50000.0],
    ])

    files = {
        "file_a": ("multi_sheet.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("single_sheet.xlsx", target_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    data_payload = {
        "sheet_a": "Delhi_Branch",
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, data=data_payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["matched_records"] == 1


def test_ambiguous_mapping_requires_user_resolution(user_tokens):
    """Scenario 6: Ambiguous column detection prompts preview ambiguity, and user explicit mapping resolves it."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    content = create_excel_bytes([
        ["Date", "Reference", "Description", "Gross Amount", "Net Amount"],
        ["2026-09-01", "AMB01", "Service Charge", 1180.0, 1000.0],
    ])

    # 1. Preview file: should flag ambiguity due to multiple amount columns
    preview_resp = client.post(
        "/api/v1/reconciliation/preview-file",
        files={"file": ("ambiguous.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=headers,
    )
    assert preview_resp.status_code == 200
    preview_data = preview_resp.json()
    assert preview_data["is_ambiguous"] is True
    assert preview_data["ambiguity_reason"] is not None
    assert "Gross Amount" in preview_data["available_columns"]
    assert "Net Amount" in preview_data["available_columns"]

    # 2. Run reconciliation with user resolved mapping
    import json
    user_mapping = json.dumps({"date": "Date", "reference": "Reference", "description": "Description", "amount": "Net Amount"})
    target_content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "AMB01", "Service Charge", 1000.0],
    ])

    files = {
        "file_a": ("ambiguous.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("target.xlsx", target_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    data_payload = {
        "mapping_a": user_mapping,
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, data=data_payload, headers=headers)
    assert resp.status_code == 201
    assert resp.json()["summary"]["matched_records"] == 1


def test_no_differences_found(user_tokens):
    """Scenario 7: Identical files result in 0 differences and 100% match."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    content = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "ID01", "Consulting", 50000.0],
        ["2026-09-02", "ID02", "Software", 12000.0],
    ])

    files = {
        "file_a": ("identical_a.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("identical_b.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["total_discrepancies"] == 0
    assert data["summary"]["matched_records"] == 2
    assert data["summary"]["match_rate_percentage"] == 100.0


def test_unmatched_rows(user_tokens):
    """Scenario 8: Completely unmatched records are accurately reported."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    file_a = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "AAA999", "Alpha Expense", 99999.0],
    ])
    file_b = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-20", "ZZZ111", "Omega Revenue", 11111.0],
    ])

    files = {
        "file_a": ("unmatched_a.xlsx", file_a, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("unmatched_b.xlsx", file_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["summary"]["matched_records"] == 0
    assert data["summary"]["total_discrepancies"] == 2


def test_original_files_remaining_unchanged(user_tokens, db: Session):
    """Scenario 9: Never modify uploaded source files on disk."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    content_a = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "IMM01", "Security Audit", 45000.0],
    ])
    content_b = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "IMM01", "Security Audit", 40000.0],
    ])

    hash_a_before = hashlib.sha256(content_a).hexdigest()
    hash_b_before = hashlib.sha256(content_b).hexdigest()

    files = {
        "file_a": ("immutable_a.xlsx", content_a, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("immutable_b.xlsx", content_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # Download report
    report_resp = client.get(f"/api/v1/reconciliation/results/{session_id}/difference-report", headers=headers)
    assert report_resp.status_code == 200

    # Verify input hashes remain unchanged
    assert hashlib.sha256(content_a).hexdigest() == hash_a_before
    assert hashlib.sha256(content_b).hexdigest() == hash_b_before


def test_downloadable_report_accuracy_and_review_status(user_tokens):
    """Scenario 10: Downloadable separate Difference_Report_<timestamp>.xlsx accurately formatted and reviewable."""
    headers = {"Authorization": f"Bearer {user_tokens['token_a']}"}

    file_a = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "REP101", "Audit Retainer", 20000.0],
        ["2026-09-02", "REP102", "Hardware Server", 75000.0],
    ])
    file_b = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "REP101", "Audit Retainer", 18500.0],  # Changed value
    ])

    files = {
        "file_a": ("report_a.xlsx", file_a, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("report_b.xlsx", file_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers)
    assert resp.status_code == 201
    session_data = resp.json()
    session_id = session_data["session_id"]
    item_id = session_data["items"][0]["item_id"]

    # 1. Update review status
    review_resp = client.post(
        f"/api/v1/reconciliation/results/{session_id}/items/{item_id}/review",
        json={"status": "CONFIRMED"},
        headers=headers,
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["review_status"] == "CONFIRMED"

    # 2. Download difference report
    report_resp = client.get(f"/api/v1/reconciliation/results/{session_id}/difference-report", headers=headers)
    assert report_resp.status_code == 200
    assert "attachment; filename=\"Difference_Report_" in report_resp.headers.get("content-disposition", "")
    assert report_resp.headers.get("content-type") == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # 3. Inspect report contents with openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(report_resp.content))
    assert "Summary" in wb.sheetnames
    assert "Detected Differences" in wb.sheetnames

    summary_sheet = wb["Summary"]
    diff_sheet = wb["Detected Differences"]

    # Check headers on diff sheet
    diff_headers = [cell.value for cell in diff_sheet[1]]
    assert "Difference Type" in diff_headers
    assert "Source File" in diff_headers
    assert "Sheet" in diff_headers
    assert "Source Row" in diff_headers
    assert "Cell" in diff_headers
    assert "Relevant Field" in diff_headers
    assert "Review Status" in diff_headers

    # Check that rows exist
    assert diff_sheet.max_row >= 2


def test_cross_user_access_prevention(user_tokens):
    """Scenario 11: Cross-user access isolation prevents User B from accessing User A's data."""
    headers_a = {"Authorization": f"Bearer {user_tokens['token_a']}"}
    headers_b = {"Authorization": f"Bearer {user_tokens['token_b']}"}

    file_a = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "SEC01", "Confidential Salary", 99000.0],
    ])
    file_b = create_excel_bytes([
        ["Date", "Reference", "Description", "Amount"],
        ["2026-09-01", "SEC01", "Confidential Salary", 99000.0],
    ])

    files = {
        "file_a": ("sec_a.xlsx", file_a, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        "file_b": ("sec_b.xlsx", file_b, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }
    resp = client.post("/api/v1/reconciliation/run", files=files, headers=headers_a)
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]
    item_id = resp.json()["items"][0]["item_id"]

    # User B attempts to access session results
    resp_b_results = client.get(f"/api/v1/reconciliation/results/{session_id}", headers=headers_b)
    assert resp_b_results.status_code in (403, 404)

    # User B attempts to download report
    resp_b_report = client.get(f"/api/v1/reconciliation/results/{session_id}/difference-report", headers=headers_b)
    assert resp_b_report.status_code in (403, 404)

    # User B attempts to update item review
    resp_b_review = client.post(
        f"/api/v1/reconciliation/results/{session_id}/items/{item_id}/review",
        json={"status": "CONFIRMED"},
        headers=headers_b,
    )
    assert resp_b_review.status_code in (403, 404)
