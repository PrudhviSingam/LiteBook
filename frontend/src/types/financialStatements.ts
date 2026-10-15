export type FSStatus = 'DRAFT' | 'ANALYZED' | 'REVIEW_REQUIRED' | 'UNDER_REVIEW' | 'APPROVED'
export type FSSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'

export interface FSProfile {
  id: number
  user_id: number
  entity_name: string
  cin_or_pan?: string | null
  financial_year: string
  reporting_period: string
  framework: string
  status: FSStatus
  approved_at?: string | null
  approved_by_user_id?: number | null
  approval_notes?: string | null
  created_at: string
  tb_entries_count: number
  bs_lines_count: number
  pl_lines_count: number
  cf_lines_count: number
  findings_count: number
}

export interface FSProfileCreatePayload {
  entity_name: string
  cin_or_pan?: string
  financial_year: string
  reporting_period?: string
  framework?: string
}

export interface TrialBalanceEntryItem {
  id: number
  profile_id: number
  account_code?: string | null
  account_name: string
  account_category: string
  debit_amount: number | string
  credit_amount: number | string
  net_balance: number | string
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  source_cell?: string | null
  source_value?: string | null
  provenance_notes?: string | null
  created_at: string
}

export interface BalanceSheetLineItem {
  id: number
  profile_id: number
  classification: string
  sub_category: string
  line_item_name: string
  amount: number | string
  schedule_note_number?: string | null
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  source_cell?: string | null
  provenance_notes?: string | null
  created_at: string
}

export interface ProfitLossLineItem {
  id: number
  profile_id: number
  category: string
  line_item_name: string
  amount: number | string
  schedule_note_number?: string | null
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  source_cell?: string | null
  provenance_notes?: string | null
  created_at: string
}

export interface CashFlowLineItem {
  id: number
  profile_id: number
  activity_type: string
  line_item_name: string
  amount: number | string
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  provenance_notes?: string | null
  created_at: string
}

export interface FSOverview {
  profile_id: number
  entity_name: string
  financial_year: string
  reporting_period: string
  framework: string
  status: FSStatus
  total_assets: number | string | null
  total_liabilities: number | string | null
  total_equity: number | string | null
  total_revenue: number | string | null
  total_expenses: number | string | null
  net_profit: number | string | null
  closing_cash: number | string | null
  trial_balance_difference: number | string | null
  is_tb_balanced: boolean
  is_bs_balanced: boolean
  unresolved_findings_count: number
  eligible_for_approval: boolean
  latest_snapshot_hash?: string | null
}

export interface FSSnapshot {
  id: number
  profile_id: number
  version: number
  snapshot_hash: string
  tb_total_debit: number | string
  tb_total_credit: number | string
  tb_difference: number | string
  tb_is_balanced: boolean
  total_assets: number | string
  total_equity_and_liabilities: number | string
  balance_difference: number | string
  is_balance_sheet_balanced: boolean
  total_revenue: number | string
  total_expenses: number | string
  profit_after_tax: number | string
  closing_cash: number | string
  created_at: string
}

export interface FSFinding {
  id: number
  profile_id: number
  finding_type: string
  severity: FSSeverity
  status: string
  category: string
  title: string
  description: string
  expected?: number | string | null
  actual?: number | string | null
  variance?: number | string | null
  possible_cause?: string | null
  proven_cause?: string | null
  evidence?: string | null
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  source_cell?: string | null
  accountant_decision?: string | null
  decision_notes?: string | null
}
