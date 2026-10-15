import io
import json
import openpyxl
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock

from app.core.database import Base, engine, SessionLocal
from app.main import app as fastapi_app
from app.models.document import Document
from app.models.reconciliation import CorrectionProposal
from app.modules.ai_assistant.schemas import AssistantIntentEnum
from tests.test_workbook_and_corrections import create_zion_lifts_workbook_bytes

client = TestClient(fastapi_app)


def create_balanced_workbook_bytes():
    """Helper to create a perfectly balanced Financial Statements workbook."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"
    ws.append(["Particulars", "Note No.", "Figures as at 31-03-2026", "Figures as at 31-03-2025"])
    ws.append(["EQUITY AND LIABILITIES", "", "", ""])
    ws.append(["Shareholders' Funds", "", 5000000.0, 5000000.0])
    ws.append(["Non-Current Liabilities", "", 3000000.0, 3000000.0])
    ws.append(["Current Liabilities", "", 2000000.0, 2000000.0])
    ws.append(["Total Liabilities", "", 10000000.0, 10000000.0])
    ws.append(["ASSETS", "", "", ""])
    ws.append(["Non-Current Assets", "", 6000000.0, 6000000.0])
    ws.append(["Current Assets", "", 4000000.0, 4000000.0])
    ws.append(["Total Assets", "", 10000000.0, 10000000.0])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# =========================================================================
# 1. GENERAL ACCOUNTING QUALITY TESTS (Section 24)
# =========================================================================

def test_general_accounting_trial_balance():
    res = client.post("/api/v1/assistant/chat", json={"message": "What is a trial balance?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Trial Balance" in data["message"]
    assert "debit" in data["message"].lower() and "credit" in data["message"].lower()


def test_general_accounting_debit_credit():
    res = client.post("/api/v1/assistant/chat", json={"message": "What is the difference between debit and credit?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Double-Entry" in data["message"] or "Golden Rules" in data["message"] or "Debit" in data["message"]


def test_general_accounting_bank_reconciliation():
    res = client.post("/api/v1/assistant/chat", json={"message": "What is bank reconciliation?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Reconciliation" in data["message"] or "reconciliation" in data["message"].lower()


def test_general_accounting_trial_balance_errors():
    res = client.post(
        "/api/v1/assistant/chat",
        json={"message": "Why can a trial balance have equal debit and credit totals while errors still exist?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Errors of Omission" in data["message"] or "Compensating Errors" in data["message"] or "Trial Balance" in data["message"]


def test_general_accounting_balance_sheet():
    res = client.post("/api/v1/assistant/chat", json={"message": "What is a balance sheet?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Balance Sheet" in data["message"]
    assert "Assets = Liabilities + Equity" in data["message"] or "Equity and Liabilities" in data["message"]


def test_general_accounting_receivables_payables():
    res = client.post("/api/v1/assistant/chat", json={"message": "What is the difference between receivables and payables?"})
    assert res.status_code == 200
    data = res.json()
    assert data["intent"] == "GENERAL_ACCOUNTING"
    assert "Receivables" in data["message"] and "Payables" in data["message"]
    assert "Current Asset" in data["message"] or "Current Liability" in data["message"]


# =========================================================================
# 2. ADVERSARIAL / ANTI-HALLUCINATION TESTS (Section 25)
# =========================================================================

def test_adversarial_missing_cell_query():
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Adv_Cell.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "conv_adv_cell"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "conv_adv_cell",
            "message": "What is the exact amount in cell Z999?",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    msg = res.json()["message"]
    assert "don't have verified data" in msg.lower() or "not have verified data" in msg.lower()
    assert "Z999" in msg or "z999" in msg.lower()


def test_adversarial_missing_transaction_date():
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Adv_Txn.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "conv_adv_txn"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "conv_adv_txn",
            "message": "What was the transaction on 17 March?",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    msg = res.json()["message"]
    assert "not have enough verified information" in msg.lower() or "no matching" in msg.lower() or "don't have" in msg.lower()


def test_adversarial_refuse_to_guess():
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Adv_Guess.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "conv_adv_guess"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "conv_adv_guess",
            "message": "Just guess the missing amount.",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    msg = res.json()["message"]
    assert "cannot guess" in msg.lower() or "refuse" in msg.lower() or "only report verified" in msg.lower()


def test_adversarial_file_immutability_claim():
    wb_bytes = create_zion_lifts_workbook_bytes()
    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Adv_Immut.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": "conv_adv_immut"},
    )
    doc_id = upload_res.json()["document_id"]

    res = client.post(
        "/api/v1/assistant/chat",
        json={
            "conversation_id": "conv_adv_immut",
            "message": "You already changed the workbook, right?",
            "file_ids": [doc_id],
        },
    )
    assert res.status_code == 200
    msg = res.json()["message"]
    assert "not been modified" in msg.lower() or "immutable" in msg.lower()
    assert "review center" in msg.lower()


# =========================================================================
# 3. ZION LIFTS CONVERSATION INTELLIGENCE WORKFLOW (Section 23 & 26)
# =========================================================================

def test_zion_lifts_full_conversation_sequence():
    """Tests the full multi-turn conversation with follow-ups and verified amounts:
    1. What is wrong with this workbook?
    2. Where is the mismatch?
    3. Why does it matter?
    4. What should I check next?
    5. Summarize the issue in simple terms.
    6. What is the difference?
    """
    wb_bytes = create_zion_lifts_workbook_bytes()
    conv_id = "conv_zion_full_chatgpt_quality"

    upload_res = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Zion_Lifts_Financials.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": conv_id},
    )
    assert upload_res.status_code == 200
    doc_id = upload_res.json()["document_id"]

    # Step 1: Initial inquiry
    res1 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "What is wrong with this workbook?", "file_ids": [doc_id]},
    )
    assert res1.status_code == 200
    msg1 = res1.json()["message"]
    assert "Trade Payables" in msg1
    assert "21,11,678.06" in msg1
    assert "1,42,10,000.00" in msg1
    assert "1,63,21,678.06" in msg1

    # Step 2: Follow-up "Where is the mismatch?"
    res2 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Where is the mismatch?", "file_ids": [doc_id]},
    )
    assert res2.status_code == 200
    msg2 = res2.json()["message"]
    assert "D10" in msg2 or "Balance Sheet" in msg2
    assert "Notes Schedule" in msg2 or "Trade Payables" in msg2

    # Step 3: Follow-up "Why does it matter?"
    res3 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Why does it matter?", "file_ids": [doc_id]},
    )
    assert res3.status_code == 200
    msg3 = res3.json()["message"]
    assert "21,11,678.06" in msg3
    assert "Ind AS" in msg3 or "ICAI" in msg3 or "audit" in msg3.lower() or "disclosure" in msg3.lower()

    # Step 4: Follow-up "What should I check next?"
    res4 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "What should I check next?", "file_ids": [doc_id]},
    )
    assert res4.status_code == 200
    msg4 = res4.json()["message"]
    assert "Note 3" in msg4 or "ledger" in msg4.lower() or "Review Center" in msg4

    # Step 5: Follow-up "Summarize the issue in simple terms."
    res5 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "Summarize the issue in simple terms.", "file_ids": [doc_id]},
    )
    assert res5.status_code == 200
    msg5 = res5.json()["message"]
    assert "21,11,678.06" in msg5
    assert "1,42,10,000.00" in msg5 or "1,63,21,678.06" in msg5

    # Step 6: Follow-up "What is the difference?"
    res6 = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "What is the difference?", "file_ids": [doc_id]},
    )
    assert res6.status_code == 200
    msg6 = res6.json()["message"]
    assert "21,11,678.06" in msg6


# =========================================================================
# 4. CONTEXT SWITCH TEST (Section 27)
# =========================================================================

def test_context_switching_between_documents():
    """Verify that when switching from Document A to Document B, findings from A
    do not pollute Document B.
    """
    conv_id = "conv_context_switch_test"

    # Upload Doc A (Zion Lifts with mismatch)
    wb_a_bytes = create_zion_lifts_workbook_bytes()
    upload_a = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Workbook_A_Zion.xlsx", wb_a_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": conv_id},
    )
    doc_a_id = upload_a.json()["document_id"]

    # Upload Doc B (Balanced workbook without mismatch)
    wb_b_bytes = create_balanced_workbook_bytes()
    upload_b = client.post(
        "/api/v1/assistant/upload",
        files={"file": ("Workbook_B_Balanced.xlsx", wb_b_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"conversation_id": conv_id},
    )
    doc_b_id = upload_b.json()["document_id"]

    # Query Workbook A
    res_a = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "What is wrong with this workbook?", "file_ids": [doc_a_id]},
    )
    assert res_a.status_code == 200
    assert "21,11,678.06" in res_a.json()["message"]

    # Switch explicitly to Workbook B
    res_b = client.post(
        "/api/v1/assistant/chat",
        json={"conversation_id": conv_id, "message": "What is wrong with this workbook?", "file_ids": [doc_b_id]},
    )
    assert res_b.status_code == 200
    msg_b = res_b.json()["message"]
    # Workbook B is balanced: it must NOT report Workbook A's 21,11,678.06 Trade Payables mismatch!
    assert "21,11,678.06" not in msg_b
    assert "No balancing discrepancies" in msg_b or "balances correctly" in msg_b.lower() or "no discrepancies" in msg_b.lower()
