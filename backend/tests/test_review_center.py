import json
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.reconciliation import CorrectionProposal
from app.core.auth import get_current_user


client = TestClient(app)


def test_dashboard_summary_real_metrics(default_test_user):
    """Verifies that the dashboard summary returns real, non-placeholder metrics."""
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 200
    data = response.json()

    assert data["is_demo_data"] is False
    assert "total_documents" in data
    assert "analyzed_documents" in data
    assert "needs_review_count" in data
    assert "high_severity_count" in data
    assert "reconciliation_needs_review" in data
    assert isinstance(data["needs_attention_items"], list)
    assert isinstance(data["recent_documents_list"], list)


def test_review_center_findings_list(default_test_user):
    """Verifies listing findings from Review Center with summary counters."""
    response = client.get("/api/v1/review-center/findings")
    assert response.status_code == 200
    data = response.json()

    assert "all_count" in data
    assert "high_count" in data
    assert "medium_count" in data
    assert "low_count" in data
    assert "review_required_count" in data
    assert "reviewed_count" in data
    assert isinstance(data["findings"], list)


def test_review_center_decision_on_proposal(default_test_user):
    """Verifies an accountant can record an explicit decision on a correction proposal."""
    db = SessionLocal()
    # Clean up prior if exists
    db.query(CorrectionProposal).filter(CorrectionProposal.correction_id == "COR-TEST-9999").delete()
    db.commit()

    prop = CorrectionProposal(
        correction_id="COR-TEST-9999",
        user_id=default_test_user.id,
        sheet_name="Balance Sheet",
        cell_address="F42",
        row_reference="42",
        field="Total Assets",
        original_value="201402126.89",
        proposed_value="201403570.73",
        difference=1443.84,
        reason_category="BALANCE_SHEET_IMBALANCE",
        explanation="Assets and Liabilities do not balance by 1443.84.",
        evidence_json="[]",
        recommended_verification_json="[]",
        confidence="HIGH",
        status="PROPOSED",
    )
    db.add(prop)
    db.commit()
    db.close()

    try:
        # Make decision: CONFIRMED / APPROVED
        decision_resp = client.post(
            "/api/v1/review-center/findings/COR-TEST-9999/decision",
            json={"decision": "CONFIRMED", "notes": "Approved after checking supporting vouchers"}
        )
        assert decision_resp.status_code == 200
        data = decision_resp.json()
        assert data["id"] == "COR-TEST-9999"
        assert data["status"] == "APPROVED"
        assert data["accountant_decision"] == "approved"
    finally:
        # Clean up
        db2 = SessionLocal()
        db2.query(CorrectionProposal).filter(CorrectionProposal.correction_id == "COR-TEST-9999").delete()
        db2.commit()
        db2.close()


def test_review_center_unauthorized_access(default_test_user):
    """Verifies that users cannot modify findings owned by another user."""
    db = SessionLocal()
    other_user = db.query(User).filter(User.username == "other_user_review").first()
    if not other_user:
        other_user = User(
            username="other_user_review",
            email="other@litebooks.ai",
            full_name="Other Review User",
            hashed_password="hashed_pass_xyz",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

    prop = CorrectionProposal(
        correction_id="COR-OTHER-8888",
        user_id=other_user.id,
        sheet_name="P&L",
        row_reference="12",
        field="Revenue",
        original_value="1000",
        proposed_value="1200",
        difference=200,
        reason_category="REVENUE_MISMATCH",
        explanation="Revenue understated.",
        confidence="MEDIUM",
        status="PROPOSED",
    )
    db.add(prop)
    db.commit()
    db.close()

    # default_test_user tries to decide on other_user's proposal -> 403
    resp = client.post(
        "/api/v1/review-center/findings/COR-OTHER-8888/decision",
        json={"decision": "CONFIRMED"}
    )
    assert resp.status_code == 403

    # Clean up
    db2 = SessionLocal()
    p = db2.query(CorrectionProposal).filter(CorrectionProposal.correction_id == "COR-OTHER-8888").first()
    if p:
        db2.delete(p)
        db2.commit()
    db2.close()


def test_document_analysis_endpoint(default_test_user):
    """Verifies that an accountant can inspect analysis of their document."""
    # Find a document owned by default_test_user
    db = SessionLocal()
    doc = db.query(Document).filter(Document.user_id == default_test_user.id).first()
    db.close()

    if doc:
        resp = client.get(f"/api/v1/documents/{doc.id}/analysis")
        assert resp.status_code == 200
        data = resp.json()
        assert "sheets" in data
        assert "document_type" in data
        assert "confidence" in data

    # Non-existent doc -> 404
    resp_404 = client.get("/api/v1/documents/999999/analysis")
    assert resp_404.status_code == 404

