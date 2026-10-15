import hashlib
import io
import json
import uuid
from pathlib import Path

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, get_password_hash
from app.main import app as fastapi_app
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.document import Document
from app.models.history import HistoryRecord
from app.models.reconciliation import CorrectionProposal, ReconciliationSession
from app.models.user import User
from app.modules.ai_assistant.assistant_service import AssistantService
from app.modules.ai_assistant.schemas import ChatRequest
from app.modules.reconciliation.correction_service import CorrectionService
from app.modules.reconciliation.schemas import CorrectionDecisionRequest, CorrectionStatusEnum
from app.services.document_service import DocumentService

client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def remove_default_user_override():
    """Ensures test_backend_hardening tests run against real JWT authentication without bypass."""
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


# =========================================================================
# FIXTURES: DISTINCT USERS & TEST TOKENS
# =========================================================================

@pytest.fixture
def auth_users():
    """Creates two isolated test users in database."""
    db = SessionLocal()
    user_a = db.query(User).filter(User.email == "user_a@litebooks.ai").first()
    if not user_a:
        user_a = User(
            username="user_a",
            email="user_a@litebooks.ai",
            hashed_password=get_password_hash("PasswordA123!"),
            full_name="Accountant Alice",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_a)

    user_b = db.query(User).filter(User.email == "user_b@litebooks.ai").first()
    if not user_b:
        user_b = User(
            username="user_b",
            email="user_b@litebooks.ai",
            hashed_password=get_password_hash("PasswordB123!"),
            full_name="Accountant Bob",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_b)

    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    token_a = create_access_token({"sub": user_a.email, "user_id": user_a.id, "email": user_a.email})
    token_b = create_access_token({"sub": user_b.email, "user_id": user_b.id, "email": user_b.email})

    data = {
        "user_a": user_a,
        "user_b": user_b,
        "token_a": token_a,
        "token_b": token_b,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }
    db.close()
    return data




def create_sample_excel_bytes(cell_val=16321678.06) -> bytes:
    """Helper to generate a clean test Excel workbook."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance Sheet"
    ws.append(["Particulars", "31 March 2026"])
    ws.append(["Trade Payables", cell_val])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# =========================================================================
# 1. AUTHENTICATION TESTS
# =========================================================================

def test_auth_register_user():
    """POST /auth/register creates user, returns clean UserResponse without plaintext password."""
    email = f"new_accountant_{uuid.uuid4().hex[:6]}@litebooks.ai"
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "StrongSecretPass123!",
            "full_name": "New Registered Accountant",
            "organization": "Alpha CPAs LLP",
        },
    )
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == email
    assert data["full_name"] == "New Registered Accountant"
    assert "password" not in data
    assert "hashed_password" not in data

    # Verify password in DB is hashed and verify_password succeeds
    db = SessionLocal()
    user_db = db.query(User).filter(User.email == email).first()
    assert user_db is not None
    assert user_db.hashed_password != "StrongSecretPass123!"
    assert user_db.hashed_password.startswith("$2b$")
    db.close()


def test_auth_login_success(auth_users):
    """POST /auth/login returns JWT access token for valid credentials."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user_a@litebooks.ai", "password": "PasswordA123!"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "user_a@litebooks.ai"


