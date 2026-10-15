import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.history import HistoryRecord
from app.models.reconciliation import CorrectionProposal, ReconciliationSession
from app.models.user import User
from app.schemas.dashboard import AttentionItem, DashboardSummary, RecentDocumentItem
from app.schemas.history import HistoryRecordResponse
from app.services.history_service import HistoryService
from app.services.review_center_service import ReviewCenterService

logger = logging.getLogger(__name__)


class DashboardService:
    @staticmethod
    def get_summary(db: Session, current_user: Optional[User] = None) -> DashboardSummary:
        user_id = current_user.id if current_user else None

        # 1. Real documents count
        doc_query = db.query(Document)
        if user_id is not None:
            doc_query = doc_query.filter(Document.user_id == user_id)
        total_docs = doc_query.count()
        recent_docs = doc_query.order_by(Document.created_at.desc()).limit(6).all()

        # 2. Real reconciliation sessions count
        recon_query = db.query(ReconciliationSession)
        if user_id is not None:
            recon_query = recon_query.filter(ReconciliationSession.user_id == user_id)
        recon_count = recon_query.count()
        recon_sessions = recon_query.order_by(ReconciliationSession.created_at.desc()).limit(10).all()

        # 3. Real Review Center findings
        review_summary = ReviewCenterService.get_findings(db, user_id=user_id)
        all_findings = review_summary.findings

        needs_review_count = review_summary.review_required_count
        high_severity_count = review_summary.high_count

        # Reconciliation needs review items
        recon_needs_review = sum(
            1 for s in recon_sessions
            if (s.mismatched_count > 0 or s.unmatched_bank_count > 0 or s.unmatched_ledger_count > 0)
        )

        # 4. Attention items: sorted by priority (HIGH/CRITICAL -> REVIEW_REQUIRED -> MEDIUM -> LOW)
        def priority_score(item):
            sev = item.severity.upper()
            stat = item.status.upper()
            score = 0
            if sev in ("HIGH", "CRITICAL"):
                score += 100
            elif sev == "MEDIUM":
                score += 50
            else:
                score += 10

            if stat in ("REVIEW_REQUIRED", "NEEDS_REVIEW"):
                score += 30
            elif stat == "UNDER_REVIEW":
                score += 20
            return score

        sorted_findings = sorted(
            [f for f in all_findings if f.status in ("NEEDS_REVIEW", "REVIEW_REQUIRED", "UNDER_REVIEW", "OPEN", "PROPOSED")],
            key=priority_score,
            reverse=True,
        )

        attention_items: List[AttentionItem] = []
        for f in sorted_findings[:6]:
            attention_items.append(
                AttentionItem(
                    id=f.id,
                    severity=f.severity,
                    finding_type=f.type,
                    title=f.title,
                    document_name=f.document_name,
                    document_id=f.document_id,
                    financial_period=f.financial_period,
                    difference=f.difference,
                    status=f.status,
                    cell_address=f.cell_address,
                )
            )

        # 5. Recent documents list
        recent_documents_list: List[RecentDocumentItem] = []
        for doc in recent_docs:
            doc_findings = [f for f in all_findings if f.document_id == doc.id]
            doc_needs_review = [f for f in doc_findings if f.status in ("NEEDS_REVIEW", "REVIEW_REQUIRED", "UNDER_REVIEW")]
            
            period_text = None
            if doc_findings and doc_findings[0].financial_period:
                period_text = doc_findings[0].financial_period

            recent_documents_list.append(
                RecentDocumentItem(
                    id=doc.id,
                    original_filename=doc.original_filename,
                    category=doc.category,
                    document_type=doc.category.replace("_", " ").title(),
                    financial_period=period_text,
                    created_at=doc.created_at.strftime("%b %d, %Y") if doc.created_at else "",
                    status="Analyzed" if doc.status == "ready" else doc.status.title(),
                    findings_count=len(doc_findings),
                    needs_review_count=len(doc_needs_review),
                    file_size=doc.file_size or 0,
                )
            )

        # 6. Real history
        recent_history = HistoryService.list_history(db, user_id=user_id, limit=8)

        user_name = current_user.full_name or current_user.username if current_user else "Partner Accountant"

        return DashboardSummary(
            total_reports=recon_count + total_docs,
            pending_items=needs_review_count,
            recent_documents=total_docs,
            reconciliations=recon_count,
            user_name=user_name,
            is_demo_data=False,
            recent_activities=[
                HistoryRecordResponse.model_validate(rec) for rec in recent_history
            ],
            total_documents=total_docs,
            analyzed_documents=sum(1 for d in recent_docs if d.status == "ready"),
            needs_review_count=needs_review_count,
            high_severity_count=high_severity_count,
            reconciliation_needs_review=recon_needs_review,
            needs_attention_items=attention_items,
            recent_documents_list=recent_documents_list,
        )
