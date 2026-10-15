import { useState, useEffect } from 'react'
import type { ModuleId } from './types'
import { AppShell } from './components/shell/AppShell'
import { Login } from './pages/Login'
import { isAuthenticated, clearAuthToken } from './services/api'
import { Dashboard } from './pages/Dashboard'
import { ReviewCenter } from './pages/ReviewCenter'
import { ReconciliationPage } from './pages/Reconciliation'
import { GSTReturnsPage } from './pages/GSTReturns'
import { ITRPage } from './pages/ITR'
import { FinancialStatementsPage } from './pages/FinancialStatements'
import { AIAssistantPage } from './pages/AIAssistant'
import { DocumentsPage } from './pages/Documents'
import { HistoryPage } from './pages/History'
import { SettingsPage } from './pages/Settings'

export default function App() {
  const [authed, setAuthed] = useState<boolean>(() => isAuthenticated())
  const [activeModule, setActiveModule] = useState<ModuleId>('dashboard')

  useEffect(() => {
    const handleUnauthorized = () => {
      setAuthed(false)
    }
    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [])

  const handleLogout = () => {
    clearAuthToken()
    setAuthed(false)
  }

  if (!authed) {
    return <Login onLoginSuccess={() => setAuthed(true)} />
  }

  const renderModule = () => {
    switch (activeModule) {
      case 'dashboard':
        return <Dashboard onNavigate={setActiveModule} />
      case 'review-center':
        return <ReviewCenter />
      case 'reconciliation':
        return <ReconciliationPage />
      case 'gst':
        return <GSTReturnsPage onNavigate={(mod) => setActiveModule(mod as any)} />
      case 'itr':
        return <ITRPage onNavigate={(mod) => setActiveModule(mod as any)} />
      case 'financial-statements':
        return <FinancialStatementsPage />
      case 'ai-assistant':
        return <AIAssistantPage />
      case 'documents':
        return <DocumentsPage />
      case 'history':
        return <HistoryPage />
      case 'settings':
        return <SettingsPage />
      default:
        return <Dashboard onNavigate={setActiveModule} />
    }
  }

  return (
    <AppShell
      activeModule={activeModule}
      onSelectModule={setActiveModule}
      onLogout={handleLogout}
    >
      {renderModule()}
    </AppShell>
  )
}

