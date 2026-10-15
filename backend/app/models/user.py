from sqlalchemy import Column, String, Boolean
from app.models.base import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=True)
    full_name = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=True, nullable=False)

    # Authentication
    hashed_password = Column(String(255), nullable=True)

    # Modular extensible placeholder fields for future multi-user / client segregation
    role = Column(String(50), default="accountant", nullable=False)
    organization_id = Column(String(100), nullable=True)

