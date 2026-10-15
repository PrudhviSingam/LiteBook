import { getAuthToken, clearAuthToken, API_HOST } from './api'
import type {
  ITRProfile,
  ITRIncomeEntry,
  ITRDeductionEntry,
  ITRTaxCreditEntry,
  ITRRegimeComparison,
  ITRFinding,
  ITRStatus,
  ITRRegime,
} from '../types/itr'

const ITR_BASE = `${API_HOST}/api/itr`

async function itrFetch(url: string, init?: RequestInit): Promise<Response> {
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

export async function fetchITRProfiles(): Promise<ITRProfile[]> {
  const res = await itrFetch(`${ITR_BASE}/profiles`)
  if (!res.ok) {
    throw new Error('Failed to fetch ITR profiles')
  }
  return res.json()
}

export async function createITRProfile(data: {
  pan: string
  taxpayer_name: string
  taxpayer_category?: string
  assessment_year: string
  financial_year: string
  selected_regime?: ITRRegime
}): Promise<ITRProfile> {
  const res = await itrFetch(`${ITR_BASE}/profiles`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to create ITR profile')
  }
  return res.json()
}

export async function fetchITRProfile(profileId: number | string): Promise<ITRProfile> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}`)
  if (!res.ok) {
    throw new Error('Failed to fetch ITR profile')
  }
  return res.json()
}

export async function updateITRProfile(
  profileId: number | string,
  data: { taxpayer_name?: string; selected_regime?: ITRRegime; taxpayer_category?: string }
): Promise<ITRProfile> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update ITR profile')
  }
  return res.json()
}

export async function fetchITRIncomes(profileId: number | string): Promise<ITRIncomeEntry[]> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/incomes`)
  if (!res.ok) {
    throw new Error('Failed to fetch income entries')
  }
  return res.json()
}

export async function addITRIncome(
  profileId: number | string,
  data: Partial<ITRIncomeEntry>
): Promise<ITRIncomeEntry> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/incomes`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add income entry')
  }
  return res.json()
}

export async function fetchITRDeductions(profileId: number | string): Promise<ITRDeductionEntry[]> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/deductions`)
  if (!res.ok) {
    throw new Error('Failed to fetch deduction entries')
  }
  return res.json()
}

export async function addITRDeduction(
  profileId: number | string,
  data: Partial<ITRDeductionEntry>
): Promise<ITRDeductionEntry> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/deductions`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add deduction entry')
  }
  return res.json()
}

export async function updateITRDeduction(
  profileId: number | string,
  deductionId: number | string,
  data: { eligible_amount?: number | string; status?: string; provenance_notes?: string }
): Promise<ITRDeductionEntry> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/deductions/${deductionId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update deduction entry')
  }
  return res.json()
}

export async function fetchITRTaxCredits(profileId: number | string): Promise<ITRTaxCreditEntry[]> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/tax-credits`)
  if (!res.ok) {
    throw new Error('Failed to fetch tax credit entries')
  }
  return res.json()
}

export async function addITRTaxCredit(
  profileId: number | string,
  data: Partial<ITRTaxCreditEntry>
): Promise<ITRTaxCreditEntry> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/tax-credits`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to add tax credit entry')
  }
  return res.json()
}

export async function uploadITRFile(
  profileId: number | string,
  file: File
): Promise<{ status: string; message: string; imported_incomes: number; imported_deductions: number; imported_credits: number }> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/upload`, {
    method: 'POST',
    body: formData,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to upload tax document')
  }
  return res.json()
}

export async function calculateITR(profileId: number | string): Promise<ITRRegimeComparison> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/calculate`, {
    method: 'POST',
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to calculate ITR')
  }
  return res.json()
}

export async function fetchITRRegimeComparison(profileId: number | string): Promise<ITRRegimeComparison> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/regime-comparison`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to fetch regime comparison')
  }
  return res.json()
}

export async function transitionITRStatus(
  profileId: number | string,
  targetStatus: ITRStatus,
  notes?: string
): Promise<ITRProfile> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/status`, {
    method: 'POST',
    body: JSON.stringify({ target_status: targetStatus, notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to update ITR status')
  }
  return res.json()
}

export async function fetchITRFindings(profileId: number | string): Promise<ITRFinding[]> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/findings`)
  if (!res.ok) {
    throw new Error('Failed to fetch review findings')
  }
  return res.json()
}

export async function decideITRFinding(
  profileId: number | string,
  findingId: number | string,
  decision: 'ACCEPTED' | 'REJECTED' | 'OVERRIDDEN',
  notes?: string
): Promise<ITRFinding> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/findings/${findingId}/decision`, {
    method: 'POST',
    body: JSON.stringify({ decision, notes }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Failed to record decision')
  }
  return res.json()
}

export async function downloadITRReport(profileId: number | string): Promise<void> {
  const res = await itrFetch(`${ITR_BASE}/profiles/${profileId}/export`)
  if (!res.ok) {
    throw new Error('Failed to download ITR report')
  }
  const blob = await res.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `itr_preparation_report_profile_${profileId}.csv`
  document.body.appendChild(a)
  a.click()
  window.URL.revokeObjectURL(url)
  document.body.removeChild(a)
}
