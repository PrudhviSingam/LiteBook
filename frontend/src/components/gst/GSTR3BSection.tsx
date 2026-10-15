import React from 'react'
import {
  Calculator,
  RefreshCw,
  Download,
} from 'lucide-react'
import type { GSTR3BSummary } from '../../types/gst'
import { formatINR } from '../../utils/formatters'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'

interface GSTR3BSectionProps {
  summary: GSTR3BSummary | null
  isLocked: boolean
  isRecalculating: boolean
  onRecalculate: () => void
  onExportClick?: () => void
}

export const GSTR3BSection: React.FC<GSTR3BSectionProps> = ({
  summary,
  isLocked,
  isRecalculating,
  onRecalculate,
  onExportClick,
}) => {
  if (!summary) {
    return (
      <EmptyState
        title="GSTR-3B Computation Not Generated"
        description="No statutory summary has been computed for this filing period yet. Click recalculate to run the monthly tax computation."
        action={
          <Button
            size="sm"
            variant="primary"
            icon={<RefreshCw className="w-4 h-4" />}
            isLoading={isRecalculating}
            onClick={onRecalculate}
          >
            Compute GSTR-3B
          </Button>
        }
      />
    )
  }

  const setOff = summary.set_off_summary || {}

  return (
    <div className="space-y-6">
      {/* Header bar with statutory rule reminder & recalculate */}
      <div className="glass-panel p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center shrink-0 border border-brand-200">
            <Calculator className="w-4 h-4" />
          </div>
          <div>
            <h4 className="text-xs font-bold text-slate-800">
              Statutory GST Council Set-Off Matrix
            </h4>
            <p className="text-2xs text-slate-500">
              IGST credit is utilized first against IGST, then CGST & SGST. CGST and SGST cannot cross-utilize.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-2xs text-slate-400">
            Computed: {summary.calculated_at ? new Date(summary.calculated_at).toLocaleTimeString() : 'N/A'}
          </span>
          {onExportClick && (
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={onExportClick}
            >
              Export GSTR-3B
            </Button>
          )}
          <Button
            size="sm"
            variant="secondary"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            disabled={isLocked}
            isLoading={isRecalculating}
            onClick={onRecalculate}
          >
            Recalculate
          </Button>
        </div>
      </div>

      {/* Table 3.1 & Table 4 Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Table 3.1 Outward Supplies */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              3.1 Outward Taxable Supplies (Output Liability)
            </h4>
            <Badge variant="pink">Calculated from Invoices</Badge>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Total Taxable Value</span>
              <span className="font-mono font-bold text-slate-800">
                {formatINR(summary.outward_taxable_value)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Integrated Tax (IGST)</span>
              <span className="font-mono font-semibold text-slate-800">
                {formatINR(summary.outward_igst)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Central Tax (CGST)</span>
              <span className="font-mono font-semibold text-slate-800">
                {formatINR(summary.outward_cgst)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">State Tax (SGST)</span>
              <span className="font-mono font-semibold text-slate-800">
                {formatINR(summary.outward_sgst)}
              </span>
            </div>
            {Number(summary.outward_cess) > 0 && (
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Compensation Cess</span>
                <span className="font-mono font-semibold text-slate-800">
                  {formatINR(summary.outward_cess)}
                </span>
              </div>
            )}
            <div className="flex justify-between pt-2 text-sm font-bold text-slate-900 bg-pink-50/50 p-2.5 rounded-lg">
              <span>Total Outward Tax</span>
              <span className="font-mono text-brand-700">
                {formatINR(summary.outward_total_tax)}
              </span>
            </div>
          </div>
        </div>

        {/* Table 4 Eligible ITC */}
        <div className="glass-card p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              4. Eligible Input Tax Credit (ITC Available)
            </h4>
            <Badge variant="success">Input Credits (Reconciled)</Badge>
          </div>

          <div className="space-y-2 text-xs">
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Integrated Tax (IGST Credit)</span>
              <span className="font-mono font-semibold text-emerald-800">
                {formatINR(summary.net_itc_igst)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">Central Tax (CGST Credit)</span>
              <span className="font-mono font-semibold text-emerald-800">
                {formatINR(summary.net_itc_cgst)}
              </span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-100">
              <span className="text-slate-500">State Tax (SGST Credit)</span>
              <span className="font-mono font-semibold text-emerald-800">
                {formatINR(summary.net_itc_sgst)}
              </span>
            </div>
            {Number(summary.net_itc_cess) > 0 && (
              <div className="flex justify-between py-1.5 border-b border-slate-100">
                <span className="text-slate-500">Cess Credit</span>
                <span className="font-mono font-semibold text-emerald-800">
                  {formatINR(summary.net_itc_cess)}
                </span>
              </div>
            )}
            <div className="flex justify-between pt-2 text-sm font-bold text-slate-900 bg-emerald-50/50 p-2.5 rounded-lg">
              <span>Total Net ITC Available</span>
              <span className="font-mono text-emerald-800">
                {formatINR(summary.itc_total)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Table 6.1 Payment of Tax (Set-Off Breakdown & Cash Liability) */}
      <div className="glass-card p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-3">
          <div>
            <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              6.1 Payment of Tax & Statutory Credit Utilization Matrix
            </h4>
            <p className="text-2xs text-slate-500 mt-0.5">
              Net balance payable in cash after complete statutory offset of eligible input credits.
            </p>
          </div>
          <Badge variant="warning">Cash Ledger Impact</Badge>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead className="bg-slate-50/80 text-slate-600 font-semibold border-b border-slate-200/80">
              <tr>
                <th className="py-2.5 px-3">Tax Head</th>
                <th className="py-2.5 px-3 text-right">Tax Payable</th>
                <th className="py-2.5 px-3 text-right">Paid via IGST Credit</th>
                <th className="py-2.5 px-3 text-right">Paid via CGST Credit</th>
                <th className="py-2.5 px-3 text-right">Paid via SGST Credit</th>
                <th className="py-2.5 px-3 text-right font-bold text-slate-900">
                  Tax Payable in Cash
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white">
              {/* IGST Row */}
              <tr>
                <td className="py-2.5 px-3 font-semibold text-slate-800">Integrated Tax (IGST)</td>
                <td className="py-2.5 px-3 text-right font-mono font-medium">
                  {formatINR(summary.outward_igst)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.igst_utilized_for_igst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.cgst_utilized_for_igst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.sgst_utilized_for_igst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono font-bold text-brand-700">
                  {formatINR(summary.tax_payable_igst)}
                </td>
              </tr>

              {/* CGST Row */}
              <tr>
                <td className="py-2.5 px-3 font-semibold text-slate-800">Central Tax (CGST)</td>
                <td className="py-2.5 px-3 text-right font-mono font-medium">
                  {formatINR(summary.outward_cgst)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.igst_utilized_for_cgst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.cgst_utilized_for_cgst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                  - (Not Allowed)
                </td>
                <td className="py-2.5 px-3 text-right font-mono font-bold text-brand-700">
                  {formatINR(summary.tax_payable_cgst)}
                </td>
              </tr>

              {/* SGST Row */}
              <tr>
                <td className="py-2.5 px-3 font-semibold text-slate-800">State Tax (SGST)</td>
                <td className="py-2.5 px-3 text-right font-mono font-medium">
                  {formatINR(summary.outward_sgst)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.igst_utilized_for_sgst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-slate-300">
                  - (Not Allowed)
                </td>
                <td className="py-2.5 px-3 text-right font-mono text-emerald-700">
                  {formatINR(setOff.sgst_utilized_for_sgst || 0)}
                </td>
                <td className="py-2.5 px-3 text-right font-mono font-bold text-brand-700">
                  {formatINR(summary.tax_payable_sgst)}
                </td>
              </tr>

              {/* Total Footer Row */}
              <tr className="bg-pink-50/70 font-bold text-slate-900 border-t-2 border-pink-200">
                <td className="py-3 px-3">Total Statutory Liability</td>
                <td className="py-3 px-3 text-right font-mono">
                  {formatINR(summary.outward_total_tax)}
                </td>
                <td className="py-3 px-3 text-right font-mono text-emerald-800" colSpan={3}>
                  Net ITC Set-Off Applied
                </td>
                <td className="py-3 px-3 text-right font-mono text-base text-rose-700">
                  {formatINR(summary.total_tax_payable)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
