import React from 'react'
import {
  LayoutDashboard,
  ShieldAlert,
  ArrowLeftRight,
  Receipt,
  FileCheck2,
  TrendingUp,
  Sparkles,
  Files,
  Clock,
  Settings,
  ShieldCheck,
  LogOut,
} from 'lucide-react'
import type { ModuleId } from '../../types'
import { cn } from '../../utils/cn'
import { DeveloperCard } from '../DeveloperCard'

interface SidebarProps {
  activeModule: ModuleId
  onSelectModule: (module: ModuleId) => void
  onCloseMobile?: () => void
  onLogout?: () => void
}

interface NavItem {
  id: ModuleId
  label: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

export const navItems: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'reconciliation', label: 'Reconciliation', icon: ArrowLeftRight },
  { id: 'review-center', label: 'Review Center', icon: ShieldAlert },
  { id: 'gst', label: 'GST Returns', icon: Receipt },
  { id: 'itr', label: 'ITR Returns', icon: FileCheck2 },
  { id: 'financial-statements', label: 'Financial Statements', icon: TrendingUp },
  { id: 'ai-assistant', label: 'AI Assistant', icon: Sparkles },
  { id: 'documents', label: 'Documents', icon: Files },
  { id: 'history', label: 'History', icon: Clock },
]

export const Sidebar: React.FC<SidebarProps> = ({
  activeModule,
  onSelectModule,
  onCloseMobile,
  onLogout,
}) => {
  return (
    <aside className="w-[260px] glass-sidebar rounded-2xl flex flex-col h-full select-none overflow-hidden transition-all duration-200">
      {/* Brand Header */}
      <div className="h-16 flex items-center px-5 border-b border-slate-200/60 shrink-0 bg-white/40">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-600 to-brand-500 text-white flex items-center justify-center font-extrabold text-base shadow-sm shadow-brand-500/25 ring-2 ring-white/90">
            L
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-extrabold text-slate-800 text-base tracking-tight font-sans">
                LiteBooks
              </span>
              <span className="text-[10px] font-bold text-brand-600 bg-brand-50 border border-brand-200/70 px-1 rounded-sm">
                ai
              </span>
            </div>
            <span className="text-[10px] font-medium text-slate-400 block -mt-0.5 tracking-tight">
              Autonomous Accounting
            </span>
          </div>
        </div>
      </div>

      {/* Main Navigation List */}
      <div className="flex-1 py-3 px-3 overflow-y-auto space-y-1">
        <div className="px-3 pb-2 pt-1">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
            Workspace
          </span>
        </div>

        {navItems.map((item) => {
          const Icon = item.icon
          const isActive = activeModule === item.id

          return (
            <button
              key={item.id}
              onClick={() => {
                onSelectModule(item.id)
                onCloseMobile?.()
              }}
              className={cn(
                'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 group text-left cursor-pointer',
                isActive
                  ? 'bg-pink-50 text-pink-700 border border-pink-100 shadow-sm font-bold'
                  : 'text-slate-600 hover:text-slate-900 hover:bg-white/60 hover:border hover:border-slate-200/50'
              )}
            >
              <div className="flex items-center gap-2.5">
                <div
                  className={cn(
                    'w-6 h-6 rounded-lg flex items-center justify-center transition-colors',
                    isActive
                      ? 'bg-brand-500/10 text-brand-600'
                      : 'text-slate-400 group-hover:text-slate-600'
                  )}
                >
                  <Icon className="w-4 h-4" />
                </div>
                <span>{item.label}</span>
              </div>

              {isActive ? (
                <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0 shadow-xs shadow-brand-500/50" />
              ) : item.id === 'review-center' ? (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-brand-100 text-brand-700">
                  Audit
                </span>
              ) : null}
            </button>
          )
        })}
      </div>

      {/* Bottom Section: Settings & DeveloperCard */}
      <div className="p-3 border-t border-slate-200/60 bg-white/40 space-y-2 shrink-0">
        {/* Settings Navigation Item */}
        <button
          onClick={() => {
            onSelectModule('settings')
            onCloseMobile?.()
          }}
          className={cn(
            'w-full flex items-center justify-between px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 group text-left cursor-pointer',
            activeModule === 'settings'
              ? 'bg-pink-50 text-pink-700 border border-pink-100 shadow-sm font-bold'
              : 'text-slate-600 hover:text-slate-900 hover:bg-white/60 hover:border hover:border-slate-200/50'
          )}
        >
          <div className="flex items-center gap-2.5">
            <div
              className={cn(
                'w-6 h-6 rounded-lg flex items-center justify-center transition-colors',
                activeModule === 'settings'
                  ? 'bg-brand-500/10 text-brand-600'
                  : 'text-slate-400 group-hover:text-slate-600'
              )}
            >
              <Settings className="w-4 h-4" />
            </div>
            <span>Settings</span>
          </div>

          {activeModule === 'settings' && (
            <span className="w-1.5 h-1.5 rounded-full bg-brand-500 shrink-0 shadow-xs shadow-brand-500/50" />
          )}
        </button>

        {/* User Session Row */}
        <div className="flex items-center justify-between p-2 rounded-xl bg-white/70 border border-slate-200/70 shadow-2xs">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-brand-100 to-brand-50 text-brand-700 border border-brand-200/60 flex items-center justify-center font-bold text-[11px] shrink-0 shadow-2xs">
              PA
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs font-bold text-slate-800 truncate">
                Accountant
              </p>
              <p className="text-[9px] text-slate-400 truncate flex items-center gap-1">
                <ShieldCheck className="w-2.5 h-2.5 text-emerald-500 inline shrink-0" /> Verified
              </p>
            </div>
          </div>
          {onLogout && (
            <button
              onClick={onLogout}
              title="Sign Out"
              className="p-1 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50/80 transition cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        {/* Compact Developer Card in Sidebar */}
        <DeveloperCard variant="sidebar" className="shadow-none border-slate-200/60 bg-white/80" />
      </div>
    </aside>
  )
}
