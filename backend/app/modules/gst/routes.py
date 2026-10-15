"""
FastAPI Endpoints for GST Returns & Reconciliation Module.
Mounted under /api/gst and /api/v1/gst with authenticated company/user scoping.
"""

import csv
import io
import json
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Query, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.modules.gst.service import GSTService
from app.modules.gst.schemas import (
    GSTRegistrationCreate,
    GSTRegistrationUpdate,
    GSTRegistrationResponse,
    GSTFilingPeriodCreate,
    GSTFilingPeriodResponse,
    GSTPeriodStatusTransition,
    GSTSalesInvoiceCreate,
    GSTSalesInvoiceResponse,
    GSTPurchaseInvoiceCreate,
    GSTPurchaseInvoiceResponse,
    GSTR2BRecordResponse,
    GSTR2BBulkImportRequest,
    GSTR1SummaryResponse,
    GSTR3BSummaryResponse,
    ReconciliationRunRequest,
    GSTReconciliationResultResponse,
    ReconciliationDecisionRequest,
    ReconciliationSummaryResponse,
)

router = APIRouter()


# ============================================================================
# GST Registrations
# ============================================================================


@router.get("/registrations", response_model=List[GSTRegistrationResponse])
def list_registrations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all GST registrations accessible to the current user/organization."""
    return GSTService.get_registrations(db=db, user=current_user)


@router.post(
    "/registrations",
    response_model=GSTRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_registration(
    payload: GSTRegistrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new GST registration with statutory GSTIN validation."""
    return GSTService.create_registration(db=db, user=current_user, data=payload)


