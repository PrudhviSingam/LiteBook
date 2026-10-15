import io
import json
from pathlib import Path

import openpyxl
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, SessionLocal, engine
from app.main import app as fastapi_app
from app.models.document import Document
from app.models.history import HistoryRecord
from app.models.reconciliation import CorrectionProposal, ReconciliationSession
from app.modules.reconciliation.correction import CorrectionProposalFactory
from app.modules.reconciliation.correction_service import CorrectionService
from app.modules.reconciliation.explanation import DiscrepancyExplanationEngine
from app.modules.reconciliation.schemas import CorrectionDecisionRequest
from app.modules.reconciliation.workbook_inspector import (
    WorkbookInspector,
    format_indian_currency,
    parse_indian_currency,
)

Base.metadata.create_all(bind=engine)
client = TestClient(fastapi_app)


# =========================================================================
# TEST FIXTURES: REAL-WORLD WORKBOOK (ZION LIFTS LLP SIMULATION)
# =========================================================================

def create_zion_lifts_workbook_bytes() -> bytes:
    """Creates a realistic Indian accounting workbook for 'ZION LIFTS LLP'

    featuring:
    - Company title, LLPIN, Registered Address, Blank rows
    - Multiple sheets: 'Balance Sheet', 'Profit and Loss', 'Notes', 'Bank Statement'
    - Merged title cells
    - Financial year period columns ('31 March 2026', '31 March 2025')
    - Indian numbering formatting (e.g. ₹1,63,21,678.06)
    - Subtotals and accounting categories (Current Liabilities, Trade Payables)
    """
    wb = openpyxl.Workbook()

    # Sheet 1: Balance Sheet
    ws_bs = wb.active
    ws_bs.title = "Balance Sheet"

    # Title block
    ws_bs.append(["ZION LIFTS LLP", None, None, None])
    ws_bs.append(["LLPIN: AAB-8910 | Registered Office: Andheri East, Mumbai", None, None, None])
    ws_bs.append(["STATEMENT OF ASSETS AND LIABILITIES AS AT 31 MARCH 2026", None, None, None])
    ws_bs.append([])  # Blank row
    ws_bs.append(["Particulars", "Note No.", "31 March 2026", "31 March 2025"])

    # Rows
    ws_bs.append(["I. EQUITY AND LIABILITIES", None, None, None])
    ws_bs.append(["Partner Capital Accounts", "1", 5000000.0, 5000000.0])
    ws_bs.append(["Reserves and Surplus", "2", 3420000.0, 2100000.0])
    ws_bs.append(["Current Liabilities", None, None, None])
    ws_bs.append(["Trade Payables", "3", 16321678.06, 14210000.00])
    ws_bs.append(["Short Term Provisions", "4", 450000.0, 380000.0])
    ws_bs.append(["TOTAL LIABILITIES", None, 25191678.06, 21690000.0])
    ws_bs.append([])
    ws_bs.append(["II. ASSETS", None, None, None])
    ws_bs.append(["Tangible Fixed Assets", "5", 8500000.0, 9200000.0])
    ws_bs.append(["Inventories", "6", 6200000.0, 5100000.0])
    ws_bs.append(["Trade Receivables", "7", 7800000.0, 5600000.0])
    ws_bs.append(["Cash and Bank Balances", "8", 2691678.06, 1790000.0])
    ws_bs.append(["TOTAL ASSETS", None, 25191678.06, 21690000.0])

    # Sheet 2: Profit & Loss
    ws_pl = wb.create_sheet(title="Profit & Loss")
    ws_pl.append(["ZION LIFTS LLP - STATEMENT OF PROFIT AND LOSS", None, None])
    ws_pl.append(["For the year ended 31 March 2026", None, None])
    ws_pl.append([])
    ws_pl.append(["Particulars", "Note No.", "FY 2025-26", "FY 2024-25"])
    ws_pl.append(["Revenue from Operations", "9", 48200000.0, 39500000.0])
    ws_pl.append(["Other Income", "10", 125000.0, 85000.0])
    ws_pl.append(["Total Expenses", "11", 42100000.0, 35200000.0])
    ws_pl.append(["Net Profit Before Tax", None, 6225000.0, 4385000.0])

    # Sheet 3: Notes
    ws_notes = wb.create_sheet(title="Notes")
    ws_notes.append(["Note 3: Trade Payables Breakdown", None])
    ws_notes.append(["Micro & Small Enterprises", 2150000.0])
    ws_notes.append(["Other Vendor Payables", 14171678.06])
    ws_notes.append(["Total Trade Payables", 16321678.06])

    # Sheet 4: Bank Statement
    ws_bank = wb.create_sheet(title="Bank Statement")
    ws_bank.append(["HDFC Bank Current A/c - Statement", None, None, None, None])
    ws_bank.append(["Opening Balance: ₹73,97,632.43", None, None, None, None])
    ws_bank.append(["Date", "Description", "Reference", "Withdrawal", "Deposit"])
    ws_bank.append(["2026-03-15", "Vendor Payment Apex Elevators", "TXN9901", 1678.00, 0.0])
    ws_bank.append(["2026-03-20", "Client Retainer Inflow", "TXN9902", 0.0, 150000.0])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# =========================================================================
