from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.core.auth import get_current_user
from app.modules.itr.models import (
    ITRProfile,
    ITRIncomeEntry,
    ITRDeductionEntry,
    ITRTaxCreditEntry,
)
from app.modules.itr.schemas import (
    ITRProfileCreate,
    ITRProfileUpdate,
    ITRProfileResponse,
    ITRIncomeEntryCreate,
    ITRIncomeEntryResponse,
    ITRDeductionEntryCreate,
    ITRDeductionEntryUpdate,
    ITRDeductionEntryResponse,
    ITRTaxCreditEntryCreate,
    ITRTaxCreditEntryResponse,
    ITRRegimeComparisonResponse,
    ITRFindingResponse,
    ITRFindingDecisionRequest,
    ITRStatusTransitionRequest,
)
from app.modules.itr.service import ITRService

router = APIRouter()


@router.get("/profiles", response_model=List[ITRProfileResponse])
def get_profiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profiles = ITRService.get_profiles(db=db, user=current_user)
    res = []
    for p in profiles:
        income_cnt = db.query(ITRIncomeEntry).filter(ITRIncomeEntry.profile_id == p.id).count()
        ded_cnt = db.query(ITRDeductionEntry).filter(ITRDeductionEntry.profile_id == p.id).count()
        cred_cnt = db.query(ITRTaxCreditEntry).filter(ITRTaxCreditEntry.profile_id == p.id).count()
        find_cnt = len(p.findings) if p.findings else 0
        resp_obj = ITRProfileResponse(
            id=p.id,
            user_id=p.user_id,
            pan=p.pan,
            taxpayer_name=p.taxpayer_name,
            taxpayer_category=p.taxpayer_category,
            assessment_year=p.assessment_year,
            financial_year=p.financial_year,
            selected_regime=p.selected_regime,
            status=p.status,
            approved_at=p.approved_at,
            approved_by_user_id=p.approved_by_user_id,
            approval_notes=p.approval_notes,
            created_at=p.created_at,
            income_count=income_cnt,
            deduction_count=ded_cnt,
            tax_credit_count=cred_cnt,
            findings_count=find_cnt,
        )
        res.append(resp_obj)
    return res


