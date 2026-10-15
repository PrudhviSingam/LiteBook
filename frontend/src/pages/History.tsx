import React, { useEffect, useState } from 'react'
import {
  Clock,
  Search,
  ArrowLeftRight,
  FileSpreadsheet,
  TrendingUp,
  FolderOpen,
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { EmptyState } from '../components/ui/EmptyState'
import type { HistoryRecord } from '../types'
import { getHistory } from '../services/api'
import { formatDate } from '../utils/formatters'

export const HistoryPage: React.FC = () => {
  const [history, setHistory] = useState<HistoryRecord[]>([])
  const [selectedModule, setSelectedModule] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchLogs = async () => {
    setLoading(true)
    const records = await getHistory(selectedModule)
    setHistory(records)
    setLoading(false)
  }

  useEffect(() => {
    fetchLogs()
  }, [selectedModule])

  const filteredHistory = history.filter(
    (item) =>
      item.target_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (item.result_summary &&
        item.result_summary.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  const modules = [
    { id: 'all', label: 'All Modules' },
    { id: 'review_center', label: 'Review Center' },
    { id: 'reconciliation', label: 'Reconciliation' },
    { id: 'documents', label: 'Documents' },
  ]

  const getModuleIcon = (moduleName: string) => {
    switch (moduleName) {
      case 'review_center':
        return <ShieldAlert className="w-4 h-4 text-brand-600" />
      case 'reconciliation':
        return <ArrowLeftRight className="w-4 h-4 text-brand-500" />
      case 'gst':
        return <FileSpreadsheet className="w-4 h-4 text-emerald-500" />
      case 'financial_statements':
        return <TrendingUp className="w-4 h-4 text-sky-500" />
      case 'documents':
        return <FolderOpen className="w-4 h-4 text-amber-500" />
      default:
        return <Clock className="w-4 h-4 text-slate-500" />
    }
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Header Info Card */}
      <div className="glass-panel p-6 border border-white/90 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-200/70">
          <div>
            <h1 className="text-base font-extrabold text-slate-900 tracking-tight">
              Audit Trail & Action History
            </h1>
            <p className="text-xs text-slate-500">
              Immutable ledger activity log tracking calculations, reconciliations, document uploads, and accountant decisions.
            </p>
          </div>

          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search action logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 pr-3 py-1.5 text-xs glass-input focus:bg-white text-slate-800 w-full sm:w-64 font-sans"
            />
          </div>
        </div>

        {/* Module Filters */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-3 border-b border-slate-100 no-scrollbar">
          {modules.map((m) => (
            <button
              key={m.id}
              onClick={() => setSelectedModule(m.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                selectedModule === m.id
                  ? 'bg-brand-50 text-brand-700 border border-brand-200/80 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-white/60'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>

        {/* Logs Timeline */}
        <div className="mt-4">
          {loading ? (
            <div className="space-y-3 py-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 glass rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : filteredHistory.length === 0 ? (
            <EmptyState
              icon={<Clock className="w-8 h-8" />}
              title="No action logs recorded"
              description="Actions taken in LiteBooks will be immutably recorded in this audit timeline."
            />
          ) : (
            <div className="space-y-3">
              {filteredHistory.map((item) => (
                <div
                  key={item.id}
                  className="glass-card p-4 hover:bg-white/85 transition-all flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="flex items-start sm:items-center gap-3 min-w-0">
                    <div className="w-9 h-9 rounded-xl bg-brand-50/80 border border-brand-100 flex items-center justify-center shrink-0 shadow-2xs">
                      {getModuleIcon(item.module)}
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-900 text-xs sm:text-sm truncate">
                          {item.target_name}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-600">
                          {item.user_action || item.action.replace('_', ' ')}
                        </span>
                      </div>
                      {item.result_summary && (
                        <p className="text-xs text-slate-500 mt-0.5 truncate">
                          {item.result_summary}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 self-end sm:self-auto text-right">
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                      <ShieldCheck className="w-3 h-3 text-emerald-600" />
                      Verified
                    </span>
                    <span className="text-[11px] font-mono text-slate-400">
                      {formatDate(item.created_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
