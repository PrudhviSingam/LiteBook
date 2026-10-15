import React, { useState, useEffect, useId } from 'react'
import {
  FileText,
  UploadCloud,
  CheckCircle2,
  AlertTriangle,
  ArrowRight,
  TrendingUp,
  Download,
  ShieldCheck,
  RefreshCw,
  Plus,
  Scale,
  Building2,
  Briefcase,
  Home,
  Coins,
  Percent,
  Receipt,
  FileCheck2,
  ExternalLink,
  ChevronRight,
  Info,
  X,
} from 'lucide-react'
import {
  fetchITRProfiles,
  createITRProfile,
  fetchITRIncomes,
  addITRIncome,
  fetchITRDeductions,
  addITRDeduction,
  fetchITRTaxCredits,
  addITRTaxCredit,
  calculateITR,
  fetchITRRegimeComparison,
  transitionITRStatus,
  uploadITRFile,
  downloadITRReport,
  updateITRProfile,
} from '../services/itrApi'
import type {
  ITRProfile,
  ITRIncomeEntry,
  ITRDeductionEntry,
  ITRTaxCreditEntry,
  ITRRegimeComparison,
  ITRFinding,
  ITRRegime,
} from '../types/itr'

interface ITRPageProps {
  onNavigate?: (module: string) => void
}

