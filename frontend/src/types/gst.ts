export type GSTPeriodStatus = 'draft' | 'under_review' | 'approved' | 'filed' | 'locked'

export type GSTMatchStatus =
  | 'EXACT_MATCH'
  | 'PARTIAL_MATCH'
  | 'BOOKS_ONLY'
  | 'RETURN_ONLY'
  | 'EXCLUDED'

export type ReconciliationDecision =
  | 'PENDING'
  | 'ACCEPTED'
  | 'REJECTED'
  | 'MANUALLY_MATCHED'
  | 'EXCLUDED'

export interface GSTRegistration {
  id: string | number
  gstin: string
  legal_name: string
  trade_name?: string | null
  state_code: string
  state_name?: string | null
  registration_type: string
  authorized_signatory?: string | null
  is_active: boolean
  created_at: string
}

export interface GSTFilingPeriod {
  id: string | number
  registration_id: string | number
  period: string // YYYY-MM
  financial_year: string
  status: GSTPeriodStatus
  gstr1_status: string
  gstr3b_status: string
  gstr2b_status: string
  locked_at?: string | null
  filed_at?: string | null
  filing_arn?: string | null
  created_at: string
}

export interface GSTSalesInvoice {
  id: string | number
  registration_id?: string | number
  period_id: string | number
  invoice_number: string
  invoice_date: string
  customer_gstin?: string | null
  customer_name: string
  place_of_supply: string
  is_inter_state: boolean
  invoice_type: string // B2B, B2CL, B2CS, EXPORT, CDNR, NIL_EXEMPT
  hsn_code?: string | null
  taxable_value: string | number
  tax_rate: string | number
  cgst_amount: string | number
  sgst_amount: string | number
  igst_amount: string | number
  cess_amount: string | number
  total_amount: string | number
  is_reverse_charge: boolean
  validation_status: 'VALID' | 'WARNING' | 'ERROR'
  validation_errors?: string[] | null
  normalized_invoice_number?: string | null
  validation_issues?: Array<{
    code: string
    severity: string
    field: string
    message: string
    suggested_action: string
  }> | null
  created_at: string
}

export interface GSTPurchaseInvoice {
  id: string | number
  registration_id?: string | number
  period_id: string | number
  supplier_gstin: string
  supplier_name: string
  invoice_number: string
  invoice_date: string
  taxable_value: string | number
  cgst_amount: string | number
  sgst_amount: string | number
  igst_amount: string | number
  cess_amount: string | number
  total_amount: string | number
  itc_eligibility: boolean
  itc_category: string
  match_status: GSTMatchStatus
  created_at: string
}

export interface GSTR2BRecord {
  id: string | number
  registration_id?: string | number
  period_id: string | number
  supplier_gstin: string
  supplier_name: string
  invoice_number: string
  invoice_date: string
  invoice_type: string
  taxable_value: string | number
  cgst_amount: string | number
  sgst_amount: string | number
  igst_amount: string | number
  cess_amount: string | number
  total_amount: string | number
  itc_available: boolean
  filing_status: string
  gstr1_filing_date?: string | null
  created_at: string
}

export interface GSTReconciliationResult {
  id: string | number
  period_id: string | number
  purchase_invoice_id?: string | number | null
  gstr2b_record_id?: string | number | null
  match_status: GSTMatchStatus
  confidence_score: number
  taxable_difference: string | number
  tax_difference: string | number
  difference_reasons: string[]
  accountant_decision: ReconciliationDecision
  accountant_notes?: string | null
  matching_method?: string
  amount_tolerance?: string | number
  date_tolerance_days?: number
  manual_decision_preserved?: boolean
  purchase_invoice?: GSTPurchaseInvoice | null
  gstr2b_record?: GSTR2BRecord | null
  created_at: string
}

export interface GSTR1Summary {
  period_id: string | number
  total_taxable_value: string | number
  total_cgst: string | number
  total_sgst: string | number
  total_igst: string | number
  total_cess: string | number
  total_tax: string | number
  total_invoice_value: string | number
  total_invoices_count: number
  tables: Record<string, any>
  calculation_version?: number
  source_record_count?: number
  source_data_hash?: string | null
  is_stale?: boolean
  calculated_at: string
  updated_at?: string
}

export interface GSTR3BSummary {
  period_id: string | number
  outward_taxable_value: string | number
  outward_cgst: string | number
  outward_sgst: string | number
  outward_igst: string | number
  outward_cess: string | number
  outward_total_tax: string | number
  itc_cgst: string | number
  itc_sgst: string | number
  itc_igst: string | number
  itc_cess: string | number
  itc_total: string | number
  itc_reversed_cgst: string | number
  itc_reversed_sgst: string | number
  itc_reversed_igst: string | number
  itc_reversed_cess: string | number
  net_itc_cgst: string | number
  net_itc_sgst: string | number
  net_itc_igst: string | number
  net_itc_cess: string | number
  tax_payable_cgst: string | number
  tax_payable_sgst: string | number
  tax_payable_igst: string | number
  tax_payable_cess: string | number
  total_tax_payable: string | number
  set_off_summary: Record<string, any>
  calculation_version?: number
  source_record_count?: number
  source_data_hash?: string | null
  is_stale?: boolean
  calculated_at: string
  updated_at?: string
}

export interface ReconciliationSummary {
  total_records: number
  exact_matches: number
  partial_matches: number
  books_only: number
  return_only: number
  excluded: number
  match_rate_percentage: number
  total_books_taxable: string | number
  total_gstr2b_taxable: string | number
  total_itc_at_risk: string | number
}
