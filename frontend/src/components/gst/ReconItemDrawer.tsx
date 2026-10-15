import React, { useState } from 'react'
import {
  X,
  Layers,
  AlertTriangle,
  Scale,
  FileCheck2,
} from 'lucide-react'
import type { GSTReconciliationResult, ReconciliationDecision } from '../../types/gst'
import { formatINR } from '../../utils/formatters'
import { submitReconciliationDecision } from '../../services/gstApi'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface ReconItemDrawerProps {
  item: GSTReconciliationResult | null
  isLocked?: boolean
  onClose: () => void
  onDecisionUpdated: (updated: GSTReconciliationResult) => void
}

export const ReconItemDrawer: React.FC<ReconItemDrawerProps> = ({
  item,
  isLocked = false,
  onClose,
  onDecisionUpdated,
}) => {
  const [notes, setNotes] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  React.useEffect(() => {
    if (item) {
      setNotes(item.accountant_notes || '')
      setErrorMessage(null)
      setSuccessMsg(null)
    }
  }, [item])

  if (!item) return null

  const handleDecision = async (decision: ReconciliationDecision) => {
    setIsSubmitting(true)
    setErrorMessage(null)
    try {
      const updated = await submitReconciliationDecision(item.id, decision, notes)
      onDecisionUpdated(updated)
      setSuccessMsg(`Decision set to ${decision}`)
      setTimeout(() => setSuccessMsg(null), 2500)
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to submit decision')
    } finally {
      setIsSubmitting(false)
    }
  }

  const getMatchStatusBadge = (statusVal: string) => {
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
            Portal 2B Only
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

  const pInv = item.purchase_invoice
  const rInv = item.gstr2b_record

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-xl bg-white/95 backdrop-blur-md shadow-2xl border-l border-white/80 flex flex-col">
          {/* Header */}
          <div className="p-6 border-b border-slate-200/80 bg-gradient-to-r from-pink-50/50 via-white to-pink-50/30 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200/80 text-brand-600 flex items-center justify-center">
                <Scale className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-800">
                  Reconciliation Discrepancy Analysis
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">
                  ID: #{item.id} • Confidence: {item.confidence_score}%
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Status & Confidence Banner */}
            <div className="p-4 rounded-xl border border-slate-200/70 bg-slate-50/60 flex items-center justify-between">
              <div>
                <span className="text-xs text-slate-500 block">Match Classification</span>
                <span className="text-sm font-semibold text-slate-800">
                  Algorithmic Confidence: {item.confidence_score}%
                </span>
              </div>
              {getMatchStatusBadge(item.match_status)}
            </div>

            {/* Mismatch Difference & Reasons */}
            {item.difference_reasons && item.difference_reasons.length > 0 && (
              <div className="p-4 rounded-xl border border-amber-200 bg-amber-50/70 text-amber-900 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-xs text-amber-900">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
                  Identified Variances
                </div>
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {item.difference_reasons.map((reason, idx) => (
                    <span
                      key={idx}
                      className="px-2.5 py-0.5 rounded-full text-2xs font-semibold bg-amber-100/90 text-amber-800 border border-amber-300/80"
                    >
                      {reason.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
                <div className="pt-2 text-xs flex justify-between border-t border-amber-200/60">
                  <span className="text-amber-800">Taxable Variance:</span>
                  <span className="font-mono font-bold">{formatINR(item.taxable_difference)}</span>
                </div>
                <div className="text-xs flex justify-between">
                  <span className="text-amber-800">Tax Amount Variance:</span>
                  <span className="font-mono font-bold">{formatINR(item.tax_difference)}</span>
                </div>
              </div>
            )}

            {/* Side-by-Side Comparison */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Internal Books vs. GSTR-2B Portal Record
              </h4>

              <div className="grid grid-cols-2 gap-3 text-xs">
                {/* Internal Books Card */}
                <div className="p-3.5 rounded-xl border border-sky-200/80 bg-sky-50/30 space-y-3">
                  <div className="font-bold text-sky-900 flex items-center gap-1.5 border-b border-sky-100 pb-2">
                    <FileCheck2 className="w-4 h-4 text-sky-600" />
                    Internal Purchase Books
                  </div>
                  {pInv ? (
                    <div className="space-y-2">
                      <div>
                        <span className="text-slate-400 block text-2xs">Supplier</span>
                        <span className="font-semibold text-slate-800 block truncate">
                          {pInv.supplier_name}
                        </span>
                        <span className="font-mono text-2xs text-slate-500">{pInv.supplier_gstin}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-2xs">Invoice # & Date</span>
                        <span className="font-mono font-semibold text-slate-800 block">
                          {pInv.invoice_number}
                        </span>
                        <span className="text-slate-500 text-2xs">{pInv.invoice_date}</span>
                      </div>
                      <div className="pt-1 border-t border-sky-100">
                        <span className="text-slate-400 block text-2xs">Taxable Value</span>
                        <span className="font-mono font-semibold text-slate-800">
                          {formatINR(pInv.taxable_value)}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-2xs">Total Tax (CGST+SGST+IGST)</span>
                        <span className="font-mono font-bold text-sky-900">
                          {formatINR(
                            Number(pInv.cgst_amount || 0) +
                              Number(pInv.sgst_amount || 0) +
                              Number(pInv.igst_amount || 0)
                          )}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-400 italic py-6 text-center">
                      No matching record in internal purchase register (Portal Only)
                    </div>
                  )}
                </div>

                {/* External GSTR-2B Card */}
                <div className="p-3.5 rounded-xl border border-pink-200/80 bg-pink-50/30 space-y-3">
                  <div className="font-bold text-brand-900 flex items-center gap-1.5 border-b border-pink-100 pb-2">
                    <Layers className="w-4 h-4 text-brand-600" />
                    Government GSTR-2B
                  </div>
                  {rInv ? (
                    <div className="space-y-2">
                      <div>
                        <span className="text-slate-400 block text-2xs">Filing Supplier</span>
                        <span className="font-semibold text-slate-800 block truncate">
                          {rInv.supplier_name}
                        </span>
                        <span className="font-mono text-2xs text-slate-500">{rInv.supplier_gstin}</span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-2xs">Portal Invoice # & Date</span>
                        <span className="font-mono font-semibold text-slate-800 block">
                          {rInv.invoice_number}
                        </span>
                        <span className="text-slate-500 text-2xs">{rInv.invoice_date}</span>
                      </div>
                      <div className="pt-1 border-t border-pink-100">
                        <span className="text-slate-400 block text-2xs">Taxable Value</span>
                        <span className="font-mono font-semibold text-slate-800">
                          {formatINR(rInv.taxable_value)}
                        </span>
                      </div>
                      <div>
                        <span className="text-slate-400 block text-2xs">Total Tax (CGST+SGST+IGST)</span>
                        <span className="font-mono font-bold text-brand-900">
                          {formatINR(
                            Number(rInv.cgst_amount || 0) +
                              Number(rInv.sgst_amount || 0) +
                              Number(rInv.igst_amount || 0)
                          )}
                        </span>
                      </div>
                      <div className="pt-1">
                        <span className="text-2xs text-slate-400 block">ITC Availability</span>
                        <span
                          className={`text-2xs font-semibold ${
                            rInv.itc_available ? 'text-emerald-700' : 'text-rose-700'
                          }`}
                        >
                          {rInv.itc_available ? 'Eligible for Credit' : 'Ineligible Credit'}
                        </span>
                      </div>
                    </div>
                  ) : (
                    <div className="text-slate-400 italic py-6 text-center">
                      Not found in GSTR-2B portal (Unreported by Supplier)
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Decision & Audit */}
            <div className="space-y-3 pt-2">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Auditor Decision & Notes
              </h4>

              <div className="p-4 rounded-xl border border-slate-200/80 bg-white space-y-4">
                <div>
                  <label className="text-xs font-semibold text-slate-700 block mb-1.5">
                    Accountant Notes / Reconciliation Justification
                  </label>
                  <textarea
                    value={notes}
                    onChange={(e) => setNotes(e.target.value)}
                    disabled={isLocked}
                    placeholder="Enter audit trail justification or clarification..."
                    className="glass-input w-full text-xs h-20 p-2.5 rounded-lg resize-none"
                  />
                </div>

                {successMsg && (
                  <div className="text-xs text-emerald-700 bg-emerald-50 p-2.5 rounded-lg border border-emerald-200">
                    {successMsg}
                  </div>
                )}
                {errorMessage && (
                  <div className="text-xs text-rose-700 bg-rose-50 p-2.5 rounded-lg border border-rose-200">
                    {errorMessage}
                  </div>
                )}

                <div className="flex items-center gap-2 pt-1">
                  <span className="text-xs text-slate-500 mr-auto">
                    Current: <strong>{item.accountant_decision}</strong>
                  </span>
                  {!isLocked && (
                    <>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={isSubmitting}
                        onClick={() => handleDecision('ACCEPTED')}
                        className="text-emerald-700 border-emerald-200 hover:bg-emerald-50"
                      >
                        Accept Match
                      </Button>
                      <Button
                        size="sm"
                        variant="secondary"
                        disabled={isSubmitting}
                        onClick={() => handleDecision('REJECTED')}
                        className="text-rose-700 border-rose-200 hover:bg-rose-50"
                      >
                        Flag Mismatch
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={isSubmitting}
                        onClick={() => handleDecision('EXCLUDED')}
                      >
                        Exclude
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="p-4 border-t border-slate-200/80 bg-slate-50/80 flex justify-end">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Close
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}
