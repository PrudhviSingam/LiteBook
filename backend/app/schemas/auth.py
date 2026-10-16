from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email address")
    password: str = Field(..., min_length=6, description="User password (minimum 6 characters)")
    full_name: str = Field(..., min_length=1, description="Full name of accountant or user")
    username: Optional[str] = None
    organization: Optional[str] = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: Optional[str] = None
    full_name: str
    role: str
    is_active: bool
    is_superuser: bool
    organization_id: Optional[str] = None



class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, description="User email address")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