@router.post("/profiles", response_model=ITRProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    payload: ITRProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = ITRService.create_profile(db=db, user=current_user, data=payload)
    return ITRProfileResponse(
        id=p.id,
        user_id=p.user_id,
        pan=p.pan,
        taxpayer_name=p.taxpayer_name,
        taxpayer_category=p.taxpayer_category,
        assessment_year=p.assessment_year,
        financial_year=p.financial_year,
        selected_regime=p.selected_regime,
        status=p.status,
        created_at=p.created_at,
    )


@router.get("/profiles/{profile_id}", response_model=ITRProfileResponse)
def get_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = ITRService.get_scoped_profile(db=db, user=current_user, profile_id=profile_id)
    income_cnt = db.query(ITRIncomeEntry).filter(ITRIncomeEntry.profile_id == p.id).count()
    ded_cnt = db.query(ITRDeductionEntry).filter(ITRDeductionEntry.profile_id == p.id).count()
    cred_cnt = db.query(ITRTaxCreditEntry).filter(ITRTaxCreditEntry.profile_id == p.id).count()
    find_cnt = len(p.findings) if p.findings else 0
    return ITRProfileResponse(
        id=p.id,
        user_id=p.user_id,
        pan=p.pan,
        taxpayer_name=p.taxpayer_name,
        taxpayer_category=p.taxpayer_category,
        assessment_year=p.assessment_year,
        financial_year=p.financial_year,
        selected_regime=p.selected_regime,
        status=p.status,
        approved_at=p.approved_at,
        approved_by_user_id=p.approved_by_user_id,
        approval_notes=p.approval_notes,
        created_at=p.created_at,
        income_count=income_cnt,
        deduction_count=ded_cnt,
        tax_credit_count=cred_cnt,
        findings_count=find_cnt,
    )


@router.put("/profiles/{profile_id}", response_model=ITRProfileResponse)
def update_profile(
    profile_id: int,
    payload: ITRProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = ITRService.update_profile(db=db, user=current_user, profile_id=profile_id, data=payload)
    return ITRProfileResponse(
        id=p.id,
        user_id=p.user_id,
        pan=p.pan,
        taxpayer_name=p.taxpayer_name,
        taxpayer_category=p.taxpayer_category,
        assessment_year=p.assessment_year,
        financial_year=p.financial_year,
        selected_regime=p.selected_regime,
        status=p.status,
        approved_at=p.approved_at,
        approved_by_user_id=p.approved_by_user_id,
        approval_notes=p.approval_notes,
        created_at=p.created_at,
    )


@router.get("/profiles/{profile_id}/incomes", response_model=List[ITRIncomeEntryResponse])
def get_incomes(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = ITRService.get_scoped_profile(db, current_user, profile_id)
    return (
        db.query(ITRIncomeEntry)
        .filter(ITRIncomeEntry.profile_id == profile.id)
        .order_by(ITRIncomeEntry.id.asc())
        .all()
    )


@router.post("/profiles/{profile_id}/incomes", response_model=ITRIncomeEntryResponse)
def add_income(
    profile_id: int,
    payload: ITRIncomeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.add_income_entry(db=db, user=current_user, profile_id=profile_id, data=payload)


@router.get("/profiles/{profile_id}/deductions", response_model=List[ITRDeductionEntryResponse])
def get_deductions(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = ITRService.get_scoped_profile(db, current_user, profile_id)
    return (
        db.query(ITRDeductionEntry)
        .filter(ITRDeductionEntry.profile_id == profile.id)
        .order_by(ITRDeductionEntry.id.asc())
        .all()
    )


@router.post("/profiles/{profile_id}/deductions", response_model=ITRDeductionEntryResponse)
def add_deduction(
    profile_id: int,
    payload: ITRDeductionEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.add_deduction_entry(db=db, user=current_user, profile_id=profile_id, data=payload)


@router.put("/profiles/{profile_id}/deductions/{deduction_id}", response_model=ITRDeductionEntryResponse)
def update_deduction(
    profile_id: int,
    deduction_id: int,
    payload: ITRDeductionEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.update_deduction_entry(
        db=db, user=current_user, profile_id=profile_id, entry_id=deduction_id, data=payload
    )


@router.get("/profiles/{profile_id}/tax-credits", response_model=List[ITRTaxCreditEntryResponse])
def get_tax_credits(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = ITRService.get_scoped_profile(db, current_user, profile_id)
    return (
        db.query(ITRTaxCreditEntry)
        .filter(ITRTaxCreditEntry.profile_id == profile.id)
        .order_by(ITRTaxCreditEntry.id.asc())
        .all()
    )


@router.post("/profiles/{profile_id}/tax-credits", response_model=ITRTaxCreditEntryResponse)
def add_tax_credit(
    profile_id: int,
    payload: ITRTaxCreditEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.add_tax_credit_entry(db=db, user=current_user, profile_id=profile_id, data=payload)


@router.post("/profiles/{profile_id}/upload")
def upload_tax_document(
    profile_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.upload_tax_file(db=db, user=current_user, profile_id=profile_id, file=file)


@router.post("/profiles/{profile_id}/calculate", response_model=ITRRegimeComparisonResponse)
def calculate_itr(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.calculate_itr(db=db, user=current_user, profile_id=profile_id)


@router.get("/profiles/{profile_id}/regime-comparison", response_model=ITRRegimeComparisonResponse)
def get_regime_comparison(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ITRService.get_regime_comparison(db=db, user=current_user, profile_id=profile_id)


@router.post("/profiles/{profile_id}/status", response_model=ITRProfileResponse)
def transition_status(
    profile_id: int,
    payload: ITRStatusTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    p = ITRService.transition_status(
        db=db, user=current_user, profile_id=profile_id, target_status=payload.target_status, notes=payload.notes
    )
    return ITRProfileResponse(
        id=p.id,
        user_id=p.user_id,
        pan=p.pan,
        taxpayer_name=p.taxpayer_name,
        taxpayer_category=p.taxpayer_category,
        assessment_year=p.assessment_year,
        financial_year=p.financial_year,
        selected_regime=p.selected_regime,
        status=p.status,
        approved_at=p.approved_at,
        approved_by_user_id=p.approved_by_user_id,
        approval_notes=p.approval_notes,
        created_at=p.created_at,
    )


@router.get("/profiles/{profile_id}/findings", response_model=List[ITRFindingResponse])
def get_findings(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    findings = ITRService.get_findings(db=db, user=current_user, profile_id=profile_id)
    import json
    res = []
    for f in findings:
        res.append(
            ITRFindingResponse(
                id=f.id,
                profile_id=f.profile_id,
                finding_type=f.finding_type,
                severity=f.severity,
                status=f.status,
                title=f.title,
                description=f.description,
                category=f.category,
                expected_value=f.expected_value,
                actual_value=f.actual_value,
                difference=f.difference,
                source_document=f.source_document,
                source_sheet=f.source_sheet,
                source_row=f.source_row,
                possible_causes=json.loads(f.possible_causes or "[]"),
                recommended_actions=json.loads(f.recommended_actions or "[]"),
                accountant_decision=f.accountant_decision,
                decision_notes=f.decision_notes,
            )
        )
    return res


@router.post("/profiles/{profile_id}/findings/{finding_id}/decision", response_model=ITRFindingResponse)
def update_finding_decision(
    profile_id: int,
    finding_id: int,
    payload: ITRFindingDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    f = ITRService.update_finding_decision(
        db=db, user=current_user, profile_id=profile_id, finding_id=finding_id, req=payload
    )
    import json
    return ITRFindingResponse(
        id=f.id,
        profile_id=f.profile_id,
        finding_type=f.finding_type,
        severity=f.severity,
        status=f.status,
        title=f.title,
        description=f.description,
        category=f.category,
        expected_value=f.expected_value,
        actual_value=f.actual_value,
        difference=f.difference,
        source_document=f.source_document,
        source_sheet=f.source_sheet,
        source_row=f.source_row,
        possible_causes=json.loads(f.possible_causes or "[]"),
        recommended_actions=json.loads(f.recommended_actions or "[]"),
        accountant_decision=f.accountant_decision,
        decision_notes=f.decision_notes,
    )


@router.get("/profiles/{profile_id}/export")
def export_report(
    profile_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    csv_data = ITRService.export_report(db=db, user=current_user, profile_id=profile_id)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=itr_preparation_report_profile_{profile_id}.csv"
        },
    )
