import React, { useState } from 'react'
import {
  User,
  ShieldCheck,
  FileSpreadsheet,
  Bell,
  Sparkles,
  Lock,
  Check,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Button } from '../components/ui/Button'
import { DeveloperCard } from '../components/DeveloperCard'

export const SettingsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | 'documents' | 'preferences'>('profile')
  const [savedMessage, setSavedMessage] = useState<string | null>(null)

  const handleSave = () => {
    setSavedMessage('Settings updated successfully.')
    setTimeout(() => setSavedMessage(null), 3000)
  }

  return (
    <div className="space-y-6 max-w-5xl pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
          Settings
        </h1>
        <p className="text-xs sm:text-sm text-slate-500 mt-1">
          Manage your accountant profile, workspace security, and document verification preferences.
        </p>
      </div>

      {/* Settings Glass Tabs */}
      <div className="flex border-b border-slate-200/80 gap-6 text-xs font-bold text-slate-500 overflow-x-auto no-scrollbar">
        <button
          onClick={() => setActiveTab('profile')}
          className={`pb-3 flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'profile'
              ? 'border-b-2 border-brand-600 text-brand-700 font-extrabold'
              : 'hover:text-slate-800'
          }`}
        >
          <User className="w-4 h-4" /> Account
        </button>
        <button
          onClick={() => setActiveTab('security')}
          className={`pb-3 flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'security'
              ? 'border-b-2 border-brand-600 text-brand-700 font-extrabold'
              : 'hover:text-slate-800'
          }`}
        >
          <ShieldCheck className="w-4 h-4" /> Security
        </button>
        <button
          onClick={() => setActiveTab('documents')}
          className={`pb-3 flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'documents'
              ? 'border-b-2 border-brand-600 text-brand-700 font-extrabold'
              : 'hover:text-slate-800'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" /> Application
        </button>
        <button
          onClick={() => setActiveTab('preferences')}
          className={`pb-3 flex items-center gap-1.5 transition-all cursor-pointer whitespace-nowrap ${
            activeTab === 'preferences'
              ? 'border-b-2 border-brand-600 text-brand-700 font-extrabold'
              : 'hover:text-slate-800'
          }`}
        >
          <Sparkles className="w-4 h-4" /> Preferences
        </button>
      </div>

      {savedMessage && (
        <div className="p-3.5 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center gap-2">
          <Check className="w-4 h-4 text-emerald-600 shrink-0" />
          <span>{savedMessage}</span>
        </div>
      )}

      {/* Tab: Account Profile */}
      {activeTab === 'profile' && (
        <div className="glass-panel p-6 space-y-6 border border-white/90">
          <div>
            <h3 className="text-sm font-bold text-slate-800">Accountant Profile</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Personal and firm credentials used for audit logs and verification reports.
            </p>
          </div>

          <div className="flex items-center gap-4 p-4 rounded-2xl bg-white/70 border border-slate-200/70 shadow-2xs">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-brand-600 to-brand-500 text-white font-extrabold flex items-center justify-center text-lg shadow-sm">
              PA
            </div>
            <div>
              <h4 className="text-base font-bold text-slate-900">Partner Accountant</h4>
              <p className="text-xs text-slate-500">accountant@litebooks.ai</p>
              <div className="mt-2 flex items-center gap-2">
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-100 text-brand-800">
                  Principal Signer
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 text-emerald-800">
                  Active Member
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                Full Name
              </label>
              <input
                type="text"
                defaultValue="Partner Accountant"
                className="w-full glass-input px-3 py-2 text-xs text-slate-800 font-sans"
              />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
                Firm / Practice Name
              </label>
              <input
                type="text"
                defaultValue="LiteBooks Financial Associates"
                className="w-full glass-input px-3 py-2 text-xs text-slate-800 font-sans"
              />
            </div>
          </div>

          <div className="flex justify-end pt-2">
            <Button variant="primary" size="sm" onClick={handleSave}>
              Save Profile
            </Button>
          </div>
        </div>
      )}

      {/* Tab: Security */}
      {activeTab === 'security' && (
        <div className="glass-panel p-6 space-y-6 border border-white/90">
          <div>
            <h3 className="text-sm font-bold text-slate-800">Workspace Security</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Two-factor authentication, cryptographic signatures, and audit tracking.
            </p>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70 flex items-center justify-between shadow-2xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                  <Lock className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Session Encryption</h4>
                  <p className="text-[11px] text-slate-500">JSON Web Tokens with HS256 deterministic signatures</p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Enabled
              </span>
            </div>

            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70 flex items-center justify-between shadow-2xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Document Hash Fingerprint</h4>
                  <p className="text-[11px] text-slate-500">SHA-256 integrity digest stored with each uploaded workbook</p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Active
              </span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Application */}
      {activeTab === 'documents' && (
        <div className="glass-panel p-6 space-y-6 border border-white/90">
          <div>
            <h3 className="text-sm font-bold text-slate-800">Application Formatting & Standards</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Default currency display, financial year conventions, and tolerance rules.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70">
              <span className="text-slate-400 font-medium block">Default Currency</span>
              <span className="text-sm font-bold text-slate-800 mt-1 block">Indian Rupee (INR — ₹ Lakhs / Crores)</span>
            </div>
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70">
              <span className="text-slate-400 font-medium block">Financial Year Cycle</span>
              <span className="text-sm font-bold text-slate-800 mt-1 block">April 1 – March 31 (Indian Standard)</span>
            </div>
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70">
              <span className="text-slate-400 font-medium block">Reconciliation Date Tolerance</span>
              <span className="text-sm font-bold text-slate-800 mt-1 block">± 1 Day Standard Bank Float</span>
            </div>
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70">
              <span className="text-slate-400 font-medium block">Amount Tolerance</span>
              <span className="text-sm font-bold text-slate-800 mt-1 block">₹0.00 (Exact Currency Matching)</span>
            </div>
          </div>
        </div>
      )}

      {/* Tab: Preferences */}
      {activeTab === 'preferences' && (
        <div className="glass-panel p-6 space-y-6 border border-white/90">
          <div>
            <h3 className="text-sm font-bold text-slate-800">AI Assistant & Notification Preferences</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Configure assistant explanations and audit alerts.
            </p>
          </div>

          <div className="space-y-4">
            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70 flex items-center justify-between shadow-2xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                  <Sparkles className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Forensic Anomaly Explanations</h4>
                  <p className="text-[11px] text-slate-500">Provide root cause deduction for financial variances</p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Enabled
              </span>
            </div>

            <div className="p-4 rounded-2xl bg-white/70 border border-slate-200/70 flex items-center justify-between shadow-2xs">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-brand-50 text-brand-600 flex items-center justify-center">
                  <Bell className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-xs font-bold text-slate-800">Critical Variance Alerts</h4>
                  <p className="text-[11px] text-slate-500">Highlight balance sheet imbalances in the Review Center</p>
                </div>
              </div>
              <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                Enabled
              </span>
            </div>
          </div>
        </div>
      )}

      {/* About & Engineering Section */}
      <div className="pt-4 border-t border-slate-200/60 space-y-2">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
          About LiteBooks & Engineering
        </h3>
        <DeveloperCard
          name="Singam Prudhviswar Reddy"
          role="Core Platform Engineer"
          email="singamprudhviswerreddy@gmail.com"
          avatarUrl="/assets/singam-profile.png"
        />
      </div>
    </div>
  )
}
