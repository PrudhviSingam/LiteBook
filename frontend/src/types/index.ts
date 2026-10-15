export type ModuleId =
  | 'dashboard'
  | 'review-center'
  | 'reconciliation'
  | 'gst'
  | 'itr'
  | 'financial-statements'
  | 'ai-assistant'
  | 'documents'
  | 'history'
  | 'settings'

export interface DocumentItem {
  id: number
  original_filename: string
  stored_filename: string
  file_size: number
  mime_type: string
  category: 'bank_statement' | 'ledger' | 'gst' | 'itr' | 'financial' | 'general' | string
  status: 'uploaded' | 'ready' | 'processing' | 'archived' | 'error' | string
  checksum?: string | null
  file_hash?: string | null
  document_type?: string | null
  analysis_status?: string | null
  notes?: string | null
  created_at: string
  updated_at: string
}

export interface HistoryRecord {
  id: number
  module: string
  action: string
  target_name: string
  status: 'completed' | 'pending' | 'in_progress' | 'failed' | string
  result_summary?: string | null
  user_action: string
  report_reference?: string | null
  document_id?: number | null
  created_at: string
  updated_at: string
}

export interface AttentionItem {
  id: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL' | 'INFO' | string
  finding_type: string
  title: string
  document_name: string
  document_id?: number | null
  financial_period?: string | null
  difference?: number | null
  status: string
  cell_address?: string | null
}

export interface RecentDocumentItem {
  id: number
  original_filename: string
  category: string
  document_type: string
  financial_period?: string | null
  created_at: string
  status: string
  findings_count: number
  needs_review_count: number
  file_size: number
}

export interface DashboardSummaryData {
  total_reports: number
  pending_items: number
  recent_documents: number
  reconciliations: number
  user_name: string
  is_demo_data: boolean
  recent_activities: HistoryRecord[]
  total_documents: number
  analyzed_documents: number
  needs_review_count: number
  high_severity_count: number
  reconciliation_needs_review: number
  needs_attention_items: AttentionItem[]
  recent_documents_list: RecentDocumentItem[]
}

export interface ReviewFindingItem {
  id: string
  document_id?: number | null
  document_name: string
  session_id?: number | null
  category: string
  financial_period?: string | null
  type: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW' | 'CRITICAL' | 'INFO' | string
  status: 'NEEDS_REVIEW' | 'UNDER_REVIEW' | 'APPROVED' | 'REJECTED' | 'IGNORED' | 'CORRECTED' | 'REVIEW_REQUIRED' | string
  title: string
  description: string
  expected_value?: number | null
  actual_value?: number | null
  difference?: number | null
  currency: string
  sheet_name?: string | null
  cell_address?: string | null
  row_reference?: string | null
  column_reference?: string | null
  formula?: string | null
  confidence: 'Deterministic' | 'HIGH' | 'MEDIUM' | 'LOW' | 'REVIEW_REQUIRED' | string
  row_index?: number | null
  possible_cause?: string | null
  finding_type?: string | null
  proven_cause?: string | null
  possible_causes: string[]
  ai_explanation?: string | null
  recommended_actions: string[]
  correction_id?: string | null
  original_value_display?: string | null
  proposed_value_display?: string | null
  created_at?: string | null
  reviewed_at?: string | null
  accountant_decision?: string | null
  decision_notes?: string | null
}

export interface ReviewCenterSummary {
  all_count: number
  high_count: number
  medium_count: number
  low_count: number
  review_required_count: number
  reviewed_count: number
  severity_breakdown?: Record<string, number>
  findings: ReviewFindingItem[]
}

export interface FindingDecisionRequest {
  decision: 'APPROVE' | 'REJECT' | 'IGNORE' | 'UNDER_REVIEW' | string
  notes?: string
  propose_correction?: boolean
  proposed_value?: string
}

export interface UserProfile {
  id: number
  full_name: string
  email: string
  role: string
  organization?: string
}

// Reconciliation Module Types
export type ReconciliationStatus =
  | 'MATCHED'
  | 'AMOUNT_MISMATCH'
  | 'DATE_MISMATCH'
  | 'REFERENCE_MISMATCH'
  | 'MISSING_IN_LEDGER'
  | 'MISSING_IN_BANK'
  | 'POSSIBLE_DUPLICATE'
  | 'REVIEW_REQUIRED'

