import React, { useState, useEffect, useMemo } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Search,
  RefreshCw,
  FileSpreadsheet,
  ChevronRight,
  Info,
  ShieldCheck,
  Filter,
} from 'lucide-react'
import type { ReviewFindingItem, ReviewCenterSummary } from '../types'
import { getReviewCenterFindings } from '../services/api'
import { formatINR } from '../utils/formatters'
import { FindingDetailDrawer } from '../components/review/FindingDetailDrawer'
import { Button } from '../components/ui/Button'

export const ReviewCenter: React.FC = () => {
  const [data, setData] = useState<ReviewCenterSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  // Filters
  const [activeSeverity, setActiveSeverity] = useState<string>('ALL')
  const [activeStatus, setActiveStatus] = useState<string>('ALL')
  const [selectedDoc, setSelectedDoc] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  // Selected finding for Drawer
  const [selectedFinding, setSelectedFinding] = useState<ReviewFindingItem | null>(null)
  const [viewMode, setViewMode] = useState<'cards' | 'table'>('cards')

  const loadFindings = async () => {
    setIsLoading(true)
    setErrorMessage(null)
    try {
      const summary = await getReviewCenterFindings({
        severity: activeSeverity !== 'ALL' ? activeSeverity : undefined,
        status: activeStatus !== 'ALL' ? activeStatus : undefined,
        search: searchQuery ? searchQuery : undefined,
      })
      setData(summary)
    } catch (err: any) {
      setErrorMessage(err.message || 'Unable to load findings. Please try again.')
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadFindings()
    const handleReset = () => {
      loadFindings()
    }
    window.addEventListener('workspace:documents_reset', handleReset)
    return () => window.removeEventListener('workspace:documents_reset', handleReset)
  }, [activeSeverity, activeStatus])

  // Filtered findings on client side for immediate responsiveness
  const filteredFindings = useMemo(() => {
    if (!data?.findings) return []
    return data.findings.filter((f) => {
      if (selectedDoc !== 'ALL' && f.document_name !== selectedDoc) {
        return false
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase().trim()
        const matches =
          f.title.toLowerCase().includes(q) ||
          f.document_name.toLowerCase().includes(q) ||
          (f.description && f.description.toLowerCase().includes(q)) ||
          (f.cell_address && f.cell_address.toLowerCase().includes(q)) ||
          (f.financial_period && f.financial_period.toLowerCase().includes(q)) ||
          (f.difference !== null && f.difference !== undefined && f.difference.toString().includes(q))
        if (!matches) return false
      }
      return true
    })
  }, [data, selectedDoc, searchQuery])

  // Unique documents for filter dropdown
  const uniqueDocuments = useMemo(() => {
    if (!data?.findings) return []
    const set = new Set<string>()
    data.findings.forEach((f) => {
      if (f.document_name) set.add(f.document_name)
    })
    return Array.from(set)
  }, [data])

  const handleFindingUpdated = (updated: ReviewFindingItem) => {
    setData((prev) => {
      if (!prev) return prev
      return {
        ...prev,
        findings: prev.findings.map((f) => (f.id === updated.id ? updated : f)),
      }
    })
    setSelectedFinding(updated)
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-extrabold bg-rose-100 text-rose-800 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
            CRITICAL
          </span>
        )
      case 'HIGH':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3 h-3 text-rose-600" />
            HIGH
          </span>
        )
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3 h-3 text-amber-600" />
            MEDIUM
          </span>
        )
      case 'LOW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200">
            LOW
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-medium bg-slate-100 text-slate-700">
            {severity}
          </span>
        )
    }
  }

  const getStatusBadge = (status: string) => {
    switch (status.toUpperCase()) {
      case 'APPROVED':
      case 'CONFIRMED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Approved
          </span>
        )
      case 'REVIEW_REQUIRED':
      case 'NEEDS_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3 h-3 text-amber-600" />
            Needs Review
          </span>
        )
      case 'UNDER_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-sky-50 text-sky-800 border border-sky-200">
            <Clock className="w-3 h-3 text-sky-600" />
            Under Review
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            Rejected
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">
            {status}
          </span>
        )
    }
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Top Header Card */}
      <div className="glass-panel p-6 sm:p-7 flex flex-col md:flex-row md:items-center justify-between gap-4 border border-white/90">
        <div>
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200/60 mb-2">
            <ShieldCheck className="w-3.5 h-3.5 text-brand-500" />
            <span>Forensic Accounting Audit</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            Review Center
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Review financial findings before taking action. Every anomaly is backed by deterministic cell provenance.
          </p>
        </div>

        <Button
          variant="secondary"
          size="sm"
          icon={<RefreshCw className="w-3.5 h-3.5" />}
          onClick={loadFindings}
          isLoading={isLoading}
        >
          Refresh Findings
        </Button>
      </div>

      {/* Summary Cards: Critical, High, Medium, Low */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
        <div
          onClick={() => setActiveSeverity('CRITICAL')}
          className={`glass-card p-4 sm:p-5 cursor-pointer transition-all ${
            activeSeverity === 'CRITICAL'
              ? 'ring-2 ring-rose-500 bg-rose-50/60'
              : 'hover:border-rose-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-rose-700">
              Critical
            </span>
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-pulse" />
          </div>
          <span className="text-2xl sm:text-3xl font-extrabold text-rose-700 mt-2 block font-sans">
            {data?.severity_breakdown?.CRITICAL ?? 0}
          </span>
          <span className="text-[10px] sm:text-[11px] text-rose-600/80 mt-0.5 block">
            Severe variances
          </span>
        </div>

        <div
          onClick={() => setActiveSeverity('HIGH')}
          className={`glass-card p-4 sm:p-5 cursor-pointer transition-all ${
            activeSeverity === 'HIGH'
              ? 'ring-2 ring-rose-400 bg-rose-50/50'
              : 'hover:border-rose-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-rose-700">
              High
            </span>
            <AlertTriangle className="w-3.5 h-3.5 text-rose-500" />
          </div>
          <span className="text-2xl sm:text-3xl font-extrabold text-rose-700 mt-2 block font-sans">
            {data?.severity_breakdown?.HIGH ?? 0}
          </span>
          <span className="text-[10px] sm:text-[11px] text-rose-600/80 mt-0.5 block">
            Discrepancies
          </span>
        </div>

        <div
          onClick={() => setActiveSeverity('MEDIUM')}
          className={`glass-card p-4 sm:p-5 cursor-pointer transition-all ${
            activeSeverity === 'MEDIUM'
              ? 'ring-2 ring-amber-400 bg-amber-50/50'
              : 'hover:border-amber-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-amber-700">
              Medium
            </span>
            <AlertTriangle className="w-3.5 h-3.5 text-amber-500" />
          </div>
          <span className="text-2xl sm:text-3xl font-extrabold text-amber-700 mt-2 block font-sans">
            {data?.severity_breakdown?.MEDIUM ?? 0}
          </span>
          <span className="text-[10px] sm:text-[11px] text-amber-600/80 mt-0.5 block">
            Classification issues
          </span>
        </div>

        <div
          onClick={() => setActiveSeverity('LOW')}
          className={`glass-card p-4 sm:p-5 cursor-pointer transition-all ${
            activeSeverity === 'LOW'
              ? 'ring-2 ring-slate-400 bg-slate-50/70'
              : 'hover:border-slate-300'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-[10px] sm:text-xs font-bold uppercase tracking-wider text-slate-600">
              Low
            </span>
            <Info className="w-3.5 h-3.5 text-slate-400" />
          </div>
          <span className="text-2xl sm:text-3xl font-extrabold text-slate-800 mt-2 block font-sans">
            {data?.severity_breakdown?.LOW ?? 0}
          </span>
          <span className="text-[10px] sm:text-[11px] text-slate-500 mt-0.5 block">
            Informational notes
          </span>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="glass-card p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex-1 relative">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search findings by title, document, cell address, or amount..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 glass-input text-xs sm:text-sm text-slate-800 placeholder-slate-400 font-sans"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Severity selector */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-400 text-[11px] font-medium hidden sm:inline">Severity:</span>
            <select
              value={activeSeverity}
              onChange={(e) => setActiveSeverity(e.target.value)}
              className="glass-input px-2.5 py-1.5 text-xs text-slate-700 font-semibold cursor-pointer"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>

          {/* Status selector */}
          <div className="flex items-center gap-1 text-xs">
            <span className="text-slate-400 text-[11px] font-medium hidden sm:inline">Status:</span>
            <select
              value={activeStatus}
              onChange={(e) => setActiveStatus(e.target.value)}
              className="glass-input px-2.5 py-1.5 text-xs text-slate-700 font-semibold cursor-pointer"
            >
              <option value="ALL">All Statuses</option>
              <option value="NEEDS_REVIEW">Needs Review</option>
              <option value="APPROVED">Approved</option>
              <option value="UNDER_REVIEW">Under Review</option>
              <option value="REJECTED">Rejected</option>
            </select>
          </div>

          {/* Document selector */}
          {uniqueDocuments.length > 0 && (
            <div className="flex items-center gap-1 text-xs">
              <span className="text-slate-400 text-[11px] font-medium hidden sm:inline">Doc:</span>
              <select
                value={selectedDoc}
                onChange={(e) => setSelectedDoc(e.target.value)}
                className="glass-input px-2.5 py-1.5 text-xs text-slate-700 font-semibold cursor-pointer max-w-[140px] truncate"
              >
                <option value="ALL">All Documents</option>
                {uniqueDocuments.map((doc) => (
                  <option key={doc} value={doc}>
                    {doc}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* View mode toggle */}
          <div className="flex items-center bg-white/70 p-0.5 rounded-xl border border-slate-200/80 shadow-2xs">
            <button
              type="button"
              onClick={() => setViewMode('cards')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                viewMode === 'cards'
                  ? 'bg-pink-50 text-pink-700 font-bold shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Cards
            </button>
            <button
              type="button"
              onClick={() => setViewMode('table')}
              className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-colors cursor-pointer ${
                viewMode === 'table'
                  ? 'bg-pink-50 text-pink-700 font-bold shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Table
            </button>
          </div>
        </div>
      </div>

      {/* Main Findings Display: Elegant Glass Cards or Dense Table */}
      {isLoading ? (
        <div className="p-12 text-center text-slate-400 text-xs glass-card">
          <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-brand-500" />
          <p className="font-semibold text-slate-700">Loading audit findings...</p>
        </div>
      ) : filteredFindings.length === 0 ? (
        <div className="p-12 text-center text-slate-400 text-xs glass-card border-dashed border-slate-200">
          <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
          <p className="font-bold text-slate-800 text-sm">No findings match the current filters</p>
          <p className="mt-1 text-slate-500">Try adjusting your severity, status, or search query.</p>
        </div>
      ) : viewMode === 'cards' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredFindings.map((finding) => (
            <div
              key={finding.id}
              onClick={() => setSelectedFinding(finding)}
              className="glass-card glass-card-hover p-5 cursor-pointer flex flex-col justify-between group border border-white/90"
            >
              <div>
                {/* Header row: Severity & Status */}
                <div className="flex items-center justify-between gap-2 mb-2.5">
                  <div className="flex items-center gap-1.5">
                    {getSeverityBadge(finding.severity)}
                    <span className="text-[10px] font-mono text-slate-500 bg-white/70 px-2 py-0.5 rounded-md border border-slate-200/60">
                      {finding.cell_address ? `Cell ${finding.cell_address}` : finding.finding_type}
                    </span>
                  </div>
                  {getStatusBadge(finding.status)}
                </div>

                {/* Finding Title & Explanation */}
                <h3 className="text-sm font-bold text-slate-900 group-hover:text-brand-700 transition-colors line-clamp-1 font-sans">
                  {finding.title}
                </h3>
                <p className="text-xs text-slate-500 mt-1 line-clamp-2 leading-relaxed">
                  {finding.description || 'Forensic ledger discrepancy detected.'}
                </p>

                {/* Source information */}
                <div className="flex items-center gap-1.5 mt-3 text-xs text-slate-500 bg-white/50 p-2 rounded-xl border border-slate-100/80">
                  <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                  <span className="truncate font-medium">{finding.document_name}</span>
                  {finding.sheet_name && (
                    <span className="text-[10px] text-slate-400 shrink-0">({finding.sheet_name})</span>
                  )}
                </div>
              </div>

              {/* Bottom footer: Variance & View Details button */}
              <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                <div>
                  <span className="text-[10px] text-slate-400 block font-medium">Variance / Difference</span>
                  <span className="text-xs font-bold text-rose-700 font-mono">
                    {finding.difference !== null && finding.difference !== undefined && finding.difference > 0
                      ? formatINR(finding.difference)
                      : finding.actual_value
                      ? formatINR(finding.actual_value)
                      : 'Discrepancy'}
                  </span>
                </div>

                <Button
                  size="sm"
                  variant="outline"
                  icon={<ChevronRight className="w-3.5 h-3.5" />}
                  onClick={(e) => {
                    e.stopPropagation()
                    setSelectedFinding(finding)
                  }}
                >
                  View Details
                </Button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="glass-table-container">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="bg-white/90 border-b border-slate-200/80 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4">Finding & Provenance</th>
                  <th className="py-3 px-4">Document</th>
                  <th className="py-3 px-4 text-right">Actual Value</th>
                  <th className="py-3 px-4 text-right">Difference</th>
                  <th className="py-3 px-4 text-center">Severity</th>
                  <th className="py-3 px-4 text-center">Confidence</th>
                  <th className="py-3 px-4 text-center">Status</th>
                  <th className="py-3 px-4 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100/80 bg-white/40">
                {filteredFindings.map((finding) => (
                  <tr
                    key={finding.id}
                    onClick={() => setSelectedFinding(finding)}
                    className="hover:bg-pink-50/40 transition-colors cursor-pointer group"
                  >
                    <td className="py-3 px-4 min-w-[200px]">
                      <span className="font-bold text-slate-900 group-hover:text-brand-700 transition-colors block">
                        {finding.title}
                      </span>
                      <span className="text-[10px] font-mono text-slate-400 block mt-0.5">
                        {finding.cell_address ? `Cell ${finding.cell_address}` : finding.finding_type}
                        {finding.sheet_name ? ` • Sheet: ${finding.sheet_name}` : ''}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-slate-600 max-w-[160px] truncate">
                      <div className="flex items-center gap-1.5 truncate">
                        <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                        <span className="truncate">{finding.document_name}</span>
                      </div>
                    </td>

                    <td className="py-3 px-4 text-right font-mono font-semibold text-slate-800">
                      {finding.actual_value !== null && finding.actual_value !== undefined
                        ? formatINR(finding.actual_value)
                        : '—'}
                    </td>

                    <td className="py-3 px-4 text-right font-mono font-bold text-rose-700">
                      {finding.difference !== null && finding.difference !== undefined && finding.difference > 0
                        ? formatINR(finding.difference)
                        : '—'}
                    </td>

                    <td className="py-3 px-4 text-center">
                      {getSeverityBadge(finding.severity)}
                    </td>

                    <td className="py-3 px-4 text-center">
                      <span className="text-[10px] font-semibold text-slate-500 bg-white/80 px-2 py-0.5 rounded-full border border-slate-200">
                        {finding.confidence}
                      </span>
                    </td>

                    <td className="py-3 px-4 text-center">
                      {getStatusBadge(finding.status)}
                    </td>

                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          setSelectedFinding(finding)
                        }}
                        className="inline-flex items-center gap-1 text-xs font-bold text-brand-600 hover:text-brand-800 group-hover:translate-x-0.5 transition-all p-1 cursor-pointer"
                      >
                        Inspect <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Slide-out Finding Detail Drawer */}
      <FindingDetailDrawer
        finding={selectedFinding}
        onClose={() => setSelectedFinding(null)}
        onFindingUpdated={handleFindingUpdated}
      />
    </div>
  )
}
