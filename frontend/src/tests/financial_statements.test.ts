import { describe, it, expect } from 'vitest'
import { formatINR } from '../utils/formatters'
import type {
  TrialBalanceEntryItem,
  BalanceSheetLineItem,
  ProfitLossLineItem,
  CashFlowLineItem,
  FSFinding,
} from '../types/financialStatements'

describe('Financial Statements Frontend Logic & Synthetic Fixtures', () => {
  // Deterministic Synthetic Fixture
  const syntheticFixture = {
    entity_name: 'Apex Robotics Industrial Solutions Ltd',
    financial_year: '2023-24',
    reporting_period: 'ANNUAL',
    framework: 'SCHEDULE_III',
    trial_balance: [
      {
        account_code: '1001',
        account_name: 'Property, Plant & Equipment',
        account_category: 'ASSET',
        debit_amount: 1200000,
        credit_amount: 0,
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 4,
        source_cell: 'D4',
      },
      {
        account_code: '1002',
        account_name: 'Trade Receivables',
        account_category: 'ASSET',
        debit_amount: 450000,
        credit_amount: 0,
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 5,
        source_cell: 'D5',
      },
      {
        account_code: '1003',
        account_name: 'Cash and Cash Equivalents',
        account_category: 'ASSET',
        debit_amount: 250000,
        credit_amount: 0,
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 6,
        source_cell: 'D6',
      },
      {
        account_code: '2001',
        account_name: 'Share Capital',
        account_category: 'EQUITY',
        debit_amount: 0,
        credit_amount: 1000000,
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 7,
        source_cell: 'E7',
      },
      {
        account_code: '2002',
        account_name: 'Long-term Borrowings',
        account_category: 'LIABILITY',
        debit_amount: 0,
        credit_amount: 600000,
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 8,
        source_cell: 'E8',
      },
      {
        account_code: '2003',
        account_name: 'Trade Payables',
        account_category: 'LIABILITY',
        debit_amount: 0,
        credit_amount: 300000, // Intentional Discrepancy: Total Cr = 1,900,000 vs Total Dr = 1,900,000 (Balanced in TB)
        source_document: 'Synthetic_TB_FY24.xlsx',
        source_sheet: 'TB',
        source_row: 9,
        source_cell: 'E9',
      },
    ],
    // Balance Sheet lines with an intentional discrepancy:
    // Assets = 1,200,000 (PPE) + 450,000 (Receivables) + 250,000 (Cash) = 1,900,000
    // Equity & Liab = 1,000,000 (Equity) + 600,000 (Non-current Liab) + 250,000 (Current Liab) = 1,850,000 (Variance = 50,000!)
    balance_sheet: [
      { classification: 'NON_CURRENT_ASSETS', line_item_name: 'Property, Plant & Equipment', amount: 1200000 },
      { classification: 'CURRENT_ASSETS', line_item_name: 'Trade Receivables', amount: 450000 },
      { classification: 'CURRENT_ASSETS', line_item_name: 'Cash and Bank', amount: 250000 },
      { classification: 'EQUITY', line_item_name: 'Share Capital', amount: 1000000 },
      { classification: 'NON_CURRENT_LIABILITIES', line_item_name: 'Borrowings', amount: 600000 },
      { classification: 'CURRENT_LIABILITIES', line_item_name: 'Trade Payables', amount: 250000 }, // Discrepancy: 50,000 omitted!
    ],
  }

  describe('Trial Balance Deterministic Verification', () => {
    const verifyTB = (entries: { debit_amount: number; credit_amount: number }[]) => {
      const totalDebit = entries.reduce((acc, curr) => acc + curr.debit_amount, 0)
      const totalCredit = entries.reduce((acc, curr) => acc + curr.credit_amount, 0)
      const diff = Math.abs(totalDebit - totalCredit)
      return {
        totalDebit,
        totalCredit,
        diff,
        isBalanced: diff === 0,
      }
    }

    it('validates balanced synthetic trial balance correctly', () => {
      const res = verifyTB(syntheticFixture.trial_balance)
      expect(res.totalDebit).toBe(1900000)
      expect(res.totalCredit).toBe(1900000)
      expect(res.diff).toBe(0)
      expect(res.isBalanced).toBe(true)
    })

    it('detects unbalanced trial balance with exact variance', () => {
      const unbalancedEntries = [
        { debit_amount: 100000, credit_amount: 0 },
        { debit_amount: 0, credit_amount: 85000 },
      ]
      const res = verifyTB(unbalancedEntries)
      expect(res.totalDebit).toBe(100000)
      expect(res.totalCredit).toBe(85000)
      expect(res.diff).toBe(15000)
      expect(res.isBalanced).toBe(false)
    })
  })

  describe('Schedule III Balance Sheet Tally Verification', () => {
    const verifyBS = (lines: { classification: string; amount: number }[]) => {
      let assets = 0
      let equityAndLiabilities = 0

      for (const line of lines) {
        if (line.classification === 'NON_CURRENT_ASSETS' || line.classification === 'CURRENT_ASSETS') {
          assets += line.amount
        } else if (
          line.classification === 'EQUITY' ||
          line.classification === 'NON_CURRENT_LIABILITIES' ||
          line.classification === 'CURRENT_LIABILITIES'
        ) {
          equityAndLiabilities += line.amount
        }
      }

      const diff = Math.abs(assets - equityAndLiabilities)
      return {
        totalAssets: assets,
        totalEquityAndLiabilities: equityAndLiabilities,
        diff,
        isBalanced: diff === 0,
      }
    }

    it('detects intentional synthetic balance sheet discrepancy for Review Center', () => {
      const res = verifyBS(syntheticFixture.balance_sheet)
      expect(res.totalAssets).toBe(1900000)
      expect(res.totalEquityAndLiabilities).toBe(1850000)
      expect(res.diff).toBe(50000) // 50,000 variance detected!
      expect(res.isBalanced).toBe(false)
    })
  })

  describe('Profit & Loss Deterministic Aggregation', () => {
    const calculatePL = (lines: { category: string; amount: number }[]) => {
      let revenue = 0
      let expenses = 0
      let tax = 0
      let cogs = 0
      let employee = 0
      let otherExp = 0

      for (const l of lines) {
        if (l.category === 'REVENUE' || l.category === 'OTHER_INCOME') {
          revenue += l.amount
        } else if (l.category === 'TAX_EXPENSE') {
          tax += l.amount
        } else {
          expenses += l.amount
          if (l.category === 'COST_OF_MATERIALS') cogs += l.amount
          if (l.category === 'EMPLOYEE_BENEFITS') employee += l.amount
          if (l.category === 'OTHER_EXPENSES') otherExp += l.amount
        }
      }

      const ebitda = revenue - (cogs + employee + otherExp)
      const pbt = revenue - expenses
      const pat = pbt - tax
      return { revenue, expenses, ebitda, pbt, tax, pat }
    }

    it('calculates Revenue, Expenses, EBITDA, PBT, and PAT without guessing', () => {
      const plLines = [
        { category: 'REVENUE', amount: 2000000 },
        { category: 'OTHER_INCOME', amount: 50000 },
        { category: 'COST_OF_MATERIALS', amount: 800000 },
        { category: 'EMPLOYEE_BENEFITS', amount: 400000 },
        { category: 'FINANCE_COSTS', amount: 50000 },
        { category: 'DEPRECIATION', amount: 100000 },
        { category: 'OTHER_EXPENSES', amount: 200000 },
        { category: 'TAX_EXPENSE', amount: 125000 },
      ]
      const res = calculatePL(plLines)
      expect(res.revenue).toBe(2050000)
      expect(res.expenses).toBe(1550000)
      expect(res.ebitda).toBe(650000)
      expect(res.pbt).toBe(500000)
      expect(res.tax).toBe(125000)
      expect(res.pat).toBe(375000)
    })
  })

  describe('Approval Safety Checks', () => {
    const isEligibleForApproval = (
      isTbBalanced: boolean,
      isBsBalanced: boolean,
      findings: { severity: string; status: string }[]
    ): boolean => {
      if (!isTbBalanced) return false
      if (!isBsBalanced) return false
      const unresolvedCritical = findings.filter(
        (f) => (f.severity === 'CRITICAL' || f.severity === 'HIGH') && f.status !== 'APPROVED' && f.status !== 'REJECTED'
      )
      return unresolvedCritical.length === 0
    }

    it('blocks approval when balance sheet has a discrepancy', () => {
      const findings = [{ severity: 'CRITICAL', status: 'REVIEW_REQUIRED' }]
      expect(isEligibleForApproval(true, false, findings)).toBe(false)
    })

    it('blocks approval when critical review findings are unresolved', () => {
      const findings = [{ severity: 'CRITICAL', status: 'REVIEW_REQUIRED' }]
      expect(isEligibleForApproval(true, true, findings)).toBe(false)
    })

    it('permits approval only when balanced and findings are accepted/resolved', () => {
      const findings = [{ severity: 'CRITICAL', status: 'APPROVED' }]
      expect(isEligibleForApproval(true, true, findings)).toBe(true)
    })
  })
})
