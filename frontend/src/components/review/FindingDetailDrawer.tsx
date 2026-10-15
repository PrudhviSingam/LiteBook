import React, { useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  XCircle,
  FileSpreadsheet,
  Info,
  Download,
  Clock,
  Sparkles,
  ExternalLink,
  ShieldCheck,
  X,
  FileCheck,
} from 'lucide-react'
import type { ReviewFindingItem } from '../../types'
import { formatINR } from '../../utils/formatters'
import { updateFindingDecision, generateCorrectedWorkbook, getDocumentDownloadUrl } from '../../services/api'
import { Button } from '../ui/Button'

interface FindingDetailDrawerProps {
  finding: ReviewFindingItem | null
  onClose: () => void
  onFindingUpdated: (updated: ReviewFindingItem) => void
}

export const FindingDetailDrawer: React.FC<FindingDetailDrawerProps> = ({
  finding,
  onClose,
  onFindingUpdated,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [decisionNotes, setDecisionNotes] = useState('')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  // Correction workflow states
  const [correctionState, setCorrectionState] = useState<'idle' | 'approving' | 'approved' | 'generating' | 'generated' | 'failed'>('idle')
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null)

  if (!finding) return null

  const handleDecision = async (decision: 'APPROVE' | 'REJECT' | 'UNDER_REVIEW' | 'IGNORE') => {
    setIsSubmitting(true)
    setErrorMessage(null)
    setSuccessMessage(null)

    try {
      const updated = await updateFindingDecision(finding.id, {
        decision,
        notes: decisionNotes || undefined,
      })
      onFindingUpdated(updated)
      setSuccessMessage(`Decision recorded: ${decision}`)
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to record decision')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleApproveCorrection = async () => {
    setIsSubmitting(true)
    setErrorMessage(null)
    setCorrectionState('approving')

    try {
      const updated = await updateFindingDecision(finding.id, {
        decision: 'APPROVE',
        notes: decisionNotes || 'Accountant approved correction proposal',
      })
      onFindingUpdated(updated)
      setCorrectionState('generating')

      if (finding.session_id) {
        const genRes = await generateCorrectedWorkbook(finding.session_id, 'Partner Accountant')
        if (genRes.success) {
          setCorrectionState('generated')
          setDownloadUrl(genRes.download_url)
        } else {
          setCorrectionState('failed')
          setErrorMessage(genRes.message || 'Failed to generate corrected workbook.')
        }
      } else {
        setCorrectionState('approved')
      }
    } catch (err: any) {
      setCorrectionState('failed')
      setErrorMessage(err.message || 'Correction could not be approved. The original file remains unchanged.')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity.toUpperCase()) {
      case 'CRITICAL':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-100 text-rose-800 border border-rose-200">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-600 animate-pulse" />
            CRITICAL
          </span>
        )
      case 'HIGH':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-bold bg-rose-50 text-rose-700 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            HIGH
          </span>
        )
      case 'MEDIUM':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            MEDIUM
          </span>
        )
      case 'LOW':
      case 'INFO':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <Info className="w-3.5 h-3.5 text-slate-500" />
            LOW
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
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
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            Approved
          </span>
        )
      case 'REVIEW_REQUIRED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-800 border border-rose-200">
            <AlertTriangle className="w-3.5 h-3.5 text-rose-600" />
            Review Required
          </span>
        )
      case 'NEEDS_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-200">
            <Clock className="w-3.5 h-3.5 text-amber-600" />
            Needs Review
          </span>
        )
      case 'UNDER_REVIEW':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-sky-50 text-sky-800 border border-sky-200">
            <Clock className="w-3.5 h-3.5 text-sky-600" />
            Under Review
          </span>
        )
      case 'REJECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700 border border-slate-200">
            <XCircle className="w-3.5 h-3.5 text-slate-500" />
            Rejected
          </span>
        )
      case 'CORRECTED':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-50 text-purple-800 border border-purple-200">
            <FileCheck className="w-3.5 h-3.5 text-purple-600" />
            Corrected
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
            {status}
          </span>
        )
    }
  }

  const hasDifference =
    finding.difference !== null && finding.difference !== undefined && finding.difference > 0

  return (
    <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/30 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
      <div className="w-full max-w-2xl bg-white/95 backdrop-blur-xl h-full shadow-2xl flex flex-col border-l border-white/80 overflow-y-auto">
        {/* Header */}
        <div className="p-6 border-b border-slate-200/70 glass-header flex items-start justify-between sticky top-0 z-10">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              {getSeverityBadge(finding.severity)}
              {getStatusBadge(finding.status)}
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-brand-50 text-brand-700 border border-brand-200/60">
                <ShieldCheck className="w-3 h-3 text-brand-500" />
                {finding.confidence} Confidence
              </span>
            </div>
            <h2 className="text-xl font-extrabold text-slate-900 tracking-tight leading-snug">
              {finding.title}
            </h2>
            <p className="text-xs text-slate-500 flex items-center gap-1.5">
              <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
              <span>{finding.document_name}</span>
              {finding.financial_period && (
                <>
                  <span>•</span>
                  <span className="font-semibold text-slate-700">{finding.financial_period}</span>
                </>
              )}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100/80 rounded-xl transition-colors cursor-pointer"
            title="Close drawer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 space-y-6 flex-1 text-sm">
          {/* Notifications */}
          {errorMessage && (
            <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-start gap-2.5">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
              <div>
                <p className="font-bold">Action could not be completed</p>
                <p>{errorMessage}</p>
              </div>
            </div>
          )}
          {successMessage && (
            <div className="p-4 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{successMessage}</span>
            </div>
          )}

          {/* Section 1: Finding Overview */}
          <div className="glass-card p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              1. What Was Found?
            </h3>
            <p className="text-slate-800 text-sm leading-relaxed">
              {finding.description}
            </p>
          </div>

          {/* Section 2: Expected vs Actual Financial Values */}
          <div className="glass-card p-5 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              2. Financial Values & Variance
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3 rounded-xl bg-white/80 border border-slate-200/80">
                <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider block">
                  Expected Value
                </span>
                <span className="text-base font-bold text-slate-800 mt-1 block font-mono">
                  {finding.expected_value !== null && finding.expected_value !== undefined
                    ? formatINR(finding.expected_value)
                    : '—'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-white/80 border border-slate-200/80">
                <span className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider block">
                  Actual Value
                </span>
                <span className="text-base font-bold text-slate-800 mt-1 block font-mono">
                  {finding.actual_value !== null && finding.actual_value !== undefined
                    ? formatINR(finding.actual_value)
                    : '—'}
                </span>
              </div>
              <div className="p-3 rounded-xl bg-rose-50/80 border border-rose-200/80">
                <span className="text-[10px] text-rose-700 font-semibold uppercase tracking-wider block">
                  Difference / Variance
                </span>
                <span className="text-base font-bold text-rose-700 mt-1 block font-mono">
                  {hasDifference ? formatINR(finding.difference!) : 'No variance'}
                </span>
              </div>
            </div>
          </div>

          {/* Section 3: Provenance & Exact Location */}
          <div className="glass-card p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              3. Provenance & Cell Reference
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
              <div className="p-2.5 rounded-lg bg-white/70 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Workbook</span>
                <span className="font-semibold text-slate-800 truncate block">{finding.document_name}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/70 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Sheet</span>
                <span className="font-semibold text-slate-800 truncate block">{finding.sheet_name || '—'}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/70 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Cell Address</span>
                <span className="font-mono font-bold text-brand-600 block">{finding.cell_address || '—'}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-white/70 border border-slate-200/60">
                <span className="text-slate-400 block text-[10px]">Row Index</span>
                <span className="font-mono font-semibold text-slate-800 block">
                  {finding.row_index !== null && finding.row_index !== undefined ? finding.row_index : '—'}
                </span>
              </div>
            </div>
          </div>

          {/* Section 4: Cause Analysis */}
          <div className="glass-card p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-500">
              4. Root Cause Analysis
            </h3>
            <div className="space-y-2 text-xs">
              {finding.possible_cause && (
                <div className="p-3 rounded-xl bg-amber-50/70 border border-amber-200/70">
                  <span className="font-bold text-amber-900 block mb-0.5">Potential Cause:</span>
                  <p className="text-amber-800 leading-relaxed">{finding.possible_cause}</p>
                </div>
              )}
              {finding.proven_cause && (
                <div className="p-3 rounded-xl bg-purple-50/70 border border-purple-200/70">
                  <span className="font-bold text-purple-900 block mb-0.5">Verified Finding:</span>
                  <p className="text-purple-800 leading-relaxed">{finding.proven_cause}</p>
                </div>
              )}
              {!finding.possible_cause && !finding.proven_cause && (
                <p className="text-slate-500">Deterministic check verified mathematically.</p>
              )}
            </div>
          </div>

          {/* Section 5: AI Explanation (Where available) */}
          {finding.ai_explanation && (
            <div className="glass-card p-5 space-y-2 border-brand-200/70 bg-brand-50/40">
              <div className="flex items-center gap-1.5 text-brand-700">
                <Sparkles className="w-4 h-4 text-brand-500" />
                <h3 className="text-xs font-bold uppercase tracking-wider">AI Forensic Explanation</h3>
              </div>
              <p className="text-slate-700 text-xs sm:text-sm leading-relaxed whitespace-pre-wrap">
                {finding.ai_explanation}
              </p>
            </div>
          )}

          {/* Section 6: Accountant Decision */}
          <div className="glass-card p-5 space-y-4 border-2 border-brand-200/70">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-700">
              5. Accountant Decision & Safety Workflow
            </h3>
            <p className="text-xs text-slate-500 leading-relaxed">
              LiteBooks operates strictly in a non-destructive accountant-first workflow. Original files are never modified without explicit decision approval.
            </p>

            <div>
              <label className="block text-[11px] font-semibold text-slate-600 mb-1">
                Accountant Audit Notes (Optional)
              </label>
              <textarea
                value={decisionNotes}
                onChange={(e) => setDecisionNotes(e.target.value)}
                placeholder="Add audit justification or notes for this finding..."
                rows={2}
                className="w-full glass-input p-2.5 text-xs text-slate-800 placeholder-slate-400 font-sans"
              />
            </div>

            <div className="flex flex-wrap items-center gap-2 pt-2">
              <Button
                variant="primary"
                size="sm"
                icon={<CheckCircle2 className="w-4 h-4" />}
                isLoading={isSubmitting}
                onClick={() => handleDecision('APPROVE')}
              >
                Approve / Confirm
              </Button>
              <Button
                variant="secondary"
                size="sm"
                icon={<Clock className="w-4 h-4" />}
                disabled={isSubmitting}
                onClick={() => handleDecision('UNDER_REVIEW')}
              >
                Mark Reviewed
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon={<XCircle className="w-4 h-4" />}
                disabled={isSubmitting}
                onClick={() => handleDecision('REJECT')}
              >
                Reject
              </Button>
            </div>

            {/* Non-destructive corrected copy download */}
            {finding.session_id && (
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-[11px] text-slate-500">
                  Generate timestamped corrected copy with audit worksheet
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  icon={<Download className="w-3.5 h-3.5" />}
                  isLoading={correctionState === 'generating'}
                  onClick={handleApproveCorrection}
                >
                  Generate Corrected Copy
                </Button>
              </div>
            )}

            {downloadUrl && (
              <div className="p-3 rounded-xl bg-purple-50 border border-purple-200 flex items-center justify-between">
                <span className="text-xs font-semibold text-purple-900">
                  Corrected copy ready for download
                </span>
                <a
                  href={downloadUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="px-3 py-1 bg-purple-600 text-white rounded-lg text-xs font-bold hover:bg-purple-700 flex items-center gap-1"
                >
                  <Download className="w-3 h-3" /> Download
                </a>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
