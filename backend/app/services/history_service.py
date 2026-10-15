from datetime import datetime, timedelta, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.history import HistoryRecord


class HistoryService:
    @staticmethod
    def list_history(
        db: Session,
        module: Optional[str] = None,
        status: Optional[str] = None,
        user_id: Optional[int] = None,
        limit: int = 50,
    ) -> List[HistoryRecord]:
        query = db.query(HistoryRecord)
        if user_id is not None:
            query = query.filter((HistoryRecord.user_id == user_id) | (HistoryRecord.user_id.is_(None)))
        if module and module != "all":
            query = query.filter(HistoryRecord.module == module)
        if status and status != "all":
            query = query.filter(HistoryRecord.status == status)
        records = query.order_by(HistoryRecord.created_at.desc()).limit(limit).all()

        # Seed initial demonstrative placeholder records if empty
        if not records and not module and not status:
            HistoryService._seed_sample_placeholders(db)
            records = query.order_by(HistoryRecord.created_at.desc()).limit(limit).all()

        return records

    @staticmethod
    def record_activity(
        db: Session,
        module: str,
        action: str,
        target_name: str,
        status: str = "completed",
        result_summary: Optional[str] = None,
        user_action: str = "Manual action by user",
        report_reference: Optional[str] = None,
        document_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> HistoryRecord:
        record = HistoryRecord(
            user_id=user_id,
            module=module,
            action=action,
            target_name=target_name,
            status=status,
            result_summary=result_summary,
            user_action=user_action,
            report_reference=report_reference,
            document_id=document_id,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def _seed_sample_placeholders(db: Session) -> None:
        """Seeds initial foundation placeholder activities for UI presentation."""
        now = datetime.now(timezone.utc)
        samples = [
            HistoryRecord(
                module="reconciliation",
                action="reconciliation_completed",
                target_name="HDFC Bank Q1 Statement.pdf",
                status="completed",
                result_summary="Reconciliation completed: 142 transactions matched, 0 discrepancies.",
                user_action="Manual reconciliation run",
                report_reference="REC-2026-001",
                created_at=now - timedelta(hours=2),
            ),
            HistoryRecord(
                module="gst",
                action="gst_analysis_completed",
                target_name="GSTR-3B Aug 2026",
                status="completed",
                result_summary="GST analysis completed: Input tax credit verified against GSTR-2B.",
                user_action="GST audit check",
                report_reference="GST-AUG-2026",
                created_at=now - timedelta(hours=5),
            ),
            HistoryRecord(
                module="financial_statements",
                action="financial_statement_generated",
                target_name="Provisional P&L FY 2026-27",
                status="completed",
                result_summary="Financial statement generated: Clean trial balance validation.",
                user_action="Export P&L statement",
                report_reference="FS-Q2-2026",
                created_at=now - timedelta(days=1),
            ),
            HistoryRecord(
                module="documents",
                action="document_uploaded",
                target_name="Vendor_Invoices_Aug26.zip",
                status="completed",
                result_summary="Document uploaded: 18 PDF files cataloged successfully.",
                user_action="Uploaded by user",
                report_reference=None,
                created_at=now - timedelta(days=2),
            ),
        ]
        db.add_all(samples)
        db.commit()
