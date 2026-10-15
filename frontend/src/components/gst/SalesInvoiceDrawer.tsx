import React from 'react'
import { X, FileText, AlertCircle } from 'lucide-react'
import type { GSTSalesInvoice } from '../../types/gst'
import { formatINR } from '../../utils/formatters'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

interface SalesInvoiceDrawerProps {
  invoice: GSTSalesInvoice | null
  onClose: () => void
}

export const SalesInvoiceDrawer: React.FC<SalesInvoiceDrawerProps> = ({ invoice, onClose }) => {
  if (!invoice) return null

  const getValidationBadge = (statusVal: string) => {
    switch (statusVal) {
      case 'VALID':
        return (
          <Badge variant="success" dot>
            Compliant
          </Badge>
        )
      case 'WARNING':
        return (
          <Badge variant="warning" dot>
            Review Warning
          </Badge>
        )
      case 'ERROR':
        return (
          <Badge variant="danger" dot>
            Statutory Error
          </Badge>
        )
      default:
        return <Badge variant="neutral">{statusVal}</Badge>
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div
        className="absolute inset-0 bg-slate-900/30 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-lg bg-white/95 backdrop-blur-md shadow-2xl border-l border-white/80 flex flex-col">
          {/* Header */}
          <div className="p-6 border-b border-slate-200/80 bg-gradient-to-r from-pink-50/50 via-white to-pink-50/30 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-50 border border-brand-200/80 text-brand-600 flex items-center justify-center">
                <FileText className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-800">Sales Invoice Details</h3>
                <p className="text-xs text-slate-500 font-mono mt-0.5">{invoice.invoice_number}</p>
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
            {/* Status Card */}
            <div className="p-4 rounded-xl border border-slate-200/70 bg-slate-50/60 flex items-center justify-between">
              <div>
                <span className="text-xs text-slate-500 block">Compliance Status</span>
                <span className="text-sm font-semibold text-slate-800">
                  GSTR-1 Validation Check
                </span>
              </div>
              {getValidationBadge(invoice.validation_status)}
            </div>

            {/* Validation Errors or Alerts */}
            {invoice.validation_issues && invoice.validation_issues.length > 0 ? (
              <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/80 text-rose-900 space-y-3">
                <div className="flex items-center gap-2 font-semibold text-xs text-rose-950">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  Statutory Validation Issues ({invoice.validation_issues.length})
                </div>
                <div className="space-y-2">
                  {invoice.validation_issues.map((issue, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-white/80 border border-rose-200/80 text-xs space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-bold text-2xs text-rose-800 uppercase px-1.5 py-0.5 rounded bg-rose-100">
                          {issue.code}
                        </span>
                        <span className="text-2xs text-slate-500 font-medium">
                          Field: <span className="font-mono text-slate-700">{issue.field}</span>
                        </span>
                      </div>
                      <p className="text-slate-800 font-medium">{issue.message}</p>
                      {issue.suggested_action && (
                        <p className="text-slate-600 text-2xs bg-amber-50/70 p-1.5 rounded border border-amber-200/50">
                          <strong className="text-amber-900">Action:</strong> {issue.suggested_action}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : invoice.validation_errors && invoice.validation_errors.length > 0 && (
              <div className="p-4 rounded-xl border border-rose-200 bg-rose-50/70 text-rose-800 space-y-1.5">
                <div className="flex items-center gap-2 font-semibold text-xs text-rose-900">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  Validation Discrepancies
                </div>
                <ul className="list-disc list-inside text-xs space-y-1 pl-1 text-rose-700">
                  {invoice.validation_errors.map((err, idx) => (
                    <li key={idx}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* General Details */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Counterparty & Delivery
              </h4>
              <div className="grid grid-cols-2 gap-3 text-xs">
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Customer Name</span>
                  <span className="font-semibold text-slate-800">{invoice.customer_name}</span>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Customer GSTIN</span>
                  <span className="font-mono font-medium text-slate-800">
                    {invoice.customer_gstin || 'Unregistered / Consumer'}
                  </span>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Invoice Date</span>
                  <span className="font-semibold text-slate-800">{invoice.invoice_date}</span>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Normalized Number</span>
                  <span className="font-mono text-slate-700">{invoice.normalized_invoice_number || invoice.invoice_number}</span>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Invoice Classification</span>
                  <Badge variant="pink">{invoice.invoice_type}</Badge>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Place of Supply (POS)</span>
                  <span className="font-semibold text-slate-800">
                    State Code {invoice.place_of_supply}
                  </span>
                </div>
                <div className="p-3 rounded-lg border border-slate-200/60 bg-white">
                  <span className="text-slate-400 block mb-1">Supply Nature</span>
                  <span className="font-semibold text-slate-800">
                    {invoice.is_inter_state ? 'Inter-State (IGST)' : 'Intra-State (CGST + SGST)'}
                  </span>
                </div>
                {invoice.hsn_code && (
                  <div className="p-3 rounded-lg border border-slate-200/60 bg-white col-span-2">
                    <span className="text-slate-400 block mb-1">HSN / SAC Code</span>
                    <span className="font-mono font-medium text-slate-800">
                      {invoice.hsn_code}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Financial Computation */}
            <div className="space-y-3">
              <h4 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
                Financial & Tax Split Breakdown
              </h4>
              <div className="border border-slate-200/80 rounded-xl overflow-hidden bg-white shadow-2xs divide-y divide-slate-100">
                <div className="p-3 flex justify-between items-center text-xs">
                  <span className="text-slate-500">Taxable Value</span>
                  <span className="font-mono font-semibold text-slate-800">
                    {formatINR(invoice.taxable_value)}
                  </span>
                </div>
                <div className="p-3 flex justify-between items-center text-xs">
                  <span className="text-slate-500">Tax Rate</span>
                  <span className="font-mono font-medium text-slate-800">
                    {invoice.tax_rate}%
                  </span>
                </div>

                {!invoice.is_inter_state ? (
                  <>
                    <div className="p-3 flex justify-between items-center text-xs bg-slate-50/50">
                      <span className="text-slate-500">Central Tax (CGST)</span>
                      <span className="font-mono font-semibold text-slate-700">
                        {formatINR(invoice.cgst_amount)}
                      </span>
                    </div>
                    <div className="p-3 flex justify-between items-center text-xs bg-slate-50/50">
                      <span className="text-slate-500">State Tax (SGST)</span>
                      <span className="font-mono font-semibold text-slate-700">
                        {formatINR(invoice.sgst_amount)}
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="p-3 flex justify-between items-center text-xs bg-brand-50/30">
                    <span className="text-brand-800 font-medium">Integrated Tax (IGST)</span>
                    <span className="font-mono font-semibold text-brand-900">
                      {formatINR(invoice.igst_amount)}
                    </span>
                  </div>
                )}

                {Number(invoice.cess_amount) > 0 && (
                  <div className="p-3 flex justify-between items-center text-xs">
                    <span className="text-slate-500">Compensation Cess</span>
                    <span className="font-mono font-semibold text-slate-700">
                      {formatINR(invoice.cess_amount)}
                    </span>
                  </div>
                )}

                <div className="p-3 flex justify-between items-center text-sm font-bold bg-pink-50/60 text-slate-900">
                  <span>Total Invoice Amount</span>
                  <span className="font-mono text-brand-700">
                    {formatINR(invoice.total_amount)}
                  </span>
                </div>
              </div>
            </div>

            {/* Reverse Charge info */}
            <div className="p-3 rounded-xl border border-slate-200/60 bg-white flex items-center justify-between text-xs">
              <span className="text-slate-500">Reverse Charge Mechanism (RCM)</span>
              <span className="font-semibold text-slate-700">
                {invoice.is_reverse_charge ? 'Yes (Applicable)' : 'No'}
              </span>
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
