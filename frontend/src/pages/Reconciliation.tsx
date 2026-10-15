import React, { useState, useEffect } from 'react'
import {
  FileSpreadsheet,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Clock,
  Download,
  Search,
  Eye,
  X,
  SlidersHorizontal,
  FileCheck,
  Check,
  Filter,
  ArrowRight,
  ShieldCheck,
  RefreshCw,
  HelpCircle,
  FileText,
  TableProperties,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import type {
  ColumnMappingPreview,
  DifferenceType,
  ReconciliationItem,
  ReconciliationSessionResponse,
} from '../types'
import { formatINR } from '../utils/formatters'
import {
  previewReconciliationFile,
  runReconciliation,
  getReconciliationReportUrl,
  getDifferenceReportUrl,
  updateItemReviewStatus,
} from '../services/api'

const SAMPLE_FILE_A_CSV = `Date,Reference,Description,Amount
2026-09-02,TXN901021,AWS Cloud Infrastructure Hosting,14500.00
2026-09-05,TXN901022,Commercial Office Lease September,45000.00
2026-09-08,TXN901023,Client Retainer Inflow - Acme Corp,120000.00
2026-09-10,TXN901024,State Electricity Board Power Bill,25000.00
2026-09-11,SUB88102,SaaS Productivity Suite Subscription,4999.00
2026-09-11,SUB88102,SaaS Productivity Suite Subscription,4999.00
2026-09-12,UTR789201,Statutory Annual Audit Fee,50000.00
2026-09-14,CHG202609,Bank Quarterly Maintenance & SMS Charges,1750.00
2026-09-15,INT202609,Fixed Deposit Interest Credit,8420.00
2026-09-16,TXN901025,Vendor Hardware Workstation Supply,38200.00`

const SAMPLE_FILE_B_CSV = `Date,Particulars,Voucher No,Net Amount
2026-09-02,AWS Cloud Infrastructure Hosting,TXN901021,14500.00
2026-09-05,Commercial Office Lease September,TXN901022,45000.00
2026-09-08,Client Retainer Inflow - Acme Corp,TXN901023,120000.00
2026-09-09,Vendor Hardware Workstation Supply,TXN901025,38200.00
2026-09-10,State Electricity Board Power Bill,TXN901024,24500.00
2026-09-11,SaaS Productivity Suite Subscription,SUB88102,4999.00
2026-09-12,Statutory Annual Audit Fee,UTR789201,50000.00
2026-09-13,Apex Logistics Clearing Charges,CHQ991001,19800.00
2026-09-14,Branch Office Petty Cash Top-up,VCH402,3200.00`

export const ReconciliationPage: React.FC = () => {
  // File A (Primary)
  const [fileA, setFileA] = useState<File | null>(null)
  const [sheetA, setSheetA] = useState<string>('')
  const [previewA, setPreviewA] = useState<ColumnMappingPreview | null>(null)
  const [mappingA, setMappingA] = useState<Record<string, string>>({
    date: '',
    reference: '',
    description: '',
    amount: '',
  })

  // File B (Comparison)
  const [fileB, setFileB] = useState<File | null>(null)
  const [sheetB, setSheetB] = useState<string>('')
  const [previewB, setPreviewB] = useState<ColumnMappingPreview | null>(null)
  const [mappingB, setMappingB] = useState<Record<string, string>>({
    date: '',
    reference: '',
    description: '',
    amount: '',
  })

  // Matching Configuration
  const [dateToleranceDays, setDateToleranceDays] = useState<number>(1)
  const [amountTolerance, setAmountTolerance] = useState<number>(0.0)
  const [showConfig, setShowConfig] = useState(false)
  const [statusOnlyMode, setStatusOnlyMode] = useState(false)

  // Execution & Audit States
  const [processing, setProcessing] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [sessionResponse, setSessionResponse] = useState<ReconciliationSessionResponse | null>(null)

  // Filtering & Selected Difference Drawer
  const [activeFilter, setActiveFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState<string>('')
  const [selectedItem, setSelectedItem] = useState<ReconciliationItem | null>(null)
  const [reviewUpdating, setReviewUpdating] = useState(false)

  // Initialize mappings from preview
  useEffect(() => {
    if (previewA) {
      setMappingA({
        date: previewA.column_mapping.date || '',
        reference: previewA.column_mapping.reference || '',
        description: previewA.column_mapping.description || '',
        amount: previewA.column_mapping.amount || previewA.column_mapping.debit || '',
      })
      if (previewA.sheet_names && previewA.sheet_names.length > 0 && !sheetA) {
        setSheetA(previewA.selected_sheet || previewA.sheet_names[0])
      }
    }
  }, [previewA])

  useEffect(() => {
    if (previewB) {
      setMappingB({
        date: previewB.column_mapping.date || '',
        reference: previewB.column_mapping.reference || '',
        description: previewB.column_mapping.description || '',
        amount: previewB.column_mapping.amount || previewB.column_mapping.debit || '',
      })
      if (previewB.sheet_names && previewB.sheet_names.length > 0 && !sheetB) {
        setSheetB(previewB.selected_sheet || previewB.sheet_names[0])
      }
    }
  }, [previewB])

  // Handle File A Upload
  const handleFileAChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setFileA(file)
      setErrorMessage(null)
      try {
        const prev = await previewReconciliationFile(file)
        setPreviewA(prev)
      } catch (err: any) {
        setErrorMessage(err.message || 'Error parsing File A.')
      }
    }
  }

  // Handle Sheet A Change
  const handleSheetAChange = async (sheet: string) => {
    setSheetA(sheet)
    if (fileA) {
      try {
        const prev = await previewReconciliationFile(fileA, sheet)
        setPreviewA(prev)
      } catch (err: any) {
        setErrorMessage(err.message || 'Error loading Sheet for File A.')
      }
    }
  }

  // Handle File B Upload
  const handleFileBChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0]
      setFileB(file)
      setErrorMessage(null)
      try {
        const prev = await previewReconciliationFile(file)
        setPreviewB(prev)
      } catch (err: any) {
        setErrorMessage(err.message || 'Error parsing File B.')
      }
    }
  }

  // Handle Sheet B Change
  const handleSheetBChange = async (sheet: string) => {
    setSheetB(sheet)
    if (fileB) {
      try {
        const prev = await previewReconciliationFile(fileB, sheet)
        setPreviewB(prev)
      } catch (err: any) {
        setErrorMessage(err.message || 'Error loading Sheet for File B.')
      }
    }
  }

  // Load Representative Sample Data
  const handleLoadSampleData = async () => {
    setErrorMessage(null)
    const blobA = new Blob([SAMPLE_FILE_A_CSV], { type: 'text/csv' })
    const fA = new File([blobA], 'financial_records_primary.csv', { type: 'text/csv' })
    const blobB = new Blob([SAMPLE_FILE_B_CSV], { type: 'text/csv' })
    const fB = new File([blobB], 'financial_records_comparison.csv', { type: 'text/csv' })

    setFileA(fA)
    setFileB(fB)

    try {
      const prevA = await previewReconciliationFile(fA)
      const prevB = await previewReconciliationFile(fB)
      setPreviewA(prevA)
      setPreviewB(prevB)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to load sample data')
    }
  }

  // Execute Difference Detection
  const handleRunDifferenceDetection = async () => {
    if (!fileA || !fileB) {
      setErrorMessage('Please select both Source File A and Source File B to detect differences.')
      return
    }

    setProcessing(true)
    setErrorMessage(null)
    setSelectedItem(null)

    try {
      const response = await runReconciliation({
        fileA,
        fileB,
        sheetA: sheetA || undefined,
        sheetB: sheetB || undefined,
        mappingA: mappingA,
        mappingB: mappingB,
        dateToleranceDays,
        amountTolerance,
      })
      setSessionResponse(response)
    } catch (err: any) {
      setErrorMessage(err.message || 'Difference detection failed. Please review column mappings.')
    } finally {
      setProcessing(false)
    }
  }

  // Handle Review Status Update
  const handleUpdateItemStatus = async (item: ReconciliationItem, status: 'CONFIRMED' | 'REVIEWED' | 'IGNORED') => {
    if (!sessionResponse) return
    const sessionId = sessionResponse.session_id || sessionResponse.id
    const itemId = item.item_id || item.id

    setReviewUpdating(true)
    try {
      await updateItemReviewStatus(sessionId, itemId, status)
      // Update locally
      const updatedTx = (sessionResponse.transactions || sessionResponse.items || []).map((t) => {
        if ((t.item_id || t.id) === itemId) {
          return { ...t, review_status: status }
        }
        return t
      })
      setSessionResponse({
        ...sessionResponse,
        transactions: updatedTx,
        items: updatedTx,
      })
      if (selectedItem && (selectedItem.item_id || selectedItem.id) === itemId) {
        setSelectedItem({ ...selectedItem, review_status: status })
      }
    } catch (err: any) {
      alert(err.message || 'Failed to update review status')
    } finally {
      setReviewUpdating(false)
    }
  }

  // Filter Items
  const items = sessionResponse?.transactions || sessionResponse?.items || []
  const filteredItems = items.filter((item) => {
    // Difference Type Filter
    const diffType = item.difference_type || item.status
    if (activeFilter === 'changed' && diffType !== 'CHANGED_VALUE' && item.status !== 'AMOUNT_MISMATCH' && item.status !== 'DATE_MISMATCH' && item.status !== 'REFERENCE_MISMATCH') {
      return false
    }
    if (activeFilter === 'missing' && diffType !== 'MISSING_ROW' && item.status !== 'MISSING_IN_LEDGER') {
      return false
    }
    if (activeFilter === 'extra' && diffType !== 'EXTRA_ROW' && item.status !== 'MISSING_IN_BANK') {
      return false
    }
    if (activeFilter === 'duplicate' && diffType !== 'DUPLICATE_ENTRY' && item.status !== 'POSSIBLE_DUPLICATE') {
      return false
    }
    if (activeFilter === 'matched' && diffType !== 'MATCHED' && item.status !== 'MATCHED') {
      return false
    }

    // Search Query
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      const desc = (item.description || '').toLowerCase()
      const ref = (item.reference || '').toLowerCase()
      const reason = (item.reason || '').toLowerCase()
      const field = (item.relevant_field || '').toLowerCase()
      return desc.includes(q) || ref.includes(q) || reason.includes(q) || field.includes(q)
    }

    return true
  })

  // Summary Metrics
  const summary = sessionResponse?.summary
  const totalDifferences = summary?.total_discrepancies ?? summary?.unmatched_count ?? 0
  const changedCount = summary?.changed_value_count ?? (summary ? (summary.amount_mismatch_count + summary.date_mismatch_count + summary.reference_mismatch_count) : 0)
  const missingCount = summary?.missing_row_count ?? summary?.missing_in_ledger_count ?? 0
  const extraCount = summary?.extra_row_count ?? summary?.missing_in_bank_count ?? 0
  const duplicateCount = summary?.duplicate_count ?? summary?.possible_duplicate_count ?? 0
  const matchedCount = summary?.matched_records ?? summary?.matched_count ?? 0

  // Difference Type Badge Helper
  const renderDifferenceBadge = (diffType?: DifferenceType | string, status?: string) => {
    const type = diffType || status || 'MATCHED'
    switch (type) {
      case 'CHANGED_VALUE':
      case 'AMOUNT_MISMATCH':
      case 'DATE_MISMATCH':
      case 'REFERENCE_MISMATCH':
        return <Badge variant="warning">Changed Value</Badge>
      case 'MISSING_ROW':
      case 'MISSING_IN_LEDGER':
        return <Badge variant="danger">Missing in B</Badge>
      case 'EXTRA_ROW':
      case 'MISSING_IN_BANK':
        return <Badge variant="info">Extra in B</Badge>
      case 'DUPLICATE_ENTRY':
      case 'POSSIBLE_DUPLICATE':
        return <Badge variant="neutral">Duplicate</Badge>
      case 'UNMATCHED':
        return <Badge variant="danger">Unmatched</Badge>
      case 'MATCHED':
        return <Badge variant="success">Matched</Badge>
      default:
        return <Badge variant="neutral">{type}</Badge>
    }
  }

  // Review Status Badge Helper
  const renderReviewBadge = (reviewStatus?: string) => {
    const s = reviewStatus || 'PENDING_REVIEW'
    switch (s) {
      case 'CONFIRMED':
        return <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-400">Confirmed</span>
      case 'REVIEWED':
        return <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-400">Reviewed</span>
      case 'IGNORED':
        return <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400">Ignored</span>
      default:
        return <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-400">Pending Review</span>
    }
  }

  return (
    <div className="relative min-h-screen bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 pb-16">
      {/* Header */}
      <header className="border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <span className="p-2 rounded-lg bg-indigo-600 text-white shadow-sm">
                  <FileSpreadsheet className="w-5 h-5" />
                </span>
                <div>
                  <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-white">
                    Difference Detection & File Comparison
                  </h1>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Compare any two financial workbooks or sheets, verify discrepancies with exact cell provenance, and download clean reports.
                  </p>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleLoadSampleData}
                disabled={processing}
                className="text-xs"
              >
                Load Sample Files
              </Button>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowConfig(!showConfig)}
                className="text-xs flex items-center gap-1.5"
              >
                <SlidersHorizontal className="w-3.5 h-3.5" />
                Comparison Rules
              </Button>

              {sessionResponse && (
                <a
                  href={getDifferenceReportUrl(sessionResponse.session_id || sessionResponse.id)}
                  download
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition"
                  id="btn-download-difference-report"
                >
                  <Download className="w-3.5 h-3.5" />
                  Download Difference Report (.xlsx)
                </a>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Error Alert */}
        {errorMessage && (
          <div className="p-4 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900 text-rose-800 dark:text-rose-200 text-sm flex items-start justify-between">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
              <span>{errorMessage}</span>
            </div>
            <button onClick={() => setErrorMessage(null)} className="text-rose-500 hover:text-rose-700">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* Collapsible Rules Config */}
        {showConfig && (
          <Card className="p-4 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">Matching Sensitivity</h3>
                <p className="text-xs text-slate-500">Fine-tune tolerance thresholds when identifying matching records.</p>
              </div>

              <div className="flex flex-wrap items-center gap-6">
                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Date Tolerance:</label>
                  <select
                    value={dateToleranceDays}
                    onChange={(e) => setDateToleranceDays(Number(e.target.value))}
                    className="text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
                  >
                    <option value={0}>Exact Date (0 days)</option>
                    <option value={1}>±1 Day Tolerance</option>
                    <option value={2}>±2 Days Tolerance</option>
                    <option value={3}>±3 Days Tolerance</option>
                  </select>
                </div>

                <div className="flex items-center gap-2">
                  <label className="text-xs font-medium text-slate-600 dark:text-slate-300">Amount Tolerance:</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={amountTolerance}
                    onChange={(e) => setAmountTolerance(Number(e.target.value))}
                    className="w-20 text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
                    placeholder="0.00"
                  />
                  <span className="text-xs text-slate-400">₹</span>
                </div>
              </div>
            </div>
          </Card>
        )}

        {/* File Input & Column Mapping Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Source File A */}
          <Card className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-400 flex items-center justify-center font-bold text-xs">
                    A
                  </span>
                  <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Source File A (Primary)</h2>
                </div>
                {previewA && (
                  <Badge variant="neutral" className="text-xs">
                    {previewA.total_rows} records
                  </Badge>
                )}
              </div>

              {/* Upload Input */}
              <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-lg p-4 text-center hover:border-indigo-400 dark:hover:border-indigo-600 transition bg-slate-50/50 dark:bg-slate-950/50">
                <input
                  type="file"
                  id="file-a-input"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileAChange}
                  className="hidden"
                />
                <label htmlFor="file-a-input" className="cursor-pointer block">
                  <UploadCloud className="w-6 h-6 mx-auto mb-1 text-slate-400" />
                  <span className="text-xs font-medium text-indigo-600 dark:text-indigo-400">
                    {fileA ? fileA.name : 'Choose primary Excel or CSV file'}
                  </span>
                  <p className="text-[11px] text-slate-400 mt-0.5">Supports XLSX, XLS, and CSV</p>
                </label>
              </div>

              {/* Sheet Selector (Multi-Sheet Excel) */}
              {previewA?.sheet_names && previewA.sheet_names.length > 1 && (
                <div className="flex items-center justify-between text-xs pt-1">
                  <span className="text-slate-500 font-medium">Active Sheet:</span>
                  <select
                    value={sheetA}
                    onChange={(e) => handleSheetAChange(e.target.value)}
                    className="text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
                  >
                    {previewA.sheet_names.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Ambiguity Alert */}
              {previewA?.is_ambiguous && (
                <div className="p-3 rounded-md bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs">
                  <div className="flex items-start gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Ambiguous Columns Detected</p>
                      <p className="text-[11px] mt-0.5">{previewA.ambiguity_reason}</p>
                      <p className="text-[11px] mt-1 text-amber-700 dark:text-amber-300">
                        Please review and confirm column mappings below.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Editable Column Mappings */}
              {previewA && (
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-2">
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">Column Mapping Preview</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <label className="text-[11px] text-slate-500">Date Column</label>
                      <select
                        value={mappingA.date}
                        onChange={(e) => setMappingA({ ...mappingA, date: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewA.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Voucher / Reference</label>
                      <select
                        value={mappingA.reference}
                        onChange={(e) => setMappingA({ ...mappingA, reference: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewA.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Description / Narration</label>
                      <select
                        value={mappingA.description}
                        onChange={(e) => setMappingA({ ...mappingA, description: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewA.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Amount Column</label>
                      <select
                        value={mappingA.amount}
                        onChange={(e) => setMappingA({ ...mappingA, amount: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewA.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>

          {/* Source File B */}
          <Card className="p-5 border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm flex flex-col justify-between">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-6 h-6 rounded-full bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-400 flex items-center justify-center font-bold text-xs">
                    B
                  </span>
                  <h2 className="text-sm font-semibold text-slate-900 dark:text-white">Source File B (Comparison)</h2>
                </div>
                {previewB && (
                  <Badge variant="neutral" className="text-xs">
                    {previewB.total_rows} records
                  </Badge>
                )}
              </div>

              {/* Upload Input */}
              <div className="border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-lg p-4 text-center hover:border-blue-400 dark:hover:border-blue-600 transition bg-slate-50/50 dark:bg-slate-950/50">
                <input
                  type="file"
                  id="file-b-input"
                  accept=".xlsx,.xls,.csv"
                  onChange={handleFileBChange}
                  className="hidden"
                />
                <label htmlFor="file-b-input" className="cursor-pointer block">
                  <UploadCloud className="w-6 h-6 mx-auto mb-1 text-slate-400" />
                  <span className="text-xs font-medium text-blue-600 dark:text-blue-400">
                    {fileB ? fileB.name : 'Choose comparison Excel or CSV file'}
                  </span>
                  <p className="text-[11px] text-slate-400 mt-0.5">Supports XLSX, XLS, and CSV</p>
                </label>
              </div>

              {/* Sheet Selector (Multi-Sheet Excel) */}
              {previewB?.sheet_names && previewB.sheet_names.length > 1 && (
                <div className="flex items-center justify-between text-xs pt-1">
                  <span className="text-slate-500 font-medium">Active Sheet:</span>
                  <select
                    value={sheetB}
                    onChange={(e) => handleSheetBChange(e.target.value)}
                    className="text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1"
                  >
                    {previewB.sheet_names.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Ambiguity Alert */}
              {previewB?.is_ambiguous && (
                <div className="p-3 rounded-md bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs">
                  <div className="flex items-start gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold">Ambiguous Columns Detected</p>
                      <p className="text-[11px] mt-0.5">{previewB.ambiguity_reason}</p>
                      <p className="text-[11px] mt-1 text-amber-700 dark:text-amber-300">
                        Please review and confirm column mappings below.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Editable Column Mappings */}
              {previewB && (
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800 space-y-2">
                  <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">Column Mapping Preview</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <label className="text-[11px] text-slate-500">Date Column</label>
                      <select
                        value={mappingB.date}
                        onChange={(e) => setMappingB({ ...mappingB, date: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewB.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Voucher / Reference</label>
                      <select
                        value={mappingB.reference}
                        onChange={(e) => setMappingB({ ...mappingB, reference: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewB.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Description / Narration</label>
                      <select
                        value={mappingB.description}
                        onChange={(e) => setMappingB({ ...mappingB, description: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewB.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] text-slate-500">Amount Column</label>
                      <select
                        value={mappingB.amount}
                        onChange={(e) => setMappingB({ ...mappingB, amount: e.target.value })}
                        className="w-full text-xs rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 px-2 py-1 mt-0.5"
                      >
                        <option value="">-- None --</option>
                        {previewB.detected_columns.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* Action Button */}
        <div className="flex justify-center pt-2">
          <Button
            size="lg"
            onClick={handleRunDifferenceDetection}
            disabled={!fileA || !fileB || processing}
            className="w-full sm:w-auto px-8 py-3 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg shadow-md transition flex items-center justify-center gap-2"
            id="btn-detect-differences"
          >
            {processing ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                Analyzing & Detecting Differences...
              </>
            ) : (
              <>
                <FileCheck className="w-4 h-4" />
                Detect Differences Between Files
              </>
            )}
          </Button>
        </div>

        {/* Results Workspace */}
        {sessionResponse && (
          <div className="space-y-6 pt-6 border-t border-slate-200 dark:border-slate-800">
            {/* Summary Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
              <div className="p-3.5 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
                <span className="text-[11px] font-medium text-slate-500 block">Total Differences</span>
                <span className="text-xl font-bold text-slate-900 dark:text-white mt-1 block">
                  {totalDifferences}
                </span>
              </div>

              <div className="p-3.5 rounded-lg border border-amber-200 dark:border-amber-900/50 bg-amber-50/50 dark:bg-amber-950/20 shadow-sm">
                <span className="text-[11px] font-medium text-amber-700 dark:text-amber-400 block">Changed Values</span>
                <span className="text-xl font-bold text-amber-900 dark:text-amber-300 mt-1 block">
                  {changedCount}
                </span>
              </div>

              <div className="p-3.5 rounded-lg border border-rose-200 dark:border-rose-900/50 bg-rose-50/50 dark:bg-rose-950/20 shadow-sm">
                <span className="text-[11px] font-medium text-rose-700 dark:text-rose-400 block">Missing in B</span>
                <span className="text-xl font-bold text-rose-900 dark:text-rose-300 mt-1 block">
                  {missingCount}
                </span>
              </div>

              <div className="p-3.5 rounded-lg border border-blue-200 dark:border-blue-900/50 bg-blue-50/50 dark:bg-blue-950/20 shadow-sm">
                <span className="text-[11px] font-medium text-blue-700 dark:text-blue-400 block">Extra in B</span>
                <span className="text-xl font-bold text-blue-900 dark:text-blue-300 mt-1 block">
                  {extraCount}
                </span>
              </div>

              <div className="p-3.5 rounded-lg border border-purple-200 dark:border-purple-900/50 bg-purple-50/50 dark:bg-purple-950/20 shadow-sm">
                <span className="text-[11px] font-medium text-purple-700 dark:text-purple-400 block">Duplicates</span>
                <span className="text-xl font-bold text-purple-900 dark:text-purple-300 mt-1 block">
                  {duplicateCount}
                </span>
              </div>

              <div className="p-3.5 rounded-lg border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/50 dark:bg-emerald-950/20 shadow-sm">
                <span className="text-[11px] font-medium text-emerald-700 dark:text-emerald-400 block">Matched Records</span>
                <span className="text-xl font-bold text-emerald-900 dark:text-emerald-300 mt-1 block">
                  {matchedCount}
                </span>
              </div>
            </div>

            {/* Controls Bar */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-white dark:bg-slate-900 p-3 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
              {/* Filter Tabs */}
              <div className="flex items-center gap-1 overflow-x-auto pb-1 sm:pb-0">
                <button
                  onClick={() => setActiveFilter('all')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'all' ? 'bg-indigo-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  All ({items.length})
                </button>
                <button
                  onClick={() => setActiveFilter('changed')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'changed' ? 'bg-amber-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  Changed ({changedCount})
                </button>
                <button
                  onClick={() => setActiveFilter('missing')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'missing' ? 'bg-rose-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  Missing ({missingCount})
                </button>
                <button
                  onClick={() => setActiveFilter('extra')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'extra' ? 'bg-blue-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  Extra ({extraCount})
                </button>
                <button
                  onClick={() => setActiveFilter('duplicate')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'duplicate' ? 'bg-purple-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  Duplicates ({duplicateCount})
                </button>
                <button
                  onClick={() => setActiveFilter('matched')}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition ${activeFilter === 'matched' ? 'bg-emerald-600 text-white' : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800'}`}
                >
                  Matched ({matchedCount})
                </button>
              </div>

              {/* Search & Status-Only Toggle */}
              <div className="flex items-center gap-3">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 absolute left-2.5 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search differences..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-8 pr-3 py-1 text-xs rounded-md border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-white w-48 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                  />
                </div>

                <label className="flex items-center gap-1.5 cursor-pointer select-none text-xs text-slate-600 dark:text-slate-400">
                  <input
                    type="checkbox"
                    checked={statusOnlyMode}
                    onChange={(e) => setStatusOnlyMode(e.target.checked)}
                    className="rounded text-indigo-600 focus:ring-indigo-500 w-3.5 h-3.5"
                  />
                  <span>Status-Only View</span>
                </label>
              </div>
            </div>

            {/* Differences Table */}
            <Card className="overflow-hidden border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 dark:border-slate-800 bg-slate-50/75 dark:bg-slate-950/75 text-slate-500 uppercase tracking-wider font-semibold">
                      <th className="py-2.5 px-3">Status / Type</th>
                      <th className="py-2.5 px-3">Voucher / Identifier</th>
                      <th className="py-2.5 px-3">Description</th>
                      <th className="py-2.5 px-3">Location (File A & B)</th>
                      {!statusOnlyMode && <th className="py-2.5 px-3">Source Values</th>}
                      {!statusOnlyMode && <th className="py-2.5 px-3 text-right">Variance</th>}
                      <th className="py-2.5 px-3">Review</th>
                      <th className="py-2.5 px-3 text-center">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {filteredItems.length === 0 ? (
                      <tr>
                        <td colSpan={statusOnlyMode ? 6 : 8} className="py-8 text-center text-slate-400">
                          No differences match the current filter.
                        </td>
                      </tr>
                    ) : (
                      filteredItems.map((item, idx) => {
                        const isSelected = selectedItem && (selectedItem.item_id || selectedItem.id) === (item.item_id || item.id)
                        const locA = item.source_a_location
                        const locB = item.source_b_location

                        return (
                          <tr
                            key={item.item_id || item.id || idx}
                            onClick={() => setSelectedItem(item)}
                            className={`cursor-pointer transition hover:bg-indigo-50/40 dark:hover:bg-indigo-950/20 ${isSelected ? 'bg-indigo-50 dark:bg-indigo-950/40' : ''}`}
                          >
                            <td className="py-2.5 px-3">
                              {renderDifferenceBadge(item.difference_type, item.status)}
                            </td>

                            <td className="py-2.5 px-3 font-mono font-medium text-slate-800 dark:text-slate-200">
                              {item.reference || '—'}
                            </td>

                            <td className="py-2.5 px-3 max-w-xs truncate text-slate-700 dark:text-slate-300" title={item.description}>
                              {item.description || '—'}
                            </td>

                            <td className="py-2.5 px-3 text-[11px] text-slate-500">
                              <div>
                                {locA?.row_number ? (
                                  <span className="font-mono text-indigo-600 dark:text-indigo-400">
                                    A: R{locA.row_number}{locA.cell_address ? ` (${locA.cell_address})` : ''}
                                  </span>
                                ) : (
                                  <span className="text-slate-400">A: —</span>
                                )}
                              </div>
                              <div>
                                {locB?.row_number ? (
                                  <span className="font-mono text-blue-600 dark:text-blue-400">
                                    B: R{locB.row_number}{locB.cell_address ? ` (${locB.cell_address})` : ''}
                                  </span>
                                ) : (
                                  <span className="text-slate-400">B: —</span>
                                )}
                              </div>
                            </td>

                            {!statusOnlyMode && (
                              <td className="py-2.5 px-3 text-[11px] text-slate-600 dark:text-slate-300">
                                <div>A: {item.bank_amount !== null && item.bank_amount !== undefined ? formatINR(item.bank_amount) : (item.source_a_value !== null && item.source_a_value !== undefined ? String(item.source_a_value) : '—')}</div>
                                <div>B: {item.ledger_amount !== null && item.ledger_amount !== undefined ? formatINR(item.ledger_amount) : (item.source_b_value !== null && item.source_b_value !== undefined ? String(item.source_b_value) : '—')}</div>
                              </td>
                            )}

                            {!statusOnlyMode && (
                              <td className="py-2.5 px-3 text-right font-medium text-slate-900 dark:text-white">
                                {item.difference !== 0 ? formatINR(Math.abs(item.difference)) : '—'}
                              </td>
                            )}

                            <td className="py-2.5 px-3">
                              {renderReviewBadge(item.review_status)}
                            </td>

                            <td className="py-2.5 px-3 text-center">
                              <button
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setSelectedItem(item)
                                }}
                                className="p-1 rounded text-slate-400 hover:text-indigo-600 dark:hover:text-indigo-400"
                                title="Inspect Difference in Drawer"
                              >
                                <Eye className="w-4 h-4" />
                              </button>
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        )}
      </main>

      {/* Compact Right-Side Drawer */}
      {selectedItem && (
        <aside
          className="fixed top-0 right-0 bottom-0 w-96 max-w-full bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl z-50 p-6 flex flex-col justify-between overflow-y-auto animate-in slide-in-from-right duration-200"
          id="difference-detail-drawer"
        >
          <div className="space-y-5">
            {/* Drawer Header */}
            <div className="flex items-start justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
              <div>
                <span className="text-[10px] uppercase font-bold tracking-wider text-slate-400 block mb-1">
                  Difference Details
                </span>
                <div className="flex items-center gap-2">
                  {renderDifferenceBadge(selectedItem.difference_type, selectedItem.status)}
                  {renderReviewBadge(selectedItem.review_status)}
                </div>
              </div>
              <button
                onClick={() => setSelectedItem(null)}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Reason & Explanation */}
            <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1">
              <span className="text-[11px] font-semibold text-slate-700 dark:text-slate-300 block">
                Reason for Difference
              </span>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                {selectedItem.reason || 'No detailed reason provided.'}
              </p>
            </div>

            {/* Exact Provenance / Location */}
            <div className="space-y-3">
              <span className="text-[11px] font-semibold uppercase text-slate-400 tracking-wider block">
                Source Provenance
              </span>

              {/* Source A Location */}
              <div className="p-2.5 rounded border border-indigo-100 dark:border-indigo-950/60 bg-indigo-50/40 dark:bg-indigo-950/20 text-xs">
                <span className="font-semibold text-indigo-700 dark:text-indigo-400 block">Source File A</span>
                <p className="text-slate-600 dark:text-slate-300 mt-0.5 truncate">
                  {selectedItem.source_a_location?.file_name || fileA?.name || 'File A'}
                </p>
                <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-500 font-mono">
                  <span>Sheet: {selectedItem.source_a_location?.sheet_name || sheetA || 'Sheet1'}</span>
                  <span>Row: {selectedItem.source_a_location?.row_number ?? '—'}</span>
                  <span>Cell: {selectedItem.source_a_location?.cell_address ?? '—'}</span>
                </div>
              </div>

              {/* Source B Location */}
              <div className="p-2.5 rounded border border-blue-100 dark:border-blue-950/60 bg-blue-50/40 dark:bg-blue-950/20 text-xs">
                <span className="font-semibold text-blue-700 dark:text-blue-400 block">Source File B</span>
                <p className="text-slate-600 dark:text-slate-300 mt-0.5 truncate">
                  {selectedItem.source_b_location?.file_name || fileB?.name || 'File B'}
                </p>
                <div className="flex items-center gap-3 mt-1.5 text-[11px] text-slate-500 font-mono">
                  <span>Sheet: {selectedItem.source_b_location?.sheet_name || sheetB || 'Sheet1'}</span>
                  <span>Row: {selectedItem.source_b_location?.row_number ?? '—'}</span>
                  <span>Cell: {selectedItem.source_b_location?.cell_address ?? '—'}</span>
                </div>
              </div>
            </div>

            {/* Field & Value Comparison */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold uppercase text-slate-400 tracking-wider block">
                Compared Values
              </span>

              <div className="space-y-1.5 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">Relevant Field:</span>
                  <span className="font-medium text-slate-900 dark:text-white capitalize">
                    {selectedItem.relevant_field || 'Amount / Record'}
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">File A Value:</span>
                  <span className="font-mono text-slate-900 dark:text-white">
                    {selectedItem.bank_amount !== null && selectedItem.bank_amount !== undefined
                      ? formatINR(selectedItem.bank_amount)
                      : (selectedItem.source_a_value !== null && selectedItem.source_a_value !== undefined ? String(selectedItem.source_a_value) : '—')}
                  </span>
                </div>

                <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                  <span className="text-slate-500">File B Value:</span>
                  <span className="font-mono text-slate-900 dark:text-white">
                    {selectedItem.ledger_amount !== null && selectedItem.ledger_amount !== undefined
                      ? formatINR(selectedItem.ledger_amount)
                      : (selectedItem.source_b_value !== null && selectedItem.source_b_value !== undefined ? String(selectedItem.source_b_value) : '—')}
                  </span>
                </div>

                {selectedItem.difference !== 0 && (
                  <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                    <span className="text-slate-500">Difference / Variance:</span>
                    <span className="font-mono font-semibold text-rose-600 dark:text-rose-400">
                      {formatINR(Math.abs(selectedItem.difference))}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Raw Row Entries */}
            {(selectedItem.source_a_entry || selectedItem.source_b_entry) && (
              <div className="space-y-2">
                <span className="text-[11px] font-semibold uppercase text-slate-400 tracking-wider block">
                  Raw Source Record
                </span>
                <div className="max-h-40 overflow-y-auto text-[10px] font-mono p-2 rounded bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 space-y-1">
                  {selectedItem.source_a_entry && (
                    <div>
                      <span className="font-bold text-indigo-600">File A: </span>
                      {JSON.stringify(selectedItem.source_a_entry)}
                    </div>
                  )}
                  {selectedItem.source_b_entry && (
                    <div className="mt-1">
                      <span className="font-bold text-blue-600">File B: </span>
                      {JSON.stringify(selectedItem.source_b_entry)}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Review Actions in Drawer Footer */}
          <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-2">
            <span className="text-[11px] font-medium text-slate-500 block mb-1">
              Accountant Review Action:
            </span>
            <div className="grid grid-cols-3 gap-1.5">
              <Button
                variant={selectedItem.review_status === 'CONFIRMED' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => handleUpdateItemStatus(selectedItem, 'CONFIRMED')}
                disabled={reviewUpdating}
                className="text-xs justify-center"
              >
                Confirm
              </Button>
              <Button
                variant={selectedItem.review_status === 'REVIEWED' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => handleUpdateItemStatus(selectedItem, 'REVIEWED')}
                disabled={reviewUpdating}
                className="text-xs justify-center"
              >
                Reviewed
              </Button>
              <Button
                variant={selectedItem.review_status === 'IGNORED' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => handleUpdateItemStatus(selectedItem, 'IGNORED')}
                disabled={reviewUpdating}
                className="text-xs justify-center"
              >
                Ignore
              </Button>
            </div>
          </div>
        </aside>
      )}
    </div>
  )
}
