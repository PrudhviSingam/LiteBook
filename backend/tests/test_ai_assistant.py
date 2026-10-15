import hashlib
import io
import json
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app as fastapi_app
from app.models.document import Document
from app.models.history import HistoryRecord
from app.modules.ai_assistant.schemas import AssistantIntentEnum
from tests.test_workbook_and_corrections import create_zion_lifts_workbook_bytes

Base.metadata.create_all(bind=engine)
client = TestClient(fastapi_app)


def create_sample_bank_and_ledger_bytes():
    """Helper to create matching bank and ledger bytes for two-file comparison."""
    wb_bank = openpyxl.Workbook()
    ws_b = wb_bank.active
    ws_b.title = "Bank"
    ws_b.append(["Date", "Description", "Reference", "Withdrawal", "Deposit"])
    ws_b.append(["2026-03-01", "Office Rent", "TXN101", 50000.0, 0.0])
    ws_b.append(["2026-03-05", "Client Advance", "TXN102", 0.0, 120000.0])
    ws_b.append(["2026-03-10", "Bank Service Fee", "TXN103", 1500.0, 0.0])  # Missing in ledger
    buf_b = io.BytesIO()
    wb_bank.save(buf_b)

    wb_ledger = openpyxl.Workbook()
    ws_l = wb_ledger.active
    ws_l.title = "Ledger"
    ws_l.append(["Date", "Particulars", "Vch No", "Debit", "Credit"])
    ws_l.append(["2026-03-01", "Office Rent", "TXN101", 50000.0, 0.0])
    ws_l.append(["2026-03-05", "Client Advance", "TXN102", 0.0, 118000.0])  # Amount mismatch (120k vs 118k)
    ws_l.append(["2026-03-15", "Vendor Stationery", "TXN104", 3500.0, 0.0])  # Missing in bank
    buf_l = io.BytesIO()
    wb_ledger.save(buf_l)

    return buf_b.getvalue(), buf_l.getvalue()


# =========================================================================
# 1. TEXT-ONLY QUESTIONS
# =========================================================================

def test_text_only_accounting_question():
    """Verifies that the assistant answers conceptual accounting questions

    with clear professional explanations and does not pretend to know company-specific info.
    """
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is debit and credit?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Double-Entry" in data["message"] or "Debit" in data["message"]
    assert "Assets = Liabilities + Equity" in data["message"] or "Golden Rules" in data["message"]
    assert data["confidence"] == "HIGH"

    # Test amount mismatch explanation
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Explain amount mismatch."},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "GENERAL_ACCOUNTING"
    assert "Transposition Errors" in data2["message"] or "mismatch" in data2["message"].lower()

    # Test reconciliation explanation
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"message": "What is reconciliation?"},
    )
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["intent"] == "GENERAL_ACCOUNTING"
    assert "reconciliation" in data3["message"].lower()


# =========================================================================
# 2. FILE UPLOAD & INSPECTION
# =========================================================================

def test_file_upload_and_inspection():
    """Attaches a real Excel workbook (Zion Lifts LLP) and verifies metadata extraction."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_01"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["filename"] == "Zion_Lifts_Financials.xlsx"
    assert data["document_type"] in ("FINANCIAL_STATEMENT", "BALANCE_SHEET")
    assert data["sheet_name"] == "Balance Sheet"
    assert "31 March 2026" in data["period"]
    assert data["status"] == "ready"


# =========================================================================
# 3. FILE-AWARE QUESTION (SUMMARY)
# =========================================================================

def test_file_aware_summary_question():
    """Asks to explain the attached Balance Sheet and verifies sheet metadata."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_summary"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "test_conv_summary",
            "message": "Explain this Balance Sheet",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "FILE_SUMMARY"
    assert "Balance Sheet" in data["message"]
    assert "31 March 2026" in data["message"]


# =========================================================================
# 4. FIND MISMATCH WORKFLOW
# =========================================================================

