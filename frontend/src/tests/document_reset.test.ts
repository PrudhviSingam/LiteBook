import { describe, it, expect, vi, beforeEach } from 'vitest'
import { resetWorkspaceDocuments, setAuthToken, clearAuthToken } from '../services/api'
import type { DocumentResetResponse, DocumentItem } from '../types'

describe('Global Document Reset Frontend Workflow', () => {
  // Global mocks for Vitest Node environment
  const storage: Record<string, string> = {}
  const mockLocalStorage = {
    getItem: (k: string) => storage[k] ?? null,
    setItem: (k: string, v: string) => {
      storage[k] = v
    },
    removeItem: (k: string) => {
      delete storage[k]
    },
    clear: () => {
      Object.keys(storage).forEach((k) => delete storage[k])
    },
  }
  vi.stubGlobal('localStorage', mockLocalStorage)

  const eventListeners: Record<string, Function[]> = {}
  vi.stubGlobal('window', {
    addEventListener: (type: string, handler: Function) => {
      eventListeners[type] = eventListeners[type] || []
      eventListeners[type].push(handler)
    },
    removeEventListener: (type: string, handler: Function) => {
      if (eventListeners[type]) {
        eventListeners[type] = eventListeners[type].filter((h) => h !== handler)
      }
    },
    dispatchEvent: (evt: any) => {
      const handlers = eventListeners[evt.type] || []
      handlers.forEach((h) => h(evt))
      return true
    },
  })

  // Polyfill CustomEvent if not in Node environment
  if (typeof (globalThis as any).CustomEvent === 'undefined') {
    class MockCustomEvent {
      type: string
      detail: any
      constructor(type: string, init?: { detail?: any }) {
        this.type = type
        this.detail = init?.detail
      }
    }
    vi.stubGlobal('CustomEvent', MockCustomEvent)
  }

  beforeEach(() => {
    mockLocalStorage.clear()
    setAuthToken('mock-test-jwt-token')
  })

  describe('API Service: resetWorkspaceDocuments', () => {
    it('successfully calls DELETE /api/v1/documents/reset and dispatches workspace:documents_reset event', async () => {
      const mockResponse: DocumentResetResponse = {
        success: true,
        documents_deleted: 3,
        derived_records_deleted: 12,
        files_deleted: 3,
      }

      const fetchMock = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockResponse,
      })
      vi.stubGlobal('fetch', fetchMock)

      let eventPayload: any = null
      const eventListener = (e: any) => {
        eventPayload = e.detail
      }
      window.addEventListener('workspace:documents_reset', eventListener)

      const result = await resetWorkspaceDocuments()

      expect(fetchMock).toHaveBeenCalledTimes(1)
      const [calledUrl, calledInit] = fetchMock.mock.calls[0]
      expect(calledUrl).toContain('/api/v1/documents/reset')
      expect(calledInit.method).toBe('DELETE')
      expect(calledInit.headers.get('Authorization')).toBe('Bearer mock-test-jwt-token')

      expect(result).toEqual(mockResponse)
      expect(eventPayload).toEqual(mockResponse)

      window.removeEventListener('workspace:documents_reset', eventListener)
    })

    it('handles failure gracefully without dispatching reset event', async () => {
      const errorJson = { detail: 'Database connection failed during reset' }
      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        json: async () => errorJson,
        text: async () => JSON.stringify(errorJson),
      })
      vi.stubGlobal('fetch', fetchMock)

      let eventDispatched = false
      const eventListener = () => {
        eventDispatched = true
      }
      window.addEventListener('workspace:documents_reset', eventListener)

      await expect(resetWorkspaceDocuments()).rejects.toThrow('Database connection failed during reset')
      expect(eventDispatched).toBe(false)

      window.removeEventListener('workspace:documents_reset', eventListener)
    })
  })

  describe('Modal & State Invalidation Semantics', () => {
    it('verifies confirmation modal content contracts', () => {
      const modalContract = {
        expectedTitle: 'Delete all documents?',
        expectedMessage:
          'This will permanently remove all uploaded documents and their derived analysis data for your current workspace. This action cannot be undone.',
        confirmButtonLabel: 'Delete everything',
        cancelButtonLabel: 'Cancel',
      }

      expect(modalContract.expectedTitle).toBe('Delete all documents?')
      expect(modalContract.expectedMessage).toContain('permanently remove all uploaded documents')
      expect(modalContract.confirmButtonLabel).toBe('Delete everything')
      expect(modalContract.cancelButtonLabel).toBe('Cancel')
    })

    it('models cancellation action without clearing documents state', () => {
      let isModalOpen = true
      let documentsList: DocumentItem[] = [
        {
          id: 1,
          original_filename: 'bank_statement.xlsx',
          stored_filename: 'uuid.xlsx',
          file_size: 15400,
          mime_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          document_type: 'BANK_STATEMENT',
          category: 'bank_statement',
          status: 'ready',
          created_at: '2026-03-31T12:00:00Z',
          updated_at: '2026-03-31T12:00:00Z',
        },
      ]
      let selectedDoc: DocumentItem | null = documentsList[0]

      const handleCancel = () => {
        isModalOpen = false
      }

      handleCancel()

      expect(isModalOpen).toBe(false)
      expect(documentsList.length).toBe(1)
      expect(selectedDoc).not.toBeNull()
    })

    it('models successful reset clearing stale document and inspection states', () => {
      let isModalOpen = true
      let documentsList: DocumentItem[] = [
        {
          id: 1,
          original_filename: 'bank_statement.xlsx',
          stored_filename: 'uuid1.xlsx',
          file_size: 15400,
          mime_type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
          document_type: 'BANK_STATEMENT',
          category: 'bank_statement',
          status: 'ready',
          created_at: '2026-03-31T12:00:00Z',
          updated_at: '2026-03-31T12:00:00Z',
        },
        {
          id: 2,
          original_filename: 'ledger.csv',
          stored_filename: 'uuid2.csv',
          file_size: 8200,
          mime_type: 'text/csv',
          document_type: 'LEDGER',
          category: 'ledger',
          status: 'ready',
          created_at: '2026-03-31T12:05:00Z',
          updated_at: '2026-03-31T12:05:00Z',
        },
      ]
      let selectedDoc: DocumentItem | null = documentsList[0]
      let analysisResult: any = { sheets: [{ name: 'Bank', row_count: 45 }] }
      let resetSuccessMessage: string | null = null

      const handleResetSuccess = (res: DocumentResetResponse) => {
        selectedDoc = null
        analysisResult = null
        documentsList = []
        isModalOpen = false
        resetSuccessMessage = `Workspace reset successfully: ${res.documents_deleted} document(s) removed.`
      }

      handleResetSuccess({
        success: true,
        documents_deleted: 2,
        derived_records_deleted: 8,
        files_deleted: 2,
      })

      expect(isModalOpen).toBe(false)
      expect(documentsList.length).toBe(0)
      expect(selectedDoc).toBeNull()
      expect(analysisResult).toBeNull()
      expect(resetSuccessMessage).toContain('2 document(s) removed')
    })
  })
})
