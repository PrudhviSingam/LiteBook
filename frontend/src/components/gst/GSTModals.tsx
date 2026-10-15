import React, { useState } from 'react'
import { X, CheckCircle2, Upload, Lock } from 'lucide-react'
import { Button } from '../ui/Button'
import type { GSTPeriodStatus } from '../../types/gst'

// ---------------------------------------------------------------------------
// 1. Add GST Registration Modal
// ---------------------------------------------------------------------------

interface AddRegistrationModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: {
    gstin: string
    legal_name: string
    trade_name?: string
    state_code: string
    registration_type?: string
    authorized_signatory?: string
  }) => Promise<void>
}

export const AddRegistrationModal: React.FC<AddRegistrationModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [gstin, setGstin] = useState('')
  const [legalName, setLegalName] = useState('')
  const [tradeName, setTradeName] = useState('')
  const [stateCode, setStateCode] = useState('27')
  const [signatory, setSignatory] = useState('')
  const [regType, setRegType] = useState('REGULAR')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handleGstinChange = (val: string) => {
    const clean = val.toUpperCase().trim()
    setGstin(clean)
    if (clean.length >= 2 && !isNaN(Number(clean.slice(0, 2)))) {
      setStateCode(clean.slice(0, 2))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!gstin || gstin.length !== 15) {
      setErrorMsg('GSTIN must be exactly 15 alphanumeric characters.')
      return
    }
    if (!legalName) {
      setErrorMsg('Legal Name is required.')
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      await onSubmit({
        gstin,
        legal_name: legalName,
        trade_name: tradeName || undefined,
        state_code: stateCode,
        registration_type: regType,
        authorized_signatory: signatory || undefined,
      })
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create registration.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-md bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <h3 className="text-base font-bold text-slate-800">Add GST Registration</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-50 text-rose-800 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              GSTIN (15 Digits) *
            </label>
            <input
              type="text"
              required
              maxLength={15}
              value={gstin}
              onChange={(e) => handleGstinChange(e.target.value)}
              placeholder="e.g. 27AABCT3518Q1ZV"
              className="glass-input w-full text-xs p-2.5 rounded-lg font-mono uppercase"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Legal Business Name *
            </label>
            <input
              type="text"
              required
              value={legalName}
              onChange={(e) => setLegalName(e.target.value)}
              placeholder="e.g. Acme Enterprises Private Limited"
              className="glass-input w-full text-xs p-2.5 rounded-lg"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                State Code (2 Digits) *
              </label>
              <input
                type="text"
                required
                maxLength={2}
                value={stateCode}
                onChange={(e) => setStateCode(e.target.value)}
                placeholder="27"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Registration Type
              </label>
              <select
                value={regType}
                onChange={(e) => setRegType(e.target.value)}
                className="glass-input w-full text-xs p-2.5 rounded-lg"
              >
                <option value="REGULAR">Regular</option>
                <option value="COMPOSITION">Composition</option>
                <option value="SEZ">SEZ Unit / Developer</option>
              </select>
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Trade Name (Optional)
            </label>
            <input
              type="text"
              value={tradeName}
              onChange={(e) => setTradeName(e.target.value)}
              placeholder="e.g. Acme Tech"
              className="glass-input w-full text-xs p-2.5 rounded-lg"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Authorized Signatory
            </label>
            <input
              type="text"
              value={signatory}
              onChange={(e) => setSignatory(e.target.value)}
              placeholder="e.g. Rajesh Kumar"
              className="glass-input w-full text-xs p-2.5 rounded-lg"
            />
          </div>

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isSubmitting}>
              Add Registration
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 2. Add Filing Period Modal
// ---------------------------------------------------------------------------

interface AddPeriodModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (data: { period: string; financial_year: string }) => Promise<void>
}

