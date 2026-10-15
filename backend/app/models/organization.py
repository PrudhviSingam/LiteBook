from sqlalchemy import Column, String, Integer, ForeignKey
from app.models.base import BaseModel


class Organization(BaseModel):
    """Multi-tenant ready Organization abstraction.

    Allows future company expansion without disrupting single-accountant workflow.
    """
    __tablename__ = "organizations"

    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=True)


class OrganizationMember(BaseModel):
    """Member roles within an organization."""
    __tablename__ = "organization_members"

    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Roles: "OWNER", "ACCOUNTANT", "STAFF", "VIEWER"
    role = Column(String(50), default="ACCOUNTANT", nullable=False)
