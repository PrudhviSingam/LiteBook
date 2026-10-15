import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.user import User
from app.models.history import HistoryRecord
from app.modules.gst.models import (
    GSTRegistration,
    GSTFilingPeriod,
    GSTSalesInvoice,
    GSTPurchaseInvoice,
    GSTR2BRecord,
    GSTReconciliationResult,
    GSTR1Summary,
    GSTR3BSummary,
)
from app.modules.gst.constants import (
    PeriodStatus,
    MatchStatus,
    ReconciliationDecision,
    round_currency,
)
from app.modules.gst.validators import (
    validate_gstin,
    validate_state_code,
    validate_period_format,
    validate_invoice_structured,
    calculate_tax_split,
)
from app.modules.gst.calculators import (
    aggregate_gstr1,
    calculate_gstr3b,
    compute_gstr1_source_hash,
    compute_gstr3b_source_hash,
)
from app.modules.gst.reconciliation import (
    reconcile_purchases_with_gstr2b,
    normalize_invoice_number,
)
from app.modules.gst.schemas import (
    GSTRegistrationCreate,
    GSTRegistrationUpdate,
    GSTFilingPeriodCreate,
    GSTPeriodStatusTransition,
    GSTSalesInvoiceCreate,
    GSTPurchaseInvoiceCreate,
    GSTR2BRecordCreate,
    ReconciliationRunRequest,
    ReconciliationDecisionRequest,
)


