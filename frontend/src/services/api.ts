import type {
  AssistantChatResponse,
  AssistantFileContext,
  ColumnMappingPreview,
  CorrectionProposal,
  CorrectionProposalInfo,
  DashboardSummaryData,
  DiscrepancyExplanationResponse,
  DocumentItem,
  FindingDecisionRequest,
  GenerateCorrectedWorkbookResponse,
  HistoryRecord,
  ReconciliationSessionResponse,
  ReviewCenterSummary,
  ReviewFindingItem,
  WorkbookInspectionResult,
  DocumentResetResponse,
} from '../types'

export const API_HOST = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/+$/, '') || ''
export const API_BASE = `${API_HOST}/api/v1`
const AUTH_TOKEN_KEY = 'litebooks_auth_token'

export function getAuthToken(): string | null {
  if (typeof localStorage === 'undefined') return null
  return localStorage.getItem(AUTH_TOKEN_KEY)
}

export function setAuthToken(token: string): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.setItem(AUTH_TOKEN_KEY, token)
  }
}

export function clearAuthToken(): void {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem(AUTH_TOKEN_KEY)
  }
}

export async function loginUser(email: string, password: string): Promise<any> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) {
    const errorText = await res.text()
    try {
      const err = JSON.parse(errorText)
      throw new Error(err.detail || 'Incorrect email or password.')
    } catch {
      throw new Error(errorText || 'Incorrect email or password.')
    }
  }
  const data = await res.json()
  if (data.access_token) {
    setAuthToken(data.access_token)
  }
  return data
}

/**
 * Ensures a valid Bearer token exists. If none is stored,
 * auto-authenticates to the default accountant account.
 */
export function isAuthenticated(): boolean {
  return !!getAuthToken()
}

export async function ensureAuthToken(): Promise<string> {
  return getAuthToken() || ''
}

/**
 * Wrapper around fetch that adds Bearer token authorization header and notifies on 401.
 */
async function authFetch(url: string, init?: RequestInit): Promise<Response> {
  const token = getAuthToken()

  const headers = new Headers(init?.headers || {})
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

// ---------------------------------------------------------------------------
// Dashboard APIs
// ---------------------------------------------------------------------------

export async function getDashboardSummary(): Promise<DashboardSummaryData> {
  const res = await authFetch(`${API_BASE}/dashboard/summary`)
  if (!res.ok) {
    throw new Error(`Failed to load dashboard summary (HTTP ${res.status})`)
  }
  return await res.json()
}

// ---------------------------------------------------------------------------
// Review Center APIs
// ---------------------------------------------------------------------------

export async function getReviewCenterFindings(params?: {
  severity?: string
  status?: string
  document_id?: number
  search?: string
}): Promise<ReviewCenterSummary> {
  const q = new URLSearchParams()
  if (params?.severity && params.severity !== 'ALL') q.append('severity', params.severity)
  if (params?.status && params.status !== 'ALL') q.append('status', params.status)
  if (params?.document_id) q.append('document_id', params.document_id.toString())
  if (params?.search) q.append('search', params.search)

  const url = `${API_BASE}/review-center/findings${q.toString() ? `?${q.toString()}` : ''}`
  const res = await authFetch(url)
  if (!res.ok) {
    throw new Error(`Failed to load review center findings (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function updateFindingDecision(
  findingId: string,
  req: FindingDecisionRequest
): Promise<ReviewFindingItem> {
  const res = await authFetch(`${API_BASE}/review-center/findings/${encodeURIComponent(findingId)}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })

  if (!res.ok) {
    const errText = await res.text()
    try {
      const errJson = JSON.parse(errText)
      throw new Error(errJson.detail || 'Failed to update finding decision')
    } catch {
      throw new Error(errText || 'Failed to update finding decision')
    }
  }

  return await res.json()
}

// ---------------------------------------------------------------------------
// Documents APIs
// ---------------------------------------------------------------------------

export async function getDocuments(category?: string): Promise<DocumentItem[]> {
  const url =
    category && category !== 'all'
      ? `${API_BASE}/documents?category=${encodeURIComponent(category)}`
      : `${API_BASE}/documents`
  const res = await authFetch(url)
  if (!res.ok) {
    throw new Error(`Failed to load documents (HTTP ${res.status})`)
  }
  return await res.json()
}

export async function getDocumentAnalysis(documentId: number): Promise<WorkbookInspectionResult> {
  const res = await authFetch(`${API_BASE}/documents/${documentId}/analysis`)
  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || `Failed to load document analysis for ID ${documentId}`)
  }
  return await res.json()
}

