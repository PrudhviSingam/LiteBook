import hashlib
import io
import json
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, get_password_hash
from app.main import app as fastapi_app
from app.models.assistant import AssistantConversation, AssistantFileContext
from app.models.document import Document
from app.models.history import HistoryRecord
from app.models.reconciliation import CorrectionProposal, ReconciliationSession
from app.models.user import User
from app.modules.gst.models import GSTRegistration
from app.services.document_service import DocumentService

Base.metadata.create_all(bind=engine)
client = TestClient(fastapi_app)


@pytest.fixture(autouse=True)
def remove_default_user_override():
    """Ensures test runs against real JWT tokens and current_user resolution."""
    fastapi_app.dependency_overrides.pop(get_current_user, None)
    yield
    fastapi_app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def test_users():
    """Sets up two distinct users with their authentication tokens."""
    db = SessionLocal()
    user_a = db.query(User).filter(User.email == "reset_user_a@litebooks.ai").first()
    if not user_a:
        user_a = User(
            username="reset_user_a",
            email="reset_user_a@litebooks.ai",
            hashed_password=get_password_hash("PasswordA123!"),
            full_name="Reset User A",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_a)

    user_b = db.query(User).filter(User.email == "reset_user_b@litebooks.ai").first()
    if not user_b:
        user_b = User(
            username="reset_user_b",
            email="reset_user_b@litebooks.ai",
            hashed_password=get_password_hash("PasswordB123!"),
            full_name="Reset User B",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user_b)

    db.commit()
    db.refresh(user_a)
    db.refresh(user_b)

    token_a = create_access_token({"sub": user_a.email})
    token_b = create_access_token({"sub": user_b.email})
    users_data = {
        "user_a": user_a,
        "token_a": token_a,
        "headers_a": {"Authorization": f"Bearer {token_a}"},
        "user_b": user_b,
        "token_b": token_b,
        "headers_b": {"Authorization": f"Bearer {token_b}"},
    }
    db.close()
    return users_data


def test_unauthorized_reset():
    """1. Unauthenticated request to /documents/reset returns 401."""
    res = client.delete("/api/v1/documents/reset")
    assert res.status_code == 401


def test_empty_workspace_reset(test_users):
    """2. Calling reset on an empty workspace succeeds cleanly with 0 documents deleted."""
    headers_a = test_users["headers_a"]
    user_a = test_users["user_a"]

    # Ensure no documents or history exist for user A before test
    db = SessionLocal()
    db.query(Document).filter(Document.user_id == user_a.id).delete()
    db.query(HistoryRecord).filter(HistoryRecord.user_id == user_a.id).delete()
    db.commit()
    db.close()

    res = client.delete("/api/v1/documents/reset", headers=headers_a)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["documents_deleted"] == 0
    assert data["derived_records_deleted"] == 0
    assert data["files_deleted"] == 0

    # Verify audit log was created even for empty reset
    db = SessionLocal()
    audit = (
        db.query(HistoryRecord)
        .filter(HistoryRecord.user_id == user_a.id, HistoryRecord.action == "GLOBAL_DOCUMENT_RESET")
        .order_by(HistoryRecord.created_at.desc())
        .first()
    )
    assert audit is not None
    assert "deleted 0 documents" in audit.result_summary
    db.close()


