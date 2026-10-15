from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, UploadFile, File, Response, status, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.core.auth import get_current_user
from app.modules.financial_statements.models import (
    FinancialStatementProfile,
    TrialBalanceEntry,
    BalanceSheetLine,
    ProfitLossLine,
    CashFlowLine,
    FinancialStatementSnapshot,
    FinancialStatementFinding,
)
from app.modules.financial_statements.schemas import (
    FSProfileCreate,
    FSProfileUpdate,
    FSProfileResponse,
    TrialBalanceEntryCreate,
    TrialBalanceEntryResponse,
    BalanceSheetLineCreate,
    BalanceSheetLineResponse,
    ProfitLossLineCreate,
    ProfitLossLineResponse,
    CashFlowLineCreate,
    CashFlowLineResponse,
    FSOverviewResponse,
    FSFindingResponse,
    FSFindingDecisionRequest,
    FSStatusTransitionRequest,
    FSSnapshotResponse,
)
from app.modules.financial_statements.service import FSService

router = APIRouter()


# -------------------------------------------------------------
# Profile Endpoints
# -------------------------------------------------------------

@router.get("/profiles", response_model=List[FSProfileResponse])
def get_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profiles = FSService.list_profiles(db=db, user_id=current_user.id)
    results = []
    for p in profiles:
        tb_count = db.query(TrialBalanceEntry).filter(TrialBalanceEntry.profile_id == p.id).count()
        bs_count = db.query(BalanceSheetLine).filter(BalanceSheetLine.profile_id == p.id).count()
        pl_count = db.query(ProfitLossLine).filter(ProfitLossLine.profile_id == p.id).count()
        cf_count = db.query(CashFlowLine).filter(CashFlowLine.profile_id == p.id).count()
        find_count = db.query(FinancialStatementFinding).filter(FinancialStatementFinding.profile_id == p.id).count()

        results.append(
            FSProfileResponse(
                id=p.id,
                user_id=p.user_id,
                entity_name=p.entity_name,
                cin_or_pan=p.cin_or_pan,
                financial_year=p.financial_year,
                reporting_period=p.reporting_period,
                framework=p.framework,
                status=p.status,
                approved_at=p.approved_at,
                approved_by_user_id=p.approved_by_user_id,
                approval_notes=p.approval_notes,
                created_at=p.created_at,
                tb_entries_count=tb_count,
                bs_lines_count=bs_count,
                pl_lines_count=pl_count,
                cf_lines_count=cf_count,
                findings_count=find_count,
            )
        )
    return results


