import csv
import hashlib
import io
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.modules.financial_statements.calculator import FSCalculator
from app.modules.financial_statements.models import (
    BalanceSheetLine,
    CashFlowLine,
    FinancialStatementFinding,
    FinancialStatementProfile,
    FinancialStatementSnapshot,
    ProfitLossLine,
    TrialBalanceEntry,
)
from app.modules.financial_statements.schemas import (
    FSProfileCreate,
    FSProfileUpdate,
    TrialBalanceEntryCreate,
    BalanceSheetLineCreate,
    ProfitLossLineCreate,
    CashFlowLineCreate,
)
from app.modules.financial_statements.validator import FSValidator
from app.services.history_service import HistoryService

logger = logging.getLogger(__name__)


class FSService:
    """
    End-to-end service for Financial Statements:
    - Profile management (entity, FY, reporting period)
    - Source ingestion (.csv, .xlsx, direct entries) with provenance
    - Deterministic calculation (TB, BS Schedule III, P&L, Cash Flow)
    - Immutable snapshot hashing (SHA-256)
    - Validation findings and Review Center decisions
    - Strict Approval safety guardrails
    - Accountant report export (CSV / formatted text)
    - Full audit logging
    """

    # -------------------------------------------------------------
    # Profile CRUD
    # -------------------------------------------------------------

    @staticmethod
    def list_profiles(db: Session, user_id: int) -> List[FinancialStatementProfile]:
        return (
            db.query(FinancialStatementProfile)
            .filter(FinancialStatementProfile.user_id == user_id)
            .order_by(FinancialStatementProfile.created_at.desc())
            .all()
        )

    @staticmethod
    def get_profile(db: Session, user_id: int, profile_id: int) -> FinancialStatementProfile:
        profile = (
            db.query(FinancialStatementProfile)
            .filter(
                FinancialStatementProfile.id == profile_id,
                FinancialStatementProfile.user_id == user_id,
            )
            .first()
        )
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Financial statement profile #{profile_id} not found.",
            )
        return profile

    @staticmethod
    def get_or_create_profile(
        db: Session, user_id: int, profile_in: FSProfileCreate
    ) -> FinancialStatementProfile:
        existing = (
            db.query(FinancialStatementProfile)
            .filter(
                FinancialStatementProfile.user_id == user_id,
                FinancialStatementProfile.entity_name == profile_in.entity_name,
                FinancialStatementProfile.financial_year == profile_in.financial_year,
                FinancialStatementProfile.reporting_period == profile_in.reporting_period,
            )
            .first()
        )
        if existing:
            return existing

        profile = FinancialStatementProfile(
            user_id=user_id,
            entity_name=profile_in.entity_name,
            cin_or_pan=profile_in.cin_or_pan,
            financial_year=profile_in.financial_year,
            reporting_period=profile_in.reporting_period,
            framework=profile_in.framework or "SCHEDULE_III",
            status="DRAFT",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="create_profile",
            target_name=f"{profile.entity_name} ({profile.financial_year})",
            status="completed",
            result_summary=f"Created financial statements profile for {profile.entity_name} FY {profile.financial_year} ({profile.reporting_period})",
            user_action="Create Profile",
        )
        return profile

    @staticmethod
    def update_profile(
        db: Session, user_id: int, profile_id: int, update_in: FSProfileUpdate
    ) -> FinancialStatementProfile:
        profile = FSService.get_profile(db, user_id, profile_id)
        if update_in.entity_name is not None:
            profile.entity_name = update_in.entity_name
        if update_in.cin_or_pan is not None:
            profile.cin_or_pan = update_in.cin_or_pan
        if update_in.framework is not None:
            profile.framework = update_in.framework
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def delete_profile(db: Session, user_id: int, profile_id: int) -> bool:
        profile = FSService.get_profile(db, user_id, profile_id)
        db.delete(profile)
        db.commit()
        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="delete_profile",
            target_name=f"{profile.entity_name} #{profile_id}",
            status="completed",
            result_summary=f"Deleted financial statements profile #{profile_id}",
            user_action="Delete Profile",
        )
        return True

    # -------------------------------------------------------------
    # Entries & Line Management
    # -------------------------------------------------------------

    @staticmethod
    def add_trial_balance_entries(
        db: Session, user_id: int, profile_id: int, entries: List[TrialBalanceEntryCreate]
    ) -> List[TrialBalanceEntry]:
        profile = FSService.get_profile(db, user_id, profile_id)
        created: List[TrialBalanceEntry] = []
        for e in entries:
            net = e.debit_amount - e.credit_amount
            entry = TrialBalanceEntry(
                profile_id=profile.id,
                account_code=e.account_code,
                account_name=e.account_name,
                account_category=e.account_category.upper(),
                debit_amount=e.debit_amount,
                credit_amount=e.credit_amount,
                net_balance=net,
                source_document=e.source_document,
                source_sheet=e.source_sheet,
                source_row=e.source_row,
                source_cell=e.source_cell,
                source_value=e.source_value or str(e.debit_amount or e.credit_amount),
                provenance_notes=e.provenance_notes,
            )
            db.add(entry)
            created.append(entry)

        db.commit()
        for c in created:
            db.refresh(c)

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="import_trial_balance",
            target_name=f"{profile.entity_name} ({len(entries)} accounts)",
            status="completed",
            result_summary=f"Ingested {len(entries)} trial balance ledger accounts",
            user_action="Add Trial Balance Entries",
        )
        return created

    @staticmethod
    def add_balance_sheet_lines(
        db: Session, user_id: int, profile_id: int, lines: List[BalanceSheetLineCreate]
    ) -> List[BalanceSheetLine]:
        profile = FSService.get_profile(db, user_id, profile_id)
        created: List[BalanceSheetLine] = []
        for line in lines:
            bs = BalanceSheetLine(
                profile_id=profile.id,
                classification=line.classification.upper(),
                sub_category=line.sub_category,
                line_item_name=line.line_item_name,
                amount=line.amount,
                schedule_note_number=line.schedule_note_number,
                source_document=line.source_document,
                source_sheet=line.source_sheet,
                source_row=line.source_row,
                source_cell=line.source_cell,
                provenance_notes=line.provenance_notes,
            )
            db.add(bs)
            created.append(bs)

        db.commit()
        for c in created:
            db.refresh(c)
        return created

    @staticmethod
    def add_profit_loss_lines(
        db: Session, user_id: int, profile_id: int, lines: List[ProfitLossLineCreate]
    ) -> List[ProfitLossLine]:
        profile = FSService.get_profile(db, user_id, profile_id)
        created: List[ProfitLossLine] = []
        for line in lines:
            pl = ProfitLossLine(
                profile_id=profile.id,
                category=line.category.upper(),
                line_item_name=line.line_item_name,
                amount=line.amount,
                schedule_note_number=line.schedule_note_number,
                source_document=line.source_document,
                source_sheet=line.source_sheet,
                source_row=line.source_row,
                source_cell=line.source_cell,
                provenance_notes=line.provenance_notes,
            )
            db.add(pl)
            created.append(pl)

        db.commit()
        for c in created:
            db.refresh(c)
        return created

    @staticmethod
    def add_cash_flow_lines(
        db: Session, user_id: int, profile_id: int, lines: List[CashFlowLineCreate]
    ) -> List[CashFlowLine]:
        profile = FSService.get_profile(db, user_id, profile_id)
        created: List[CashFlowLine] = []
        for line in lines:
            cf = CashFlowLine(
                profile_id=profile.id,
                activity_type=line.activity_type.upper(),
                line_item_name=line.line_item_name,
                amount=line.amount,
                source_document=line.source_document,
                source_sheet=line.source_sheet,
                source_row=line.source_row,
                provenance_notes=line.provenance_notes,
            )
            db.add(cf)
            created.append(cf)

        db.commit()
        for c in created:
            db.refresh(c)
        return created

    # -------------------------------------------------------------
    # Auto-Classification from Trial Balance
    # -------------------------------------------------------------

    @staticmethod
    def auto_classify_from_trial_balance(
        db: Session, user_id: int, profile_id: int, overwrite: bool = True
    ) -> Dict[str, int]:
        """
        Classifies Trial Balance accounts into Schedule III Balance Sheet and Profit & Loss lines
        preserving strict provenance back to the TB entry and original source file.
        """
        profile = FSService.get_profile(db, user_id, profile_id)
        tb_entries = profile.trial_balance_entries

        if not tb_entries:
            raise HTTPException(
                status_code=400,
                detail="Cannot generate financial statements: No Trial Balance entries found.",
            )

        if overwrite:
            db.query(BalanceSheetLine).filter(BalanceSheetLine.profile_id == profile.id).delete()
            db.query(ProfitLossLine).filter(ProfitLossLine.profile_id == profile.id).delete()
            db.commit()

        bs_created = 0
        pl_created = 0

        for entry in tb_entries:
            cat = entry.account_category.upper()
            name_lower = entry.account_name.lower()
            amt = entry.debit_amount if entry.debit_amount > 0 else entry.credit_amount

            # ASSETS -> Balance Sheet Assets
            if cat == "ASSET":
                if any(k in name_lower for k in ("cash", "bank", "petty cash", "cheque")):
                    sub = "CASH_BANK"
                    cls_type = "CURRENT_ASSETS"
                elif any(k in name_lower for k in ("inventory", "stock", "raw material")):
                    sub = "INVENTORIES"
                    cls_type = "CURRENT_ASSETS"
                elif any(k in name_lower for k in ("debtor", "receivable", "customer", "trade receivable")):
                    sub = "TRADE_RECEIVABLES"
                    cls_type = "CURRENT_ASSETS"
                elif any(k in name_lower for k in ("plant", "machinery", "building", "furniture", "vehicle", "computer", "equipment", "asset")):
                    sub = "PROPERTY_PLANT_EQUIPMENT"
                    cls_type = "NON_CURRENT_ASSETS"
                elif any(k in name_lower for k in ("software", "trademark", "patent", "copyright", "goodwill")):
                    sub = "INTANGIBLE"
                    cls_type = "NON_CURRENT_ASSETS"
                elif any(k in name_lower for k in ("investment", "mutual fund", "fixed deposit", "shares")):
                    sub = "NON_CURRENT_INVESTMENTS"
                    cls_type = "NON_CURRENT_ASSETS"
                else:
                    sub = "OTHER_CURRENT_ASSETS"
                    cls_type = "CURRENT_ASSETS"

                bs_line = BalanceSheetLine(
                    profile_id=profile.id,
                    classification=cls_type,
                    sub_category=sub,
                    line_item_name=entry.account_name,
                    amount=entry.debit_amount if entry.debit_amount > 0 else -entry.credit_amount,
                    source_document=entry.source_document,
                    source_sheet=entry.source_sheet,
                    source_row=entry.source_row,
                    source_cell=entry.source_cell,
                    provenance_notes=f"Auto-classified from TB {entry.account_code or entry.account_name}",
                )
                db.add(bs_line)
                bs_created += 1

            # LIABILITIES -> Balance Sheet Liabilities
            elif cat == "LIABILITY":
                if any(k in name_lower for k in ("creditor", "payable", "vendor", "trade payable", "supplier")):
                    sub = "TRADE_PAYABLES"
                    cls_type = "CURRENT_LIABILITIES"
                elif any(k in name_lower for k in ("loan", "borrowing", "overdraft", "od limit", "credit facility")):
                    sub = "SHORT_TERM_BORROWINGS" if "short" in name_lower else "LONG_TERM_BORROWINGS"
                    cls_type = "CURRENT_LIABILITIES" if "short" in name_lower else "NON_CURRENT_LIABILITIES"
                elif any(k in name_lower for k in ("provision", "prov")):
                    sub = "PROVISIONS"
                    cls_type = "CURRENT_LIABILITIES"
                else:
                    sub = "OTHER_CURRENT_LIABILITIES"
                    cls_type = "CURRENT_LIABILITIES"

                bs_line = BalanceSheetLine(
                    profile_id=profile.id,
                    classification=cls_type,
                    sub_category=sub,
                    line_item_name=entry.account_name,
                    amount=entry.credit_amount if entry.credit_amount > 0 else -entry.debit_amount,
                    source_document=entry.source_document,
                    source_sheet=entry.source_sheet,
                    source_row=entry.source_row,
                    source_cell=entry.source_cell,
                    provenance_notes=f"Auto-classified from TB {entry.account_code or entry.account_name}",
                )
                db.add(bs_line)
                bs_created += 1

            # EQUITY -> Balance Sheet Equity
            elif cat == "EQUITY":
                if any(k in name_lower for k in ("capital", "equity share", "partner's capital")):
                    sub = "SHARE_CAPITAL"
                else:
                    sub = "RESERVES_AND_SURPLUS"

                bs_line = BalanceSheetLine(
                    profile_id=profile.id,
                    classification="EQUITY",
                    sub_category=sub,
                    line_item_name=entry.account_name,
                    amount=entry.credit_amount if entry.credit_amount > 0 else -entry.debit_amount,
                    source_document=entry.source_document,
                    source_sheet=entry.source_sheet,
                    source_row=entry.source_row,
                    source_cell=entry.source_cell,
                    provenance_notes=f"Auto-classified from TB {entry.account_code or entry.account_name}",
                )
                db.add(bs_line)
                bs_created += 1

            # REVENUE -> Profit & Loss Revenue
            elif cat == "REVENUE":
                if any(k in name_lower for k in ("interest", "dividend", "other income", "discount", "scrap", "gain")):
                    pl_cat = "OTHER_INCOME"
                else:
                    pl_cat = "REVENUE"

                pl_line = ProfitLossLine(
                    profile_id=profile.id,
                    category=pl_cat,
                    line_item_name=entry.account_name,
                    amount=entry.credit_amount if entry.credit_amount > 0 else -entry.debit_amount,
                    source_document=entry.source_document,
                    source_sheet=entry.source_sheet,
                    source_row=entry.source_row,
                    source_cell=entry.source_cell,
                    provenance_notes=f"Auto-classified from TB {entry.account_code or entry.account_name}",
                )
                db.add(pl_line)
                pl_created += 1

            # EXPENSE -> Profit & Loss Expenses
            elif cat == "EXPENSE":
                if any(k in name_lower for k in ("purchase", "raw material", "cogs", "stock in trade", "freight inward")):
                    pl_cat = "COST_OF_MATERIALS"
                elif any(k in name_lower for k in ("salary", "wage", "staff", "employee", "bonus", "pf", "esi", "gratuity")):
                    pl_cat = "EMPLOYEE_BENEFITS"
                elif any(k in name_lower for k in ("interest", "finance", "bank charges", "loan processing")):
                    pl_cat = "FINANCE_COSTS"
                elif any(k in name_lower for k in ("depreciation", "amortization")):
                    pl_cat = "DEPRECIATION"
                elif any(k in name_lower for k in ("tax", "income tax", "tds on profit")):
                    pl_cat = "TAX_EXPENSE"
                else:
                    pl_cat = "OTHER_EXPENSES"

                pl_line = ProfitLossLine(
                    profile_id=profile.id,
                    category=pl_cat,
                    line_item_name=entry.account_name,
                    amount=entry.debit_amount if entry.debit_amount > 0 else -entry.credit_amount,
                    source_document=entry.source_document,
                    source_sheet=entry.source_sheet,
                    source_row=entry.source_row,
                    source_cell=entry.source_cell,
                    provenance_notes=f"Auto-classified from TB {entry.account_code or entry.account_name}",
                )
                db.add(pl_line)
                pl_created += 1

        db.commit()

        # Also auto-populate basic Cash Flow if none exists
        existing_cf = profile.cash_flow_lines
        if not existing_cf:
            # Operating cash estimate = Revenue - Operating Expenses
            # Investing cash estimate = Change in PPE
            # Financing cash estimate = Borrowings / Capital
            # Add basic operating line
            cf1 = CashFlowLine(
                profile_id=profile.id,
                activity_type="OPERATING",
                line_item_name="Cash Generated from Operations",
                amount=Decimal("0.00"),
                provenance_notes="Derived placeholder from operations",
            )
            db.add(cf1)
            db.commit()

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="classify_trial_balance",
            target_name=f"{profile.entity_name} ({bs_created} BS lines, {pl_created} P&L lines)",
            status="completed",
            result_summary=f"Classified {len(tb_entries)} TB entries into {bs_created} BS lines and {pl_created} P&L lines",
            user_action="Classify Statements",
        )
        return {"balance_sheet_lines": bs_created, "profit_loss_lines": pl_created}

    # -------------------------------------------------------------
    # Workbook & CSV Parser
    # -------------------------------------------------------------

    @staticmethod
    def parse_and_ingest_file(
        db: Session,
        user_id: int,
        profile_id: int,
        filename: str,
        file_bytes: bytes,
        sheet_type: str = "TRIAL_BALANCE",
    ) -> Dict[str, Any]:
        """
        Parses uploaded .csv, .xlsx, or .xls file, extracting ledger records with strict
        provenance: source_document, source_sheet, source_row, source_cell.
        File bytes remain immutable.
        """
        profile = FSService.get_profile(db, user_id, profile_id)
        imported_count = 0
        fn_lower = filename.lower()

        if fn_lower.endswith(".csv"):
            text_data = file_bytes.decode("utf-8", errors="replace")
            reader = csv.reader(io.StringIO(text_data))
            rows = list(reader)
            if not rows:
                raise HTTPException(status_code=400, detail="Uploaded CSV file is empty.")

            # Identify header row
            header_row_idx = 0
            for idx, r in enumerate(rows[:5]):
                lowers = [c.lower().strip() for c in r]
                if any(k in lowers for k in ("account", "particulars", "ledger", "account name", "debit", "credit")):
                    header_row_idx = idx
                    break

            headers = [c.lower().strip() for c in rows[header_row_idx]]

            def find_col(aliases: List[str]) -> Optional[int]:
                for a in aliases:
                    if a in headers:
                        return headers.index(a)
                return None

            col_code = find_col(["code", "account code", "account_code", "ledger code", "acc no", "acc_no"])
            col_name = find_col(["account", "particulars", "account name", "account_name", "ledger", "name", "ledger name"])
            col_category = find_col(["category", "type", "account_category", "group", "head"])
            col_debit = find_col(["debit", "debit amount", "dr", "debit (inr)", "debit rs"])
            col_credit = find_col(["credit", "credit amount", "cr", "credit (inr)", "credit rs"])
            col_amount = find_col(["amount", "balance", "net amount"])

            if col_name is None:
                col_name = 0 if len(headers) > 0 else None

            entries: List[TrialBalanceEntry] = []
            for r_idx in range(header_row_idx + 1, len(rows)):
                row_vals = rows[r_idx]
                if not row_vals or not any(row_vals):
                    continue

                acct_name = row_vals[col_name].strip() if col_name is not None and col_name < len(row_vals) else ""
                if not acct_name or acct_name.lower().startswith("total"):
                    continue

                acct_code = row_vals[col_code].strip() if col_code is not None and col_code < len(row_vals) else None
                acct_cat = row_vals[col_category].strip().upper() if col_category is not None and col_category < len(row_vals) else None

                # Clean numeric values
                def clean_num(val_str: Optional[str]) -> Decimal:
                    if not val_str:
                        return Decimal("0.00")
                    cleaned = val_str.replace("₹", "").replace("Rs.", "").replace(",", "").strip()
                    try:
                        return Decimal(cleaned)
                    except Exception:
                        return Decimal("0.00")

                dr = clean_num(row_vals[col_debit]) if col_debit is not None and col_debit < len(row_vals) else Decimal("0.00")
                cr = clean_num(row_vals[col_credit]) if col_credit is not None and col_credit < len(row_vals) else Decimal("0.00")

                if col_amount is not None and dr == Decimal("0.00") and cr == Decimal("0.00") and col_amount < len(row_vals):
                    raw_amt = clean_num(row_vals[col_amount])
                    if raw_amt >= 0:
                        dr = raw_amt
                    else:
                        cr = abs(raw_amt)

                # Heuristic category if not given
                if not acct_cat:
                    nl = acct_name.lower()
                    if any(k in nl for k in ("sales", "revenue", "income", "fees")):
                        acct_cat = "REVENUE"
                    elif any(k in nl for k in ("expense", "salary", "rent", "cost", "fee", "purchase", "depreciation")):
                        acct_cat = "EXPENSE"
                    elif any(k in nl for k in ("bank", "cash", "debtor", "stock", "asset", "building", "computer", "receivable")):
                        acct_cat = "ASSET"
                    elif any(k in nl for k in ("capital", "equity", "reserves", "retained")):
                        acct_cat = "EQUITY"
                    else:
                        acct_cat = "LIABILITY"

                entry = TrialBalanceEntry(
                    profile_id=profile.id,
                    account_code=acct_code,
                    account_name=acct_name,
                    account_category=acct_cat,
                    debit_amount=dr,
                    credit_amount=cr,
                    net_balance=dr - cr,
                    source_document=filename,
                    source_sheet="CSV",
                    source_row=r_idx + 1,
                    source_cell=f"A{r_idx + 1}",
                    source_value=str(dr if dr > 0 else cr),
                    provenance_notes=f"Parsed from row {r_idx + 1} of {filename}",
                )
                db.add(entry)
                entries.append(entry)

            db.commit()
            imported_count = len(entries)

        elif fn_lower.endswith(".xlsx") or fn_lower.endswith(".xls"):
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            entries = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                header_row = 1
                headers = []
                for row_idx, row in enumerate(ws.iter_rows(values_only=True, max_row=6), start=1):
                    if not row:
                        continue
                    lowers = [str(c or "").lower().strip() for c in row]
                    if any(k in lowers for k in ("account", "particulars", "ledger", "debit", "credit")):
                        header_row = row_idx
                        headers = lowers
                        break

                if not headers:
                    continue

                def find_col_idx(aliases: List[str]) -> Optional[int]:
                    for a in aliases:
                        if a in headers:
                            return headers.index(a)
                    return None

                col_name = find_col_idx(["account", "particulars", "ledger", "account name", "name"]) or 0
                col_code = find_col_idx(["code", "account code", "account_code", "ledger code"])
                col_cat = find_col_idx(["category", "type", "account_category", "group"])
                col_dr = find_col_idx(["debit", "debit amount", "dr", "debit (inr)"])
                col_cr = find_col_idx(["credit", "credit amount", "cr", "credit (inr)"])

                for r_idx, row in enumerate(ws.iter_rows(values_only=True, min_row=header_row + 1), start=header_row + 1):
                    if not row or not any(row):
                        continue
                    name_val = str(row[col_name] or "").strip() if col_name < len(row) else ""
                    if not name_val or name_val.lower().startswith("total"):
                        continue

                    def clean_val(v: Any) -> Decimal:
                        if v is None:
                            return Decimal("0.00")
                        if isinstance(v, (int, float, Decimal)):
                            return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        s = str(v).replace("₹", "").replace(",", "").strip()
                        try:
                            return Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                        except Exception:
                            return Decimal("0.00")

                    dr_val = clean_val(row[col_dr]) if col_dr is not None and col_dr < len(row) else Decimal("0.00")
                    cr_val = clean_val(row[col_cr]) if col_cr is not None and col_cr < len(row) else Decimal("0.00")
                    code_val = str(row[col_code]).strip() if col_code is not None and col_code < len(row) and row[col_code] else None
                    cat_val = str(row[col_cat]).strip().upper() if col_cat is not None and col_cat < len(row) and row[col_cat] else "ASSET"

                    entry = TrialBalanceEntry(
                        profile_id=profile.id,
                        account_code=code_val,
                        account_name=name_val,
                        account_category=cat_val,
                        debit_amount=dr_val,
                        credit_amount=cr_val,
                        net_balance=dr_val - cr_val,
                        source_document=filename,
                        source_sheet=sheet_name,
                        source_row=r_idx,
                        source_cell=f"{chr(65 + col_name)}{r_idx}",
                        source_value=str(dr_val if dr_val > 0 else cr_val),
                        provenance_notes=f"Parsed from sheet '{sheet_name}', row {r_idx}",
                    )
                    db.add(entry)
                    entries.append(entry)

            db.commit()
            imported_count = len(entries)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{filename}'. Please upload .xlsx, .xls, or .csv.",
            )

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="upload_financial_document",
            target_name=filename,
            status="completed",
            result_summary=f"Ingested {imported_count} financial entries from immutable document {filename}",
            user_action="Upload Financial Statement Document",
        )
        return {
            "filename": filename,
            "imported_entries": imported_count,
            "status": "SUCCESS",
        }

    # -------------------------------------------------------------
    # Calculation Engine & Snapshot Generator
    # -------------------------------------------------------------

    @staticmethod
    def calculate_and_snapshot(
        db: Session, user_id: int, profile_id: int
    ) -> Dict[str, Any]:
        """
        Executes deterministic financial statement calculations:
        1. Trial Balance debit vs credit reconciliation
        2. Balance Sheet Schedule III asset vs equity/liabilities tally
        3. Profit & Loss computation (Revenue, Expenses, EBITDA, PBT, PAT)
        4. Cash Flow reconciliation against Balance Sheet cash
        5. Generates immutable versioned FinancialStatementSnapshot with SHA-256 hash
        6. Runs validation rules and updates Review Center findings
        """
        profile = FSService.get_profile(db, user_id, profile_id)

        tb_entries = profile.trial_balance_entries
        bs_lines = profile.balance_sheet_lines
        pl_lines = profile.profit_loss_lines
        cf_lines = profile.cash_flow_lines

        # Calculate TB
        tb_calc = FSCalculator.calculate_trial_balance(tb_entries)

        # Calculate P&L
        pl_calc = FSCalculator.calculate_profit_loss(pl_lines)

        # Calculate BS
        bs_calc = FSCalculator.calculate_balance_sheet(bs_lines)

        # Extract BS Cash & Bank for CF reconciliation
        bs_cash_amount = None
        for b in bs_lines:
            if b.sub_category in ("CASH_BANK", "CASH", "BANK") or "cash" in b.line_item_name.lower() or "bank" in b.line_item_name.lower():
                bs_cash_amount = (bs_cash_amount or Decimal("0.00")) + b.amount

        # Calculate CF
        cf_calc = FSCalculator.calculate_cash_flow(
            cf_lines, opening_cash=Decimal("0.00"), balance_sheet_cash=bs_cash_amount
        )

        # Determine next snapshot version
        latest_snapshot = (
            db.query(FinancialStatementSnapshot)
            .filter(FinancialStatementSnapshot.profile_id == profile.id)
            .order_by(FinancialStatementSnapshot.version.desc())
            .first()
        )
        next_version = (latest_snapshot.version + 1) if latest_snapshot else 1

        # Build payload dictionary for cryptographic hashing
        payload_dict = {
            "profile_id": profile.id,
            "entity_name": profile.entity_name,
            "financial_year": profile.financial_year,
            "reporting_period": profile.reporting_period,
            "framework": profile.framework,
            "version": next_version,
            "trial_balance": {
                "total_debit": str(tb_calc["total_debit"]),
                "total_credit": str(tb_calc["total_credit"]),
                "difference": str(tb_calc["difference"]),
                "is_balanced": tb_calc["is_balanced"],
            },
            "balance_sheet": {
                "total_non_current_assets": str(bs_calc["total_non_current_assets"]),
                "total_current_assets": str(bs_calc["total_current_assets"]),
                "total_assets": str(bs_calc["total_assets"]),
                "total_equity": str(bs_calc["total_equity"]),
                "total_non_current_liabilities": str(bs_calc["total_non_current_liabilities"]),
                "total_current_liabilities": str(bs_calc["total_current_liabilities"]),
                "total_liabilities": str(bs_calc["total_liabilities"]),
                "total_equity_and_liabilities": str(bs_calc["total_equity_and_liabilities"]),
                "balance_difference": str(bs_calc["balance_difference"]),
                "is_balanced": bs_calc["is_balanced"],
            },
            "profit_loss": {
                "total_revenue": str(pl_calc["total_revenue"]),
                "total_expenses": str(pl_calc["total_expenses"]),
                "ebitda": str(pl_calc["ebitda"]),
                "profit_before_tax": str(pl_calc["profit_before_tax"]),
                "tax_expense": str(pl_calc["tax_expense"]),
                "profit_after_tax": str(pl_calc["profit_after_tax"]),
            },
            "cash_flow": {
                "net_cash_operating": str(cf_calc["net_cash_operating"]),
                "net_cash_investing": str(cf_calc["net_cash_investing"]),
                "net_cash_financing": str(cf_calc["net_cash_financing"]),
                "net_change_in_cash": str(cf_calc["net_change_in_cash"]),
                "closing_cash": str(cf_calc["closing_cash"]),
                "cash_matches_balance_sheet": cf_calc["cash_matches_balance_sheet"],
            },
        }

        canonical_json = json.dumps(payload_dict, sort_keys=True)
        snapshot_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        # Save immutable snapshot
        snapshot = FinancialStatementSnapshot(
            profile_id=profile.id,
            version=next_version,
            snapshot_hash=snapshot_hash,
            tb_total_debit=tb_calc["total_debit"],
            tb_total_credit=tb_calc["total_credit"],
            tb_difference=tb_calc["difference"],
            tb_is_balanced=tb_calc["is_balanced"],
            total_non_current_assets=bs_calc["total_non_current_assets"],
            total_current_assets=bs_calc["total_current_assets"],
            total_assets=bs_calc["total_assets"],
            total_equity=bs_calc["total_equity"],
            total_non_current_liabilities=bs_calc["total_non_current_liabilities"],
            total_current_liabilities=bs_calc["total_current_liabilities"],
            total_equity_and_liabilities=bs_calc["total_equity_and_liabilities"],
            balance_difference=bs_calc["balance_difference"],
            is_balance_sheet_balanced=bs_calc["is_balanced"],
            total_revenue=pl_calc["total_revenue"],
            total_expenses=pl_calc["total_expenses"],
            profit_before_tax=pl_calc["profit_before_tax"],
            tax_expense=pl_calc["tax_expense"],
            profit_after_tax=pl_calc["profit_after_tax"],
            net_cash_operating=cf_calc["net_cash_operating"],
            net_cash_investing=cf_calc["net_cash_investing"],
            net_cash_financing=cf_calc["net_cash_financing"],
            net_change_in_cash=cf_calc["net_change_in_cash"],
            opening_cash=cf_calc["opening_cash"],
            closing_cash=cf_calc["closing_cash"],
            statement_payload_json=canonical_json,
        )
        db.add(snapshot)

        # Run Validation Rules
        rule_findings = FSValidator.validate_profile(
            profile=profile,
            tb_entries=tb_entries,
            bs_lines=bs_lines,
            pl_lines=pl_lines,
            cf_lines=cf_lines,
            tb_calc=tb_calc,
            bs_calc=bs_calc,
            pl_calc=pl_calc,
            cf_calc=cf_calc,
        )

        # Merge findings: preserve existing accountant decisions
        existing_findings = {f.finding_type: f for f in profile.findings}
        for rf in rule_findings:
            f_type = rf["finding_type"]
            if f_type in existing_findings:
                # Update current variance & evidence while preserving manual decisions
                ef = existing_findings[f_type]
                ef.expected = rf["expected"]
                ef.actual = rf["actual"]
                ef.variance = rf["variance"]
                ef.evidence = rf["evidence"]
                ef.possible_cause = rf["possible_cause"]
                ef.proven_cause = rf["proven_cause"]
            else:
                new_finding = FinancialStatementFinding(
                    profile_id=profile.id,
                    finding_type=rf["finding_type"],
                    severity=rf["severity"],
                    status=rf["status"],
                    category=rf["category"],
                    title=rf["title"],
                    description=rf["description"],
                    expected=rf["expected"],
                    actual=rf["actual"],
                    variance=rf["variance"],
                    possible_cause=rf["possible_cause"],
                    proven_cause=rf["proven_cause"],
                    evidence=rf["evidence"],
                    source_document=rf["source_document"],
                    source_sheet=rf["source_sheet"],
                    source_row=rf["source_row"],
                    source_cell=rf["source_cell"],
                )
                db.add(new_finding)

        # Determine workflow status
        has_critical_findings = any(
            f.severity in ("CRITICAL", "HIGH") and f.status in ("REVIEW_REQUIRED", "UNDER_REVIEW")
            for f in profile.findings
        ) or any(
            rf["severity"] in ("CRITICAL", "HIGH") for rf in rule_findings
        )

        if profile.status != "APPROVED":
            if has_critical_findings:
                profile.status = "REVIEW_REQUIRED"
            elif profile.status == "DRAFT":
                profile.status = "ANALYZED"

        db.commit()
        db.refresh(snapshot)
        db.refresh(profile)

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="calculate_and_snapshot",
            target_name=f"{profile.entity_name} (Snapshot v{next_version})",
            status="completed",
            result_summary=(
                f"Generated Snapshot v{next_version} [SHA256: {snapshot_hash[:12]}...]. "
                f"TB diff: ₹{tb_calc['difference']}, BS diff: ₹{bs_calc['balance_difference']}, "
                f"PAT: ₹{pl_calc['profit_after_tax']}. Generated {len(rule_findings)} review findings."
            ),
            user_action="Calculate Financial Statements",
            report_reference=snapshot_hash,
        )

        return {
            "snapshot_version": next_version,
            "snapshot_hash": snapshot_hash,
            "status": profile.status,
            "trial_balance": tb_calc,
            "balance_sheet": bs_calc,
            "profit_loss": pl_calc,
            "cash_flow": cf_calc,
            "findings_count": len(profile.findings),
            "eligible_for_approval": (
                not has_critical_findings
                and tb_calc["is_balanced"]
                and bs_calc["is_balanced"]
            ),
        }

    # -------------------------------------------------------------
    # Overview Summary & Status Safety Transition
    # -------------------------------------------------------------

    @staticmethod
    def get_overview(db: Session, user_id: int, profile_id: int) -> Dict[str, Any]:
        profile = FSService.get_profile(db, user_id, profile_id)
        latest_snapshot = (
            db.query(FinancialStatementSnapshot)
            .filter(FinancialStatementSnapshot.profile_id == profile.id)
            .order_by(FinancialStatementSnapshot.version.desc())
            .first()
        )

        unresolved_findings = (
            db.query(FinancialStatementFinding)
            .filter(
                FinancialStatementFinding.profile_id == profile.id,
                FinancialStatementFinding.status.in_(["REVIEW_REQUIRED", "UNDER_REVIEW"]),
            )
            .all()
        )
        critical_unresolved = [f for f in unresolved_findings if f.severity in ("CRITICAL", "HIGH")]

        tb_calc = FSCalculator.calculate_trial_balance(profile.trial_balance_entries) if profile.trial_balance_entries else None
        bs_calc = FSCalculator.calculate_balance_sheet(profile.balance_sheet_lines) if profile.balance_sheet_lines else None
        pl_calc = FSCalculator.calculate_profit_loss(profile.profit_loss_lines) if profile.profit_loss_lines else None

        tb_diff = tb_calc["difference"] if tb_calc else None
        tb_balanced = tb_calc["is_balanced"] if tb_calc else True
        bs_balanced = bs_calc["is_balanced"] if bs_calc else True

        eligible = (
            len(critical_unresolved) == 0
            and tb_balanced
            and bs_balanced
            and (bool(profile.trial_balance_entries) or bool(profile.balance_sheet_lines))
        )

        return {
            "profile_id": profile.id,
            "entity_name": profile.entity_name,
            "financial_year": profile.financial_year,
            "reporting_period": profile.reporting_period,
            "framework": profile.framework,
            "status": profile.status,
            "total_assets": bs_calc["total_assets"] if bs_calc else (latest_snapshot.total_assets if latest_snapshot else None),
            "total_liabilities": bs_calc["total_liabilities"] if bs_calc else (latest_snapshot.total_non_current_liabilities + latest_snapshot.total_current_liabilities if latest_snapshot else None),
            "total_equity": bs_calc["total_equity"] if bs_calc else (latest_snapshot.total_equity if latest_snapshot else None),
            "total_revenue": pl_calc["total_revenue"] if pl_calc else (latest_snapshot.total_revenue if latest_snapshot else None),
            "total_expenses": pl_calc["total_expenses"] if pl_calc else (latest_snapshot.total_expenses if latest_snapshot else None),
            "net_profit": pl_calc["profit_after_tax"] if pl_calc else (latest_snapshot.profit_after_tax if latest_snapshot else None),
            "closing_cash": latest_snapshot.closing_cash if latest_snapshot else None,
            "trial_balance_difference": tb_diff,
            "is_tb_balanced": tb_balanced,
            "is_bs_balanced": bs_balanced,
            "unresolved_findings_count": len(unresolved_findings),
            "eligible_for_approval": eligible,
            "latest_snapshot_hash": latest_snapshot.snapshot_hash if latest_snapshot else None,
        }

    @staticmethod
    def transition_status(
        db: Session, user_id: int, profile_id: int, target_status: str, notes: Optional[str] = None
    ) -> FinancialStatementProfile:
        """
        Guards workflow transitions with strict approval safety:
        - NEVER allows APPROVED if:
          1. Critical/High findings remain unresolved
          2. Trial Balance is unbalanced
          3. Balance Sheet does not balance
          4. Required source data is missing
        """
        profile = FSService.get_profile(db, user_id, profile_id)
        target = target_status.upper().strip()

        allowed_statuses = ("DRAFT", "ANALYZED", "REVIEW_REQUIRED", "UNDER_REVIEW", "APPROVED")
        if target not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid target status '{target}'. Must be one of: {allowed_statuses}",
            )

        if target == "APPROVED":
            # Safety Gate 1: Check unresolved critical/high findings
            unresolved_critical = (
                db.query(FinancialStatementFinding)
                .filter(
                    FinancialStatementFinding.profile_id == profile.id,
                    FinancialStatementFinding.severity.in_(["CRITICAL", "HIGH"]),
                    FinancialStatementFinding.status.in_(["REVIEW_REQUIRED", "UNDER_REVIEW"]),
                )
                .all()
            )
            if unresolved_critical:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cannot approve statements: {len(unresolved_critical)} critical/high review "
                        f"finding(s) remain unresolved. Accountant must review all critical discrepancies first."
                    ),
                )

            # Safety Gate 2: Check Trial Balance equality
            if profile.trial_balance_entries:
                tb_calc = FSCalculator.calculate_trial_balance(profile.trial_balance_entries)
                if not tb_calc["is_balanced"]:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Approval rejected: Trial Balance is unbalanced by ₹{tb_calc['difference']:,.2f}. "
                            "Books must balance before statutory sign-off."
                        ),
                    )

            # Safety Gate 3: Check Balance Sheet tally
            if profile.balance_sheet_lines:
                bs_calc = FSCalculator.calculate_balance_sheet(profile.balance_sheet_lines)
                if not bs_calc["is_balanced"]:
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"Approval rejected: Balance Sheet does not balance. "
                            f"Assets differ from Equity & Liabilities by ₹{bs_calc['balance_difference']:,.2f}."
                        ),
                    )

            # Safety Gate 4: Source data presence
            if not profile.trial_balance_entries and not profile.balance_sheet_lines:
                raise HTTPException(
                    status_code=400,
                    detail="Approval rejected: No source financial statements data found.",
                )

            profile.status = "APPROVED"
            profile.approved_at = datetime.now(timezone.utc)
            profile.approved_by_user_id = user_id
            profile.approval_notes = notes

            HistoryService.record_activity(
                db=db,
                user_id=user_id,
                module="financial_statements",
                action="approve_financial_statements",
                target_name=f"{profile.entity_name} ({profile.financial_year})",
                status="completed",
                result_summary=f"Accountant formally approved Financial Statements for {profile.entity_name}. Notes: {notes or 'None'}",
                user_action="Approve Financial Statements",
            )
        else:
            profile.status = target
            if notes:
                profile.approval_notes = notes

            HistoryService.record_activity(
                db=db,
                user_id=user_id,
                module="financial_statements",
                action="update_status",
                target_name=f"{profile.entity_name} ({profile.financial_year})",
                status="completed",
                result_summary=f"Status changed to '{target}'. Notes: {notes or 'None'}",
                user_action=f"Change Status to {target}",
            )

        db.commit()
        db.refresh(profile)
        return profile

    # -------------------------------------------------------------
    # Finding Decisions
    # -------------------------------------------------------------

    @staticmethod
    def apply_finding_decision(
        db: Session,
        user_id: int,
        finding_id: int,
        decision: str,
        notes: Optional[str] = None,
    ) -> FinancialStatementFinding:
        finding = (
            db.query(FinancialStatementFinding)
            .join(FinancialStatementProfile)
            .filter(
                FinancialStatementFinding.id == finding_id,
                FinancialStatementProfile.user_id == user_id,
            )
            .first()
        )
        if not finding:
            raise HTTPException(
                status_code=404,
                detail=f"Financial statement review finding #{finding_id} not found.",
            )

        dec = decision.upper().strip()
        if dec in ("ACCEPT", "ACCEPTED", "CONFIRM", "CONFIRMED"):
            finding.status = "APPROVED"
            finding.accountant_decision = "ACCEPTED"
        elif dec in ("REJECT", "REJECTED"):
            finding.status = "REJECTED"
            finding.accountant_decision = "REJECTED"
        elif dec in ("OVERRIDE", "OVERRIDDEN"):
            finding.status = "APPROVED"
            finding.accountant_decision = "OVERRIDDEN"
        else:
            finding.status = "UNDER_REVIEW"
            finding.accountant_decision = dec

        finding.decision_notes = notes
        finding.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(finding)

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="finding_decision",
            target_name=f"Finding #{finding.id} ({finding.finding_type})",
            status="completed",
            result_summary=f"Accountant recorded decision '{finding.accountant_decision}' on finding #{finding.id}. Notes: {notes or 'None'}",
            user_action=f"Decision: {finding.accountant_decision}",
        )
        return finding

    # -------------------------------------------------------------
    # Export Accountant Report (CSV / Plain Text)
    # -------------------------------------------------------------

    @staticmethod
    def generate_export_report_csv(
        db: Session, user_id: int, profile_id: int
    ) -> str:
        """
        Creates comprehensive accountant preparation report clearly labeled:
        'Financial Statements — Accountant Review Required'
        Never claims statutory filing/submission.
        """
        profile = FSService.get_profile(db, user_id, profile_id)
        latest_snapshot = (
            db.query(FinancialStatementSnapshot)
            .filter(FinancialStatementSnapshot.profile_id == profile.id)
            .order_by(FinancialStatementSnapshot.version.desc())
            .first()
        )

        output = io.StringIO()
        writer = csv.writer(output)

        # 1. Header & Disclaimer
        writer.writerow(["================================================================================"])
        writer.writerow(["FINANCIAL STATEMENTS — ACCOUNTANT REVIEW REQUIRED"])
        writer.writerow(["CONFIDENTIAL — PREPARED FOR ACCOUNTANT REVIEW ONLY — NOT A STATUTORY SUBMISSION"])
        writer.writerow(["================================================================================"])
        writer.writerow([])
        writer.writerow(["Entity Name", profile.entity_name])
        writer.writerow(["CIN / PAN", profile.cin_or_pan or "—"])
        writer.writerow(["Financial Year", profile.financial_year])
        writer.writerow(["Reporting Period", profile.reporting_period])
        writer.writerow(["Accounting Framework", profile.framework])
        writer.writerow(["Workflow Status", profile.status])
        writer.writerow(["Approved At", str(profile.approved_at) if profile.approved_at else "Not Approved"])
        writer.writerow(["Latest Snapshot Hash (SHA-256)", latest_snapshot.snapshot_hash if latest_snapshot else "None"])
        writer.writerow(["Report Generated At (UTC)", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")])
        writer.writerow([])

        # 2. Trial Balance Section
        writer.writerow(["--- TRIAL BALANCE VALIDATION ---"])
        tb_calc = FSCalculator.calculate_trial_balance(profile.trial_balance_entries)
        writer.writerow(["Total Debits (INR)", str(tb_calc["total_debit"])])
        writer.writerow(["Total Credits (INR)", str(tb_calc["total_credit"])])
        writer.writerow(["Difference (INR)", str(tb_calc["difference"])])
        writer.writerow(["Status", "VALID (Balanced)" if tb_calc["is_balanced"] else "REVIEW_REQUIRED (Unbalanced)"])
        writer.writerow([])
        writer.writerow(["Account Code", "Account Name", "Category", "Debit", "Credit", "Source Doc", "Sheet", "Row", "Cell"])
        for e in profile.trial_balance_entries:
            writer.writerow([
                e.account_code or "",
                e.account_name,
                e.account_category,
                str(e.debit_amount),
                str(e.credit_amount),
                e.source_document or "",
                e.source_sheet or "",
                str(e.source_row or ""),
                e.source_cell or "",
            ])
        writer.writerow([])

        # 3. Balance Sheet Section
        writer.writerow(["--- BALANCE SHEET (SCHEDULE III) ---"])
        bs_calc = FSCalculator.calculate_balance_sheet(profile.balance_sheet_lines)
        writer.writerow(["Total Non-Current Assets", str(bs_calc["total_non_current_assets"])])
        writer.writerow(["Total Current Assets", str(bs_calc["total_current_assets"])])
        writer.writerow(["TOTAL ASSETS", str(bs_calc["total_assets"])])
        writer.writerow(["Total Equity", str(bs_calc["total_equity"])])
        writer.writerow(["Total Non-Current Liabilities", str(bs_calc["total_non_current_liabilities"])])
        writer.writerow(["Total Current Liabilities", str(bs_calc["total_current_liabilities"])])
        writer.writerow(["TOTAL EQUITY & LIABILITIES", str(bs_calc["total_equity_and_liabilities"])])
        writer.writerow(["Balance Difference", str(bs_calc["balance_difference"])])
        writer.writerow(["Tally Status", "BALANCED" if bs_calc["is_balanced"] else "MISMATCH — REVIEW_REQUIRED"])
        writer.writerow([])
        writer.writerow(["Classification", "Sub-Category", "Line Item", "Amount (INR)", "Note", "Source Doc", "Sheet", "Row"])
        for b in profile.balance_sheet_lines:
            writer.writerow([
                b.classification,
                b.sub_category,
                b.line_item_name,
                str(b.amount),
                b.schedule_note_number or "",
                b.source_document or "",
                b.source_sheet or "",
                str(b.source_row or ""),
            ])
        writer.writerow([])

        # 4. Profit & Loss Section
        writer.writerow(["--- PROFIT & LOSS STATEMENT ---"])
        pl_calc = FSCalculator.calculate_profit_loss(profile.profit_loss_lines)
        writer.writerow(["Revenue from Operations", str(pl_calc["revenue_from_operations"])])
        writer.writerow(["Other Income", str(pl_calc["other_income"])])
        writer.writerow(["TOTAL REVENUE", str(pl_calc["total_revenue"])])
        writer.writerow(["Cost of Materials", str(pl_calc["cost_of_materials"])])
        writer.writerow(["Employee Benefits", str(pl_calc["employee_benefits"])])
        writer.writerow(["Finance Costs", str(pl_calc["finance_costs"])])
        writer.writerow(["Depreciation & Amortization", str(pl_calc["depreciation"])])
        writer.writerow(["Other Expenses", str(pl_calc["other_expenses"])])
        writer.writerow(["TOTAL EXPENSES", str(pl_calc["total_expenses"])])
        writer.writerow(["EBITDA", str(pl_calc["ebitda"])])
        writer.writerow(["PROFIT BEFORE TAX (PBT)", str(pl_calc["profit_before_tax"])])
        writer.writerow(["Tax Expense", str(pl_calc["tax_expense"])])
        writer.writerow(["PROFIT AFTER TAX (PAT)", str(pl_calc["profit_after_tax"])])
        writer.writerow([])
        writer.writerow(["Category", "Line Item", "Amount (INR)", "Note", "Source Doc", "Sheet", "Row"])
        for p in profile.profit_loss_lines:
            writer.writerow([
                p.category,
                p.line_item_name,
                str(p.amount),
                p.schedule_note_number or "",
                p.source_document or "",
                p.source_sheet or "",
                str(p.source_row or ""),
            ])
        writer.writerow([])

        # 5. Cash Flow Section
        writer.writerow(["--- CASH FLOW STATEMENT ---"])
        bs_cash_amount = None
        for b in profile.balance_sheet_lines:
            if b.sub_category in ("CASH_BANK", "CASH", "BANK") or "cash" in b.line_item_name.lower():
                bs_cash_amount = (bs_cash_amount or Decimal("0.00")) + b.amount

        cf_calc = FSCalculator.calculate_cash_flow(
            profile.cash_flow_lines, balance_sheet_cash=bs_cash_amount
        )
        writer.writerow(["Net Cash from Operating Activities", str(cf_calc["net_cash_operating"])])
        writer.writerow(["Net Cash from Investing Activities", str(cf_calc["net_cash_investing"])])
        writer.writerow(["Net Cash from Financing Activities", str(cf_calc["net_cash_financing"])])
        writer.writerow(["Net Change in Cash", str(cf_calc["net_change_in_cash"])])
        writer.writerow(["Opening Cash Balance", str(cf_calc["opening_cash"])])
        writer.writerow(["Closing Cash Balance", str(cf_calc["closing_cash"])])
        writer.writerow(["Balance Sheet Cash & Bank", str(cf_calc["balance_sheet_cash"]) if cf_calc["balance_sheet_cash"] is not None else "—"])
        writer.writerow(["Reconciliation Status", "RECONCILED" if cf_calc["cash_matches_balance_sheet"] else "DISCREPANCY DETECTED"])
        writer.writerow([])

        # 6. Review Center Findings Section
        writer.writerow(["--- REVIEW FINDINGS & DISCREPANCIES ---"])
        writer.writerow(["ID", "Finding Type", "Severity", "Status", "Title", "Variance", "Possible Cause", "Proven Cause", "Accountant Decision", "Decision Notes"])
        for f in profile.findings:
            writer.writerow([
                f"fs_{f.id}",
                f.finding_type,
                f.severity,
                f.status,
                f.title,
                str(f.variance or "0.00"),
                f.possible_cause or "",
                f.proven_cause or "",
                f.accountant_decision or "",
                f.decision_notes or "",
            ])

        HistoryService.record_activity(
            db=db,
            user_id=user_id,
            module="financial_statements",
            action="export_report",
            target_name=f"{profile.entity_name} ({profile.financial_year})",
            status="completed",
            result_summary=f"Exported accountant preparation report for {profile.entity_name} ({profile.financial_year})",
            user_action="Export Accountant Preparation Report",
        )

        return output.getvalue()
