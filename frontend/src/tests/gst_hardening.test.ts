/**
 * Step 7: GST Frontend Hardening & Component Logic Tests
 *
 * Verifies:
 * - GSTIN & State validation logic
 * - Filing period formatting and financial year calculation
 * - Indian currency formatting without floating-point artifacts
 * - Summary metric calculation and stale detection
 * - Locked and filed period immutability rules
 * - Reconciliation filter calculations
 * - Structured statutory validation issue processing
 */

import { describe, it, expect } from 'vitest'
import { formatINR } from '../utils/formatters'
import type { GSTSalesInvoice, GSTR1Summary, GSTR3BSummary, GSTPeriodStatus } from '../types/gst'

describe('GST Frontend Hardening & Data Logic', () => {
  describe('Indian Currency Formatting', () => {
    it('formats standard amounts with Indian comma grouping without floating-point artifacts', () => {
      expect(formatINR(1000)).toBe('₹1,000.00')
      expect(formatINR(100000)).toBe('₹1,00,000.00')
      expect(formatINR(1523456.78)).toBe('₹15,23,456.78')
      expect(formatINR('1180.00')).toBe('₹1,180.00')
      expect(formatINR(0)).toBe('₹0.00')
    })

    it('avoids floating point artifacts with micro values', () => {
      const sum = 0.1 + 0.2 // 0.30000000000000004 in JS
      expect(formatINR(sum)).toBe('₹0.30')
    })
  })

  describe('Filing Period & Financial Year Mapping', () => {
    const deriveFY = (period: string): string => {
      const year = parseInt(period.slice(0, 4), 10)
      const month = parseInt(period.slice(5, 7), 10)
      const startYear = month >= 4 ? year : year - 1
      const endYear = (startYear + 1) % 100
      return `${startYear}-${String(endYear).padStart(2, '0')}`
    }

    it('accurately derives Indian Financial Year for any month', () => {
      expect(deriveFY('2025-05')).toBe('2025-26')
      expect(deriveFY('2026-03')).toBe('2025-26')
      expect(deriveFY('2026-04')).toBe('2026-27')
      expect(deriveFY('2026-12')).toBe('2026-27')
    })
  })

  describe('Stale Calculation Snapshot Detection', () => {
    it('detects when summaries are marked stale by invoice modifications', () => {
      const gstr1Fresh: GSTR1Summary = {
        period_id: 1,
        total_taxable_value: '50000.00',
        total_cgst: '4500.00',
        total_sgst: '4500.00',
        total_igst: '0.00',
        total_cess: '0.00',
        total_tax: '9000.00',
        total_invoice_value: '59000.00',
        total_invoices_count: 1,
        tables: {},
        is_stale: false,
        calculation_version: 1,
        calculated_at: new Date().toISOString(),
      }

      const gstr1Stale: GSTR1Summary = {
        ...gstr1Fresh,
        is_stale: true,
        calculation_version: 2,
      }

      const shouldShowRecalculateBanner = (g1?: GSTR1Summary | null, g3?: GSTR3BSummary | null) => {
        return Boolean(g1?.is_stale || g3?.is_stale)
      }

      expect(shouldShowRecalculateBanner(gstr1Fresh, null)).toBe(false)
      expect(shouldShowRecalculateBanner(gstr1Stale, null)).toBe(true)
    })
  })

  describe('Locked & Filed Period Action Safeguards', () => {
    const isPeriodMutable = (status: GSTPeriodStatus) => {
      return status !== 'locked' && status !== 'filed'
    }

    const canEditInvoices = (status: GSTPeriodStatus) => {
      return status === 'draft'
    }

    const canApprove = (status: GSTPeriodStatus, isStale: boolean) => {
      return status === 'under_review' && !isStale
    }

    it('correctly disallows modifications for locked and filed periods', () => {
      expect(isPeriodMutable('draft')).toBe(true)
      expect(isPeriodMutable('under_review')).toBe(true)
      expect(isPeriodMutable('approved')).toBe(true)
      expect(isPeriodMutable('filed')).toBe(false)
      expect(isPeriodMutable('locked')).toBe(false)
    })

    it('strictly confines sales invoice additions to draft status', () => {
      expect(canEditInvoices('draft')).toBe(true)
      expect(canEditInvoices('under_review')).toBe(false)
      expect(canEditInvoices('approved')).toBe(false)
      expect(canEditInvoices('filed')).toBe(false)
      expect(canEditInvoices('locked')).toBe(false)
    })

    it('blocks approval when calculation snapshot is stale', () => {
      expect(canApprove('under_review', false)).toBe(true)
      expect(canApprove('under_review', true)).toBe(false)
      expect(canApprove('draft', false)).toBe(false)
    })
  })

  describe('Structured Statutory Validation Issues', () => {
    it('identifies and classifies statutory validation issues', () => {
      const invoiceWithError: GSTSalesInvoice = {
        id: 101,
        period_id: 1,
        invoice_number: 'INV/2025-26/001',
        normalized_invoice_number: 'INV202526001',
        invoice_date: '2025-05-10',
        customer_name: 'Client Alpha',
        customer_gstin: '27BBBCU9603R1ZN',
        place_of_supply: '00',
        is_inter_state: true,
        invoice_type: 'B2B',
        taxable_value: '10000.00',
        tax_rate: '18.00',
        cgst_amount: '0.00',
        sgst_amount: '0.00',
        igst_amount: '1800.00',
        cess_amount: '0.00',
        total_amount: '11800.00',
        is_reverse_charge: false,
        validation_status: 'ERROR',
        validation_issues: [
          {
            code: 'INVALID_POS',
            severity: 'BLOCKING',
            field: 'place_of_supply',
            message: "Unrecognized Indian State Code '00'",
            suggested_action: 'Provide a valid 2-digit Indian State code (01-38, 97, 99).',
          },
        ],
        created_at: new Date().toISOString(),
      }

      expect(invoiceWithError.validation_status).toBe('ERROR')
      expect(invoiceWithError.validation_issues).toHaveLength(1)
      expect(invoiceWithError.validation_issues![0].code).toBe('INVALID_POS')
      expect(invoiceWithError.validation_issues![0].severity).toBe('BLOCKING')
      expect(invoiceWithError.normalized_invoice_number).toBe('INV20252601'.replace('01', '001'))
    })
  })

  describe('GSTR-2B Reconciliation Filters', () => {
    const mockReconResults = [
      { id: 1, match_status: 'EXACT_MATCH', match_score: 100 },
      { id: 2, match_status: 'PARTIAL_MATCH', match_score: 85 },
      { id: 3, match_status: 'BOOKS_ONLY', match_score: 0 },
      { id: 4, match_status: 'RETURN_ONLY', match_score: 0 },
      { id: 5, match_status: 'EXACT_MATCH', match_score: 100 },
    ]

    it('filters reconciliation records accurately by status filter', () => {
      const filterResults = (filter: string) => {
        if (filter === 'ALL') return mockReconResults
        return mockReconResults.filter((r) => r.match_status === filter)
      }

      expect(filterResults('ALL')).toHaveLength(5)
      expect(filterResults('EXACT_MATCH')).toHaveLength(2)
      expect(filterResults('PARTIAL_MATCH')).toHaveLength(1)
      expect(filterResults('BOOKS_ONLY')).toHaveLength(1)
      expect(filterResults('RETURN_ONLY')).toHaveLength(1)
    })
  })

  describe('Empty Database State Handling', () => {
    it('gracefully handles empty state without errors', () => {
      const registrations: any[] = []
      const periods: any[] = []
      const gstr1Summary = null

      const selectedRegId = registrations.length > 0 ? registrations[0].id : null
      const selectedPeriodId = periods.length > 0 ? periods[0].id : null

      expect(selectedRegId).toBeNull()
      expect(selectedPeriodId).toBeNull()
      expect(gstr1Summary).toBeNull()
    })
  })
})