export async function uploadDocument(
  file: File,
  category: string = 'general',
  notes?: string
): Promise<DocumentItem> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('category', category)
  if (notes) formData.append('notes', notes)

  const res = await authFetch(`${API_BASE}/documents/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errorText = await res.text()
    try {
      const errJson = JSON.parse(errorText)
      throw new Error(errJson.detail || 'Upload failed')
    } catch {
      throw new Error(errorText || 'Upload failed')
    }
  }

  return await res.json()
}

export async function deleteDocument(id: number): Promise<void> {
  const res = await authFetch(`${API_BASE}/documents/${id}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    throw new Error('Failed to delete document')
  }
}

export async function resetWorkspaceDocuments(): Promise<DocumentResetResponse> {
  const res = await authFetch(`${API_BASE}/documents/reset`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    let errMessage = 'Failed to reset workspace documents.'
    try {
      const err = await res.json()
      if (err.detail) errMessage = err.detail
    } catch {}
    throw new Error(errMessage)
  }
  const data: DocumentResetResponse = await res.json()
  window.dispatchEvent(new CustomEvent('workspace:documents_reset', { detail: data }))
  return data
}


export function getDocumentDownloadUrl(documentId: number): string {
  return `${API_BASE}/documents/${documentId}/download`
}

// ---------------------------------------------------------------------------
// History / Audit APIs
// ---------------------------------------------------------------------------

export async function getHistory(
  module?: string,
  status?: string
): Promise<HistoryRecord[]> {
  const params = new URLSearchParams()
  if (module && module !== 'all') params.append('module', module)
  if (status && status !== 'all') params.append('status', status)

  const res = await authFetch(`${API_BASE}/history?${params.toString()}`)
  if (!res.ok) {
    throw new Error(`Failed to load history (HTTP ${res.status})`)
  }
  return await res.json()
}

// ---------------------------------------------------------------------------
// Reconciliation APIs
// ---------------------------------------------------------------------------

export async function previewReconciliationFile(file: File, sheetName?: string): Promise<ColumnMappingPreview> {
  const formData = new FormData()
  formData.append('file', file)
  if (sheetName) formData.append('sheet_name', sheetName)

  const res = await authFetch(`${API_BASE}/reconciliation/preview-file`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errText = await res.text()
    try {
      const errJson = JSON.parse(errText)
      throw new Error(errJson.detail || 'Failed to preview file')
    } catch {
      throw new Error(errText || 'Failed to preview file')
    }
  }

  return await res.json()
}

export interface RunDifferenceOptions {
  fileA?: File | null
  fileB?: File | null
  fileADocId?: number | null
  fileBDocId?: number | null
  sheetA?: string | null
  sheetB?: string | null
  mappingA?: Record<string, string | null> | null
  mappingB?: Record<string, string | null> | null
  // Legacy aliases
  bankFile?: File | null
  ledgerFile?: File | null
  bankDocId?: number | null
  ledgerDocId?: number | null
  dateToleranceDays?: number
  amountTolerance?: number
}

