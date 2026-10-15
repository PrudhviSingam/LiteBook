import React from 'react'
import { Card } from './Card'

interface StatCardProps {
  title: string
  value: string | number
  icon: React.ReactNode
  description?: string
  trend?: string
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  icon,
  description,
  trend,
}) => {
  return (
    <Card hoverable className="relative overflow-hidden p-5 flex flex-col justify-between">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 block truncate">
            {title}
          </span>
          <h3 className="mt-1.5 text-2xl font-bold text-slate-800 tracking-tight font-sans">
            {value}
          </h3>
        </div>
        <div className="w-10 h-10 rounded-xl bg-brand-50/80 text-brand-600 flex items-center justify-center shrink-0 border border-brand-100 shadow-2xs">
          {icon}
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between text-xs text-slate-500 pt-3 border-t border-slate-100/80">
        <span className="truncate">{description || 'Active accounting ledger'}</span>
        {trend && (
          <span className="font-semibold text-emerald-700 bg-emerald-50/80 px-2 py-0.5 rounded-md border border-emerald-200/60 shrink-0">
            {trend}
          </span>
        )}
      </div>
    </Card>
  )
}
