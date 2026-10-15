import React, { useState, useEffect, useMemo } from 'react'
import {
  FileSpreadsheet,
  PieChart,
  TrendingUp,
  Scale,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Info,
  RefreshCw,
  Upload,
  Download,
  Plus,
  ArrowRight,
  ExternalLink,
  Lock,
  Layers,
  FileText,
  Clock,
  Sparkles,
  HelpCircle,
  Hash,
  ChevronRight,
  Check,
  X,
  FileCheck,
  Search,
} from 'lucide-react'
import { Badge } from '../components/ui/Badge'
import { formatINR } from '../utils/formatters'
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
import {
  fetchFSProfiles,
  createFSProfile,
  fetchFSOverview,
  uploadFSDocument,
  fetchTrialBalance,
  fetchBalanceSheet,
  fetchProfitLoss,
  fetchCashFlow,
  autoClassifyStatements,
  calculateAndSnapshot,
  fetchFSSnapshots,
  fetchFSFindings,
  recordFSFindingDecision,
  updateFSStatus,
  exportFSReport,
} from '../services/financialStatementsApi'

export const FinancialStatementsPage: React.FC = () => {
  // Profiles state
  const [profiles, setProfiles] = useState<FSProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [actionLoading, setActionLoading] = useState<boolean>(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Current profile detailed data
  const [overview, setOverview] = useState<FSOverview | null>(null)
  const [trialBalance, setTrialBalance] = useState<TrialBalanceEntryItem[]>([])
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetLineItem[]>([])
  const [profitLoss, setProfitLoss] = useState<ProfitLossLineItem[]>([])
  const [cashFlow, setCashFlow] = useState<CashFlowLineItem[]>([])
  const [snapshots, setSnapshots] = useState<FSSnapshot[]>([])
  const [findings, setFindings] = useState<FSFinding[]>([])

  // UI Tabs
  type TabType =
    | 'overview'
    | 'trial-balance'
    | 'balance-sheet'
    | 'profit-loss'
    | 'cash-flow'
    | 'notes'
    | 'findings'
    | 'snapshots'

  const [activeTab, setActiveTab] = useState<TabType>('overview')

  // Modals
  const [showCreateProfileModal, setShowCreateProfileModal] = useState(false)
  const [showUploadModal, setShowUploadModal] = useState(false)
  const [showApprovalModal, setShowApprovalModal] = useState(false)
  const [provenanceTarget, setProvenanceTarget] = useState<any | null>(null)

  // Create Profile Form
  const [newProfileForm, setNewProfileForm] = useState<FSProfileCreatePayload>({
    entity_name: '',
    cin_or_pan: '',
    financial_year: '2023-24',
    reporting_period: 'ANNUAL',
    framework: 'SCHEDULE_III',
  })

  // Upload Form
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [uploadSheetType, setUploadSheetType] = useState('TRIAL_BALANCE')

  // Findings filter
  const [findingSeverityFilter, setFindingSeverityFilter] = useState<string>('ALL')

  // -------------------------------------------------------------
  // Initial Data Loading
  // -------------------------------------------------------------

  const loadProfiles = async () => {
    try {
      setLoading(true)
      setErrorMsg(null)
      const list = await fetchFSProfiles()
      setProfiles(list)
      if (list.length > 0) {
        if (!selectedProfileId || !list.some((p) => p.id === selectedProfileId)) {
          setSelectedProfileId(list[0].id)
        }
      } else {
        setSelectedProfileId(null)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load financial statement profiles')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProfiles()
  }, [])

  // Load active profile data
  const loadProfileDetails = async (id: number) => {
    try {
      setErrorMsg(null)
      const [ov, tb, bs, pl, cf, sn, fd] = await Promise.all([
        fetchFSOverview(id),
        fetchTrialBalance(id),
        fetchBalanceSheet(id),
        fetchProfitLoss(id),
        fetchCashFlow(id),
        fetchFSSnapshots(id),
        fetchFSFindings(id),
      ])
      setOverview(ov)
      setTrialBalance(tb)
      setBalanceSheet(bs)
      setProfitLoss(pl)
      setCashFlow(cf)
      setSnapshots(sn)
      setFindings(fd)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to fetch financial details for profile')
    }
  }

  useEffect(() => {
    if (selectedProfileId) {
      loadProfileDetails(selectedProfileId)
    }
  }, [selectedProfileId])

  const selectedProfile = useMemo(() => {
    return profiles.find((p) => p.id === selectedProfileId) || null
  }, [profiles, selectedProfileId])

  // Helper to format currency safely, returning "—" if null or unavailable
  const renderAmount = (val: number | string | null | undefined): string => {
    if (val === null || val === undefined || val === '') return '—'
    const num = Number(val)
    if (isNaN(num)) return '—'
    return formatINR(num)
  }

  // -------------------------------------------------------------
  // Action Handlers
  // -------------------------------------------------------------

  const handleCreateProfile = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newProfileForm.entity_name.trim() || !newProfileForm.financial_year.trim()) return
    try {
      setActionLoading(true)
      const created = await createFSProfile(newProfileForm)
      setShowCreateProfileModal(false)
      setSuccessMsg(`Created profile for ${created.entity_name} (${created.financial_year})`)
      await loadProfiles()
      setSelectedProfileId(created.id)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create profile')
    } finally {
      setActionLoading(false)
    }
  }

  const handleUploadDocument = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProfileId || !uploadFile) return
    try {
      setActionLoading(true)
      const res = await uploadFSDocument(selectedProfileId, uploadFile, uploadSheetType)
      setShowUploadModal(false)
      setUploadFile(null)
      setSuccessMsg(`Ingested ${res.imported_entries} accounts from ${res.filename} with strict audit provenance`)
      await loadProfileDetails(selectedProfileId)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to upload document')
    } finally {
      setActionLoading(false)
    }
  }

  const handleAutoClassify = async () => {
    if (!selectedProfileId) return
    try {
      setActionLoading(true)
      const res = await autoClassifyStatements(selectedProfileId, true)
      setSuccessMsg(`Classified Trial Balance into ${res.balance_sheet_lines} Balance Sheet and ${res.profit_loss_lines} P&L lines`)
      await loadProfileDetails(selectedProfileId)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to auto-classify trial balance')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCalculateAndSnapshot = async () => {
    if (!selectedProfileId) return
    try {
      setActionLoading(true)
      const res = await calculateAndSnapshot(selectedProfileId)
      setSuccessMsg(
        `Generated immutable Snapshot v${res.snapshot_version} [SHA-256: ${res.snapshot_hash.slice(0, 12)}...]. Statement checks completed.`
      )
      await loadProfileDetails(selectedProfileId)
      await loadProfiles()
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to calculate statements')
    } finally {
      setActionLoading(false)
    }
  }

  const handleApplyFindingDecision = async (findingId: number, decision: string) => {
    try {
      await recordFSFindingDecision(findingId, decision, 'Accountant confirmed verification decision')
      setSuccessMsg(`Recorded decision '${decision}' on finding #${findingId}`)
      if (selectedProfileId) {
        await loadProfileDetails(selectedProfileId)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to save review decision')
    }
  }

  const handleApproveStatements = async () => {
    if (!selectedProfileId) return
    try {
      setActionLoading(true)
      await updateFSStatus(selectedProfileId, 'APPROVED', 'Formally verified and approved by accountant')
      setShowApprovalModal(false)
      setSuccessMsg('Financial statements approved. Audit sign-off timestamp and user ID permanently recorded.')
      await loadProfiles()
      await loadProfileDetails(selectedProfileId)
    } catch (err: any) {
      setErrorMsg(err.message || 'Approval blocked by safety validation checks')
    } finally {
      setActionLoading(false)
    }
  }

  const handleExportCSV = async () => {
    if (!selectedProfileId) return
    try {
      await exportFSReport(selectedProfileId)
      setSuccessMsg('Accountant preparation report exported successfully.')
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to export report')
    }
  }

  // -------------------------------------------------------------
  // Filtered Findings
  // -------------------------------------------------------------

  const filteredFindings = useMemo(() => {
    if (findingSeverityFilter === 'ALL') return findings
    return findings.filter((f) => f.severity === findingSeverityFilter)
  }, [findings, findingSeverityFilter])

  return (
    <div className="space-y-6 pb-16">
      {/* 1. Header Banner */}
      <div className="glass-panel p-6 border border-pink-100 shadow-sm rounded-2xl flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-bold bg-pink-50 text-pink-700 border border-pink-200 mb-2">
            <ShieldCheck className="w-4 h-4 text-pink-500" />
            <span>Schedule III & Ind AS Financial Engine</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Financial Statements
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1 max-w-2xl">
            Deterministic preparation, validation, and snapshotting of Balance Sheet, Profit & Loss, Trial Balance, and Cash Flow.
          </p>
        </div>

        {/* Profile Selector & New Profile Button */}
        <div className="flex flex-wrap items-center gap-2.5">
          {profiles.length > 0 && (
            <select
              value={selectedProfileId || ''}
              onChange={(e) => setSelectedProfileId(Number(e.target.value))}
              className="px-3.5 py-2 text-xs font-semibold bg-white border border-pink-200 rounded-xl shadow-xs text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
            >
              {profiles.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.entity_name} ({p.financial_year} — {p.status})
                </option>
              ))}
            </select>
          )}

          <button
            onClick={() => setShowCreateProfileModal(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-pink-700 bg-pink-50 hover:bg-pink-100 border border-pink-200 rounded-xl transition-all shadow-xs cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Profile</span>
          </button>

          {selectedProfile && (
            <>
              <button
                onClick={() => setShowUploadModal(true)}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-xs cursor-pointer"
              >
                <Upload className="w-3.5 h-3.5 text-pink-500" />
                <span>Upload</span>
              </button>

              <button
                onClick={handleCalculateAndSnapshot}
                disabled={actionLoading}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold text-white bg-pink-500 hover:bg-pink-600 rounded-xl transition-all shadow-xs cursor-pointer disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${actionLoading ? 'animate-spin' : ''}`} />
                <span>Recalculate</span>
              </button>

              <button
                onClick={handleExportCSV}
                className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-bold text-slate-700 bg-white hover:bg-slate-50 border border-slate-200 rounded-xl transition-all shadow-xs cursor-pointer"
              >
                <Download className="w-3.5 h-3.5 text-slate-600" />
                <span>Export Report</span>
              </button>

              <button
                onClick={() => setShowApprovalModal(true)}
                disabled={selectedProfile.status === 'APPROVED'}
                className={`inline-flex items-center gap-1.5 px-3.5 py-2 text-xs font-bold rounded-xl transition-all shadow-xs cursor-pointer ${
                  selectedProfile.status === 'APPROVED'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200 cursor-default'
                    : 'bg-slate-900 text-white hover:bg-slate-800'
                }`}
              >
                {selectedProfile.status === 'APPROVED' ? (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    <span>Approved</span>
                  </>
                ) : (
                  <>
                    <Lock className="w-3.5 h-3.5 text-pink-300" />
                    <span>Approve</span>
                  </>
                )}
              </button>
            </>
          )}
        </div>
      </div>

      {/* Alerts */}
      {errorMsg && (
        <div className="p-4 rounded-xl bg-red-50 border border-red-200 flex items-start gap-3">
          <AlertTriangle className="w-4 h-4 text-red-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold text-red-800">Validation Notice</h4>
            <p className="text-xs text-red-700 mt-0.5">{errorMsg}</p>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-red-400 hover:text-red-700 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 flex items-start gap-3">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <h4 className="text-xs font-bold text-emerald-800">Action Confirmed</h4>
            <p className="text-xs text-emerald-700 mt-0.5">{successMsg}</p>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-700 text-xs">
            Dismiss
          </button>
        </div>
      )}

      {/* 2. Top Metric Cards (8 Core Metrics) */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Total Assets</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate">
            {renderAmount(overview?.total_assets)}
          </span>
          <span className="text-[10px] text-pink-600 font-medium">Schedule III</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Total Liabilities</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate">
            {renderAmount(overview?.total_liabilities)}
          </span>
          <span className="text-[10px] text-slate-400 font-medium">Non-Current + Current</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Total Equity</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate">
            {renderAmount(overview?.total_equity)}
          </span>
          <span className="text-[10px] text-slate-400 font-medium">Capital + Reserves</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Revenue</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate text-emerald-700">
            {renderAmount(overview?.total_revenue)}
          </span>
          <span className="text-[10px] text-emerald-600 font-medium">Ops + Other Income</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Expenses</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate text-slate-800">
            {renderAmount(overview?.total_expenses)}
          </span>
          <span className="text-[10px] text-slate-400 font-medium">Direct + Indirect</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Net Profit</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate text-pink-700">
            {renderAmount(overview?.net_profit)}
          </span>
          <span className="text-[10px] text-pink-600 font-medium">Profit After Tax</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">Cash Balance</span>
          <span className="text-base font-extrabold text-slate-900 mt-1 block truncate">
            {renderAmount(overview?.closing_cash)}
          </span>
          <span className="text-[10px] text-sky-600 font-medium">Closing Position</span>
        </div>

        <div className="glass-card p-3.5 bg-white/80 border border-pink-100/80 rounded-2xl shadow-2xs">
          <span className="text-[11px] font-semibold text-slate-500 block truncate">TB Difference</span>
          <span
            className={`text-base font-extrabold mt-1 block truncate ${
              overview?.trial_balance_difference && Number(overview.trial_balance_difference) !== 0
                ? 'text-red-600'
                : 'text-emerald-700'
            }`}
          >
            {renderAmount(overview?.trial_balance_difference)}
          </span>
          <span
            className={`text-[10px] font-bold ${
              overview?.is_tb_balanced ? 'text-emerald-600' : 'text-red-500'
            }`}
          >
            {overview?.is_tb_balanced ? 'Balanced' : 'Review Required'}
          </span>
        </div>
      </div>

      {/* 3. Navigation Tabs */}
      <div className="border-b border-pink-100">
        <div className="flex flex-wrap gap-2 text-xs font-bold text-slate-600">
          {(
            [
              { key: 'overview', label: 'Overview', icon: PieChart },
              { key: 'trial-balance', label: 'Trial Balance', icon: FileSpreadsheet },
              { key: 'balance-sheet', label: 'Balance Sheet', icon: Scale },
              { key: 'profit-loss', label: 'Profit & Loss', icon: TrendingUp },
              { key: 'cash-flow', label: 'Cash Flow', icon: ArrowRight },
              { key: 'notes', label: 'Notes & Schedules', icon: FileText },
              { key: 'findings', label: `Review Findings (${findings.length})`, icon: AlertTriangle },
              { key: 'snapshots', label: `Snapshots (${snapshots.length})`, icon: Clock },
            ] as const
          ).map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`inline-flex items-center gap-1.5 px-4 py-2.5 rounded-t-xl transition-all cursor-pointer ${
                  isActive
                    ? 'text-pink-700 bg-pink-50/80 border-t-2 border-pink-500 font-extrabold'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-pink-500' : 'text-slate-400'}`} />
                <span>{tab.label}</span>
              </button>
            )
          })}
        </div>
      </div>

      {/* 4. Tab Content */}

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Entity Summary Card */}
            <div className="glass-card p-5 bg-white/90 border border-pink-100 rounded-2xl shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <FileCheck className="w-4 h-4 text-pink-500" />
                <span>Entity & Compliance Profile</span>
              </h3>
              <div className="mt-4 space-y-2.5 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Entity Name</span>
                  <span className="font-bold text-slate-800">{selectedProfile?.entity_name || '—'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">CIN / PAN</span>
                  <span className="font-semibold text-slate-700">{selectedProfile?.cin_or_pan || '—'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Financial Year</span>
                  <span className="font-bold text-pink-700">{selectedProfile?.financial_year || '—'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Reporting Period</span>
                  <span className="font-semibold text-slate-700">{selectedProfile?.reporting_period || 'ANNUAL'}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-500">Accounting Standard</span>
                  <span className="font-semibold text-slate-700">{selectedProfile?.framework || 'Schedule III'}</span>
                </div>
                <div className="flex justify-between py-1">
                  <span className="text-slate-500">Workflow Status</span>
                  <span className="font-bold text-pink-600 bg-pink-50 px-2 py-0.5 rounded-full border border-pink-200">
                    {selectedProfile?.status || 'DRAFT'}
                  </span>
                </div>
              </div>
            </div>

            {/* Validation Equality Status Card */}
            <div className="glass-card p-5 bg-white/90 border border-pink-100 rounded-2xl shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Scale className="w-4 h-4 text-pink-500" />
                <span>Mathematical Tally Verification</span>
              </h3>
              <div className="mt-4 space-y-3">
                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700">Trial Balance Equality</span>
                    {overview?.is_tb_balanced ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                        <Check className="w-3 h-3 text-emerald-600" /> Balanced
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-md border border-red-200">
                        <X className="w-3 h-3 text-red-600" /> Out of Balance
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Debit sum equals credit sum. Variance: ₹{overview?.trial_balance_difference ?? '0.00'}
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700">Balance Sheet Equation</span>
                    {overview?.is_bs_balanced ? (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-md border border-emerald-200">
                        <Check className="w-3 h-3 text-emerald-600" /> Balanced
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded-md border border-red-200">
                        <X className="w-3 h-3 text-red-600" /> Mismatch
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Total Assets == Total Equity + Total Liabilities
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-slate-50 border border-slate-200/80">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-slate-700">Approval Eligibility</span>
                    <span
                      className={`text-[11px] font-bold px-2 py-0.5 rounded-md border ${
                        overview?.eligible_for_approval
                          ? 'text-emerald-700 bg-emerald-50 border-emerald-200'
                          : 'text-amber-700 bg-amber-50 border-amber-200'
                      }`}
                    >
                      {overview?.eligible_for_approval ? 'Ready for Sign-Off' : 'Safety Block Active'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    {overview?.eligible_for_approval
                      ? 'No unresolved critical findings. Books balance.'
                      : `${overview?.unresolved_findings_count || 0} unresolved finding(s) or imbalances require review.`}
                  </p>
                </div>
              </div>
            </div>

            {/* Cryptographic Snapshot Status */}
            <div className="glass-card p-5 bg-white/90 border border-pink-100 rounded-2xl shadow-xs">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Hash className="w-4 h-4 text-pink-500" />
                <span>Cryptographic Snapshot</span>
              </h3>
              <p className="text-xs text-slate-500 mt-1 leading-relaxed">
                Deterministic calculation runs generate immutable snapshots stamped with a SHA-256 hash.
              </p>
              <div className="mt-4 p-3 bg-pink-50/50 border border-pink-100 rounded-xl space-y-2">
                <span className="text-[11px] font-semibold text-pink-700 block">Latest SHA-256 Hash</span>
                <code className="text-[11px] font-mono text-slate-800 block break-all bg-white p-2 rounded-lg border border-pink-200">
                  {overview?.latest_snapshot_hash || 'No calculation snapshot generated yet'}
                </code>
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={handleAutoClassify}
                  className="flex-1 py-2 text-xs font-bold text-pink-700 bg-pink-50 hover:bg-pink-100 border border-pink-200 rounded-xl transition-all cursor-pointer text-center"
                >
                  Auto-Classify
                </button>
                <button
                  onClick={handleCalculateAndSnapshot}
                  className="flex-1 py-2 text-xs font-bold text-white bg-pink-500 hover:bg-pink-600 rounded-xl transition-all cursor-pointer text-center"
                >
                  New Snapshot
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: TRIAL BALANCE */}
      {activeTab === 'trial-balance' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Trial Balance Ledger Accounts</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                {trialBalance.length} ledger accounts ingested with strict cell-level audit provenance.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleAutoClassify}
                className="px-3 py-1.5 text-xs font-bold text-pink-700 bg-pink-50 hover:bg-pink-100 border border-pink-200 rounded-xl transition-all cursor-pointer"
              >
                Auto-Classify into Statements
              </button>
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-pink-100 bg-white/90 shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-pink-50/60 text-slate-700 font-bold border-b border-pink-100">
                <tr>
                  <th className="py-3 px-4">Code</th>
                  <th className="py-3 px-4">Account Name</th>
                  <th className="py-3 px-4">Category</th>
                  <th className="py-3 px-4 text-right">Debit (INR)</th>
                  <th className="py-3 px-4 text-right">Credit (INR)</th>
                  <th className="py-3 px-4 text-right">Net Balance</th>
                  <th className="py-3 px-4 text-center">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {trialBalance.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-slate-400">
                      No Trial Balance entries loaded. Click "Upload" to ingest a trial balance workbook or CSV.
                    </td>
                  </tr>
                ) : (
                  trialBalance.map((item) => (
                    <tr key={item.id} className="hover:bg-pink-50/30 transition-all">
                      <td className="py-3 px-4 font-mono text-slate-600">{item.account_code || '—'}</td>
                      <td className="py-3 px-4 font-bold text-slate-900">{item.account_name}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-700">
                          {item.account_category}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-slate-800">
                        {renderAmount(item.debit_amount)}
                      </td>
                      <td className="py-3 px-4 text-right font-semibold text-slate-800">
                        {renderAmount(item.credit_amount)}
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900">
                        {renderAmount(item.net_balance)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setProvenanceTarget(item)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-pink-600 hover:text-pink-800 bg-pink-50 px-2 py-0.5 rounded border border-pink-200 cursor-pointer"
                        >
                          <Info className="w-3 h-3" />
                          <span>{item.source_cell || item.source_sheet || 'Audit Link'}</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: BALANCE SHEET (SCHEDULE III) */}
      {activeTab === 'balance-sheet' && (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Balance Sheet (Companies Act Schedule III)</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Classified line items mapped to Non-Current Assets, Current Assets, Equity, and Liabilities.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`px-3 py-1 text-xs font-bold rounded-lg border ${
                  overview?.is_bs_balanced
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : 'bg-red-50 text-red-700 border-red-200'
                }`}
              >
                {overview?.is_bs_balanced ? 'Balance Sheet Tallies Exactly' : 'Tally Mismatch Detected'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* ASSETS COLUMN */}
            <div className="glass-card p-5 bg-white/90 border border-pink-100 rounded-2xl shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-pink-100">
                <h4 className="text-sm font-extrabold text-slate-900 tracking-wide uppercase">I. ASSETS</h4>
                <span className="text-xs font-bold text-pink-700">Total: {renderAmount(overview?.total_assets)}</span>
              </div>

              {/* Non-Current Assets */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  (1) Non-Current Assets
                </span>
                <div className="divide-y divide-slate-100 text-xs">
                  {balanceSheet
                    .filter((l) => l.classification === 'NON_CURRENT_ASSETS')
                    .map((line) => (
                      <div key={line.id} className="py-2 flex items-center justify-between hover:bg-pink-50/20 px-2 rounded">
                        <div>
                          <span className="font-semibold text-slate-800">{line.line_item_name}</span>
                          <span className="text-[10px] text-slate-400 block">{line.sub_category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-slate-900">{renderAmount(line.amount)}</span>
                          <button
                            onClick={() => setProvenanceTarget(line)}
                            className="text-pink-500 hover:text-pink-700"
                            title="View Provenance"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Current Assets */}
              <div className="space-y-2 pt-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  (2) Current Assets
                </span>
                <div className="divide-y divide-slate-100 text-xs">
                  {balanceSheet
                    .filter((l) => l.classification === 'CURRENT_ASSETS')
                    .map((line) => (
                      <div key={line.id} className="py-2 flex items-center justify-between hover:bg-pink-50/20 px-2 rounded">
                        <div>
                          <span className="font-semibold text-slate-800">{line.line_item_name}</span>
                          <span className="text-[10px] text-slate-400 block">{line.sub_category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-slate-900">{renderAmount(line.amount)}</span>
                          <button
                            onClick={() => setProvenanceTarget(line)}
                            className="text-pink-500 hover:text-pink-700"
                            title="View Provenance"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>

            {/* EQUITY & LIABILITIES COLUMN */}
            <div className="glass-card p-5 bg-white/90 border border-pink-100 rounded-2xl shadow-2xs space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-pink-100">
                <h4 className="text-sm font-extrabold text-slate-900 tracking-wide uppercase">
                  II. EQUITY & LIABILITIES
                </h4>
                <span className="text-xs font-bold text-pink-700">
                  Total: {renderAmount(Number(overview?.total_equity || 0) + Number(overview?.total_liabilities || 0))}
                </span>
              </div>

              {/* Equity */}
              <div className="space-y-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  (1) Shareholders' Funds / Equity
                </span>
                <div className="divide-y divide-slate-100 text-xs">
                  {balanceSheet
                    .filter((l) => l.classification === 'EQUITY')
                    .map((line) => (
                      <div key={line.id} className="py-2 flex items-center justify-between hover:bg-pink-50/20 px-2 rounded">
                        <div>
                          <span className="font-semibold text-slate-800">{line.line_item_name}</span>
                          <span className="text-[10px] text-slate-400 block">{line.sub_category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-slate-900">{renderAmount(line.amount)}</span>
                          <button
                            onClick={() => setProvenanceTarget(line)}
                            className="text-pink-500 hover:text-pink-700"
                            title="View Provenance"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Non-Current Liabilities */}
              <div className="space-y-2 pt-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  (2) Non-Current Liabilities
                </span>
                <div className="divide-y divide-slate-100 text-xs">
                  {balanceSheet
                    .filter((l) => l.classification === 'NON_CURRENT_LIABILITIES')
                    .map((line) => (
                      <div key={line.id} className="py-2 flex items-center justify-between hover:bg-pink-50/20 px-2 rounded">
                        <div>
                          <span className="font-semibold text-slate-800">{line.line_item_name}</span>
                          <span className="text-[10px] text-slate-400 block">{line.sub_category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-slate-900">{renderAmount(line.amount)}</span>
                          <button
                            onClick={() => setProvenanceTarget(line)}
                            className="text-pink-500 hover:text-pink-700"
                            title="View Provenance"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>

              {/* Current Liabilities */}
              <div className="space-y-2 pt-2">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wider block">
                  (3) Current Liabilities
                </span>
                <div className="divide-y divide-slate-100 text-xs">
                  {balanceSheet
                    .filter((l) => l.classification === 'CURRENT_LIABILITIES')
                    .map((line) => (
                      <div key={line.id} className="py-2 flex items-center justify-between hover:bg-pink-50/20 px-2 rounded">
                        <div>
                          <span className="font-semibold text-slate-800">{line.line_item_name}</span>
                          <span className="text-[10px] text-slate-400 block">{line.sub_category}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <span className="font-bold text-slate-900">{renderAmount(line.amount)}</span>
                          <button
                            onClick={() => setProvenanceTarget(line)}
                            className="text-pink-500 hover:text-pink-700"
                            title="View Provenance"
                          >
                            <Info className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: PROFIT & LOSS */}
      {activeTab === 'profit-loss' && (
        <div className="space-y-4">
          <div className="p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Profit & Loss Statement</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic calculation of Revenue, Direct/Indirect Expenses, EBITDA, PBT, and PAT.
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">Profit After Tax (PAT)</span>
              <span className="text-base font-extrabold text-pink-700">
                {renderAmount(overview?.net_profit)}
              </span>
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-pink-100 bg-white/90 shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-pink-50/60 text-slate-700 font-bold border-b border-pink-100">
                <tr>
                  <th className="py-3 px-4">Classification / Category</th>
                  <th className="py-3 px-4">Line Item Description</th>
                  <th className="py-3 px-4 text-center">Schedule Note</th>
                  <th className="py-3 px-4 text-right">Amount (INR)</th>
                  <th className="py-3 px-4 text-center">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {profitLoss.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-slate-400">
                      No Profit & Loss lines recorded. Click "Auto-Classify" from Trial Balance or upload a P&L sheet.
                    </td>
                  </tr>
                ) : (
                  profitLoss.map((line) => (
                    <tr key={line.id} className="hover:bg-pink-50/30 transition-all">
                      <td className="py-3 px-4 font-bold text-slate-800">{line.category}</td>
                      <td className="py-3 px-4 text-slate-900">{line.line_item_name}</td>
                      <td className="py-3 px-4 text-center font-mono text-slate-500">
                        {line.schedule_note_number || '—'}
                      </td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900">
                        {renderAmount(line.amount)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setProvenanceTarget(line)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-pink-600 hover:text-pink-800 bg-pink-50 px-2 py-0.5 rounded border border-pink-200 cursor-pointer"
                        >
                          <Info className="w-3 h-3" />
                          <span>Audit Link</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 5: CASH FLOW */}
      {activeTab === 'cash-flow' && (
        <div className="space-y-4">
          <div className="p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Cash Flow Statement (AS 3 / Ind AS 7)</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Structured into Operating, Investing, and Financing cash movements reconciled against Balance Sheet cash.
              </p>
            </div>
            <div className="text-right">
              <span className="text-xs text-slate-500 block">Closing Cash Position</span>
              <span className="text-base font-extrabold text-sky-700">
                {renderAmount(overview?.closing_cash)}
              </span>
            </div>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-pink-100 bg-white/90 shadow-2xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-pink-50/60 text-slate-700 font-bold border-b border-pink-100">
                <tr>
                  <th className="py-3 px-4">Activity Type</th>
                  <th className="py-3 px-4">Line Item Description</th>
                  <th className="py-3 px-4 text-right">Cash Inflow / (Outflow)</th>
                  <th className="py-3 px-4 text-center">Provenance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {cashFlow.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="py-8 text-center text-slate-400">
                      No Cash Flow entries found. Add entries or calculate to synthesize cash flow movements.
                    </td>
                  </tr>
                ) : (
                  cashFlow.map((line) => (
                    <tr key={line.id} className="hover:bg-pink-50/30 transition-all">
                      <td className="py-3 px-4 font-bold text-slate-800">{line.activity_type}</td>
                      <td className="py-3 px-4 text-slate-900">{line.line_item_name}</td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900">
                        {renderAmount(line.amount)}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={() => setProvenanceTarget(line)}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-pink-600 hover:text-pink-800 bg-pink-50 px-2 py-0.5 rounded border border-pink-200 cursor-pointer"
                        >
                          <Info className="w-3 h-3" />
                          <span>Audit Link</span>
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 6: NOTES & SCHEDULES */}
      {activeTab === 'notes' && (
        <div className="space-y-4">
          <div className="p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs">
            <h3 className="text-sm font-bold text-slate-900">Notes & Supporting Schedules</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Statutory disclosures under Companies Act 2013 and applicable Indian Accounting Standards.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 rounded-2xl bg-white border border-pink-100 shadow-2xs space-y-2">
              <h4 className="text-xs font-bold text-pink-700 uppercase tracking-wide">
                Note 1: Significant Accounting Policies
              </h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                The financial statements have been prepared in accordance with Indian Accounting Standards and Schedule III of the Companies Act, 2013 under the historical cost convention on an accrual basis.
              </p>
            </div>
            <div className="p-4 rounded-2xl bg-white border border-pink-100 shadow-2xs space-y-2">
              <h4 className="text-xs font-bold text-pink-700 uppercase tracking-wide">
                Note 2: Property, Plant & Equipment (Depreciation)
              </h4>
              <p className="text-xs text-slate-600 leading-relaxed">
                Depreciation on tangible assets is provided under the Written Down Value (WDV) method over useful lives prescribed in Schedule II of the Companies Act, 2013 and Section 32 of the Income Tax Act, 1961.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 7: REVIEW FINDINGS */}
      {activeTab === 'findings' && (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs">
            <div>
              <h3 className="text-sm font-bold text-slate-900">Review Center Discrepancies & Audit Findings</h3>
              <p className="text-xs text-slate-500 mt-0.5">
                Deterministic accounting discrepancies requiring accountant verification prior to final approval.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-500">Filter Severity:</span>
              <select
                value={findingSeverityFilter}
                onChange={(e) => setFindingSeverityFilter(e.target.value)}
                className="px-2.5 py-1 text-xs font-semibold bg-white border border-pink-200 rounded-lg text-slate-700 focus:outline-none"
              >
                <option value="ALL">All Severities</option>
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>
          </div>

          <div className="space-y-3">
            {filteredFindings.length === 0 ? (
              <div className="p-8 text-center bg-white rounded-2xl border border-pink-100">
                <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-slate-800">All Verification Checks Passed</h4>
                <p className="text-xs text-slate-500 mt-1">
                  No active discrepancies found. All Trial Balance and Schedule III equations balance exactly.
                </p>
              </div>
            ) : (
              filteredFindings.map((finding) => (
                <div
                  key={finding.id}
                  className="p-4 rounded-2xl bg-white border border-pink-100 shadow-2xs space-y-3 hover:border-pink-300 transition-all"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`px-2 py-0.5 text-[10px] font-bold rounded-md ${
                            finding.severity === 'CRITICAL'
                              ? 'bg-red-50 text-red-700 border border-red-200'
                              : finding.severity === 'HIGH'
                              ? 'bg-amber-50 text-amber-700 border border-amber-200'
                              : 'bg-slate-100 text-slate-700'
                          }`}
                        >
                          {finding.severity}
                        </span>
                        <span className="text-xs font-bold text-slate-900">{finding.title}</span>
                      </div>
                      <p className="text-xs text-slate-600 leading-relaxed">{finding.description}</p>
                    </div>

                    <span
                      className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                        finding.status === 'APPROVED'
                          ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                          : finding.status === 'REJECTED'
                          ? 'bg-red-50 text-red-700 border-red-200'
                          : 'bg-amber-50 text-amber-700 border-amber-200'
                      }`}
                    >
                      {finding.status}
                    </span>
                  </div>

                  {/* Root Cause Analysis (possible vs proven) */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs p-3 bg-slate-50 rounded-xl">
                    <div>
                      <span className="font-bold text-slate-700 block text-[11px]">Possible Cause:</span>
                      <p className="text-slate-600 text-[11px] mt-0.5">{finding.possible_cause || '—'}</p>
                    </div>
                    <div>
                      <span className="font-bold text-slate-700 block text-[11px]">Proven Cause:</span>
                      <p className="text-slate-600 text-[11px] mt-0.5">{finding.proven_cause || 'Requires accountant verification'}</p>
                    </div>
                  </div>

                  {/* Actions Bar */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-100 text-xs">
                    <span className="text-[11px] text-slate-400">
                      Provenance: {finding.source_document || 'Direct Ledger Calculation'}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleApplyFindingDecision(finding.id, 'ACCEPTED')}
                        className="px-2.5 py-1 text-[11px] font-bold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg cursor-pointer"
                      >
                        Accept
                      </button>
                      <button
                        onClick={() => handleApplyFindingDecision(finding.id, 'REJECTED')}
                        className="px-2.5 py-1 text-[11px] font-bold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 rounded-lg cursor-pointer"
                      >
                        Reject
                      </button>
                      <button
                        onClick={() => handleApplyFindingDecision(finding.id, 'OVERRIDDEN')}
                        className="px-2.5 py-1 text-[11px] font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg cursor-pointer"
                      >
                        Override
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* TAB 8: SNAPSHOTS */}
      {activeTab === 'snapshots' && (
        <div className="space-y-4">
          <div className="p-4 bg-white border border-pink-100 rounded-2xl shadow-2xs">
            <h3 className="text-sm font-bold text-slate-900">Immutable Statement Snapshots</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Historical calculations are permanently versioned with cryptographic SHA-256 integrity hashes.
            </p>
          </div>

          <div className="space-y-3">
            {snapshots.length === 0 ? (
              <div className="p-8 text-center bg-white rounded-2xl border border-pink-100">
                <Clock className="w-8 h-8 text-slate-400 mx-auto mb-2" />
                <h4 className="text-sm font-bold text-slate-800">No Snapshots Stored Yet</h4>
                <p className="text-xs text-slate-500 mt-1">
                  Click "Recalculate" above to create Snapshot v1 with SHA-256 verification hash.
                </p>
              </div>
            ) : (
              snapshots.map((snap) => (
                <div
                  key={snap.id}
                  className="p-4 rounded-2xl bg-white border border-pink-100 shadow-2xs space-y-2 hover:border-pink-300 transition-all"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 text-xs font-extrabold bg-pink-50 text-pink-700 rounded-lg border border-pink-200">
                        v{snap.version}
                      </span>
                      <span className="text-xs font-semibold text-slate-500">
                        {new Date(snap.created_at).toLocaleString()}
                      </span>
                    </div>
                    <span className="text-[11px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                      Immutable
                    </span>
                  </div>

                  <div className="p-2 bg-slate-50 rounded-xl font-mono text-[11px] text-slate-700 break-all border border-slate-200/60">
                    <span className="text-pink-600 font-bold mr-1">SHA-256:</span>
                    {snap.snapshot_hash}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 text-xs">
                    <div>
                      <span className="text-[10px] text-slate-400 block">Total Assets</span>
                      <span className="font-bold text-slate-800">{renderAmount(snap.total_assets)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block">Equity + Liabilities</span>
                      <span className="font-bold text-slate-800">
                        {renderAmount(snap.total_equity_and_liabilities)}
                      </span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block">Profit After Tax</span>
                      <span className="font-bold text-pink-700">{renderAmount(snap.profit_after_tax)}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-slate-400 block">Closing Cash</span>
                      <span className="font-bold text-sky-700">{renderAmount(snap.closing_cash)}</span>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* 5. MODALS */}

      {/* Provenance Detail Modal */}
      {provenanceTarget && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-pink-100 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Info className="w-4 h-4 text-pink-500" />
                <span>Audit Provenance Details</span>
              </h3>
              <button
                onClick={() => setProvenanceTarget(null)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-2 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Account / Item Name</span>
                <span className="font-bold text-slate-900">
                  {provenanceTarget.account_name || provenanceTarget.line_item_name}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Source Document</span>
                <span className="font-mono text-pink-700">
                  {provenanceTarget.source_document || 'Direct Ingestion'}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Worksheet Name</span>
                <span className="font-semibold text-slate-700">{provenanceTarget.source_sheet || '—'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Row Index</span>
                <span className="font-mono text-slate-700">{provenanceTarget.source_row || '—'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Cell Address</span>
                <span className="font-mono font-bold text-pink-600">{provenanceTarget.source_cell || '—'}</span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100">
                <span className="text-slate-500">Source Recorded Value</span>
                <span className="font-mono text-slate-800">{provenanceTarget.source_value || renderAmount(provenanceTarget.amount || provenanceTarget.debit_amount || provenanceTarget.credit_amount)}</span>
              </div>
              <div className="pt-2">
                <span className="text-slate-500 block mb-1">Provenance Notes</span>
                <p className="text-slate-700 bg-slate-50 p-2.5 rounded-xl border border-slate-200/70 text-[11px]">
                  {provenanceTarget.provenance_notes || 'Immutable source line item audited under Schedule III compliance.'}
                </p>
              </div>
            </div>

            <button
              onClick={() => setProvenanceTarget(null)}
              className="w-full py-2 text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all cursor-pointer"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* New Profile Modal */}
      {showCreateProfileModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleCreateProfile}
            className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-pink-100 space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900">New Financial Statements Profile</h3>
              <button
                type="button"
                onClick={() => setShowCreateProfileModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Entity Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Nexus Dynamics India Pvt Ltd"
                  value={newProfileForm.entity_name}
                  onChange={(e) => setNewProfileForm({ ...newProfileForm, entity_name: e.target.value })}
                  className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">CIN or PAN</label>
                <input
                  type="text"
                  placeholder="e.g. U72200MH2024PTC123456"
                  value={newProfileForm.cin_or_pan || ''}
                  onChange={(e) => setNewProfileForm({ ...newProfileForm, cin_or_pan: e.target.value })}
                  className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300 font-mono"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Financial Year *</label>
                  <input
                    type="text"
                    required
                    placeholder="2023-24"
                    value={newProfileForm.financial_year}
                    onChange={(e) => setNewProfileForm({ ...newProfileForm, financial_year: e.target.value })}
                    className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
                  />
                </div>
                <div>
                  <label className="font-bold text-slate-700 block mb-1">Reporting Period</label>
                  <select
                    value={newProfileForm.reporting_period}
                    onChange={(e) => setNewProfileForm({ ...newProfileForm, reporting_period: e.target.value })}
                    className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
                  >
                    <option value="ANNUAL">Annual</option>
                    <option value="Q1">Quarter 1</option>
                    <option value="Q2">Quarter 2</option>
                    <option value="Q3">Quarter 3</option>
                    <option value="Q4">Quarter 4</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Framework</label>
                <select
                  value={newProfileForm.framework}
                  onChange={(e) => setNewProfileForm({ ...newProfileForm, framework: e.target.value })}
                  className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
                >
                  <option value="SCHEDULE_III">Schedule III (Companies Act 2013)</option>
                  <option value="IND_AS">Ind AS (Indian Accounting Standards)</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowCreateProfileModal(false)}
                className="flex-1 py-2 text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading}
                className="flex-1 py-2 text-xs font-bold text-white bg-pink-500 hover:bg-pink-600 rounded-xl transition-all shadow-xs cursor-pointer disabled:opacity-50"
              >
                Create Profile
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <form
            onSubmit={handleUploadDocument}
            className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-pink-100 space-y-4"
          >
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900">Upload Financial Workbook / CSV</h3>
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 bg-pink-50/60 rounded-xl border border-pink-200 text-xs text-pink-800">
              <span className="font-bold block mb-1">Immutable Source File Guarantee</span>
              Original uploaded workbooks are stored immutably. Ledger accounts and balances are extracted with strict cell and row references.
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="font-bold text-slate-700 block mb-1">Select File (.xlsx, .xls, .csv)</label>
                <input
                  type="file"
                  required
                  accept=".xlsx,.xls,.csv"
                  onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-700 file:mr-3 file:py-2 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-bold file:bg-pink-50 file:text-pink-700 hover:file:bg-pink-100"
                />
              </div>

              <div>
                <label className="font-bold text-slate-700 block mb-1">Statement Format Type</label>
                <select
                  value={uploadSheetType}
                  onChange={(e) => setUploadSheetType(e.target.value)}
                  className="w-full px-3 py-2 border border-pink-200 rounded-xl text-slate-800 focus:outline-none focus:ring-2 focus:ring-pink-300"
                >
                  <option value="TRIAL_BALANCE">Trial Balance / General Ledger</option>
                  <option value="BALANCE_SHEET">Balance Sheet</option>
                  <option value="PROFIT_LOSS">Profit & Loss Statement</option>
                </select>
              </div>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowUploadModal(false)}
                className="flex-1 py-2 text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={actionLoading || !uploadFile}
                className="flex-1 py-2 text-xs font-bold text-white bg-pink-500 hover:bg-pink-600 rounded-xl transition-all shadow-xs cursor-pointer disabled:opacity-50"
              >
                Upload & Ingest
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Approval Confirmation Modal */}
      {showApprovalModal && (
        <div className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-xl border border-pink-100 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h3 className="text-sm font-bold text-slate-900 flex items-center gap-2">
                <Lock className="w-4 h-4 text-pink-500" />
                <span>Accountant Statutory Approval</span>
              </h3>
              <button
                onClick={() => setShowApprovalModal(false)}
                className="text-slate-400 hover:text-slate-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {!overview?.eligible_for_approval ? (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs space-y-2">
                <div className="flex items-center gap-1.5 font-bold text-red-800">
                  <AlertTriangle className="w-4 h-4 text-red-600" />
                  <span>Approval Safety Block Active</span>
                </div>
                <p className="text-red-700 leading-relaxed">
                  Financial Statements cannot be approved while critical/high review findings remain unresolved or while the Balance Sheet or Trial Balance is out of balance.
                </p>
                <ul className="list-disc pl-4 text-[11px] text-red-800 space-y-1">
                  {!overview?.is_tb_balanced && <li>Trial Balance is out of balance.</li>}
                  {!overview?.is_bs_balanced && <li>Balance Sheet does not tally.</li>}
                  {(overview?.unresolved_findings_count || 0) > 0 && (
                    <li>{overview?.unresolved_findings_count} review finding(s) require review.</li>
                  )}
                </ul>
              </div>
            ) : (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-xs space-y-2">
                <div className="flex items-center gap-1.5 font-bold text-emerald-800">
                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                  <span>All Pre-Approval Checks Satisfied</span>
                </div>
                <p className="text-emerald-700 leading-relaxed">
                  Trial balance balances, Balance Sheet tallies exactly, and all critical review findings are resolved.
                </p>
              </div>
            )}

            <p className="text-xs text-slate-600 leading-relaxed">
              By approving, you record a permanent timestamped sign-off as the responsible accountant. The AI assistant never makes final accounting decisions.
            </p>

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setShowApprovalModal(false)}
                className="flex-1 py-2 text-xs font-bold text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveStatements}
                disabled={actionLoading || !overview?.eligible_for_approval}
                className="flex-1 py-2 text-xs font-bold text-white bg-slate-900 hover:bg-slate-800 rounded-xl transition-all shadow-xs cursor-pointer disabled:opacity-40"
              >
                Confirm Sign-Off
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
