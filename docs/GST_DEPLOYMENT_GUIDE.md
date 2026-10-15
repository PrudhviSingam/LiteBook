# LiteBooks GST Module: Production Deployment & Hardening Guide

## 1. Overview
The LiteBooks GST Module provides end-to-end statutory compliance for Indian businesses, including:
- **GSTR-1**: Outward supplies aggregation (Tables 4, 5, 6A, 7, 8, 9B CDNR).
- **GSTR-3B**: Inward and outward tax summary, statutory set-off hierarchy (IGST -> CGST -> SGST), and net payable calculation.
- **GSTR-2B Reconciliation**: Multi-tier fuzzy matching between books of accounts and portal 2B data with auditor override preservation.
- **Production Hardening**: Deterministic SHA-256 calculation snapshots, stale summary detection, idempotent imports, role-based workflow guards, and period locking.

---

## 2. Environment Configuration

Ensure the following variables are set in `backend/.env`:

```env
# Database URL (PostgreSQL for Production, SQLite for Local Dev)
DATABASE_URL=postgresql://user:password@localhost:5432/litebooks_db
# or SQLite dev: sqlite:///./finance_ai.db

# Security & JWT Authentication
SECRET_KEY=your-secure-256-bit-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Multi-tenant and App Settings
PROJECT_NAME="LiteBooks"
API_V1_STR="/api/v1"

# CORS Allowed Origins
BACKEND_CORS_ORIGINS=["http://localhost:5173","https://app.litebooks.ai"]
```

---

## 3. Database Migrations (Alembic)

Database schema synchronization at runtime is **deprecated and disabled** in production. All schema evolution is managed via Alembic migrations.

### Migration Commands

1. **Verify Current Migration Status**:
   ```bash
   alembic current
   ```

2. **Inspect Migration Heads**:
   ```bash
   alembic heads
   # Expected output: 001_gst_module (head)
   ```

3. **Fresh Database Setup**:
   To initialize all core and GST tables on a new PostgreSQL/SQLite database:
   ```bash
   alembic upgrade head
   ```

4. **Existing Database Upgrade**:
   To safely add missing GST tables, columns, indexes, and constraints to an existing database:
   ```bash
   alembic upgrade head
   ```
   *Note: Migration `001_gst_module` uses inspector-based introspection and batch alteration for zero downtime and safe idempotent application.*

5. **Rollback (Downgrade)**:
   ```bash
   alembic downgrade base
   ```

---

## 4. API Endpoint Prefixes & Route Structure

The GST module is mounted under two identical prefixes for backwards compatibility and forward standardization:
- Primary: `/api/gst`
- Versioned: `/api/v1/gst`

### Core Endpoints:
- `GET/POST /registrations`: Organization-scoped GSTIN registrations.
- `GET/POST /periods`: Monthly filing periods (`YYYY-MM`) with auto-derived Financial Year (`YYYY-YY`).
- `POST /periods/{id}/status`: Strict workflow transitions (`draft` -> `under_review` -> `approved` -> `filed` -> `locked`).
- `GET/POST/DELETE /periods/{id}/sales`: Sales invoices with statutory validation and normalization.
- `GET/POST/DELETE /periods/{id}/purchases`: Books purchase invoices.
- `GET/POST /periods/{id}/gstr2b`: GSTR-2B portal records and bulk idempotent import.
- `GET/POST /periods/{id}/gstr1/summary`: GSTR-1 aggregation and deterministic recalculation.
- `GET/POST /periods/{id}/gstr3b/summary`: GSTR-3B tax computation, statutory set-off, and recalculation.
- `POST /periods/{id}/reconciliation/run`: Multi-tier matching engine with manual decision preservation.

---

## 5. Workflow States & Immutability Rules

The GST filing lifecycle enforces strict state machine rules:

```
[DRAFT] <---------> [UNDER_REVIEW] ---------> [APPROVED] ---------> [FILED] ---------> [LOCKED]
 (Editable)          (Review Only)             (Ready)           (Immutable)         (Frozen)
```

1. **DRAFT**:
   - Invoices, purchases, and 2B records can be added, modified, or deleted.
   - Summaries can be recalculated anytime.
2. **UNDER_REVIEW**:
   - Invoices cannot receive edits or deletions without returning to `draft`.
   - Auditors can run reconciliation and apply manual match/exclude decisions.
3. **APPROVED**:
   - **Pre-condition**: All summary calculations must be fresh (`is_stale == False`) and no blocking statutory validation issues can exist.
   - Prevents filing erroneous returns.
4. **FILED**:
   - **Pre-condition**: Requires valid statutory ARN (`arn`) and acknowledgment metadata.
   - Invoices, purchases, summaries, and reconciliations are permanently locked against modifications.
5. **LOCKED**:
   - Completely frozen for accounting audit.
   - Recalculation, invoice addition, status transitions, and deletions return HTTP 400 Bad Request.

---

## 6. GSTR-2B Import Safeguards

When importing CP (Common Portal) GSTR-2B JSON payloads:
- **Payload & Size Validation**: Enforces maximum batch limit (5,000 records) and validates document schema.
- **GSTIN & Period Consistency**: Reject files that do not match the selected registration GSTIN and filing period.
- **Checksum & Idempotency**: SHA-256 payload checksum (`import_checksum`) is stored per batch. Duplicate uploads are detected and processed idempotently without creating duplicate portal records.
- **Raw Payload Preservation**: The original portal payload is preserved in `raw_payload` for compliance provenance.

---

## 7. Reconciliation Safeguards

- **Invoice Normalization**: Strips punctuation, whitespace, and leading zeros (`INV/2023-24/0042` -> `INV20232442`) while preserving `original_invoice_number`.
- **Configurable Tolerances**: Supports explicit amount tolerance (default: ₹1.00) and date tolerance (default: 30 days).
- **Manual Decision Preservation**: When re-running reconciliation after modifying books, manual auditor decisions (`match`, `exclude`, `dispute`) are preserved across recalculation runs (`manual_decision_preserved = True`).
- **Company Scoping**: Cross-organization or cross-company reconciliation is strictly rejected.

---

## 8. Verification & Test Commands

### Backend Verification:
```bash
# GST Hardening and E2E Tests (15 tests)
python -m pytest tests/test_gst_module.py tests/test_gst_hardening.py -v

# Full Backend Suite (159 tests)
python -m pytest tests/ -v

# Code Quality & Formatting
ruff check app/modules/gst tests/test_gst_module.py tests/test_gst_hardening.py
ruff format --check app/modules/gst tests/test_gst_module.py tests/test_gst_hardening.py
```

### Frontend Verification:
```bash
# Vitest Component & Hardening Tests (10 tests)
npm test -- --run

# TypeScript Type-Check & Production Build
npm run build

# Static Linting
npx oxlint
```

---

## 9. Statutory Limitations & Professional Accountant Review

The LiteBooks GST Module provides deterministic mathematical aggregation, reconciliation, and validation rules according to Indian GST law. However, certain legal edge cases require professional chartered accountant review:
1. **Ineligible ITC under Section 17(5)**: Goods/services restricted by statute (e.g., motor vehicles, food & beverages, personal consumption) must be explicitly verified and marked using the manual Exclude action.
2. **Reverse Charge Mechanism (RCM)**: Supplies under RCM (Section 9(3)/9(4)) require tax payment via cash ledger rather than ITC offset.
3. **Export / SEZ Supplies without Payment of Tax**: Requires Letter of Undertaking (LUT) submission on the GSTN portal.
4. **Rule 42 / 43 Reversals**: Common credit apportionment between taxable and exempt supplies requires annual year-end true-up.