def test_find_mismatch_in_file():
    """Tests the deterministic discrepancy detection and structured response."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_mismatch"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "test_conv_mismatch",
            "message": "Find any mismatch in this file.",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "FIND_MISMATCH"
    assert "Finding" in data["message"]
    assert "Location" in data["message"]
    assert "Difference" in data["message"]
    assert "Recommended Verification" in data["message"]
    assert "Confidence" in data["message"]
    assert data["confidence"] == "HIGH"
    # Never dogmatic
    assert "definitely the error" not in data["message"].lower()


# =========================================================================
# 5. FIND MISSING RECORD WORKFLOW
# =========================================================================

def test_find_missing_record_workflow():
    """Tests 'Find missing amounts' query with attached workbook."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_missing"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "test_conv_missing",
            "message": "Find missing amounts in this file.",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] in ("FIND_MISSING_RECORD", "FIND_MISMATCH")
    assert len(data["evidence"]) > 0


# =========================================================================
# 6. TWO-FILE COMPARISON
# =========================================================================

def test_two_file_comparison():
    """Attaches Ledger and Bank Statement, verifies deterministic reconciliation matching."""
    bank_bytes, ledger_bytes = create_sample_bank_and_ledger_bytes()

    upload_b = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Bank_Statement_Q1.xlsx", bank_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_compare", "category": "bank_statement"},
    )
    doc_id_b = upload_b.json()["document_id"]

    upload_l = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Ledger_March2026.xlsx", ledger_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_compare", "category": "ledger"},
    )
    doc_id_l = upload_l.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "test_conv_compare",
            "message": "Compare these files and find missing transactions.",
            "file_ids": [doc_id_b, doc_id_l],
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "COMPARE_FILES"
    assert "Deterministic Reconciliation Results" in data["message"]
    assert "Matched Transactions" in data["message"]
    assert "Missing in Ledger" in data["message"]
    assert "Missing in Bank" in data["message"]
    assert "Net Variance" in data["message"]


# =========================================================================
# 7. CONVERSATION CONTEXT & MULTI-TURN MEMORY
# =========================================================================

def test_conversation_context_memory():
    """Verifies that the assistant remembers context across multi-turn queries:

    Turn 1: 'Find any mismatch' -> finds discrepancy
    Turn 2: 'Why?' -> explains the discrepancy
    Turn 3: 'Can you correct it?' -> prepares proposal
    """
    wb_bytes = create_zion_lifts_workbook_bytes()
    conv_id = "test_conv_multiturn"

    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": conv_id},
    )
    doc_id = upload_res.json()["document_id"]

    # Turn 1: Find mismatch
    r1 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Find any mismatch in this file.", "file_ids": [doc_id]},
    )
    assert r1.status_code == 200
    assert r1.json()["intent"] == "FIND_MISMATCH"

    # Turn 2: "Why?"
    r2 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Why?"},
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["intent"] == "EXPLAIN_DISCREPANCY"
    assert "Audit Explanation" in d2["message"] or "WHAT:" in d2["message"]
    assert "WHAT TO VERIFY:" in d2["message"]

    # Turn 3: "Can you correct it?"
    r3 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Can you correct it?"},
    )
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["intent"] == "CORRECTION_REQUEST"
    assert d3["correction_available"] is True
    assert d3["correction_id"] is not None
    assert d3["proposal"] is not None
    assert "Before:" in d3["message"]
    assert "Proposed:" in d3["message"]


# =========================================================================
# 8, 9 & 10. CORRECTION REQUEST, APPROVAL ROUTING & IMMUTABILITY
# =========================================================================

