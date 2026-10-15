# Finance AI — Foundation

**Finance AI** is a specialized accounting and finance automation workspace initially designed for a professional accountant, engineered with a modular, extensible foundation ready for multi-tenant and enterprise capabilities.

---

## 1. System Architecture

```
d:/LiteBooks/
├── frontend/                     # React 19 + TypeScript + Vite + Tailwind CSS
│   ├── src/
│   │   ├── components/
│   │   │   ├── shell/            # AppShell, Sidebar, Header
│   │   │   ├── ui/               # Button, Card, Badge, StatCard, EmptyState
│   │   │   └── documents/        # FileUploadZone
│   │   ├── pages/                # All 9 module pages
│   │   │   ├── Dashboard.tsx     # Overview cards & activity feed
│   │   │   ├── Documents.tsx     # Upload area, filters, & documents table
│   │   │   ├── History.tsx       # Audit trail & action history
│   │   │   ├── Reconciliation.tsx# Bank reconciliation foundation
│   │   │   ├── GSTReturns.tsx    # GSTR-1, 2B, 3B foundation
│   │   │   ├── ITR.tsx           # Income Tax Return foundation
│   │   │   ├── FinancialStatements.tsx # P&L, Balance Sheet foundation
│   │   │   ├── AIAssistant.tsx   # Pluggable AI conversational assistant
│   │   │   └── Settings.tsx      # Single-user profile & architecture status
│   │   ├── modules/              # Modular domain boundaries for future logic
│   │   │   ├── reconciliation/
│   │   │   ├── gst/
│   │   │   ├── itr/
│   │   │   ├── financial-statements/
│   │   │   └── ai-assistant/
│   │   ├── services/             # API client with offline fallback resilience
│   │   └── types/                # Strict TypeScript models
│   └── package.json
│
├── backend/                      # Python FastAPI application
│   ├── app/
│   │   ├── api/v1/endpoints/     # health, dashboard, documents, history
│   │   ├── core/                 # Config (pydantic-settings) & DB engine
│   │   ├── models/               # SQLAlchemy models (User, Document, HistoryRecord, etc.)
│   │   ├── schemas/              # Pydantic validation schemas
│   │   ├── services/             # Document storage & history service
│   │   ├── ai/                   # Pluggable provider abstraction (Mock, Gemini, OpenAI)
│   │   └── modules/              # Domain logic modules for future steps
│   ├── run.py                    # Uvicorn server runner
│   ├── requirements.txt
│   └── .env.example
├── .gitignore
└── README.md
```

---

## 2. Design System

- **Primary Theme**: White + Soft Pink
- **Aesthetic**: Minimal, professional, light-mode accounting SaaS.
- **Accents**: Soft blush pink (`#FFF1F5`, `#FCE7ED`, `#E05A87`, `#BE185D`)
- **Typography**: Plus Jakarta Sans / Inter
- **Icons**: Lucide React line icons

---

## 3. How to Run the Project

### Prerequisites
- Node.js (v18+)
- Python (v3.10+)

### Start Backend
```powershell
cd backend
python run.py
```
- API Health Check: `http://127.0.0.1:8000/api/v1/health`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/api/v1/docs`

### Start Frontend
```powershell
cd frontend
npm run dev
```
- Open browser at: `http://localhost:5173`

---

## 4. Single-User Foundation & Future Scalability

- **Initial State**: Streamlined for single-user operation (no permission blockers or complex tenancy hurdles).
- **Extensibility**: Database models (`User`, `Document`, `HistoryRecord`) already contain tenant and authorization hooks to enable team roles, multi-company accounting, and approval workflows in future updates without requiring architectural rewrites.
