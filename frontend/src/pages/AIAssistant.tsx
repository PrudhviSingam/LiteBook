import React, { useState, useRef, useEffect } from 'react'
import {
  Sparkles,
  Send,
  Bot,
  Paperclip,
  X,
  FileSpreadsheet,
  AlertTriangle,
  AlertCircle,
  CheckCircle2,
  Download,
  RotateCcw,
  Scale,
  ShieldCheck,
  FileText,
} from 'lucide-react'
import { Card } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { DeveloperCard } from '../components/DeveloperCard'
import type {
  AssistantFileContext,
  AssistantMessage,
  CorrectionProposalInfo,
} from '../types'
import {
  assistantChat,
  assistantCorrectionDecision,
  assistantGenerateCorrectedCopy,
  assistantGetConversation,
  assistantUpload,
} from '../services/api'

export const AIAssistantPage: React.FC = () => {
  const [conversationId, setConversationId] = useState<string>(() => {
    const saved = localStorage.getItem('litebooks_active_conversation_id')
    if (saved) return saved
    const newId = `conv_${Date.now()}`
    localStorage.setItem('litebooks_active_conversation_id', newId)
    return newId
  })
  const [prompt, setPrompt] = useState('')
  const [attachedFiles, setAttachedFiles] = useState<AssistantFileContext[]>([])
  const [isUploading, setIsUploading] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  // Correction Review Modal State
  const [reviewProposal, setReviewProposal] = useState<CorrectionProposalInfo | null>(null)
  const [isDeciding, setIsDeciding] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [generationResult, setGenerationResult] = useState<{
    download_url: string
    generated_filename: string
    corrections_sheet_name: string
  } | null>(null)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const [messages, setMessages] = useState<AssistantMessage[]>([
    {
      id: 'init-1',
      role: 'assistant',
      text: "Hello! I'm your LiteBooks AI Assistant. I can assist with accounting principles, reconciliation, and discrepancy detection.\n\nYou can ask general finance questions or attach financial statements (XLSX, XLS, CSV, PDF) to analyze variances and reconcile records.",
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    },
  ])

  useEffect(() => {
    let isMounted = true
    async function restoreConversation() {
      if (!conversationId) return
      try {
        const data = await assistantGetConversation(conversationId)
        if (!isMounted) return
        if (data && data.messages && data.messages.length > 0) {
          const restored: AssistantMessage[] = data.messages.map((m: any) => ({
            id: m.id || `msg_${Date.now()}_${Math.random()}`,
            role: m.role,
            text: m.text,
            timestamp: m.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            intent: m.intent,
            findings: m.findings,
            proposal: m.proposal,
            correction_available: m.correction_available,
            correction_id: m.correction_id,
          }))
          setMessages(restored)
        }
        if (data && data.files && data.files.length > 0) {
          setAttachedFiles(data.files)
        }
      } catch (err) {
        console.debug('No prior conversation found or unable to restore:', err)
      }
    }
    restoreConversation()
    return () => {
      isMounted = false
    }
  }, [conversationId])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  useEffect(() => {
    const handleReset = () => {
      setAttachedFiles([])
      setReviewProposal(null)
      setGenerationResult(null)
    }
    window.addEventListener('workspace:documents_reset', handleReset)
    return () => window.removeEventListener('workspace:documents_reset', handleReset)
  }, [])

  // Handle File Upload
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setUploadError(null)
    setIsUploading(true)
    try {
      const fileInfo = await assistantUpload(file, conversationId)
      setAttachedFiles((prev) => {
        // Allow up to 2 files for comparison
        const filtered = prev.filter((f) => f.document_id !== fileInfo.document_id)
        return [...filtered, fileInfo].slice(-2)
      })

      // Add system announcement in chat
      const announceText =
        fileInfo.document_type === 'PDF_DOCUMENT'
          ? `Attached PDF document **${fileInfo.filename}**. *Note: PDF text/table extraction requires review; Excel/CSV files provide automated cell calculations.*`
          : `Attached file **${fileInfo.filename}**.\n- **Detected:** ${fileInfo.document_type.replace(/_/g, ' ')}\n- **Sheet:** ${fileInfo.sheet_name}\n- **Period:** ${fileInfo.period || 'Standard'}\n- **Status:** ${fileInfo.status === 'ready' ? 'Ready for analysis' : 'Review Required'}`

      setMessages((prev) => [
        ...prev,
        {
          id: `upload-${Date.now()}`,
          role: 'assistant',
          text: announceText,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          files: [fileInfo],
        },
      ])
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload and inspect file.')
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleRemoveFile = (docId: number) => {
    setAttachedFiles((prev) => prev.filter((f) => f.document_id !== docId))
  }

  // Handle Send Message
  const handleSend = async (userTextToSend?: string) => {
    const text = (userTextToSend || prompt).trim()
    if (!text || isLoading) return

    const userMessage: AssistantMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      text,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    }

    setMessages((prev) => [...prev, userMessage])
    setPrompt('')
    setIsLoading(true)

    try {
      const activeFileIds = attachedFiles.map((f) => f.document_id)
      const res = await assistantChat(text, conversationId, activeFileIds)

      const assistantMessage: AssistantMessage = {
        id: `asst-${Date.now()}`,
        role: 'assistant',
        text: res.message,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        intent: res.intent,
        findings: res.findings,
        proposal: res.proposal,
        correction_available: res.correction_available,
        correction_id: res.correction_id,
        files: res.files,
        confidence: res.confidence,
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          text: "I couldn't reliably interpret this request. Please verify the uploaded file structure or rephrase your accounting question.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          error: true,
        },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  // Handle Correction Decisions
  const handleDecision = async (decision: 'CONFIRMED' | 'REJECTED') => {
    if (!reviewProposal) return
    setIsDeciding(true)
    try {
      const updated = await assistantCorrectionDecision(
        reviewProposal.correction_id,
        decision,
        `Accountant recorded ${decision.toLowerCase()} via Assistant`
      )
      setReviewProposal((prev) => (prev ? { ...prev, status: updated.status } : null))
      setMessages((prev) => [
        ...prev,
        {
          id: `dec-${Date.now()}`,
          role: 'assistant',
          text:
            decision === 'CONFIRMED'
              ? `Correction **${reviewProposal.correction_id}** has been confirmed by the accountant. You can now generate a timestamped non-destructive Excel copy.`
              : `Correction **${reviewProposal.correction_id}** was rejected. Original values remain unchanged.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } catch (err: any) {
      setActionError(err.message || 'Failed to record decision')
    } finally {
      setIsDeciding(false)
    }
  }

  // Handle Generate Corrected Workbook Copy
  const handleGenerateCopy = async () => {
    if (!reviewProposal) return
    setIsGenerating(true)
    setActionError(null)
    try {
      const res = await assistantGenerateCorrectedCopy(reviewProposal.correction_id)
      setGenerationResult({
        download_url: res.download_url,
        generated_filename: res.generated_filename,
        corrections_sheet_name: res.corrections_sheet_name,
      })
      setReviewProposal((prev) => (prev ? { ...prev, status: 'GENERATED' } : null))

      setMessages((prev) => [
        ...prev,
        {
          id: `gen-${Date.now()}`,
          role: 'assistant',
          text: `### Non-Destructive Copy Generated\n\nSuccessfully created **${res.generated_filename}** with approved corrections and the **${res.corrections_sheet_name}** audit log sheet.\n\n[Download Corrected Copy](${res.download_url})`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ])
    } catch (err: any) {
      setActionError(err.message || 'Failed to generate corrected workbook')
    } finally {
      setIsGenerating(false)
    }
  }

  // Suggestion chips based on file state (including required default chips)
  const defaultChips = [
    'What is wrong?',
    'Explain this discrepancy',
    'Check formula issues',
    'Summarize this document',
    'Compare bank and ledger',
  ]

  const suggestionChips =
    attachedFiles.length >= 2
      ? [
          'Compare bank and ledger',
          'Show missing transactions',
          'Find discrepancies',
          'Which file contains the missing record?',
        ]
      : attachedFiles.length === 1
      ? [
          'Analyze my uploaded files',
          'Find discrepancies',
          'Explain this finding',
          'Check Balance Sheet',
          'Where is the problem?',
        ]
      : defaultChips

  // Render markdown with clean styles
  const renderMessageContent = (text: string) => {
    const lines = text.split('\n')
    return (
      <div className="space-y-2 text-xs leading-relaxed">
        {lines.map((line, idx) => {
          if (line.startsWith('### ')) {
            return (
              <h4 key={idx} className="font-bold text-slate-800 text-sm mt-3 mb-1 first:mt-0">
                {line.replace('### ', '')}
              </h4>
            )
          }
          if (line.startsWith('#### ')) {
            return (
              <h5 key={idx} className="font-semibold text-slate-700 text-xs mt-2 mb-1">
                {line.replace('#### ', '')}
              </h5>
            )
          }
          if (line.startsWith('- ')) {
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="text-brand-500 font-bold shrink-0">•</span>
                <span>{renderInlineFormatting(line.replace('- ', ''))}</span>
              </div>
            )
          }
          if (/^\d+\.\s/.test(line)) {
            const num = line.match(/^(\d+)\.\s/)?.[1]
            const content = line.replace(/^\d+\.\s/, '')
            return (
              <div key={idx} className="flex items-start gap-2 pl-2">
                <span className="font-bold text-brand-600 shrink-0">{num}.</span>
                <span>{renderInlineFormatting(content)}</span>
              </div>
            )
          }
          if (!line.trim()) {
            return <div key={idx} className="h-1" />
          }
          return <p key={idx}>{renderInlineFormatting(line)}</p>
        })}
      </div>
    )
  }

  const renderInlineFormatting = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|\*.*?\*|\[.*?\]\(.*?\)|\b\[View Finding\]\b)/g)
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={i} className="font-semibold text-slate-900">{part.slice(2, -2)}</strong>
      }
      if (part.startsWith('*') && part.endsWith('*')) {
        return <em key={i} className="text-slate-500 italic">{part.slice(1, -1)}</em>
      }
      if (part === '[View Finding]' || part === '[View Finding in Review Center]') {
        return (
          <button
            key={i}
            type="button"
            onClick={() => {
              window.location.hash = '#review-center'
            }}
            className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700 underline underline-offset-2 cursor-pointer my-1"
          >
            <AlertTriangle className="w-3 h-3 text-amber-500" /> View Finding in Review Center
          </button>
        )
      }
      const linkMatch = part.match(/\[(.*?)\]\((.*?)\)/)
      if (linkMatch) {
        const linkLabel = linkMatch[1]
        const linkUrl = linkMatch[2]
        if (linkLabel.toLowerCase().includes('finding') || linkLabel.toLowerCase().includes('review center')) {
          return (
            <button
              key={i}
              type="button"
              onClick={() => {
                window.location.hash = '#review-center'
              }}
              className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700 underline underline-offset-2 cursor-pointer my-1"
            >
              <AlertTriangle className="w-3 h-3 text-amber-500" /> {linkLabel}
            </button>
          )
        }
        return (
          <a
            key={i}
            href={linkUrl}
            download
            className="inline-flex items-center gap-1 font-semibold text-brand-600 hover:text-brand-700 underline underline-offset-2"
          >
            <Download className="w-3 h-3" /> {linkLabel}
          </a>
        )
      }
      return part
    })
  }

  return (
    <div className="space-y-4 max-w-6xl mx-auto pb-8">
      {/* Header Info Banner */}
      <div className="glass-panel p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 border border-white/90">
        <div className="flex items-start gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand-50 border border-brand-200/70 text-brand-600 flex items-center justify-center shrink-0 shadow-2xs">
            <Bot className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-extrabold text-slate-900 tracking-tight">
                AI Accounting Assistant
              </h2>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-brand-50 text-brand-700 border border-brand-200/60">
                Grounded in Real Ledgers
              </span>
            </div>
            <p className="text-[11px] text-slate-500 mt-0.5">
              Deterministic accounting logic combined with Sarvam AI forensic explanations.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold bg-white/80 hover:bg-white text-slate-700 border border-slate-200 shadow-2xs transition-colors cursor-pointer"
          >
            <Paperclip className="w-3.5 h-3.5 text-brand-500" />
            {isUploading ? 'Inspecting...' : 'Attach File'}
          </button>
          <button
            onClick={() => {
              const newId = `conv_${Date.now()}`
              localStorage.setItem('litebooks_active_conversation_id', newId)
              setConversationId(newId)
              setAttachedFiles([])
              setMessages([
                {
                  id: `init-${Date.now()}`,
                  role: 'assistant',
                  text: 'New conversation session started. How can I assist with your financial records today?',
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
              ])
            }}
            className="p-1.5 text-slate-400 hover:text-slate-700 hover:bg-white/80 rounded-xl transition-colors cursor-pointer"
            title="Reset conversation"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Layout: Chat Area + Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Main Glass Chat Panel */}
        <div className="lg:col-span-8 glass-panel overflow-hidden flex flex-col h-[680px] border border-white/90 shadow-lg">
        {/* Attached Files Bar */}
        {attachedFiles.length > 0 && (
          <div className="p-3 bg-brand-50/50 border-b border-brand-100 flex flex-wrap items-center gap-2.5">
            <span className="text-[10px] font-bold uppercase tracking-wider text-brand-700 flex items-center gap-1">
              <FileSpreadsheet className="w-3.5 h-3.5 text-brand-600" /> Active Context:
            </span>
            {attachedFiles.map((file, idx) => (
              <div
                key={file.document_id}
                className="flex items-center gap-2 bg-white/90 border border-brand-200/80 rounded-xl px-2.5 py-1 shadow-2xs text-xs"
              >
                <div className="w-5 h-5 rounded-md bg-brand-50 text-brand-600 flex items-center justify-center font-bold text-[10px]">
                  {idx === 0 ? 'A' : 'B'}
                </div>
                <div className="leading-tight">
                  <span className="font-semibold text-slate-800 truncate max-w-[140px] block">
                    {file.filename}
                  </span>
                </div>
                <Badge variant={file.status === 'ready' ? 'success' : 'warning'} className="text-[9px] py-0 px-1">
                  {file.status === 'ready' ? 'Ready' : 'Review'}
                </Badge>
                <button
                  type="button"
                  onClick={() => handleRemoveFile(file.document_id)}
                  className="text-slate-400 hover:text-slate-600 p-0.5 rounded cursor-pointer"
                  title="Remove file"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
            {attachedFiles.length === 1 && (
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="text-[11px] text-brand-600 hover:text-brand-700 font-semibold flex items-center gap-1 bg-white/80 hover:bg-brand-50 border border-dashed border-brand-300 rounded-xl px-2.5 py-1 transition-colors cursor-pointer"
              >
                + Attach Second File to Compare
              </button>
            )}
          </div>
        )}

        {/* Messages Stream */}
        <div className="flex-1 p-5 overflow-y-auto space-y-4 bg-white/20">
          {messages.map((m) => {
            const isUser = m.role === 'user'
            return (
              <div
                key={m.id}
                className={`flex gap-3 max-w-3xl ${isUser ? 'ml-auto flex-row-reverse' : ''}`}
              >
                {/* Avatar */}
                <div
                  className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-xs font-bold shadow-2xs ${
                    isUser
                      ? 'bg-slate-800 text-white'
                      : 'bg-brand-50 text-brand-600 border border-brand-200/70'
                  }`}
                >
                  {isUser ? 'ME' : <Bot className="w-4 h-4" />}
                </div>

                {/* Message Bubble Container */}
                <div className="space-y-2 max-w-2xl">
                  {/* USER: Subtle pink glass | ASSISTANT: White glass */}
                  <div
                    className={`p-4 rounded-2xl shadow-2xs border ${
                      isUser
                        ? 'bg-brand-50/90 text-slate-800 border-brand-200/80 rounded-tr-xs backdrop-blur-md'
                        : 'bg-white/95 text-slate-800 border-white rounded-tl-xs backdrop-blur-md'
                    }`}
                  >
                    {isUser ? (
                      <p className="text-xs sm:text-sm leading-relaxed whitespace-pre-wrap font-medium">
                        {m.text}
                      </p>
                    ) : (
                      renderMessageContent(m.text)
                    )}
                  </div>

                  {/* Render Structured Finding Card if Present */}
                  {m.findings && m.findings.length > 0 && (
                    <div className="space-y-2">
                      {m.findings.map((f, fIdx) => (
                        <div
                          key={fIdx}
                          className="glass-card p-4 space-y-3 border-2 border-brand-200/70"
                        >
                          <div className="flex items-center justify-between gap-2 border-b border-slate-100 pb-2">
                            <div className="flex items-center gap-2">
                              <span className="w-2 h-2 rounded-full bg-brand-500 animate-pulse" />
                              <span className="text-xs font-bold uppercase tracking-wider text-brand-700">
                                Discrepancy Found
                              </span>
                            </div>
                            <Badge variant="pink">{f.confidence} Confidence</Badge>
                          </div>

                          <div className="grid grid-cols-2 gap-3 text-xs">
                            <div className="p-2.5 bg-white/80 rounded-xl border border-slate-200/60">
                              <span className="text-[10px] text-slate-400 uppercase font-semibold">Location</span>
                              <div className="font-semibold text-slate-800 mt-0.5 truncate">{f.location}</div>
                            </div>
                            <div className="p-2.5 bg-brand-50/80 rounded-xl border border-brand-200/60">
                              <span className="text-[10px] text-brand-600 uppercase font-semibold">Variance Amount</span>
                              <div className="font-bold text-brand-700 text-sm mt-0.5">{f.difference || '₹0.00'}</div>
                            </div>
                          </div>

                          {f.expected_value && f.actual_value && (
                            <div className="grid grid-cols-2 gap-3 text-xs">
                              <div className="p-2 bg-white/70 rounded-lg border border-slate-200/60">
                                <span className="text-[10px] text-slate-500">Expected Stated Value:</span>
                                <div className="font-semibold text-slate-700">{f.expected_value}</div>
                              </div>
                              <div className="p-2 bg-white/70 rounded-lg border border-slate-200/60">
                                <span className="text-[10px] text-slate-500">Actual Recorded Value:</span>
                                <div className="font-semibold text-slate-700">{f.actual_value}</div>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Render Correction CTA if Available */}
                  {m.correction_available && m.proposal && (
                    <div className="p-3.5 glass-card bg-brand-50/80 border border-brand-200 flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2.5">
                        <Scale className="w-5 h-5 text-brand-600 shrink-0" />
                        <div>
                          <div className="text-xs font-bold text-brand-800">Correction Proposal Prepared</div>
                          <div className="text-[11px] text-brand-600 font-mono">
                            Adjust {m.proposal.row_reference} ({m.proposal.difference < 0 ? '-' : '+'}
                            {m.proposal.difference})
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => {
                            setReviewProposal(m.proposal || null)
                            setGenerationResult(null)
                          }}
                        >
                          Review Correction
                        </Button>
                      </div>
                    </div>
                  )}

                  <div className={`text-[10px] text-slate-400 px-1 ${isUser ? 'text-right' : 'text-left'}`}>
                    {m.timestamp}
                  </div>
                </div>
              </div>
            )
          })}

          {/* Loading Bubble */}
          {isLoading && (
            <div className="flex gap-3 max-w-md">
              <div className="w-8 h-8 rounded-xl bg-brand-50 text-brand-600 border border-brand-200 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4" />
              </div>
              <div className="p-3.5 bg-white/95 border border-white rounded-2xl rounded-tl-xs shadow-2xs flex items-center gap-2 text-xs text-slate-500 backdrop-blur-md">
                <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce" />
                <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.2s]" />
                <span className="w-2 h-2 rounded-full bg-brand-500 animate-bounce [animation-delay:0.4s]" />
                <span className="text-xs font-medium text-slate-600 ml-1">Analyzing financial records...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Suggestion Chips */}
        <div className="px-4 py-2.5 bg-white/80 border-t border-slate-200/60 flex items-center gap-2 overflow-x-auto no-scrollbar backdrop-blur-md">
          <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 shrink-0 flex items-center gap-1">
            <Sparkles className="w-3 h-3 text-brand-500" /> Prompts:
          </span>
          {suggestionChips.map((chip, idx) => (
            <button
              key={idx}
              type="button"
              onClick={() => handleSend(chip)}
              disabled={isLoading}
              className="text-[11px] text-slate-700 bg-white/80 hover:bg-brand-50 hover:text-brand-700 hover:border-brand-300 px-3 py-1 rounded-full border border-slate-200/80 whitespace-nowrap transition-all shadow-2xs cursor-pointer disabled:opacity-50"
            >
              {chip}
            </button>
          ))}
        </div>

        {/* Error Alert */}
        {uploadError && (
          <div className="px-4 py-2 bg-rose-50 border-t border-rose-200 text-rose-800 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{uploadError}</span>
            </div>
            <button onClick={() => setUploadError(null)} className="text-rose-600 font-bold p-1 cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Input Form */}
        <form
          onSubmit={(e) => {
            e.preventDefault()
            handleSend()
          }}
          className="p-3 bg-white/90 border-t border-slate-200/70 flex items-center gap-2 backdrop-blur-md"
        >
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept=".xlsx,.xls,.csv,.pdf"
            className="hidden"
          />

          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading || isLoading}
            icon={<Paperclip className="w-4 h-4 text-slate-500" />}
            title="Attach Excel (XLSX), CSV, or PDF file"
          >
            {isUploading ? 'Uploading...' : 'Attach'}
          </Button>

          <input
            type="text"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={
              attachedFiles.length > 0
                ? "Ask about this file (e.g., 'Find any mismatch', 'Why is this different?')"
                : "Ask an accounting question or attach a financial file..."
            }
            disabled={isLoading}
            className="flex-1 text-xs sm:text-sm glass-input px-3.5 py-2.5 text-slate-800 placeholder:text-slate-400 font-sans"
          />

          <Button
            type="submit"
            variant="primary"
            size="sm"
            disabled={!prompt.trim() || isLoading}
            icon={<Send className="w-3.5 h-3.5" />}
          >
            Send
          </Button>
        </form>
      </div>

      {/* AI Assistant Sidebar */}
      <aside className="lg:col-span-4 flex flex-col gap-4">
        {/* Compact "Built by Singam" Developer Profile Card */}
        <DeveloperCard variant="sidebar" />

        {/* Forensic Assistant Specifications Card */}
        <div className="glass-panel p-4 border border-white/90 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles className="w-4 h-4 text-brand-600" />
            <h3 className="text-xs font-bold text-slate-800 uppercase tracking-wider">
              Forensic Assistant
            </h3>
          </div>
          <p className="text-[11px] text-slate-500 leading-relaxed">
            Deterministic accounting logic combined with Sarvam AI forensic explanations.
          </p>
          <div className="pt-2 border-t border-slate-100 flex flex-col gap-2 text-[11px] text-slate-600">
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Engine Status</span>
              <span className="font-semibold text-emerald-600 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" /> Live & Ready
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Context Source</span>
              <span className="font-medium text-slate-700">Bank & Ledger Sheets</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-slate-400">Safety Principle</span>
              <span className="font-medium text-slate-700">Originals Immutable</span>
            </div>
          </div>
        </div>

        {/* Quick Prompts Panel */}
        <div className="glass-panel p-4 border border-white/90 space-y-2.5">
          <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
            Quick Prompts
          </h4>
          <div className="flex flex-col gap-1.5">
            {defaultChips.slice(0, 4).map((chip, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setPrompt(chip)}
                className="text-left text-xs p-2.5 rounded-xl bg-white/70 hover:bg-white text-slate-700 border border-slate-200/70 hover:border-brand-300 transition-all shadow-2xs hover:shadow-xs cursor-pointer truncate"
                title={chip}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      </aside>
    </div>

    {/* Accountant Review & Correction Proposal Modal */}
      {reviewProposal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="glass-modal max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="p-5 border-b border-slate-200/70 flex items-center justify-between bg-brand-50/60">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-brand-100 text-brand-700 flex items-center justify-center shadow-2xs">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="text-sm font-bold text-slate-900">Accountant Correction Review</h4>
                  <p className="text-[11px] text-slate-500">ID: {reviewProposal.correction_id}</p>
                </div>
              </div>
              <Badge variant={reviewProposal.status === 'CONFIRMED' ? 'success' : 'pink'}>
                {reviewProposal.status}
              </Badge>
            </div>

            {/* Modal Body */}
            <div className="p-5 space-y-4 text-xs">
              {actionError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                  <span>{actionError}</span>
                </div>
              )}
              <div className="p-3 rounded-2xl bg-white/80 border border-slate-200/70 space-y-1">
                <div className="text-slate-500 font-medium">Target Statement Location:</div>
                <div className="font-bold text-slate-800 text-sm">
                  {reviewProposal.sheet_name} → {reviewProposal.row_reference}
                </div>
              </div>

              {/* Before vs Proposed Comparison */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3.5 rounded-2xl bg-rose-50/70 border border-rose-200/70">
                  <span className="text-[10px] uppercase font-bold text-rose-700">Recorded (Before)</span>
                  <div className="text-base font-bold text-slate-800 mt-1 font-mono">
                    {typeof reviewProposal.original_value === 'number'
                      ? `₹${reviewProposal.original_value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                      : reviewProposal.original_value}
                  </div>
                </div>

                <div className="p-3.5 rounded-2xl bg-emerald-50/70 border border-emerald-200/70">
                  <span className="text-[10px] uppercase font-bold text-emerald-700">Proposed (After)</span>
                  <div className="text-base font-bold text-slate-800 mt-1 font-mono">
                    {typeof reviewProposal.proposed_value === 'number'
                      ? `₹${reviewProposal.proposed_value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`
                      : reviewProposal.proposed_value}
                  </div>
                </div>
              </div>

              {/* Rationale & Evidence */}
              <div className="space-y-1.5">
                <span className="text-[10px] uppercase font-bold text-slate-400">Audit Rationale:</span>
                <p className="text-slate-700 leading-relaxed bg-white/70 p-3 rounded-xl border border-slate-200/70">
                  {reviewProposal.explanation}
                </p>
              </div>

              {/* Generation Result Banner if complete */}
              {generationResult && (
                <div className="p-3.5 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 space-y-2">
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                    Corrected Copy Created Successfully
                  </div>
                  <p className="text-[11px] text-emerald-700">
                    File: <strong>{generationResult.generated_filename}</strong>
                    <br />
                    Worksheet <em>'{generationResult.corrections_sheet_name}'</em> appended with full audit trail.
                  </p>
                  <a
                    href={generationResult.download_url}
                    download
                    className="inline-flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white px-3 py-1.5 rounded-xl text-xs font-semibold transition-colors mt-1"
                  >
                    <Download className="w-3.5 h-3.5" /> Download Corrected Excel
                  </a>
                </div>
              )}

              {/* Safety notice */}
              <div className="text-[11px] text-slate-500 bg-brand-50/50 p-2.5 rounded-xl border border-brand-100 flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-brand-600 shrink-0 mt-0.5" />
                <span>
                  <strong>Safety Principle:</strong> Original files remain 100% immutable. Generating a copy creates a new timestamped workbook without overwriting past data.
                </span>
              </div>
            </div>

            {/* Modal Footer Actions */}
            <div className="p-4 border-t border-slate-200/70 bg-white/80 flex items-center justify-between gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setReviewProposal(null)}
              >
                Close
              </Button>

              <div className="flex items-center gap-2">
                {reviewProposal.status === 'PROPOSED' && (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDecision('REJECTED')}
                      disabled={isDeciding}
                    >
                      Reject
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleDecision('CONFIRMED')}
                      disabled={isDeciding}
                      icon={<CheckCircle2 className="w-3.5 h-3.5" />}
                    >
                      {isDeciding ? 'Recording...' : 'Approve & Confirm'}
                    </Button>
                  </>
                )}

                {reviewProposal.status === 'CONFIRMED' && !generationResult && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleGenerateCopy}
                    disabled={isGenerating}
                    icon={<FileSpreadsheet className="w-3.5 h-3.5" />}
                  >
                    {isGenerating ? 'Generating Copy...' : 'Generate Corrected Excel Copy'}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
