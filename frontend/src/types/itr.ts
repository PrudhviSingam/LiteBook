export type ITRRegime = 'NEW' | 'OLD' | 'UNDECIDED'

export type ITRStatus = 'DRAFT' | 'ANALYZED' | 'REVIEW_REQUIRED' | 'UNDER_REVIEW' | 'APPROVED'

export type IncomeHead =
  | 'SALARY'
  | 'BUSINESS_PROFESSION'
  | 'HOUSE_PROPERTY'
  | 'CAPITAL_GAINS'
  | 'OTHER_SOURCES'

export type VerificationStatus = 'VERIFIED' | 'REVIEW_REQUIRED' | 'UNVERIFIED'

export type DeductionStatus = 'VERIFIED' | 'REVIEW_REQUIRED' | 'NOT_SUPPORTED' | 'EXCLUDED'

export interface ITRProfile {
  id: number
  user_id: number
  pan: string
  taxpayer_name: string
  taxpayer_category: string
  assessment_year: string
  financial_year: string
  selected_regime: ITRRegime
  status: ITRStatus
  approved_at?: string | null
  approved_by_user_id?: number | null
  approval_notes?: string | null
  created_at: string
  income_count?: number
  deduction_count?: number
  tax_credit_count?: number
  findings_count?: number
}

export interface ITRIncomeEntry {
  id: number
  profile_id: number
  head_of_income: IncomeHead
  subcategory: string
  description?: string
  gross_amount: number | string
  exemptions_allowances: number | string
  net_taxable_amount: number | string
  verification_status: VerificationStatus
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  source_cell?: string | null
  provenance_notes?: string | null
  created_at: string
}

export interface ITRDeductionEntry {
  id: number
  profile_id: number
  section: string
  description: string
  claimed_amount: number | string
  eligible_amount: number | string
  status: DeductionStatus
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  provenance_notes?: string | null
  created_at: string
}

export interface ITRTaxCreditEntry {
  id: number
  profile_id: number
  credit_type: 'TDS_SALARY' | 'TDS_OTHER' | 'TCS' | 'ADVANCE_TAX' | 'SELF_ASSESSMENT_TAX'
  deductor_or_bank?: string | null
  deductor_tan_pan?: string | null
  section_code?: string | null
  challan_or_cert_no?: string | null
  credit_amount: number | string
  date_of_payment?: string | null
  verification_status: VerificationStatus
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  provenance_notes?: string | null
  created_at: string
}

export interface ITRComputation {
  profile_id: number
  regime: 'NEW' | 'OLD'
  computation_hash: string
  gross_salary: number | string
  standard_deduction: number | string
  net_salary: number | string
  house_property_income: number | string
  business_profession_income: number | string
  capital_gains: number | string
  other_sources_income: number | string
  gross_total_income: number | string
  total_deductions: number | string
  total_taxable_income: number | string
  basic_tax: number | string
  rebate_87a: number | string
  tax_after_rebate: number | string
  cess_4_pct: number | string
  total_tax_liability: number | string
  tds_total: number | string
  tcs_total: number | string
  advance_tax_total: number | string
  self_assessment_tax_total: number | string
  total_taxes_paid: number | string
  net_payable_or_refund: number | string
  breakdown: {
    slab_details?: Array<{
      slab: string
      rate: string
      taxable: number | string
      tax: number | string
    }>
    deduction_details?: Record<string, any>
  }
}

export interface ITRRegimeComparison {
  profile_id: number
  pan: string
  taxpayer_name: string
  assessment_year: string
  selected_regime: ITRRegime
  old_regime: ITRComputation
  new_regime: ITRComputation
  difference_in_tax: number | string
  unresolved_findings_count: number
  eligible_for_approval: boolean
}

export interface ITRFinding {
  id: number
  profile_id: number
  finding_type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  status: string
  title: string
  description: string
  category: string
  expected_value?: number | string | null
  actual_value?: number | string | null
  difference?: number | string | null
  source_document?: string | null
  source_sheet?: string | null
  source_row?: number | null
  possible_causes: string[]
  recommended_actions: string[]
  accountant_decision?: string | null
  decision_notes?: string | null
}
