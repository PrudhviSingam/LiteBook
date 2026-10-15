import { describe, it, expect } from 'vitest'
import { formatINR } from '../utils/formatters'
import type { ITRProfile, ITRRegimeComparison, ITRFinding } from '../types/itr'

describe('ITR Frontend Workflow & Computation Logic', () => {
  describe('PAN Validation', () => {
    const isValidPAN = (pan: string): boolean => {
      const panRegex = /^[A-Z]{5}[0-9]{4}[A-Z]{1}$/
      return panRegex.test(pan.trim().toUpperCase())
    }

    it('validates 10-character Indian PAN correctly', () => {
      expect(isValidPAN('ABCDE1234F')).toBe(true)
      expect(isValidPAN('aaapa1234k')).toBe(true)
      expect(isValidPAN('ABCDE123')).toBe(false)
      expect(isValidPAN('ABCDE12345')).toBe(false)
      expect(isValidPAN('12345ABCDE')).toBe(false)
    })
  })

  describe('AY to FY Derivation', () => {
    const deriveFYFromAY = (ay: string): string => {
      const parts = ay.split('-')
      const startAY = parseInt(parts[0], 10)
      const startFY = startAY - 1
      const endFY = (startFY + 1) % 100
      return `${startFY}-${String(endFY).padStart(2, '0')}`
    }

    it('derives accurate Financial Year from Assessment Year', () => {
      expect(deriveFYFromAY('2024-25')).toBe('2023-24')
      expect(deriveFYFromAY('2025-26')).toBe('2024-25')
      expect(deriveFYFromAY('2026-27')).toBe('2025-26')
    })
  })

  describe('Section 288A Rounding Rule', () => {
    const roundSec288A = (val: number): number => {
      const rem = val % 10
      return rem >= 5 ? val - rem + 10 : val - rem
    }

    it('rounds total taxable income to nearest multiple of ten', () => {
      expect(roundSec288A(500004)).toBe(500000)
      expect(roundSec288A(500005)).toBe(500010)
      expect(roundSec288A(500009)).toBe(500010)
      expect(roundSec288A(725134)).toBe(725130)
      expect(roundSec288A(725135)).toBe(725140)
    })
  })

  describe('Chapter VI-A 80C Statutory Limit', () => {
    const cap80C = (claimed: number): number => {
      return Math.min(claimed, 150000)
    }

    it('caps Section 80C deductions at ₹1,50,000 max', () => {
      expect(cap80C(120000)).toBe(120000)
      expect(cap80C(150000)).toBe(150000)
      expect(cap80C(220000)).toBe(150000)
    })
  })

  describe('Health & Education Cess Calculation', () => {
    const calcCess = (taxAfterRebate: number): number => {
      return Math.round(taxAfterRebate * 0.04 * 100) / 100
    }

    it('computes 4% Health & Education cess accurately', () => {
      expect(calcCess(100000)).toBe(4000)
      expect(calcCess(97500)).toBe(3900)
      expect(calcCess(0)).toBe(0)
    })
  })

  describe('Regime Comparison Variance & Safety Check', () => {
    it('computes exact differential between Old and New regimes without bias', () => {
      const oldTax = 101400
      const newTax = 78000
      const diff = Math.abs(oldTax - newTax)
      expect(diff).toBe(23400)
      expect(formatINR(diff)).toBe('₹23,400.00')
    })

    it('strictly requires no unresolved critical/high findings for approval eligibility', () => {
      const checkEligibility = (
        findings: Array<{ severity: string; status: string }>,
        selectedRegime: string
      ): boolean => {
        const hasUnresolved = findings.some(
          (f) =>
            ['CRITICAL', 'HIGH'].includes(f.severity) &&
            ['REVIEW_REQUIRED', 'UNDER_REVIEW'].includes(f.status)
        )
        return !hasUnresolved && ['NEW', 'OLD'].includes(selectedRegime)
      }

      // Blocked because regime is UNDECIDED
      expect(checkEligibility([], 'UNDECIDED')).toBe(false)

      // Blocked because unresolved HIGH finding exists
      expect(
        checkEligibility(
          [{ severity: 'HIGH', status: 'REVIEW_REQUIRED' }],
          'NEW'
        )
      ).toBe(false)

      // Eligible when finding is RESOLVED and regime is explicit
      expect(
        checkEligibility(
          [{ severity: 'HIGH', status: 'APPROVED' }],
          'NEW'
        )
      ).toBe(true)
    })
  })
})
