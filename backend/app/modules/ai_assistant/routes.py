import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.assistant import AssistantConversation
from app.models.user import User
from app.modules.ai_assistant.assistant_service import AssistantService
from app.modules.ai_assistant.schemas import (
    AnalyzeRequest,
    AssistantIntentEnum,
    ChatRequest,
    ChatResponse,
    CompareRequest,
    CorrectionProposalInfo,
    CorrectionReviewDecisionRequest,
    FileContextInfo,
    GenerateCorrectedCopyRequest,
)

from app.services.document_service import DocumentService
from app.services.history_service import HistoryService

router = APIRouter()


import logging
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=ChatResponse)
async def assistant_chat_endpoint(
    req: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Processes conversational questions (both text-only accounting concepts and file-aware queries)."""
    try:
        return await AssistantService.process_chat(db=db, req=req, user_id=current_user.id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in assistant_chat_endpoint: %s", e)
        # Never expose raw python tracebacks or internal DB errors to user
        return ChatResponse(
            conversation_id=req.conversation_id or str(uuid.uuid4()),
            message="I couldn't reliably interpret this request. Please verify the uploaded file structure or rephrase your accounting question.",
            intent=AssistantIntentEnum.UNKNOWN,
            files=[],
            recommended_actions=["Review the uploaded document sheet and columns."],
        )



@router.post("/upload", response_model=FileContextInfo)
async def assistant_upload_endpoint(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Form(None),
    category: str = Form("financial"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Uploads a workbook or financial statement (XLSX, XLS, CSV, PDF), inspects it via
    the existing inspection pipeline, and registers it with the active conversation.
    """
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")

    # Upload via DocumentService (immutable original storage + checksum)
    doc = await DocumentService.upload_document(
        db=db,
        file=file,
        category=category,
        notes="Attached for Finance AI Assistant conversation",
        user_id=current_user.id,
    )

    # Build structured file context
    file_info = AssistantService._build_file_context_info(doc)

    # If conversation_id is provided, attach to active conversation state
    if conversation_id:
        AssistantService.attach_file_to_conversation(
            db=db,
            conversation_id=conversation_id,
            document_id=doc.id,
            file_info=file_info,
            user_id=current_user.id,
        )

    # Record history
    HistoryService.record_activity(
        db=db,
        user_id=current_user.id,
        module="ai_assistant",
        action="file_attached",
        target_name=doc.original_filename,
        status="completed",
        result_summary=f"Attached {doc.original_filename} ({file_info.document_type}) to assistant",
        user_action="Upload file to assistant",
        document_id=doc.id,
    )

    return file_info


@router.post("/analyze", response_model=ChatResponse)
async def assistant_analyze_endpoint(
    req: AnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Runs targeted file-aware variance and anomaly analysis on an attached document."""
    chat_req = ChatRequest(
        message=req.prompt or "Find any mismatch or discrepancy in this file.",
        conversation_id=req.conversation_id,
        file_ids=[req.document_id],
    )
    return await AssistantService.process_chat(db=db, req=chat_req, user_id=current_user.id)


@router.post("/compare", response_model=ChatResponse)
async def assistant_compare_endpoint(
    req: CompareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executes deterministic reconciliation comparing two uploaded files."""
    chat_req = ChatRequest(
        message=req.prompt or "Compare these two files and find missing transactions and variances.",
        conversation_id=req.conversation_id,
        file_ids=[req.file_a_id, req.file_b_id],
    )
    return await AssistantService.process_chat(db=db, req=chat_req, user_id=current_user.id)


@router.get("/conversation/{conversation_id}")
def get_conversation_endpoint(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves conversation context, attached file metadata, and last detected discrepancy."""
    conv = db.query(AssistantConversation).filter(AssistantConversation.id == conversation_id).first()
    if conv and conv.user_id is not None and conv.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. You do not own this conversation.",
        )
    ctx = AssistantService.get_conversation_context(db=db, conversation_id=conversation_id)
    return {
        "conversation_id": conversation_id,
        "file_ids": ctx.get("file_ids", []),
        "files": ctx.get("files", []),
        "messages": ctx.get("messages", []),
        "files_meta": ctx.get("files_meta", {}),
        "has_discrepancy": ctx.get("last_discrepancy") is not None,
        "last_discrepancy": ctx.get("last_discrepancy"),
        "last_proposal": ctx.get("last_proposal"),
    }


@router.post("/corrections/{correction_id}/decision", response_model=CorrectionProposalInfo)
def update_assistant_correction_decision(
    correction_id: str,
    req: CorrectionReviewDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accountant approval routing: confirms or rejects a proposed correction."""
    try:
        updated = AssistantService.record_correction_decision(
            db=db,
            correction_id=correction_id,
            decision=req.decision,
            notes=req.notes,
            user_id=current_user.id,
        )
        return CorrectionProposalInfo(**updated)
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))


@router.post("/generate-corrected-file")
def generate_corrected_file_endpoint(
    req: GenerateCorrectedCopyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a non-destructive timestamped Excel copy of the file with the approved correction
    and appends an 'AI Correction Log' worksheet. Original file remains completely unchanged.
    """
    try:
        return AssistantService.generate_corrected_copy_from_proposal(
            db=db,
            correction_id=req.correction_id,
            accountant_name=req.accountant_name,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

