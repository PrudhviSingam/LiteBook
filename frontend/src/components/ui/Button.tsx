import React from 'react'
import { cn } from '../../utils/cn'
import { Loader2 } from 'lucide-react'

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
  icon?: React.ReactNode
  isLoading?: boolean
}

export const Button: React.FC<ButtonProps> = ({
  variant = 'primary',
  size = 'md',
  className,
  children,
  icon,
  isLoading = false,
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-semibold rounded-xl transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-brand-400 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer select-none active:scale-[0.98]'

  const variants = {
    primary:
      'bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white shadow-sm hover:shadow-md shadow-brand-500/20',
    secondary:
      'bg-white/80 hover:bg-white text-slate-700 border border-slate-200/90 hover:border-brand-200 hover:text-brand-700 backdrop-blur-xs shadow-2xs',
    outline:
      'border border-slate-200/90 hover:border-brand-300 hover:bg-brand-50/40 text-slate-700 bg-transparent',
    ghost:
      'text-slate-600 hover:text-slate-900 hover:bg-slate-100/70 focus:ring-slate-300',
    danger:
      'bg-rose-50/90 hover:bg-rose-100/90 text-rose-700 border border-rose-200/80 hover:border-rose-300 shadow-2xs',
  }

  const sizes = {
    sm: 'text-xs px-3 py-1.5 gap-1.5',
    md: 'text-sm px-4 py-2 gap-2',
    lg: 'text-base px-5 py-2.5 gap-2.5',
  }

  return (
    <button
      className={cn(baseStyles, variants[variant], sizes[size], className)}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <Loader2 className="w-4 h-4 animate-spin shrink-0" />
      ) : (
        icon && <span className="shrink-0">{icon}</span>
      )}
      {children}
    </button>
  )
}