export const ITRPage: React.FC<ITRPageProps> = ({ onNavigate }) => {
  const panInputId = useId()
  const nameInputId = useId()
  const ayInputId = useId()
  const headInputId = useId()
  const subcatInputId = useId()
  const amountInputId = useId()
  const docInputId = useId()
  const sectionInputId = useId()
  const dedDescInputId = useId()
  const claimedInputId = useId()
  const creditTypeInputId = useId()
  const deductorInputId = useId()
  const creditAmountInputId = useId()

  const [profiles, setProfiles] = useState<ITRProfile[]>([])
  const [selectedProfileId, setSelectedProfileId] = useState<number | null>(null)
  const [activeProfile, setActiveProfile] = useState<ITRProfile | null>(null)

  const [activeTab, setActiveTab] = useState<'comparison' | 'income' | 'deductions' | 'credits' | 'findings'>('comparison')
  const [comparison, setComparison] = useState<ITRRegimeComparison | null>(null)
  const [incomes, setIncomes] = useState<ITRIncomeEntry[]>([])
  const [deductions, setDeductions] = useState<ITRDeductionEntry[]>([])
  const [credits, setCredits] = useState<ITRTaxCreditEntry[]>([])

  const [isLoading, setIsLoading] = useState(false)
  const [isCalculating, setIsCalculating] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [successMsg, setSuccessMsg] = useState<string | null>(null)

  // Modals
  const [isCreateProfileOpen, setIsCreateProfileOpen] = useState(false)
  const [isUploadOpen, setIsUploadOpen] = useState(false)
  const [isAddIncomeOpen, setIsAddIncomeOpen] = useState(false)
  const [isAddDeductionOpen, setIsAddDeductionOpen] = useState(false)
  const [isAddCreditOpen, setIsAddCreditOpen] = useState(false)

  // Form states
  const [newPan, setNewPan] = useState('')
  const [newName, setNewName] = useState('')
  const [newAY, setNewAY] = useState('2024-25')

  const [incHead, setIncHead] = useState<any>('SALARY')
  const [incSubcat, setIncSubcat] = useState('BASIC_SALARY')
  const [incDesc, setIncDesc] = useState('')
  const [incAmount, setIncAmount] = useState('')
  const [incDoc, setIncDoc] = useState('')

  const [dedSection, setDedSection] = useState('80C')
  const [dedDesc, setDedDesc] = useState('')
  const [dedAmount, setDedAmount] = useState('')

  const [credType, setCredType] = useState<any>('TDS_SALARY')
  const [credDeductor, setCredDeductor] = useState('')
  const [credAmount, setCredAmount] = useState('')

  // Load profiles on mount
  useEffect(() => {
    loadProfiles()
  }, [])

  const loadProfiles = async () => {
    setIsLoading(true)
    setErrorMsg(null)
    try {
      const data = await fetchITRProfiles()
      setProfiles(data)
      if (data.length > 0 && !selectedProfileId) {
        setSelectedProfileId(data[0].id)
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load ITR profiles')
    } finally {
      setIsLoading(false)
    }
  }

  // Load profile details when selection changes
  useEffect(() => {
    if (!selectedProfileId) return
    const prof = profiles.find((p) => p.id === selectedProfileId) || null
    setActiveProfile(prof)
    loadProfileData(selectedProfileId)
  }, [selectedProfileId, profiles])

  const loadProfileData = async (profId: number) => {
    setErrorMsg(null)
    try {
      const [compRes, incRes, dedRes, credRes] = await Promise.all([
        fetchITRRegimeComparison(profId).catch(() => null),
        fetchITRIncomes(profId).catch(() => []),
        fetchITRDeductions(profId).catch(() => []),
        fetchITRTaxCredits(profId).catch(() => []),
      ])
      setComparison(compRes)
      setIncomes(incRes)
      setDeductions(dedRes)
      setCredits(credRes)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to load ITR data')
    }
  }

  const handleRunCalculation = async () => {
    if (!selectedProfileId) return
    setIsCalculating(true)
    setErrorMsg(null)
    try {
      const res = await calculateITR(selectedProfileId)
      setComparison(res)
      await loadProfiles()
      setSuccessMsg('Deterministic tax calculation completed for both Old and New regimes.')
      setTimeout(() => setSuccessMsg(null), 4000)
    } catch (err: any) {
      setErrorMsg(err.message || 'Calculation failed.')
    } finally {
      setIsCalculating(false)
    }
  }

  const handleSelectRegime = async (regime: ITRRegime) => {
    if (!selectedProfileId) return
    try {
      await updateITRProfile(selectedProfileId, { selected_regime: regime })
      await loadProfiles()
      setSuccessMsg(`Tax regime explicitly set to ${regime === 'NEW' ? 'New Regime (Sec 115BAC)' : 'Old Regime'}.`)
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to update regime')
    }
  }

  const handleApproveReturn = async () => {
    if (!selectedProfileId) return
    setErrorMsg(null)
    try {
      await transitionITRStatus(selectedProfileId, 'APPROVED', 'Approved by authorized accountant')
      await loadProfiles()
      setSuccessMsg('ITR return approved successfully.')
      setTimeout(() => setSuccessMsg(null), 4000)
    } catch (err: any) {
      setErrorMsg(err.message || 'Approval blocked by safety validation.')
    }
  }

  const handleCreateProfileSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newPan || !newName) return
    try {
      const created = await createITRProfile({
        pan: newPan.toUpperCase().trim(),
        taxpayer_name: newName.trim(),
        assessment_year: newAY,
        financial_year: newAY === '2024-25' ? '2023-24' : '2024-25',
        selected_regime: 'UNDECIDED',
      })
      await loadProfiles()
      setSelectedProfileId(created.id)
      setIsCreateProfileOpen(false)
      setNewPan('')
      setNewName('')
      setSuccessMsg('ITR Profile created successfully.')
      setTimeout(() => setSuccessMsg(null), 3000)
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create profile')
    }
  }

  const handleAddIncomeSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProfileId || !incAmount) return
    try {
      await addITRIncome(selectedProfileId, {
        head_of_income: incHead,
        subcategory: incSubcat,
        description: incDesc || `${incHead} Income`,
        gross_amount: parseFloat(incAmount),
        source_document: incDoc || undefined,
        verification_status: incDoc ? 'VERIFIED' : 'REVIEW_REQUIRED',
      })
      await loadProfileData(selectedProfileId)
      setIsAddIncomeOpen(false)
      setIncAmount('')
      setIncDesc('')
      setIncDoc('')
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add income')
    }
  }

  const handleAddDeductionSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProfileId || !dedAmount) return
    try {
      await addITRDeduction(selectedProfileId, {
        section: dedSection,
        description: dedDesc || `Deduction under Section ${dedSection}`,
        claimed_amount: parseFloat(dedAmount),
        eligible_amount: parseFloat(dedAmount),
        status: 'VERIFIED',
      })
      await loadProfileData(selectedProfileId)
      setIsAddDeductionOpen(false)
      setDedAmount('')
      setDedDesc('')
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add deduction')
    }
  }

  const handleAddCreditSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedProfileId || !credAmount) return
    try {
      await addITRTaxCredit(selectedProfileId, {
        credit_type: credType,
        deductor_or_bank: credDeductor || undefined,
        credit_amount: parseFloat(credAmount),
        verification_status: 'VERIFIED',
      })
      await loadProfileData(selectedProfileId)
      setIsAddCreditOpen(false)
      setCredAmount('')
      setCredDeductor('')
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add tax credit')
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!selectedProfileId || !e.target.files || e.target.files.length === 0) return
    const file = e.target.files[0]
    setIsLoading(true)
    setErrorMsg(null)
    try {
      const res = await uploadITRFile(selectedProfileId, file)
      await loadProfileData(selectedProfileId)
      setIsUploadOpen(false)
      setSuccessMsg(res.message || 'File imported successfully.')
      setTimeout(() => setSuccessMsg(null), 4000)
    } catch (err: any) {
      setErrorMsg(err.message || 'File upload failed')
    } finally {
      setIsLoading(false)
    }
  }

  // Format real currency values cleanly without fake numbers
  const formatRealVal = (val: any) => {
    if (val === null || val === undefined || val === '') return '—'
    const num = typeof val === 'number' ? val : parseFloat(val)
    if (isNaN(num)) return '—'
    return `₹${num.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  const chosenComp = activeProfile?.selected_regime === 'NEW' ? comparison?.new_regime : comparison?.old_regime

  return (
    <div className="space-y-6 max-w-7xl mx-auto py-6 px-4 sm:px-6">
      {/* ------------------------------------------------------------------ */}
      {/* Statutory Header & Profile Context                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold bg-brand-50 text-brand-700 border border-brand-200/80 shadow-2xs">
              <FileCheck2 className="w-3.5 h-3.5 text-brand-600" />
              Direct Tax Intelligence
            </span>
            {activeProfile?.status && (
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold border shadow-2xs ${
                  activeProfile.status === 'APPROVED'
                    ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                    : activeProfile.status === 'REVIEW_REQUIRED'
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-slate-100 text-slate-700 border-slate-200'
                }`}
              >
                {activeProfile.status === 'APPROVED' ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                {activeProfile.status}
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
            ITR Returns
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Autonomous statutory tax preparation, Old vs New regime evaluation & accountant sign-off.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center flex-wrap gap-2.5">
          <select
            value={selectedProfileId || ''}
            onChange={(e) => setSelectedProfileId(Number(e.target.value))}
            className="px-3 py-2 bg-white/80 border border-slate-200/80 rounded-xl text-xs font-semibold text-slate-700 shadow-2xs focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          >
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.taxpayer_name} ({p.pan}) — AY {p.assessment_year}
              </option>
            ))}
          </select>

          <button
            onClick={() => setIsCreateProfileOpen(true)}
            className="btn-secondary text-xs px-3 py-2 inline-flex items-center gap-1.5"
          >
            <Plus className="w-3.5 h-3.5" />
            New Taxpayer Profile
          </button>

          <button
            onClick={() => setIsUploadOpen(true)}
            disabled={!selectedProfileId || activeProfile?.status === 'APPROVED'}
            className="btn-secondary text-xs px-3 py-2 inline-flex items-center gap-1.5 disabled:opacity-50"
          >
            <UploadCloud className="w-3.5 h-3.5 text-brand-600" />
            Upload Source Files
          </button>

          <button
            onClick={handleRunCalculation}
            disabled={!selectedProfileId || isCalculating || activeProfile?.status === 'APPROVED'}
            className="btn-primary text-xs px-3.5 py-2 inline-flex items-center gap-1.5 shadow-sm disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isCalculating ? 'animate-spin' : ''}`} />
            {isCalculating ? 'Calculating...' : 'Calculate Tax'}
          </button>

          <button
            onClick={() => selectedProfileId && downloadITRReport(selectedProfileId)}
            disabled={!selectedProfileId}
            className="btn-secondary text-xs px-3 py-2 inline-flex items-center gap-1.5 text-slate-700 hover:text-brand-600"
            title="Download ITR Preparation Report"
          >
            <Download className="w-3.5 h-3.5" />
            Export Report
          </button>

          {activeProfile?.status !== 'APPROVED' ? (
            <button
              onClick={handleApproveReturn}
              disabled={!selectedProfileId || !comparison?.eligible_for_approval}
              className="px-3.5 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold inline-flex items-center gap-1.5 shadow-sm disabled:opacity-40 disabled:cursor-not-allowed transition-all"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              Approve Return
            </button>
          ) : (
            <span className="px-3 py-2 bg-emerald-100/80 border border-emerald-300 text-emerald-800 rounded-xl text-xs font-bold inline-flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              Approved & Locked
            </span>
          )}
        </div>
      </div>

      {/* Notifications */}
      {errorMsg && (
        <div className="p-3.5 rounded-2xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
            <span>{errorMsg}</span>
          </div>
          <button onClick={() => setErrorMsg(null)} className="text-rose-500 hover:text-rose-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {successMsg && (
        <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs flex items-center justify-between shadow-2xs">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{successMsg}</span>
          </div>
          <button onClick={() => setSuccessMsg(null)} className="text-emerald-500 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* Statutory Disclaimer & Preparation Notice                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="glass-panel p-3.5 border-l-4 border-l-brand-500 bg-white/70 flex items-start gap-3">
        <Info className="w-4 h-4 text-brand-600 mt-0.5 shrink-0" />
        <div className="text-xs text-slate-600">
          <span className="font-bold text-slate-800">Statutory Notice:</span> LiteBooks provides deterministic computation and accountant review for statutory income tax preparation. This statement is strictly for internal verification and taxpayer sign-off; it has <span className="font-bold text-slate-800">not</span> been submitted to the Income Tax Department.
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Visible 7-Step Workflow Stepper                                    */}
      {/* ------------------------------------------------------------------ */}
      <div className="glass-panel p-4 border border-white/90">
        <div className="flex items-center justify-between overflow-x-auto gap-2 pb-1">
          {[
            { step: 1, title: 'Upload Files', desc: 'Form 16 / CSV / JSON', active: Boolean(incomes.length || deductions.length) },
            { step: 2, title: 'Extract Data', desc: 'Parse provenance', active: Boolean(incomes.length || deductions.length) },
            { step: 3, title: 'Classify Heads', desc: '5 Income Heads', active: Boolean(incomes.length) },
            { step: 4, title: 'Deductions & TDS', desc: 'Chapter VI-A / Credits', active: Boolean(deductions.length || credits.length) },
            { step: 5, title: 'Calculate Tax', desc: 'Dual Regimes', active: Boolean(comparison) },
            { step: 6, title: 'Review Issues', desc: 'Review Center', active: Boolean(comparison) },
            { step: 7, title: 'Accountant Sign-Off', desc: 'Approved return', active: activeProfile?.status === 'APPROVED' },
          ].map((s, idx) => (
            <div key={s.step} className="flex items-center gap-2 shrink-0">
              <div
                className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs ${
                  s.active
                    ? 'bg-brand-600 text-white shadow-xs'
                    : 'bg-slate-100 text-slate-400 border border-slate-200'
                }`}
              >
                {s.active ? <CheckCircle2 className="w-3.5 h-3.5" /> : s.step}
              </div>
              <div className="text-left">
                <div className={`text-xs font-bold leading-tight ${s.active ? 'text-slate-800' : 'text-slate-400'}`}>
                  {s.title}
                </div>
                <div className="text-[10px] text-slate-400">{s.desc}</div>
              </div>
              {idx < 6 && <ChevronRight className="w-3.5 h-3.5 text-slate-300 ml-1 shrink-0" />}
            </div>
          ))}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* 7 Summary Cards (REAL Calculated Values Only)                      */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Gross Income</div>
          <div className="text-base sm:text-lg font-black text-slate-900 mt-1 truncate">
            {formatRealVal(chosenComp?.gross_total_income)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Sum of 5 heads</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Deductions</div>
          <div className="text-base sm:text-lg font-black text-slate-900 mt-1 truncate">
            {formatRealVal(chosenComp?.total_deductions)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Chapter VI-A allowed</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Taxable Income</div>
          <div className="text-base sm:text-lg font-black text-brand-600 mt-1 truncate">
            {formatRealVal(chosenComp?.total_taxable_income)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Rounded u/s 288A</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">TDS / TCS</div>
          <div className="text-base sm:text-lg font-black text-slate-900 mt-1 truncate">
            {formatRealVal(chosenComp ? Number(chosenComp.tds_total) + Number(chosenComp.tcs_total) : null)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Form 26AS credits</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Tax Liability</div>
          <div className="text-base sm:text-lg font-black text-slate-900 mt-1 truncate">
            {formatRealVal(chosenComp?.total_tax_liability)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Incl. 4% cess</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">Total Tax Paid</div>
          <div className="text-base sm:text-lg font-black text-slate-900 mt-1 truncate">
            {formatRealVal(chosenComp?.total_taxes_paid)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">TDS + Adv + Self</div>
        </div>

        <div className="glass-panel p-3.5 border border-white/90">
          <div className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
            {chosenComp && Number(chosenComp.net_payable_or_refund) < 0 ? 'Refund Due' : 'Net Tax Payable'}
          </div>
          <div
            className={`text-base sm:text-lg font-black mt-1 truncate ${
              chosenComp && Number(chosenComp.net_payable_or_refund) < 0 ? 'text-emerald-600' : 'text-rose-600'
            }`}
          >
            {formatRealVal(chosenComp ? Math.abs(Number(chosenComp.net_payable_or_refund)) : null)}
          </div>
          <div className="text-[10px] text-slate-400 mt-0.5">Final balance</div>
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Navigation Tabs                                                    */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex border-b border-slate-200/80 gap-6">
        {[
          { key: 'comparison', label: 'Old vs New Regime Comparison', icon: Scale },
          { key: 'income', label: `Income Breakdown (${incomes.length})`, icon: Briefcase },
          { key: 'deductions', label: `Chapter VI-A Deductions (${deductions.length})`, icon: Receipt },
          { key: 'credits', label: `Tax Credits & TDS (${credits.length})`, icon: Coins },
          { key: 'findings', label: `Review Center (${comparison?.unresolved_findings_count || 0})`, icon: AlertTriangle },
        ].map((tab) => {
          const Icon = tab.icon
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              className={`pb-3 text-xs sm:text-sm font-bold inline-flex items-center gap-2 border-b-2 transition-all ${
                isActive
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-slate-500 hover:text-slate-800'
              }`}
            >
              <Icon className="w-4 h-4" />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* TAB 1: Dual Regime Side-by-Side Comparison                         */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === 'comparison' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Old Regime Card */}
            <div
              className={`glass-panel p-6 border transition-all ${
                activeProfile?.selected_regime === 'OLD'
                  ? 'ring-2 ring-brand-500 border-brand-300 shadow-md bg-white/90'
                  : 'border-white/90 bg-white/60'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Traditional Framework</span>
                  <h3 className="text-lg font-black text-slate-900">Old Tax Regime</h3>
                </div>
                {activeProfile?.selected_regime === 'OLD' ? (
                  <span className="px-3 py-1 bg-brand-50 border border-brand-200 text-brand-700 text-xs font-bold rounded-full">
                    Selected Regime
                  </span>
                ) : (
                  <button
                    onClick={() => handleSelectRegime('OLD')}
                    disabled={activeProfile?.status === 'APPROVED'}
                    className="btn-secondary text-xs px-3 py-1.5"
                  >
                    Select Old Regime
                  </button>
                )}
              </div>

              <div className="space-y-3 text-xs divide-y divide-slate-100">
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Gross Total Income (GTI):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.old_regime.gross_total_income)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Standard Deduction (Salary):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.old_regime.standard_deduction)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Eligible Deductions (Chapter VI-A):</span>
                  <span className="font-bold text-emerald-700">-{formatRealVal(comparison?.old_regime.total_deductions)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-700 font-bold">Total Taxable Income (Sec 288A):</span>
                  <span className="font-extrabold text-slate-900">{formatRealVal(comparison?.old_regime.total_taxable_income)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Basic Tax (Slab Rates):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.old_regime.basic_tax)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Rebate under Section 87A:</span>
                  <span className="font-bold text-emerald-700">-{formatRealVal(comparison?.old_regime.rebate_87a)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Health & Education Cess @ 4%:</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.old_regime.cess_4_pct)}</span>
                </div>
                <div className="flex justify-between pt-2 bg-slate-50/50 p-2 rounded-xl">
                  <span className="font-bold text-slate-900">Total Tax Liability:</span>
                  <span className="font-black text-brand-600 text-sm">{formatRealVal(comparison?.old_regime.total_tax_liability)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Total Taxes Paid (TDS + Adv):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.old_regime.total_taxes_paid)}</span>
                </div>
                <div className="flex justify-between pt-2 font-bold">
                  <span className="text-slate-900">
                    {comparison && Number(comparison.old_regime.net_payable_or_refund) < 0 ? 'Refund Due:' : 'Net Tax Payable:'}
                  </span>
                  <span
                    className={
                      comparison && Number(comparison.old_regime.net_payable_or_refund) < 0 ? 'text-emerald-700' : 'text-rose-700'
                    }
                  >
                    {formatRealVal(comparison ? Math.abs(Number(comparison.old_regime.net_payable_or_refund)) : null)}
                  </span>
                </div>
              </div>
            </div>

            {/* New Regime Card (Section 115BAC) */}
            <div
              className={`glass-panel p-6 border transition-all ${
                activeProfile?.selected_regime === 'NEW'
                  ? 'ring-2 ring-brand-500 border-brand-300 shadow-md bg-white/90'
                  : 'border-white/90 bg-white/60'
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <div>
                  <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Concessional Tax Rates</span>
                  <h3 className="text-lg font-black text-slate-900">New Regime (Section 115BAC)</h3>
                </div>
                {activeProfile?.selected_regime === 'NEW' ? (
                  <span className="px-3 py-1 bg-brand-50 border border-brand-200 text-brand-700 text-xs font-bold rounded-full">
                    Selected Regime
                  </span>
                ) : (
                  <button
                    onClick={() => handleSelectRegime('NEW')}
                    disabled={activeProfile?.status === 'APPROVED'}
                    className="btn-secondary text-xs px-3 py-1.5"
                  >
                    Select New Regime
                  </button>
                )}
              </div>

              <div className="space-y-3 text-xs divide-y divide-slate-100">
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Gross Total Income (GTI):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.new_regime.gross_total_income)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Standard Deduction (Enhanced):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.new_regime.standard_deduction)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Chapter VI-A Deductions:</span>
                  <span className="font-bold text-slate-400">Disallowed (₹0.00)</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-700 font-bold">Total Taxable Income (Sec 288A):</span>
                  <span className="font-extrabold text-slate-900">{formatRealVal(comparison?.new_regime.total_taxable_income)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Basic Tax (115BAC Slabs):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.new_regime.basic_tax)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Rebate u/s 87A (Income ≤ ₹7L):</span>
                  <span className="font-bold text-emerald-700">-{formatRealVal(comparison?.new_regime.rebate_87a)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Health & Education Cess @ 4%:</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.new_regime.cess_4_pct)}</span>
                </div>
                <div className="flex justify-between pt-2 bg-slate-50/50 p-2 rounded-xl">
                  <span className="font-bold text-slate-900">Total Tax Liability:</span>
                  <span className="font-black text-brand-600 text-sm">{formatRealVal(comparison?.new_regime.total_tax_liability)}</span>
                </div>
                <div className="flex justify-between pt-2">
                  <span className="text-slate-500">Total Taxes Paid (TDS + Adv):</span>
                  <span className="font-bold text-slate-800">{formatRealVal(comparison?.new_regime.total_taxes_paid)}</span>
                </div>
                <div className="flex justify-between pt-2 font-bold">
                  <span className="text-slate-900">
                    {comparison && Number(comparison.new_regime.net_payable_or_refund) < 0 ? 'Refund Due:' : 'Net Tax Payable:'}
                  </span>
                  <span
                    className={
                      comparison && Number(comparison.new_regime.net_payable_or_refund) < 0 ? 'text-emerald-700' : 'text-rose-700'
                    }
                  >
                    {formatRealVal(comparison ? Math.abs(Number(comparison.new_regime.net_payable_or_refund)) : null)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Differential summary */}
          {comparison && (
            <div className="glass-panel p-4 border border-brand-200/60 bg-brand-50/30 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Scale className="w-5 h-5 text-brand-600" />
                <div className="text-xs">
                  <span className="font-bold text-slate-900">Regime Variance: </span>
                  Difference in tax liability between Old and New regimes is{' '}
                  <span className="font-extrabold text-brand-700">{formatRealVal(comparison.difference_in_tax)}</span>.
                  The user and accountant maintain full statutory discretion to adopt either regime.
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* TAB 2: Income Category Breakdown                                   */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === 'income' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800">Income Classified by Statutory Heads</h3>
            <button
              onClick={() => setIsAddIncomeOpen(true)}
              disabled={activeProfile?.status === 'APPROVED'}
              className="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Income Item
            </button>
          </div>

          {incomes.length === 0 ? (
            <div className="glass-panel p-8 text-center text-xs text-slate-400">
              No income entries recorded yet. Upload a Form 16 / tax document or click &apos;Add Income Item&apos;.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {incomes.map((item) => (
                <div key={item.id} className="glass-panel p-4 border border-white/90 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="px-2 py-0.5 rounded-md text-[10px] font-bold bg-slate-100 text-slate-700">
                      {item.head_of_income}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                        item.verification_status === 'VERIFIED'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {item.verification_status}
                    </span>
                  </div>
                  <div className="flex items-baseline justify-between">
                    <span className="text-sm font-black text-slate-900">{formatRealVal(item.gross_amount)}</span>
                    <span className="text-[11px] text-slate-500">{item.subcategory}</span>
                  </div>
                  <p className="text-xs text-slate-600">{item.description || 'No description provided'}</p>
                  <div className="pt-2 border-t border-slate-100 text-[10px] text-slate-400 flex items-center justify-between">
                    <span>Source: {item.source_document || 'Source not verified'}</span>
                    {item.source_row && <span>Row: {item.source_row}</span>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* TAB 3: Chapter VI-A Deductions                                     */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === 'deductions' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800">Chapter VI-A Deductions Schedule</h3>
            <button
              onClick={() => setIsAddDeductionOpen(true)}
              disabled={activeProfile?.status === 'APPROVED'}
              className="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Deduction
            </button>
          </div>

          {deductions.length === 0 ? (
            <div className="glass-panel p-8 text-center text-xs text-slate-400">
              No deductions recorded. Deductions are applicable primarily under the Old Regime.
            </div>
          ) : (
            <div className="glass-panel overflow-hidden border border-white/90">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/80 text-slate-500 font-bold border-b border-slate-200/60">
                  <tr>
                    <th className="py-2.5 px-4">Section</th>
                    <th className="py-2.5 px-4">Description</th>
                    <th className="py-2.5 px-4 text-right">Claimed</th>
                    <th className="py-2.5 px-4 text-right">Eligible</th>
                    <th className="py-2.5 px-4 text-center">Status</th>
                    <th className="py-2.5 px-4">Source Provenance</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {deductions.map((d) => (
                    <tr key={d.id} className="hover:bg-slate-50/40">
                      <td className="py-3 px-4 font-bold text-brand-700">Section {d.section}</td>
                      <td className="py-3 px-4">{d.description}</td>
                      <td className="py-3 px-4 text-right font-medium">{formatRealVal(d.claimed_amount)}</td>
                      <td className="py-3 px-4 text-right font-bold text-slate-900">{formatRealVal(d.eligible_amount)}</td>
                      <td className="py-3 px-4 text-center">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                            d.status === 'VERIFIED'
                              ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                              : 'bg-amber-50 text-amber-700 border border-amber-200'
                          }`}
                        >
                          {d.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[11px] text-slate-400">{d.source_document || 'Source not verified'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* TAB 4: Tax Credits & TDS                                           */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === 'credits' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800">TDS, TCS & Advance Tax Register</h3>
            <button
              onClick={() => setIsAddCreditOpen(true)}
              disabled={activeProfile?.status === 'APPROVED'}
              className="btn-primary text-xs px-3 py-1.5 inline-flex items-center gap-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              Add Tax Credit
            </button>
          </div>

          {credits.length === 0 ? (
            <div className="glass-panel p-8 text-center text-xs text-slate-400">
              No tax credit records found. Import Form 26AS or click &apos;Add Tax Credit&apos;.
            </div>
          ) : (
            <div className="glass-panel overflow-hidden border border-white/90">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/80 text-slate-500 font-bold border-b border-slate-200/60">
                  <tr>
                    <th className="py-2.5 px-4">Type</th>
                    <th className="py-2.5 px-4">Deductor / Bank</th>
                    <th className="py-2.5 px-4">TAN / PAN</th>
                    <th className="py-2.5 px-4 text-right">Credit Amount</th>
                    <th className="py-2.5 px-4 text-center">Status</th>
                    <th className="py-2.5 px-4">Source Document</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 text-slate-700">
                  {credits.map((c) => (
                    <tr key={c.id} className="hover:bg-slate-50/40">
                      <td className="py-3 px-4 font-bold text-slate-800">{c.credit_type}</td>
                      <td className="py-3 px-4">{c.deductor_or_bank || '—'}</td>
                      <td className="py-3 px-4 font-mono text-[11px]">{c.deductor_tan_pan || '—'}</td>
                      <td className="py-3 px-4 text-right font-black text-slate-900">{formatRealVal(c.credit_amount)}</td>
                      <td className="py-3 px-4 text-center">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          {c.verification_status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-[11px] text-slate-400">{c.source_document || 'Source not verified'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* TAB 5: Review Center Integration                                   */}
      {/* ------------------------------------------------------------------ */}
      {activeTab === 'findings' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-800">Accountant Verification Issues</h3>
              <p className="text-xs text-slate-500">
                All statutory direct-tax discrepancies automatically sync to the centralized Review Center.
              </p>
            </div>
            {onNavigate && (
              <button
                onClick={() => onNavigate('review-center')}
                className="btn-secondary text-xs px-3 py-1.5 inline-flex items-center gap-1.5 text-brand-600"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Open Central Review Center
              </button>
            )}
          </div>

          <div className="glass-panel p-6 border border-white/90 space-y-3">
            <div className="flex items-center gap-3">
              <ShieldCheck className="w-5 h-5 text-brand-600" />
              <div className="text-xs text-slate-700">
                Unresolved critical or high severity review findings strictly prevent return approval.
                Current unresolved issues: <span className="font-bold text-brand-700">{comparison?.unresolved_findings_count || 0}</span>.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MODAL 1: Create ITR Profile                                        */}
      {/* ------------------------------------------------------------------ */}
      {isCreateProfileOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="glass-panel p-6 max-w-md w-full border border-white/90 shadow-xl space-y-4 bg-white/95">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">New Taxpayer Profile</h3>
              <button onClick={() => setIsCreateProfileOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleCreateProfileSubmit} className="space-y-3 text-xs">
              <div>
                <label htmlFor={panInputId} className="block font-semibold text-slate-700 mb-1">Permanent Account Number (PAN)</label>
                <input
                  id={panInputId}
                  type="text"
                  maxLength={10}
                  placeholder="e.g. ABCDE1234F"
                  value={newPan}
                  onChange={(e) => setNewPan(e.target.value.toUpperCase())}
                  className="w-full px-3 py-2 border rounded-xl font-mono uppercase"
                  required
                />
              </div>
              <div>
                <label htmlFor={nameInputId} className="block font-semibold text-slate-700 mb-1">Taxpayer Legal Name</label>
                <input
                  id={nameInputId}
                  type="text"
                  placeholder="e.g. Rohan Sharma"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl"
                  required
                />
              </div>
              <div>
                <label htmlFor={ayInputId} className="block font-semibold text-slate-700 mb-1">Assessment Year</label>
                <select id={ayInputId} value={newAY} onChange={(e) => setNewAY(e.target.value)} className="w-full px-3 py-2 border rounded-xl">
                  <option value="2024-25">AY 2024-25 (FY 2023-24)</option>
                  <option value="2025-26">AY 2025-26 (FY 2024-25)</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setIsCreateProfileOpen(false)} className="btn-secondary text-xs px-3 py-1.5">
                  Cancel
                </button>
                <button type="submit" className="btn-primary text-xs px-4 py-1.5">
                  Create Profile
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MODAL 2: Upload Tax File                                           */}
      {/* ------------------------------------------------------------------ */}
      {isUploadOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="glass-panel p-6 max-w-md w-full border border-white/90 shadow-xl space-y-4 bg-white/95">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Upload Tax Source File</h3>
              <button onClick={() => setIsUploadOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 border-2 border-dashed border-brand-200 rounded-2xl text-center space-y-2 bg-brand-50/20">
              <UploadCloud className="w-8 h-8 text-brand-500 mx-auto" />
              <div className="text-xs font-bold text-slate-800">Drag & drop tax file or click to browse</div>
              <div className="text-[11px] text-slate-400">Supports .json and .csv files with audit provenance</div>
              <input
                type="file"
                accept=".json,.csv"
                onChange={handleFileUpload}
                className="text-xs text-slate-500 mt-2 file:mr-2 file:py-1 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100"
              />
            </div>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MODAL 3: Add Income Item                                           */}
      {/* ------------------------------------------------------------------ */}
      {isAddIncomeOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="glass-panel p-6 max-w-md w-full border border-white/90 shadow-xl space-y-4 bg-white/95">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Add Income Entry</h3>
              <button onClick={() => setIsAddIncomeOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleAddIncomeSubmit} className="space-y-3 text-xs">
              <div>
                <label htmlFor={headInputId} className="block font-semibold text-slate-700 mb-1">Head of Income</label>
                <select id={headInputId} value={incHead} onChange={(e) => setIncHead(e.target.value)} className="w-full px-3 py-2 border rounded-xl">
                  <option value="SALARY">Salary Income</option>
                  <option value="BUSINESS_PROFESSION">Business / Profession</option>
                  <option value="HOUSE_PROPERTY">House Property</option>
                  <option value="CAPITAL_GAINS">Capital Gains</option>
                  <option value="OTHER_SOURCES">Other Sources (Interest / Dividend)</option>
                </select>
              </div>
              <div>
                <label htmlFor={subcatInputId} className="block font-semibold text-slate-700 mb-1">Subcategory</label>
                <input
                  id={subcatInputId}
                  type="text"
                  placeholder="e.g. BASIC_SALARY, RENTAL"
                  value={incSubcat}
                  onChange={(e) => setIncSubcat(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label htmlFor={amountInputId} className="block font-semibold text-slate-700 mb-1">Gross Amount (INR)</label>
                <input
                  id={amountInputId}
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={incAmount}
                  onChange={(e) => setIncAmount(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl font-bold"
                  required
                />
              </div>
              <div>
                <label htmlFor={docInputId} className="block font-semibold text-slate-700 mb-1">Supporting Document (Provenance)</label>
                <input
                  id={docInputId}
                  type="text"
                  placeholder="e.g. Form16_PartB.pdf"
                  value={incDoc}
                  onChange={(e) => setIncDoc(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setIsAddIncomeOpen(false)} className="btn-secondary text-xs px-3 py-1.5">
                  Cancel
                </button>
                <button type="submit" className="btn-primary text-xs px-4 py-1.5">
                  Save Income
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MODAL 4: Add Deduction Item                                        */}
      {/* ------------------------------------------------------------------ */}
      {isAddDeductionOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="glass-panel p-6 max-w-md w-full border border-white/90 shadow-xl space-y-4 bg-white/95">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Add Chapter VI-A Deduction</h3>
              <button onClick={() => setIsAddDeductionOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleAddDeductionSubmit} className="space-y-3 text-xs">
              <div>
                <label htmlFor={sectionInputId} className="block font-semibold text-slate-700 mb-1">Section</label>
                <select id={sectionInputId} value={dedSection} onChange={(e) => setDedSection(e.target.value)} className="w-full px-3 py-2 border rounded-xl">
                  <option value="80C">Section 80C (PPF, EPF, ELSS - Max 1.5L)</option>
                  <option value="80D">Section 80D (Health Insurance)</option>
                  <option value="80CCD_1B">Section 80CCD(1B) (NPS - Max 50k)</option>
                  <option value="80G">Section 80G (Donations)</option>
                  <option value="80TTA">Section 80TTA (Savings Interest)</option>
                </select>
              </div>
              <div>
                <label htmlFor={dedDescInputId} className="block font-semibold text-slate-700 mb-1">Description</label>
                <input
                  id={dedDescInputId}
                  type="text"
                  placeholder="e.g. PPF Contribution"
                  value={dedDesc}
                  onChange={(e) => setDedDesc(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label htmlFor={claimedInputId} className="block font-semibold text-slate-700 mb-1">Claimed Amount (INR)</label>
                <input
                  id={claimedInputId}
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={dedAmount}
                  onChange={(e) => setDedAmount(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl font-bold"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setIsAddDeductionOpen(false)} className="btn-secondary text-xs px-3 py-1.5">
                  Cancel
                </button>
                <button type="submit" className="btn-primary text-xs px-4 py-1.5">
                  Save Deduction
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ------------------------------------------------------------------ */}
      {/* MODAL 5: Add Tax Credit                                            */}
      {/* ------------------------------------------------------------------ */}
      {isAddCreditOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="glass-panel p-6 max-w-md w-full border border-white/90 shadow-xl space-y-4 bg-white/95">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-bold text-slate-900">Add Tax Credit</h3>
              <button onClick={() => setIsAddCreditOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-4 h-4" />
              </button>
            </div>
            <form onSubmit={handleAddCreditSubmit} className="space-y-3 text-xs">
              <div>
                <label htmlFor={creditTypeInputId} className="block font-semibold text-slate-700 mb-1">Credit Type</label>
                <select id={creditTypeInputId} value={credType} onChange={(e) => setCredType(e.target.value)} className="w-full px-3 py-2 border rounded-xl">
                  <option value="TDS_SALARY">TDS on Salary (Sec 192)</option>
                  <option value="TDS_OTHER">TDS Other (Sec 194J, 194C, etc.)</option>
                  <option value="TCS">TCS (Sec 206C)</option>
                  <option value="ADVANCE_TAX">Advance Tax (Challan 280)</option>
                  <option value="SELF_ASSESSMENT_TAX">Self Assessment Tax</option>
                </select>
              </div>
              <div>
                <label htmlFor={deductorInputId} className="block font-semibold text-slate-700 mb-1">Deductor / Bank Name</label>
                <input
                  id={deductorInputId}
                  type="text"
                  placeholder="e.g. Employer Name"
                  value={credDeductor}
                  onChange={(e) => setCredDeductor(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl"
                />
              </div>
              <div>
                <label htmlFor={creditAmountInputId} className="block font-semibold text-slate-700 mb-1">Credit Amount (INR)</label>
                <input
                  id={creditAmountInputId}
                  type="number"
                  step="0.01"
                  placeholder="0.00"
                  value={credAmount}
                  onChange={(e) => setCredAmount(e.target.value)}
                  className="w-full px-3 py-2 border rounded-xl font-bold"
                  required
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setIsAddCreditOpen(false)} className="btn-secondary text-xs px-3 py-1.5">
                  Cancel
                </button>
                <button type="submit" className="btn-primary text-xs px-4 py-1.5">
                  Save Credit
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