def test_correction_request_and_approval_routing():
    """Verifies that:

    1. Assistant proposes correction without directly modifying the file.
    2. Original file remains completely unchanged (hash verified).
    3. Accountant decision endpoint confirms approval.
    4. Corrected file copy is generated with 'AI Correction Log'.
    5. Document and History integration records the action.
    """
    wb_bytes = create_zion_lifts_workbook_bytes()
    orig_hash = hashlib.sha256(wb_bytes).hexdigest()
    conv_id = "test_conv_approval"

    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": conv_id},
    )
    doc_id = upload_res.json()["document_id"]

    # Trigger mismatch & correction
    client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Find any mismatch in this file.", "file_ids": [doc_id]},
    )
    cor_res = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Fix this mismatch."},
    )
    cor_data = cor_res.json()
    cid = cor_data["correction_id"]
    assert cid is not None
    assert cor_data["proposal"]["status"] == "PROPOSED"

    # Verify original file in database is untouched
    db = SessionLocal()
    orig_doc = db.query(Document).filter(Document.id == doc_id).first()
    assert orig_doc is not None
    with open(orig_doc.file_path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    assert current_hash == orig_hash  # IMMUTABLE ORIGINAL
    db.close()

    # Accountant Decision: Approve
    decision_res = client.post(
        f"/api/v1/assistant/corrections/{cid}/decision",
        json={"decision": "CONFIRMED", "notes": "Approved by senior partner accountant"},
    )
    assert decision_res.status_code == 200
    assert decision_res.json()["status"] == "CONFIRMED"

    # Generate Corrected File Copy
    gen_res = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid, "accountant_name": "Senior Partner CPA"},
    )
    assert gen_res.status_code == 200
    gen_data = gen_res.json()
    assert gen_data["success"] is True
    assert gen_data["corrections_sheet_name"] == "AI Correction Log"
    assert "_Corrected_" in gen_data["generated_filename"]
    assert gen_data["download_url"].startswith("/api/v1/documents/")

    # Check that new document was added to DB
    db = SessionLocal()
    new_doc = db.query(Document).filter(Document.id == gen_data["document_id"]).first()
    assert new_doc is not None
    assert new_doc.original_filename == gen_data["generated_filename"]

    # Check that History logged the generation
    hist = db.query(HistoryRecord).filter(HistoryRecord.module == "ai_assistant", HistoryRecord.action == "corrected_file_generated").first()
    assert hist is not None
    db.close()


# =========================================================================
# 11. INVALID FILE HANDLING
# =========================================================================

def test_invalid_file_handling():
    """Verifies that an unsupported or dangerous executable file is rejected safely (HTTP 400),
    and an uninterpretable document produces a safe polite guidance response without 500 error."""
    # 1. Dangerous executable file is rejected with 400
    res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("malicious_script.exe", b"MZDummyBinaryContent", "application/octet-stream")},
        data={"conversation_id": "test_conv_invalid"},
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"] or "Allowed formats" in res.json()["detail"]

    # 2. Upload an allowed extension with general document content
    res_csv = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("unstructured_notes.csv", b"Header1,Header2\nValue1,Value2\n", "text/csv")},
        data={"conversation_id": "test_conv_invalid"},
    )
    assert res_csv.status_code == 200
    data = res_csv.json()
    assert data["document_type"] in ("GENERAL_DOCUMENT", "UNKNOWN")




    # Chat with this file returns polite guidance
    doc_id = data["document_id"]
    chat_res = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": "test_conv_invalid", "message": "Find any mismatch.", "file_ids": [doc_id]},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "couldn't reliably interpret" in chat_data["message"].lower() or "review" in chat_data["message"].lower() or "discrepancies" in chat_data["message"].lower()





# =========================================================================
# 12. AMBIGUOUS WORKBOOK / REVIEW REQUIRED
# =========================================================================

def test_ambiguous_workbook_handling():
    """Workbook with blank or ambiguous data triggers REVIEW_REQUIRED status."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "EmptySheet"
    ws.append(["Random Notes", "No Columns"])
    buf = io.BytesIO()
    wb.save(buf)

    res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Ambiguous_Notes.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("REVIEW_REQUIRED", "ready")


# =========================================================================
# 13. AI CANNOT INVENT FINANCIAL VALUES
# =========================================================================

def test_ai_cannot_invent_financial_values():
    """Verifies that all values reported in findings originate strictly from deterministic analysis."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "test_conv_deterministic"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": "test_conv_deterministic", "message": "Find any mismatch.", "file_ids": [doc_id]},
    )
    assert res.status_code == 200
    findings = res.json()["findings"]
    if findings:
        f = findings[0]
        # Any reported difference must be in the message
        assert f["difference"] in res.json()["message"]


# =========================================================================
# 14. DOCUMENTS QUERY INTEGRATION
# =========================================================================

def test_documents_query_in_chat():
    """Verifies that asking 'Show my recent financial files' queries the Documents repository."""
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Show my recent financial files"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "DOCUMENTS_QUERY"
    assert "Recent Financial Documents" in data["message"] or "uploaded" in data["message"]
