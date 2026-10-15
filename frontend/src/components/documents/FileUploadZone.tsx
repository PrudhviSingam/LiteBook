import React, { useState, useRef } from 'react'
import { UploadCloud, FileSpreadsheet, AlertCircle, CheckCircle2, FileText } from 'lucide-react'
import { Button } from '../ui/Button'

interface FileUploadZoneProps {
  onUploadSuccess?: () => void
  onUpload: (file: File, category: string, notes?: string) => Promise<void>
}

type UploadPhase = 'idle' | 'uploading' | 'processing' | 'analyzing' | 'completed' | 'failed'

export const FileUploadZone: React.FC<FileUploadZoneProps> = ({
  onUploadSuccess,
  onUpload,
}) => {
  const [dragActive, setDragActive] = useState(false)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [category, setCategory] = useState('bank_statement')
  const [notes, setNotes] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const [uploadPhase, setUploadPhase] = useState<UploadPhase>('idle')
  const [uploadStatus, setUploadStatus] = useState<{
    type: 'success' | 'error' | null
    message: string
  }>({ type: null, message: '' })

  const inputRef = useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true)
    } else if (e.type === 'dragleave') {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0])
      setUploadPhase('idle')
      setUploadStatus({ type: null, message: '' })
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0])
      setUploadPhase('idle')
      setUploadStatus({ type: null, message: '' })
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!selectedFile) return

    setIsUploading(true)
    setUploadPhase('uploading')
    setUploadStatus({ type: null, message: '' })

    try {
      setTimeout(() => setUploadPhase('processing'), 300)
      setTimeout(() => setUploadPhase('analyzing'), 700)
      await onUpload(selectedFile, category, notes)
      setUploadPhase('completed')
      setUploadStatus({
        type: 'success',
        message: `Successfully uploaded ${selectedFile.name}`,
      })
      setSelectedFile(null)
      setNotes('')
      if (inputRef.current) inputRef.current.value = ''
      onUploadSuccess?.()
    } catch (err: any) {
      setUploadPhase('failed')
      setUploadStatus({
        type: 'error',
        message: err.message || 'Error uploading document. Please try again.',
      })
    } finally {
      setIsUploading(false)
    }
  }

  return (
    <div className="glass-panel p-6 shadow-xs border border-white/90">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
        <div>
          <h3 className="text-sm font-extrabold text-slate-900 font-sans">
            Upload Financial Document
          </h3>
          <p className="text-xs text-slate-500">
            Deterministic parsing for Bank Statements, General Ledgers, and Financial Workbooks.
          </p>
        </div>
        <div className="text-[11px] font-mono text-slate-500 bg-white/70 px-2.5 py-1 rounded-full border border-slate-200/60 self-start sm:self-auto font-medium">
          Supported: XLSX, XLS, CSV or PDF
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Drop Area */}
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          onClick={() => inputRef.current?.click()}
          className={`relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 ${
            dragActive
              ? 'border-brand-500 bg-brand-50/70 scale-[0.99]'
              : selectedFile
              ? 'border-brand-400 bg-brand-50/40'
              : 'border-slate-200/90 hover:border-brand-300 hover:bg-white/60 bg-white/30'
          }`}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,.csv,.pdf"
            onChange={handleChange}
            className="hidden"
          />

          <div className="w-12 h-12 rounded-2xl bg-brand-50 text-brand-600 flex items-center justify-center mb-3 shadow-xs border border-brand-100/80">
            {selectedFile ? (
              <FileSpreadsheet className="w-6 h-6" />
            ) : (
              <UploadCloud className="w-6 h-6" />
            )}
          </div>

          {selectedFile ? (
            <div>
              <p className="text-sm font-bold text-slate-800">
                {selectedFile.name}
              </p>
              <p className="text-xs text-slate-500 mt-0.5">
                {(selectedFile.size / 1024).toFixed(1)} KB • Click or drop another file to change
              </p>
            </div>
          ) : (
            <div>
              <p className="text-sm font-bold text-slate-800">
                Drop your financial file here, or <span className="text-brand-600 underline">browse</span>
              </p>
              <p className="text-xs text-slate-400 mt-1 font-medium">
                XLSX, XLS, CSV or PDF
              </p>
            </div>
          )}
        </div>

        {/* Upload Lifecycle Progress Indicator */}
        {isUploading && (
          <div className="p-3 rounded-xl bg-white/80 border border-brand-100 flex items-center justify-between text-xs shadow-2xs">
            <span className="font-semibold text-slate-700 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-brand-500 animate-ping" />
              Upload Lifecycle
            </span>
            <div className="flex items-center gap-2 text-[10px] font-bold uppercase tracking-wider">
              {['uploading', 'processing', 'analyzing', 'completed'].map((stage, idx) => {
                const isCurrent = uploadPhase === stage
                const isPast =
                  (stage === 'uploading' && uploadPhase !== 'idle') ||
                  (stage === 'processing' && (uploadPhase === 'analyzing' || uploadPhase === 'completed')) ||
                  (stage === 'analyzing' && uploadPhase === 'completed')

                return (
                  <span
                    key={stage}
                    className={`px-2 py-0.5 rounded-full ${
                      isCurrent
                        ? 'bg-brand-500 text-white animate-pulse'
                        : isPast
                        ? 'bg-emerald-100 text-emerald-800'
                        : 'bg-slate-100 text-slate-400'
                    }`}
                  >
                    {idx + 1}. {stage}
                  </span>
                )
              })}
            </div>
          </div>
        )}

        {/* Options & Metadata */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
              Document Classification
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full glass-input px-3 py-2 text-xs text-slate-800 font-semibold cursor-pointer"
            >
              <option value="bank_statement">Bank Statement</option>
              <option value="ledger">General Ledger / Trial Balance</option>
              <option value="financial">Financial Statements (P&L / Balance Sheet)</option>
              <option value="gst">GST 2B / GSTR-1 File</option>
              <option value="general">General Financial Document</option>
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-600 mb-1">
              Audit Notes (Optional)
            </label>
            <input
              type="text"
              placeholder="e.g. Q3 HDFC Current Account Statement"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="w-full glass-input px-3 py-2 text-xs text-slate-800 font-sans"
            />
          </div>
        </div>

        {/* Status Alert */}
        {uploadStatus.type && (
          <div
            className={`p-3 rounded-xl text-xs flex items-center gap-2 ${
              uploadStatus.type === 'success'
                ? 'bg-emerald-50 text-emerald-800 border border-emerald-200'
                : 'bg-rose-50 text-rose-800 border border-rose-200'
            }`}
          >
            {uploadStatus.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span>{uploadStatus.message}</span>
          </div>
        )}

        <div className="flex justify-end pt-1">
          <Button
            type="submit"
            variant="primary"
            size="md"
            disabled={!selectedFile}
            isLoading={isUploading}
          >
            Upload and Inspect
          </Button>
        </div>
      </form>
    </div>
  )
}