class GSTService:
    # =========================================================================
    # Helpers & Scoping
    # =========================================================================

    @staticmethod
    def _log_audit(
        db: Session,
        user: User,
        action: str,
        target_name: str,
        summary: str,
        status_val: str = "completed",
    ) -> HistoryRecord:
        """Create audit log entry in history_records table."""
        record = HistoryRecord(
            user_id=user.id,
            module="gst",
            action=action,
            target_name=target_name,
            status=status_val,
            result_summary=summary,
            user_action=f"Executed by {user.full_name or user.email}",
        )
        db.add(record)
        return record

    @staticmethod
    def _verify_period_not_locked(period: GSTFilingPeriod):
        """Disallow any operations or recalculations if the period is locked or filed."""
        if period.status in (PeriodStatus.LOCKED.value, PeriodStatus.FILED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filing period '{period.period}' is {period.status.upper()} and cannot be modified or recalculated.",
            )

    @staticmethod
    def _verify_period_editable(period: GSTFilingPeriod):
        """Disallow invoice changes if period is under review, filed, or locked."""
        if period.status in (PeriodStatus.LOCKED.value, PeriodStatus.FILED.value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filing period '{period.period}' is {period.status.upper()} and cannot be modified.",
            )
        if period.status == PeriodStatus.UNDER_REVIEW.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filing period '{period.period}' is UNDER_REVIEW and cannot be modified. Re-open to DRAFT before adding or modifying records.",
            )

    @classmethod
    def get_scoped_registration(
        cls, db: Session, user: User, registration_id: str
    ) -> GSTRegistration:
        query = db.query(GSTRegistration).filter(GSTRegistration.id == registration_id)
        if not user.is_superuser:
            if user.organization_id:
                query = query.filter(
                    (GSTRegistration.user_id == user.id)
                    | (GSTRegistration.organization_id == user.organization_id)
                )
            else:
                query = query.filter(GSTRegistration.user_id == user.id)
        reg = query.first()
        if not reg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GST Registration not found or access denied",
            )
        return reg

    @classmethod
    def get_scoped_period(
        cls, db: Session, user: User, period_id: str
    ) -> GSTFilingPeriod:
        period = (
            db.query(GSTFilingPeriod).filter(GSTFilingPeriod.id == period_id).first()
        )
        if not period:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="GST Filing Period not found",
            )
        # Verify access through registration ownership
        cls.get_scoped_registration(db, user, period.registration_id)
        return period

    # =========================================================================
    # GST Registrations
    # =========================================================================

    @classmethod
    def create_registration(
        cls, db: Session, user: User, data: GSTRegistrationCreate
    ) -> GSTRegistration:
        is_gstin_valid, gstin_err = validate_gstin(data.gstin)
        if not is_gstin_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=gstin_err
            )

        is_state_valid, state_err = validate_state_code(data.state_code)
        if not is_state_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=state_err
            )

        # Check uniqueness per user/org
        existing = (
            db.query(GSTRegistration)
            .filter(
                GSTRegistration.gstin == data.gstin.strip().upper(),
                GSTRegistration.user_id == user.id,
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Registration with GSTIN {data.gstin} already exists.",
            )

        reg = GSTRegistration(
            gstin=data.gstin.strip().upper(),
            legal_name=data.legal_name.strip(),
            trade_name=data.trade_name.strip() if data.trade_name else None,
            state_code=data.state_code.strip(),
            registration_type=data.registration_type,
            authorized_signatory=data.authorized_signatory,
            is_active=data.is_active,
            user_id=user.id,
            organization_id=user.organization_id,
        )
        db.add(reg)
        db.flush()

        cls._log_audit(
            db,
            user,
            action="gst_registration_created",
            target_name=reg.gstin,
            summary=f"Created GST Registration for {reg.legal_name} ({reg.gstin})",
        )
        db.commit()
        db.refresh(reg)
        return reg

    @classmethod
    def get_registrations(cls, db: Session, user: User) -> List[GSTRegistration]:
        query = db.query(GSTRegistration)
        if not user.is_superuser:
            if user.organization_id:
                query = query.filter(
                    (GSTRegistration.user_id == user.id)
                    | (GSTRegistration.organization_id == user.organization_id)
                )
            else:
                query = query.filter(GSTRegistration.user_id == user.id)
        return query.order_by(GSTRegistration.created_at.desc()).all()

    @classmethod
    def update_registration(
        cls, db: Session, user: User, registration_id: str, data: GSTRegistrationUpdate
    ) -> GSTRegistration:
        reg = cls.get_scoped_registration(db, user, registration_id)
        if data.legal_name is not None:
            reg.legal_name = data.legal_name.strip()
        if data.trade_name is not None:
            reg.trade_name = data.trade_name.strip()
        if data.authorized_signatory is not None:
            reg.authorized_signatory = data.authorized_signatory.strip()
        if data.is_active is not None:
            reg.is_active = data.is_active

        cls._log_audit(
            db,
            user,
            action="gst_registration_updated",
            target_name=reg.gstin,
            summary=f"Updated GST Registration {reg.gstin}",
        )
        db.commit()
        db.refresh(reg)
        return reg

    # =========================================================================
    # GST Filing Periods
    # =========================================================================

    @classmethod
    def create_period(
        cls, db: Session, user: User, data: GSTFilingPeriodCreate
    ) -> GSTFilingPeriod:
        reg = cls.get_scoped_registration(db, user, data.registration_id)

        is_p_valid, p_err = validate_period_format(data.period)
        if not is_p_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=p_err)

        existing = (
            db.query(GSTFilingPeriod)
            .filter(
                GSTFilingPeriod.registration_id == reg.id,
                GSTFilingPeriod.period == data.period.strip(),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filing period '{data.period}' already exists for this registration.",
            )

        period = GSTFilingPeriod(
            registration_id=reg.id,
            period=data.period.strip(),
            financial_year=data.financial_year.strip(),
            status=PeriodStatus.DRAFT.value,
        )
        db.add(period)
        db.flush()

        cls._log_audit(
            db,
            user,
            action="gst_period_created",
            target_name=f"{reg.gstin} - {period.period}",
            summary=f"Created filing period {period.period} for {reg.gstin}",
        )
        db.commit()
        db.refresh(period)
        return period

    @classmethod
    def get_periods(
        cls, db: Session, user: User, registration_id: str
    ) -> List[GSTFilingPeriod]:
        reg = cls.get_scoped_registration(db, user, registration_id)
        return (
            db.query(GSTFilingPeriod)
            .filter(GSTFilingPeriod.registration_id == reg.id)
            .order_by(desc(GSTFilingPeriod.period))
            .all()
        )

    @classmethod
    def transition_period_status(
        cls, db: Session, user: User, period_id: str, data: GSTPeriodStatusTransition
    ) -> GSTFilingPeriod:
        # Role permission check: Viewer/guest roles cannot perform workflow transitions
        if hasattr(user, "role") and str(user.role).lower() in ("viewer", "guest"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your user role is not authorized to perform GST workflow transitions.",
            )

        period = cls.get_scoped_period(db, user, period_id)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        current_st = period.status
        target_st = data.new_status

        if current_st == target_st:
            return period

        # Workflow validation:
        # draft -> under_review -> approved -> filed -> locked
        # Can also re-open from under_review -> draft, or approved -> draft
        valid_transitions = {
            PeriodStatus.DRAFT.value: [PeriodStatus.UNDER_REVIEW.value],
            PeriodStatus.UNDER_REVIEW.value: [
                PeriodStatus.DRAFT.value,
                PeriodStatus.APPROVED.value,
            ],
            PeriodStatus.APPROVED.value: [
                PeriodStatus.UNDER_REVIEW.value,
                PeriodStatus.FILED.value,
            ],
            PeriodStatus.FILED.value: [PeriodStatus.LOCKED.value],
            PeriodStatus.LOCKED.value: [],  # Locked is immutable
        }

        if target_st not in valid_transitions.get(current_st, []):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status transition from '{current_st}' to '{target_st}'",
            )

        now_utc = datetime.now(timezone.utc)

        # Production Safeguard: Approval requires valid, non-stale calculation snapshots and zero error-level validation issues
        if target_st == PeriodStatus.APPROVED.value:
            g1 = (
                db.query(GSTR1Summary)
                .filter(GSTR1Summary.period_id == period.id)
                .first()
            )
            g3 = (
                db.query(GSTR3BSummary)
                .filter(GSTR3BSummary.period_id == period.id)
                .first()
            )
            if not g1 or not g3:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot approve period: Both GSTR-1 and GSTR-3B summaries must be generated prior to approval.",
                )

            sales = (
                db.query(GSTSalesInvoice)
                .filter(GSTSalesInvoice.period_id == period.id)
                .all()
            )
            purchases = (
                db.query(GSTPurchaseInvoice)
                .filter(GSTPurchaseInvoice.period_id == period.id)
                .all()
            )

            g1_curr_hash = compute_gstr1_source_hash(sales)
            g3_curr_hash = compute_gstr3b_source_hash(sales, purchases)

            if g1.is_stale or g1.source_data_hash != g1_curr_hash:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot approve period: GSTR-1 calculation snapshot is stale. Recalculate GSTR-1 before approving.",
                )
            if g3.is_stale or g3.source_data_hash != g3_curr_hash:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot approve period: GSTR-3B calculation snapshot is stale. Recalculate GSTR-3B before approving.",
                )

            invalid_invoices = [
                inv for inv in sales if inv.validation_status == "ERROR"
            ]
            if invalid_invoices:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve period: {len(invalid_invoices)} sales invoice(s) have blocking statutory validation errors.",
                )

        period.status = target_st

        if target_st == PeriodStatus.FILED.value:
            if not data.arn or not data.arn.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Filing ARN (Acknowledgement Reference Number) is required to mark period as FILED.",
                )
            period.filing_arn = data.arn.strip()
            period.filed_at = now_utc
            period.gstr1_status = "filed"
            period.gstr3b_status = "filed"
            period.filing_metadata = json.dumps(
                {
                    "arn": data.arn.strip(),
                    "filed_by": user.email,
                    "filed_at": now_utc.isoformat(),
                    "reason": data.reason or "Statutory return filed",
                }
            )

        elif target_st == PeriodStatus.LOCKED.value:
            period.locked_at = now_utc

        cls._log_audit(
            db,
            user,
            action=f"gst_period_{target_st}",
            target_name=f"{reg.gstin} - {period.period}",
            summary=f"Changed status from {current_st} to {target_st}. Reason: {data.reason or 'User action'}",
        )
        db.commit()
        db.refresh(period)
        return period

    # =========================================================================
    # Sales Invoices (GSTR-1)
    # =========================================================================

    @classmethod
    def create_sales_invoice(
        cls, db: Session, user: User, data: GSTSalesInvoiceCreate
    ) -> GSTSalesInvoice:
        period = cls.get_scoped_period(db, user, data.period_id)
        cls._verify_period_editable(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        norm_num = normalize_invoice_number(data.invoice_number)

        # Check duplicate invoice number (both raw and normalized) in period
        existing = (
            db.query(GSTSalesInvoice)
            .filter(
                GSTSalesInvoice.period_id == period.id,
                (GSTSalesInvoice.invoice_number == data.invoice_number.strip().upper())
                | (GSTSalesInvoice.normalized_invoice_number == norm_num),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invoice number '{data.invoice_number}' already exists in period '{period.period}'.",
            )

        # Handle tax split calculation
        cgst = data.cgst_amount
        sgst = data.sgst_amount
        igst = data.igst_amount
        cess = data.cess_amount

        if data.auto_calculate_tax:
            tax_split = calculate_tax_split(
                place_of_supply=data.place_of_supply,
                supplier_state=reg.state_code,
                taxable_value=data.taxable_value,
                tax_rate=data.tax_rate,
            )
            cgst = tax_split["cgst_amount"]
            sgst = tax_split["sgst_amount"]
            igst = tax_split["igst_amount"]
            total_amount = round_currency(
                data.taxable_value + cgst + sgst + igst + cess
            )
        else:
            total_amount = data.total_amount

        # Validate statutory correctness with structured issues
        is_valid, structured_issues, val_errors = validate_invoice_structured(
            supplier_state=reg.state_code,
            place_of_supply=data.place_of_supply,
            customer_gstin=data.customer_gstin,
            invoice_type=data.invoice_type,
            taxable_value=data.taxable_value,
            tax_rate=data.tax_rate,
            cgst=cgst,
            sgst=sgst,
            igst=igst,
            cess=cess,
            total_amount=total_amount,
            invoice_number=data.invoice_number,
            invoice_date=str(data.invoice_date),
            period=period.period,
            original_invoice_number=data.original_invoice_number,
        )

        inv = GSTSalesInvoice(
            gst_registration_id=reg.id,
            filing_period_id=period.id,
            user_id=user.id,
            period=period.period,
            invoice_number=data.invoice_number.strip().upper(),
            normalized_invoice_number=norm_num,
            invoice_date=str(data.invoice_date),
            customer_gstin=data.customer_gstin.strip().upper()
            if data.customer_gstin
            else None,
            customer_name=data.customer_name.strip(),
            place_of_supply=data.place_of_supply.strip(),
            invoice_type=data.invoice_type,
            supply_type="INTRA_STATE"
            if data.place_of_supply.strip() == reg.state_code.strip()
            else "INTER_STATE",
            taxable_value=data.taxable_value,
            tax_rate=data.tax_rate,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            cess_amount=cess,
            total_amount=total_amount,
            reverse_charge=data.reverse_charge,
            original_invoice_number=data.original_invoice_number,
            hsn_code=data.hsn_code,
            description=data.description,
            validation_status="VALID" if is_valid else "ERROR",
            validation_errors=json.dumps(val_errors) if val_errors else None,
            validation_issues=json.dumps(
                [
                    issue.model_dump() if hasattr(issue, "model_dump") else issue
                    for issue in structured_issues
                ]
            )
            if structured_issues
            else None,
        )
        db.add(inv)

        # Invalidate existing GSTR-1 and GSTR-3B snapshots so they are flagged as stale
        g1 = db.query(GSTR1Summary).filter(GSTR1Summary.period_id == period.id).first()
        if g1:
            g1.is_stale = True
        g3 = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        if g3:
            g3.is_stale = True

        db.flush()

        cls._log_audit(
            db,
            user,
            action="gst_sales_invoice_created",
            target_name=inv.invoice_number,
            summary=f"Added sales invoice {inv.invoice_number} of value ₹{inv.total_amount}",
        )
        db.commit()
        db.refresh(inv)
        return inv

    @classmethod
    def get_sales_invoices(
        cls, db: Session, user: User, period_id: str, invoice_type: Optional[str] = None
    ) -> List[GSTSalesInvoice]:
        period = cls.get_scoped_period(db, user, period_id)
        query = db.query(GSTSalesInvoice).filter(GSTSalesInvoice.period_id == period.id)
        if invoice_type:
            query = query.filter(GSTSalesInvoice.invoice_type == invoice_type)
        return query.order_by(desc(GSTSalesInvoice.invoice_date)).all()

    @classmethod
    def delete_sales_invoice(cls, db: Session, user: User, invoice_id: str):
        inv = db.query(GSTSalesInvoice).filter(GSTSalesInvoice.id == invoice_id).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Sales invoice not found"
            )
        period = cls.get_scoped_period(db, user, inv.period_id)
        cls._verify_period_editable(period)

        inv_num = inv.invoice_number
        db.delete(inv)

        # Invalidate summaries
        g1 = db.query(GSTR1Summary).filter(GSTR1Summary.period_id == period.id).first()
        if g1:
            g1.is_stale = True
        g3 = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        if g3:
            g3.is_stale = True

        cls._log_audit(
            db,
            user,
            action="gst_sales_invoice_deleted",
            target_name=inv_num,
            summary=f"Deleted sales invoice {inv_num}",
        )
        db.commit()

    # =========================================================================
    # Purchase Invoices (Books Register)
    # =========================================================================

    @classmethod
    def create_purchase_invoice(
        cls, db: Session, user: User, data: GSTPurchaseInvoiceCreate
    ) -> GSTPurchaseInvoice:
        period = cls.get_scoped_period(db, user, data.period_id)
        cls._verify_period_editable(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        # Validate supplier GSTIN
        is_sup_valid, sup_err = validate_gstin(data.supplier_gstin)
        if not is_sup_valid:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=sup_err)

        norm_num = normalize_invoice_number(data.invoice_number)

        # Check duplicate
        existing = (
            db.query(GSTPurchaseInvoice)
            .filter(
                GSTPurchaseInvoice.period_id == period.id,
                GSTPurchaseInvoice.supplier_gstin
                == data.supplier_gstin.strip().upper(),
                (
                    GSTPurchaseInvoice.invoice_number
                    == data.invoice_number.strip().upper()
                )
                | (GSTPurchaseInvoice.normalized_invoice_number == norm_num),
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Purchase invoice '{data.invoice_number}' for supplier '{data.supplier_gstin}' already exists in period.",
            )

        # Handle tax split
        cgst = data.cgst_amount
        sgst = data.sgst_amount
        igst = data.igst_amount
        cess = data.cess_amount

        if data.auto_calculate_tax:
            tax_split = calculate_tax_split(
                place_of_supply=data.place_of_supply,
                supplier_state=data.supplier_gstin[:2],
                taxable_value=data.taxable_value,
                tax_rate=data.tax_rate,
            )
            cgst = tax_split["cgst_amount"]
            sgst = tax_split["sgst_amount"]
            igst = tax_split["igst_amount"]
            total_amount = round_currency(
                data.taxable_value + cgst + sgst + igst + cess
            )
        else:
            total_amount = data.total_amount

        inv = GSTPurchaseInvoice(
            gst_registration_id=reg.id,
            filing_period_id=period.id,
            user_id=user.id,
            period=period.period,
            invoice_number=data.invoice_number.strip().upper(),
            normalized_invoice_number=norm_num,
            invoice_date=str(data.invoice_date),
            supplier_gstin=data.supplier_gstin.strip().upper(),
            supplier_name=data.supplier_name.strip(),
            place_of_supply=data.place_of_supply.strip(),
            supply_type="INTRA_STATE"
            if data.place_of_supply.strip() == reg.state_code.strip()
            else "INTER_STATE",
            invoice_type="B2B",
            reverse_charge=data.reverse_charge,
            taxable_value=data.taxable_value,
            tax_rate=data.tax_rate,
            cgst_amount=cgst,
            sgst_amount=sgst,
            igst_amount=igst,
            cess_amount=cess,
            total_amount=total_amount,
            itc_eligibility=data.itc_eligibility,
            itc_category=data.itc_category,
            hsn_code=data.hsn_code,
            notes=data.notes,
            match_status=MatchStatus.BOOKS_ONLY.value,
        )
        db.add(inv)

        # Invalidate GSTR-3B summary
        g3 = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        if g3:
            g3.is_stale = True

        db.flush()

        cls._log_audit(
            db,
            user,
            action="gst_purchase_invoice_created",
            target_name=inv.invoice_number,
            summary=f"Added purchase invoice {inv.invoice_number} from {inv.supplier_name}",
        )
        db.commit()
        db.refresh(inv)
        return inv

    @classmethod
    def get_purchase_invoices(
        cls, db: Session, user: User, period_id: str
    ) -> List[GSTPurchaseInvoice]:
        period = cls.get_scoped_period(db, user, period_id)
        return (
            db.query(GSTPurchaseInvoice)
            .filter(GSTPurchaseInvoice.period_id == period.id)
            .order_by(desc(GSTPurchaseInvoice.invoice_date))
            .all()
        )

    @classmethod
    def delete_purchase_invoice(cls, db: Session, user: User, invoice_id: str):
        inv = (
            db.query(GSTPurchaseInvoice)
            .filter(GSTPurchaseInvoice.id == invoice_id)
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Purchase invoice not found",
            )
        period = cls.get_scoped_period(db, user, inv.period_id)
        cls._verify_period_editable(period)

        inv_num = inv.invoice_number
        db.delete(inv)

        # Invalidate GSTR-3B summary
        g3 = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        if g3:
            g3.is_stale = True

        cls._log_audit(
            db,
            user,
            action="gst_purchase_invoice_deleted",
            target_name=inv_num,
            summary=f"Deleted purchase invoice {inv_num}",
        )
        db.commit()

    # =========================================================================
    # GSTR-2B External Records
    # =========================================================================

    @classmethod
    def import_gstr2b_records(
        cls,
        db: Session,
        user: User,
        period_id: str,
        records_data: List[GSTR2BRecordCreate],
        payload_checksum: Optional[str] = None,
    ) -> int:
        period = cls.get_scoped_period(db, user, period_id)
        cls._verify_period_not_locked(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        # Enforce batch payload limits (max 5,000 records)
        if len(records_data) > 5000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Batch import exceeds limit of 5,000 records per upload.",
            )

        # Calculate payload checksum
        raw_repr = []
        for r in records_data:
            d = r.model_dump(mode="json") if hasattr(r, "model_dump") else r.dict()
            raw_repr.append(d)
        serialized_payload = json.dumps(raw_repr, sort_keys=True, default=str)
        calculated_checksum = hashlib.sha256(
            serialized_payload.encode("utf-8")
        ).hexdigest()
        final_checksum = payload_checksum or calculated_checksum

        count = 0
        for r in records_data:
            # Validate supplier GSTIN format
            is_valid_gstin, g_err = validate_gstin(r.supplier_gstin)
            if not is_valid_gstin:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid supplier GSTIN '{r.supplier_gstin}' in GSTR-2B record: {g_err}",
                )

            norm_num = normalize_invoice_number(r.invoice_number)
            raw_record_json = json.dumps(
                r.model_dump(mode="json") if hasattr(r, "model_dump") else r.dict(),
                default=str,
            )

            # Upsert or ignore duplicate GSTR-2B entry
            existing = (
                db.query(GSTR2BRecord)
                .filter(
                    GSTR2BRecord.period_id == period.id,
                    GSTR2BRecord.supplier_gstin == r.supplier_gstin.strip().upper(),
                    (GSTR2BRecord.invoice_number == r.invoice_number.strip().upper())
                    | (GSTR2BRecord.normalized_invoice_number == norm_num),
                )
                .first()
            )

            itc_avail_bool = (
                (r.itc_available.upper() == "YES")
                if isinstance(r.itc_available, str)
                else bool(r.itc_available)
            )

            if existing:
                existing.taxable_value = r.taxable_value
                existing.tax_rate = r.tax_rate
                existing.cgst_amount = r.cgst_amount
                existing.sgst_amount = r.sgst_amount
                existing.igst_amount = r.igst_amount
                existing.cess_amount = r.cess_amount
                existing.total_amount = r.total_amount
                existing.itc_available = itc_avail_bool
                existing.supplier_filing_status = r.supplier_filing_status
                existing.import_checksum = final_checksum
                existing.uploader_id = user.id
                existing.raw_payload = raw_record_json
            else:
                new_rec = GSTR2BRecord(
                    gst_registration_id=reg.id,
                    filing_period_id=period.id,
                    user_id=user.id,
                    period=period.period,
                    supplier_gstin=r.supplier_gstin.strip().upper(),
                    supplier_name=r.supplier_name.strip(),
                    invoice_number=r.invoice_number.strip().upper(),
                    normalized_invoice_number=norm_num,
                    invoice_type=r.invoice_type,
                    invoice_date=str(r.invoice_date),
                    taxable_value=r.taxable_value,
                    tax_rate=r.tax_rate,
                    cgst_amount=r.cgst_amount,
                    sgst_amount=r.sgst_amount,
                    igst_amount=r.igst_amount,
                    cess_amount=r.cess_amount,
                    total_amount=r.total_amount,
                    place_of_supply=r.place_of_supply.strip(),
                    reverse_charge=r.reverse_charge,
                    itc_available=itc_avail_bool,
                    itc_reason=r.itc_reason,
                    supplier_filing_date=str(r.supplier_filing_date)
                    if r.supplier_filing_date
                    else None,
                    supplier_filing_status=r.supplier_filing_status,
                    match_status=MatchStatus.RETURN_ONLY.value,
                    import_checksum=final_checksum,
                    uploader_id=user.id,
                    raw_payload=raw_record_json,
                )
                db.add(new_rec)
            count += 1

        cls._log_audit(
            db,
            user,
            action="gstr2b_records_imported",
            target_name=f"{reg.gstin} - {period.period}",
            summary=f"Imported/Updated {count} external GSTR-2B records for {period.period}",
        )
        db.commit()
        return count

    @classmethod
    def get_gstr2b_records(
        cls, db: Session, user: User, period_id: str
    ) -> List[GSTR2BRecord]:
        period = cls.get_scoped_period(db, user, period_id)
        return (
            db.query(GSTR2BRecord)
            .filter(GSTR2BRecord.period_id == period.id)
            .order_by(desc(GSTR2BRecord.invoice_date))
            .all()
        )

    # =========================================================================
    # GSTR-1 Aggregation & Statutory Summary
    # =========================================================================

    @classmethod
    def generate_gstr1_summary(
        cls, db: Session, user: User, period_id: str
    ) -> GSTR1Summary:
        period = cls.get_scoped_period(db, user, period_id)
        cls._verify_period_not_locked(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        sales = (
            db.query(GSTSalesInvoice)
            .filter(GSTSalesInvoice.period_id == period.id)
            .all()
        )
        summary_dict = aggregate_gstr1(sales)
        source_hash = compute_gstr1_source_hash(sales)

        existing = (
            db.query(GSTR1Summary).filter(GSTR1Summary.period_id == period.id).first()
        )
        valid_cols = {c.name for c in GSTR1Summary.__table__.columns}
        filtered = {k: v for k, v in summary_dict.items() if k in valid_cols}

        now_utc = datetime.now(timezone.utc)
        if existing:
            new_ver = (existing.calculation_version or 1) + 1
            existing.calculation_version = new_ver
            existing.source_record_count = len(sales)
            existing.source_data_hash = source_hash
            existing.is_stale = False
            existing.calculated_at = now_utc
            existing.calculation_metadata = json.dumps(
                {
                    "version": new_ver,
                    "calculated_by": user.email,
                    "calculated_at": now_utc.isoformat(),
                    "invoices_count": len(sales),
                }
            )
            for k, v in filtered.items():
                setattr(existing, k, v)
            summary_obj = existing
        else:
            summary_obj = GSTR1Summary(
                gst_registration_id=reg.id,
                filing_period_id=period.id,
                period=period.period,
                calculation_version=1,
                source_record_count=len(sales),
                source_data_hash=source_hash,
                is_stale=False,
                calculated_at=now_utc,
                calculation_metadata=json.dumps(
                    {
                        "version": 1,
                        "calculated_by": user.email,
                        "calculated_at": now_utc.isoformat(),
                        "invoices_count": len(sales),
                    }
                ),
                **filtered,
            )
            db.add(summary_obj)

        cls._log_audit(
            db,
            user,
            action="gstr1_summary_recalculated",
            target_name=period.period,
            summary=f"Aggregated GSTR-1 v{summary_obj.calculation_version} for {len(sales)} invoices. Total Taxable: ₹{summary_dict['total_taxable_value']}",
        )
        db.commit()
        db.refresh(summary_obj)
        return summary_obj

    @classmethod
    def get_gstr1_summary(cls, db: Session, user: User, period_id: str) -> GSTR1Summary:
        period = cls.get_scoped_period(db, user, period_id)
        summary_obj = (
            db.query(GSTR1Summary).filter(GSTR1Summary.period_id == period.id).first()
        )
        if not summary_obj:
            # Auto-generate if not existing yet
            summary_obj = cls.generate_gstr1_summary(db, user, period_id)
        else:
            # Detect staleness against current database records
            sales = (
                db.query(GSTSalesInvoice)
                .filter(GSTSalesInvoice.period_id == period.id)
                .all()
            )
            curr_hash = compute_gstr1_source_hash(sales)
            if summary_obj.source_data_hash != curr_hash:
                summary_obj.is_stale = True
                db.commit()
                db.refresh(summary_obj)
        return summary_obj

    # =========================================================================
    # GSTR-3B Computation & Statutory Set-off
    # =========================================================================

    @classmethod
    def generate_gstr3b_summary(
        cls, db: Session, user: User, period_id: str
    ) -> GSTR3BSummary:
        period = cls.get_scoped_period(db, user, period_id)
        cls._verify_period_not_locked(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        sales = (
            db.query(GSTSalesInvoice)
            .filter(GSTSalesInvoice.period_id == period.id)
            .all()
        )
        purchases = (
            db.query(GSTPurchaseInvoice)
            .filter(GSTPurchaseInvoice.period_id == period.id)
            .all()
        )

        calc_dict = calculate_gstr3b(sales_invoices=sales, purchase_invoices=purchases)
        source_hash = compute_gstr3b_source_hash(sales, purchases)

        existing = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        valid_cols = {c.name for c in GSTR3BSummary.__table__.columns}
        filtered = {k: v for k, v in calc_dict.items() if k in valid_cols}

        now_utc = datetime.now(timezone.utc)
        if existing:
            new_ver = (existing.calculation_version or 1) + 1
            existing.calculation_version = new_ver
            existing.source_record_count = len(sales) + len(purchases)
            existing.source_data_hash = source_hash
            existing.is_stale = False
            existing.calculated_at = now_utc
            existing.set_off_details = (
                json.dumps(calc_dict.get("utilization"))
                if calc_dict.get("utilization")
                else None
            )
            existing.calculation_metadata = json.dumps(
                {
                    "version": new_ver,
                    "calculated_by": user.email,
                    "calculated_at": now_utc.isoformat(),
                    "sales_count": len(sales),
                    "purchases_count": len(purchases),
                }
            )
            for k, v in filtered.items():
                setattr(existing, k, v)
            summary_obj = existing
        else:
            summary_obj = GSTR3BSummary(
                gst_registration_id=reg.id,
                filing_period_id=period.id,
                period=period.period,
                calculation_version=1,
                source_record_count=len(sales) + len(purchases),
                source_data_hash=source_hash,
                is_stale=False,
                calculated_at=now_utc,
                set_off_details=json.dumps(calc_dict.get("utilization"))
                if calc_dict.get("utilization")
                else None,
                calculation_metadata=json.dumps(
                    {
                        "version": 1,
                        "calculated_by": user.email,
                        "calculated_at": now_utc.isoformat(),
                        "sales_count": len(sales),
                        "purchases_count": len(purchases),
                    }
                ),
                **filtered,
            )
            db.add(summary_obj)

        cls._log_audit(
            db,
            user,
            action="gstr3b_summary_recalculated",
            target_name=period.period,
            summary=f"Computed GSTR-3B v{summary_obj.calculation_version}. Outward IGST: ₹{calc_dict['outward_igst']}, Net ITC IGST: ₹{calc_dict['net_itc_igst']}",
        )
        db.commit()
        db.refresh(summary_obj)
        return summary_obj

    @classmethod
    def get_gstr3b_summary(
        cls, db: Session, user: User, period_id: str
    ) -> GSTR3BSummary:
        period = cls.get_scoped_period(db, user, period_id)
        summary_obj = (
            db.query(GSTR3BSummary).filter(GSTR3BSummary.period_id == period.id).first()
        )
        if not summary_obj:
            summary_obj = cls.generate_gstr3b_summary(db, user, period_id)
        else:
            # Detect staleness against current database records
            sales = (
                db.query(GSTSalesInvoice)
                .filter(GSTSalesInvoice.period_id == period.id)
                .all()
            )
            purchases = (
                db.query(GSTPurchaseInvoice)
                .filter(GSTPurchaseInvoice.period_id == period.id)
                .all()
            )
            curr_hash = compute_gstr3b_source_hash(sales, purchases)
            if summary_obj.source_data_hash != curr_hash:
                summary_obj.is_stale = True
                db.commit()
                db.refresh(summary_obj)
        return summary_obj

    # =========================================================================
    # GSTR-2B vs Purchase Register Reconciliation
    # =========================================================================

    @classmethod
    def run_reconciliation(
        cls, db: Session, user: User, period_id: str, params: ReconciliationRunRequest
    ) -> List[GSTReconciliationResult]:
        period = cls.get_scoped_period(db, user, period_id)
        cls._verify_period_not_locked(period)
        reg = cls.get_scoped_registration(db, user, period.registration_id)

        books = (
            db.query(GSTPurchaseInvoice)
            .filter(GSTPurchaseInvoice.period_id == period.id)
            .all()
        )
        returns_2b = (
            db.query(GSTR2BRecord).filter(GSTR2BRecord.period_id == period.id).all()
        )

        matches = reconcile_purchases_with_gstr2b(
            books_invoices=books,
            gstr2b_records=returns_2b,
            date_tolerance_days=params.date_tolerance_days,
            exact_tolerance_inr=params.exact_tolerance_inr,
            partial_tolerance_inr=params.partial_tolerance_inr,
        )

        # Preserve existing manual decisions (e.g. ACCEPTED, REJECTED, FORCE_MATCH)
        existing_decisions = {}
        for r in (
            db.query(GSTReconciliationResult)
            .filter(GSTReconciliationResult.period_id == period.id)
            .all()
        ):
            if r.status and r.status != ReconciliationDecision.PENDING.value:
                key = (r.purchase_invoice_id, r.gstr2b_record_id)
                existing_decisions[key] = (r.status, r.accountant_notes)

        # Clear existing reconciliation results for this period
        db.query(GSTReconciliationResult).filter(
            GSTReconciliationResult.period_id == period.id
        ).delete()

        created_results = []
        for m in matches:
            key = (m.purchase_invoice_id, m.gstr2b_record_id)
            prev_status, prev_notes = existing_decisions.get(
                key, (ReconciliationDecision.PENDING.value, m.notes)
            )
            decision_preserved = key in existing_decisions

            res = GSTReconciliationResult(
                gst_registration_id=reg.id,
                filing_period_id=period.id,
                user_id=user.id,
                period=period.period,
                purchase_invoice_id=m.purchase_invoice_id,
                gstr2b_record_id=m.gstr2b_record_id,
                match_type=m.match_status.value,
                matching_method="automated_exact"
                if m.match_status == MatchStatus.EXACT_MATCH
                else "automated_partial",
                amount_tolerance=params.exact_tolerance_inr,
                date_tolerance_days=params.date_tolerance_days,
                manual_decision_preserved=decision_preserved,
                match_score=m.confidence_score,
                taxable_difference=m.taxable_difference,
                tax_difference=m.tax_difference,
                mismatch_reasons=json.dumps(m.difference_reasons)
                if m.difference_reasons
                else None,
                status=prev_status,
                accountant_notes=prev_notes,
            )
            db.add(res)
            created_results.append(res)

            # Update status on invoices
            if m.purchase_invoice_id:
                b_inv = next((b for b in books if b.id == m.purchase_invoice_id), None)
                if b_inv:
                    b_inv.match_status = m.match_status.value
            if m.gstr2b_record_id:
                r_2b = next((r for r in returns_2b if r.id == m.gstr2b_record_id), None)
                if r_2b:
                    r_2b.match_status = m.match_status.value

        period.gstr2b_status = "reconciled"
        cls._log_audit(
            db,
            user,
            action="gstr2b_reconciliation_executed",
            target_name=period.period,
            summary=f"Reconciled {len(books)} books invoices with {len(returns_2b)} GSTR-2B records. Created {len(matches)} match results. Preserved {len(existing_decisions)} manual decisions.",
        )
        db.commit()

        return (
            db.query(GSTReconciliationResult)
            .filter(GSTReconciliationResult.period_id == period.id)
            .all()
        )

    @classmethod
    def get_reconciliation_results(
        cls, db: Session, user: User, period_id: str, match_status: Optional[str] = None
    ) -> List[GSTReconciliationResult]:
        period = cls.get_scoped_period(db, user, period_id)
        query = db.query(GSTReconciliationResult).filter(
            GSTReconciliationResult.period_id == period.id
        )
        if match_status:
            query = query.filter(GSTReconciliationResult.match_status == match_status)
        return query.all()

    @classmethod
    def update_reconciliation_decision(
        cls,
        db: Session,
        user: User,
        result_id: str,
        data: ReconciliationDecisionRequest,
    ) -> GSTReconciliationResult:
        res = (
            db.query(GSTReconciliationResult)
            .filter(GSTReconciliationResult.id == result_id)
            .first()
        )
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Reconciliation result not found",
            )

        period = cls.get_scoped_period(db, user, res.period_id)
        cls._verify_period_not_locked(period)

        res.decision_status = data.decision
        if data.notes:
            res.accountant_notes = data.notes

        cls._log_audit(
            db,
            user,
            action="reconciliation_decision_updated",
            target_name=res.id,
            summary=f"Updated match decision to {data.decision}. Notes: {data.notes or 'None'}",
        )
        db.commit()
        db.refresh(res)
        return res

    @classmethod
    def get_reconciliation_summary(
        cls, db: Session, user: User, period_id: str
    ) -> Dict[str, Any]:
        period = cls.get_scoped_period(db, user, period_id)
        results = (
            db.query(GSTReconciliationResult)
            .filter(GSTReconciliationResult.period_id == period.id)
            .all()
        )

        exact_cnt = 0
        partial_cnt = 0
        books_only_cnt = 0
        return_only_cnt = 0
        excluded_cnt = 0

        tot_books_tax = Decimal("0.00")
        tot_2b_tax = Decimal("0.00")
        matched_tax = Decimal("0.00")
        mismatch_tax = Decimal("0.00")
        books_only_tax = Decimal("0.00")
        return_only_tax = Decimal("0.00")

        for r in results:
            if r.match_status == MatchStatus.EXACT_MATCH.value:
                exact_cnt += 1
                if r.purchase_invoice:
                    tax = (
                        r.purchase_invoice.cgst_amount
                        + r.purchase_invoice.sgst_amount
                        + r.purchase_invoice.igst_amount
                        + r.purchase_invoice.cess_amount
                    )
                    matched_tax += tax
                    tot_books_tax += tax
                if r.gstr2b_record:
                    tot_2b_tax += (
                        r.gstr2b_record.cgst_amount
                        + r.gstr2b_record.sgst_amount
                        + r.gstr2b_record.igst_amount
                        + r.gstr2b_record.cess_amount
                    )
            elif r.match_status == MatchStatus.PARTIAL_MATCH.value:
                partial_cnt += 1
                if r.purchase_invoice:
                    tax = (
                        r.purchase_invoice.cgst_amount
                        + r.purchase_invoice.sgst_amount
                        + r.purchase_invoice.igst_amount
                        + r.purchase_invoice.cess_amount
                    )
                    tot_books_tax += tax
                if r.gstr2b_record:
                    tot_2b_tax += (
                        r.gstr2b_record.cgst_amount
                        + r.gstr2b_record.sgst_amount
                        + r.gstr2b_record.igst_amount
                        + r.gstr2b_record.cess_amount
                    )
                mismatch_tax += r.tax_difference
            elif r.match_status == MatchStatus.BOOKS_ONLY.value:
                books_only_cnt += 1
                if r.purchase_invoice:
                    tax = (
                        r.purchase_invoice.cgst_amount
                        + r.purchase_invoice.sgst_amount
                        + r.purchase_invoice.igst_amount
                        + r.purchase_invoice.cess_amount
                    )
                    books_only_tax += tax
                    tot_books_tax += tax
            elif r.match_status == MatchStatus.RETURN_ONLY.value:
                return_only_cnt += 1
                if r.gstr2b_record:
                    tax = (
                        r.gstr2b_record.cgst_amount
                        + r.gstr2b_record.sgst_amount
                        + r.gstr2b_record.igst_amount
                        + r.gstr2b_record.cess_amount
                    )
                    return_only_tax += tax
                    tot_2b_tax += tax
            elif r.match_status == MatchStatus.EXCLUDED.value:
                excluded_cnt += 1

        return {
            "total_records": len(results),
            "exact_matches": exact_cnt,
            "partial_matches": partial_cnt,
            "books_only": books_only_cnt,
            "return_only": return_only_cnt,
            "excluded": excluded_cnt,
            "total_books_tax": round_currency(tot_books_tax),
            "total_2b_tax": round_currency(tot_2b_tax),
            "matched_tax": round_currency(matched_tax),
            "mismatch_tax": round_currency(mismatch_tax),
            "books_only_tax": round_currency(books_only_tax),
            "return_only_tax": round_currency(return_only_tax),
        }
