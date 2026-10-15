import React from 'react'
import { cn } from '../../utils/cn'

interface BadgeProps {
  variant?: 'pink' | 'success' | 'warning' | 'info' | 'neutral' | 'danger'
  children: React.ReactNode
  className?: string
  dot?: boolean
}

export const Badge: React.FC<BadgeProps> = ({
  variant = 'pink',
  children,
  className,
  dot = false,
}) => {
  const variants = {
    pink: 'bg-brand-50/90 text-brand-700 border-brand-200/80 shadow-2xs',
    success: 'bg-emerald-50/90 text-emerald-800 border-emerald-200/80 shadow-2xs',
    warning: 'bg-amber-50/90 text-amber-800 border-amber-200/80 shadow-2xs',
    info: 'bg-sky-50/90 text-sky-800 border-sky-200/80 shadow-2xs',
    neutral: 'bg-slate-50/90 text-slate-700 border-slate-200/80 shadow-2xs',
    danger: 'bg-rose-50/90 text-rose-800 border-rose-200/80 shadow-2xs',
  }

  const dotColors = {
    pink: 'bg-brand-500',
    success: 'bg-emerald-500',
    warning: 'bg-amber-500',
    info: 'bg-sky-500',
    neutral: 'bg-slate-400',
    danger: 'bg-rose-500',
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border backdrop-blur-xs',
        variants[variant],
        className
      )}
    >
      {dot && <span className={cn('w-1.5 h-1.5 rounded-full shrink-0', dotColors[variant])} />}
      {children}
    </span>
  )
}
