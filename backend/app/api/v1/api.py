from fastapi import APIRouter
from app.api.v1.endpoints import health, auth, dashboard, documents, history, review_center
from app.modules.reconciliation.routes import router as reconciliation_router
from app.modules.ai_assistant.routes import router as assistant_router
from app.modules.gst.routes import router as gst_router
from app.modules.itr.routes import router as itr_router
from app.modules.financial_statements.routes import router as financial_statements_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
api_router.include_router(review_center.router, prefix="/review-center", tags=["Review Center"])
api_router.include_router(documents.router, prefix="/documents", tags=["Documents"])
api_router.include_router(history.router, prefix="/history", tags=["History"])
api_router.include_router(reconciliation_router, prefix="/reconciliation", tags=["Reconciliation"])
api_router.include_router(assistant_router, prefix="/assistant", tags=["AI Assistant"])
api_router.include_router(gst_router, prefix="/gst", tags=["GST"])
api_router.include_router(itr_router, prefix="/itr", tags=["ITR"])
api_router.include_router(financial_statements_router, prefix="/financial-statements", tags=["Financial Statements"])