export async function runReconciliation(
  bankFileOrOptions?: File | null | RunDifferenceOptions,
  ledgerFile?: File | null,
  bankDocId?: number | null,
  ledgerDocId?: number | null,
  dateToleranceDays: number = 1,
  amountTolerance: number = 0.0
): Promise<ReconciliationSessionResponse> {
  const formData = new FormData()

  if (bankFileOrOptions && typeof bankFileOrOptions === 'object' && !('name' in bankFileOrOptions)) {
    const opts = bankFileOrOptions as RunDifferenceOptions
    if (opts.fileA) formData.append('file_a', opts.fileA)
    if (opts.fileB) formData.append('file_b', opts.fileB)
    if (opts.bankFile) formData.append('bank_file', opts.bankFile)
    if (opts.ledgerFile) formData.append('ledger_file', opts.ledgerFile)
    if (opts.fileADocId) formData.append('file_a_document_id', opts.fileADocId.toString())
    if (opts.fileBDocId) formData.append('file_b_document_id', opts.fileBDocId.toString())
    if (opts.bankDocId) formData.append('bank_document_id', opts.bankDocId.toString())
    if (opts.ledgerDocId) formData.append('ledger_document_id', opts.ledgerDocId.toString())
    if (opts.sheetA) formData.append('sheet_a', opts.sheetA)
    if (opts.sheetB) formData.append('sheet_b', opts.sheetB)
    if (opts.mappingA) formData.append('mapping_a', JSON.stringify(opts.mappingA))
    if (opts.mappingB) formData.append('mapping_b', JSON.stringify(opts.mappingB))
    formData.append('date_tolerance_days', (opts.dateToleranceDays ?? 1).toString())
    formData.append('amount_tolerance', (opts.amountTolerance ?? 0.0).toString())
  } else {
    const bFile = bankFileOrOptions as File | null | undefined
    if (bFile) formData.append('bank_file', bFile)
    if (ledgerFile) formData.append('ledger_file', ledgerFile)
    if (bankDocId) formData.append('bank_document_id', bankDocId.toString())
    if (ledgerDocId) formData.append('ledger_document_id', ledgerDocId.toString())
    formData.append('date_tolerance_days', dateToleranceDays.toString())
    formData.append('amount_tolerance', amountTolerance.toString())
  }

  const res = await authFetch(`${API_BASE}/reconciliation/run`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errText = await res.text()
    try {
      const errJson = JSON.parse(errText)
      throw new Error(errJson.detail || 'Reconciliation failed')
    } catch {
      throw new Error(errText || 'Reconciliation failed')
    }
  }

  return await res.json()
}

export async function getReconciliationSession(sessionId: number): Promise<ReconciliationSessionResponse> {
  const res = await authFetch(`${API_BASE}/reconciliation/results/${sessionId}`)
  if (!res.ok) throw new Error(`Failed to load session ${sessionId}`)
  return await res.json()
}

export async function listReconciliationSessions(): Promise<any[]> {
  try {
    const res = await authFetch(`${API_BASE}/reconciliation/sessions`)
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export function getReconciliationReportUrl(sessionId: number): string {
  return `${API_BASE}/reconciliation/results/${sessionId}/report`
}

export function getDifferenceReportUrl(sessionId: number): string {
  return `${API_BASE}/reconciliation/results/${sessionId}/difference-report`
}

export async function updateItemReviewStatus(
  sessionId: number,
  itemId: string,
  status: 'CONFIRMED' | 'REVIEWED' | 'IGNORED' | string
): Promise<any> {
  const res = await authFetch(`${API_BASE}/reconciliation/results/${sessionId}/items/${itemId}/review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  })
  if (!res.ok) throw new Error('Failed to update item review status')
  return await res.json()
}

export async function inspectWorkbook(
  file: File,
  uploadCategory?: string
): Promise<WorkbookInspectionResult> {
  const formData = new FormData()
  formData.append('file', file)
  if (uploadCategory) formData.append('upload_category', uploadCategory)

  const res = await authFetch(`${API_BASE}/reconciliation/inspect-workbook`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errText = await res.text()
    try {
      const errJson = JSON.parse(errText)
      throw new Error(errJson.detail || 'Failed to inspect workbook')
    } catch {
      throw new Error(errText || 'Failed to inspect workbook')
    }
  }

  return await res.json()
}

export async function explainDiscrepancy(
  discrepancyData: any,
  comparisonRecords: any[] = [],
  documentMetadata: any = {}
): Promise<DiscrepancyExplanationResponse> {
  const res = await authFetch(`${API_BASE}/reconciliation/explain-discrepancy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      discrepancy_data: discrepancyData,
      comparison_records: comparisonRecords,
      document_metadata: documentMetadata,
    }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to generate discrepancy explanation')
  }

  return await res.json()
}

export async function listSessionCorrections(sessionId: number): Promise<CorrectionProposal[]> {
  try {
    const res = await authFetch(`${API_BASE}/reconciliation/sessions/${sessionId}/corrections`)
    if (!res.ok) return []
    return await res.json()
  } catch {
    return []
  }
}

export async function updateCorrectionDecision(
  correctionId: string,
  decision: 'CONFIRMED' | 'REJECTED' | 'MANUAL_REVIEW',
  notes?: string
): Promise<CorrectionProposal> {
  const res = await authFetch(`${API_BASE}/reconciliation/corrections/${correctionId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, notes }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to record correction decision')
  }

  return await res.json()
}

export async function generateCorrectedWorkbook(
  sessionId: number,
  accountantName: string = 'Partner Accountant'
): Promise<GenerateCorrectedWorkbookResponse> {
  const formData = new FormData()
  formData.append('accountant_name', accountantName)

  const res = await authFetch(`${API_BASE}/reconciliation/sessions/${sessionId}/generate-corrected-workbook`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errText = await res.text()
    try {
      const errJson = JSON.parse(errText)
      throw new Error(errJson.detail || 'Failed to generate corrected workbook')
    } catch {
      throw new Error(errText || 'Failed to generate corrected workbook')
    }
  }

  return await res.json()
}

// ---------------------------------------------------------------------------
// AI Assistant APIs
// ---------------------------------------------------------------------------

export async function assistantChat(
  message: string,
  conversationId?: string,
  fileIds: number[] = []
): Promise<AssistantChatResponse> {
  const res = await authFetch(`${API_BASE}/assistant/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      file_ids: fileIds,
    }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Assistant chat request failed')
  }

  return await res.json()
}

