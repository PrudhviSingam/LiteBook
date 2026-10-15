import React, { useState, useEffect, useCallback } from 'react'
import {
  Receipt,
  Building2,
  Calendar,
  FileText,
  Calculator,
  Scale,
  RefreshCw,
  Plus,
  Lock,
  CheckCircle2,
  AlertCircle,
  UploadCloud,
  Download,
  ShieldCheck,
  ExternalLink,
  ArrowRight,
  ShieldAlert,
} from 'lucide-react'
import type {
  GSTRegistration,
  GSTFilingPeriod,
  GSTSalesInvoice,
  GSTReconciliationResult,
  GSTR1Summary,
  GSTR3BSummary,
  ReconciliationSummary,
  GSTPeriodStatus,
  ReconciliationDecision,
} from '../types/gst'
import {
  fetchGSTRegistrations,
  createGSTRegistration,
  fetchFilingPeriods,
  createFilingPeriod,
  transitionPeriodStatus,
  fetchGSTR1Summary,
  fetchSalesInvoices,
  createSalesInvoice,
  fetchGSTR3BSummary,
  bulkImportGSTR2B,
  runReconciliation,
  fetchReconciliationResults,
  fetchReconciliationSummary,
  submitReconciliationDecision,
  downloadGSTReport,
} from '../services/gstApi'
import { formatINR } from '../utils/formatters'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'

import { GSTR1Section } from '../components/gst/GSTR1Section'
import { GSTR3BSection } from '../components/gst/GSTR3BSection'
import { GSTR2BSection } from '../components/gst/GSTR2BSection'
import { SalesInvoiceDrawer } from '../components/gst/SalesInvoiceDrawer'
import { ReconItemDrawer } from '../components/gst/ReconItemDrawer'
import {
  AddRegistrationModal,
  AddPeriodModal,
  AddSalesInvoiceModal,
  ImportGSTR2BModal,
  TransitionModal,
  UploadGSTFileModal,
} from '../components/gst/GSTModals'

interface GSTReturnsPageProps {
  onNavigate?: (module: string) => void
}

