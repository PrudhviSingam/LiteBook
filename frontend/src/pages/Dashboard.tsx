import React, { useEffect, useState } from 'react'
import {
  ArrowLeftRight,
  Clock,
  AlertTriangle,
  FileSpreadsheet,
  FolderOpen,
  Sparkles,
  ShieldAlert,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  History,
  AlertCircle,
  RefreshCw,
  FileCheck2,
  UploadCloud,
} from 'lucide-react'
import { Button } from '../components/ui/Button'
import type { DashboardSummaryData, ModuleId } from '../types'
import { getDashboardSummary, getDocumentDownloadUrl } from '../services/api'
import { formatINR } from '../utils/formatters'
import { DeveloperCard } from '../components/DeveloperCard'

interface DashboardProps {
  onNavigate: (module: ModuleId) => void
}

export const Dashboard: React.FC<DashboardProps> = ({ onNavigate }) => {
  const [data, setData] = useState<DashboardSummaryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setErrorMessage(null)
    try {
      const res = await getDashboardSummary()
      setData(res)
    } catch (err: any) {
      setErrorMessage(err.message || 'Unable to load dashboard data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
    const handleReset = () => {
      loadData()
    }
    window.addEventListener('workspace:documents_reset', handleReset)
    return () => window.removeEventListener('workspace:documents_reset', handleReset)
  }, [])

  const getGreeting = () => {
    const hour = new Date().getHours()
    if (hour < 12) return 'Good morning'
    if (hour < 18) return 'Good afternoon'
    return 'Good evening'
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

  return (
    <div className="space-y-6 pb-12">
      {/* 1. SaaS Command Center Top Section */}
      <div className="glass-panel p-6 sm:p-7 flex flex-col md:flex-row md:items-center justify-between gap-6 relative overflow-hidden border border-white/90">
        <div className="max-w-xl relative z-10">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200/60 mb-2.5 shadow-2xs">
            <Sparkles className="w-3.5 h-3.5 text-brand-500" />
            <span>Autonomous Accounting Engine</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight font-sans">
            {getGreeting()}, {data?.user_name || 'Accountant'}
          </h1>
          <p className="mt-1 text-xs sm:text-sm text-slate-500 leading-relaxed">
            Here is your financial workspace at a glance. Continuous variance deduction and audit reconciliation active.
          </p>
        </div>

        {/* System Health / Status indicator */}
        <div className="flex items-center gap-2 self-start md:self-auto bg-white/70 px-3 py-2 rounded-2xl border border-slate-200/60 shadow-2xs">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
          </span>
          <div className="text-[11px] leading-tight">
            <span className="font-bold text-slate-800 block">Ledger Guard Active</span>
            <span className="text-slate-400">Zero data discrepancies ignored</span>
          </div>
        </div>
      </div>

      {/* Error state */}
      {errorMessage && (
        <div className="p-4 rounded-2xl bg-rose-50/90 border border-rose-200 text-rose-800 text-xs flex items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={loadData}
            className="px-3 py-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold transition-colors flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            Retry
          </button>
        </div>
      )}

      {/* Quick Actions Bar */}
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Quick Actions
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <button
            onClick={() => onNavigate('documents')}
            className="glass-card glass-card-hover p-3.5 flex items-center gap-3 text-left group cursor-pointer border border-white/80"
          >
            <div className="w-9 h-9 rounded-xl bg-pink-50 text-pink-700 flex items-center justify-center shrink-0 border border-pink-100 group-hover:scale-105 transition-transform shadow-2xs">
              <UploadCloud className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-slate-800 block group-hover:text-brand-700 transition-colors truncate">
                Upload Document
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                Bank & ledger files
              </span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('reconciliation')}
            className="glass-card glass-card-hover p-3.5 flex items-center gap-3 text-left group cursor-pointer border border-white/80"
          >
            <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center shrink-0 border border-brand-100 group-hover:scale-105 transition-transform shadow-2xs">
              <ArrowLeftRight className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-slate-800 block group-hover:text-brand-700 transition-colors truncate">
                Start Reconciliation
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                Automated matching
              </span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('review-center')}
            className="glass-card glass-card-hover p-3.5 flex items-center gap-3 text-left group cursor-pointer border border-white/80"
          >
            <div className="w-9 h-9 rounded-xl bg-rose-50 text-rose-600 flex items-center justify-center shrink-0 border border-rose-100 group-hover:scale-105 transition-transform shadow-2xs">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-slate-800 block group-hover:text-brand-700 transition-colors truncate">
                Review Findings
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                Variance audit queue
              </span>
            </div>
          </button>

          <button
            onClick={() => onNavigate('ai-assistant')}
            className="glass-card glass-card-hover p-3.5 flex items-center gap-3 text-left group cursor-pointer border border-white/80"
          >
            <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-600 flex items-center justify-center shrink-0 border border-purple-100 group-hover:scale-105 transition-transform shadow-2xs">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="min-w-0">
              <span className="text-xs font-bold text-slate-800 block group-hover:text-brand-700 transition-colors truncate">
                Open AI Assistant
              </span>
              <span className="text-[10px] text-slate-400 block truncate">
                Forensic explanations
              </span>
            </div>
          </button>
        </div>
      </div>

      {/* 4 Top Metric Cards (Linear & Stripe Clarity) */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Documents */}
        <div
          onClick={() => onNavigate('documents')}
          className="glass-card glass-card-hover p-5 cursor-pointer flex flex-col justify-between"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Documents
            </span>
            <div className="w-9 h-9 rounded-xl bg-slate-100/70 border border-slate-200/80 flex items-center justify-center text-slate-700 shadow-2xs">
              <FolderOpen className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 block tracking-tight font-sans">
              {loading ? '...' : (data?.total_documents ?? 0)}
            </span>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100/70 text-[11px]">
              <span className="text-slate-500">
                {data?.analyzed_documents ? `${data.analyzed_documents} analyzed` : 'Awaiting data'}
              </span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded text-[10px]">
                {data?.total_documents ? 'Active' : 'Empty'}
              </span>
            </div>
          </div>
        </div>

        {/* Metric 2: Reconciliation */}
        <div
          onClick={() => onNavigate('reconciliation')}
          className="glass-card glass-card-hover p-5 cursor-pointer flex flex-col justify-between"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Reconciliation
            </span>
            <div className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-200/80 flex items-center justify-center text-brand-600 shadow-2xs">
              <ArrowLeftRight className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 block tracking-tight font-sans">
              {loading ? '...' : (data?.reconciliations ?? 0)}
            </span>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100/70 text-[11px]">
              <span className="text-slate-500">
                {data?.reconciliation_needs_review ? `${data.reconciliation_needs_review} batches review` : 'No active batches'}
              </span>
              <span className="text-slate-600 font-medium bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">
                Tolerance ±1D
              </span>
            </div>
          </div>
        </div>

        {/* Metric 3: Review Required */}
        <div
          onClick={() => onNavigate('review-center')}
          className="glass-card glass-card-hover p-5 cursor-pointer flex flex-col justify-between border-brand-200/60"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-brand-700">
              Review Required
            </span>
            <div className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-200/80 flex items-center justify-center text-brand-600 shadow-2xs">
              <AlertTriangle className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl sm:text-3xl font-extrabold text-brand-600 block tracking-tight font-sans">
              {loading ? '...' : (data?.needs_review_count ?? 0)}
            </span>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100/70 text-[11px]">
              <span className="text-brand-600/90 font-medium">
                {data?.high_severity_count ? `${data.high_severity_count} high severity` : 'All items reviewed'}
              </span>
              <span className="text-brand-700 font-semibold bg-brand-50 px-1.5 py-0.5 rounded text-[10px]">
                Auditor Action
              </span>
            </div>
          </div>
        </div>

        {/* Metric 4: Tax & Compliance */}
        <div
          onClick={() => onNavigate('gst')}
          className="glass-card glass-card-hover p-5 cursor-pointer flex flex-col justify-between border-slate-200/80"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Tax & Compliance
            </span>
            <div className="w-9 h-9 rounded-xl bg-emerald-50 border border-emerald-200/80 flex items-center justify-center text-emerald-600 shadow-2xs">
              <FileCheck2 className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3">
            <span className="text-2xl sm:text-3xl font-extrabold text-slate-900 block tracking-tight font-sans">
              {loading ? '...' : (data?.total_documents ? 'Audit Ready' : 'Awaiting data')}
            </span>
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-100/70 text-[11px]">
              <span className="text-slate-500">
                GST & ITR Workspaces
              </span>
              <span className="text-emerald-700 font-semibold bg-emerald-50 px-1.5 py-0.5 rounded text-[10px]">
                Compliant
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Dashboard Responsive Grid: 2/3 Content, 1/3 Activity Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left 2/3 Section: Financial Overview & Priority Findings */}
        <div className="lg:col-span-8 space-y-6">
          {/* Priority Financial Findings */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h2 className="text-base font-extrabold text-slate-900 tracking-tight">
                  Financial Overview
                </h2>
                <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-100 text-brand-800">
                  Priority Issues
                </span>
              </div>
              <button
                onClick={() => onNavigate('review-center')}
                className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center gap-1 cursor-pointer transition-colors"
              >
                Open Review Center <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {loading ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {[1, 2].map((i) => (
                  <div key={i} className="h-32 glass-card animate-pulse" />
                ))}
              </div>
            ) : !data?.needs_attention_items || data.needs_attention_items.length === 0 ? (
              <div className="p-8 text-center glass-card border-dashed border-slate-200">
                <CheckCircle2 className="w-9 h-9 text-emerald-500 mx-auto mb-2" />
                <h3 className="text-sm font-bold text-slate-800">No financial discrepancies detected</h3>
                <p className="text-xs text-slate-500 mt-1 max-w-sm mx-auto leading-relaxed">
                  All detected variances and ledger transactions are currently reviewed. Upload a bank statement or general ledger to begin new analysis.
                </p>
                <div className="mt-4">
                  <Button
                    variant="outline"
                    size="sm"
                    icon={<UploadCloud className="w-3.5 h-3.5" />}
                    onClick={() => onNavigate('documents')}
                  >
                    Upload Document
                  </Button>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {data.needs_attention_items.map((item) => (
                  <div
                    key={item.id}
                    onClick={() => onNavigate('review-center')}
                    className="glass-card glass-card-hover p-4 cursor-pointer flex flex-col justify-between group"
                  >
                    <div>
                      <div className="flex items-center justify-between gap-2 mb-2">
                        {getSeverityBadge(item.severity)}
                        <span className="text-[10px] font-mono text-slate-500 bg-white/70 px-1.5 py-0.5 rounded border border-slate-200/60">
                          {item.cell_address || item.finding_type}
                        </span>
                      </div>
                      <h3 className="text-xs font-bold text-slate-900 group-hover:text-brand-700 transition-colors line-clamp-1">
                        {item.title}
                      </h3>
                      <p className="text-xs text-slate-500 mt-1 flex items-center gap-1.5">
                        <FileSpreadsheet className="w-3 h-3 text-slate-400 shrink-0" />
                        <span className="truncate">{item.document_name}</span>
                        {item.financial_period && (
                          <span className="text-[10px] text-slate-400">({item.financial_period})</span>
                        )}
                      </p>
                    </div>

                    <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
                      <div>
                        <span className="text-[10px] text-slate-400 block font-medium">Variance / Difference</span>
                        <span className="text-xs font-bold text-rose-700 font-mono">
                          {item.difference ? formatINR(item.difference) : 'Discrepancy'}
                        </span>
                      </div>
                      <span className="inline-flex items-center gap-1 text-xs font-bold text-brand-600 group-hover:translate-x-0.5 transition-transform">
                        Review <ChevronRight className="w-3.5 h-3.5" />
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Recent Documents Table Card */}
          <div className="glass-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Recent Documents</h2>
                <p className="text-xs text-slate-500">Real financial files processed in your account</p>
              </div>
              <button
                onClick={() => onNavigate('documents')}
                className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center gap-0.5 cursor-pointer"
              >
                View all <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-14 glass rounded-xl animate-pulse" />
                ))}
              </div>
            ) : !data?.recent_documents_list || data.recent_documents_list.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                <FolderOpen className="w-8 h-8 mx-auto mb-2 text-slate-300" />
                <p className="font-semibold text-slate-700 text-sm">No financial documents yet</p>
                <p className="mt-1">Upload an Excel statement or ledger to begin analysis.</p>
                <div className="mt-3">
                  <Button
                    variant="primary"
                    size="sm"
                    icon={<UploadCloud className="w-3.5 h-3.5" />}
                    onClick={() => onNavigate('documents')}
                  >
                    Upload Statement
                  </Button>
                </div>
              </div>
            ) : (
              <div className="divide-y divide-slate-100/80">
                {data.recent_documents_list.map((doc) => (
                  <div
                    key={doc.id}
                    className="py-3 flex items-center justify-between gap-3 hover:bg-white/60 rounded-xl px-2 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 shrink-0 shadow-2xs">
                        <FileSpreadsheet className="w-4 h-4" />
                      </div>
                      <div className="min-w-0">
                        <span className="text-xs font-bold text-slate-800 truncate block">
                          {doc.original_filename}
                        </span>
                        <span className="text-[11px] text-slate-400 block">
                          {doc.document_type} • {doc.created_at}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-2 shrink-0">
                      {doc.findings_count > 0 && (
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                          {doc.findings_count} findings
                        </span>
                      )}
                      <a
                        href={getDocumentDownloadUrl(doc.id)}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-white transition-colors"
                        title="Download file"
                      >
                        <ExternalLink className="w-3.5 h-3.5" />
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right 1/3 Section: Recent Activity & Platform Developer Info */}
        <div className="lg:col-span-4 space-y-6">
          {/* Recent Activity Card */}
          <div className="glass-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-bold text-slate-900">Recent Activity</h2>
                <p className="text-xs text-slate-500">Audit logs & engine actions</p>
              </div>
              <button
                onClick={() => onNavigate('history')}
                className="text-xs font-bold text-brand-600 hover:text-brand-700 flex items-center gap-0.5 cursor-pointer"
              >
                History <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>

            {loading ? (
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="h-12 glass rounded-xl animate-pulse" />
                ))}
              </div>
            ) : !data?.recent_activities || data.recent_activities.length === 0 ? (
              <div className="p-8 text-center text-slate-400 text-xs">
                <History className="w-7 h-7 mx-auto mb-2 text-slate-300" />
                <p className="font-semibold text-slate-700">No recent activity</p>
                <p className="mt-0.5">Actions performed in LiteBooks will be recorded here.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-100/80">
                {data.recent_activities.map((act) => (
                  <div key={act.id} className="py-2.5 flex items-start justify-between gap-3 text-xs">
                    <div className="flex items-start gap-2.5 min-w-0">
                      <div className="w-6 h-6 rounded-full bg-slate-100/90 text-slate-600 flex items-center justify-center shrink-0 mt-0.5 border border-slate-200/60">
                        <Clock className="w-3 h-3" />
                      </div>
                      <div className="min-w-0">
                        <span className="font-bold text-slate-800 block truncate">
                          {act.result_summary || act.target_name}
                        </span>
                        <span className="text-[11px] text-slate-400 block mt-0.5">
                          {act.user_action || act.action.replace('_', ' ')}
                        </span>
                      </div>
                    </div>

                    <span className="text-[10px] text-slate-400 whitespace-nowrap shrink-0 font-mono">
                      {new Date(act.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Platform Engineering & Developer Card */}
          <div className="glass-card p-4 space-y-2.5 border border-white/90">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Platform Engineering
            </span>
            <DeveloperCard
              name="Singam Prudhviswar Reddy"
              role="Core Platform Engineer"
              email="singamprudhviswerreddy@gmail.com"
              avatarUrl="/assets/singam-profile.png"
              compact={false}
              className="border-0 shadow-none p-0 bg-transparent"
            />
          </div>
        </div>
      </div>
    </div>
  )
}
