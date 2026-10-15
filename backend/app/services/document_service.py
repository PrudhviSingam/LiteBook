import hashlib
import logging
import re
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document import Document
from app.models.history import HistoryRecord

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".pdf"}
DANGEROUS_EXTENSIONS = {".exe", ".bat", ".cmd", ".sh", ".js", ".py", ".msi", ".dll", ".vbs", ".com", ".scr"}
MAX_FILE_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class DocumentService:
    @staticmethod
    def _compute_sha256(file_path: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    @classmethod
    async def upload_document(
        cls,
        db: Session,
        file: UploadFile,
        category: str = "general",
        notes: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> Document:
        raw_filename = file.filename or "uploaded_file"

        # 1. Path Traversal & Sanitize Filename
        # Extract purely the basename to prevent path traversal like ../../etc/passwd
        sanitized_filename = Path(raw_filename).name.strip()
        # Clean any remaining control chars
        sanitized_filename = re.sub(r'[\r\n\t\x00]', '', sanitized_filename)
        if not sanitized_filename or sanitized_filename in (".", ".."):
            sanitized_filename = f"file_{uuid.uuid4().hex[:8]}.xlsx"

        file_ext = Path(sanitized_filename).suffix.lower()

        # 2. Extension Validation
        if file_ext in DANGEROUS_EXTENSIONS or file_ext not in ALLOWED_EXTENSIONS:
            logger.warning("Rejected upload attempt for dangerous/unsupported file extension: %s", sanitized_filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{file_ext}'. Allowed formats for financial documents: XLSX, XLS, CSV, PDF.",
            )

        upload_dir = settings.uploads_dir
        safe_stored_name = f"{uuid.uuid4().hex}{file_ext}"
        destination = upload_dir / safe_stored_name

        # 3. Stream & Validate File Size
        file_size = 0
        chunk_size = 64 * 1024  # 64 KB chunks
        header_sample = bytearray()

        try:
            with destination.open("wb") as buffer:
                while True:
                    chunk = await file.read(chunk_size)
                    if not chunk:
                        break
                    if len(header_sample) < 512:
                        header_sample.extend(chunk[:512 - len(header_sample)])
                    file_size += len(chunk)
                    if file_size > MAX_FILE_BYTES:
                        # Clean up and abort
                        buffer.close()
                        if destination.exists():
                            destination.unlink()
                        raise HTTPException(
                            status_code=getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
                        detail=f"File size exceeds the maximum limit of {settings.MAX_UPLOAD_SIZE_MB} MB.",

                        )
                    buffer.write(chunk)
        except HTTPException:
            raise
        except Exception as e:
            if destination.exists():
                destination.unlink()
            logger.error("Failed to save uploaded file: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file.",
            )
        finally:
            await file.seek(0)

        # 4. Empty File Check
        if file_size == 0:
            if destination.exists():
                destination.unlink()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded file is empty (0 bytes). Please upload a valid financial document.",
            )

        # 5. Content Signature / Magic Byte Inspection
        # Reject executable / script magic bytes
        if header_sample.startswith(b"MZ") or header_sample.startswith(b"\x7fELF") or header_sample.startswith(b"#!"):
            if destination.exists():
                destination.unlink()
            logger.warning("Rejected file disguised as document: header signature detected for %s", sanitized_filename)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File content signature does not match allowed financial document formats.",
            )

        # 5. Compute SHA-256 Checksum
        checksum = cls._compute_sha256(destination)

        # 6. Create Document record scoped to user
        doc = Document(
            user_id=user_id,
            original_filename=sanitized_filename,
            stored_filename=safe_stored_name,
            file_path=str(destination),
            file_size=file_size,
            mime_type=file.content_type or "application/octet-stream",
            category=category,
            status="ready",
            checksum=checksum,
            original_sha256=checksum,
            is_corrected_copy=False,
            notes=notes,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 7. Audit History Entry
        history_entry = HistoryRecord(
            user_id=user_id,
            module="documents",
            action="document_uploaded",
            target_name=doc.original_filename,
            status="completed",
            result_summary=f"Uploaded {doc.original_filename} ({round(file_size / 1024, 1)} KB, SHA-256: {checksum[:12]}...)",
            user_action="Uploaded by user",
            document_id=doc.id,
        )
        db.add(history_entry)
        db.commit()

        return doc

    @staticmethod
    def list_documents(
        db: Session,
        category: Optional[str] = None,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Document]:
        query = db.query(Document)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        if category and category != "all":
            query = query.filter(Document.category == category)
        return query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def get_document(
        db: Session,
        document_id: int,
        user_id: Optional[int] = None,
    ) -> Optional[Document]:
        query = db.query(Document).filter(Document.id == document_id)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        return query.first()

    @staticmethod
    def delete_document(
        db: Session,
        document_id: int,
        user_id: Optional[int] = None,
    ) -> bool:
        query = db.query(Document).filter(Document.id == document_id)
        if user_id is not None:
            query = query.filter(Document.user_id == user_id)
        doc = query.first()
        if not doc:
            return False

        # Remove local file if exists
        try:
            local_file = Path(doc.file_path)
            if local_file.exists():
                local_file.unlink()
        except Exception as e:
            logger.error("Error unlinking file on delete: %s", e)

        db.delete(doc)
        db.commit()
        return True

    @classmethod
    def reset_workspace_documents(
        cls,
        db: Session,
        user_id: int,
    ) -> dict:
        """Permanently and transactionally resets all document-derived data for the given user:
        - Uploaded documents
        - Document file records
        - Reconciliation sessions/results derived from those documents
        - AI file contexts derived from those documents
        - Document-related correction proposals
        - Document-specific history / review records
        - Physical storage files belonging to deleted documents
        - Clears in-memory inspection cache
        - Emits an audit log HistoryRecord with action 'GLOBAL_DOCUMENT_RESET'
        """
        from app.models.assistant import AssistantFileContext
        from app.models.reconciliation import CorrectionProposal, ReconciliationSession
        from app.services.review_center_service import _INSPECTION_CACHE

        try:
            # 1. User documents
            user_docs = db.query(Document).filter(Document.user_id == user_id).all()
            doc_ids = [d.id for d in user_docs]
            file_paths = [Path(d.file_path) for d in user_docs if d.file_path]

            derived_count = 0

            # 2. Correction proposals
            if doc_ids:
                proposals = db.query(CorrectionProposal).filter(
                    or_(CorrectionProposal.user_id == user_id, CorrectionProposal.document_id.in_(doc_ids))
                ).all()
            else:
                proposals = db.query(CorrectionProposal).filter(CorrectionProposal.user_id == user_id).all()
            derived_count += len(proposals)
            for p in proposals:
                db.delete(p)

            # 3. Assistant file contexts
            if doc_ids:
                file_contexts = db.query(AssistantFileContext).filter(
                    AssistantFileContext.document_id.in_(doc_ids)
                ).all()
                derived_count += len(file_contexts)
                for fc in file_contexts:
                    db.delete(fc)

            # 4. Reconciliation sessions
            if doc_ids:
                sessions = db.query(ReconciliationSession).filter(
                    or_(
                        ReconciliationSession.user_id == user_id,
                        ReconciliationSession.bank_document_id.in_(doc_ids),
                        ReconciliationSession.ledger_document_id.in_(doc_ids),
                    )
                ).all()
            else:
                sessions = db.query(ReconciliationSession).filter(ReconciliationSession.user_id == user_id).all()
            derived_count += len(sessions)
            for s in sessions:
                db.delete(s)

            # 5. Document-derived history records
            if doc_ids:
                history_records = db.query(HistoryRecord).filter(
                    HistoryRecord.user_id == user_id,
                    or_(
                        HistoryRecord.document_id.in_(doc_ids),
                        HistoryRecord.module.in_(["documents", "reconciliation"]),
                    ),
                ).all()
            else:
                history_records = db.query(HistoryRecord).filter(
                    HistoryRecord.user_id == user_id,
                    HistoryRecord.module.in_(["documents", "reconciliation"]),
                ).all()
            derived_count += len(history_records)
            for h in history_records:
                db.delete(h)

            # 6. Delete documents
            doc_count = len(user_docs)
            for d in user_docs:
                db.delete(d)

            # 7. Pre-calculate storage files that exist
            files_to_unlink = [fp for fp in file_paths if fp.exists()]
            files_deleted_count = len(files_to_unlink)

            # 8. Create official audit log entry
            audit_entry = HistoryRecord(
                user_id=user_id,
                module="documents",
                action="GLOBAL_DOCUMENT_RESET",
                target_name="Workspace Documents",
                status="completed",
                result_summary=(
                    f"Reset workspace: deleted {doc_count} documents, "
                    f"{derived_count} derived records, and {files_deleted_count} storage files."
                ),
                user_action="User triggered global document reset",
                document_id=None,
            )
            db.add(audit_entry)

            # 9. Atomically commit database changes
            db.commit()

            # 10. Safely remove physical files from storage after successful commit
            for fp in files_to_unlink:
                try:
                    if fp.exists():
                        fp.unlink()
                except Exception as ex:
                    logger.warning("Could not unlink physical file %s: %s", fp, ex)

            # 11. Evict deleted document keys from in-memory inspection cache
            for did in doc_ids:
                keys_to_remove = [k for k in _INSPECTION_CACHE if k.startswith(f"{did}_")]
                for k in keys_to_remove:
                    _INSPECTION_CACHE.pop(k, None)

            logger.info(
                "Global document reset completed for user %s: %s docs, %s derived, %s files.",
                user_id, doc_count, derived_count, files_deleted_count
            )

            return {
                "success": True,
                "documents_deleted": doc_count,
                "derived_records_deleted": derived_count,
                "files_deleted": files_deleted_count,
            }

        except Exception as e:
            db.rollback()
            logger.exception("Global document reset failed for user %s: %s", user_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to reset workspace documents: {str(e)}",
            )