export type DifferenceType =
  | 'CHANGED_VALUE'
  | 'MISSING_ROW'
  | 'EXTRA_ROW'
  | 'DUPLICATE_ENTRY'
  | 'UNMATCHED'
  | 'MATCHED'

export interface SourceLocation {
  file_name?: string
  sheet_name?: string
  row_number?: number | null
  cell_address?: string | null
}

export interface MatchingFactors {
  amount_match: boolean
  date_match: boolean
  reference_match: boolean
  description_similarity: number
}

export interface NormalizedTransaction {
  id: string
  date: string
  description: string
  reference: string
  debit: number
  credit: number
  amount: number
  direction: 'debit' | 'credit'
  source: 'bank' | 'ledger'
  filename?: string
  sheet_name?: string
  original_row_number?: number
  cell_addresses?: Record<string, string>
  raw_row?: Record<string, any>
}

export interface ReconciliationItem {
  id: string
  item_id?: string
  status: ReconciliationStatus
  difference_type?: DifferenceType
  bank_transaction?: NormalizedTransaction | null
  ledger_transaction?: NormalizedTransaction | null
  bank_date?: string | null
  ledger_date?: string | null
  description: string
  reference?: string | null
  bank_amount?: number | null
  ledger_amount?: number | null
  difference: number
  match_tier?: number | null
  confidence: 'high' | 'medium' | 'low'
  matching_factors: MatchingFactors
  reason: string
  suggested_action: string
  // Difference Detection Provenance
  relevant_field?: string | null
  source_a_location?: SourceLocation | null
  source_b_location?: SourceLocation | null
  source_a_value?: any
  source_b_value?: any
  source_a_entry?: Record<string, any> | null
  source_b_entry?: Record<string, any> | null
  review_status?: 'PENDING_REVIEW' | 'REVIEWED' | 'CONFIRMED' | 'IGNORED' | string
}

export interface ReconciliationSummary {
  total_bank_transactions: number
  total_ledger_transactions: number
  matched_count: number
  unmatched_count: number
  amount_mismatch_count: number
  date_mismatch_count: number
  reference_mismatch_count: number
  missing_in_ledger_count: number
  missing_in_bank_count: number
  possible_duplicate_count: number
  reconciliation_rate: number
  total_bank_amount: number
  total_ledger_amount: number
  total_variance: number
  // Difference Detection Counts
  changed_value_count?: number
  missing_row_count?: number
  extra_row_count?: number
  duplicate_count?: number
  unmatched_record_count?: number
  total_discrepancies?: number
  matched_records?: number
  match_rate_percentage?: number
  missing_rows?: number
  extra_rows?: number
}

export interface ReconciliationSessionResponse {
  id: number
  session_id?: number
  bank_statement_name: string
  ledger_file_name: string
  status: string
  summary: ReconciliationSummary
  transactions: ReconciliationItem[]
  items?: ReconciliationItem[]
  created_at: string
  file_a_name?: string
  file_b_name?: string
  sheet_a_name?: string
  sheet_b_name?: string
  excel_report_url?: string
  difference_summary?: Record<string, any>
}

export interface ColumnMappingPreview {
  filename: string
  total_rows: number
  detected_columns: string[]
  column_mapping: Record<string, string | null>
  sample_rows: Record<string, any>[]
  status?: string
  message?: string | null
  sheet_names?: string[]
  selected_sheet?: string
  is_ambiguous?: boolean
  ambiguity_reason?: string | null
  available_columns?: string[]
}

export type DocumentType =
  | 'BANK_STATEMENT'
  | 'ACCOUNTING_LEDGER'
  | 'TRIAL_BALANCE'
  | 'BALANCE_SHEET'
  | 'PROFIT_LOSS'
  | 'FINANCIAL_STATEMENT'
  | 'UNKNOWN'

export interface SheetInspectionInfo {
  sheet_name: string
  name?: string
  row_count: number
  col_count: number
  detected_columns: string[]
  classification: DocumentType
  header_row_index: number
  period_columns: string[]
  has_merged_cells: boolean
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  is_recommended: boolean
}