export const AddPeriodModal: React.FC<AddPeriodModalProps> = ({ isOpen, onClose, onSubmit }) => {
  const [period, setPeriod] = useState('2024-04')
  const [fy, setFy] = useState('2024-25')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handlePeriodChange = (val: string) => {
    setPeriod(val)
    if (/^\d{4}-\d{2}$/.test(val)) {
      const year = parseInt(val.slice(0, 4), 10)
      const month = parseInt(val.slice(5, 7), 10)
      const fyStart = month >= 4 ? year : year - 1
      const fyEnd = (fyStart + 1) % 100
      setFy(`${fyStart}-${fyEnd.toString().padStart(2, '0')}`)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!/^\d{4}-\d{2}$/.test(period)) {
      setErrorMsg('Period must follow format YYYY-MM (e.g. 2024-04)')
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      await onSubmit({ period, financial_year: fy })
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to create period.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-sm bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <h3 className="text-base font-bold text-slate-800">Add Return Filing Period</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-50 text-rose-800 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Filing Period (Month) *
            </label>
            <input
              type="month"
              required
              value={period}
              onChange={(e) => handlePeriodChange(e.target.value)}
              className="glass-input w-full text-xs p-2.5 rounded-lg"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Financial Year
            </label>
            <input
              type="text"
              required
              value={fy}
              onChange={(e) => setFy(e.target.value)}
              placeholder="2024-25"
              className="glass-input w-full text-xs p-2.5 rounded-lg"
            />
          </div>

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isSubmitting}>
              Create Period
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 3. Add Sales Invoice Modal
// ---------------------------------------------------------------------------

interface AddSalesInvoiceModalProps {
  isOpen: boolean
  registrationStateCode: string
  onClose: () => void
  onSubmit: (data: any) => Promise<void>
}

export const AddSalesInvoiceModal: React.FC<AddSalesInvoiceModalProps> = ({
  isOpen,
  registrationStateCode,
  onClose,
  onSubmit,
}) => {
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0])
  const [customerGstin, setCustomerGstin] = useState('')
  const [customerName, setCustomerName] = useState('')
  const [placeOfSupply, setPlaceOfSupply] = useState(registrationStateCode || '27')
  const [invoiceType, setInvoiceType] = useState('B2B')
  const [taxableValue, setTaxableValue] = useState('')
  const [taxRate, setTaxRate] = useState('18.00')
  const [hsnCode, setHsnCode] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handleCustomerGstinChange = (val: string) => {
    const clean = val.toUpperCase().trim()
    setCustomerGstin(clean)
    if (clean.length >= 2 && !isNaN(Number(clean.slice(0, 2)))) {
      setPlaceOfSupply(clean.slice(0, 2))
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!invoiceNumber) {
      setErrorMsg('Invoice Number is required.')
      return
    }
    if (!taxableValue || isNaN(Number(taxableValue)) || Number(taxableValue) < 0) {
      setErrorMsg('Please enter a valid taxable amount.')
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      await onSubmit({
        invoice_number: invoiceNumber,
        invoice_date: invoiceDate,
        customer_gstin: customerGstin || undefined,
        customer_name: customerName || 'Retail Customer',
        place_of_supply: placeOfSupply,
        invoice_type: invoiceType,
        taxable_value: taxableValue,
        tax_rate: taxRate,
        hsn_code: hsnCode || undefined,
        auto_calculate_tax: true,
      })
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to add invoice.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-lg bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <h3 className="text-base font-bold text-slate-800">Add Sales Invoice</h3>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-50 text-rose-800 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Invoice Number *
              </label>
              <input
                type="text"
                required
                value={invoiceNumber}
                onChange={(e) => setInvoiceNumber(e.target.value)}
                placeholder="INV-2024-001"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Invoice Date *
              </label>
              <input
                type="date"
                required
                value={invoiceDate}
                onChange={(e) => setInvoiceDate(e.target.value)}
                className="glass-input w-full text-xs p-2.5 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Customer GSTIN
              </label>
              <input
                type="text"
                maxLength={15}
                value={customerGstin}
                onChange={(e) => handleCustomerGstinChange(e.target.value)}
                placeholder="27ABCDE1234F1Z5"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono uppercase"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Customer Name
              </label>
              <input
                type="text"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                placeholder="Acme Client Corp"
                className="glass-input w-full text-xs p-2.5 rounded-lg"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Place of Supply *
              </label>
              <input
                type="text"
                required
                maxLength={2}
                value={placeOfSupply}
                onChange={(e) => setPlaceOfSupply(e.target.value)}
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Invoice Type
              </label>
              <select
                value={invoiceType}
                onChange={(e) => setInvoiceType(e.target.value)}
                className="glass-input w-full text-xs p-2.5 rounded-lg"
              >
                <option value="B2B">B2B</option>
                <option value="B2CL">B2C Large</option>
                <option value="B2CS">B2C Small</option>
                <option value="EXPORT">Export</option>
                <option value="CDNR">Credit / Debit Note</option>
                <option value="NIL_EXEMPT">Nil / Exempt</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                HSN Code
              </label>
              <input
                type="text"
                value={hsnCode}
                onChange={(e) => setHsnCode(e.target.value)}
                placeholder="998311"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Taxable Value (₹) *
              </label>
              <input
                type="number"
                step="0.01"
                required
                value={taxableValue}
                onChange={(e) => setTaxableValue(e.target.value)}
                placeholder="10000.00"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono"
              />
            </div>
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Tax Rate (%) *
              </label>
              <select
                value={taxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                className="glass-input w-full text-xs p-2.5 rounded-lg"
              >
                <option value="0.00">0% (Nil / Exempt)</option>
                <option value="5.00">5%</option>
                <option value="12.00">12%</option>
                <option value="18.00">18%</option>
                <option value="28.00">28%</option>
              </select>
            </div>
          </div>

          <div className="p-3 bg-pink-50/50 rounded-xl border border-pink-200/60 text-2xs text-slate-600">
            Intra-State vs Inter-State tax splits (CGST/SGST vs IGST) are deterministically calculated based on POS and Supplier state code.
          </div>

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isSubmitting}>
              Save Invoice
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 4. Import GSTR-2B Modal
// ---------------------------------------------------------------------------

interface ImportGSTR2BModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (records: any[]) => Promise<void>
}

export const ImportGSTR2BModal: React.FC<ImportGSTR2BModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
}) => {
  const [jsonText, setJsonText] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen) return null

  const handleSampleLoad = () => {
    const sample = [
      {
        supplier_gstin: '27AAPFU0939F1ZV',
        supplier_name: 'Tata Steel Limited',
        invoice_number: 'INV-2024-001',
        invoice_date: '2024-04-15',
        invoice_type: 'B2B',
        taxable_value: '25000.00',
        cgst_amount: '2250.00',
        sgst_amount: '2250.00',
        igst_amount: '0.00',
        total_amount: '29500.00',
        itc_available: true,
        filing_status: 'FILED',
      },
    ]
    setJsonText(JSON.stringify(sample, null, 2))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!jsonText.trim()) {
      setErrorMsg('Please paste GSTR-2B JSON records.')
      return
    }

    let parsed: any[]
    try {
      parsed = JSON.parse(jsonText)
      if (!Array.isArray(parsed)) {
        throw new Error('Root JSON must be an array of records.')
      }
    } catch (err: any) {
      setErrorMsg(`JSON format error: ${err.message}`)
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      await onSubmit(parsed)
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Import failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-lg bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <div className="flex items-center gap-2">
            <Upload className="w-5 h-5 text-brand-600" />
            <h3 className="text-base font-bold text-slate-800">Import GSTR-2B Portal Records</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-50 text-rose-800 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold text-slate-700">
              GSTR-2B JSON Data Array
            </label>
            <button
              type="button"
              onClick={handleSampleLoad}
              className="text-2xs font-semibold text-brand-600 hover:underline cursor-pointer"
            >
              Insert Sample Record
            </button>
          </div>

          <textarea
            required
            rows={10}
            value={jsonText}
            onChange={(e) => setJsonText(e.target.value)}
            placeholder="[{ supplier_gstin: '...', invoice_number: '...', taxable_value: '...' }]"
            className="glass-input w-full text-xs p-3 rounded-xl font-mono resize-none"
          />

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button variant="primary" size="sm" type="submit" isLoading={isSubmitting}>
              Import Records
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 5. Workflow Transition Modal (Review / Approve / File ARN / Lock)
// ---------------------------------------------------------------------------

interface TransitionModalProps {
  isOpen: boolean
  targetStatus: GSTPeriodStatus | null
  periodName: string
  onClose: () => void
  onConfirm: (notes?: string, arn?: string) => Promise<void>
}

export const TransitionModal: React.FC<TransitionModalProps> = ({
  isOpen,
  targetStatus,
  periodName,
  onClose,
  onConfirm,
}) => {
  const [notes, setNotes] = useState('')
  const [arn, setArn] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  if (!isOpen || !targetStatus) return null

  const getTitleAndDescription = () => {
    switch (targetStatus) {
      case 'under_review':
        return {
          title: 'Submit Return for Review',
          desc: `Submit period ${periodName} for formal supervisory review and audit inspection.`,
          btnText: 'Submit for Review',
          variant: 'primary' as const,
        }
      case 'approved':
        return {
          title: 'Approve GST Return',
          desc: `Approve period ${periodName} return computations as verified and ready for statutory filing.`,
          btnText: 'Approve Return',
          variant: 'primary' as const,
        }
      case 'filed':
        return {
          title: 'Record Statutory Filing',
          desc: `Record statutory submission of ${periodName} return to the GST Common Portal. Please enter the government Acknowledgement Reference Number (ARN).`,
          btnText: 'Confirm Filing',
          variant: 'primary' as const,
        }
      case 'locked':
        return {
          title: 'Lock Filing Period (Permanent)',
          desc: `Lock period ${periodName}. Once locked, no sales invoices, purchase invoices, or reconciliation decisions can be edited or deleted.`,
          btnText: 'Lock Period Permanently',
          variant: 'danger' as const,
        }
      default:
        return {
          title: 'Transition Period Status',
          desc: `Change period status to ${targetStatus}.`,
          btnText: 'Confirm',
          variant: 'primary' as const,
        }
    }
  }

  const { title, desc, btnText, variant } = getTitleAndDescription()

  const handleConfirm = async () => {
    if (targetStatus === 'filed' && !arn.trim()) {
      setErrorMsg('Filing ARN is required to mark as filed.')
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      await onConfirm(notes || undefined, arn || undefined)
      onClose()
    } catch (err: any) {
      setErrorMsg(err.message || 'Status transition failed.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-md bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <div className="flex items-center gap-2">
            {targetStatus === 'locked' ? (
              <Lock className="w-5 h-5 text-rose-600" />
            ) : (
              <CheckCircle2 className="w-5 h-5 text-brand-600" />
            )}
            <h3 className="text-base font-bold text-slate-800">{title}</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-lg bg-rose-50 text-rose-800 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <p className="text-xs text-slate-600 leading-relaxed">{desc}</p>

          {targetStatus === 'filed' && (
            <div>
              <label className="text-xs font-semibold text-slate-700 block mb-1">
                Filing ARN (Acknowledgement Reference Number) *
              </label>
              <input
                type="text"
                required
                value={arn}
                onChange={(e) => setArn(e.target.value)}
                placeholder="e.g. AA2705240019284"
                className="glass-input w-full text-xs p-2.5 rounded-lg font-mono uppercase"
              />
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              Audit Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Reason or authorization reference..."
              className="glass-input w-full text-xs p-2.5 rounded-lg resize-none"
            />
          </div>

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" onClick={onClose}>
              Cancel
            </Button>
            <Button variant={variant} size="sm" onClick={handleConfirm} isLoading={isSubmitting}>
              {btnText}
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// 6. Upload & Import GST File Modal (Excel, CSV, JSON)
// ---------------------------------------------------------------------------

interface UploadGSTFileModalProps {
  isOpen: boolean
  periodId: string | number | null
  periodName: string
  isLocked: boolean
  onClose: () => void
  onUploadSuccess: (result: { message: string; file_type: string; imported_count: number }) => void
}

export const UploadGSTFileModal: React.FC<UploadGSTFileModalProps> = ({
  isOpen,
  periodId,
  periodName,
  isLocked,
  onClose,
  onUploadSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [targetType, setTargetType] = useState('auto')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  if (!isOpen) return null

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0])
      setErrorMsg(null)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setSelectedFile(e.dataTransfer.files[0])
      setErrorMsg(null)
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!periodId) {
      setErrorMsg('Please select a valid filing period first.')
      return
    }
    if (isLocked) {
      setErrorMsg('This filing period is locked and cannot accept new file imports.')
      return
    }
    if (!selectedFile) {
      setErrorMsg('Please select a file to upload.')
      return
    }

    setIsSubmitting(true)
    setErrorMsg(null)
    try {
      const { uploadGSTFile } = await import('../../services/gstApi')
      const res = await uploadGSTFile(periodId, selectedFile, targetType)
      if (res.success) {
        onUploadSuccess({
          message: res.message,
          file_type: res.file_type,
          imported_count: res.imported_count,
        })
        onClose()
      } else {
        setErrorMsg(res.message || 'Import failed. No records were imported.')
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'File upload failed. Please verify format.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
      <div className="glass-modal w-full max-w-lg bg-white/95 rounded-2xl shadow-2xl border border-white/90 overflow-hidden">
        <div className="p-5 border-b border-slate-200/80 flex items-center justify-between bg-gradient-to-r from-pink-50/50 via-white to-pink-50/20">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-200/80">
              <Upload className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-slate-900">Upload GST Accounting File</h3>
              <p className="text-2xs text-slate-500">Period: {periodName || 'Active Period'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-50 text-rose-900 border border-rose-200 text-xs">
              {errorMsg}
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-slate-700 block mb-1">
              File Category & Format
            </label>
            <select
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
              className="glass-input w-full text-xs p-2.5 rounded-lg font-medium text-slate-800"
            >
              <option value="auto">Auto-Detect File Content (Recommended)</option>
              <option value="sales">Sales Invoices / Outward Register (GSTR-1)</option>
              <option value="purchases">Purchase Register / Books Inward</option>
              <option value="gstr2b">GSTR-2B Portal Records for Reconciliation</option>
            </select>
          </div>

          {/* Drag & Drop Zone */}
          <div
            onDragOver={(e) => {
              e.preventDefault()
              setIsDragging(true)
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            className={`border-2 border-dashed rounded-xl p-6 text-center transition-all ${
              isDragging
                ? 'border-brand-500 bg-pink-50/50'
                : 'border-slate-300 hover:border-brand-400 bg-slate-50/50'
            }`}
          >
            <Upload className="w-8 h-8 text-brand-500 mx-auto mb-2" />
            <p className="text-xs font-semibold text-slate-700">
              {selectedFile ? selectedFile.name : 'Drag & drop Excel, CSV, or JSON file here'}
            </p>
            <p className="text-2xs text-slate-400 mt-1">
              Supported formats: .xlsx, .xls, .csv, .json (Max 10MB)
            </p>
            <label className="inline-block mt-3">
              <span className="px-3 py-1.5 bg-white border border-brand-200 text-brand-700 text-xs font-semibold rounded-lg shadow-xs hover:bg-brand-50 cursor-pointer transition-colors">
                Browse Files
              </span>
              <input
                type="file"
                accept=".xlsx,.xls,.csv,.json"
                onChange={handleFileChange}
                className="hidden"
              />
            </label>
          </div>

          <div className="p-3 bg-pink-50/40 rounded-xl border border-pink-200/60 text-2xs text-slate-600 space-y-1">
            <p className="font-semibold text-brand-900">Deterministic Processing Note:</p>
            <p>
              Invoices are validated with statutory GSTIN checks, place of supply (POS) verification,
              and automatic intra-state (CGST+SGST) vs inter-state (IGST) tax calculation.
            </p>
          </div>

          <div className="pt-3 border-t border-slate-200/80 flex items-center justify-end gap-2">
            <Button variant="secondary" size="sm" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              type="submit"
              disabled={!selectedFile || isLocked}
              isLoading={isSubmitting}
            >
              Upload & Import
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