def test_successful_global_reset_and_storage_cleanup(test_users):
    """3. Comprehensive global reset test:

    - Creates 2 real documents with physical files on disk
    - Creates a reconciliation session
    - Creates a correction proposal
    - Creates assistant conversation and file context
    - Calls DELETE /api/v1/documents/reset
    - Verifies DB records deleted, storage files removed, and audit log created.
    """
    user_a = test_users["user_a"]
    headers_a = test_users["headers_a"]
    db = SessionLocal()

    # Create dummy storage files
    upload_dir = settings.uploads_dir
    file_a1 = upload_dir / f"test_reset_a1_{uuid.uuid4().hex[:6]}.xlsx"
    file_a2 = upload_dir / f"test_reset_a2_{uuid.uuid4().hex[:6]}.csv"
    file_a1.write_bytes(b"PK\x03\x04test_content_a1")
    file_a2.write_bytes(b"Date,Amount\n2026-03-01,1000")

    doc1 = Document(
        user_id=user_a.id,
        original_filename="Bank_Stmt.xlsx",
        stored_filename=file_a1.name,
        file_path=str(file_a1),
        file_size=len(file_a1.read_bytes()),
        category="bank_statement",
        status="ready",
    )
    doc2 = Document(
        user_id=user_a.id,
        original_filename="Ledger_Data.csv",
        stored_filename=file_a2.name,
        file_path=str(file_a2),
        file_size=len(file_a2.read_bytes()),
        category="ledger",
        status="ready",
    )
    db.add_all([doc1, doc2])
    db.commit()
    db.refresh(doc1)
    db.refresh(doc2)

    # Derived Reconciliation Session
    session = ReconciliationSession(
        user_id=user_a.id,
        bank_document_id=doc1.id,
        ledger_document_id=doc2.id,
        bank_statement_name=doc1.original_filename,
        ledger_file_name=doc2.original_filename,
        status="completed",
        details_json="{}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Derived Correction Proposal
    proposal = CorrectionProposal(
        correction_id=f"cor_test_{uuid.uuid4().hex[:6]}",
        user_id=user_a.id,
        session_id=session.id,
        document_id=doc2.id,
        row_reference="Row 1",
        field="Amount",
        explanation="Test variance",
        difference=500.0,
    )
    db.add(proposal)

    # Derived Assistant Conversation and File Context
    conv = AssistantConversation(
        id=f"conv_test_{uuid.uuid4().hex[:6]}",
        user_id=user_a.id,
        title="Test Conversation",
    )
    db.add(conv)
    db.commit()

    file_ctx = AssistantFileContext(
        conversation_id=conv.id,
        document_id=doc1.id,
    )
    db.add(file_ctx)

    # Derived History Record
    hist = HistoryRecord(
        user_id=user_a.id,
        module="documents",
        action="document_uploaded",
        target_name=doc1.original_filename,
        document_id=doc1.id,
    )
    db.add(hist)
    db.commit()

    # Pre-assertions: files exist on disk
    assert file_a1.exists()
    assert file_a2.exists()
    doc1_id = doc1.id
    db.close()

    # Execute Reset
    res = client.delete("/api/v1/documents/reset", headers=headers_a)
    assert res.status_code == 200
    res_data = res.json()
    assert res_data["success"] is True
    assert res_data["documents_deleted"] == 2
    assert res_data["derived_records_deleted"] >= 4
    assert res_data["files_deleted"] == 2

    # Verify physical storage cleanup
    assert not file_a1.exists()
    assert not file_a2.exists()

    # Verify database records deleted
    db2 = SessionLocal()
    assert db2.query(Document).filter(Document.user_id == user_a.id).count() == 0
    assert db2.query(ReconciliationSession).filter(ReconciliationSession.user_id == user_a.id).count() == 0
    assert db2.query(CorrectionProposal).filter(CorrectionProposal.user_id == user_a.id).count() == 0
    assert db2.query(AssistantFileContext).filter(AssistantFileContext.document_id == doc1_id).count() == 0

    # Verify Audit Log
    audit = (
        db2.query(HistoryRecord)
        .filter(HistoryRecord.user_id == user_a.id, HistoryRecord.action == "GLOBAL_DOCUMENT_RESET")
        .first()
    )
    assert audit is not None
    assert "deleted 2 documents" in audit.result_summary
    assert "2 storage files" in audit.result_summary
    db2.close()


def test_cross_user_isolation(test_users):
    """4. Security: User A resetting their workspace MUST NOT touch User B's documents or files."""
    user_a = test_users["user_a"]
    headers_a = test_users["headers_a"]
    user_b = test_users["user_b"]
    db = SessionLocal()

    upload_dir = settings.uploads_dir
    file_b = upload_dir / f"test_b_preserve_{uuid.uuid4().hex[:6]}.xlsx"
    file_b.write_bytes(b"PK\x03\x04user_b_private_content")

    doc_b = Document(
        user_id=user_b.id,
        original_filename="User_B_Confidential.xlsx",
        stored_filename=file_b.name,
        file_path=str(file_b),
        file_size=len(file_b.read_bytes()),
        category="financial",
        status="ready",
    )
    db.add(doc_b)
    db.commit()
    db.refresh(doc_b)
    db.close()

    assert file_b.exists()

    # User A calls reset
    res = client.delete("/api/v1/documents/reset", headers=headers_a)
    assert res.status_code == 200

    # User B's document and physical file MUST still exist!
    assert file_b.exists()
    db2 = SessionLocal()
    doc_b_check = db2.query(Document).filter(Document.id == doc_b.id).first()
    assert doc_b_check is not None
    assert doc_b_check.original_filename == "User_B_Confidential.xlsx"

    # Cleanup user B test file
    db2.delete(doc_b_check)
    db2.commit()
    db2.close()
    if file_b.exists():
        file_b.unlink()


def test_unrelated_account_and_tax_data_intact(test_users):
    """5. Accounting Safety: Reset must NOT delete user credentials, account, or GST registration."""
    user_a = test_users["user_a"]
    headers_a = test_users["headers_a"]
    db = SessionLocal()

    # Create a GST registration for User A
    gst_reg = db.query(GSTRegistration).filter(GSTRegistration.user_id == user_a.id).first()
    if not gst_reg:
        gst_reg = GSTRegistration(
            user_id=user_a.id,
            gstin="29ABCDE1234F1Z5",
            legal_name="Reset User A Enterprise",
            trade_name="User A Trading",
            state_code="29",
            registration_type="regular",
        )
        db.add(gst_reg)
        db.commit()
    db.close()

    # Call reset
    res = client.delete("/api/v1/documents/reset", headers=headers_a)
    assert res.status_code == 200

    # Verify user account is completely intact
    db2 = SessionLocal()
    u = db2.query(User).filter(User.id == user_a.id).first()
    assert u is not None
    assert u.email == "reset_user_a@litebooks.ai"
    assert u.is_active is True

    # Verify GST registration is completely intact
    reg_check = db2.query(GSTRegistration).filter(GSTRegistration.user_id == user_a.id).first()
    assert reg_check is not None
    assert reg_check.gstin == "29ABCDE1234F1Z5"
    db2.close()


def test_transaction_rollback_on_error(test_users):
    """6. Transactionality: If an unexpected error occurs during database operations,

    the entire transaction is rolled back and physical files are preserved.
    """
    user_a = test_users["user_a"]
    headers_a = test_users["headers_a"]
    db = SessionLocal()

    upload_dir = settings.uploads_dir
    test_file = upload_dir / f"test_rollback_{uuid.uuid4().hex[:6]}.csv"
    test_file.write_bytes(b"col1,col2\nval1,val2")

    doc = Document(
        user_id=user_a.id,
        original_filename="Rollback_Doc.csv",
        stored_filename=test_file.name,
        file_path=str(test_file),
        file_size=len(test_file.read_bytes()),
        category="general",
        status="ready",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    doc_id = doc.id
    db.close()

    assert test_file.exists()

    # Simulate database failure during commit
    with patch("sqlalchemy.orm.Session.commit", side_effect=Exception("Simulated DB Crash")):
        res = client.delete("/api/v1/documents/reset", headers=headers_a)
        assert res.status_code == 500
        assert "Simulated DB Crash" in res.json()["detail"]

    # Verify file and document still exist after crash/failure
    assert test_file.exists()
    db2 = SessionLocal()
    doc_check = db2.query(Document).filter(Document.id == doc_id).first()
    assert doc_check is not None

    # Clean up test artifact
    db2.delete(doc_check)
    db2.commit()
    db2.close()
    if test_file.exists():
        test_file.unlink()
