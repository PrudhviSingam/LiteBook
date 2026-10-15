import React, { useState } from 'react'
import {
  Plus,
  Search,
  Eye,
  Download,
} from 'lucide-react'
import type { GSTSalesInvoice, GSTR1Summary } from '../../types/gst'
import { formatINR } from '../../utils/formatters'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { EmptyState } from '../ui/EmptyState'

interface GSTR1SectionProps {
  summary: GSTR1Summary | null
  invoices: GSTSalesInvoice[]
  isLocked: boolean
  onAddInvoiceClick: () => void
  onSelectInvoice: (invoice: GSTSalesInvoice) => void
  onExportClick?: () => void
}

export const GSTR1Section: React.FC<GSTR1SectionProps> = ({
  summary,
  invoices,
  isLocked,
  onAddInvoiceClick,
  onSelectInvoice,
  onExportClick,
}) => {
  const [typeFilter, setTypeFilter] = useState('ALL')
  const [statusFilter, setStatusFilter] = useState('ALL')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredInvoices = invoices.filter((inv) => {
    if (typeFilter !== 'ALL' && inv.invoice_type !== typeFilter) return false
    if (statusFilter !== 'ALL' && inv.validation_status !== statusFilter) return false
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim()
      const matches =
        inv.invoice_number.toLowerCase().includes(q) ||
        inv.customer_name.toLowerCase().includes(q) ||
        (inv.customer_gstin && inv.customer_gstin.toLowerCase().includes(q)) ||
        inv.total_amount.toString().includes(q)
      if (!matches) return false
    }
    return true
  })

  const getValidationBadge = (statusVal: string) => {
    switch (statusVal) {
      case 'VALID':
        return (
          <Badge variant="success" dot>
            Valid
          </Badge>
        )
      case 'WARNING':
        return (
          <Badge variant="warning" dot>
            Warning
          </Badge>
        )
      case 'ERROR':
        return (
          <Badge variant="danger" dot>
            Error
          </Badge>
        )
      default:
        return <Badge variant="neutral">{statusVal}</Badge>
    }
  }

  const tables = summary?.tables || {}

  return (
    <div className="space-y-6">
      {/* Statutory Aggregation Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="glass-card p-3 border-l-4 border-l-brand-500">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 4 (B2B)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table4_b2b?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">
            Tax: {formatINR(tables.table4_b2b?.total_tax || 0)}
          </span>
        </div>

        <div className="glass-card p-3 border-l-4 border-l-pink-400">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 5 (B2CL)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table5_b2cl?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">
            Tax: {formatINR(tables.table5_b2cl?.total_tax || 0)}
          </span>
        </div>

        <div className="glass-card p-3 border-l-4 border-l-sky-500">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 7 (B2CS)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table7_b2cs?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">
            Tax: {formatINR(tables.table7_b2cs?.total_tax || 0)}
          </span>
        </div>

        <div className="glass-card p-3 border-l-4 border-l-emerald-500">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 6A (Exp)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table6a_exports?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">Zero-Rated</span>
        </div>

        <div className="glass-card p-3 border-l-4 border-l-amber-500">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 9B (CDNR)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table9b_cdnr?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">
            Tax: {formatINR(tables.table9b_cdnr?.total_tax || 0)}
          </span>
        </div>

        <div className="glass-card p-3 border-l-4 border-l-slate-400">
          <span className="text-2xs font-semibold text-slate-500 uppercase block">Table 8 (Nil)</span>
          <span className="text-sm font-bold text-slate-800 block mt-1">
            {formatINR(tables.table8_nil_exempt?.taxable_value || 0)}
          </span>
          <span className="text-2xs text-slate-400 mt-0.5 block">Exempt Supplies</span>
        </div>
      </div>

      {/* Control & Filter Toolbar */}
      <div className="glass-panel p-4 flex flex-col md:flex-row md:items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Search */}
          <div className="relative min-w-[200px]">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search invoice or customer..."
              className="glass-input text-xs pl-8 pr-3 py-1.5 rounded-lg w-full"
            />
          </div>

          {/* Type Filter */}
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="glass-input text-xs px-2.5 py-1.5 rounded-lg"
          >
            <option value="ALL">All Supply Types</option>
            <option value="B2B">B2B (Regular)</option>
            <option value="B2CL">B2C Large (&gt; 2.5L)</option>
            <option value="B2CS">B2C Small</option>
            <option value="EXPORT">Exports</option>
            <option value="CDNR">Credit / Debit Notes</option>
            <option value="NIL_EXEMPT">Nil / Exempt</option>
          </select>

          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="glass-input text-xs px-2.5 py-1.5 rounded-lg"
          >
            <option value="ALL">All Validations</option>
            <option value="VALID">Compliant (Valid)</option>
            <option value="WARNING">Warnings</option>
            <option value="ERROR">Errors</option>
          </select>
        </div>

        <div className="flex items-center gap-2">
          {onExportClick && (
            <Button
              size="sm"
              variant="secondary"
              icon={<Download className="w-3.5 h-3.5" />}
              onClick={onExportClick}
            >
              Export Summary
            </Button>
          )}
          <Button
            size="sm"
            variant="primary"
            icon={<Plus className="w-4 h-4" />}
            disabled={isLocked}
            onClick={onAddInvoiceClick}
          >
            Add Sales Invoice
          </Button>
        </div>
      </div>

      {/* Invoices Table */}
      {filteredInvoices.length === 0 ? (
        <EmptyState
          title="No Sales Invoices Found"
          description={
            invoices.length === 0
              ? "No outward sales invoices have been added for this filing period yet. Click 'Add Sales Invoice' to create one."
              : 'No invoices match the selected filter criteria.'
          }
        />
      ) : (
        <div className="glass-table-container overflow-x-auto shadow-xs rounded-xl border border-white/80">
          <table className="w-full text-left text-xs">
            <thead className="bg-pink-50/50 text-slate-600 font-semibold border-b border-pink-100/80">
              <tr>
                <th className="py-3 px-4">Invoice # & Date</th>
                <th className="py-3 px-4">Customer & GSTIN</th>
                <th className="py-3 px-4">Type & POS</th>
                <th className="py-3 px-4 text-right">Taxable Value</th>
                <th className="py-3 px-4 text-right">Tax Amount</th>
                <th className="py-3 px-4 text-right">Total Amount</th>
                <th className="py-3 px-4 text-center">Status</th>
                <th className="py-3 px-4 text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white/70">
              {filteredInvoices.map((inv) => {
                const taxAmt =
                  Number(inv.cgst_amount || 0) +
                  Number(inv.sgst_amount || 0) +
                  Number(inv.igst_amount || 0) +
                  Number(inv.cess_amount || 0)

                return (
                  <tr
                    key={inv.id}
                    className="hover:bg-brand-50/30 transition-colors cursor-pointer"
                    onClick={() => onSelectInvoice(inv)}
                  >
                    <td className="py-3 px-4">
                      <span className="font-mono font-semibold text-slate-800 block">
                        {inv.invoice_number}
                      </span>
                      <span className="text-2xs text-slate-400">{inv.invoice_date}</span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="font-medium text-slate-800 block truncate max-w-[180px]">
                        {inv.customer_name}
                      </span>
                      <span className="font-mono text-2xs text-slate-400">
                        {inv.customer_gstin || 'B2C / Unregistered'}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-block px-2 py-0.5 rounded text-2xs font-semibold bg-pink-100/70 text-brand-800 mr-1.5">
                        {inv.invoice_type}
                      </span>
                      <span className="text-2xs text-slate-500 font-mono">POS: {inv.place_of_supply}</span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-medium text-slate-700">
                      {formatINR(inv.taxable_value)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-slate-600">
                      {formatINR(taxAmt)}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-slate-900">
                      {formatINR(inv.total_amount)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      {getValidationBadge(inv.validation_status)}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <button
                        onClick={(e) => {
                          e.stopPropagation()
                          onSelectInvoice(inv)
                        }}
                        className="p-1 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-brand-50 transition-colors cursor-pointer"
                        title="View Details"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
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