export const GSTReturnsPage: React.FC<GSTReturnsPageProps> = ({ onNavigate }) => {
  // -------------------------------------------------------------------------
  // State: Selections & Core Context
  // -------------------------------------------------------------------------
  const [registrations, setRegistrations] = useState<GSTRegistration[]>([])
  const [selectedRegId, setSelectedRegId] = useState<string | number | null>(null)

  const [periods, setPeriods] = useState<GSTFilingPeriod[]>([])
  const [selectedPeriodId, setSelectedPeriodId] = useState<string | number | null>(null)

  const [activeTab, setActiveTab] = useState<'gstr1' | 'gstr3b' | 'gstr2b'>('gstr1')

  // -------------------------------------------------------------------------
  // State: Data Models
  // -------------------------------------------------------------------------
  const [gstr1Summary, setGstr1Summary] = useState<GSTR1Summary | null>(null)
  const [salesInvoices, setSalesInvoices] = useState<GSTSalesInvoice[]>([])

  const [gstr3bSummary, setGstr3bSummary] = useState<GSTR3BSummary | null>(null)

  const [reconSummary, setReconSummary] = useState<ReconciliationSummary | null>(null)
  const [reconResults, setReconResults] = useState<GSTReconciliationResult[]>([])

  // -------------------------------------------------------------------------
  // State: Loading, Error & Async
  // -------------------------------------------------------------------------
  const [isLoadingContext, setIsLoadingContext] = useState(true)
  const [isLoadingPeriodData, setIsLoadingPeriodData] = useState(false)
  const [isRecalculating, setIsRecalculating] = useState(false)
  const [isReconciling, setIsReconciling] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [bannerNotice, setBannerNotice] = useState<string | null>(null)

  // -------------------------------------------------------------------------
  // State: Drawers & Modals
  // -------------------------------------------------------------------------
  const [selectedInvoice, setSelectedInvoice] = useState<GSTSalesInvoice | null>(null)
  const [selectedReconResult, setSelectedReconResult] =
    useState<GSTReconciliationResult | null>(null)

  const [isAddRegOpen, setIsAddRegOpen] = useState(false)
  const [isAddPeriodOpen, setIsAddPeriodOpen] = useState(false)
  const [isAddInvoiceOpen, setIsAddInvoiceOpen] = useState(false)
  const [isImport2BOpen, setIsImport2BOpen] = useState(false)
  const [isUploadFileOpen, setIsUploadFileOpen] = useState(false)
  const [isExporting, setIsExporting] = useState<string | null>(null)
  const [transitionTarget, setTransitionTarget] = useState<GSTPeriodStatus | null>(null)

  // Current active registration & period objects
  const activeReg = registrations.find((r) => String(r.id) === String(selectedRegId)) || null
  const activePeriod = periods.find((p) => String(p.id) === String(selectedPeriodId)) || null
  const isPeriodLocked =
    activePeriod?.status === 'locked' || activePeriod?.status === 'filed'

  // -------------------------------------------------------------------------
  // 1. Initial Load: Registrations
  // -------------------------------------------------------------------------
  const loadRegistrations = async () => {
    setIsLoadingContext(true)
    setErrorMessage(null)
    try {
      const regs = await fetchGSTRegistrations()
      setRegistrations(regs)
      if (regs.length > 0) {
        setSelectedRegId((prev) => (prev ? prev : regs[0].id))
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load GST Registrations')
    } finally {
      setIsLoadingContext(false)
    }
  }

  useEffect(() => {
    loadRegistrations()
  }, [])

  // -------------------------------------------------------------------------
  // 2. Load Periods when Selected Registration changes
  // -------------------------------------------------------------------------
  const loadPeriodsForReg = useCallback(async (regId: string | number) => {
    try {
      const pList = await fetchFilingPeriods(regId)
      setPeriods(pList)
      if (pList.length > 0) {
        // Select latest period by default
        setSelectedPeriodId(pList[0].id)
      } else {
        setSelectedPeriodId(null)
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load filing periods')
    }
  }, [])

  useEffect(() => {
    if (selectedRegId) {
      loadPeriodsForReg(selectedRegId)
    } else {
      setPeriods([])
      setSelectedPeriodId(null)
    }
  }, [selectedRegId, loadPeriodsForReg])

  // -------------------------------------------------------------------------
  // 3. Load Period Details (GSTR-1, GSTR-3B, GSTR-2B)
  // -------------------------------------------------------------------------
  const loadPeriodDetails = useCallback(async (periodId: string | number) => {
    setIsLoadingPeriodData(true)
    setErrorMessage(null)
    try {
      const [g1Sum, sInvoices, g3bSum, rSum, rRes] = await Promise.all([
        fetchGSTR1Summary(periodId).catch(() => null),
        fetchSalesInvoices(periodId).catch(() => []),
        fetchGSTR3BSummary(periodId).catch(() => null),
        fetchReconciliationSummary(periodId).catch(() => null),
        fetchReconciliationResults(periodId).catch(() => []),
      ])

      setGstr1Summary(g1Sum)
      setSalesInvoices(sInvoices)
      setGstr3bSummary(g3bSum)
      setReconSummary(rSum)
      setReconResults(rRes)
    } catch (err: any) {
      setErrorMessage(err.message || 'Error loading period returns data')
    } finally {
      setIsLoadingPeriodData(false)
    }
  }, [])

  useEffect(() => {
    if (selectedPeriodId) {
      loadPeriodDetails(selectedPeriodId)
    } else {
      setGstr1Summary(null)
      setSalesInvoices([])
      setGstr3bSummary(null)
      setReconSummary(null)
      setReconResults([])
    }
  }, [selectedPeriodId, loadPeriodDetails])

  // -------------------------------------------------------------------------
  // Actions: Recalculate
  // -------------------------------------------------------------------------
  const handleRecalculate = async () => {
    if (!selectedPeriodId) return
    setIsRecalculating(true)
    setErrorMessage(null)
    try {
      const [g1Sum, g3bSum] = await Promise.all([
        fetchGSTR1Summary(selectedPeriodId, true),
        fetchGSTR3BSummary(selectedPeriodId, true),
      ])
      setGstr1Summary(g1Sum)
      setGstr3bSummary(g3bSum)
      setBannerNotice('Return summaries recalculated with statutory set-off logic.')
      setTimeout(() => setBannerNotice(null), 3500)
    } catch (err: any) {
      setErrorMessage(err.message || 'Recalculation failed')
    } finally {
      setIsRecalculating(false)
    }
  }

  // -------------------------------------------------------------------------
  // Actions: Run Reconciliation Engine
  // -------------------------------------------------------------------------
  const handleRunReconciliation = async () => {
    if (!selectedPeriodId) return
    setIsReconciling(true)
    setErrorMessage(null)
    try {
      await runReconciliation(selectedPeriodId, 1.0, 3)
      const [rSum, rRes, g3bSum] = await Promise.all([
        fetchReconciliationSummary(selectedPeriodId),
        fetchReconciliationResults(selectedPeriodId),
        fetchGSTR3BSummary(selectedPeriodId, true),
      ])
      setReconSummary(rSum)
      setReconResults(rRes)
      setGstr3bSummary(g3bSum)
      setBannerNotice('GSTR-2B matching engine completed successfully.')
      setTimeout(() => setBannerNotice(null), 3500)
    } catch (err: any) {
      setErrorMessage(err.message || 'Reconciliation failed')
    } finally {
      setIsReconciling(false)
    }
  }

  // -------------------------------------------------------------------------
  // Actions: Quick Decision
  // -------------------------------------------------------------------------
  const handleQuickDecision = async (
    resultId: string | number,
    decision: ReconciliationDecision
  ) => {
    try {
      const updated = await submitReconciliationDecision(resultId, decision)
      setReconResults((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to update decision')
    }
  }

  // -------------------------------------------------------------------------
  // Actions: Workflow Status Transition
  // -------------------------------------------------------------------------
  const handleConfirmTransition = async (notes?: string, arn?: string) => {
    if (!selectedPeriodId || !transitionTarget) return
    const updated = await transitionPeriodStatus(
      selectedPeriodId,
      transitionTarget,
      notes,
      arn
    )
    setPeriods((prev) => prev.map((p) => (p.id === updated.id ? updated : p)))
    setBannerNotice(`Period status updated to ${updated.status.toUpperCase()}`)
    setTimeout(() => setBannerNotice(null), 3500)
  }

  // -------------------------------------------------------------------------
  // Actions: Statutory Export Functionality
  // -------------------------------------------------------------------------
  const handleExportReport = async (reportType: 'gstr1' | 'gstr3b' | 'reconciliation') => {
    if (!selectedPeriodId) return
    setIsExporting(reportType)
    try {
      await downloadGSTReport(selectedPeriodId, reportType, 'csv')
      setBannerNotice(`Successfully exported ${reportType.toUpperCase()} statutory calculation report.`)
      setTimeout(() => setBannerNotice(null), 3500)
    } catch (err: any) {
      setErrorMessage(err.message || `Failed to export ${reportType} report`)
    } finally {
      setIsExporting(null)
    }
  }

  // Helper for real computed values only (show "—" when unavailable, no fake numbers)
  const formatRealVal = (val: string | number | null | undefined): string => {
    if (val === null || val === undefined || val === '') return '—'
    const num = typeof val === 'number' ? val : Number(val)
    if (isNaN(num)) return '—'
    return formatINR(num)
  }

  // Helper for status badge
  const getStatusBadge = (statusVal?: GSTPeriodStatus) => {
    switch (statusVal) {
      case 'draft':
        return (
          <Badge variant="pink" dot>
            Draft Preparation
          </Badge>
        )
      case 'under_review':
        return (
          <Badge variant="warning" dot>
            Under Review
          </Badge>
        )
      case 'approved':
        return (
          <Badge variant="info" dot>
            Approved
          </Badge>
        )
      case 'filed':
        return (
          <Badge variant="success" dot>
            Filed (Statutory)
          </Badge>
        )
      case 'locked':
        return (
          <Badge variant="danger" dot>
            Period Locked
          </Badge>
        )
      default:
        return <Badge variant="neutral">No Period Selected</Badge>
    }
  }

  const discrepanciesCount =
    (reconSummary?.partial_matches || 0) +
    (reconSummary?.books_only || 0) +
    (reconSummary?.return_only || 0)

  return (
    <div className="space-y-6 max-w-7xl mx-auto py-2">
      {/* --------------------------------------------------------------------- */}
      {/* 1. Header & Period Selector Bar */}
      {/* --------------------------------------------------------------------- */}
      <div className="glass-panel p-5 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-brand-50 to-pink-100 border border-brand-200/90 text-brand-600 flex items-center justify-center shadow-xs">
              <Receipt className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
                  GST Returns & Statutory Compliance
                </h1>
                <span className="hidden sm:inline-flex px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                  GST Council Rules Active
                </span>
                {isPeriodLocked && (
                  <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-2xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
                    <Lock className="w-3 h-3" />
                    Period Locked
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-500 mt-0.5">
                Indian GSTR-1 outward filing, GSTR-3B monthly tax computation, and GSTR-2B ITC reconciliation.
              </p>
            </div>
          </div>

          {/* Workflow Status & Actions */}
          <div className="flex flex-wrap items-center gap-2">
            {getStatusBadge(activePeriod?.status)}

            {/* Upload GST/Accounting File */}
            <Button
              size="sm"
              variant="primary"
              icon={<UploadCloud className="w-3.5 h-3.5" />}
              disabled={isPeriodLocked || !selectedPeriodId}
              onClick={() => setIsUploadFileOpen(true)}
              title={!selectedPeriodId ? 'Select or create a period first' : 'Upload GST/Accounting files'}
            >
              Upload GST File
            </Button>

            {/* Recalculate Button */}
            {activePeriod && (
              <Button
                size="sm"
                variant="secondary"
                icon={<RefreshCw className="w-3.5 h-3.5" />}
                isLoading={isRecalculating}
                disabled={isPeriodLocked}
                onClick={handleRecalculate}
                title="Recalculate GSTR-1 and GSTR-3B"
              >
                Recalculate
              </Button>
            )}

            {/* Review Center Deep Link */}
            {onNavigate && discrepanciesCount > 0 && (
              <Button
                size="sm"
                variant="secondary"
                icon={<ExternalLink className="w-3.5 h-3.5 text-brand-600" />}
                onClick={() => onNavigate('review-center')}
                title="Review GST discrepancies in Review Center"
                className="bg-brand-50/80 hover:bg-brand-100 border-brand-200 text-brand-700 font-semibold"
              >
                Review Center ({discrepanciesCount})
              </Button>
            )}

            {/* Export Reports Group */}
            {activePeriod && (
              <div className="flex items-center gap-1 border-l border-slate-200/80 pl-2">
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Download className="w-3.5 h-3.5" />}
                  isLoading={isExporting === 'gstr1'}
                  onClick={() => handleExportReport('gstr1')}
                  title="Export GSTR-1 Summary CSV"
                  className="text-xs text-slate-700"
                >
                  GSTR-1
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Download className="w-3.5 h-3.5" />}
                  isLoading={isExporting === 'gstr3b'}
                  onClick={() => handleExportReport('gstr3b')}
                  title="Export GSTR-3B Computation CSV"
                  className="text-xs text-slate-700"
                >
                  GSTR-3B
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  icon={<Download className="w-3.5 h-3.5" />}
                  isLoading={isExporting === 'reconciliation'}
                  onClick={() => handleExportReport('reconciliation')}
                  title="Export GSTR-2B Reconciliation CSV"
                  className="text-xs text-slate-700"
                >
                  Recon
                </Button>
              </div>
            )}

            {/* Transition Action Buttons */}
            {activePeriod?.status === 'draft' && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setTransitionTarget('under_review')}
              >
                Submit for Review
              </Button>
            )}

            {activePeriod?.status === 'under_review' && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setTransitionTarget('approved')}
              >
                Approve Return
              </Button>
            )}

            {activePeriod?.status === 'approved' && (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setTransitionTarget('filed')}
              >
                Mark as Filed
              </Button>
            )}

            {activePeriod?.status === 'filed' && (
              <Button
                size="sm"
                variant="danger"
                icon={<Lock className="w-3.5 h-3.5" />}
                onClick={() => setTransitionTarget('locked')}
              >
                Lock Period
              </Button>
            )}

            {activePeriod?.status === 'locked' && (
              <span className="text-xs font-semibold text-slate-500 flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-100 border border-slate-200">
                <Lock className="w-3.5 h-3.5 text-slate-600" />
                Locked on {activePeriod.locked_at ? new Date(activePeriod.locked_at).toLocaleDateString() : 'Record'}
              </span>
            )}
          </div>
        </div>

        {/* GSTIN & Period Selectors Bar */}
        <div className="pt-3 border-t border-slate-200/70 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            {/* Registration Dropdown */}
            <div className="flex items-center gap-2">
              <Building2 className="w-4 h-4 text-brand-600 shrink-0" />
              <select
                value={selectedRegId || ''}
                onChange={(e) => setSelectedRegId(e.target.value)}
                className="glass-input text-xs px-3 py-1.5 rounded-lg font-medium text-slate-800"
              >
                {registrations.length === 0 ? (
                  <option value="">No GST Registrations Found</option>
                ) : (
                  registrations.map((reg) => (
                    <option key={reg.id} value={reg.id}>
                      {reg.legal_name} ({reg.gstin}) - State {reg.state_code}
                    </option>
                  ))
                )}
              </select>
              <button
                onClick={() => setIsAddRegOpen(true)}
                className="p-1.5 rounded-lg text-brand-600 hover:bg-brand-50 border border-brand-200/80 transition-colors cursor-pointer"
                title="Add New GSTIN"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Filing Period Dropdown */}
            {activeReg && (
              <div className="flex items-center gap-2 border-l border-slate-200/80 pl-3">
                <Calendar className="w-4 h-4 text-brand-600 shrink-0" />
                <select
                  value={selectedPeriodId || ''}
                  onChange={(e) => setSelectedPeriodId(e.target.value)}
                  className="glass-input text-xs px-3 py-1.5 rounded-lg font-medium text-slate-800"
                >
                  {periods.length === 0 ? (
                    <option value="">No Periods Created</option>
                  ) : (
                    periods.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.period} (FY {p.financial_year}) • {p.status.toUpperCase()}
                      </option>
                    ))
                  )}
                </select>
                <button
                  onClick={() => setIsAddPeriodOpen(true)}
                  className="p-1.5 rounded-lg text-brand-600 hover:bg-brand-50 border border-brand-200/80 transition-colors cursor-pointer"
                  title="Create Filing Period"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>

          {activePeriod?.filing_arn && (
            <div className="text-2xs font-mono text-slate-600 bg-pink-50/60 px-3 py-1 rounded-lg border border-pink-200/80 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
              Govt ARN: <strong>{activePeriod.filing_arn}</strong>
            </div>
          )}
        </div>
      </div>

      {/* Notices & Banners */}
      {bannerNotice && (
        <div className="p-3 rounded-xl bg-emerald-50 text-emerald-900 border border-emerald-200/80 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            {bannerNotice}
          </div>
          <button
            onClick={() => setBannerNotice(null)}
            className="text-emerald-700 hover:underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 rounded-xl bg-rose-50 text-rose-900 border border-rose-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            {errorMessage}
          </div>
          <button
            onClick={() => setErrorMessage(null)}
            className="text-rose-700 hover:underline cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Statutory Non-Submission Disclaimer Banner */}
      <div className="p-3.5 rounded-xl bg-pink-50/60 text-slate-700 border border-pink-200/80 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center gap-2.5">
          <ShieldCheck className="w-4 h-4 text-brand-600 shrink-0" />
          <div>
            <span className="font-bold text-brand-900">Statutory Policy: </span>
            Internal preparation, computation, and reconciliation workbench only. GST returns are <strong>never silently submitted to any government portal</strong>. Official filing requires authorized accountant review and DSC/EVC sign-off.
          </div>
        </div>
      </div>

      {/* Period Locked Banner */}
      {isPeriodLocked && (
        <div className="p-3.5 rounded-xl bg-slate-100 text-slate-800 border border-slate-300 text-xs flex items-center justify-between shadow-xs">
          <div className="flex items-center gap-2.5">
            <Lock className="w-4 h-4 text-slate-700 shrink-0" />
            <div>
              <span className="font-bold text-slate-900">Period Locked: </span>
              This statutory period ({activePeriod?.period}) is locked/filed. Data modifications, imports, and recalculations are disabled by backend statutory protections.
            </div>
          </div>
        </div>
      )}

      {/* Stale Calculation Warning Banner */}
      {(gstr1Summary?.is_stale || gstr3bSummary?.is_stale) && (
        <div className="p-3.5 rounded-xl bg-amber-50 text-amber-950 border border-amber-300 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
          <div className="flex items-center gap-2.5">
            <AlertCircle className="w-5 h-5 text-amber-600 shrink-0" />
            <div>
              <span className="font-bold text-amber-900">Recalculation Required: </span>
              Deterministic SHA-256 calculation snapshot detected changes in source records. Recalculate to generate fresh statutory figures before approval or filing.
            </div>
          </div>
          <Button
            size="sm"
            variant="secondary"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            isLoading={isRecalculating}
            disabled={isPeriodLocked}
            onClick={handleRecalculate}
            className="shrink-0 bg-white hover:bg-amber-100/50 border-amber-300 text-amber-900"
          >
            Recalculate Now
          </Button>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 2. Interactive 9-Step Visible Workflow */}
      {/* --------------------------------------------------------------------- */}
      {activePeriod && (
        <div className="glass-panel p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-slate-200/60 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="text-2xs font-extrabold uppercase tracking-wider text-brand-700 bg-brand-50 px-2 py-0.5 rounded">
                GST Lifecycle Workflow
              </span>
              <span className="text-xs text-slate-500">
                End-to-end statutory preparation from upload to accountant review
              </span>
            </div>
            {discrepanciesCount > 0 && onNavigate && (
              <button
                onClick={() => onNavigate('review-center')}
                className="text-xs font-semibold text-brand-700 hover:text-brand-900 flex items-center gap-1 cursor-pointer"
              >
                <span>{discrepanciesCount} Discrepancies in Review Center</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-2">
            {[
              {
                num: 1,
                label: 'Upload Files',
                desc: salesInvoices.length > 0 || reconResults.length > 0 ? 'Files present' : 'Needs upload',
                done: salesInvoices.length > 0 || reconResults.length > 0,
                active: !isPeriodLocked,
                onClick: () => setIsUploadFileOpen(true),
              },
              {
                num: 2,
                label: 'Select Period',
                desc: activePeriod.period,
                done: true,
                active: false,
              },
              {
                num: 3,
                label: 'Analyze / Import',
                desc: isRecalculating ? 'Syncing...' : gstr1Summary ? 'Calculated' : 'Ready',
                done: !!gstr1Summary && !gstr1Summary.is_stale,
                active: !isPeriodLocked && !!selectedPeriodId,
                onClick: handleRecalculate,
              },
              {
                num: 4,
                label: 'Extracted Data',
                desc: `${salesInvoices.length} Invoices`,
                done: salesInvoices.length > 0,
                active: activeTab === 'gstr1',
                onClick: () => setActiveTab('gstr1'),
              },
              {
                num: 5,
                label: 'Validate',
                desc: gstr1Summary?.is_stale || gstr3bSummary?.is_stale ? 'Recalc needed' : 'Validated',
                done: !!gstr1Summary && !gstr1Summary.is_stale,
                active: false,
              },
              {
                num: 6,
                label: 'Reconcile 1/3B/2B',
                desc: reconSummary ? `${reconSummary.match_rate_percentage}% Matched` : 'Run Recon',
                done: !!reconSummary,
                active: activeTab === 'gstr2b',
                onClick: () => {
                  setActiveTab('gstr2b')
                  if (!reconSummary) handleRunReconciliation()
                },
              },
              {
                num: 7,
                label: 'Discrepancies',
                desc: `${discrepanciesCount} items`,
                done: reconResults.length > 0,
                active: discrepanciesCount > 0,
                onClick: () => setActiveTab('gstr2b'),
              },
              {
                num: 8,
                label: 'GST Summary',
                desc: gstr3bSummary ? `Payable ${formatINR(gstr3bSummary.total_tax_payable)}` : 'Pending',
                done: !!gstr3bSummary,
                active: activeTab === 'gstr3b',
                onClick: () => setActiveTab('gstr3b'),
              },
              {
                num: 9,
                label: 'Accountant Review',
                desc: activePeriod.status.toUpperCase(),
                done: activePeriod.status === 'approved' || activePeriod.status === 'filed' || activePeriod.status === 'locked',
                active: activePeriod.status === 'under_review',
                onClick: () => {
                  if (activePeriod.status === 'draft') setTransitionTarget('under_review')
                },
              },
            ].map((st) => (
              <div
                key={st.num}
                onClick={st.onClick}
                className={`p-2 rounded-xl border text-center transition-all ${
                  st.onClick ? 'cursor-pointer hover:border-brand-400 hover:shadow-2xs' : ''
                } ${
                  st.done
                    ? 'bg-emerald-50/50 border-emerald-200 text-emerald-900'
                    : st.active
                    ? 'bg-pink-50/70 border-brand-300 text-brand-900'
                    : 'bg-white/50 border-slate-200/80 text-slate-600'
                }`}
              >
                <div className="flex items-center justify-center gap-1 mb-1">
                  <span
                    className={`w-4 h-4 rounded-full text-2xs font-extrabold flex items-center justify-center ${
                      st.done
                        ? 'bg-emerald-600 text-white'
                        : st.active
                        ? 'bg-brand-600 text-white'
                        : 'bg-slate-200 text-slate-600'
                    }`}
                  >
                    {st.done ? '✓' : st.num}
                  </span>
                </div>
                <div className="text-2xs font-bold truncate leading-tight">{st.label}</div>
                <div className="text-3xs text-slate-500 truncate mt-0.5">{st.desc}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 3. GST Dashboard: 7 REAL Calculated Value Cards Only ("—" if unavailable) */}
      {/* --------------------------------------------------------------------- */}
      {activePeriod && (
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {/* Card 1: Total Outward Supplies */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              Total Outward
            </span>
            <div className="text-base sm:text-lg font-extrabold text-slate-900 tracking-tight truncate">
              {gstr1Summary
                ? formatRealVal(Number(gstr1Summary.total_taxable_value) + Number(gstr1Summary.total_tax))
                : '—'}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Taxable + Tax Value
            </div>
          </div>

          {/* Card 2: Taxable Value */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              Taxable Value
            </span>
            <div className="text-base sm:text-lg font-extrabold text-slate-900 tracking-tight truncate">
              {formatRealVal(gstr1Summary?.total_taxable_value)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Invoices: {gstr1Summary?.total_invoices_count ?? '—'}
            </div>
          </div>

          {/* Card 3: IGST */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              IGST (Integrated)
            </span>
            <div className="text-base sm:text-lg font-extrabold text-brand-700 tracking-tight truncate">
              {formatRealVal(gstr1Summary?.total_igst)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Inter-state Outward
            </div>
          </div>

          {/* Card 4: CGST */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              CGST (Central)
            </span>
            <div className="text-base sm:text-lg font-extrabold text-brand-700 tracking-tight truncate">
              {formatRealVal(gstr1Summary?.total_cgst)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Intra-state Outward
            </div>
          </div>

          {/* Card 5: SGST */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              SGST (State)
            </span>
            <div className="text-base sm:text-lg font-extrabold text-brand-700 tracking-tight truncate">
              {formatRealVal(gstr1Summary?.total_sgst)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Intra-state Outward
            </div>
          </div>

          {/* Card 6: Input Tax Credit */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              Input Tax Credit
            </span>
            <div className="text-base sm:text-lg font-extrabold text-emerald-700 tracking-tight truncate">
              {formatRealVal(gstr3bSummary?.itc_total ?? null)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Recon: {reconSummary ? `${reconSummary.match_rate_percentage}%` : '—'}
            </div>
          </div>

          {/* Card 7: Net Tax Payable */}
          <div className="glass-card p-3.5 space-y-1">
            <span className="text-3xs font-bold text-slate-500 uppercase tracking-wider block">
              Net Tax Payable
            </span>
            <div className="text-base sm:text-lg font-extrabold text-rose-700 tracking-tight truncate">
              {formatRealVal(gstr3bSummary?.total_tax_payable)}
            </div>
            <div className="text-3xs text-slate-500 truncate pt-1 border-t border-slate-100">
              Cash Liability
            </div>
          </div>
        </div>
      )}

      {/* Empty State before upload */}
      {activePeriod && salesInvoices.length === 0 && reconResults.length === 0 && !isLoadingPeriodData && (
        <div className="glass-card p-8 text-center space-y-3">
          <div className="w-12 h-12 mx-auto rounded-2xl bg-gradient-to-br from-brand-50 to-pink-100 border border-brand-200/90 text-brand-600 flex items-center justify-center">
            <UploadCloud className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-extrabold text-slate-800">
            Upload GST/accounting files to begin.
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Import sales invoices, purchase registers, or GSTR-2B portal exports (.xlsx, .csv, .json) for period {activePeriod.period}.
          </p>
          <Button
            size="sm"
            variant="primary"
            icon={<UploadCloud className="w-4 h-4" />}
            disabled={isPeriodLocked}
            onClick={() => setIsUploadFileOpen(true)}
          >
            Upload GST / Accounting Files
          </Button>
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 3. Empty State if no registration or period exists */}
      {/* --------------------------------------------------------------------- */}
      {registrations.length === 0 && !isLoadingContext && (
        <EmptyState
          title="No GST Registration Configured"
          description="Register your business's GSTIN and state registration code to start generating statutory GST returns and running automated reconciliations."
          action={
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setIsAddRegOpen(true)}
            >
              Add GST Registration
            </Button>
          }
        />
      )}

      {registrations.length > 0 && periods.length === 0 && !isLoadingPeriodData && (
        <EmptyState
          title="No Filing Period Found"
          description={`No monthly filing periods exist for ${activeReg?.legal_name} (${activeReg?.gstin}). Create a filing period (e.g. 2024-04) to begin.`}
          action={
            <Button
              variant="primary"
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setIsAddPeriodOpen(true)}
            >
              Create Filing Period
            </Button>
          }
        />
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 4. Tab Navigation & Active Return View */}
      {/* --------------------------------------------------------------------- */}
      {activePeriod && (
        <div className="space-y-6">
          {/* Tab Selector */}
          <div className="border-b border-slate-200/80 flex items-center gap-2">
            <button
              onClick={() => setActiveTab('gstr1')}
              className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                activeTab === 'gstr1'
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <FileText className="w-4 h-4" />
              GSTR-1 (Outward Supplies)
              <span className="px-2 py-0.5 rounded-full text-2xs bg-pink-100 text-brand-800">
                {salesInvoices.length}
              </span>
            </button>

            <button
              onClick={() => setActiveTab('gstr3b')}
              className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                activeTab === 'gstr3b'
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Calculator className="w-4 h-4" />
              GSTR-3B (Tax Computation & Set-off)
            </button>

            <button
              onClick={() => setActiveTab('gstr2b')}
              className={`px-4 py-2.5 text-xs font-bold border-b-2 transition-all flex items-center gap-2 cursor-pointer ${
                activeTab === 'gstr2b'
                  ? 'border-brand-600 text-brand-700'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Scale className="w-4 h-4" />
              GSTR-2B (ITC Reconciliation Engine)
              <span className="px-2 py-0.5 rounded-full text-2xs bg-pink-100 text-brand-800">
                {reconResults.length}
              </span>
            </button>
          </div>

          {/* Tab Content Panels */}
          {activeTab === 'gstr1' && (
            <GSTR1Section
              summary={gstr1Summary}
              invoices={salesInvoices}
              isLocked={isPeriodLocked}
              onAddInvoiceClick={() => setIsAddInvoiceOpen(true)}
              onSelectInvoice={(inv) => setSelectedInvoice(inv)}
              onExportClick={() => handleExportReport('gstr1')}
            />
          )}

          {activeTab === 'gstr3b' && (
            <GSTR3BSection
              summary={gstr3bSummary}
              isLocked={isPeriodLocked}
              isRecalculating={isRecalculating}
              onRecalculate={handleRecalculate}
              onExportClick={() => handleExportReport('gstr3b')}
            />
          )}

          {activeTab === 'gstr2b' && (
            <GSTR2BSection
              summary={reconSummary}
              results={reconResults}
              isLocked={isPeriodLocked}
              isReconciling={isReconciling}
              onRunReconciliation={handleRunReconciliation}
              onImportGSTR2BClick={() => setIsImport2BOpen(true)}
              onSelectResult={(item) => setSelectedReconResult(item)}
              onQuickDecision={handleQuickDecision}
              onExportClick={() => handleExportReport('reconciliation')}
            />
          )}
        </div>
      )}

      {/* --------------------------------------------------------------------- */}
      {/* 5. Drawers */}
      {/* --------------------------------------------------------------------- */}
      <SalesInvoiceDrawer
        invoice={selectedInvoice}
        onClose={() => setSelectedInvoice(null)}
      />

      <ReconItemDrawer
        item={selectedReconResult}
        isLocked={isPeriodLocked}
        onClose={() => setSelectedReconResult(null)}
        onDecisionUpdated={(updated) => {
          setSelectedReconResult(updated)
          setReconResults((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
        }}
      />

      {/* --------------------------------------------------------------------- */}
      {/* 6. Modals */}
      {/* --------------------------------------------------------------------- */}
      <AddRegistrationModal
        isOpen={isAddRegOpen}
        onClose={() => setIsAddRegOpen(false)}
        onSubmit={async (data) => {
          const newReg = await createGSTRegistration(data)
          setRegistrations((prev) => [...prev, newReg])
          setSelectedRegId(newReg.id)
        }}
      />

      <AddPeriodModal
        isOpen={isAddPeriodOpen}
        onClose={() => setIsAddPeriodOpen(false)}
        onSubmit={async (data) => {
          if (!selectedRegId) return
          const newPeriod = await createFilingPeriod({
            registration_id: selectedRegId,
            period: data.period,
            financial_year: data.financial_year,
          })
          setPeriods((prev) => [newPeriod, ...prev])
          setSelectedPeriodId(newPeriod.id)
        }}
      />

      <AddSalesInvoiceModal
        isOpen={isAddInvoiceOpen}
        registrationStateCode={activeReg?.state_code || '27'}
        onClose={() => setIsAddInvoiceOpen(false)}
        onSubmit={async (data) => {
          if (!selectedPeriodId) return
          const created = await createSalesInvoice(selectedPeriodId, data)
          setSalesInvoices((prev) => [created, ...prev])
          // Auto recalculate summaries
          handleRecalculate()
        }}
      />

      <ImportGSTR2BModal
        isOpen={isImport2BOpen}
        onClose={() => setIsImport2BOpen(false)}
        onSubmit={async (records) => {
          if (!selectedPeriodId) return
          await bulkImportGSTR2B(selectedPeriodId, records)
          // Run matching engine
          handleRunReconciliation()
        }}
      />

      <UploadGSTFileModal
        isOpen={isUploadFileOpen}
        periodId={selectedPeriodId}
        periodName={activePeriod?.period || ''}
        isLocked={isPeriodLocked}
        onClose={() => setIsUploadFileOpen(false)}
        onUploadSuccess={(res) => {
          if (selectedPeriodId) {
            loadPeriodDetails(selectedPeriodId)
            setBannerNotice(res.message || 'GST file uploaded and records successfully imported.')
            setTimeout(() => setBannerNotice(null), 3500)
          }
        }}
      />

      <TransitionModal
        isOpen={transitionTarget !== null}
        targetStatus={transitionTarget}
        periodName={activePeriod?.period || ''}
        onClose={() => setTransitionTarget(null)}
        onConfirm={handleConfirmTransition}
      />
    </div>
  )
}
export default GSTReturnsPage
