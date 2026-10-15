import csv
import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Dict, Any, Optional

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.modules.itr.models import (
    ITRProfile,
    ITRIncomeEntry,
    ITRDeductionEntry,
    ITRTaxCreditEntry,
    ITRComputationSnapshot,
    ITRFinding,
)
from app.modules.itr.schemas import (
    ITRProfileCreate,
    ITRProfileUpdate,
    ITRIncomeEntryCreate,
    ITRDeductionEntryCreate,
    ITRDeductionEntryUpdate,
    ITRTaxCreditEntryCreate,
    ITRComputationResponse,
    ITRRegimeComparisonResponse,
    ITRFindingDecisionRequest,
)
from app.modules.itr.calculator import ITRCalculator
from app.services.history_service import HistoryService

logger = logging.getLogger(__name__)


class ITRService:
    """Service layer orchestrating Indian ITR preparation, deterministic computation, and accountant review."""

    @classmethod
    def get_scoped_profile(cls, db: Session, user: User, profile_id: int) -> ITRProfile:
        profile = (
            db.query(ITRProfile)
            .filter(ITRProfile.id == profile_id, ITRProfile.user_id == user.id)
            .first()
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"ITR profile with ID {profile_id} not found or access denied.",
            )
        return profile

    @classmethod
    def get_profiles(cls, db: Session, user: User) -> List[ITRProfile]:
        return (
            db.query(ITRProfile)
            .filter(ITRProfile.user_id == user.id)
            .order_by(ITRProfile.assessment_year.desc(), ITRProfile.created_at.desc())
            .all()
        )

    @classmethod
    def create_profile(cls, db: Session, user: User, data: ITRProfileCreate) -> ITRProfile:
        pan_clean = data.pan.upper().strip()
        existing = (
            db.query(ITRProfile)
            .filter(
                ITRProfile.user_id == user.id,
                ITRProfile.pan == pan_clean,
                ITRProfile.assessment_year == data.assessment_year.strip(),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"An ITR profile for PAN {pan_clean} and AY {data.assessment_year} already exists.",
            )

        profile = ITRProfile(
            user_id=user.id,
            pan=pan_clean,
            taxpayer_name=data.taxpayer_name.strip(),
            taxpayer_category=data.taxpayer_category.upper().strip(),
            assessment_year=data.assessment_year.strip(),
            financial_year=data.financial_year.strip(),
            selected_regime=data.selected_regime.upper().strip(),
            status="DRAFT",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="create_profile",
            target_name=f"ITR {profile.pan} ({profile.assessment_year})",
            result_summary=f"Created ITR profile for {profile.taxpayer_name} (AY {profile.assessment_year})",
            user_action="Created ITR Profile",
        )
        return profile

    @classmethod
    def update_profile(cls, db: Session, user: User, profile_id: int, data: Any) -> ITRProfile:
        profile = cls.get_scoped_profile(db, user, profile_id)
        if profile.status == "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approved ITR profile is locked and cannot be modified without re-opening.",
            )

        if isinstance(data, dict):
            data = ITRProfileUpdate(**data)

        if data.taxpayer_name:
            profile.taxpayer_name = data.taxpayer_name.strip()
        if data.taxpayer_category:
            profile.taxpayer_category = data.taxpayer_category.upper().strip()
        if data.selected_regime:
            profile.selected_regime = data.selected_regime.upper().strip()

        db.commit()
        db.refresh(profile)
        return profile

    @classmethod
    def add_income_entry(cls, db: Session, user: User, profile_id: int, data: ITRIncomeEntryCreate) -> ITRIncomeEntry:
        profile = cls.get_scoped_profile(db, user, profile_id)
        cls._verify_profile_editable(profile)

        entry = ITRIncomeEntry(
            profile_id=profile.id,
            head_of_income=data.head_of_income.upper().strip(),
            subcategory=data.subcategory.upper().strip(),
            description=data.description,
            gross_amount=data.gross_amount,
            exemptions_allowances=data.exemptions_allowances,
            net_taxable_amount=max(Decimal("0.00"), data.gross_amount - data.exemptions_allowances),
            verification_status=data.verification_status,
            source_document=data.source_document,
            source_sheet=data.source_sheet,
            source_row=data.source_row,
            source_cell=data.source_cell,
            provenance_notes=data.provenance_notes or ("Source verified" if data.source_document else "Source not verified"),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="add_income",
            target_name=f"{entry.head_of_income} Entry",
            result_summary=f"Added {entry.head_of_income} income of ₹{float(entry.gross_amount):,.2f}",
            user_action="Added Income Entry",
        )
        return entry

    @classmethod
    def add_deduction_entry(cls, db: Session, user: User, profile_id: int, data: ITRDeductionEntryCreate) -> ITRDeductionEntry:
        profile = cls.get_scoped_profile(db, user, profile_id)
        cls._verify_profile_editable(profile)

        entry = ITRDeductionEntry(
            profile_id=profile.id,
            section=data.section.upper().strip(),
            description=data.description,
            claimed_amount=data.claimed_amount,
            eligible_amount=data.eligible_amount if data.eligible_amount > 0 else data.claimed_amount,
            status=data.status,
            source_document=data.source_document,
            source_sheet=data.source_sheet,
            source_row=data.source_row,
            provenance_notes=data.provenance_notes or ("Source verified" if data.source_document else "Source not verified"),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="add_deduction",
            target_name=f"Section {entry.section}",
            result_summary=f"Claimed Section {entry.section} deduction of ₹{float(entry.claimed_amount):,.2f}",
            user_action="Added Deduction Entry",
        )
        return entry

    @classmethod
    def update_deduction_entry(
        cls, db: Session, user: User, profile_id: int, entry_id: int, data: ITRDeductionEntryUpdate
    ) -> ITRDeductionEntry:
        profile = cls.get_scoped_profile(db, user, profile_id)
        cls._verify_profile_editable(profile)

        entry = (
            db.query(ITRDeductionEntry)
            .filter(ITRDeductionEntry.id == entry_id, ITRDeductionEntry.profile_id == profile.id)
            .first()
        )
        if not entry:
            raise HTTPException(status_code=404, detail="Deduction entry not found.")

        if data.eligible_amount is not None:
            entry.eligible_amount = data.eligible_amount
        if data.status:
            entry.status = data.status.upper().strip()
        if data.provenance_notes:
            entry.provenance_notes = data.provenance_notes

        db.commit()
        db.refresh(entry)
        return entry

    @classmethod
    def add_tax_credit_entry(
        cls, db: Session, user: User, profile_id: int, data: ITRTaxCreditEntryCreate
    ) -> ITRTaxCreditEntry:
        profile = cls.get_scoped_profile(db, user, profile_id)
        cls._verify_profile_editable(profile)

        entry = ITRTaxCreditEntry(
            profile_id=profile.id,
            credit_type=data.credit_type.upper().strip(),
            deductor_or_bank=data.deductor_or_bank,
            deductor_tan_pan=data.deductor_tan_pan,
            section_code=data.section_code,
            challan_or_cert_no=data.challan_or_cert_no,
            credit_amount=data.credit_amount,
            date_of_payment=data.date_of_payment,
            verification_status=data.verification_status,
            source_document=data.source_document,
            source_sheet=data.source_sheet,
            source_row=data.source_row,
            provenance_notes=data.provenance_notes or ("Source verified" if data.source_document else "Source not verified"),
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="add_tax_credit",
            target_name=f"{entry.credit_type} Credit",
            result_summary=f"Recorded tax credit {entry.credit_type} of ₹{float(entry.credit_amount):,.2f}",
            user_action="Added Tax Credit Entry",
        )
        return entry

    @classmethod
    def upload_tax_file(cls, db: Session, user: User, profile_id: int, file: UploadFile) -> Dict[str, Any]:
        """
        Parses source tax / accounting file (Excel, CSV, or JSON) and populates structured records
        while strictly preserving source provenance: document, sheet, row, and cell.
        """
        profile = cls.get_scoped_profile(db, user, profile_id)
        cls._verify_profile_editable(profile)

        filename = file.filename or "unknown_tax_file"
        content = file.file.read()

        imported_incomes = 0
        imported_deductions = 0
        imported_credits = 0

        if filename.endswith(".json"):
            try:
                payload = json.loads(content.decode("utf-8"))
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON tax document: {str(e)}")

            # Process Incomes
            for i, inc in enumerate(payload.get("income", [])):
                entry = ITRIncomeEntry(
                    profile_id=profile.id,
                    head_of_income=inc.get("head_of_income", "OTHER_SOURCES").upper(),
                    subcategory=inc.get("subcategory", "GENERAL"),
                    description=inc.get("description", "Imported income"),
                    gross_amount=Decimal(str(inc.get("gross_amount", 0))),
                    exemptions_allowances=Decimal(str(inc.get("exemptions_allowances", 0))),
                    net_taxable_amount=Decimal(str(inc.get("net_taxable_amount", inc.get("gross_amount", 0)))),
                    verification_status=inc.get("verification_status", "VERIFIED"),
                    source_document=filename,
                    source_sheet="JSON_PAYLOAD",
                    source_row=i + 1,
                    source_cell=f"R{i+1}C1",
                    provenance_notes=f"Imported from {filename} row {i+1}",
                )
                db.add(entry)
                imported_incomes += 1

            # Process Deductions
            for i, ded in enumerate(payload.get("deductions", [])):
                entry = ITRDeductionEntry(
                    profile_id=profile.id,
                    section=ded.get("section", "80C").upper(),
                    description=ded.get("description", "Imported deduction"),
                    claimed_amount=Decimal(str(ded.get("claimed_amount", 0))),
                    eligible_amount=Decimal(str(ded.get("eligible_amount", ded.get("claimed_amount", 0)))),
                    status=ded.get("status", "REVIEW_REQUIRED"),
                    source_document=filename,
                    source_sheet="JSON_PAYLOAD",
                    source_row=i + 1,
                    provenance_notes=f"Imported from {filename} row {i+1}",
                )
                db.add(entry)
                imported_deductions += 1

            # Process Credits
            for i, cred in enumerate(payload.get("tax_credits", [])):
                entry = ITRTaxCreditEntry(
                    profile_id=profile.id,
                    credit_type=cred.get("credit_type", "TDS_SALARY").upper(),
                    deductor_or_bank=cred.get("deductor_or_bank"),
                    deductor_tan_pan=cred.get("deductor_tan_pan"),
                    section_code=cred.get("section_code"),
                    challan_or_cert_no=cred.get("challan_or_cert_no"),
                    credit_amount=Decimal(str(cred.get("credit_amount", 0))),
                    date_of_payment=cred.get("date_of_payment"),
                    verification_status=cred.get("verification_status", "VERIFIED"),
                    source_document=filename,
                    source_sheet="JSON_PAYLOAD",
                    source_row=i + 1,
                    provenance_notes=f"Imported from {filename} row {i+1}",
                )
                db.add(entry)
                imported_credits += 1

        elif filename.endswith(".csv"):
            text_data = content.decode("utf-8-sig", errors="ignore").splitlines()
            reader = csv.DictReader(text_data)
            for row_idx, row in enumerate(reader, start=2):
                cat = row.get("type", "").strip().upper()
                if cat == "INCOME":
                    entry = ITRIncomeEntry(
                        profile_id=profile.id,
                        head_of_income=row.get("head", "OTHER_SOURCES").upper().strip(),
                        subcategory=row.get("subcategory", "GENERAL").strip(),
                        description=row.get("description", ""),
                        gross_amount=Decimal(str(row.get("amount", 0) or 0)),
                        exemptions_allowances=Decimal("0.00"),
                        net_taxable_amount=Decimal(str(row.get("amount", 0) or 0)),
                        verification_status="VERIFIED" if row.get("verified", "").lower() in ("true", "1", "yes") else "REVIEW_REQUIRED",
                        source_document=filename,
                        source_sheet="CSV_SHEET",
                        source_row=row_idx,
                        provenance_notes=f"Document: {filename} | Row: {row_idx}",
                    )
                    db.add(entry)
                    imported_incomes += 1
                elif cat == "DEDUCTION":
                    entry = ITRDeductionEntry(
                        profile_id=profile.id,
                        section=row.get("section", "80C").upper().strip(),
                        description=row.get("description", "Deduction"),
                        claimed_amount=Decimal(str(row.get("amount", 0) or 0)),
                        eligible_amount=Decimal(str(row.get("amount", 0) or 0)),
                        status="VERIFIED" if row.get("verified", "").lower() in ("true", "1", "yes") else "REVIEW_REQUIRED",
                        source_document=filename,
                        source_sheet="CSV_SHEET",
                        source_row=row_idx,
                        provenance_notes=f"Document: {filename} | Row: {row_idx}",
                    )
                    db.add(entry)
                    imported_deductions += 1
                elif cat in ("TDS", "TCS", "ADVANCE_TAX", "TAX_CREDIT"):
                    entry = ITRTaxCreditEntry(
                        profile_id=profile.id,
                        credit_type=cat if cat != "TAX_CREDIT" else "TDS_SALARY",
                        deductor_or_bank=row.get("deductor", ""),
                        deductor_tan_pan=row.get("tan_pan", ""),
                        credit_amount=Decimal(str(row.get("amount", 0) or 0)),
                        verification_status="VERIFIED" if row.get("verified", "").lower() in ("true", "1", "yes") else "REVIEW_REQUIRED",
                        source_document=filename,
                        source_sheet="CSV_SHEET",
                        source_row=row_idx,
                        provenance_notes=f"Document: {filename} | Row: {row_idx}",
                    )
                    db.add(entry)
                    imported_credits += 1
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported tax document format. Supported formats: .json, .csv",
            )

        db.commit()

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="import_tax_document",
            target_name=filename,
            result_summary=f"Imported {imported_incomes} incomes, {imported_deductions} deductions, and {imported_credits} credits from {filename}",
            user_action="Imported Tax Document",
        )

        return {
            "status": "success",
            "message": f"Successfully parsed and imported tax source file: {filename}",
            "imported_incomes": imported_incomes,
            "imported_deductions": imported_deductions,
            "imported_credits": imported_credits,
        }

    @classmethod
    def calculate_itr(cls, db: Session, user: User, profile_id: int) -> ITRRegimeComparisonResponse:
        """
        Executes deterministic statutory calculation for both New and Old regimes.
        Generates SHA-256 snapshot hashes and evaluates review findings.
        """
        profile = cls.get_scoped_profile(db, user, profile_id)

        # 1. Fetch entries
        incomes = (
            db.query(ITRIncomeEntry)
            .filter(ITRIncomeEntry.profile_id == profile.id)
            .all()
        )
        deductions = (
            db.query(ITRDeductionEntry)
            .filter(ITRDeductionEntry.profile_id == profile.id)
            .all()
        )
        credits = (
            db.query(ITRTaxCreditEntry)
            .filter(ITRTaxCreditEntry.profile_id == profile.id)
            .all()
        )

        # 2. Aggregate Heads of Income
        salary_gross = sum((e.gross_amount for e in incomes if e.head_of_income == "SALARY"), Decimal("0.00"))
        hp_gross = sum((e.gross_amount for e in incomes if e.head_of_income == "HOUSE_PROPERTY"), Decimal("0.00"))
        business_gross = sum((e.gross_amount for e in incomes if e.head_of_income == "BUSINESS_PROFESSION"), Decimal("0.00"))
        capital_gains = sum((e.gross_amount for e in incomes if e.head_of_income == "CAPITAL_GAINS"), Decimal("0.00"))
        other_sources = sum((e.gross_amount for e in incomes if e.head_of_income == "OTHER_SOURCES"), Decimal("0.00"))

        # 3. Aggregate Deductions (Only eligible/verified entries)
        ded_80c = sum((d.eligible_amount for d in deductions if d.section == "80C" and d.status in ("VERIFIED", "REVIEW_REQUIRED")), Decimal("0.00"))
        ded_80d = sum((d.eligible_amount for d in deductions if d.section == "80D" and d.status in ("VERIFIED", "REVIEW_REQUIRED")), Decimal("0.00"))
        ded_80ccd = sum((d.eligible_amount for d in deductions if d.section == "80CCD_1B" and d.status in ("VERIFIED", "REVIEW_REQUIRED")), Decimal("0.00"))
        ded_other = sum((d.eligible_amount for d in deductions if d.section not in ("80C", "80D", "80CCD_1B") and d.status in ("VERIFIED", "REVIEW_REQUIRED")), Decimal("0.00"))

        # 4. Aggregate Tax Credits
        tds_total = sum((c.credit_amount for c in credits if c.credit_type.startswith("TDS")), Decimal("0.00"))
        tcs_total = sum((c.credit_amount for c in credits if c.credit_type == "TCS"), Decimal("0.00"))
        adv_tax = sum((c.credit_amount for c in credits if c.credit_type == "ADVANCE_TAX"), Decimal("0.00"))
        self_tax = sum((c.credit_amount for c in credits if c.credit_type == "SELF_ASSESSMENT_TAX"), Decimal("0.00"))

        # 5. Deterministic Tax Calculations for Both Regimes
        calc_old = ITRCalculator.calculate_tax(
            regime="OLD",
            assessment_year=profile.assessment_year,
            gross_salary=salary_gross,
            house_property=hp_gross,
            business_profession=business_gross,
            capital_gains=capital_gains,
            other_sources=other_sources,
            verified_deductions_80c=ded_80c,
            verified_deductions_80d=ded_80d,
            verified_deductions_80ccd_1b=ded_80ccd,
            other_verified_deductions=ded_other,
            tds_total=tds_total,
            tcs_total=tcs_total,
            advance_tax_total=adv_tax,
            self_assessment_tax_total=self_tax,
        )

        calc_new = ITRCalculator.calculate_tax(
            regime="NEW",
            assessment_year=profile.assessment_year,
            gross_salary=salary_gross,
            house_property=hp_gross,
            business_profession=business_gross,
            capital_gains=capital_gains,
            other_sources=other_sources,
            verified_deductions_80c=Decimal("0.00"),
            verified_deductions_80d=Decimal("0.00"),
            verified_deductions_80ccd_1b=Decimal("0.00"),
            other_verified_deductions=Decimal("0.00"),
            tds_total=tds_total,
            tcs_total=tcs_total,
            advance_tax_total=adv_tax,
            self_assessment_tax_total=self_tax,
        )

        # 6. Store Snapshots
        for r_name, calc_res in [("OLD", calc_old), ("NEW", calc_new)]:
            # Deterministic SHA-256 hash
            raw_hash_str = f"{profile.id}:{r_name}:{calc_res['gross_total_income']}:{calc_res['total_taxable_income']}:{calc_res['total_tax_liability']}"
            comp_hash = hashlib.sha256(raw_hash_str.encode("utf-8")).hexdigest()

            # Remove previous snapshot for this regime
            db.query(ITRComputationSnapshot).filter(
                ITRComputationSnapshot.profile_id == profile.id,
                ITRComputationSnapshot.regime == r_name,
            ).delete()

            snapshot = ITRComputationSnapshot(
                profile_id=profile.id,
                regime=r_name,
                computation_hash=comp_hash,
                gross_salary=calc_res["gross_salary"],
                standard_deduction=calc_res["standard_deduction"],
                net_salary=calc_res["net_salary"],
                house_property_income=calc_res["house_property_income"],
                business_profession_income=calc_res["business_profession_income"],
                capital_gains=calc_res["capital_gains"],
                other_sources_income=calc_res["other_sources_income"],
                gross_total_income=calc_res["gross_total_income"],
                total_deductions=calc_res["total_deductions"],
                total_taxable_income=calc_res["total_taxable_income"],
                basic_tax=calc_res["basic_tax"],
                rebate_87a=calc_res["rebate_87a"],
                tax_after_rebate=calc_res["tax_after_rebate"],
                cess_4_pct=calc_res["cess_4_pct"],
                total_tax_liability=calc_res["total_tax_liability"],
                tds_total=calc_res["tds_total"],
                tcs_total=calc_res["tcs_total"],
                advance_tax_total=calc_res["advance_tax_total"],
                self_assessment_tax_total=calc_res["self_assessment_tax_total"],
                total_taxes_paid=calc_res["total_taxes_paid"],
                net_payable_or_refund=calc_res["net_payable_or_refund"],
                calculation_breakdown_json=json.dumps(calc_res["breakdown"], default=str),
            )
            db.add(snapshot)

        # 7. Evaluate and populate Review Findings
        cls._evaluate_review_findings(db, profile, incomes, deductions, credits, calc_new, calc_old)

        # Update profile status if in DRAFT
        if profile.status == "DRAFT":
            profile.status = "ANALYZED"

        db.commit()

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="calculate_tax",
            target_name=f"ITR AY {profile.assessment_year}",
            result_summary=f"Calculated ITR for {profile.pan}: GTI ₹{float(calc_new['gross_total_income']):,.2f}, Tax New ₹{float(calc_new['total_tax_liability']):,.2f}, Tax Old ₹{float(calc_old['total_tax_liability']):,.2f}",
            user_action="Calculated Tax",
        )

        return cls.get_regime_comparison(db, user, profile.id)

    @classmethod
    def _evaluate_review_findings(
        cls,
        db: Session,
        profile: ITRProfile,
        incomes: List[ITRIncomeEntry],
        deductions: List[ITRDeductionEntry],
        credits: List[ITRTaxCreditEntry],
        calc_new: Dict[str, Any],
        calc_old: Dict[str, Any],
    ) -> None:
        """Evaluates statutory compliance and generates Review Center findings."""
        # Clear existing un-reviewed findings
        db.query(ITRFinding).filter(
            ITRFinding.profile_id == profile.id,
            ITRFinding.status == "REVIEW_REQUIRED",
        ).delete()

        # Finding 1: Salary without corresponding TDS entry
        has_salary = any(i.head_of_income == "SALARY" and i.gross_amount > Decimal("500000.00") for i in incomes)
        has_salary_tds = any(c.credit_type == "TDS_SALARY" and c.credit_amount > Decimal("0.00") for c in credits)
        if has_salary and not has_salary_tds:
            f = ITRFinding(
                profile_id=profile.id,
                finding_type="MISSING_TDS",
                severity="HIGH",
                status="REVIEW_REQUIRED",
                title="Missing Salary TDS (Form 16 / Section 192)",
                description="Salary income exceeds ₹5,00,000 but no corresponding TDS under Section 192 has been recorded.",
                expected_value=Decimal("0.00"),
                actual_value=Decimal("0.00"),
                possible_causes=json.dumps([
                    "Form 16 Part A not yet imported",
                    "Employer TDS not reflected in Form 26AS",
                    "Taxpayer exempt or tax deducted under wrong TAN",
                ]),
                recommended_actions=json.dumps([
                    "Cross-check AIS/TIS and Form 26AS on Income Tax Portal",
                    "Import employer Form 16 Part A and verify TAN",
                ]),
            )
            db.add(f)

        # Finding 2: Section 80C claimed exceeds ₹1,50,000 ceiling
        total_80c_claimed = sum((d.claimed_amount for d in deductions if d.section == "80C"), Decimal("0.00"))
        if total_80c_claimed > Decimal("150000.00"):
            f = ITRFinding(
                profile_id=profile.id,
                finding_type="UNSUPPORTED_DEDUCTION",
                severity="MEDIUM",
                status="REVIEW_REQUIRED",
                title="Section 80C Claim Exceeds Statutory Limit",
                description=f"Total Section 80C deduction claimed (₹{total_80c_claimed:,.2f}) exceeds the statutory limit of ₹1,50,000.",
                expected_value=Decimal("150000.00"),
                actual_value=total_80c_claimed,
                difference=total_80c_claimed - Decimal("150000.00"),
                possible_causes=json.dumps([
                    "Multiple 80C instruments (PPF, ELSS, EPF, Life Insurance) combined without applying statutory cap",
                ]),
                recommended_actions=json.dumps([
                    "System automatically caps eligible deduction to ₹1,50,000 under Old Regime",
                    "Accountant verification required for tax schedule disclosures",
                ]),
            )
            db.add(f)

        # Finding 3: Missing Document Provenance on large entries (> ₹1,00,000)
        unverified_incomes = [i for i in incomes if not i.source_document and i.gross_amount >= Decimal("100000.00")]
        if unverified_incomes:
            f = ITRFinding(
                profile_id=profile.id,
                finding_type="MISSING_DOCUMENT",
                severity="HIGH",
                status="REVIEW_REQUIRED",
                title=f"Source Document Missing on {len(unverified_incomes)} Significant Income Items",
                description=f"{len(unverified_incomes)} income items over ₹1,00,000 lack verified source document provenance.",
                possible_causes=json.dumps(["Manual entry without attaching supporting ledger or bank statement"]),
                recommended_actions=json.dumps(["Upload bank statement, Form 16, or salary certificate for full audit trail"]),
            )
            db.add(f)

        # Finding 4: Undecided Tax Regime
        if profile.selected_regime == "UNDECIDED":
            f = ITRFinding(
                profile_id=profile.id,
                finding_type="CALCULATION_VERIFICATION",
                severity="MEDIUM",
                status="REVIEW_REQUIRED",
                title="Tax Regime Selection Required",
                description="The taxpayer has not explicitly selected between the Old and New tax regimes.",
                possible_causes=json.dumps(["Default status upon initial analysis"]),
                recommended_actions=json.dumps([
                    "Review side-by-side comparison with the taxpayer and select Old or New Regime",
                ]),
            )
            db.add(f)

    @classmethod
    def get_regime_comparison(cls, db: Session, user: User, profile_id: int) -> ITRRegimeComparisonResponse:
        profile = cls.get_scoped_profile(db, user, profile_id)

        old_snap = (
            db.query(ITRComputationSnapshot)
            .filter(ITRComputationSnapshot.profile_id == profile.id, ITRComputationSnapshot.regime == "OLD")
            .first()
        )
        new_snap = (
            db.query(ITRComputationSnapshot)
            .filter(ITRComputationSnapshot.profile_id == profile.id, ITRComputationSnapshot.regime == "NEW")
            .first()
        )

        if not old_snap or not new_snap:
            # Trigger calculation if not done yet
            return cls.calculate_itr(db, user, profile.id)

        diff = abs(old_snap.total_tax_liability - new_snap.total_tax_liability)

        # Unresolved critical/high findings
        critical_high_count = (
            db.query(ITRFinding)
            .filter(
                ITRFinding.profile_id == profile.id,
                ITRFinding.severity.in_(["CRITICAL", "HIGH"]),
                ITRFinding.status.in_(["REVIEW_REQUIRED", "UNDER_REVIEW"]),
            )
            .count()
        )

        all_unresolved = (
            db.query(ITRFinding)
            .filter(
                ITRFinding.profile_id == profile.id,
                ITRFinding.status.in_(["REVIEW_REQUIRED", "UNDER_REVIEW"]),
            )
            .count()
        )

        eligible_for_approval = critical_high_count == 0 and profile.selected_regime in ("NEW", "OLD")

        return ITRRegimeComparisonResponse(
            profile_id=profile.id,
            pan=profile.pan,
            taxpayer_name=profile.taxpayer_name,
            assessment_year=profile.assessment_year,
            selected_regime=profile.selected_regime,
            old_regime=ITRComputationResponse(
                profile_id=profile.id,
                regime="OLD",
                computation_hash=old_snap.computation_hash,
                gross_salary=old_snap.gross_salary,
                standard_deduction=old_snap.standard_deduction,
                net_salary=old_snap.net_salary,
                house_property_income=old_snap.house_property_income,
                business_profession_income=old_snap.business_profession_income,
                capital_gains=old_snap.capital_gains,
                other_sources_income=old_snap.other_sources_income,
                gross_total_income=old_snap.gross_total_income,
                total_deductions=old_snap.total_deductions,
                total_taxable_income=old_snap.total_taxable_income,
                basic_tax=old_snap.basic_tax,
                rebate_87a=old_snap.rebate_87a,
                tax_after_rebate=old_snap.tax_after_rebate,
                cess_4_pct=old_snap.cess_4_pct,
                total_tax_liability=old_snap.total_tax_liability,
                tds_total=old_snap.tds_total,
                tcs_total=old_snap.tcs_total,
                advance_tax_total=old_snap.advance_tax_total,
                self_assessment_tax_total=old_snap.self_assessment_tax_total,
                total_taxes_paid=old_snap.total_taxes_paid,
                net_payable_or_refund=old_snap.net_payable_or_refund,
                breakdown=json.loads(old_snap.calculation_breakdown_json or "{}"),
            ),
            new_regime=ITRComputationResponse(
                profile_id=profile.id,
                regime="NEW",
                computation_hash=new_snap.computation_hash,
                gross_salary=new_snap.gross_salary,
                standard_deduction=new_snap.standard_deduction,
                net_salary=new_snap.net_salary,
                house_property_income=new_snap.house_property_income,
                business_profession_income=new_snap.business_profession_income,
                capital_gains=new_snap.capital_gains,
                other_sources_income=new_snap.other_sources_income,
                gross_total_income=new_snap.gross_total_income,
                total_deductions=new_snap.total_deductions,
                total_taxable_income=new_snap.total_taxable_income,
                basic_tax=new_snap.basic_tax,
                rebate_87a=new_snap.rebate_87a,
                tax_after_rebate=new_snap.tax_after_rebate,
                cess_4_pct=new_snap.cess_4_pct,
                total_tax_liability=new_snap.total_tax_liability,
                tds_total=new_snap.tds_total,
                tcs_total=new_snap.tcs_total,
                advance_tax_total=new_snap.advance_tax_total,
                self_assessment_tax_total=new_snap.self_assessment_tax_total,
                total_taxes_paid=new_snap.total_taxes_paid,
                net_payable_or_refund=new_snap.net_payable_or_refund,
                breakdown=json.loads(new_snap.calculation_breakdown_json or "{}"),
            ),
            difference_in_tax=diff,
            unresolved_findings_count=all_unresolved,
            eligible_for_approval=eligible_for_approval,
        )

    @classmethod
    def transition_status(cls, db: Session, user: User, profile_id: int, target_status: str, notes: Optional[str] = None) -> ITRProfile:
        profile = cls.get_scoped_profile(db, user, profile_id)
        target_norm = target_status.upper().strip()

        # Strict safety check: Approval requires NO unresolved CRITICAL or HIGH findings!
        if target_norm == "APPROVED":
            critical_high_count = (
                db.query(ITRFinding)
                .filter(
                    ITRFinding.profile_id == profile.id,
                    ITRFinding.severity.in_(["CRITICAL", "HIGH"]),
                    ITRFinding.status.in_(["REVIEW_REQUIRED", "UNDER_REVIEW"]),
                )
                .count()
            )
            if critical_high_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Safety Block: Cannot approve ITR with {critical_high_count} unresolved CRITICAL or HIGH review findings.",
                )
            if profile.selected_regime not in ("NEW", "OLD"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Safety Block: An explicit tax regime (New or Old) must be selected before approval.",
                )
            profile.status = "APPROVED"
            profile.approved_at = datetime.now(timezone.utc)
            profile.approved_by_user_id = user.id
            profile.approval_notes = notes
        else:
            profile.status = target_norm

        db.commit()
        db.refresh(profile)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="transition_status",
            target_name=f"ITR {profile.pan}",
            result_summary=f"ITR status transitioned to {profile.status}. Notes: {notes or 'None'}",
            user_action=f"ITR Status: {profile.status}",
        )
        return profile

    @classmethod
    def get_findings(cls, db: Session, user: User, profile_id: int) -> List[ITRFinding]:
        profile = cls.get_scoped_profile(db, user, profile_id)
        return (
            db.query(ITRFinding)
            .filter(ITRFinding.profile_id == profile.id)
            .order_by(ITRFinding.created_at.desc())
            .all()
        )

    @classmethod
    def update_finding_decision(
        cls, db: Session, user: User, profile_id: int, finding_id: int, req: ITRFindingDecisionRequest
    ) -> ITRFinding:
        profile = cls.get_scoped_profile(db, user, profile_id)
        finding = (
            db.query(ITRFinding)
            .filter(ITRFinding.id == finding_id, ITRFinding.profile_id == profile.id)
            .first()
        )
        if not finding:
            raise HTTPException(status_code=404, detail="Finding not found.")

        finding.accountant_decision = req.decision.upper().strip()
        finding.decision_notes = req.notes
        finding.reviewed_at = datetime.now(timezone.utc)
        finding.status = "APPROVED" if req.decision.upper() == "ACCEPTED" else "REJECTED"

        db.commit()
        db.refresh(finding)

        HistoryService.record_activity(
            db=db,
            user_id=user.id,
            module="itr",
            action="review_finding",
            target_name=f"ITR Finding #{finding.id}",
            result_summary=f"Recorded accountant decision '{finding.accountant_decision}' for {finding.finding_type}",
            user_action=f"ITR Finding Decision: {finding.accountant_decision}",
        )
        return finding

    @classmethod
    def export_report(cls, db: Session, user: User, profile_id: int) -> str:
        """
        Generates structured accountant-friendly preparation report in CSV format
        prominently labeled 'ITR Preparation Report — Accountant Review Required'.
        """
        profile = cls.get_scoped_profile(db, user, profile_id)
        comparison = cls.get_regime_comparison(db, user, profile.id)

        chosen_comp = comparison.new_regime if profile.selected_regime == "NEW" else comparison.old_regime

        lines = [
            "==================================================================",
            "ITR Preparation Report — Accountant Review Required",
            "STATUTORY NOTICE: This report is an internal preparation statement",
            "generated for accountant verification and taxpayer sign-off.",
            "This return has NOT been submitted to the Income Tax Department.",
            "==================================================================",
            f"Taxpayer Name,{profile.taxpayer_name}",
            f"Permanent Account Number (PAN),{profile.pan}",
            f"Assessment Year,{profile.assessment_year}",
            f"Financial Year,{profile.financial_year}",
            f"Selected Tax Regime,{profile.selected_regime}",
            f"Return Status,{profile.status}",
            "",
            "HEADS OF INCOME (INR),Amount",
            f"Gross Salary,{chosen_comp.gross_salary}",
            f"Less: Standard Deduction,{chosen_comp.standard_deduction}",
            f"Net Salary,{chosen_comp.net_salary}",
            f"House Property Income,{chosen_comp.house_property_income}",
            f"Profits and Gains of Business or Profession,{chosen_comp.business_profession_income}",
            f"Capital Gains,{chosen_comp.capital_gains}",
            f"Income from Other Sources,{chosen_comp.other_sources_income}",
            f"Gross Total Income (GTI),{chosen_comp.gross_total_income}",
            f"Less: Chapter VI-A Eligible Deductions,{chosen_comp.total_deductions}",
            f"Total Taxable Income (Rounded Sec 288A),{chosen_comp.total_taxable_income}",
            "",
            "TAX LIABILITY COMPUTATION (INR),Amount",
            f"Basic Income Tax,{chosen_comp.basic_tax}",
            f"Less: Rebate under Section 87A,{chosen_comp.rebate_87a}",
            f"Tax After Rebate,{chosen_comp.tax_after_rebate}",
            f"Health & Education Cess @ 4%,{chosen_comp.cess_4_pct}",
            f"Total Tax Liability,{chosen_comp.total_tax_liability}",
            "",
            "TAXES PAID & CREDITS (INR),Amount",
            f"Tax Deducted at Source (TDS),{chosen_comp.tds_total}",
            f"Tax Collected at Source (TCS),{chosen_comp.tcs_total}",
            f"Advance Tax Paid,{chosen_comp.advance_tax_total}",
            f"Self-Assessment Tax Paid,{chosen_comp.self_assessment_tax_total}",
            f"Total Taxes Paid,{chosen_comp.total_taxes_paid}",
            "",
            "NET RESULT (INR),Amount",
            f"Net Tax Payable / (Refund Due),{chosen_comp.net_payable_or_refund}",
            "",
            "REGIME COMPARISON SUMMARY",
            f"Old Regime Tax Liability,{comparison.old_regime.total_tax_liability}",
            f"New Regime Tax Liability (Sec 115BAC),{comparison.new_regime.total_tax_liability}",
            f"Difference in Tax Liability,{comparison.difference_in_tax}",
        ]
        return "\n".join(lines)

    @classmethod
    def _verify_profile_editable(cls, profile: ITRProfile) -> None:
        if profile.status == "APPROVED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ITR Profile has been approved and locked. Modifications are prohibited.",
            )
