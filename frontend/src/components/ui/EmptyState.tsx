import React from 'react'
import { Inbox } from 'lucide-react'
import { Button } from './Button'

interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  action?: React.ReactNode
  children?: React.ReactNode
}

export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  action,
  children,
}) => {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center glass-card border-dashed border-brand-200/60">
      <div className="w-14 h-14 rounded-2xl bg-brand-50/90 text-brand-600 flex items-center justify-center border border-brand-100/80 mb-4 shadow-xs">
        {icon || <Inbox className="w-6 h-6" />}
      </div>
      <h4 className="text-base font-bold text-slate-800 mb-1">{title}</h4>
      <p className="text-xs sm:text-sm text-slate-500 max-w-sm mb-5 leading-relaxed">
        {description}
      </p>
      {actionLabel && onAction && (
        <Button variant="primary" size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
      {action}
      {children}
    </div>
  )
}

