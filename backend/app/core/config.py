from typing import Annotated, List, Union
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    from pydantic_settings import NoDecode
except ImportError:
    class NoDecode:
        pass
from pathlib import Path
import json


class Settings(BaseSettings):
    APP_NAME: str = "Finance AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS origins: Annotated with NoDecode to prevent pydantic-settings from crashing on comma-separated or unquoted strings
    BACKEND_CORS_ORIGINS: Annotated[Union[str, List[str]], NoDecode] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "https://litebooksingam.netlify.app",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(i).strip().rstrip("/") for i in parsed if str(i).strip()]
                except Exception:
                    pass
            return [i.strip().rstrip("/") for i in v.split(",") if i.strip()]
        if isinstance(v, (list, tuple, set)):
            return [str(i).strip().rstrip("/") for i in v if str(i).strip()]
        return []

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

    # Authentication & Security (internal defaults, no manual config needed)
    JWT_SECRET_KEY: str = "litebooks-autonomous-secret-key-production-safe"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Upload Security
    MAX_UPLOAD_SIZE_MB: int = 25

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
