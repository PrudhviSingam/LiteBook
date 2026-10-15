from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import Base, engine
from app.api.v1.api import api_router
import app.models  # Ensure all SQLAlchemy models are registered before tables are created


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables
    Base.metadata.create_all(bind=engine)
    # Schema is now governed strictly by Alembic database migrations.
    # Runtime schema alteration on startup has been safely removed.

    # Ensure storage paths exist
    _ = settings.uploads_dir
    _ = settings.reports_dir

    # Ensure default accountant account exists for seamless local development (disabled in production)
    if settings.APP_ENV != "production":
        from app.core.database import SessionLocal
        from app.models.user import User
        from app.core.security import hash_password
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == "accountant@litebooks.ai").first()
            if not user:
                user = User(
                    email="accountant@litebooks.ai",
                    full_name="Partner Accountant",
                    hashed_password=hash_password("Password123!"),
                    role="accountant",
                    is_active=True,
                    is_superuser=False,
                )
                db.add(user)
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="Finance AI — Specialized accounting and finance automation workspace.",
    version="1.0.0-foundation",
    lifespan=lifespan,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS configuration
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include v1 API router
app.include_router(api_router, prefix=settings.API_V1_STR)

# Also expose under /api/gst for direct unversioned frontend access if needed
from app.modules.gst.routes import router as gst_router
app.include_router(gst_router, prefix="/api/gst", tags=["GST"])

from app.modules.itr.routes import router as itr_router
app.include_router(itr_router, prefix="/api/itr", tags=["ITR"])

from app.modules.financial_statements.routes import router as financial_statements_router
app.include_router(financial_statements_router, prefix="/api/financial-statements", tags=["Financial Statements"])


@app.get("/")
def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API Foundation",
        "docs_url": f"{settings.API_V1_STR}/docs",
        "version": "1.0.0-foundation",
    }
