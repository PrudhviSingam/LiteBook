import { getAuthToken, clearAuthToken, API_HOST } from './api'
import type {
  GSTRegistration,
  GSTFilingPeriod,
  GSTSalesInvoice,
  GSTPurchaseInvoice,
  GSTR2BRecord,
  GSTReconciliationResult,
  GSTR1Summary,
  GSTR3BSummary,
  ReconciliationSummary,
  GSTPeriodStatus,
  ReconciliationDecision,
} from '../types/gst'

const GST_BASE = `${API_HOST}/api/gst`

async function gstFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = getAuthToken()
  const headers = new Headers(init?.headers || {})
  if (!headers.has('Content-Type') && !(init?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(url, { ...init, headers })
  if (res.status === 401) {
    clearAuthToken()
    window.dispatchEvent(new Event('auth:unauthorized'))
  }
  return res
}

async function handleResponse<T>(res: Response, fallbackMessage: string): Promise<T> {
  if (!res.ok) {
    let errorDetail = fallbackMessage
    try {
      const err = await res.json()
      errorDetail = err.detail || fallbackMessage
    } catch {
      // ignore
    }
    throw new Error(errorDetail)
  }
  return await res.json()
}

// ---------------------------------------------------------------------------
// Registrations
// ---------------------------------------------------------------------------

export async function fetchGSTRegistrations(): Promise<GSTRegistration[]> {
  const res = await gstFetch(`${GST_BASE}/registrations`)
  return handleResponse<GSTRegistration[]>(res, 'Failed to fetch GST registrations')
}

export async function createGSTRegistration(data: {
  gstin: string
  legal_name: string
  trade_name?: string
  state_code: string
  registration_type?: string
  authorized_signatory?: string
}): Promise<GSTRegistration> {
  const res = await gstFetch(`${GST_BASE}/registrations`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  return handleResponse<GSTRegistration>(res, 'Failed to create GST registration')
}

// ---------------------------------------------------------------------------
// Filing Periods
// ---------------------------------------------------------------------------

export async function fetchFilingPeriods(registrationId: string | number): Promise<GSTFilingPeriod[]> {
  const res = await gstFetch(`${GST_BASE}/registrations/${registrationId}/periods`)
  return handleResponse<GSTFilingPeriod[]>(res, 'Failed to fetch filing periods')
}

export async function createFilingPeriod(data: {
  registration_id: string | number
  period: string
  financial_year: string
}): Promise<GSTFilingPeriod> {
  const res = await gstFetch(`${GST_BASE}/periods`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  return handleResponse<GSTFilingPeriod>(res, 'Failed to create filing period')
}

export async function transitionPeriodStatus(
  periodId: string | number,
  newStatus: GSTPeriodStatus,
  notes?: string,
  arn?: string
): Promise<GSTFilingPeriod> {
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/transition`, {
    method: 'POST',
    body: JSON.stringify({ new_status: newStatus, notes, arn }),
  })
  return handleResponse<GSTFilingPeriod>(res, 'Failed to transition filing period status')
}

// ---------------------------------------------------------------------------
// GSTR-1 Summaries & Invoices
// ---------------------------------------------------------------------------

export async function fetchGSTR1Summary(
  periodId: string | number,
  recalculate = false
): Promise<GSTR1Summary> {
  const url = `${GST_BASE}/periods/${periodId}/gstr1/summary${recalculate ? '?recalculate=true' : ''}`
  const res = await gstFetch(url)
  return handleResponse<GSTR1Summary>(res, 'Failed to fetch GSTR-1 summary')
}

export async function fetchSalesInvoices(
  periodId: string | number,
  params?: { invoice_type?: string; validation_status?: string }
): Promise<GSTSalesInvoice[]> {
  const query = new URLSearchParams()
  if (params?.invoice_type) query.append('invoice_type', params.invoice_type)
  if (params?.validation_status) query.append('validation_status', params.validation_status)

  const queryString = query.toString() ? `?${query.toString()}` : ''
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/sales${queryString}`)
  return handleResponse<GSTSalesInvoice[]>(res, 'Failed to fetch sales invoices')
}

export async function createSalesInvoice(
  periodId: string | number,
  data: Partial<GSTSalesInvoice>
): Promise<GSTSalesInvoice> {
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/sales`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  return handleResponse<GSTSalesInvoice>(res, 'Failed to create sales invoice')
}

// ---------------------------------------------------------------------------
// GSTR-3B Summaries
// ---------------------------------------------------------------------------

export async function fetchGSTR3BSummary(
  periodId: string | number,
  recalculate = false
): Promise<GSTR3BSummary> {
  const url = `${GST_BASE}/periods/${periodId}/gstr3b/summary${recalculate ? '?recalculate=true' : ''}`
  const res = await gstFetch(url)
  return handleResponse<GSTR3BSummary>(res, 'Failed to fetch GSTR-3B summary')
}

// ---------------------------------------------------------------------------
// GSTR-2B & Reconciliation
// ---------------------------------------------------------------------------

export async function fetchPurchaseInvoices(
  periodId: string | number,
  matchStatus?: string
): Promise<GSTPurchaseInvoice[]> {
  const query = matchStatus ? `?match_status=${matchStatus}` : ''
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/purchases${query}`)
  return handleResponse<GSTPurchaseInvoice[]>(res, 'Failed to fetch purchase invoices')
}

export async function fetchGSTR2BRecords(
  periodId: string | number,
  matchStatus?: string
): Promise<GSTR2BRecord[]> {
  const query = matchStatus ? `?match_status=${matchStatus}` : ''
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/gstr2b${query}`)
  return handleResponse<GSTR2BRecord[]>(res, 'Failed to fetch GSTR-2B records')
}

export async function bulkImportGSTR2B(
  periodId: string | number,
  records: Array<{
    supplier_gstin: string
    supplier_name: string
    invoice_number: string
    invoice_date: string
    invoice_type?: string
    taxable_value: string | number
    cgst_amount?: string | number
    sgst_amount?: string | number
    igst_amount?: string | number
    cess_amount?: string | number
    total_amount: string | number
    itc_available?: boolean
    filing_status?: string
    gstr1_filing_date?: string
  }>
): Promise<{ message: string; count: number }> {
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/gstr2b/import`, {
    method: 'POST',
    body: JSON.stringify({ records }),
  })
  return handleResponse<{ message: string; count: number }>(res, 'Failed to import GSTR-2B records')
}

