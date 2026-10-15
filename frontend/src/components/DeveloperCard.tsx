import React, { useState } from 'react'
import { Mail, Code2, ExternalLink } from 'lucide-react'

export interface DeveloperCardProps {
  name?: string
  role?: string
  email?: string
  avatarUrl?: string
  githubUrl?: string
  className?: string
  compact?: boolean
  variant?: 'full' | 'sidebar'
}

export const DeveloperCard: React.FC<DeveloperCardProps> = ({
  name = 'Singam Prudhviswar Reddy',
  role = 'Core Platform Engineer',
  email = 'singamprudhviswerreddy@gmail.com',
  avatarUrl = '/assets/singam-profile.png',
  githubUrl,
  className = '',
  compact = false,
  variant = 'full',
}) => {
  const [imageError, setImageError] = useState(false)

  // Sidebar variant: compact "Built by Singam" card for the AI Assistant sidebar
  if (variant === 'sidebar') {
    return (
      <div
        className={`glass-panel p-3 border border-white/80 shadow-xs rounded-2xl flex items-center justify-between gap-3 text-slate-800 transition-all hover:border-brand-300/80 hover:shadow-md ${className}`}
      >
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="relative shrink-0">
            {!imageError ? (
              <img
                src={avatarUrl}
                alt="Singam"
                onError={() => setImageError(true)}
                className="w-10 h-10 rounded-full object-cover ring-2 ring-brand-200/70 shadow-2xs"
              />
            ) : (
              <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-600 to-brand-400 text-white font-bold text-sm flex items-center justify-center ring-2 ring-brand-200/70 shadow-2xs">
                S
              </div>
            )}
            <span
              className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-white"
              title="Active Contributor"
            />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <span className="text-xs font-bold text-slate-900 truncate">
                Built by Singam
              </span>
              <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[9px] font-bold bg-brand-50 text-brand-700 border border-brand-200/60 uppercase tracking-wider shrink-0">
                Developer
              </span>
            </div>

            <a
              href={`mailto:${email}`}
              className="text-[11px] text-brand-600 hover:text-brand-700 hover:underline flex items-center gap-1 mt-0.5 font-medium truncate"
              title={`Send email to ${email}`}
            >
              <Mail className="w-3 h-3 shrink-0 text-brand-500" />
              <span className="truncate">{email}</span>
            </a>
          </div>
        </div>

        {githubUrl && (
          <a
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1 rounded-lg text-slate-400 hover:text-brand-600 hover:bg-brand-50/80 transition shrink-0"
            title="View GitHub Profile"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        )}
      </div>
    )
  }

  // Full variant (default) used in Dashboard, Settings, etc.
  return (
    <div
      className={`glass-panel p-3.5 sm:p-4 border border-white/80 shadow-xs rounded-2xl flex items-center justify-between gap-3 text-slate-800 transition-all hover:border-brand-300/80 hover:shadow-md ${className}`}
    >
      <div className="flex items-center gap-3 min-w-0">
        <div className="relative shrink-0">
          {!imageError ? (
            <img
              src={avatarUrl}
              alt={name}
              onError={() => setImageError(true)}
              className="w-10 h-10 rounded-full object-cover ring-2 ring-brand-200/70 shadow-2xs"
            />
          ) : (
            <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-brand-600 to-brand-400 text-white font-bold text-sm flex items-center justify-center ring-2 ring-brand-200/70 shadow-2xs">
              {name.charAt(0).toUpperCase()}
            </div>
          )}
          <span
            className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 ring-2 ring-white"
            title="Active Contributor"
          />
        </div>

        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-xs sm:text-sm font-bold text-slate-900 truncate">
              {name}
            </span>
            <span className="inline-flex items-center px-1.5 py-0.5 rounded-md text-[9px] font-bold bg-brand-50 text-brand-700 border border-brand-200/60 uppercase tracking-wider shrink-0">
              Developer
            </span>
          </div>

          {!compact && (
            <p className="text-[11px] text-slate-500 truncate flex items-center gap-1 mt-0.5">
              <Code2 className="w-3 h-3 text-slate-400 shrink-0" />
              <span>{role}</span>
            </p>
          )}

          <a
            href={`mailto:${email}`}
            className="text-[11px] text-brand-600 hover:text-brand-700 hover:underline flex items-center gap-1 mt-0.5 font-medium truncate"
            title={`Send email to ${email}`}
          >
            <Mail className="w-3 h-3 shrink-0 text-brand-500" />
            <span className="truncate">{email}</span>
          </a>
        </div>
      </div>

      {githubUrl && (
        <a
          href={githubUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="p-1.5 rounded-xl text-slate-400 hover:text-brand-600 hover:bg-brand-50/80 transition shrink-0"
          title="View GitHub Profile"
        >
          <ExternalLink className="w-4 h-4" />
        </a>
      )}
    </div>
  )
}
