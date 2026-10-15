import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


def get_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """Dependency ensuring that the incoming request is authenticated with a valid JWT.

    Raises HTTP 401 if missing, invalid, or expired.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate authentication credentials. Please log in.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not token:
        raise credentials_exception

    payload = decode_access_token(token)
    if not payload:
        raise credentials_exception

    user_ident = payload.get("sub")
    if not user_ident:
        raise credentials_exception

    user = None
    if str(user_ident).isdigit():
        user = db.query(User).filter(User.id == int(user_ident)).first()
    if not user:
        user = db.query(User).filter(User.email == user_ident).first()
    if not user and payload.get("user_id"):
        user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if not user and payload.get("email"):
        user = db.query(User).filter(User.email == payload.get("email")).first()

    if not user:
        raise credentials_exception


    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account.",
        )

    return user


def get_optional_current_user(
    db: Session = Depends(get_db),
    token: Optional[str] = Depends(oauth2_scheme),
) -> Optional[User]:
    """Dependency that returns the authenticated User if a valid token is passed,

    or None if no authentication token is provided.
    """
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    user_email = payload.get("sub")
    if not user_email:
        return None
    return db.query(User).filter(User.email == user_email, User.is_active == True).first()


def verify_ownership(
    resource_owner_id: Optional[int],
    current_user: User,
    resource_name: str = "resource",
) -> None:
    """Verifies that the current authenticated user owns the target resource.

    If resource is owned by another user and current_user is not a superuser, raises HTTP 403 Forbidden.
    """
    if current_user.is_superuser:
        return
    if resource_owner_id is not None and resource_owner_id != current_user.id:
        logger.warning(
            "Access violation attempt: User %s (ID: %s) attempted to access %s owned by User ID %s",
            current_user.email,
            current_user.id,
            resource_name,
            resource_owner_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You do not have permission to access this {resource_name}.",
        )
