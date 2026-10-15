from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.reconciliation.schemas import WorkbookInspectionResult
from app.modules.reconciliation.workbook_inspector import WorkbookInspector
from app.schemas.document import DocumentResponse, DocumentResetResponse
from app.services.document_service import DocumentService

router = APIRouter()


@router.get("", response_model=List[DocumentResponse])
def list_documents(
    category: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists documents owned by the authenticated user with optional category filtering."""
    return DocumentService.list_documents(
        db, category=category, user_id=current_user.id, skip=skip, limit=limit
    )


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("general"),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Uploads and registers a document safely into storage for the authenticated user."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename must not be empty",
        )
    return await DocumentService.upload_document(
        db=db,
        file=file,
        category=category,
        notes=notes,
        user_id=current_user.id,
    )


@router.get("/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Downloads a document from the repository if owned by current user."""
    doc = DocumentService.get_document(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this document",
        )
    if not Path(doc.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document or file not found on disk",
        )
    return FileResponse(
        path=doc.file_path,
        filename=doc.original_filename,
        media_type=doc.mime_type or "application/octet-stream",
    )


@router.delete("/reset", response_model=DocumentResetResponse)
def reset_workspace_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently removes all uploaded documents and derived analysis records for the authenticated user."""
    return DocumentService.reset_workspace_documents(db=db, user_id=current_user.id)


@router.delete("/{document_id}")
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a document and its stored physical file if owned by current user."""
    doc = DocumentService.get_document(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this document",
        )
    DocumentService.delete_document(db, document_id, user_id=current_user.id)
    return {"message": "Document deleted successfully", "id": document_id}


@router.get("/{document_id}/analysis", response_model=WorkbookInspectionResult)
def get_document_analysis(
    document_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deeply inspects and returns classification, financial tables, period, and findings for a document."""
    doc = DocumentService.get_document(db, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    if doc.user_id is not None and doc.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this document analysis",
        )
    if not Path(doc.file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found on disk",
        )
    return WorkbookInspector.inspect(doc.file_path, doc.original_filename)


