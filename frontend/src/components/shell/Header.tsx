import React from 'react'
import { Menu, Search, Bell, ShieldCheck, User } from 'lucide-react'
import type { ModuleId } from '../../types'

interface HeaderProps {
  activeModule: ModuleId
  onToggleMobileMenu: () => void
}

const moduleTitles: Record<ModuleId, { title: string; subtitle: string }> = {
  dashboard: {
    title: 'Dashboard',
    subtitle: 'Your financial workspace at a glance',
  },
  'review-center': {
    title: 'Review Center',
    subtitle: 'Audit findings and variance decision center',
  },
  reconciliation: {
    title: 'Bank Reconciliation',
    subtitle: 'Match bank statements against general ledger',
  },
  gst: {
    title: 'GST Returns',
    subtitle: 'GSTR-1, GSTR-3B & 2B automated reconciliation',
  },
  itr: {
    title: 'ITR Returns',
    subtitle: 'Income tax returns & computation review',
  },
  'financial-statements': {
    title: 'Financial Statements',
    subtitle: 'Balance Sheet, P&L, and Trial Balance generation',
  },
  'ai-assistant': {
    title: 'AI Accounting Assistant',
    subtitle: 'Deterministic ledger intelligence & Sarvam AI copilot',
  },
  documents: {
    title: 'Financial Documents',
    subtitle: 'Secure repository for ledgers and statements',
  },
  history: {
    title: 'Activity & Audit History',
    subtitle: 'Complete chronological audit trails',
  },
  settings: {
    title: 'Workspace Settings',
    subtitle: 'Accounting rules, tolerance, and profile configuration',
  },
}

export const Header: React.FC<HeaderProps> = ({
  activeModule,
  onToggleMobileMenu,
}) => {
  const current = moduleTitles[activeModule] || {
    title: 'Dashboard',
    subtitle: 'Your financial workspace',
  }

  return (
    <header className="h-16 glass-header px-4 sm:px-6 flex items-center justify-between sticky top-0 z-20 transition-all">
      {/* Left: Mobile trigger & Current Section Title */}
      <div className="flex items-center gap-3 min-w-0">
        <button
          onClick={onToggleMobileMenu}
          className="p-2 rounded-xl text-slate-500 hover:text-slate-800 hover:bg-white/60 lg:hidden cursor-pointer focus:outline-none border border-transparent hover:border-slate-200"
          aria-label="Toggle Navigation"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="min-w-0">
          <h1 className="text-sm sm:text-base font-bold text-slate-900 tracking-tight leading-tight truncate font-sans">
            {current.title}
          </h1>
          <p className="hidden sm:block text-[11px] text-slate-500 truncate">
            {current.subtitle}
          </p>
        </div>
      </div>

      {/* Right: Actions, Search, Notifications & Account */}
      <div className="flex items-center gap-2 sm:gap-2.5 shrink-0">
        {/* Search Bar */}
        <div className="hidden md:flex items-center gap-2 glass-input px-3 py-1.5 text-xs text-slate-400 w-48 lg:w-56 rounded-xl">
          <Search className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <input
            type="text"
            placeholder="Search ledgers, reports..."
            className="bg-transparent border-none outline-none text-slate-700 placeholder-slate-400 text-xs w-full font-sans"
          />
          <kbd className="hidden lg:inline-block text-[9px] font-mono bg-white/90 border border-slate-200 rounded px-1 py-0.5 text-slate-400 shadow-2xs">
            ⌘K
          </kbd>
        </div>

        {/* Notifications Button */}
        <button
          className="relative p-2 rounded-xl text-slate-500 hover:text-slate-800 bg-white/60 hover:bg-white border border-slate-200/60 shadow-2xs transition-colors cursor-pointer"
          title="Notifications & Audit Alerts"
          aria-label="Notifications"
        >
          <Bell className="w-4 h-4" />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-brand-500 ring-2 ring-white" />
        </button>

        {/* System Active Status Pill */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl text-xs font-semibold bg-emerald-50/80 text-emerald-800 border border-emerald-200/70 shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-[11px] font-sans font-medium">Engine Active</span>
        </div>

        {/* User / Account Menu Pill */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-xl bg-white/70 hover:bg-white border border-slate-200/70 shadow-2xs transition-colors cursor-pointer">
          <div className="w-6 h-6 rounded-lg bg-brand-50 text-brand-600 border border-brand-200/60 flex items-center justify-center font-bold text-[10px]">
            <User className="w-3.5 h-3.5 text-brand-600" />
          </div>
          <span className="hidden sm:inline text-xs font-bold text-slate-800">
            Accountant
          </span>
        </div>
      </div>
    </header>
  )
}
