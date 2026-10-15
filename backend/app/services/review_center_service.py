import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.history import HistoryRecord
from app.models.reconciliation import CorrectionProposal, ReconciliationSession
from app.modules.reconciliation.correction_service import CorrectionService
from app.modules.reconciliation.schemas import CorrectionDecisionRequest, CorrectionStatusEnum
from app.modules.reconciliation.workbook_inspector import WorkbookInspector, format_indian_currency
from app.schemas.review_center import FindingDecisionRequest, ReviewCenterSummary, ReviewFindingItem
from app.services.history_service import HistoryService

logger = logging.getLogger(__name__)

# In-memory inspection cache: (document_id, checksum) -> (timestamp, inspection_result)
_INSPECTION_CACHE: Dict[str, Tuple[float, Any]] = {}


def safe_to_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.replace("₹", "").replace("Rs.", "").replace("Rs", "").replace(",", "").strip()
        try:
            return float(cleaned)
        except Exception:
            return None
    return None


class ReviewCenterService:
    @classmethod
    def _inspect_document_cached(cls, doc: Document):
        file_path = Path(doc.file_path)
        if not file_path.exists():
            return None

        cache_key = f"{doc.id}_{doc.checksum or ''}"
        mtime = file_path.stat().st_mtime
        if cache_key in _INSPECTION_CACHE:
            cached_mtime, cached_res = _INSPECTION_CACHE[cache_key]
            if cached_mtime == mtime:
                return cached_res

        try:
            result = WorkbookInspector.inspect(str(file_path), doc.original_filename)
            _INSPECTION_CACHE[cache_key] = (mtime, result)
            return result
        except Exception as e:
            logger.warning(f"Failed to inspect document {doc.id} ({doc.original_filename}): {e}")
            return None

    @classmethod
    def get_findings(
        cls,
        db: Session,
        user_id: Optional[int] = None,
        severity_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        document_id_filter: Optional[int] = None,
        search_query: Optional[str] = None,
    ) -> ReviewCenterSummary:
        findings: List[ReviewFindingItem] = []

        # 1. Fetch user documents (limit to recent 20)
        doc_query = db.query(Document)
        if user_id is not None:
            doc_query = doc_query.filter(Document.user_id == user_id)
        if document_id_filter is not None:
            doc_query = doc_query.filter(Document.id == document_id_filter)
        user_docs = doc_query.order_by(Document.created_at.desc()).limit(20).all()
        doc_map = {d.id: d for d in user_docs}

        # 2. Fetch correction proposals
        prop_query = db.query(CorrectionProposal)
        if user_id is not None:
            prop_query = prop_query.filter(CorrectionProposal.user_id == user_id)
        if document_id_filter is not None:
            prop_query = prop_query.filter(CorrectionProposal.document_id == document_id_filter)
        proposals = prop_query.order_by(CorrectionProposal.created_at.desc()).all()

        # Track proposals by (document_id, cell_address) or id to avoid duplicate findings
        proposal_cids = set()

        seen_cids = set()
        for p in proposals:
            if p.correction_id in seen_cids:
                continue
            seen_cids.add(p.correction_id)
            doc = doc_map.get(p.document_id) if p.document_id else None
            doc_name = doc.original_filename if doc else (f"Session {p.session_id}" if p.session_id else "Reconciliation")
            proposal_cids.add(p.correction_id)

            # Map status
            current_status = "NEEDS_REVIEW"
            if p.status == "CONFIRMED" or p.status == "APPROVED":
                current_status = "APPROVED"
            elif p.status == "REJECTED":
                current_status = "REJECTED"
            elif p.status == "GENERATED":
                current_status = "CORRECTED"
            elif p.status == "MANUAL_REVIEW":
                current_status = "UNDER_REVIEW"
            elif p.status == "PROPOSED":
                current_status = "REVIEW_REQUIRED" if p.confidence in ("LOW", "REVIEW_REQUIRED") else "NEEDS_REVIEW"

            sev = "HIGH"
            if p.confidence == "MEDIUM":
                sev = "MEDIUM"
            elif p.confidence == "LOW":
                sev = "LOW"

            evidence_list = []
            if p.evidence_json:
                try:
                    evidence_list = json.loads(p.evidence_json)
                except Exception:
                    evidence_list = []

            recs_list = []
            if p.recommended_verification_json:
                try:
                    recs_list = json.loads(p.recommended_verification_json)
                except Exception:
                    recs_list = []

            findings.append(
                ReviewFindingItem(
                    id=p.correction_id,
                    document_id=p.document_id,
                    document_name=doc_name,
                    session_id=p.session_id,
                    category=doc.category if doc else "reconciliation",
                    financial_period=None,
                    type=p.reason_category,
                    severity=sev,
                    status=current_status,
                    title=f"{p.field} Discrepancy — {p.reason_category}",
                    description=p.explanation,
                    expected_value=float(p.proposed_value) if p.proposed_value and p.proposed_value.replace('.', '', 1).isdigit() else None,
                    actual_value=float(p.original_value) if p.original_value and p.original_value.replace('.', '', 1).isdigit() else None,
                    difference=p.difference,
                    currency="INR",
                    sheet_name=p.sheet_name,
                    cell_address=p.cell_address,
                    row_reference=str(p.row_reference),
                    confidence=p.confidence,
                    proven_cause=None,
                    possible_causes=[p.explanation] if p.explanation else [],
                    ai_explanation="AI proposal is based on reconciliation rules and requires explicit accountant approval.",
                    recommended_actions=recs_list,
                    correction_id=p.correction_id,
                    original_value_display=str(p.original_value or ""),
                    proposed_value_display=str(p.proposed_value or ""),
                    created_at=p.created_at.isoformat() if p.created_at else None,
                    reviewed_at=p.reviewed_at.isoformat() if p.reviewed_at else None,
                    accountant_decision=p.accountant_decision or p.status,
                    decision_notes=p.decision_notes,
                )
            )

        # 3. Inspect user documents for financial discrepancies
        spreadsheet_extensions = ('.xlsx', '.xls', '.csv')
        for doc in user_docs[:10]:
            if not any(doc.original_filename.lower().endswith(ext) for ext in spreadsheet_extensions):
                continue
            inspection = cls._inspect_document_cached(doc)
            if not inspection:
                continue

            period_text = inspection.period_info.financial_year if inspection.period_info else None

            for d in getattr(inspection, "discrepancies", []):
                finding_id = f"doc_{doc.id}_{d.id}"

                # Determine if already handled by a proposal
                matching_prop = next(
                    (p for p in proposals if p.document_id == doc.id and p.cell_address == d.cell_address),
                    None
                )
                if matching_prop:
                    # Skip duplicate inspection item since proposal already listed
                    continue

                sev = d.severity.value.upper() if hasattr(d.severity, "value") else str(d.severity).upper()
                stat = d.status.value.upper() if hasattr(d.status, "value") else str(d.status).upper()
                if stat == "REVIEW_REQUIRED":
                    ui_status = "REVIEW_REQUIRED"
                elif stat == "OPEN":
                    ui_status = "NEEDS_REVIEW"
                else:
                    ui_status = stat

                diff_val = d.difference
                if diff_val is None and d.expected_value is not None and d.actual_value is not None:
                    diff_val = round(abs(d.actual_value - d.expected_value), 2)

                findings.append(
                    ReviewFindingItem(
                        id=finding_id,
                        document_id=doc.id,
                        document_name=doc.original_filename,
                        session_id=None,
                        category=doc.category,
                        financial_period=period_text,
                        type=d.type.value if hasattr(d.type, "value") else str(d.type),
                        severity=sev,
                        status=ui_status,
                        title=d.description.split(".")[0] if d.description else "Financial Discrepancy",
                        description=d.description,
                        expected_value=safe_to_float(d.expected_value),
                        actual_value=safe_to_float(d.actual_value),
                        difference=safe_to_float(diff_val),
                        currency=d.currency or "INR",
                        sheet_name=d.sheet_name,
                        cell_address=d.cell_address,
                        row_reference=None,
                        column_reference=None,
                        formula=None,
                        confidence=d.confidence or "Deterministic",
                        proven_cause=None,
                        possible_causes=d.possible_causes or [],
                        ai_explanation="Deterministic accounting discrepancy detected by rule verification. Explanation is advisory and requires accountant confirmation.",
                        recommended_actions=d.recommended_actions or [],
                        correction_id=None,
                        original_value_display=str(d.actual_value) if d.actual_value is not None else None,
                        proposed_value_display=str(d.expected_value) if d.expected_value is not None else None,
                        created_at=doc.created_at.isoformat() if doc.created_at else None,
                    )
                )

        # 4. Fetch GST Reconciliation Discrepancies
        try:
            from app.modules.gst.models import GSTReconciliationResult, GSTRegistration
            gst_query = db.query(GSTReconciliationResult).join(
                GSTRegistration, GSTReconciliationResult.gst_registration_id == GSTRegistration.id
            )
            if user_id is not None:
                gst_query = gst_query.filter(GSTRegistration.user_id == user_id)

            gst_results = (
                gst_query.filter(
                    (GSTReconciliationResult.match_type != "EXACT_MATCH")
                    | (GSTReconciliationResult.tax_difference != 0)
                )
                .order_by(GSTReconciliationResult.id.desc())
                .limit(50)
                .all()
            )

            for gr in gst_results:
                fid = f"gst_recon_{gr.id}"
                reg = gr.filing_period.registration if gr.filing_period else None
                reg_name = f"{reg.legal_name} ({reg.gstin})" if reg else "GST Return"

                inv_num = (
                    (gr.purchase_invoice.invoice_number if gr.purchase_invoice else None)
                    or (gr.gstr2b_record.invoice_number if gr.gstr2b_record else "N/A")
                )
                supp_name = (
                    (gr.gstr2b_record.supplier_name if gr.gstr2b_record else None)
                    or (gr.purchase_invoice.supplier_name if gr.purchase_invoice else "Vendor")
                )

                books_tax = 0.0
                if gr.purchase_invoice:
                    books_tax = float(
                        (getattr(gr.purchase_invoice, "igst_amount", 0) or 0)
                        + (getattr(gr.purchase_invoice, "cgst_amount", 0) or 0)
                        + (getattr(gr.purchase_invoice, "sgst_amount", 0) or 0)
                    )

                gstr_tax = 0.0
                if gr.gstr2b_record:
                    gstr_tax = float(
                        (getattr(gr.gstr2b_record, "igst_amount", 0) or 0)
                        + (getattr(gr.gstr2b_record, "cgst_amount", 0) or 0)
                        + (getattr(gr.gstr2b_record, "sgst_amount", 0) or 0)
                    )

                diff_val = float(gr.tax_difference) if gr.tax_difference is not None else abs(books_tax - gstr_tax)

                sev = "HIGH" if diff_val > 500 or gr.match_type in ("BOOKS_ONLY", "RETURN_ONLY") else "MEDIUM"

                if gr.status in ("ACCEPTED", "MANUAL_MATCHED"):
                    stat = "APPROVED"
                elif gr.status == "REJECTED":
                    stat = "REJECTED"
                elif gr.status == "EXCLUDED":
                    stat = "IGNORED"
                else:
                    stat = "REVIEW_REQUIRED"

                mismatch_desc = (
                    f"GSTR-2B vs Purchase Book Variance on Invoice {inv_num} ({supp_name}). "
                    f"Books Tax: ₹{books_tax:,.2f}, 2B Tax: ₹{gstr_tax:,.2f}, Variance: ₹{diff_val:,.2f}."
                )

                findings.append(
                    ReviewFindingItem(
                        id=fid,
                        document_id=None,
                        document_name=f"GSTR-2B Recon ({gr.period}) - {reg_name}",
                        session_id=None,
                        category="gst",
                        financial_period=gr.period,
                        type=f"GST_{gr.match_type}",
                        severity=sev,
                        status=stat,
                        title=f"GST ITC Mismatch — {gr.match_type.replace('_', ' ').title()} ({inv_num})",
                        description=mismatch_desc,
                        expected_value=gstr_tax,
                        actual_value=books_tax,
                        difference=diff_val,
                        currency="INR",
                        sheet_name="GSTR-2B",
                        cell_address=inv_num,
                        row_reference=inv_num,
                        column_reference=None,
                        formula=None,
                        confidence=f"{float(gr.match_score):.0f}% Match",
                        proven_cause=None,
                        possible_causes=[
                            "Timing difference between supplier GSTR-1 portal filing and internal purchase invoice posting.",
                            "Supplier filed with incorrect tax rate or GSTIN.",
                            "Invoice missing in GSTR-2B or missing in purchase book register.",
                        ],
                        ai_explanation="Statutory reconciliation variance between purchase register and GSTR-2B. Requires accountant verification before finalizing GSTR-3B ITC claims.",
                        recommended_actions=[
                            "Check original tax invoice from supplier.",
                            "Verify supplier GSTR-1 filing status on GST portal.",
                            "Accept, reject, or mark as force match.",
                        ],
                        correction_id=None,
                        original_value_display=f"₹{books_tax:,.2f}",
                        proposed_value_display=f"₹{gstr_tax:,.2f}",
                        created_at=gr.created_at.isoformat() if gr.created_at else None,
                        reviewed_at=gr.updated_at.isoformat() if gr.manual_decision_preserved and gr.updated_at else None,
                        accountant_decision=gr.status,
                        decision_notes=gr.accountant_notes,
                    )
                )
        except Exception as e:
            logger.warning(f"Error fetching GST review findings: {e}")

        # 5. Fetch ITR review findings (unresolved or reviewed ITR findings)
        try:
            from app.modules.itr.models import ITRFinding, ITRProfile
            itr_profiles = db.query(ITRProfile).filter(ITRProfile.user_id == user_id).all()
            profile_ids = [p.id for p in itr_profiles]
            profile_map = {p.id: p for p in itr_profiles}
            if profile_ids:
                itr_findings = (
                    db.query(ITRFinding)
                    .filter(ITRFinding.profile_id.in_(profile_ids))
                    .order_by(ITRFinding.created_at.desc())
                    .all()
                )
                for f in itr_findings:
                    prof = profile_map.get(f.profile_id)
                    pan_label = prof.pan if prof else "ITR"
                    ay_label = prof.assessment_year if prof else ""
                    causes = json.loads(f.possible_causes or "[]")
                    actions = json.loads(f.recommended_actions or "[]")
                    findings.append(
                        ReviewFindingItem(
                            id=f"itr_{f.id}",
                            document_name=f"ITR AY {ay_label} ({pan_label})",
                            category="ITR_TAX",
                            financial_period=ay_label,
                            type=f.finding_type,
                            severity=f.severity,
                            status=f.status,
                            title=f.title,
                            description=f.description,
                            expected_value=float(f.expected_value) if f.expected_value is not None else None,
                            actual_value=float(f.actual_value) if f.actual_value is not None else None,
                            difference=float(f.difference) if f.difference is not None else None,
                            currency="INR",
                            sheet_name=f.source_sheet or "ITR Preparation",
                            row_reference=str(f.source_row) if f.source_row else None,
                            confidence="Deterministic",
                            possible_causes=causes,
                            ai_explanation=f"Income Tax statutory review check for AY {ay_label}. Requires accountant verification prior to final approval.",
                            recommended_actions=actions,
                            created_at=f.created_at.isoformat() if f.created_at else None,
                            reviewed_at=f.reviewed_at.isoformat() if f.reviewed_at else None,
                            accountant_decision=f.accountant_decision,
                            decision_notes=f.decision_notes,
                        )
                    )
        except Exception as e:
            logger.warning(f"Error fetching ITR review findings: {e}")

        # 6. Fetch Financial Statement review findings
        try:
            from app.modules.financial_statements.models import (
                FinancialStatementFinding,
                FinancialStatementProfile,
            )
            fs_query = db.query(FinancialStatementFinding).join(
                FinancialStatementProfile,
                FinancialStatementFinding.profile_id == FinancialStatementProfile.id,
            )
            if user_id is not None:
                fs_query = fs_query.filter(FinancialStatementProfile.user_id == user_id)

            fs_findings = fs_query.order_by(FinancialStatementFinding.created_at.desc()).all()
            for f in fs_findings:
                prof = f.profile
                prof_name = prof.entity_name if prof else "Financial Statements"
                fy_label = prof.financial_year if prof else ""
                poss_causes = [f.possible_cause] if f.possible_cause else []

                findings.append(
                    ReviewFindingItem(
                        id=f"fs_{f.id}",
                        document_name=f"{prof_name} ({fy_label})",
                        category="FINANCIAL_STATEMENTS",
                        financial_period=fy_label,
                        type=f.finding_type,
                        severity=f.severity,
                        status=f.status,
                        title=f.title,
                        description=f.description,
                        expected_value=float(f.expected) if f.expected is not None else None,
                        actual_value=float(f.actual) if f.actual is not None else None,
                        difference=float(f.variance) if f.variance is not None else None,
                        currency="INR",
                        sheet_name=f.source_sheet or "Statements",
                        cell_address=f.source_cell,
                        row_reference=str(f.source_row) if f.source_row else None,
                        confidence="Deterministic",
                        proven_cause=f.proven_cause,
                        possible_causes=poss_causes,
                        ai_explanation="Financial statement statutory validation check. Accountant review and verification is required before statements can be approved.",
                        recommended_actions=[
                            "Inspect Trial Balance and Schedule III ledger accounts.",
                            "Verify Debit/Credit alignment and retained earnings transfer.",
                            "Record accountant review decision (Accept, Reject, Override).",
                        ],
                        created_at=f.created_at.isoformat() if f.created_at else None,
                        reviewed_at=f.reviewed_at.isoformat() if f.reviewed_at else None,
                        accountant_decision=f.accountant_decision,
                        decision_notes=f.decision_notes,
                    )
                )
        except Exception as e:
            logger.warning(f"Error fetching Financial Statements review findings: {e}")

        # 7. Filter
        filtered: List[ReviewFindingItem] = []
        for f in findings:
            if severity_filter and severity_filter.upper() != "ALL" and f.severity.upper() != severity_filter.upper():
                continue
            if status_filter and status_filter.upper() != "ALL":
                if status_filter.upper() == "REVIEWED" and f.status not in ("APPROVED", "REJECTED", "CORRECTED", "IGNORED"):
                    continue
                elif status_filter.upper() != "REVIEWED" and f.status.upper() != status_filter.upper():
                    continue
            if search_query:
                q = search_query.lower().strip()
                matches_text = (
                    q in f.title.lower()
                    or q in f.document_name.lower()
                    or q in (f.description or "").lower()
                    or q in (f.sheet_name or "").lower()
                    or q in (f.cell_address or "").lower()
                    or (f.difference is not None and q in str(f.difference))
                )
                if not matches_text:
                    continue
            filtered.append(f)

        # Summary counts
        all_count = len(findings)
        high_count = sum(1 for f in findings if f.severity in ("HIGH", "CRITICAL"))
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        low_count = sum(1 for f in findings if f.severity in ("LOW", "INFO"))
        review_required_count = sum(1 for f in findings if f.status in ("REVIEW_REQUIRED", "NEEDS_REVIEW", "UNDER_REVIEW"))
        reviewed_count = sum(1 for f in findings if f.status in ("APPROVED", "REJECTED", "CORRECTED", "IGNORED"))

        return ReviewCenterSummary(
            all_count=all_count,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
            review_required_count=review_required_count,
            reviewed_count=reviewed_count,
            findings=filtered,
        )

    @classmethod
    def update_finding_decision(
        cls,
        db: Session,
        finding_id: str,
        req: FindingDecisionRequest,
        user_id: Optional[int] = None,
    ) -> ReviewFindingItem:
        dec = req.decision.upper()
        notes = req.notes or ""

        # Check if finding_id is a CorrectionProposal
        prop = db.query(CorrectionProposal).filter(CorrectionProposal.correction_id == finding_id).first()
        if prop:
            if user_id is not None and prop.user_id is not None and prop.user_id != user_id:
                raise HTTPException(status_code=403, detail="Access denied.")

            dec_req = CorrectionDecisionRequest(decision=dec, notes=notes)
            updated = CorrectionService.update_proposal_decision(db, finding_id, dec_req, user_id=user_id)
            if not updated:
                raise HTTPException(status_code=404, detail="Proposal not found.")

            # Record history
            HistoryService.record_activity(
                db=db,
                user_id=user_id,
                module="review_center",
                action=f"finding_{dec.lower()}",
                target_name=f"Proposal {finding_id}",
                status="completed",
                result_summary=f"Accountant marked proposal {finding_id} as {dec}. Notes: {notes or 'None'}",
                user_action=f"Decision: {dec}",
                document_id=prop.document_id,
            )

            # Return refreshed item
            findings_sum = cls.get_findings(db, user_id=user_id)
            for f in findings_sum.findings:
                if f.id == finding_id:
                    return f
            raise HTTPException(status_code=404, detail="Finding not found after update.")

        # Document finding (e.g. doc_{id}_{disc_id})
        if finding_id.startswith("doc_"):
            parts = finding_id.split("_", 2)
            if len(parts) >= 3:
                doc_id = int(parts[1])
                disc_id = parts[2]
                doc = db.query(Document).filter(Document.id == doc_id).first()
                if not doc:
                    raise HTTPException(status_code=404, detail="Document not found.")
                if user_id is not None and doc.user_id is not None and doc.user_id != user_id:
                    raise HTTPException(status_code=403, detail="Access denied.")

                # If accountant wishes to propose correction from this finding:
                if req.propose_correction:
                    # Find inspection details
                    inspection = cls._inspect_document_cached(doc)
                    matched_disc = None
                    if inspection:
                        for d in getattr(inspection, "discrepancies", []):
                            if d.id == disc_id:
                                matched_disc = d
                                break

                    cell_addr = matched_disc.cell_address if matched_disc else None
                    sheet_name = matched_disc.sheet_name if matched_disc else "Sheet1"
                    orig_val = str(matched_disc.actual_value) if matched_disc and matched_disc.actual_value is not None else "0"
                    prop_val = req.proposed_value or (str(matched_disc.expected_value) if matched_disc and matched_disc.expected_value is not None else orig_val)
                    diff_val = matched_disc.difference if matched_disc and matched_disc.difference is not None else 0.0

                    new_cid = f"COR-DOC{doc.id}-{disc_id[:8]}"
                    new_prop = CorrectionProposal(
                        correction_id=new_cid,
                        user_id=user_id,
                        document_id=doc.id,
                        session_id=None,
                        sheet_name=sheet_name,
                        cell_address=cell_addr,
                        row_reference="Line Item",
                        field="Balance",
                        original_value=orig_val,
                        proposed_value=prop_val,
                        difference=diff_val,
                        reason_category="ACCOUNTANT_CORRECTION",
                        explanation=f"Accountant proposed correction: {notes}" if notes else "Accountant proposed correction.",
                        evidence_json="[]",
                        recommended_verification_json="[]",
                        confidence="HIGH",
                        status="PROPOSED",
                        accountant_decision="PROPOSED",
                        decision_notes=notes,
                    )
                    db.add(new_prop)
                    db.commit()

                # Record activity in history
                HistoryService.record_activity(
                    db=db,
                    user_id=user_id,
                    module="review_center",
                    action=f"finding_{dec.lower()}",
                    target_name=f"{doc.original_filename} finding {disc_id}",
                    status="completed",
                    result_summary=f"Accountant decision '{dec}' on {doc.original_filename} finding. Notes: {notes or 'None'}",
                    user_action=f"Review decision: {dec}",
                    document_id=doc.id,
                )

                findings_sum = cls.get_findings(db, user_id=user_id)
                for f in findings_sum.findings:
                    if f.id == finding_id:
                        f.status = dec
                        f.accountant_decision = dec
                        f.decision_notes = notes
                        return f

                return ReviewFindingItem(
                    id=finding_id,
                    document_id=doc.id,
                    document_name=doc.original_filename,
                    type="ACCOUNTING_DISCREPANCY",
                    severity="HIGH",
                    status=dec,
                    title="Accountant Reviewed Finding",
                    description=notes or "Decision recorded",
                    accountant_decision=dec,
                    decision_notes=notes,
                )

        # GST Reconciliation finding (e.g. gst_recon_{id})
        if finding_id.startswith("gst_recon_"):
            try:
                from app.modules.gst.models import GSTReconciliationResult
                recon_id = int(finding_id.replace("gst_recon_", ""))
                recon = db.query(GSTReconciliationResult).filter(GSTReconciliationResult.id == recon_id).first()
                if not recon:
                    raise HTTPException(status_code=404, detail="GST reconciliation record not found.")

                if dec in ("APPROVE", "APPROVED", "ACCEPT", "ACCEPTED"):
                    recon.status = "ACCEPTED"
                elif dec in ("REJECT", "REJECTED"):
                    recon.status = "REJECTED"
                elif dec in ("IGNORE", "IGNORED", "EXCLUDE", "EXCLUDED"):
                    recon.status = "EXCLUDED"
                elif dec in ("FORCE_MATCH", "MANUAL_MATCH", "MANUAL_MATCHED"):
                    recon.status = "MANUAL_MATCHED"
                else:
                    recon.status = "UNREVIEWED"

                recon.accountant_notes = notes
                recon.manual_decision_preserved = True
                db.commit()

                HistoryService.record_activity(
                    db=db,
                    user_id=user_id,
                    module="gst",
                    action=f"gst_recon_{dec.lower()}",
                    target_name=f"GSTR-2B Mismatch {finding_id}",
                    status="completed",
                    result_summary=f"Accountant recorded decision '{recon.status}' for GST reconciliation result #{recon.id}. Notes: {notes or 'None'}",
                    user_action=f"GST Decision: {recon.status}",
                )

                findings_sum = cls.get_findings(db, user_id=user_id)
                for f in findings_sum.findings:
                    if f.id == finding_id:
                        return f

                return ReviewFindingItem(
                    id=finding_id,
                    document_name=f"GSTR-2B Recon ({recon.period})",
                    type=f"GST_{recon.match_type}",
                    severity="HIGH",
                    status="APPROVED" if recon.status == "ACCEPTED" else recon.status,
                    title="GST Reconciliation Decision Recorded",
                    description=notes or f"Decision {recon.status} saved.",
                    accountant_decision=recon.status,
                    decision_notes=notes,
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to update GST finding decision: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # ITR finding (e.g. itr_{id})
        if finding_id.startswith("itr_"):
            try:
                from app.modules.itr.models import ITRFinding
                itr_f_id = int(finding_id.replace("itr_", ""))
                f_rec = db.query(ITRFinding).filter(ITRFinding.id == itr_f_id).first()
                if not f_rec:
                    raise HTTPException(status_code=404, detail="ITR finding record not found.")

                if dec in ("APPROVE", "APPROVED", "ACCEPT", "ACCEPTED"):
                    f_rec.status = "APPROVED"
                    f_rec.accountant_decision = "ACCEPTED"
                elif dec in ("REJECT", "REJECTED"):
                    f_rec.status = "REJECTED"
                    f_rec.accountant_decision = "REJECTED"
                else:
                    f_rec.status = "UNDER_REVIEW"
                    f_rec.accountant_decision = dec

                f_rec.decision_notes = notes
                f_rec.reviewed_at = datetime.now(timezone.utc)
                db.commit()

                HistoryService.record_activity(
                    db=db,
                    user_id=user_id,
                    module="itr",
                    action=f"itr_finding_{dec.lower()}",
                    target_name=f"ITR Finding {finding_id}",
                    status="completed",
                    result_summary=f"Accountant recorded decision '{f_rec.accountant_decision}' for ITR finding #{f_rec.id}. Notes: {notes or 'None'}",
                    user_action=f"ITR Decision: {f_rec.accountant_decision}",
                )

                findings_sum = cls.get_findings(db, user_id=user_id)
                for f in findings_sum.findings:
                    if f.id == finding_id:
                        return f

                return ReviewFindingItem(
                    id=finding_id,
                    document_name=f"ITR Finding #{f_rec.id}",
                    type=f_rec.finding_type,
                    severity=f_rec.severity,
                    status=f_rec.status,
                    title=f_rec.title,
                    description=notes or f"Decision {f_rec.accountant_decision} saved.",
                    accountant_decision=f_rec.accountant_decision,
                    decision_notes=notes,
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to update ITR finding decision: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        # Financial Statements finding (e.g. fs_{id})
        if finding_id.startswith("fs_"):
            try:
                from app.modules.financial_statements.models import (
                    FinancialStatementFinding,
                    FinancialStatementProfile,
                )
                fs_f_id = int(finding_id.replace("fs_", ""))
                f_rec = (
                    db.query(FinancialStatementFinding)
                    .join(FinancialStatementProfile)
                    .filter(
                        FinancialStatementFinding.id == fs_f_id,
                        FinancialStatementProfile.user_id == user_id,
                    )
                    .first()
                )
                if not f_rec:
                    raise HTTPException(
                        status_code=404,
                        detail="Financial Statement finding record not found.",
                    )

                if dec in ("APPROVE", "APPROVED", "ACCEPT", "ACCEPTED"):
                    f_rec.status = "APPROVED"
                    f_rec.accountant_decision = "ACCEPTED"
                elif dec in ("REJECT", "REJECTED"):
                    f_rec.status = "REJECTED"
                    f_rec.accountant_decision = "REJECTED"
                elif dec in ("OVERRIDE", "OVERRIDDEN"):
                    f_rec.status = "APPROVED"
                    f_rec.accountant_decision = "OVERRIDDEN"
                else:
                    f_rec.status = "UNDER_REVIEW"
                    f_rec.accountant_decision = dec

                f_rec.decision_notes = notes
                f_rec.reviewed_at = datetime.now(timezone.utc)
                db.commit()

                HistoryService.record_activity(
                    db=db,
                    user_id=user_id,
                    module="financial_statements",
                    action=f"fs_finding_{dec.lower()}",
                    target_name=f"Financial Statement Finding {finding_id}",
                    status="completed",
                    result_summary=f"Accountant recorded decision '{f_rec.accountant_decision}' for FS finding #{f_rec.id}. Notes: {notes or 'None'}",
                    user_action=f"FS Decision: {f_rec.accountant_decision}",
                )

                findings_sum = cls.get_findings(db, user_id=user_id)
                for f in findings_sum.findings:
                    if f.id == finding_id:
                        return f

                return ReviewFindingItem(
                    id=finding_id,
                    document_name=f"FS Finding #{f_rec.id}",
                    type=f_rec.finding_type,
                    severity=f_rec.severity,
                    status=f_rec.status,
                    title=f_rec.title,
                    description=notes or f"Decision {f_rec.accountant_decision} saved.",
                    accountant_decision=f_rec.accountant_decision,
                    decision_notes=notes,
                )
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Failed to update FS finding decision: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        raise HTTPException(status_code=404, detail=f"Finding '{finding_id}' not found.")
