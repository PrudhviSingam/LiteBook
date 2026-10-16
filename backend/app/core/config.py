from typing import List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import json


class Settings(BaseSettings):
    APP_NAME: str = "Finance AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://litebooksingam.netlify.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v.startswith("["):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    # Database
    DATABASE_URL: str = "sqlite:///./finance_ai.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_database_url(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql://", 1)
        return v

    # Storage
    STORAGE_DIR: str = "./storage"

    # AI Configuration
    AI_PROVIDER: str = "mock"  # "mock", "sarvam", "groq", "gemini", "openai"
    AI_API_KEY: str = ""
    AI_MODEL_NAME: str = "mock-financial-v1"

    # Sarvam AI Configuration
    SARVAM_API_KEY: str = ""
    SARVAM_CHAT_MODEL: str = "sarvam-105b"

    # Authentication & Security
    JWT_SECRET_KEY: str = "dev-insecure-secret-key-change-in-prod-litebooks"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Upload Security
    MAX_UPLOAD_SIZE_MB: int = 25

    @field_validator("JWT_SECRET_KEY", mode="after")
    @classmethod
    def validate_jwt_secret(cls, v: str, info) -> str:
        # If in production mode, require a strong configured secret
        # Note: in pydantic-settings, other fields can be accessed via info.data
        env = info.data.get("APP_ENV", "development") if hasattr(info, "data") else "development"
        if env == "production":
            if not v or v in ("change-me", "dev-insecure-secret-key-change-in-prod-litebooks") or len(v) < 16:
                raise ValueError("JWT_SECRET_KEY must be securely configured with at least 16 characters in production mode.")
        return v

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def uploads_dir(self) -> Path:
        p = Path(self.STORAGE_DIR) / "uploads"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def reports_dir(self) -> Path:
        p = Path(self.STORAGE_DIR) / "reports"
        p.mkdir(parents=True, exist_ok=True)
        return p


settings = Settings()
