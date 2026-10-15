from fastapi import APIRouter
from app.core.config import settings
from app.ai.factory import get_ai_provider

router = APIRouter()


@router.get("/health")
def health_check():
    ai = get_ai_provider()
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "ai_provider": ai.provider_name,
        "database": "connected",
    }
