import { getAuthToken, clearAuthToken, API_HOST } from './api'
import type {
  FSProfile,
  FSProfileCreatePayload,
  FSOverview,
  TrialBalanceEntryItem,
  BalanceSheetLineItem,
  ProfitLossLineItem,
  CashFlowLineItem,
  FSSnapshot,
  FSFinding,
  FSStatus,
} from '../types/financialStatements'

const FS_BASE = `${API_HOST}/api/financial-statements`

async function fsFetch(url: string, init?: RequestInit): Promise<Response> {
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

export async function fetchFSProfiles(): Promise<FSProfile[]> {
  const res = await fsFetch(`${FS_BASE}/profiles`)
  if (!res.ok) {
    throw new Error('Failed to fetch financial statement profiles')
  }
  return res.json()
}

export async function createFSProfile(data: FSProfileCreatePayload): Promise<FSProfile> {
  const res = await fsFetch(`${FS_BASE}/profiles`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create financial statement profile')
  }
  return res.json()
}

export async function fetchFSProfile(profileId: number | string): Promise<FSProfile> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}`)
  if (!res.ok) {
    throw new Error(`Failed to fetch profile #${profileId}`)
  }
  return res.json()
}

export async function fetchFSOverview(profileId: number | string): Promise<FSOverview> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/overview`)
  if (!res.ok) {
    throw new Error(`Failed to fetch overview for profile #${profileId}`)
  }
  return res.json()
}

export async function uploadFSDocument(
  profileId: number | string,
  file: File,
  sheetType: string = 'TRIAL_BALANCE'
): Promise<{ filename: string; imported_entries: number; status: string }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/upload?sheet_type=${sheetType}`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to parse and upload financial document')
  }
  return res.json()
}

export async function fetchTrialBalance(profileId: number | string): Promise<TrialBalanceEntryItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/trial-balance`)
  if (!res.ok) {
    throw new Error('Failed to fetch Trial Balance')
  }
  return res.json()
}

export async function addTrialBalanceEntries(
  profileId: number | string,
  entries: Partial<TrialBalanceEntryItem>[]
): Promise<TrialBalanceEntryItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/trial-balance`, {
    method: 'POST',
    body: JSON.stringify(entries),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add trial balance entries')
  }
  return res.json()
}

export async function fetchBalanceSheet(profileId: number | string): Promise<BalanceSheetLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/balance-sheet`)
  if (!res.ok) {
    throw new Error('Failed to fetch Balance Sheet')
  }
  return res.json()
}

export async function addBalanceSheetLines(
  profileId: number | string,
  lines: Partial<BalanceSheetLineItem>[]
): Promise<BalanceSheetLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/balance-sheet`, {
    method: 'POST',
    body: JSON.stringify(lines),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add balance sheet lines')
  }
  return res.json()
}

export async function fetchProfitLoss(profileId: number | string): Promise<ProfitLossLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/profit-loss`)
  if (!res.ok) {
    throw new Error('Failed to fetch Profit & Loss')
  }
  return res.json()
}

export async function addProfitLossLines(
  profileId: number | string,
  lines: Partial<ProfitLossLineItem>[]
): Promise<ProfitLossLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/profit-loss`, {
    method: 'POST',
    body: JSON.stringify(lines),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add profit & loss lines')
  }
  return res.json()
}

export async function fetchCashFlow(profileId: number | string): Promise<CashFlowLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/cash-flow`)
  if (!res.ok) {
    throw new Error('Failed to fetch Cash Flow')
  }
  return res.json()
}

export async function addCashFlowLines(
  profileId: number | string,
  lines: Partial<CashFlowLineItem>[]
): Promise<CashFlowLineItem[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/cash-flow`, {
    method: 'POST',
    body: JSON.stringify(lines),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add cash flow lines')
  }
  return res.json()
}

export async function autoClassifyStatements(
  profileId: number | string,
  overwrite: boolean = true
): Promise<{ balance_sheet_lines: number; profit_loss_lines: number }> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/auto-classify?overwrite=${overwrite}`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to auto-classify trial balance')
  }
  return res.json()
}

export async function calculateAndSnapshot(profileId: number | string): Promise<any> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/calculate`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to calculate financial statements and generate snapshot')
  }
  return res.json()
}

export async function fetchFSSnapshots(profileId: number | string): Promise<FSSnapshot[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/snapshots`)
  if (!res.ok) {
    throw new Error('Failed to fetch statement snapshots')
  }
  return res.json()
}

export async function fetchFSFindings(profileId: number | string): Promise<FSFinding[]> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/findings`)
  if (!res.ok) {
    throw new Error('Failed to fetch financial statement review findings')
  }
  return res.json()
}

export async function recordFSFindingDecision(
  findingId: number | string,
  decision: string,
  notes?: string
): Promise<FSFinding> {
  const res = await fsFetch(`${FS_BASE}/findings/${findingId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to record finding decision')
  }
  return res.json()
}

export async function updateFSStatus(
  profileId: number | string,
  targetStatus: FSStatus,
  notes?: string
): Promise<FSProfile> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/status`, {
    method: 'POST',
    body: JSON.stringify({ target_status: targetStatus, notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Status transition blocked by approval safety checks')
  }
  return res.json()
}

export async function exportFSReport(profileId: number | string): Promise<void> {
  const res = await fsFetch(`${FS_BASE}/profiles/${profileId}/export`)
  if (!res.ok) {
    throw new Error('Failed to download accountant preparation report')
  }
  const blob = await res.blob()
  const contentDisp = res.headers.get('Content-Disposition')
  let filename = `Financial_Statements_${profileId}.csv`
  if (contentDisp && contentDisp.includes('filename=')) {
    filename = contentDisp.split('filename=')[1].replace(/["']/g, '').trim()
  }

  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
