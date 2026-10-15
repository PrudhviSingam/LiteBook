import React, { useState } from 'react'
import type { ModuleId } from '../../types'
import { Sidebar } from './Sidebar'
import { Header } from './Header'
import { X } from 'lucide-react'

interface AppShellProps {
  activeModule: ModuleId
  onSelectModule: (module: ModuleId) => void
  onLogout?: () => void
  children: React.ReactNode
}

export const AppShell: React.FC<AppShellProps> = ({
  activeModule,
  onSelectModule,
  onLogout,
  children,
}) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  return (
    <div className="flex h-screen bg-gradient-to-br from-pink-50/70 via-white to-rose-50/60 overflow-hidden text-slate-800 relative selection:bg-brand-100 selection:text-brand-900">
      {/* Background Decorative Ambient Radial Lights */}
      <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <div className="absolute -top-32 -left-32 w-96 h-96 rounded-full bg-brand-200/20 blur-3xl" />
        <div className="absolute top-1/3 -right-32 w-96 h-96 rounded-full bg-brand-100/30 blur-3xl" />
        <div className="absolute -bottom-32 left-1/3 w-96 h-96 rounded-full bg-brand-200/15 blur-3xl" />
      </div>

      {/* Desktop Floating Glass Sidebar */}
      <div className="hidden lg:flex lg:flex-shrink-0 z-20 p-3 h-screen">
        <Sidebar
          activeModule={activeModule}
          onSelectModule={onSelectModule}
          onLogout={onLogout}
        />
      </div>

      {/* Mobile Drawer Navigation */}
      {mobileMenuOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-slate-900/30 backdrop-blur-sm transition-opacity"
            onClick={() => setMobileMenuOpen(false)}
          />

          {/* Drawer container */}
          <div className="relative flex-1 flex flex-col max-w-[270px] w-full p-2.5 z-10 animate-in slide-in-from-left duration-200">
            <div className="absolute top-4 right-4 z-20">
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-white/80 cursor-pointer shadow-xs"
                aria-label="Close menu"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
            <Sidebar
              activeModule={activeModule}
              onSelectModule={onSelectModule}
              onCloseMobile={() => setMobileMenuOpen(false)}
              onLogout={onLogout}
            />
          </div>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden z-10">
        <Header
          activeModule={activeModule}
          onToggleMobileMenu={() => setMobileMenuOpen(true)}
        />

        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <div className="max-w-6xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
