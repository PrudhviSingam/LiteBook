import React, { useEffect, useState } from 'react'
import {
  FolderArchive,
  Search,
  Trash2,
  Download,
  FileSpreadsheet,
  AlertTriangle,
  Eye,
  X,
  Info,
  ShieldCheck,
  Layers,
  FileText,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { FileUploadZone } from '../components/documents/FileUploadZone'
import type { DocumentItem, WorkbookInspectionResult } from '../types'
import {
  getDocuments,
  uploadDocument,
  deleteDocument,
  resetWorkspaceDocuments,
  getDocumentAnalysis,
  getDocumentDownloadUrl,
} from '../services/api'
import { formatFileSize, formatDate } from '../utils/formatters'
import { Button } from '../components/ui/Button'

export const DocumentsPage: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [activeCategory, setActiveCategory] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)

  // Document Inspection Drawer
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null)
  const [analysisResult, setAnalysisResult] = useState<WorkbookInspectionResult | null>(null)
  const [loadingAnalysis, setLoadingAnalysis] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)

  // Global Document Reset Modal & State
  const [isResetModalOpen, setIsResetModalOpen] = useState(false)
  const [isResetting, setIsResetting] = useState(false)
  const [resetError, setResetError] = useState<string | null>(null)
  const [resetSuccessMessage, setResetSuccessMessage] = useState<string | null>(null)

  const fetchDocs = async () => {
    setLoading(true)
    try {
      const docs = await getDocuments(activeCategory)
      setDocuments(docs)
    } catch (err) {
      console.error('Failed to fetch docs', err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocs()
  }, [activeCategory])

  const handleDelete = async (id: number) => {
    if (window.confirm('Are you sure you want to remove this document?')) {
      await deleteDocument(id)
      fetchDocs()
    }
  }

  const handleGlobalReset = async () => {
    setIsResetting(true)
    setResetError(null)
    try {
      const res = await resetWorkspaceDocuments()
      setSelectedDoc(null)
      setAnalysisResult(null)
      setDocuments([])
      setIsResetModalOpen(false)
      setResetSuccessMessage(
        `Workspace reset successfully: ${res.documents_deleted} document(s) and ${res.derived_records_deleted} derived analysis record(s) removed.`
      )
      await fetchDocs()
    } catch (err: any) {
      setResetError(err.message || 'Failed to reset workspace documents. Please try again.')
    } finally {
      setIsResetting(false)
    }
  }

  const handleInspect = async (doc: DocumentItem) => {
    setSelectedDoc(doc)
    setLoadingAnalysis(true)
    setAnalysisError(null)
    setAnalysisResult(null)

    try {
      const result = await getDocumentAnalysis(doc.id)
      setAnalysisResult(result)
    } catch (err: any) {
      setAnalysisError(err.message || 'Unable to inspect document analysis.')
    } finally {
      setLoadingAnalysis(false)
    }
  }

  const filteredDocs = documents.filter((doc) =>
    doc.original_filename.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const categories = [
    { id: 'all', label: 'All Files' },
    { id: 'bank_statement', label: 'Bank Statements' },
    { id: 'ledger', label: 'Ledger Files' },
    { id: 'financial', label: 'Financial Workbooks' },
    { id: 'gst', label: 'GST Documents' },
    { id: 'general', label: 'General' },
  ]

  return (
    <div className="space-y-6 pb-12">
      {/* Upload Zone */}
      <FileUploadZone
        onUploadSuccess={fetchDocs}
        onUpload={async (file, category, notes) => {
          await uploadDocument(file, category, notes)
        }}
      />

      {/* Document Library Section */}
      <div className="glass-panel p-6 border border-white/90">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-200/70">
          <div>
            <h1 className="text-base font-extrabold text-slate-900 tracking-tight">
              Financial Document Repository
            </h1>
            <p className="text-xs text-slate-500">
              Verified financial records with SHA-256 integrity fingerprints.
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 pr-3 py-1.5 text-xs glass-input focus:bg-white text-slate-800 w-full sm:w-60 font-sans"
              />
            </div>

            <button
              type="button"
              id="delete-all-documents-btn"
              onClick={() => {
                setResetError(null)
                setIsResetModalOpen(true)
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold border transition-all duration-200 cursor-pointer bg-rose-50/80 hover:bg-rose-100/90 text-rose-700 border-rose-200/80 shadow-2xs hover:shadow-xs active:scale-98 shrink-0"
              title="Delete all workspace documents and derived records"
            >
              <Trash2 className="w-3.5 h-3.5 text-rose-600 shrink-0" />
              <span>Delete All</span>
            </button>
          </div>
        </div>

        {/* Success Alert Banner */}
        {resetSuccessMessage && (
          <div className="mt-3.5 p-3 rounded-xl bg-emerald-50/90 border border-emerald-200/80 text-emerald-800 text-xs flex items-center justify-between gap-2 shadow-2xs animate-in fade-in duration-200">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>{resetSuccessMessage}</span>
            </div>
            <button
              onClick={() => setResetSuccessMessage(null)}
              className="p-1 text-emerald-600 hover:text-emerald-800 rounded-lg hover:bg-emerald-100/50 cursor-pointer"
              title="Dismiss notification"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Filter Categories */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-3 border-b border-slate-100 no-scrollbar">
          {categories.map((cat) => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id)}
              className={`px-3 py-1.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                activeCategory === cat.id
                  ? 'bg-brand-50 text-brand-700 border border-brand-200/80 shadow-2xs'
                  : 'text-slate-500 hover:text-slate-800 hover:bg-white/60'
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>

        {/* Document List */}
        <div className="mt-4">
          {loading ? (
            <div className="space-y-3 py-4">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 glass rounded-2xl animate-pulse" />
              ))}
            </div>
          ) : filteredDocs.length === 0 ? (
            <EmptyState
              icon={<FolderArchive className="w-8 h-8" />}
              title="No documents found"
              description="Upload your accounting files (.xlsx, .xls, .csv, .pdf) to initiate analysis."
            />
          ) : (
            <div className="glass-table-container">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="bg-white/90 border-b border-slate-200/80 text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      <th className="py-3 px-4">Filename & SHA256</th>
                      <th className="py-3 px-4">Document Type</th>
                      <th className="py-3 px-4">Size</th>
                      <th className="py-3 px-4">Upload Date</th>
                      <th className="py-3 px-4 text-center">Status</th>
                      <th className="py-3 px-4 text-center">Analysis</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100/80 bg-white/40">
                    {filteredDocs.map((doc) => (
                      <tr
                        key={doc.id}
                        className="hover:bg-brand-50/30 transition-colors group"
                      >
                        <td className="py-3 px-4 max-w-[240px]">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 shrink-0">
                              <FileSpreadsheet className="w-4 h-4" />
                            </div>
                            <div className="min-w-0">
                              <span className="font-bold text-slate-900 truncate block">
                                {doc.original_filename}
                              </span>
                              {doc.file_hash && (
                                <span className="font-mono text-[9px] text-slate-400 truncate block" title={doc.file_hash}>
                                  SHA: {doc.file_hash.slice(0, 14)}...
                                </span>
                              )}
                            </div>
                          </div>
                        </td>

                        <td className="py-3 px-4 text-slate-600">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-100 text-slate-700">
                            {doc.document_type}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-slate-500 font-mono text-[11px]">
                          {formatFileSize(doc.file_size)}
                        </td>

                        <td className="py-3 px-4 text-slate-500 text-[11px]">
                          {formatDate(doc.created_at)}
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
                            <ShieldCheck className="w-3 h-3 text-emerald-600" />
                            Stored
                          </span>
                        </td>

                        <td className="py-3 px-4 text-center">
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-50 text-brand-700 border border-brand-200/60">
                            {doc.analysis_status}
                          </span>
                        </td>

                        <td className="py-3 px-4 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => handleInspect(doc)}
                              className="p-1.5 text-slate-400 hover:text-brand-600 hover:bg-white rounded-lg transition-colors cursor-pointer"
                              title="Inspect workbook analysis"
                            >
                              <Eye className="w-4 h-4" />
                            </button>
                            <a
                              href={getDocumentDownloadUrl(doc.id)}
                              target="_blank"
                              rel="noreferrer"
                              className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-white rounded-lg transition-colors cursor-pointer"
                              title="Download original file"
                            >
                              <Download className="w-4 h-4" />
                            </a>
                            <button
                              onClick={() => handleDelete(doc.id)}
                              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-white rounded-lg transition-colors cursor-pointer"
                              title="Delete file"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Document Inspection Drawer */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-slate-900/30 backdrop-blur-xs flex justify-end animate-in fade-in duration-200">
          <div className="w-full max-w-xl bg-white/95 backdrop-blur-xl h-full shadow-2xl flex flex-col border-l border-white/80 overflow-y-auto">
            {/* Drawer Header */}
            <div className="p-6 border-b border-slate-200/70 glass-header flex items-center justify-between sticky top-0 z-10">
              <div className="min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-50 text-brand-700 border border-brand-200/60">
                    Inspection Details
                  </span>
                  <span className="text-xs text-slate-400">ID #{selectedDoc.id}</span>
                </div>
                <h3 className="text-base font-extrabold text-slate-900 truncate">
                  {selectedDoc.original_filename}
                </h3>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Content */}
            <div className="p-6 space-y-5 flex-1">
              {/* File Info Card */}
              <div className="glass-card p-4 space-y-2 text-xs">
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-400">Document Type</span>
                  <span className="font-semibold text-slate-800">{selectedDoc.document_type}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-400">File Size</span>
                  <span className="font-mono text-slate-800">{formatFileSize(selectedDoc.file_size)}</span>
                </div>
                <div className="flex justify-between py-1 border-b border-slate-100">
                  <span className="text-slate-400">Upload Date</span>
                  <span className="text-slate-800">{formatDate(selectedDoc.created_at)}</span>
                </div>
                {selectedDoc.file_hash && (
                  <div className="py-1">
                    <span className="text-slate-400 block mb-1">SHA-256 Digest</span>
                    <span className="font-mono text-[10px] text-slate-600 bg-white/80 p-1.5 rounded-lg border border-slate-200/70 block break-all">
                      {selectedDoc.file_hash}
                    </span>
                  </div>
                )}
              </div>

              {/* Analysis Result */}
              {loadingAnalysis ? (
                <div className="p-8 text-center glass-card">
                  <p className="text-xs text-slate-500">Inspecting workbook structure...</p>
                </div>
              ) : analysisError ? (
                <div className="p-4 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs">
                  {analysisError}
                </div>
              ) : analysisResult ? (
                <div className="space-y-4">
                  <div className="glass-card p-4 space-y-3">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500">
                      Workbook Structure
                    </h4>
                    <div className="grid grid-cols-2 gap-3 text-xs">
                      <div className="p-3 rounded-xl bg-white/80 border border-slate-200/70">
                        <span className="text-slate-400 text-[10px] block">Sheets Detected</span>
                        <span className="text-lg font-bold text-slate-800 mt-0.5 block">
                          {analysisResult.sheet_count ?? 1}
                        </span>
                      </div>
                      <div className="p-3 rounded-xl bg-white/80 border border-slate-200/70">
                        <span className="text-slate-400 text-[10px] block">Total Rows</span>
                        <span className="text-lg font-bold text-slate-800 mt-0.5 block">
                          {analysisResult.total_rows ?? '—'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {analysisResult.sheets && analysisResult.sheets.length > 0 && (
                    <div className="glass-card p-4 space-y-2">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                        Sheet Breakdown
                      </h4>
                      <div className="divide-y divide-slate-100 text-xs">
                        {analysisResult.sheets.map((s, idx) => (
                          <div key={idx} className="py-2 flex items-center justify-between">
                            <span className="font-semibold text-slate-800">{s.name}</span>
                            <span className="font-mono text-slate-400">{s.row_count} rows</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="p-6 text-center glass-card text-xs text-slate-400">
                  No structural analysis available for this file type.
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Delete All Confirmation Modal */}
      {isResetModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="reset-modal-title"
          className="fixed inset-0 z-50 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 animate-in fade-in duration-200"
        >
          <div className="glass-panel bg-white/95 border border-rose-100 shadow-xl rounded-2xl max-w-md w-full p-6 text-slate-800 space-y-4">
            <div className="flex items-start gap-3.5">
              <div className="w-10 h-10 rounded-xl bg-rose-50 border border-rose-200/80 flex items-center justify-center text-rose-600 shrink-0 shadow-2xs">
                <AlertTriangle className="w-5 h-5 text-rose-600" />
              </div>
              <div className="min-w-0 flex-1">
                <h3 id="reset-modal-title" className="text-base font-extrabold text-slate-900 tracking-tight">
                  Delete all documents?
                </h3>
                <p className="text-xs text-slate-600 mt-1.5 leading-relaxed">
                  This will permanently remove all uploaded documents and their derived analysis data for your current workspace. This action cannot be undone.
                </p>
              </div>
            </div>

            {resetError && (
              <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
                <span className="flex-1 font-medium">{resetError}</span>
              </div>
            )}

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-100">
              <button
                type="button"
                id="cancel-delete-all-btn"
                onClick={() => {
                  if (!isResetting) {
                    setIsResetModalOpen(false)
                    setResetError(null)
                  }
                }}
                disabled={isResetting}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-700 hover:text-slate-900 hover:bg-slate-100/80 transition-colors disabled:opacity-50 cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                id="confirm-delete-all-btn"
                onClick={handleGlobalReset}
                disabled={isResetting}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-rose-600 hover:bg-rose-700 active:scale-98 shadow-sm transition-all disabled:opacity-50 cursor-pointer"
              >
                {isResetting ? (
                  <>
                    <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Deleting...</span>
                  </>
                ) : (
                  <>
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Delete everything</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