def test_auth_login_invalid_password():
    """POST /auth/login fails with 401 when given an invalid password."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "user_a@litebooks.ai", "password": "WrongPassword!"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]


def test_auth_protected_endpoint_without_token():
    """Protected endpoints strictly require authentication and reject calls without token."""
    # Temporarily remove dependency override to test raw header authentication
    old_override = fastapi_app.dependency_overrides.pop(get_current_user, None)
    try:
        res = client.get("/api/v1/documents")
        assert res.status_code == 401
        assert "Not authenticated" in res.json()["detail"] or "credentials" in res.json()["detail"].lower()
    finally:
        if old_override:
            fastapi_app.dependency_overrides[get_current_user] = old_override


def test_auth_valid_token_me(auth_users):
    """GET /auth/me returns the authenticated user profile with valid Bearer token."""
    old_override = fastapi_app.dependency_overrides.pop(get_current_user, None)
    try:
        res = client.get("/api/v1/auth/me", headers=auth_users["headers_a"])
        assert res.status_code == 200
        assert res.json()["email"] == "user_a@litebooks.ai"
    finally:
        if old_override:
            fastapi_app.dependency_overrides[get_current_user] = old_override


# =========================================================================
# 2. AUTHORIZATION & OWNERSHIP ISOLATION TESTS
# =========================================================================

def test_user_a_cannot_access_or_download_user_b_document(auth_users):
    """User A must NOT be able to access or download documents owned by User B."""
    old_override = fastapi_app.dependency_overrides.pop(get_current_user, None)
    try:
        # User B uploads a document
        wb_bytes = create_sample_excel_bytes()
        res_upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("Confidential_B.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"category": "financial"},
            headers=auth_users["headers_b"],
        )
        assert res_upload.status_code == 201
        doc_b_id = res_upload.json()["id"]

        # User A attempts to download User B's document -> must be rejected (403 Forbidden)
        res_download = client.get(
            f"/api/v1/documents/{doc_b_id}/download",
            headers=auth_users["headers_a"],
        )
        assert res_download.status_code == 403
        assert "permission" in res_download.json()["detail"].lower()

        # User A's document list must not contain User B's document
        res_list = client.get("/api/v1/documents", headers=auth_users["headers_a"])
        assert res_list.status_code == 200
        user_a_doc_ids = [d["id"] for d in res_list.json()]
        assert doc_b_id not in user_a_doc_ids
    finally:
        if old_override:
            fastapi_app.dependency_overrides[get_current_user] = old_override


def test_user_a_cannot_delete_user_b_document(auth_users):
    """User A must NOT be able to delete a document owned by User B."""
    old_override = fastapi_app.dependency_overrides.pop(get_current_user, None)
    try:
        wb_bytes = create_sample_excel_bytes()
        res_upload = client.post(
            "/api/v1/documents/upload",
            files={"file": ("Secret_Financials_B.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            headers=auth_users["headers_b"],
        )
        doc_b_id = res_upload.json()["id"]

        # User A attempts to delete User B's document -> must be 403 Forbidden
        res_del = client.delete(
            f"/api/v1/documents/{doc_b_id}",
            headers=auth_users["headers_a"],
        )
        assert res_del.status_code == 403

        # Document must still exist on disk and in database
        db = SessionLocal()
        doc = db.query(Document).filter(Document.id == doc_b_id).first()
        assert doc is not None
        db.close()
    finally:
        if old_override:
            fastapi_app.dependency_overrides[get_current_user] = old_override


def test_user_a_cannot_access_or_modify_user_b_correction(auth_users):
    """User A must NOT be able to decide or generate corrections owned by User B."""
    old_override = fastapi_app.dependency_overrides.pop(get_current_user, None)
    try:
        db = SessionLocal()
        cid = f"COR-ASST-B-{uuid.uuid4().hex[:6].upper()}"
        prop_b = CorrectionProposal(
            correction_id=cid,
            user_id=auth_users["user_b"].id,
            sheet_name="Balance Sheet",
            cell_address="B2",
            row_reference="2",
            field="Amount",
            original_value="1000.0",
            proposed_value="2000.0",
            difference=1000.0,
            reason_category="AMOUNT_MISMATCH",
            explanation="User B proposal",
            status=CorrectionStatusEnum.PROPOSED.value,
        )
        db.add(prop_b)
        db.commit()
        db.close()

        # User A tries to decide on User B's correction
        res = client.post(
            f"/api/v1/assistant/corrections/{cid}/decision",
            json={"decision": "CONFIRMED", "notes": "Tampering attempt"},
            headers=auth_users["headers_a"],
        )
        assert res.status_code == 403
        assert "access denied" in res.json()["detail"].lower()

        # User A tries to generate corrected file for User B's correction
        res_gen = client.post(
            "/api/v1/assistant/generate-corrected-file",
            json={"correction_id": cid},
            headers=auth_users["headers_a"],
        )
        assert res_gen.status_code == 403
    finally:
        if old_override:
            fastapi_app.dependency_overrides[get_current_user] = old_override


# =========================================================================
# 3. CORRECTION SAFETY & APPROVAL BYPASS ELIMINATION
# =========================================================================

def test_pending_proposal_cannot_generate_corrected_file(auth_users):
    """CRITICAL SAFETY RULE: A proposal in PENDING / PROPOSED status MUST NOT be able to generate a file."""
    db = SessionLocal()
    cid = f"COR-PENDING-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="1000.0",
        proposed_value="1500.0",
        difference=500.0,
        reason_category="AMOUNT_MISMATCH",
        explanation="Pending review proposal",
        status=CorrectionStatusEnum.PROPOSED.value,  # PENDING/PROPOSED
    )
    db.add(p)
    db.commit()
    db.close()

    res = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 409  # Conflict
    assert "must be explicitly approved by the accountant" in res.json()["detail"]


def test_rejected_proposal_cannot_generate_corrected_file(auth_users):
    """A proposal with status REJECTED must return HTTP 409 and never generate a file."""
    db = SessionLocal()
    cid = f"COR-REJ-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="1000.0",
        proposed_value="1500.0",
        difference=500.0,
        reason_category="AMOUNT_MISMATCH",
        explanation="Rejected proposal",
        status=CorrectionStatusEnum.REJECTED.value,
        accountant_decision="rejected",
    )
    db.add(p)
    db.commit()
    db.close()

    res = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 409
    assert "must be explicitly approved" in res.json()["detail"]


def test_no_automatic_confirmation_fallback(auth_users):
    """Verify complete elimination of auto-confirmation: unapproved proposals NEVER auto-confirm."""
    db = SessionLocal()
    cid = f"COR-NOAUTO-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="1000.0",
        proposed_value="1500.0",
        difference=500.0,
        reason_category="AMOUNT_MISMATCH",
        explanation="Testing no-auto-confirm safety",
        status=CorrectionStatusEnum.PROPOSED.value,
    )
    db.add(p)
    db.commit()
    db.close()

    # Attempt generation without accountant decision
    client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid},
        headers=auth_users["headers_a"],
    )

    # Verify status in database did NOT magically become CONFIRMED or APPLIED
    db = SessionLocal()
    reloaded = db.query(CorrectionProposal).filter(CorrectionProposal.correction_id == cid).first()
    assert reloaded.status == CorrectionStatusEnum.PROPOSED.value
    assert reloaded.accountant_decision is None
    db.close()


def test_applied_proposal_cannot_be_applied_twice(auth_users):
    """A proposal already marked APPLIED cannot be applied again (HTTP 409)."""
    db = SessionLocal()
    cid = f"COR-APPLIED-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="1000.0",
        proposed_value="1500.0",
        difference=500.0,
        reason_category="AMOUNT_MISMATCH",
        explanation="Already applied",
        status="APPLIED",
        accountant_decision="approved",
    )
    db.add(p)
    db.commit()
    db.close()

    res = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 409
    assert "already applied" in res.json()["detail"].lower() or "must be explicitly approved" in res.json()["detail"].lower()


def test_changed_workbook_cell_causes_conflict(auth_users):
    """SAFE CORRECTION TARGETING: If the workbook target cell changed after proposal creation, ABORT with 409."""
    # 1. Upload workbook with cell value 16321678.06
    wb_bytes = create_sample_excel_bytes(16321678.06)
    res_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("Integrity_Test.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_users["headers_a"],
    )
    doc_id = res_upload.json()["id"]

    # 2. Proposal was created expecting original_value 9999999.99 (simulating stale or tampered proposal)
    db = SessionLocal()
    cid = f"COR-STALE-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        document_id=doc_id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="9999999.99",  # Does NOT match 16321678.06 in cell B2
        proposed_value="10000000.00",
        difference=1.00,
        reason_category="AMOUNT_MISMATCH",
        explanation="Stale proposal with mismatching original value",
        status=CorrectionStatusEnum.CONFIRMED.value,
        accountant_decision="approved",
    )
    db.add(p)
    db.commit()
    db.close()

    # 3. Attempt generation -> Must conflict with HTTP 409
    res = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 409
    assert "workbook changed after the correction proposal was created" in res.json()["detail"].lower()


def test_original_file_immutability_after_correction(auth_users):
    """ORIGINAL FILE IMMUTABILITY: The original financial file SHA-256 remains 100% untouched."""
    # 1. Upload workbook
    wb_bytes = create_sample_excel_bytes(16321678.06)
    res_upload = client.post(
        "/api/v1/documents/upload",
        files={"file": ("Original_Immutable.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_users["headers_a"],
    )
    doc_id = res_upload.json()["id"]

    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    orig_filename = doc.original_filename
    orig_path = Path(doc.file_path)
    with open(orig_path, "rb") as f:
        hash_before = hashlib.sha256(f.read()).hexdigest()

    # 2. Create and approve valid proposal
    cid = f"COR-IMMUT-{uuid.uuid4().hex[:6].upper()}"
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        document_id=doc_id,
        sheet_name="Balance Sheet",
        cell_address="B2",
        row_reference="2",
        field="Amount",
        original_value="16321678.06",
        proposed_value="16320000.00",
        difference=-1678.06,
        reason_category="AMOUNT_MISMATCH",
        explanation="Valid correction proposal",
        status=CorrectionStatusEnum.CONFIRMED.value,
        accountant_decision="approved",
    )
    db.add(p)
    db.commit()
    db.close()

    # 3. Generate corrected copy
    res_gen = client.post(
        "/api/v1/assistant/generate-corrected-file",
        json={"correction_id": cid, "accountant_name": "Chief Auditor"},
        headers=auth_users["headers_a"],
    )
    assert res_gen.status_code == 200
    gen_data = res_gen.json()
    assert gen_data["success"] is True

    # 4. IMMUTABILITY VERIFICATION: Original file hash MUST be strictly identical
    with open(orig_path, "rb") as f:
        hash_after = hashlib.sha256(f.read()).hexdigest()
    assert hash_before == hash_after

    # Verify that a separate new file was created for the corrected copy
    assert gen_data["generated_filename"] != orig_filename
    assert "_Corrected_" in gen_data["generated_filename"]



# =========================================================================
# 4. FILE UPLOAD SECURITY TESTS
# =========================================================================

@pytest.mark.parametrize("dangerous_file,mime", [
    ("script.sh", "application/x-sh"),
    ("malicious.exe", "application/x-msdownload"),
    ("payload.bat", "application/x-bat"),
    ("exploit.js", "application/javascript"),
    ("backdoor.py", "text/x-python"),
    ("installer.msi", "application/x-msi"),
])
def test_unsupported_and_dangerous_extensions_rejected(auth_users, dangerous_file, mime):
    """File security must reject all executable, script, and non-whitelisted formats with HTTP 400."""
    res = client.post(
        "/api/v1/documents/upload",
        files={"file": (dangerous_file, b"echo 'malicious'", mime)},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


def test_path_traversal_filename_sanitized(auth_users):
    """Path traversal sequences (../../etc/passwd) must be sanitized and contained safely."""
    wb_bytes = create_sample_excel_bytes()
    res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("../../../../etc/shadow.xlsx", wb_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 201
    doc_id = res.json()["id"]

    db = SessionLocal()
    doc = db.query(Document).filter(Document.id == doc_id).first()
    # Check that file_path does not contain any traversal characters and resides in upload dir
    doc_path = Path(doc.file_path).resolve()
    upload_dir = settings.uploads_dir.resolve()
    assert upload_dir in doc_path.parents or doc_path.parent == upload_dir
    assert ".." not in doc.stored_filename
    db.close()


def test_oversized_file_rejected_cleanly(auth_users, monkeypatch):
    """Upload exceeding MAX_UPLOAD_SIZE_MB must be rejected with HTTP 413 without leaking memory."""
    # Temporarily set max upload size to 1 MB for deterministic test
    monkeypatch.setattr("app.services.document_service.MAX_FILE_BYTES", 1024 * 1024)
    huge_bytes = b"0" * (1024 * 1024 + 1024)  # 1 MB + 1 KB

    res = client.post(
        "/api/v1/documents/upload",
        files={"file": ("huge_statement.xlsx", huge_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_users["headers_a"],
    )
    assert res.status_code == 413
    assert "exceeds the maximum limit" in res.json()["detail"].lower()


# =========================================================================
# 5. DATABASE PERSISTENCE TESTS
# =========================================================================

def test_assistant_conversation_and_messages_persist_in_db(auth_users):
    """Assistant state is durable in database and survives server restart/reload."""
    conv_id = f"test_persist_conv_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()

    # User starts a chat
    AssistantService.get_or_create_conversation(db, conv_id, user_id=auth_users["user_a"].id, title="Audit Review")
    msg = AssistantMessage(
        id=f"msg_{uuid.uuid4().hex[:8]}",
        conversation_id=conv_id,
        role="user",
        content="What are the key tax deadlines for LLP?",
    )
    db.add(msg)
    db.commit()
    db.close()

    # Simulate backend restart: open fresh DB session
    fresh_db = SessionLocal()
    conv = fresh_db.query(AssistantConversation).filter(AssistantConversation.id == conv_id).first()
    assert conv is not None
    assert conv.user_id == auth_users["user_a"].id

    messages = fresh_db.query(AssistantMessage).filter(AssistantMessage.conversation_id == conv_id).all()
    assert len(messages) == 1
    assert messages[0].content == "What are the key tax deadlines for LLP?"
    fresh_db.close()


def test_correction_proposal_persists_in_db(auth_users):
    """Correction proposals are durable in database and survive server restart."""
    cid = f"COR-DURABLE-{uuid.uuid4().hex[:6].upper()}"
    db = SessionLocal()
    p = CorrectionProposal(
        correction_id=cid,
        user_id=auth_users["user_a"].id,
        sheet_name="Balance Sheet",
        cell_address="C14",
        row_reference="14",
        field="Amount",
        original_value="50000.0",
        proposed_value="55000.0",
        difference=5000.0,
        reason_category="MISSING_ENTRY",
        explanation="Durable proposal test",
        status=CorrectionStatusEnum.PROPOSED.value,
    )
    db.add(p)
    db.commit()
    db.close()

    # Reload from fresh DB session
    fresh_db = SessionLocal()
    reloaded = fresh_db.query(CorrectionProposal).filter(CorrectionProposal.correction_id == cid).first()
    assert reloaded is not None
    assert reloaded.cell_address == "C14"
    assert float(reloaded.original_value) == 50000.0
    assert float(reloaded.proposed_value) == 55000.0
    fresh_db.close()