export async function assistantUpload(
  file: File,
  conversationId?: string,
  category: string = 'financial'
): Promise<AssistantFileContext> {
  const formData = new FormData()
  formData.append('file', file)
  if (conversationId) {
    formData.append('conversation_id', conversationId)
  }
  formData.append('category', category)

  const res = await authFetch(`${API_BASE}/assistant/upload`, {
    method: 'POST',
    body: formData,
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to upload file to assistant')
  }

  return await res.json()
}

export async function assistantGetConversation(conversationId: string): Promise<{
  conversation_id: string
  file_ids: number[]
  files: AssistantFileContext[]
  messages: Array<{
    id: string
    role: 'user' | 'assistant'
    text: string
    timestamp: string
    intent?: string
    findings?: any[]
    proposal?: any
    correction_available?: boolean
    correction_id?: string
  }>
  discrepancy_count: number
}> {
  const res = await authFetch(`${API_BASE}/assistant/conversation/${conversationId}`)
  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to retrieve assistant conversation')
  }
  return await res.json()
}

export async function assistantCompareFiles(
  fileAId: number,
  fileBId: number,
  conversationId?: string,
  prompt?: string
): Promise<AssistantChatResponse> {
  const res = await authFetch(`${API_BASE}/assistant/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_a_id: fileAId,
      file_b_id: fileBId,
      conversation_id: conversationId,
      prompt,
    }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to compare files')
  }

  return await res.json()
}

export async function assistantCorrectionDecision(
  correctionId: string,
  decision: 'CONFIRMED' | 'REJECTED' | 'MANUAL_REVIEW',
  notes?: string
): Promise<CorrectionProposalInfo> {
  const res = await authFetch(`${API_BASE}/assistant/corrections/${correctionId}/decision`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision, notes }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to record assistant correction decision')
  }

  return await res.json()
}

export async function assistantGenerateCorrectedCopy(
  correctionId: string,
  accountantName: string = 'Partner Accountant'
): Promise<{
  success: boolean
  original_filename: string
  generated_filename: string
  download_url: string
  document_id: number
  corrections_sheet_name: string
  message: string
}> {
  const res = await authFetch(`${API_BASE}/assistant/generate-corrected-file`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      correction_id: correctionId,
      accountant_name: accountantName,
    }),
  })

  if (!res.ok) {
    const errText = await res.text()
    throw new Error(errText || 'Failed to generate corrected workbook copy')
  }

  return await res.json()
}

export async function getAssistantConversation(conversationId: string): Promise<any> {
  const res = await authFetch(`${API_BASE}/assistant/conversation/${conversationId}`)
  if (!res.ok) return null
  return await res.json()
}