# PHASE 1 & 2: WORKBOOK INSPECTOR & CLASSIFICATION TESTS
# =========================================================================

def test_indian_currency_formatting_and_parsing():
    """Verifies Indian numbering parsing and formatting (lakhs, crores)."""
    assert parse_indian_currency("₹1,63,21,678.06") == 16321678.06
    assert parse_indian_currency("1,63,20,000.06") == 16320000.06
    assert parse_indian_currency("(1,678.00)") == -1678.00
    assert parse_indian_currency("1,678.00 Dr") == -1678.00
    assert parse_indian_currency("5,000.00 Cr") == 5000.00
    assert parse_indian_currency(16321678.06) == 16321678.06
    assert parse_indian_currency(None) is None

    assert format_indian_currency(16321678.06) == "₹1,63,21,678.06"
    assert format_indian_currency(-1678.00) == "-₹1,678.00"
    assert format_indian_currency(0.0) == "₹0.00"


def test_inspect_zion_lifts_complex_workbook():
    """Tests multi-sheet workbook inspection, period detection, and classification."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    inspection = WorkbookInspector.inspect(wb_bytes, "Zion_Lifts_Financials.xlsx")

    assert inspection.total_sheets == 4
    sheet_names = [s.sheet_name for s in inspection.sheets]
    assert "Balance Sheet" in sheet_names
    assert "Profit & Loss" in sheet_names
    assert "Notes" in sheet_names
    assert "Bank Statement" in sheet_names

    # Check Balance Sheet detection
    bs_info = next(s for s in inspection.sheets if s.sheet_name == "Balance Sheet")
    assert bs_info.classification == "BALANCE_SHEET"
    assert bs_info.header_row_index == 4  # Skipped title rows
    assert any("31 March 2026" in p for p in bs_info.period_columns)

    # Check P&L detection
    pl_info = next(s for s in inspection.sheets if s.sheet_name == "Profit & Loss")
    assert pl_info.classification == "PROFIT_LOSS"

    # Check Bank Statement detection
    bank_info = next(s for s in inspection.sheets if s.sheet_name == "Bank Statement")
    assert bank_info.classification == "BANK_STATEMENT"

    # Overall document type
    assert inspection.document_type in ("FINANCIAL_STATEMENT", "BALANCE_SHEET")
    assert inspection.status == "ready"


def test_category_mismatch_warning():
    """When a Balance Sheet is uploaded under 'ledger' or 'bank_statement',

    system must set status = REVIEW_REQUIRED with an informative message.
    """
    wb_bytes = create_zion_lifts_workbook_bytes()

    # Uploaded under bank_statement category
    inspection_bank = WorkbookInspector.inspect(wb_bytes, "Zion_Financials.xlsx", upload_category="bank_statement")
    assert inspection_bank.status == "REVIEW_REQUIRED"
    assert "Balance Sheet" in inspection_bank.message or "Financial Statement" in inspection_bank.message

    # Uploaded under ledger category
    inspection_ledger = WorkbookInspector.inspect(wb_bytes, "Zion_Financials.xlsx", upload_category="ledger")
    assert inspection_ledger.status == "REVIEW_REQUIRED"
    assert "Balance Sheet" in inspection_ledger.message or "Financial Statement" in inspection_ledger.message


# =========================================================================
# PHASE 3, 4 & 11: DISCREPANCY EXPLANATION TESTS
# =========================================================================

import asyncio

def test_amount_mismatch_explanation():
    """Tests 8-point explanation for Trade Payables variance (ZION LIFTS example)."""
    discrepancy = {
        "sheet_name": "Balance Sheet",
        "section": "Current Liabilities",
        "account": "Trade Payables",
        "field": "31 March 2026",
        "original_value": 16321678.06,
        "comparison_value": 16320000.06,
        "difference": -1678.00,
        "reason_category": "AMOUNT_MISMATCH",
        "row_reference": 24,
    }
    comparison_records = [
        {"account": "Trade Payables", "source": "Ledger", "amount": 16320000.06},
    ]

    resp = asyncio.run(DiscrepancyExplanationEngine.explain(discrepancy, comparison_records))

    # 1. WHAT is different?
    assert "Trade Payables" in resp.what
    assert "1,678.00" in resp.what

    # 2. WHERE is it different?
    assert resp.where["sheet_name"] == "Balance Sheet"
    assert resp.where["section"] == "Current Liabilities"
    assert resp.where["account"] == "Trade Payables"

    # 3. Original and Expected
    assert resp.original_value == 16321678.06
    assert resp.expected_value == 16320000.06

    # 4. WHY might difference exist? (cautious reasons)
    assert len(resp.possible_reasons) > 0
    assert any("omitted" in r.lower() or "error" in r.lower() for r in resp.possible_reasons)

    # 5. Proposed correction
    assert resp.proposed_correction is not None
    assert resp.proposed_correction["proposed_value"] == 16320000.06

    # 6. Evidence
    assert len(resp.evidence) >= 3

    # 7. Recommended verification
    assert len(resp.recommended_verification) > 0

    # 8. Confidence
    assert resp.confidence == "HIGH"

    # Audit safety: No dogmatic claims of certainty
    assert "definitely the error" not in resp.summary.lower()
    assert "please verify" in resp.summary.lower() or "possible" in resp.summary.lower() or "detected" in resp.summary.lower()


def test_missing_in_ledger_explanation():
    """Tests explanation for unrecorded bank transaction."""
    discrepancy = {
        "account": "Quarterly Bank Maintenance",
        "field": "Amount",
        "original_value": 1750.00,
        "comparison_value": 0.0,
        "reason_category": "MISSING_IN_LEDGER",
    }
    resp = asyncio.run(DiscrepancyExplanationEngine.explain(discrepancy))
    assert resp.reason_category == "MISSING_IN_LEDGER"
    assert any("mandate" in r.lower() or "charges" in r.lower() or "inflow" in r.lower() for r in resp.possible_reasons)


def test_missing_in_bank_explanation():
    """Tests explanation for unpresented cheque or outstanding entry."""
    discrepancy = {
        "account": "Vendor Cheque Issued",
        "field": "Amount",
        "original_value": 45000.00,
        "comparison_value": 0.0,
        "reason_category": "MISSING_IN_BANK",
    }
    resp = asyncio.run(DiscrepancyExplanationEngine.explain(discrepancy))
    assert resp.reason_category == "MISSING_IN_BANK"
    assert any("unpresented" in r.lower() or "transit" in r.lower() or "cancelled" in r.lower() for r in resp.possible_reasons)


def test_date_mismatch_explanation():
    """Tests explanation for clearance timing difference."""
    discrepancy = {
        "account": "Office Rent NEFT",
        "field": "Date",
        "original_value": 45000.00,
        "comparison_value": 45000.00,
        "difference": 0.0,
        "reason_category": "DATE_MISMATCH",
    }
    resp = asyncio.run(DiscrepancyExplanationEngine.explain(discrepancy))
    assert any("transit" in r.lower() or "settlement" in r.lower() or "cycle" in r.lower() for r in resp.possible_reasons)


def test_duplicate_detection_explanation():
    """Tests explanation for duplicate payments."""
    discrepancy = {
        "account": "SaaS Subscription",
        "field": "Amount",
        "original_value": 4999.00,
        "comparison_value": 4999.00,
        "reason_category": "POSSIBLE_DUPLICATE",
    }
    resp = asyncio.run(DiscrepancyExplanationEngine.explain(discrepancy))
    assert any("double" in r.lower() or "recurring" in r.lower() for r in resp.possible_reasons)



# =========================================================================
# PHASE 5, 6, 7, 8, 9 & 10: CORRECTION LIFECYCLE & NON-DESTRUCTIVE EXCEL COPY
# =========================================================================

def test_correction_lifecycle_and_non_destructive_excel_copy():
    """Tests end-to-end:

    1. Seed session with discrepancies
    2. Auto-create correction proposal (PROPOSED)
    3. Accountant confirms proposal (CONFIRMED)
    4. Accountant rejects a proposal (REJECTED)
    5. Generate corrected Excel copy:
       - Original file remains completely unchanged
       - Timestamped copy created
       - Target cell updated
       - 'AI Correction Log' worksheet created with full audit columns
    6. Appears in Documents table
    7. History entries created
    """
    db = SessionLocal()

    import uuid
    # 1. Create a dummy original workbook
    orig_wb_bytes = create_zion_lifts_workbook_bytes()
    unique_name = f"zion_orig_{uuid.uuid4().hex[:8]}.xlsx"
    dest = Path("storage/uploads") / unique_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(orig_wb_bytes)

    orig_doc = Document(
        original_filename="Zion_Lifts_Financials.xlsx",
        stored_filename=unique_name,
        file_path=str(dest),
        file_size=len(orig_wb_bytes),
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        category="financial",
        status="ready",
    )
    db.add(orig_doc)
    db.commit()

    orig_mtime = dest.stat().st_mtime
    orig_size = dest.stat().st_size

    # 2. Create Reconciliation Session
    session_details = {
        "summary": {"total_bank_transactions": 2, "total_ledger_transactions": 2, "matched_count": 1, "unmatched_count": 1},
        "transactions": [
            {
                "status": "AMOUNT_MISMATCH",
                "bank_amount": 16320000.06,
                "ledger_amount": 16321678.06,
                "difference": -1678.00,
                "description": "Trade Payables Balance Adjustment",
                "reference": "TP-ADJ-001",
            },
            {
                "status": "MISSING_IN_LEDGER",
                "bank_amount": 1750.00,
                "ledger_amount": 0.0,
                "difference": 1750.00,
                "description": "Quarterly Bank SMS Fee",
                "reference": "BANK-CHG-01",
            },
        ],
    }
    session = ReconciliationSession(
        bank_statement_name="HDFC_Statement.xlsx",
        ledger_file_name="Zion_Lifts_Financials.xlsx",
        ledger_document_id=orig_doc.id,
        status="completed",
        details_json=json.dumps(session_details),
    )
    db.add(session)
    db.commit()

    # 3. Create Correction Proposals
    proposals = CorrectionService.list_or_create_proposals_for_session(db, session.id)
    assert len(proposals) == 2
    assert proposals[0].status == "PROPOSED"
    assert proposals[0].difference == -1678.00

    # 4. Confirm First Proposal
    prop_1_id = proposals[0].correction_id
    updated_1 = CorrectionService.update_proposal_decision(
        db=db,
        correction_id=prop_1_id,
        decision_req=CorrectionDecisionRequest(decision="CONFIRMED", notes="Verified against supplier ledger"),
    )
    assert updated_1.status == "CONFIRMED"
    assert updated_1.accountant_decision == "approved"

    # 5. Reject Second Proposal
    prop_2_id = proposals[1].correction_id
    updated_2 = CorrectionService.update_proposal_decision(
        db=db,
        correction_id=prop_2_id,
        decision_req=CorrectionDecisionRequest(decision="REJECTED", notes="Expense will be booked next quarter"),
    )
    assert updated_2.status == "REJECTED"
    assert updated_2.accountant_decision == "rejected"

    # 6. Generate Corrected Workbook Copy
    gen_resp = CorrectionService.generate_corrected_workbook(
        db=db,
        session_id=session.id,
        accountant_name="Chief Financial Auditor",
    )
    assert gen_resp.success is True
    assert "Zion_Lifts_Financials_Corrected_" in gen_resp.generated_filename
    assert gen_resp.applied_corrections_count == 1
    assert gen_resp.corrections_sheet_name == "AI Correction Log"

    # 7. SAFETY VERIFICATION: Original file is 100% UNCHANGED
    assert dest.stat().st_size == orig_size
    assert dest.stat().st_mtime == orig_mtime

    # 8. VERIFY GENERATED FILE & AI CORRECTION LOG SHEET
    gen_doc = db.query(Document).filter(Document.id == gen_resp.document_id).first()
    assert gen_doc is not None
    assert Path(gen_doc.file_path).exists()

    gen_wb = openpyxl.load_workbook(gen_doc.file_path)
    assert "AI Correction Log" in gen_wb.sheetnames

    # Check Log sheet rows
    ws_log = gen_wb["AI Correction Log"]
    assert ws_log.cell(row=1, column=1).value == "Correction ID"
    assert ws_log.cell(row=1, column=14).value == "Status"
    assert ws_log.cell(row=2, column=1).value == prop_1_id
    assert ws_log.cell(row=2, column=9).value == "AMOUNT_MISMATCH"
    assert ws_log.cell(row=2, column=13).value == "Chief Financial Auditor"
    assert ws_log.cell(row=2, column=14).value == "GENERATED"

    # 9. VERIFY HISTORY / AUDIT TRAIL
    history_records = db.query(HistoryRecord).filter(HistoryRecord.module == "reconciliation").all()
    actions = [h.action for h in history_records]
    assert "correction_proposed" in actions
    assert "correction_approved" in actions
    assert "correction_rejected" in actions
    assert "corrected_file_generated" in actions

    db.close()


# =========================================================================
# API ENDPOINT INTEGRATION TESTS
# =========================================================================

def test_api_inspect_workbook_endpoint():
    """Tests POST /api/v1/reconciliation/inspect-workbook."""
    wb_bytes = create_zion_lifts_workbook_bytes()
    res = client.post(
        "/api/v1/reconciliation/inspect-workbook",
        files={"file": ("Zion_Financials.xlsx", io.BytesIO(wb_bytes), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_sheets"] == 4
    assert data["status"] == "ready"
    assert data["document_type"] in ("FINANCIAL_STATEMENT", "BALANCE_SHEET")


def test_api_explain_discrepancy_endpoint():
    """Tests POST /api/v1/reconciliation/explain-discrepancy."""
    payload = {
        "discrepancy_data": {
            "account": "Trade Payables",
            "original_value": 16321678.06,
            "comparison_value": 16320000.06,
            "reason_category": "AMOUNT_MISMATCH",
        }
    }
    res = client.post("/api/v1/reconciliation/explain-discrepancy", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "Trade Payables" in data["what"]
    assert data["difference"] == 1678.00
    assert len(data["possible_reasons"]) > 0
    assert len(data["recommended_verification"]) > 0


def test_api_document_download_endpoint():
    """Tests GET /api/v1/documents/{id}/download."""
    import uuid
    db = SessionLocal()
    # Create test document
    unique_stored = f"test_download_{uuid.uuid4().hex[:8]}.xlsx"
    p = Path("storage/uploads") / unique_stored
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "wb") as f:
        f.write(b"test file content")

    doc = Document(
        original_filename="download_sample.xlsx",
        stored_filename=unique_stored,
        file_path=str(p),
        file_size=17,
        mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        category="financial",
        status="ready",
    )
    db.add(doc)
    db.commit()
    doc_id = doc.id
    db.close()

    res = client.get(f"/api/v1/documents/{doc_id}/download")
    assert res.status_code == 200
    assert res.content == b"test file content"
    assert "attachment" in res.headers.get("content-disposition", "")


def test_ai_does_not_invent_values():
    """Safety Test (Phase 13 #14 & Phase 12):

    All factual amounts in explanations and proposals must originate from
    the actual application data and never be fabricated.
    """
    actual_orig = 16321678.06
    actual_comp = 16320000.06
    actual_diff = round(actual_orig - actual_comp, 2)

    resp = asyncio.run(
        DiscrepancyExplanationEngine.explain({
            "account": "Trade Payables",
            "field": "Amount",
            "original_value": actual_orig,
            "comparison_value": actual_comp,
            "difference": actual_diff,
            "reason_category": "AMOUNT_MISMATCH",
        })
    )

    assert resp.original_value == actual_orig
    assert resp.expected_value == actual_comp
    assert resp.difference == actual_diff
    assert resp.proposed_correction["original_value"] == actual_orig
    assert resp.proposed_correction["proposed_value"] == actual_comp
    assert "1,678.00" in resp.what
    assert "1,63,21,678.06" in str(resp.evidence) or "1,63,20,000.06" in str(resp.evidence)


def test_low_confidence_discrepancy_requires_review():
    """Safety Test (Phase 13 #15 & Phase 1):

    When workbook inspection has low confidence or conflicting structure,
    it must trigger REVIEW_REQUIRED and never silently guess.
    """
    # Workbook with unstructured / unrecognizable content
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Unstructured Data"
    ws.append(["Random Note 1", "Random Note 2"])
    ws.append(["Some internal memo text without headers", "Another line"])
    buf = io.BytesIO()
    wb.save(buf)

    inspection = WorkbookInspector.inspect(buf.getvalue(), "Uncertain_File.xlsx", upload_category="bank_statement")
    assert inspection.status == "REVIEW_REQUIRED"
    assert inspection.confidence in ("LOW", "MEDIUM")
    assert inspection.document_type == "UNKNOWN" or "REVIEW_REQUIRED" in inspection.status