@router.get("/registrations/{registration_id}", response_model=GSTRegistrationResponse)
def get_registration(
    registration_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve details of a specific GST registration."""
    return GSTService.get_scoped_registration(
        db=db, user=current_user, registration_id=registration_id
    )


@router.put("/registrations/{registration_id}", response_model=GSTRegistrationResponse)
def update_registration(
    registration_id: str,
    payload: GSTRegistrationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update GST registration details."""
    return GSTService.update_registration(
        db=db, user=current_user, registration_id=registration_id, data=payload
    )


# ============================================================================
# Filing Periods
# ============================================================================


@router.get(
    "/registrations/{registration_id}/periods",
    response_model=List[GSTFilingPeriodResponse],
)
def list_filing_periods(
    registration_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all monthly filing periods for a GST registration."""
    return GSTService.get_periods(
        db=db, user=current_user, registration_id=registration_id
    )


@router.post(
    "/periods",
    response_model=GSTFilingPeriodResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_filing_period(
    payload: GSTFilingPeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Initialize a new filing period (e.g. 2024-04)."""
    return GSTService.create_period(db=db, user=current_user, data=payload)


@router.get("/periods/{period_id}", response_model=GSTFilingPeriodResponse)
def get_filing_period(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get status and details of a filing period."""
    return GSTService.get_scoped_period(db=db, user=current_user, period_id=period_id)


@router.post("/periods/{period_id}/transition", response_model=GSTFilingPeriodResponse)
def transition_period_status(
    period_id: str,
    payload: GSTPeriodStatusTransition,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Workflow state transitions: draft -> under_review -> approved -> filed -> locked."""
    return GSTService.transition_period_status(
        db=db, user=current_user, period_id=period_id, data=payload
    )


# ============================================================================
# Sales Invoices (GSTR-1)
# ============================================================================


@router.get("/periods/{period_id}/sales", response_model=List[GSTSalesInvoiceResponse])
def list_sales_invoices(
    period_id: str,
    invoice_type: Optional[str] = Query(
        None, description="Filter by B2B, B2CL, B2CS, EXPORT, CDNR, etc."
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sales invoices for the given filing period."""
    return GSTService.get_sales_invoices(
        db=db, user=current_user, period_id=period_id, invoice_type=invoice_type
    )


@router.post(
    "/periods/{period_id}/sales",
    response_model=GSTSalesInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_sales_invoice(
    period_id: str,
    payload: GSTSalesInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a sales invoice with statutory validation and automatic tax splitting."""
    payload.period_id = period_id
    return GSTService.create_sales_invoice(db=db, user=current_user, data=payload)


@router.delete("/sales/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sales_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a sales invoice (blocked if period is locked or filed)."""
    GSTService.delete_sales_invoice(db=db, user=current_user, invoice_id=invoice_id)
    return None


# ============================================================================
# Purchase Invoices (Books Register)
# ============================================================================


@router.get(
    "/periods/{period_id}/purchases", response_model=List[GSTPurchaseInvoiceResponse]
)
def list_purchase_invoices(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List internal purchase register invoices for ITC claiming."""
    return GSTService.get_purchase_invoices(
        db=db, user=current_user, period_id=period_id
    )


@router.post(
    "/periods/{period_id}/purchases",
    response_model=GSTPurchaseInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_invoice(
    period_id: str,
    payload: GSTPurchaseInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a purchase invoice with statutory tax validation."""
    payload.period_id = period_id
    return GSTService.create_purchase_invoice(db=db, user=current_user, data=payload)


@router.delete("/purchases/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_purchase_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a purchase invoice (blocked if period is locked or filed)."""
    GSTService.delete_purchase_invoice(db=db, user=current_user, invoice_id=invoice_id)
    return None


# ============================================================================
# GSTR-2B External Records
# ============================================================================


@router.get("/periods/{period_id}/gstr2b", response_model=List[GSTR2BRecordResponse])
def list_gstr2b_records(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List external GSTR-2B records downloaded or imported from GST portal."""
    return GSTService.get_gstr2b_records(db=db, user=current_user, period_id=period_id)


@router.post("/periods/{period_id}/gstr2b/import", status_code=status.HTTP_200_OK)
def import_gstr2b_records(
    period_id: str,
    payload: GSTR2BBulkImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk import GSTR-2B portal entries for reconciliation."""
    imported_count = GSTService.import_gstr2b_records(
        db=db,
        user=current_user,
        period_id=period_id,
        records_data=payload.records,
        payload_checksum=payload.checksum,
    )
    return {
        "message": f"Successfully imported {imported_count} GSTR-2B records",
        "count": imported_count,
    }


# ============================================================================
# GSTR-1 & GSTR-3B Summaries
# ============================================================================


@router.get("/periods/{period_id}/gstr1/summary", response_model=GSTR1SummaryResponse)
def get_gstr1_summary(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get GSTR-1 statutory aggregation across Table 4, 5, 6A, 7, 8, 9B."""
    return GSTService.get_gstr1_summary(db=db, user=current_user, period_id=period_id)


@router.post(
    "/periods/{period_id}/gstr1/recalculate", response_model=GSTR1SummaryResponse
)
def recalculate_gstr1_summary(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force re-aggregation of GSTR-1 statutory tables."""
    return GSTService.generate_gstr1_summary(
        db=db, user=current_user, period_id=period_id
    )


@router.get("/periods/{period_id}/gstr3b/summary", response_model=GSTR3BSummaryResponse)
def get_gstr3b_summary(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get GSTR-3B statutory tax liability, ITC eligibility, reversals, and set-off."""
    return GSTService.get_gstr3b_summary(db=db, user=current_user, period_id=period_id)


@router.post(
    "/periods/{period_id}/gstr3b/recalculate", response_model=GSTR3BSummaryResponse
)
def recalculate_gstr3b_summary(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force recalculation of GSTR-3B liability, ITC balance, and net payable tax."""
    return GSTService.generate_gstr3b_summary(
        db=db, user=current_user, period_id=period_id
    )


# ============================================================================
# Reconciliation (GSTR-2B vs Books)
# ============================================================================


@router.post(
    "/periods/{period_id}/reconciliation/run",
    response_model=List[GSTReconciliationResultResponse],
)
@router.post(
    "/periods/{period_id}/reconcile",
    response_model=List[GSTReconciliationResultResponse],
)
def run_reconciliation(
    period_id: str,
    payload: Optional[ReconciliationRunRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Execute multi-tier reconciliation between books purchases and GSTR-2B records."""
    params = payload or ReconciliationRunRequest()
    return GSTService.run_reconciliation(
        db=db, user=current_user, period_id=period_id, params=params
    )


@router.get(
    "/periods/{period_id}/reconciliation/results",
    response_model=List[GSTReconciliationResultResponse],
)
def get_reconciliation_results(
    period_id: str,
    match_status: Optional[str] = Query(
        None,
        description="EXACT_MATCH, PARTIAL_MATCH, BOOKS_ONLY, RETURN_ONLY, EXCLUDED",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get itemized reconciliation matches and discrepancy details."""
    return GSTService.get_reconciliation_results(
        db=db, user=current_user, period_id=period_id, match_status=match_status
    )


@router.get(
    "/periods/{period_id}/reconciliation/summary",
    response_model=ReconciliationSummaryResponse,
)
def get_reconciliation_summary(
    period_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get high-level reconciliation statistics and tax discrepancy totals."""
    return GSTService.get_reconciliation_summary(
        db=db, user=current_user, period_id=period_id
    )


@router.post(
    "/reconciliation/{result_id}/decision",
    response_model=GSTReconciliationResultResponse,
)
def update_reconciliation_decision(
    result_id: str,
    payload: ReconciliationDecisionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accountant decision on reconciliation item: ACCEPTED, REJECTED, FORCE_MATCH, PENDING."""
    return GSTService.update_reconciliation_decision(
        db=db, user=current_user, result_id=result_id, data=payload
    )


# ============================================================================
# Bulk Operations & File Upload
# ============================================================================


@router.post(
    "/periods/{period_id}/sales/bulk",
    response_model=List[GSTSalesInvoiceResponse],
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_sales_invoices(
    period_id: str,
    invoices: List[GSTSalesInvoiceCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk create sales invoices for the filing period."""
    created = []
    for inv in invoices:
        inv.period_id = period_id
        created.append(GSTService.create_sales_invoice(db=db, user=current_user, data=inv))
    return created


@router.post(
    "/periods/{period_id}/purchases/bulk",
    response_model=List[GSTPurchaseInvoiceResponse],
    status_code=status.HTTP_201_CREATED,
)
def bulk_create_purchase_invoices(
    period_id: str,
    invoices: List[GSTPurchaseInvoiceCreate],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk create purchase invoices for the filing period."""
    created = []
    for inv in invoices:
        inv.period_id = period_id
        created.append(GSTService.create_purchase_invoice(db=db, user=current_user, data=inv))
    return created


@router.post("/periods/{period_id}/upload")
async def upload_gst_file(
    period_id: str,
    file: UploadFile = File(...),
    target_type: str = Form("auto"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload and parse GST accounting files (Excel .xlsx, .csv, or .json)
    supporting Sales Invoices (GSTR-1), Purchase Register, and GSTR-2B portal exports.
    """
    period = GSTService.get_scoped_period(db, current_user, period_id)
    GSTService._verify_period_editable(period)
    reg = GSTService.get_scoped_registration(db, current_user, period.registration_id)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Filename must not be empty"
        )

    fname = file.filename.lower()
    contents = await file.read()

    rows: List[Dict[str, Any]] = []

    if fname.endswith(".json"):
        try:
            parsed = json.loads(contents.decode("utf-8"))
            if isinstance(parsed, list):
                rows = parsed
            elif isinstance(parsed, dict):
                rows = parsed.get("records") or parsed.get("data", {}).get("b2b") or [parsed]
            else:
                raise ValueError("JSON must be a list or object with records")
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid JSON file format: {e}",
            )

    elif fname.endswith(".csv"):
        try:
            text = contents.decode("utf-8", errors="ignore")
            reader = csv.DictReader(io.StringIO(text))
            for raw_row in reader:
                cleaned_row = {
                    k.strip().lower().replace(" ", "_").replace("#", "num"): (v.strip() if v else "")
                    for k, v in raw_row.items()
                    if k
                }
                rows.append(cleaned_row)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid CSV file format: {e}",
            )

    elif fname.endswith((".xlsx", ".xls")):
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
            sheet = wb.active
            header_keys = []
            for row_idx, r in enumerate(sheet.iter_rows(values_only=True)):
                if row_idx == 0:
                    header_keys = [
                        str(cell or "").strip().lower().replace(" ", "_").replace("#", "num")
                        for cell in r
                    ]
                else:
                    if not any(r):
                        continue
                    row_dict = {}
                    for col_idx, cell_val in enumerate(r):
                        if col_idx < len(header_keys) and header_keys[col_idx]:
                            row_dict[header_keys[col_idx]] = str(cell_val or "").strip()
                    rows.append(row_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid Excel file format: {e}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload an Excel (.xlsx), CSV (.csv), or JSON (.json) file.",
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No data records detected in uploaded file.",
        )

    # Detect target type if 'auto'
    resolved_type = target_type.lower()
    first_keys = set(rows[0].keys())
    if resolved_type == "auto":
        if "supplier_gstin" in first_keys and ("itc_available" in first_keys or "filing_status" in first_keys or "2b" in fname):
            resolved_type = "gstr2b"
        elif "supplier_gstin" in first_keys or "supplier_name" in first_keys or "purchase" in fname:
            resolved_type = "purchases"
        else:
            resolved_type = "sales"

    imported_count = 0
    skipped_count = 0
    errors: List[str] = []

    # Import GSTR-2B
    if resolved_type == "gstr2b":
        from app.modules.gst.schemas import GSTR2BRecordCreate
        record_objs: List[GSTR2BRecordCreate] = []
        for idx, row in enumerate(rows, 1):
            try:
                inv_num = str(row.get("invoice_number") or row.get("inv_num") or row.get("invoice_no") or f"INV-2B-{idx}").strip().upper()
                gstin = str(row.get("supplier_gstin") or row.get("gstin") or "").strip().upper()
                s_name = str(row.get("supplier_name") or row.get("trade_name") or "Vendor").strip()
                t_val = Decimal(str(row.get("taxable_value") or row.get("taxable_amount") or "0").replace(",", "") or "0")
                cgst = Decimal(str(row.get("cgst_amount") or row.get("cgst") or "0").replace(",", "") or "0")
                sgst = Decimal(str(row.get("sgst_amount") or row.get("sgst") or "0").replace(",", "") or "0")
                igst = Decimal(str(row.get("igst_amount") or row.get("igst") or "0").replace(",", "") or "0")
                cess = Decimal(str(row.get("cess_amount") or row.get("cess") or "0").replace(",", "") or "0")
                tot = Decimal(str(row.get("total_amount") or row.get("total") or (t_val + cgst + sgst + igst + cess)).replace(",", "") or "0")
                inv_date = str(row.get("invoice_date") or row.get("date") or "2024-04-15")[:10]
                itc_avail = str(row.get("itc_available", "true")).lower() in ("true", "1", "yes", "y")

                record_objs.append(
                    GSTR2BRecordCreate(
                        supplier_gstin=gstin,
                        supplier_name=s_name,
                        invoice_number=inv_num,
                        invoice_date=inv_date,
                        invoice_type=str(row.get("invoice_type") or "B2B").upper(),
                        taxable_value=t_val,
                        cgst_amount=cgst,
                        sgst_amount=sgst,
                        igst_amount=igst,
                        cess_amount=cess,
                        total_amount=tot,
                        itc_available=itc_avail,
                        filing_status=str(row.get("filing_status") or "FILED").upper(),
                    )
                )
            except Exception as ex:
                errors.append(f"Row {idx}: {str(ex)}")

        if record_objs:
            imported_count = GSTService.import_gstr2b_records(
                db=db, user=current_user, period_id=period_id, records_data=record_objs
            )

    # Import Sales Invoices (GSTR-1)
    elif resolved_type == "sales":
        for idx, row in enumerate(rows, 1):
            try:
                inv_num = str(row.get("invoice_number") or row.get("inv_num") or row.get("invoice_no") or f"SALES-{idx}").strip().upper()
                c_name = str(row.get("customer_name") or row.get("party_name") or row.get("client_name") or "Retail Customer").strip()
                c_gstin = str(row.get("customer_gstin") or row.get("gstin") or "").strip().upper() or None
                pos = str(row.get("place_of_supply") or row.get("pos") or reg.state_code or "27").strip().zfill(2)
                t_val = Decimal(str(row.get("taxable_value") or row.get("taxable_amount") or "0").replace(",", "") or "0")
                t_rate = Decimal(str(row.get("tax_rate") or row.get("rate") or "18.00").replace("%", "").strip() or "18.00")
                inv_type = str(row.get("invoice_type") or row.get("type") or ("B2B" if c_gstin else "B2CS")).upper()
                inv_date = str(row.get("invoice_date") or row.get("date") or "2024-04-15")[:10]

                inv_create = GSTSalesInvoiceCreate(
                    period_id=period.id,
                    invoice_number=inv_num,
                    invoice_date=inv_date,
                    customer_gstin=c_gstin,
                    customer_name=c_name,
                    place_of_supply=pos,
                    invoice_type=inv_type,
                    taxable_value=t_val,
                    tax_rate=t_rate,
                    total_amount=Decimal("0.00"),  # auto-calculated
                    auto_calculate_tax=True,
                )
                GSTService.create_sales_invoice(db=db, user=current_user, data=inv_create)
                imported_count += 1
            except HTTPException as hex:
                if "already exists" in hex.detail:
                    skipped_count += 1
                else:
                    errors.append(f"Row {idx}: {hex.detail}")
            except Exception as ex:
                errors.append(f"Row {idx}: {str(ex)}")

    # Import Purchase Invoices (Books Register)
    elif resolved_type == "purchases":
        for idx, row in enumerate(rows, 1):
            try:
                inv_num = str(row.get("invoice_number") or row.get("inv_num") or row.get("invoice_no") or f"PUR-{idx}").strip().upper()
                s_name = str(row.get("supplier_name") or row.get("vendor_name") or row.get("party_name") or "Vendor").strip()
                s_gstin = str(row.get("supplier_gstin") or row.get("gstin") or "27AAPFU0939F1ZV").strip().upper()
                pos = str(row.get("place_of_supply") or row.get("pos") or reg.state_code or "27").strip().zfill(2)
                t_val = Decimal(str(row.get("taxable_value") or row.get("taxable_amount") or "0").replace(",", "") or "0")
                t_rate = Decimal(str(row.get("tax_rate") or row.get("rate") or "18.00").replace("%", "").strip() or "18.00")
                inv_date = str(row.get("invoice_date") or row.get("date") or "2024-04-15")[:10]

                pur_create = GSTPurchaseInvoiceCreate(
                    period_id=period.id,
                    invoice_number=inv_num,
                    invoice_date=inv_date,
                    supplier_gstin=s_gstin,
                    supplier_name=s_name,
                    place_of_supply=pos,
                    taxable_value=t_val,
                    tax_rate=t_rate,
                    total_amount=Decimal("0.00"),
                    auto_calculate_tax=True,
                )
                GSTService.create_purchase_invoice(db=db, user=current_user, data=pur_create)
                imported_count += 1
            except HTTPException as hex:
                if "already exists" in hex.detail:
                    skipped_count += 1
                else:
                    errors.append(f"Row {idx}: {hex.detail}")
            except Exception as ex:
                errors.append(f"Row {idx}: {str(ex)}")

    from app.services.history_service import HistoryService
    HistoryService.record_activity(
        db=db,
        user_id=current_user.id,
        module="gst",
        action="gst_file_import",
        target_name=file.filename,
        status="completed" if imported_count > 0 else "failed",
        result_summary=f"Imported {imported_count} {resolved_type} records into period {period.period}. Skipped {skipped_count}. Errors: {len(errors)}.",
        user_action="GST File Upload & Import",
    )

    return {
        "success": imported_count > 0 or skipped_count > 0,
        "message": f"Processed {file.filename}: {imported_count} imported, {skipped_count} skipped.",
        "file_type": resolved_type,
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors[:10],
    }


# ============================================================================
# GST Export Reports
# ============================================================================


@router.get("/periods/{period_id}/export/{report_type}")
def export_gst_report(
    period_id: str,
    report_type: str,
    format: str = Query("json", description="json or csv"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Download verified statutory GST summaries and reconciliation reports.
    Notice: Generated solely for internal accountant review and verification.
    """
    period = GSTService.get_scoped_period(db, current_user, period_id)
    reg = GSTService.get_scoped_registration(db, current_user, period.registration_id)

    rep_type = report_type.lower()
    disclaimer = "NOTE: Generated by LiteBooks for internal accountant verification. Not submitted to GSTN."

    if rep_type == "gstr1":
        summary = GSTService.get_gstr1_summary(db, current_user, period_id)
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["# " + disclaimer])
            writer.writerow(["GSTR-1 Statutory Outward Supplies Summary", f"Period: {period.period}", f"GSTIN: {reg.gstin}"])
            writer.writerow([])
            writer.writerow(["Table / Category", "Taxable Value (INR)", "CGST (INR)", "SGST (INR)", "IGST (INR)", "Total Tax (INR)", "Invoices"])

            def _parse_sum(s):
                if isinstance(s, str):
                    try:
                        return json.loads(s)
                    except Exception:
                        return {}
                return s or {}

            tables = {
                "4A - B2B Invoices": _parse_sum(summary.b2b_summary),
                "5A - B2C Large": _parse_sum(summary.b2cl_summary),
                "7 - B2C Small": _parse_sum(summary.b2cs_summary),
                "6A - Exports": _parse_sum(summary.export_summary),
                "9B - Credit/Debit Notes": _parse_sum(summary.cdnr_summary),
                "8 - Nil/Exempt Supplies": _parse_sum(summary.nil_exempt_summary),
            }

            for t_title, t_data in tables.items():
                if t_data and any(t_data.values()):
                    writer.writerow([
                        t_title,
                        t_data.get("taxable_value", 0),
                        t_data.get("cgst", 0),
                        t_data.get("sgst", 0),
                        t_data.get("igst", 0),
                        float(t_data.get("cgst", 0) or 0) + float(t_data.get("sgst", 0) or 0) + float(t_data.get("igst", 0) or 0),
                        t_data.get("invoice_count", 0),
                    ])

            total_tax_val = float(summary.total_cgst or 0) + float(summary.total_sgst or 0) + float(summary.total_igst or 0)
            writer.writerow([])
            writer.writerow(["TOTAL", summary.total_taxable_value, summary.total_cgst, summary.total_sgst, summary.total_igst, total_tax_val, summary.total_invoices_count])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="GSTR1_{reg.gstin}_{period.period}.csv"'},
            )
        return {
            "disclaimer": disclaimer,
            "period": period.period,
            "gstin": reg.gstin,
            "summary": summary.model_dump() if hasattr(summary, "model_dump") else {
                "period": summary.period,
                "total_taxable_value": float(summary.total_taxable_value or 0),
                "total_cgst": float(summary.total_cgst or 0),
                "total_sgst": float(summary.total_sgst or 0),
                "total_igst": float(summary.total_igst or 0),
                "total_invoices_count": summary.total_invoices_count,
            },
        }

    elif rep_type == "gstr3b":
        summary = GSTService.get_gstr3b_summary(db, current_user, period_id)
        if format.lower() == "csv":
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(["# " + disclaimer])
            writer.writerow(["GSTR-3B Statutory Computation Report", f"Period: {period.period}", f"GSTIN: {reg.gstin}"])
            writer.writerow([])
            writer.writerow(["Description", "Taxable Value (INR)", "IGST (INR)", "CGST (INR)", "SGST (INR)", "Total Tax (INR)"])
            outward_tax = float(summary.outward_igst or 0) + float(summary.outward_cgst or 0) + float(summary.outward_sgst or 0)
            itc_tax = float(summary.itc_all_other_igst or 0) + float(summary.itc_all_other_cgst or 0) + float(summary.itc_all_other_sgst or 0)

            setoff = {}
            if summary.set_off_details:
                try:
                    setoff = json.loads(summary.set_off_details) if isinstance(summary.set_off_details, str) else summary.set_off_details
                except Exception:
                    setoff = {}

            net_payable = setoff.get("total_tax_payable", outward_tax)
            writer.writerow(["3.1 Outward Taxable Supplies", summary.outward_taxable_value, summary.outward_igst, summary.outward_cgst, summary.outward_sgst, outward_tax])
            writer.writerow(["4. Eligible ITC Available", 0, summary.itc_all_other_igst, summary.itc_all_other_cgst, summary.itc_all_other_sgst, itc_tax])
            writer.writerow(["6.1 Net Tax Payable in Cash", 0, setoff.get("payable_igst", 0), setoff.get("payable_cgst", 0), setoff.get("payable_sgst", 0), net_payable])
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="GSTR3B_{reg.gstin}_{period.period}.csv"'},
            )
        return {
            "disclaimer": disclaimer,
            "period": period.period,
            "gstin": reg.gstin,
            "summary": summary.model_dump() if hasattr(summary, "model_dump") else {
                "period": summary.period,
                "outward_taxable_value": float(summary.outward_taxable_value or 0),
                "outward_igst": float(summary.outward_igst or 0),
                "outward_cgst": float(summary.outward_cgst or 0),
                "outward_sgst": float(summary.outward_sgst or 0),
            },
        }

    elif rep_type == "reconciliation":
        results = GSTService.get_reconciliation_results(db, current_user, period_id)
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["# " + disclaimer])
        writer.writerow(["GSTR-2B vs Books ITC Reconciliation Report", f"Period: {period.period}", f"GSTIN: {reg.gstin}"])
        writer.writerow([])
        writer.writerow([
            "Result ID", "Match Status", "Confidence", "Supplier Name", "Supplier GSTIN",
            "Books Inv #", "Books Date", "Books Taxable", "Books Tax",
            "2B Inv #", "2B Date", "2B Taxable", "2B Tax",
            "Tax Variance", "Accountant Decision", "Notes"
        ])
        for r in results:
            p = r.purchase_invoice
            g = r.gstr2b_record
            s_name = (p.supplier_name if p else None) or (g.supplier_name if g else "")
            s_gstin = (p.supplier_gstin if p else None) or (g.supplier_gstin if g else "")
            p_tax = float((p.cgst_amount or 0) + (p.sgst_amount or 0) + (p.igst_amount or 0)) if p else 0.0
            g_tax = float((g.cgst_amount or 0) + (g.sgst_amount or 0) + (g.igst_amount or 0)) if g else 0.0
            writer.writerow([
                r.id,
                r.match_type,
                f"{float(r.match_score):.0f}%",
                s_name,
                s_gstin,
                p.invoice_number if p else "-",
                p.invoice_date if p else "-",
                p.taxable_value if p else 0,
                p_tax,
                g.invoice_number if g else "-",
                g.invoice_date if g else "-",
                g.taxable_value if g else 0,
                g_tax,
                r.tax_difference,
                r.status,
                r.accountant_notes or "-",
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="Reconciliation_{reg.gstin}_{period.period}.csv"'},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported report type: '{report_type}'")