export async function runReconciliation(
  periodId: string | number,
  tolerance = 1.0,
  dateToleranceDays = 3
): Promise<GSTReconciliationResult[]> {
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/reconcile`, {
    method: 'POST',
    body: JSON.stringify({
      amount_tolerance: tolerance,
      date_tolerance_days: dateToleranceDays,
    }),
  })
  return handleResponse<GSTReconciliationResult[]>(res, 'Failed to run reconciliation')
}

export async function fetchReconciliationResults(
  periodId: string | number,
  params?: { match_status?: string; accountant_decision?: string }
): Promise<GSTReconciliationResult[]> {
  const query = new URLSearchParams()
  if (params?.match_status) query.append('match_status', params.match_status)
  if (params?.accountant_decision) query.append('accountant_decision', params.accountant_decision)

  const queryString = query.toString() ? `?${query.toString()}` : ''
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/reconciliation/results${queryString}`)
  return handleResponse<GSTReconciliationResult[]>(res, 'Failed to fetch reconciliation results')
}

export async function fetchReconciliationSummary(
  periodId: string | number
): Promise<ReconciliationSummary> {
  const res = await gstFetch(`${GST_BASE}/periods/${periodId}/reconciliation/summary`)
  return handleResponse<ReconciliationSummary>(res, 'Failed to fetch reconciliation summary')
}

export async function submitReconciliationDecision(
  resultId: string | number,
  decision: ReconciliationDecision,
  notes?: string
): Promise<GSTReconciliationResult> {
  const res = await gstFetch(`${GST_BASE}/reconciliation/${resultId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, notes }),
  })
  return handleResponse<GSTReconciliationResult>(res, 'Failed to submit decision')
}



// ---------------------------------------------------------------------------
// File Upload & Bulk Import
// ---------------------------------------------------------------------------

export interface GSTUploadResponse {
  success: boolean
  message: string
  file_type: string
  imported_count: number
  skipped_count: number
  errors: string[]
}

export async function uploadGSTFile(
  periodId: string | number,
  file: File,
  targetType = 'auto'
): Promise<GSTUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('target_type', targetType)

  const token = getAuthToken()
  const headers = new Headers()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(`${GST_BASE}/periods/${periodId}/upload`, {
    method: 'POST',
    headers,
    body: formData,
  })

  return handleResponse<GSTUploadResponse>(res, 'Failed to upload and import GST file')
}

// ---------------------------------------------------------------------------
// Export Reports (GSTR-1, GSTR-3B, GSTR-2B Recon)
// ---------------------------------------------------------------------------

export async function downloadGSTReport(
  periodId: string | number,
  reportType: 'gstr1' | 'gstr3b' | 'reconciliation',
  format: 'csv' | 'json' = 'csv',
  filename?: string
): Promise<void> {
  const token = getAuthToken()
  const headers = new Headers()
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(
    `${GST_BASE}/periods/${periodId}/export/${reportType}?format=${format}`,
    { headers }
  )

  if (!res.ok) {
    throw new Error(`Failed to export ${reportType.toUpperCase()} report`)
  }

  if (format === 'json') {
    const data = await res.json()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `${reportType.toUpperCase()}_Period_${periodId}.json`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } else {
    const blob = await res.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename || `${reportType.toUpperCase()}_Period_${periodId}.csv`
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  }
}

