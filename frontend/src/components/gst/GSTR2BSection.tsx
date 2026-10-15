import React, { useState } from 'react'
import {
  Play,
  Upload,
  Search,
  CheckCircle2,
  XCircle,
  Eye,
  Download,
} from 'lucide-react'
import type {
  GSTReconciliationResult,
  ReconciliationSummary,
  GSTMatchStatus,
  ReconciliationDecision,
} from '../../types/gst'
import { formatINR } from '../../utils/formatters'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'

interface GSTR2BSectionProps {
  summary: ReconciliationSummary | null
  results: GSTReconciliationResult[]
  isLocked: boolean
  isReconciling: boolean
  onRunReconciliation: () => void
  onImportGSTR2BClick: () => void
  onSelectResult: (result: GSTReconciliationResult) => void
  onQuickDecision: (resultId: string | number, decision: ReconciliationDecision) => void
  onExportClick?: () => void
}

export const GSTR2BSection: React.FC<GSTR2BSectionProps> = ({
  summary,
  results,
  isLocked,
  isReconciling,
  onRunReconciliation,
  onImportGSTR2BClick,
  onSelectResult,
  onQuickDecision,
  onExportClick,
}) => {
  const [activeTab, setActiveTab] = useState<string>('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredResults = results.filter((res) => {
    if (activeTab === 'EXACT_MATCH' && res.match_status !== 'EXACT_MATCH') return false
    if (activeTab === 'PARTIAL_MATCH' && res.match_status !== 'PARTIAL_MATCH') return false
    if (activeTab === 'MISMATCH' && res.match_status === 'EXACT_MATCH' && Number(res.tax_difference) === 0) return false
    if (activeTab === 'RETURN_ONLY' && res.match_status !== 'RETURN_ONLY') return false
    if (activeTab === 'BOOKS_ONLY' && res.match_status !== 'BOOKS_ONLY') return false
    if (
      activeTab === 'MANUAL_REVIEW' &&
      (res.accountant_decision === 'ACCEPTED' ||
        res.accountant_decision === 'REJECTED' ||
        res.accountant_decision === 'EXCLUDED')
    )
      return false

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      const supplierName =
        res.purchase_invoice?.supplier_name || res.gstr2b_record?.supplier_name || ''
      const supplierGstin =
        res.purchase_invoice?.supplier_gstin || res.gstr2b_record?.supplier_gstin || ''
      const invNum =
        res.purchase_invoice?.invoice_number || res.gstr2b_record?.invoice_number || ''

      const matches =
        supplierName.toLowerCase().includes(q) ||
        supplierGstin.toLowerCase().includes(q) ||
        invNum.toLowerCase().includes(q)
      if (!matches) return false
    }
    return true
  })

  const getMatchBadge = (statusVal: GSTMatchStatus) => {
    switch (statusVal) {
      case 'EXACT_MATCH':
        return (
          <Badge variant="success" dot>
            Exact Match
          </Badge>
        )
      case 'PARTIAL_MATCH':
        return (
          <Badge variant="warning" dot>
            Partial Match
          </Badge>
        )
      case 'BOOKS_ONLY':
        return (
          <Badge variant="info" dot>
            Books Only
          </Badge>
        )
      case 'RETURN_ONLY':
        return (
          <Badge variant="pink" dot>
            Portal Only
          </Badge>
        )
      case 'EXCLUDED':
        return (
          <Badge variant="neutral" dot>
            Excluded
          </Badge>
        )
      default:
        return <Badge variant="neutral">{statusVal}</Badge>
    }
  }

  const getDecisionBadge = (decision: ReconciliationDecision) => {
    switch (decision) {
      case 'ACCEPTED':
        return <span className="text-2xs font-bold text-emerald-700">Accepted</span>
      case 'REJECTED':
        return <span className="text-2xs font-bold text-rose-700">Rejected</span>
      case 'EXCLUDED':
        return <span className="text-2xs font-bold text-slate-500">Excluded</span>
      default:
        return <span className="text-2xs text-amber-700 font-medium">Pending Decision</span>
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Reconciliation KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="glass-card p-4">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">
            Matching Accuracy Rate
          </span>
          <span className="text-2xl font-bold text-slate-800 block mt-1">
            {summary ? `${summary.match_rate_percentage}%` : '0%'}
          </span>
          <span className="text-2xs text-emerald-700 font-medium mt-1 block">
            {summary?.exact_matches || 0} Fully Matched Invoices
          </span>
        </div>

        <div className="glass-card p-4">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">
            Input Credit At Risk
          </span>
          <span className="text-2xl font-bold text-rose-700 block mt-1">
            {formatINR(summary?.total_itc_at_risk || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-1 block">Unmatched or Partial ITC</span>
        </div>

        <div className="glass-card p-4">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">
            Unreported by Suppliers
          </span>
          <span className="text-2xl font-bold text-sky-800 block mt-1">
            {summary?.books_only || 0}
          </span>
          <span className="text-2xs text-slate-400 mt-1 block">Recorded in Books Only</span>
        </div>

        <div className="glass-card p-4">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">
            Unclaimed in Books
          </span>
          <span className="text-2xl font-bold text-brand-700 block mt-1">
            {summary?.return_only || 0}
          </span>
          <span className="text-2xs text-slate-400 mt-1 block">Appearing on Portal Only</span>
        </div>
      </div>

      {/* Action and Filter Toolbar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        {/* Match Category Tabs */}
        <div className="flex flex-wrap items-center gap-1.5">
          {[
            { id: 'ALL', label: 'All Records', count: summary?.total_records || 0 },
            { id: 'EXACT_MATCH', label: 'Matched', count: summary?.exact_matches || 0 },
            { id: 'PARTIAL_MATCH', label: 'Potential Match', count: summary?.partial_matches || 0 },
            {
              id: 'MISMATCH',
              label: 'Mismatch',
              count: results.filter(
                (r) => r.match_status !== 'EXACT_MATCH' || Number(r.tax_difference) !== 0
              ).length,
            },
            { id: 'RETURN_ONLY', label: 'Missing in Books', count: summary?.return_only || 0 },
            { id: 'BOOKS_ONLY', label: 'Missing in 2B', count: summary?.books_only || 0 },
            {
              id: 'MANUAL_REVIEW',
              label: 'Manual Review',
              count: results.filter(
                (r) =>
                  !r.accountant_decision ||
                  r.accountant_decision === 'PENDING'
              ).length,
            },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                activeTab === tab.id
                  ? 'bg-brand-600 text-white shadow-xs'
                  : 'bg-white/80 text-slate-600 hover:bg-white hover:text-slate-900 border border-slate-200/80'
              }`}
            >
              {tab.label}
              <span className="ml-1.5 opacity-80 font-mono text-2xs">({tab.count})</span>
            </button>
          ))}
        </div>

        {/* Toolbar Buttons */}
        <div className="flex items-center gap-2">
          {onExportClick && (
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={onExportClick}
            >
              Export Report
            </Button>
          )}
          <Button
            size="sm"
            variant="secondary"
            icon={<Upload className="w-3.5 h-3.5" />}
            disabled={isLocked}
            onClick={onImportGSTR2BClick}
          >
            Import GSTR-2B
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<Play className="w-3.5 h-3.5" />}
            disabled={isLocked}
            isLoading={isReconciling}
            onClick={onRunReconciliation}
          >
            Run Matching Engine
          </Button>
        </div>
      </div>

      {/* Search Input */}
      <div className="relative max-w-sm">
        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Filter by supplier name, GSTIN, or invoice #..."
          className="glass-input text-xs pl-8 pr-3 py-1.5 rounded-lg w-full"
        />
      </div>

      {/* Results Table */}
      {filteredResults.length === 0 ? (
        <EmptyState
          title="No Reconciliation Records Found"
          description={
            results.length === 0
              ? "No reconciliation results generated for this period yet. Import GSTR-2B portal records and click 'Run Matching Engine'."
              : 'No reconciliation items match the current status filter.'
          }
        />
      ) : (
        <div className="glass-table-container overflow-x-auto shadow-xs rounded-xl border border-white/80">
          <table className="w-full text-left text-xs">
            <thead className="bg-pink-50/50 text-slate-600 font-semibold border-b border-pink-100/80">
              <tr>
                <th className="py-3 px-4">Supplier & GSTIN</th>
                <th className="py-3 px-4">Internal Books Record</th>
                <th className="py-3 px-4">GSTR-2B Portal Record</th>
                <th className="py-3 px-4 text-right">Variance</th>
                <th className="py-3 px-4 text-center">Match Status</th>
                <th className="py-3 px-4 text-center">Auditor Decision</th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white/70">
              {filteredResults.map((item) => {
                const pInv = item.purchase_invoice
                const rInv = item.gstr2b_record
                const supplierName = pInv?.supplier_name || rInv?.supplier_name || 'N/A'
                const supplierGstin = pInv?.supplier_gstin || rInv?.supplier_gstin || 'N/A'

                return (
                  <tr
                    key={item.id}
                    className="hover:bg-brand-50/30 transition-colors cursor-pointer"
                    onClick={() => onSelectResult(item)}
                  >
                    <td className="py-3 px-4">
                      <span className="font-semibold text-slate-800 block truncate max-w-[170px]">
                        {supplierName}
                      </span>
                      <span className="font-mono text-2xs text-slate-400">{supplierGstin}</span>
                    </td>

                    {/* Books Record */}
                    <td className="py-3 px-4">
                      {pInv ? (
                        <div>
                          <span className="font-mono font-semibold text-slate-800 block">
                            {pInv.invoice_number}
                          </span>
                          <span className="text-2xs text-slate-400 font-mono">
                            {formatINR(pInv.taxable_value)} ({pInv.invoice_date})
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic text-2xs">Not in Books</span>
                      )}
                    </td>

                    {/* Portal Record */}
                    <td className="py-3 px-4">
                      {rInv ? (
                        <div>
                          <span className="font-mono font-semibold text-slate-800 block">
                            {rInv.invoice_number}
                          </span>
                          <span className="text-2xs text-slate-400 font-mono">
                            {formatINR(rInv.taxable_value)} ({rInv.invoice_date})
                          </span>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic text-2xs">Not in 2B</span>
                      )}
                    </td>

                    {/* Variance */}
                    <td className="py-3 px-4 text-right">
                      {Number(item.taxable_difference) !== 0 || Number(item.tax_difference) !== 0 ? (
                        <div>
                          <span className="font-mono font-bold text-rose-700 block">
                            {formatINR(item.tax_difference)}
                          </span>
                          <span className="text-2xs text-slate-400">
                            Diff: {formatINR(item.taxable_difference)}
                          </span>
                        </div>
                      ) : (
                        <span className="text-emerald-700 font-mono font-semibold">₹0.00 (Nil)</span>
                      )}
                    </td>

                    {/* Match Status */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex flex-col items-center gap-1">
                        {getMatchBadge(item.match_status)}
                        <span className="text-2xs text-slate-400 font-mono">
                          {item.confidence_score}% confidence
                        </span>
                        {((item.difference_reasons && item.difference_reasons.length > 0) || (item as any).mismatch_reasons) && (
                          <span
                            className="text-3xs text-rose-700 bg-rose-50 px-1.5 py-0.5 rounded border border-rose-200/80 max-w-[130px] truncate block"
                            title={Array.isArray(item.difference_reasons) ? item.difference_reasons.join(', ') : String((item as any).mismatch_reasons)}
                          >
                            {Array.isArray(item.difference_reasons) ? item.difference_reasons.join(', ').replace(/_/g, ' ') : String((item as any).mismatch_reasons).replace(/[[\]"]/g, '').replace(/_/g, ' ')}
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Auditor Decision */}
                    <td className="py-3 px-4 text-center">
                      {getDecisionBadge(item.accountant_decision)}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-4 text-center">
                      <div className="flex items-center justify-center gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            onSelectResult(item)
                          }}
                          className="p-1 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-colors cursor-pointer"
                          title="View Discrepancy Details"
                        >
                          <Eye className="w-4 h-4" />
                        </button>
                        {!isLocked && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                onQuickDecision(item.id, 'ACCEPTED')
                              }}
                              className="p-1 rounded-lg text-emerald-600 hover:bg-emerald-50 transition-colors cursor-pointer"
                              title="Accept Match"
                            >
                              <CheckCircle2 className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                onQuickDecision(item.id, 'REJECTED')
                              }}
                              className="p-1 rounded-lg text-rose-600 hover:bg-rose-50 transition-colors cursor-pointer"
                              title="Flag Mismatch"
                            >
                              <XCircle className="w-4 h-4" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
