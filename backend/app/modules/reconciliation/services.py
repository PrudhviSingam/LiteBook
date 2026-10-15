import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.document import Document
from app.models.reconciliation import ReconciliationSession
from app.services.document_service import DocumentService
from app.services.history_service import HistoryService
from app.modules.reconciliation.ai_explainer import ReconciliationAIExplainer
from app.modules.reconciliation.matching import match_transactions
from app.modules.reconciliation.normalization import (
    NormalizationError,
    normalize_transactions,
    preview_file,
)
from app.modules.reconciliation.report import generate_reconciliation_csv_report
from app.modules.reconciliation.schemas import (
    ColumnMappingPreview,
    DocumentTypeEnum,
    ReconciliationItem,
    ReconciliationRuleConfig,
    ReconciliationSessionResponse,
    ReconciliationStatusEnum,
    ReconciliationSummary,
)
from app.modules.reconciliation.workbook_inspector import (
    WorkbookInspector,
    format_indian_currency,
)
from app.modules.ai_assistant.schemas import DiscrepancyFinding


class ReconciliationService:
    @classmethod
    def discover_sources(
        cls,
        db: Session,
        document_ids: List[int],
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Discovers candidate General Ledger and Bank Statement sources across documents.
        Supports:
        - Case A: Single workbook with both GL and Bank Statement sheets
        - Case B: Two distinct workbooks (one GL, one Bank)
        - Case C: Multi-sheet workbooks with extra non-reconciliation sheets
        """
        ledger_candidates: List[Dict[str, Any]] = []
        bank_candidates: List[Dict[str, Any]] = []

        for doc_id in document_ids:
            doc = DocumentService.get_document(db, doc_id, user_id=user_id)
            if not doc:
                continue
            file_path = Path(doc.file_path)
            if not file_path.exists():
                continue

            # Inspect workbook to detect sheets & classifications
            try:
                insp = WorkbookInspector.inspect(file_path, doc.original_filename)
            except Exception as e:
                logger.warning("Error inspecting doc %s: %s", doc.id, e)
                continue

            for sheet_info in insp.sheets:
                s_name = sheet_info.sheet_name
                c_type = sheet_info.classification
                confidence = sheet_info.confidence

                source_entry = {
                    "document_id": doc.id,
                    "filename": doc.original_filename,
                    "sheet_name": s_name,
                    "document_type": c_type.value if hasattr(c_type, "value") else str(c_type),
                    "confidence": confidence,
                    "row_count": sheet_info.row_count,
                    "col_count": sheet_info.col_count,
                    "period": ", ".join(insp.period_columns) if insp.period_columns else None,
                }

                if c_type in (DocumentTypeEnum.GENERAL_LEDGER, DocumentTypeEnum.ACCOUNTING_LEDGER):
                    ledger_candidates.append({**source_entry, "source_type": "GENERAL_LEDGER"})
                elif c_type == DocumentTypeEnum.BANK_STATEMENT:
                    bank_candidates.append({**source_entry, "source_type": "BANK_STATEMENT"})
                else:
                    # Secondary heuristic based on sheet name and filename if classified as UNKNOWN
                    s_low = s_name.lower()
                    f_low = doc.original_filename.lower()
                    if "bank" in s_low or "bank" in f_low:
                        bank_candidates.append({**source_entry, "source_type": "BANK_STATEMENT", "confidence": "MEDIUM"})
                    elif "ledger" in s_low or "gl" in s_low or "ledger" in f_low or "reconciliation" in f_low:
                        ledger_candidates.append({**source_entry, "source_type": "GENERAL_LEDGER", "confidence": "MEDIUM"})

        status_val = "ready"
        reason = None
        selected_ledger = None
        selected_bank = None

        if len(ledger_candidates) == 1 and len(bank_candidates) == 1:
            selected_ledger = ledger_candidates[0]
            selected_bank = bank_candidates[0]
            status_val = "ready"
        elif len(ledger_candidates) > 1 or len(bank_candidates) > 1:
            status_val = "REVIEW_REQUIRED"
            reason = "MULTIPLE_COMPATIBLE_SOURCES"
        elif len(ledger_candidates) == 0 and len(bank_candidates) == 0:
            status_val = "REVIEW_REQUIRED"
            reason = "NO_RECONCILIATION_SOURCES_FOUND"
        elif len(ledger_candidates) == 0:
            status_val = "REVIEW_REQUIRED"
            reason = "GENERAL_LEDGER_NOT_FOUND"
        elif len(bank_candidates) == 0:
            status_val = "REVIEW_REQUIRED"
            reason = "BANK_STATEMENT_NOT_FOUND"

        return {
            "status": status_val,
            "reason": reason,
            "ledger_candidates": ledger_candidates,
            "bank_candidates": bank_candidates,
            "selected_ledger": selected_ledger,
            "selected_bank": selected_bank,
        }

    @classmethod
    def format_findings_for_assistant(
        cls,
        items: List[ReconciliationItem],
        ledger_source: Dict[str, Any],
        bank_source: Dict[str, Any],
    ) -> List[DiscrepancyFinding]:
        """Converts deterministic reconciliation discrepancies into verified assistant findings."""
        findings: List[DiscrepancyFinding] = []
        for idx, item in enumerate(items):
            if item.status == ReconciliationStatusEnum.MATCHED:
                continue

            diff_str = format_indian_currency(item.difference)
            ledger_tx = item.ledger_transaction
            bank_tx = item.bank_transaction

            ledger_ev = None
            if ledger_tx:
                ledger_ev = {
                    "filename": ledger_tx.filename or ledger_source.get("filename", ""),
                    "sheet_name": ledger_tx.sheet_name or ledger_source.get("sheet_name", ""),
                    "row_number": ledger_tx.original_row_number,
                    "date": ledger_tx.date,
                    "description": ledger_tx.description,
                    "reference": ledger_tx.reference,
                    "amount": format_indian_currency(ledger_tx.amount),
                }

            bank_ev = None
            if bank_tx:
                bank_ev = {
                    "filename": bank_tx.filename or bank_source.get("filename", ""),
                    "sheet_name": bank_tx.sheet_name or bank_source.get("sheet_name", ""),
                    "row_number": bank_tx.original_row_number,
                    "date": bank_tx.date,
                    "description": bank_tx.description,
                    "reference": bank_tx.reference,
                    "amount": format_indian_currency(bank_tx.amount),
                }

            finding_type = item.status.value
            title = f"{finding_type.replace('_', ' ').title()}: {item.description}"
            if item.reference:
                title += f" ({item.reference})"

            finding = DiscrepancyFinding(
                finding_id=f"FIND-REC-{idx+1:03d}",
                finding_type=finding_type,
                title=title,
                location="General Ledger vs Bank Statement",
                sheet=ledger_source.get("sheet_name", "General Ledger"),
                cell_address=f"Row {ledger_tx.original_row_number}" if ledger_tx and ledger_tx.original_row_number else None,
                expected_value=format_indian_currency(item.ledger_amount) if item.ledger_amount is not None else "None",
                actual_value=format_indian_currency(item.bank_amount) if item.bank_amount is not None else "None",
                difference=diff_str,
                reason_category=finding_type,
                summary=item.reason,
                possible_reasons=[
                    "Possible unposted voucher or debit note in the ledger.",
                    "Possible data entry transposition error.",
                    "Bank timing difference (uncleared cheque/deposit).",
                ] if item.status == ReconciliationStatusEnum.AMOUNT_MISMATCH else [
                    "Direct bank debit or credit not yet recorded in the accounting books.",
                    "Outstanding cheque or collection in transit.",
                ],
                evidence=[
                    f"Ledger: {ledger_ev.get('filename')} (Sheet: {ledger_ev.get('sheet_name')}, Row {ledger_ev.get('row_number')}): {ledger_ev.get('amount')}" if ledger_ev else "Ledger: No corresponding entry found",
                    f"Bank: {bank_ev.get('filename')} (Sheet: {bank_ev.get('sheet_name')}, Row {bank_ev.get('row_number')}): {bank_ev.get('amount')}" if bank_ev else "Bank: No corresponding entry found",
                    f"Variance: {diff_str}",
                ],
                recommended_verification=[item.suggested_action] if item.suggested_action else [
                    "Inspect supporting vendor invoice or bank advice.",
                    "Verify sub-ledger postings against bank statement.",
                ],
                confidence="HIGH" if item.confidence in ("high", "medium") else "MEDIUM",
                severity="HIGH" if abs(item.difference) > 5000 else "MEDIUM",
                status="VERIFIED",
                ledger_evidence=ledger_ev,
                bank_evidence=bank_ev,
                possible_cause="Potential data entry error or timing delay in posting.",
                proven_cause=None,
            )
            findings.append(finding)
        return findings
    @staticmethod
    async def preview_uploaded_file(file: UploadFile, sheet_name: Optional[str] = None) -> ColumnMappingPreview:
        content = await file.read()
        await file.seek(0)
        try:
            return preview_file(content, file.filename or "uploaded_file", sheet_name=sheet_name)
        except NormalizationError as ne:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(ne),
            )
        except Exception as e:
            logger.error(
                "Error previewing file %s: %s",
                file.filename or "uploaded_file",
                e,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to read the file structure. Some column headers could not be interpreted automatically. Please review the detected columns.",
            )

    @classmethod
    async def run_reconciliation(
        cls,
        db: Session,
        bank_file: Optional[UploadFile] = None,
        ledger_file: Optional[UploadFile] = None,
        bank_document_id: Optional[int] = None,
        ledger_document_id: Optional[int] = None,
        bank_sheet_name: Optional[str] = None,
        ledger_sheet_name: Optional[str] = None,
        file_a: Optional[UploadFile] = None,
        file_b: Optional[UploadFile] = None,
        file_a_document_id: Optional[int] = None,
        file_b_document_id: Optional[int] = None,
        sheet_a: Optional[str] = None,
        sheet_b: Optional[str] = None,
        file_a_name: Optional[str] = None,
        file_b_name: Optional[str] = None,
        mapping_a: Optional[Dict[str, Optional[str]]] = None,
        mapping_b: Optional[Dict[str, Optional[str]]] = None,
        rules: ReconciliationRuleConfig = ReconciliationRuleConfig(),
        user_id: Optional[int] = None,
    ) -> ReconciliationSessionResponse:
        # Resolve Effective File A & File B
        eff_file_a = file_a or bank_file
        eff_doc_id_a = file_a_document_id or bank_document_id
        eff_sheet_a = sheet_a or bank_sheet_name
        eff_mapping_a = mapping_a

        eff_file_b = file_b or ledger_file
        eff_doc_id_b = file_b_document_id or ledger_document_id
        eff_sheet_b = sheet_b or ledger_sheet_name
        eff_mapping_b = mapping_b

        doc_a: Optional[Document] = None
        doc_b: Optional[Document] = None
        bytes_a: Optional[bytes] = None
        bytes_b: Optional[bytes] = None
        name_a = file_a_name or "Source File A"
        name_b = file_b_name or "Source File B"

        # 1. Ingest File A (Source A)
        if eff_file_a and eff_file_a.filename:
            name_a = eff_file_a.filename
            bytes_a = await eff_file_a.read()
            await eff_file_a.seek(0)
            doc_a = await DocumentService.upload_document(
                db=db,
                file=eff_file_a,
                category="reconciliation_source_a",
                notes="Difference detection Source A",
                user_id=user_id,
            )
        elif eff_doc_id_a:
            doc_a = DocumentService.get_document(db, eff_doc_id_a)
            if not doc_a:
                raise HTTPException(status_code=404, detail=f"Source A document ID {eff_doc_id_a} not found")
            if user_id is not None and doc_a.user_id is not None and doc_a.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied to Source A document")
            name_a = doc_a.original_filename
            path_a = Path(doc_a.file_path)
            if not path_a.exists():
                raise HTTPException(status_code=404, detail="Source A file missing on disk")
            bytes_a = path_a.read_bytes()
        else:
            raise HTTPException(status_code=400, detail="Source File A or document ID is required")

        # 2. Ingest File B (Source B)
        if eff_file_b and eff_file_b.filename:
            name_b = eff_file_b.filename
            bytes_b = await eff_file_b.read()
            await eff_file_b.seek(0)
            doc_b = await DocumentService.upload_document(
                db=db,
                file=eff_file_b,
                category="reconciliation_source_b",
                notes="Difference detection Source B",
                user_id=user_id,
            )
        elif eff_doc_id_b:
            doc_b = DocumentService.get_document(db, eff_doc_id_b)
            if not doc_b:
                raise HTTPException(status_code=404, detail=f"Source B document ID {eff_doc_id_b} not found")
            if user_id is not None and doc_b.user_id is not None and doc_b.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied to Source B document")
            name_b = doc_b.original_filename
            path_b = Path(doc_b.file_path)
            if not path_b.exists():
                raise HTTPException(status_code=404, detail="Source B file missing on disk")
            bytes_b = path_b.read_bytes()
        else:
            raise HTTPException(status_code=400, detail="Source File B or document ID is required")

        # 3. Normalize Transactions with Provenance & User Mappings
        try:
            txs_a = normalize_transactions(
                bytes_a,
                name_a,
                source="source_a",
                sheet_name=eff_sheet_a,
                document_id=doc_a.id if doc_a else None,
                source_type="SOURCE_A",
                user_mapping=eff_mapping_a,
            )
            txs_b = normalize_transactions(
                bytes_b,
                name_b,
                source="source_b",
                sheet_name=eff_sheet_b,
                document_id=doc_b.id if doc_b else None,
                source_type="SOURCE_B",
                user_mapping=eff_mapping_b,
            )
        except NormalizationError as ne:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ne))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Normalization failed: {str(e)}",
            )

        # 4. Deterministic Multi-Pass Difference Detection & Matching
        results, summary = match_transactions(txs_a, txs_b, rules=rules)

        # 5. Enrich with Explanations
        for item in results:
            ai_data = await ReconciliationAIExplainer.generate_explanation(item)
            item.reason = ai_data["explanation"]
            item.suggested_action = ai_data["suggested_action"]

        # 6. Save Session into Database with Full Source Provenance
        payload_data = {
            "source_a": {
                "document_id": doc_a.id if doc_a else None,
                "filename": name_a,
                "sheet_name": eff_sheet_a or "Sheet1",
                "source_type": "SOURCE_A",
            },
            "source_b": {
                "document_id": doc_b.id if doc_b else None,
                "filename": name_b,
                "sheet_name": eff_sheet_b or "Sheet1",
                "source_type": "SOURCE_B",
            },
            # Backward compatibility fields
            "ledger_source": {
                "document_id": doc_b.id if doc_b else None,
                "filename": name_b,
                "sheet_name": eff_sheet_b or "General Ledger",
                "source_type": "GENERAL_LEDGER",
            },
            "bank_source": {
                "document_id": doc_a.id if doc_a else None,
                "filename": name_a,
                "sheet_name": eff_sheet_a or "Sheet1",
                "source_type": "BANK_STATEMENT",
            },
            "summary": summary.model_dump(),
            "transactions": [t.model_dump() for t in results],
        }

        matched_amount = sum(
            r.bank_amount or r.ledger_amount or 0.0
            for r in results
            if r.status.value == "MATCHED"
        )

        session = ReconciliationSession(
            user_id=user_id,
            bank_document_id=doc_a.id if doc_a else None,
            ledger_document_id=doc_b.id if doc_b else None,
            bank_statement_name=name_a,
            ledger_file_name=name_b,
            status="completed",
            total_bank_entries=summary.total_bank_transactions,
            total_ledger_entries=summary.total_ledger_transactions,
            matched_count=summary.matched_count,
            mismatched_count=summary.unmatched_count,
            unmatched_bank_count=summary.missing_in_ledger_count,
            unmatched_ledger_count=summary.missing_in_bank_count,
            total_matched_amount=round(matched_amount, 2),
            total_variance=summary.total_variance,
            details_json=json.dumps(payload_data),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # 7. Automatically Record Activity in History
        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="reconciliation",
            action="difference_detection_completed",
            target_name=f"{name_a} vs {name_b}",
            status="completed",
            result_summary=(
                f"Comparison completed: {summary.matched_count} matched, "
                f"{summary.unmatched_count} differences detected (Rate: {summary.reconciliation_rate}%)"
            ),
            user_action="Difference Detection Comparison",
            report_reference=f"DIFF-{session.id:04d}",
            document_id=doc_a.id if doc_a else None,
        )

        return ReconciliationSessionResponse(
            id=session.id,
            bank_statement_name=session.bank_statement_name,
            ledger_file_name=session.ledger_file_name,
            status=session.status,
            summary=summary,
            transactions=results,
            created_at=session.created_at.isoformat(),
            file_a_name=name_a,
            file_b_name=name_b,
            sheet_a_name=eff_sheet_a or "Sheet1",
            sheet_b_name=eff_sheet_b or "Sheet1",
            excel_report_url=f"/api/v1/reconciliation/results/{session.id}/difference-report",
            difference_summary=summary.model_dump(),
        )

    @staticmethod
    def get_session(db: Session, session_id: int, user_id: Optional[int] = None) -> ReconciliationSessionResponse:
        session = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Reconciliation session not found")
        if user_id is not None and session.user_id is not None and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own this reconciliation session.")

        data = json.loads(session.details_json)
        summary = ReconciliationSummary(**data["summary"])
        transactions = [ReconciliationItem(**t) for t in data["transactions"]]

        source_a_meta = data.get("source_a", {})
        source_b_meta = data.get("source_b", {})

        return ReconciliationSessionResponse(
            id=session.id,
            bank_statement_name=session.bank_statement_name,
            ledger_file_name=session.ledger_file_name,
            status=session.status,
            summary=summary,
            transactions=transactions,
            created_at=session.created_at.isoformat(),
            file_a_name=source_a_meta.get("filename") or session.bank_statement_name,
            file_b_name=source_b_meta.get("filename") or session.ledger_file_name,
            sheet_a_name=source_a_meta.get("sheet_name") or "Sheet1",
            sheet_b_name=source_b_meta.get("sheet_name") or "Sheet1",
            excel_report_url=f"/api/v1/reconciliation/results/{session.id}/difference-report",
            difference_summary=summary.model_dump(),
        )

    @staticmethod
    def get_excel_difference_report(db: Session, session_id: int, user_id: Optional[int] = None) -> bytes:
        session_resp = ReconciliationService.get_session(db, session_id, user_id=user_id)
        from app.modules.reconciliation.report import generate_difference_excel_report
        return generate_difference_excel_report(
            session=session_resp,
            file_a_name=session_resp.file_a_name or session_resp.bank_statement_name,
            file_b_name=session_resp.file_b_name or session_resp.ledger_file_name,
            sheet_a_name=session_resp.sheet_a_name,
            sheet_b_name=session_resp.sheet_b_name,
        )

    @staticmethod
    def update_item_review_status(
        db: Session,
        session_id: int,
        item_id: str,
        review_status: str,
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        session = db.query(ReconciliationSession).filter(ReconciliationSession.id == session_id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Reconciliation session not found")
        if user_id is not None and session.user_id is not None and session.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied. You do not own this session.")

        data = json.loads(session.details_json)
        updated = False
        for t in data.get("transactions", []):
            if t.get("id") == item_id:
                t["review_status"] = review_status
                updated = True
                break

        if not updated:
            raise HTTPException(status_code=404, detail=f"Difference item '{item_id}' not found in session")

        session.details_json = json.dumps(data)
        db.commit()
        return {"session_id": session_id, "item_id": item_id, "review_status": review_status}

    @staticmethod
    def get_csv_report(db: Session, session_id: int, user_id: Optional[int] = None) -> str:
        session_resp = ReconciliationService.get_session(db, session_id, user_id=user_id)
        return generate_reconciliation_csv_report(
            bank_name=session_resp.bank_statement_name,
            ledger_name=session_resp.ledger_file_name,
            summary=session_resp.summary,
            items=session_resp.transactions,
        )

    @staticmethod
    def list_sessions(db: Session, limit: int = 20, user_id: Optional[int] = None) -> List[Dict[str, Any]]:
        query = db.query(ReconciliationSession)
        if user_id is not None:
            query = query.filter(ReconciliationSession.user_id == user_id)
        sessions = (
            query.order_by(ReconciliationSession.created_at.desc())
            .limit(limit)
            .all()
        )
        out = []
        for s in sessions:
            out.append({
                "id": s.id,
                "bank_statement_name": s.bank_statement_name,
                "ledger_file_name": s.ledger_file_name,
                "status": s.status,
                "matched_count": s.matched_count,
                "mismatched_count": s.mismatched_count,
                "total_bank_entries": s.total_bank_entries,
                "total_ledger_entries": s.total_ledger_entries,
                "created_at": s.created_at.isoformat(),
            })
        return out