export interface WorkbookInspectionResult {
  filename: string
  total_sheets: number
  sheet_count?: number
  total_rows?: number
  sheets: SheetInspectionInfo[]
  recommended_sheet: string
  document_type: DocumentType
  header_row_index: number
  period_columns: string[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  status: 'ready' | 'REVIEW_REQUIRED'
  message?: string | null
  sample_data: Record<string, any>[]
  classification_evidence?: {
    signals_found?: string[]
    confidence_score?: number
    explanation?: string
  } | null
  period_info?: {
    start_date?: string | null
    end_date?: string | null
    financial_year?: string | null
    raw_text?: string | null
  } | null
  tables?: any[]
  discrepancies?: any[]
}

export interface DiscrepancyExplanationResponse {
  what: string
  where: {
    sheet_name: string
    section: string
    account: string
    field: string
    row_reference: any
  }
  original_value: any
  expected_value: any
  difference: number
  reason_category: string
  summary: string
  possible_reasons: string[]
  proposed_correction?: {
    target_sheet: string
    target_row: any
    target_field: string
    original_value: any
    proposed_value: any
    difference: number
    description: string
  } | null
  evidence: string[]
  recommended_verification: string[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
}

export type CorrectionStatus =
  | 'PROPOSED'
  | 'CONFIRMED'
  | 'REJECTED'
  | 'GENERATED'
  | 'FAILED'

export interface CorrectionProposal {
  correction_id: string
  session_id: number
  document_id?: number | null
  sheet_name: string
  row_reference: any
  field: string
  original_value: any
  proposed_value: any
  difference: number
  reason_category: string
  explanation: string
  evidence: string[]
  recommended_verification: string[]
  confidence: 'HIGH' | 'MEDIUM' | 'LOW'
  status: CorrectionStatus
  accountant_decision?: string | null
  decision_notes?: string | null
  created_at?: string | null
}

export interface GenerateCorrectedWorkbookResponse {
  success: boolean
  original_filename: string
  generated_filename: string
  download_url: string
  document_id?: number | null
  applied_corrections_count: number
  corrections_sheet_name: string
  message: string
}

// AI Assistant Types
export type AssistantIntent =
  | 'GENERAL_ACCOUNTING'
  | 'FILE_SUMMARY'
  | 'FIND_MISMATCH'
  | 'FIND_MISSING_RECORD'
  | 'COMPARE_FILES'
  | 'EXPLAIN_DISCREPANCY'
  | 'EXPLAIN_ROW'
  | 'RECONCILIATION_HELP'
  | 'CORRECTION_REQUEST'
  | 'DOCUMENTS_QUERY'
  | 'UNKNOWN'

export interface AssistantFileContext {
  document_id: number
  filename: string
  document_type: string
  sheet_name: string
  period?: string | null
  status: string
  row_count?: number
  columns?: string[]
  sample_data?: any[]
  message?: string | null
}

export interface DiscrepancyFinding {
  title: string
  location: string
  sheet: string
  expected_value?: string | null
  actual_value?: string | null
  difference?: string | null
  reason_category: string
  summary: string
  possible_reasons: string[]
  evidence: string[]
  recommended_verification: string[]
  confidence: string
}

export interface CorrectionProposalInfo {
  correction_id: string
  document_id?: number | null
  sheet_name: string
  row_reference: any
  field: string
  original_value: any
  proposed_value: any
  difference: number
  reason_category: string
  explanation: string
  evidence: string[]
  recommended_verification: string[]
  confidence: string
  status: string
}

export interface AssistantChatResponse {
  conversation_id: string
  message: string
  intent: AssistantIntent
  files: AssistantFileContext[]
  findings: DiscrepancyFinding[]
  evidence: string[]
  recommended_actions: string[]
  correction_available: boolean
  correction_id?: string | null
  proposal?: CorrectionProposalInfo | null
  confidence: string
}

export interface AssistantMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp: string
  intent?: AssistantIntent
  findings?: DiscrepancyFinding[]
  proposal?: CorrectionProposalInfo | null
  correction_available?: boolean
  correction_id?: string | null
  files?: AssistantFileContext[]
  confidence?: string
  error?: boolean
}

export interface DocumentResetResponse {
  success: boolean
  documents_deleted: number
  derived_records_deleted: number
  files_deleted: number
}

export * from './gst'
export * from './itr'
export * from './financialStatements'