@router.post("/profiles", response_model=FSProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    profile_in: FSProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = FSService.get_or_create_profile(db=db, user_id=current_user.id, profile_in=profile_in)
    return FSProfileResponse(
        id=p.id,
        user_id=p.user_id,
        entity_name=p.entity_name,
        cin_or_pan=p.cin_or_pan,
        financial_year=p.financial_year,
        reporting_period=p.reporting_period,
        framework=p.framework,
        status=p.status,
        approved_at=p.approved_at,
        approved_by_user_id=p.approved_by_user_id,
        approval_notes=p.approval_notes,
        created_at=p.created_at,
        tb_entries_count=0,
        bs_lines_count=0,
        pl_lines_count=0,
        cf_lines_count=0,
        findings_count=0,
    )


@router.get("/profiles/{profile_id}", response_model=FSProfileResponse)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    tb_count = db.query(TrialBalanceEntry).filter(TrialBalanceEntry.profile_id == p.id).count()
    bs_count = db.query(BalanceSheetLine).filter(BalanceSheetLine.profile_id == p.id).count()
    pl_count = db.query(ProfitLossLine).filter(ProfitLossLine.profile_id == p.id).count()
    cf_count = db.query(CashFlowLine).filter(CashFlowLine.profile_id == p.id).count()
    find_count = db.query(FinancialStatementFinding).filter(FinancialStatementFinding.profile_id == p.id).count()

    return FSProfileResponse(
        id=p.id,
        user_id=p.user_id,
        entity_name=p.entity_name,
        cin_or_pan=p.cin_or_pan,
        financial_year=p.financial_year,
        reporting_period=p.reporting_period,
        framework=p.framework,
        status=p.status,
        approved_at=p.approved_at,
        approved_by_user_id=p.approved_by_user_id,
        approval_notes=p.approval_notes,
        created_at=p.created_at,
        tb_entries_count=tb_count,
        bs_lines_count=bs_count,
        pl_lines_count=pl_count,
        cf_lines_count=cf_count,
        findings_count=find_count,
    )


@router.patch("/profiles/{profile_id}", response_model=FSProfileResponse)
def update_profile(
    profile_id: int,
    update_in: FSProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = FSService.update_profile(db=db, user_id=current_user.id, profile_id=profile_id, update_in=update_in)
    return get_profile(profile_id=p.id, db=db, current_user=current_user)


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    FSService.delete_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------
# Overview Dashboard Metrics
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/overview", response_model=FSOverviewResponse)
def get_overview(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.get_overview(db=db, user_id=current_user.id, profile_id=profile_id)


# -------------------------------------------------------------
# Document Upload & Ingestion
# -------------------------------------------------------------

@router.post("/profiles/{profile_id}/upload")
async def upload_document(
    profile_id: int,
    file: UploadFile = File(...),
    sheet_type: str = "TRIAL_BALANCE",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    contents = await file.read()
    res = FSService.parse_and_ingest_file(
        db=db,
        user_id=current_user.id,
        profile_id=profile_id,
        filename=file.filename or "upload.csv",
        file_bytes=contents,
        sheet_type=sheet_type,
    )
    return res


# -------------------------------------------------------------
# Trial Balance
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/trial-balance", response_model=List[TrialBalanceEntryResponse])
def get_trial_balance(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return profile.trial_balance_entries


@router.post("/profiles/{profile_id}/trial-balance", response_model=List[TrialBalanceEntryResponse])
def add_trial_balance(
    profile_id: int,
    entries: List[TrialBalanceEntryCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.add_trial_balance_entries(
        db=db, user_id=current_user.id, profile_id=profile_id, entries=entries
    )


# -------------------------------------------------------------
# Balance Sheet
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/balance-sheet", response_model=List[BalanceSheetLineResponse])
def get_balance_sheet(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return profile.balance_sheet_lines


@router.post("/profiles/{profile_id}/balance-sheet", response_model=List[BalanceSheetLineResponse])
def add_balance_sheet(
    profile_id: int,
    lines: List[BalanceSheetLineCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.add_balance_sheet_lines(
        db=db, user_id=current_user.id, profile_id=profile_id, lines=lines
    )


# -------------------------------------------------------------
# Profit & Loss
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/profit-loss", response_model=List[ProfitLossLineResponse])
def get_profit_loss(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return profile.profit_loss_lines


@router.post("/profiles/{profile_id}/profit-loss", response_model=List[ProfitLossLineResponse])
def add_profit_loss(
    profile_id: int,
    lines: List[ProfitLossLineCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.add_profit_loss_lines(
        db=db, user_id=current_user.id, profile_id=profile_id, lines=lines
    )


# -------------------------------------------------------------
# Cash Flow
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/cash-flow", response_model=List[CashFlowLineResponse])
def get_cash_flow(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return profile.cash_flow_lines


@router.post("/profiles/{profile_id}/cash-flow", response_model=List[CashFlowLineResponse])
def add_cash_flow(
    profile_id: int,
    lines: List[CashFlowLineCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.add_cash_flow_lines(
        db=db, user_id=current_user.id, profile_id=profile_id, lines=lines
    )


# -------------------------------------------------------------
# Auto-Classification
# -------------------------------------------------------------

@router.post("/profiles/{profile_id}/auto-classify")
def auto_classify(
    profile_id: int,
    overwrite: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.auto_classify_from_trial_balance(
        db=db, user_id=current_user.id, profile_id=profile_id, overwrite=overwrite
    )


# -------------------------------------------------------------
# Calculate & Immutable Snapshot
# -------------------------------------------------------------

@router.post("/profiles/{profile_id}/calculate")
def calculate_and_snapshot(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.calculate_and_snapshot(
        db=db, user_id=current_user.id, profile_id=profile_id
    )


# -------------------------------------------------------------
# Snapshots List
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/snapshots", response_model=List[FSSnapshotResponse])
def list_snapshots(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return (
        db.query(FinancialStatementSnapshot)
        .filter(FinancialStatementSnapshot.profile_id == profile.id)
        .order_by(FinancialStatementSnapshot.version.desc())
        .all()
    )


# -------------------------------------------------------------
# Findings & Review Center Decisions
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/findings", response_model=List[FSFindingResponse])
def get_findings(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    return profile.findings


@router.post("/findings/{finding_id}/decision", response_model=FSFindingResponse)
def record_finding_decision(
    finding_id: int,
    req: FSFindingDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return FSService.apply_finding_decision(
        db=db,
        user_id=current_user.id,
        finding_id=finding_id,
        decision=req.decision,
        notes=req.notes,
    )


# -------------------------------------------------------------
# Status Transition with Approval Safety
# -------------------------------------------------------------

@router.post("/profiles/{profile_id}/status", response_model=FSProfileResponse)
def update_status(
    profile_id: int,
    req: FSStatusTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    FSService.transition_status(
        db=db,
        user_id=current_user.id,
        profile_id=profile_id,
        target_status=req.target_status,
        notes=req.notes,
    )
    return get_profile(profile_id=profile_id, db=db, current_user=current_user)


# -------------------------------------------------------------
# Export Accountant Preparation Report
# -------------------------------------------------------------

@router.get("/profiles/{profile_id}/export")
def export_report(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    csv_text = FSService.generate_export_report_csv(
        db=db, user_id=current_user.id, profile_id=profile_id
    )
    profile = FSService.get_profile(db=db, user_id=current_user.id, profile_id=profile_id)
    safe_name = profile.entity_name.replace(" ", "_")
    filename = f"Financial_Statements_{safe_name}_{profile.financial_year}.csv"

    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
