from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.modules.reconciliation.correction_service import CorrectionService
from app.modules.reconciliation.explanation import DiscrepancyExplanationEngine
from app.modules.reconciliation.schemas import (
    ColumnMappingPreview,
    CorrectionDecisionRequest,
    CorrectionProposalSchema,
    DiscrepancyExplainRequest,
    DiscrepancyExplanationResponse,
    GenerateCorrectedWorkbookResponse,
    ReconciliationRuleConfig,
    ReconciliationSessionResponse,
    WorkbookInspectionResult,
)
from app.modules.reconciliation.services import ReconciliationService
from app.modules.reconciliation.workbook_inspector import WorkbookInspector

router = APIRouter()


@router.post("/preview-file", response_model=ColumnMappingPreview)
async def preview_file_endpoint(
    file: UploadFile = File(...),
    sheet_name: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Parses a CSV or Excel file and returns detected column mappings, row count, and sample rows."""
    return await ReconciliationService.preview_uploaded_file(file, sheet_name=sheet_name)


@router.post("/inspect-workbook", response_model=WorkbookInspectionResult)
async def inspect_workbook_endpoint(
    file: UploadFile = File(...),
    upload_category: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
):
    """Deeply inspects multi-sheet workbooks (e.g. ZION LIFTS LLP), detecting title blocks,
    merged cells, period columns, and classifies sheets deterministically into Balance Sheet,
    P&L, Ledger, Bank Statement, etc.
    """
    content = await file.read()
    await file.seek(0)
    return WorkbookInspector.inspect(
        file_bytes_or_path=content,
        filename=file.filename or "workbook.xlsx",
        upload_category=upload_category,
    )


@router.post("/explain-discrepancy", response_model=DiscrepancyExplanationResponse)
async def explain_discrepancy_endpoint(
    req: DiscrepancyExplainRequest,
    current_user: User = Depends(get_current_user),
):
    """Generates structured 8-point discrepancy explanation answering WHAT, WHERE, original/expected values,
    WHY, evidence, and verification recommendations using cautious accounting language.
    """
    return await DiscrepancyExplanationEngine.explain(
        discrepancy_data=req.discrepancy_data,
        comparison_records=req.comparison_records,
        document_metadata=req.document_metadata,
    )


@router.get("/sessions/{session_id}/corrections", response_model=List[CorrectionProposalSchema])
def list_session_corrections_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists correction proposals for a reconciliation session."""
    return CorrectionService.list_or_create_proposals_for_session(db, session_id, user_id=current_user.id)


@router.post("/corrections/{correction_id}/decision", response_model=CorrectionProposalSchema)
def update_correction_decision_endpoint(
    correction_id: str,
    req: CorrectionDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates accountant decision (CONFIRMED, REJECTED, MANUAL_REVIEW) on a correction proposal."""
    proposal = CorrectionService.update_proposal_decision(db, correction_id, req, user_id=current_user.id)
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Correction proposal '{correction_id}' not found",
        )
    return proposal


@router.post("/sessions/{session_id}/generate-corrected-workbook", response_model=GenerateCorrectedWorkbookResponse)
def generate_corrected_workbook_endpoint(
    session_id: int,
    accountant_name: str = Form("Partner Accountant"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates a non-destructive timestamped Excel copy of the workbook applying approved
    corrections and appending the 'AI Correction Log' worksheet.
    """
    try:
        return CorrectionService.generate_corrected_workbook(
            db=db,
            session_id=session_id,
            accountant_name=accountant_name,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/run", response_model=ReconciliationSessionResponse, status_code=status.HTTP_201_CREATED)
async def run_reconciliation_endpoint(
    bank_file: Optional[UploadFile] = File(None),
    ledger_file: Optional[UploadFile] = File(None),
    bank_document_id: Optional[int] = Form(None),
    ledger_document_id: Optional[int] = Form(None),
    bank_sheet_name: Optional[str] = Form(None),
    ledger_sheet_name: Optional[str] = Form(None),
    file_a: Optional[UploadFile] = File(None),
    file_b: Optional[UploadFile] = File(None),
    file_a_document_id: Optional[int] = Form(None),
    file_b_document_id: Optional[int] = Form(None),
    sheet_a: Optional[str] = Form(None),
    sheet_b: Optional[str] = Form(None),
    mapping_a: Optional[str] = Form(None),
    mapping_b: Optional[str] = Form(None),
    date_tolerance_days: int = Form(1),
    amount_tolerance: float = Form(0.0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Executes deterministic difference detection between two financial files or sheets."""
    import json
    parsed_mapping_a = None
    if mapping_a:
        try:
            parsed_mapping_a = json.loads(mapping_a)
        except Exception:
            pass

    parsed_mapping_b = None
    if mapping_b:
        try:
            parsed_mapping_b = json.loads(mapping_b)
        except Exception:
            pass

    rules = ReconciliationRuleConfig(
        date_tolerance_days=date_tolerance_days,
        amount_tolerance=amount_tolerance,
    )
    return await ReconciliationService.run_reconciliation(
        db=db,
        bank_file=bank_file,
        ledger_file=ledger_file,
        bank_document_id=bank_document_id,
        ledger_document_id=ledger_document_id,
        bank_sheet_name=bank_sheet_name,
        ledger_sheet_name=ledger_sheet_name,
        file_a=file_a,
        file_b=file_b,
        file_a_document_id=file_a_document_id,
        file_b_document_id=file_b_document_id,
        sheet_a=sheet_a,
        sheet_b=sheet_b,
        mapping_a=parsed_mapping_a,
        mapping_b=parsed_mapping_b,
        rules=rules,
        user_id=current_user.id,
    )


@router.get("/sessions", response_model=List[Dict[str, Any]])
def list_sessions_endpoint(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists past reconciliation audit sessions."""
    return ReconciliationService.list_sessions(db, limit=limit, user_id=current_user.id)


@router.get("/results/{session_id}", response_model=ReconciliationSessionResponse)
def get_session_results_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves full reconciliation summary, transactions, and AI explanations for a session."""
    return ReconciliationService.get_session(db, session_id, user_id=current_user.id)


@router.get("/results/{session_id}/report")
def download_csv_report_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and downloads a structured audit CSV reconciliation report."""
    csv_content = ReconciliationService.get_csv_report(db, session_id, user_id=current_user.id)
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=Reconciliation_Report_Session_{session_id}.csv",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/results/{session_id}/difference-report")
def download_difference_excel_report_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generates and downloads a separate Excel Difference Report (Difference_Report_<timestamp>.xlsx)."""
    from datetime import datetime, timezone
    excel_bytes = ReconciliationService.get_excel_difference_report(db, session_id, user_id=current_user.id)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"Difference_Report_{timestamp}.xlsx"
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )


@router.post("/results/{session_id}/items/{item_id}/review")
def update_item_review_endpoint(
    session_id: int,
    item_id: str,
    status_update: Dict[str, str],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates review status of an individual discrepancy or difference item."""
    new_status = status_update.get("status")
    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'status' in request body",
        )
    return ReconciliationService.update_item_review_status(
        db=db,
        session_id=session_id,
        item_id=item_id,
        review_status=new_status,
        user_id=current_user.id,
    )



