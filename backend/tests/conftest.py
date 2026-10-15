import pytest
from typing import Optional
from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import Base, SessionLocal, engine, get_db
from app.core.security import get_password_hash
from app.core.auth import get_current_user, oauth2_scheme
from app.main import app as fastapi_app
from app.core.config import settings
from app.models.user import User
import app.models
import app.modules.gst.models

# Ensure tests run against deterministic local mock provider without hitting external rate-limited APIs
settings.AI_PROVIDER = "mock"

# Ensure all database tables exist
Base.metadata.create_all(bind=engine)


@pytest.fixture(scope="session")
def default_test_user():
    """Ensures a default test user exists for backwards compatibility of existing tests."""
    db = SessionLocal()
    user = db.query(User).filter(User.username == "default_testuser").first()
    if not user:
        user = User(
            username="default_testuser",
            email="testuser@litebooks.ai",
            hashed_password=get_password_hash("ValidPass123!"),
            full_name="Default Test Accountant",
            role="ACCOUNTANT",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    user_id = user.id
    db.close()

    # Refresh in fresh session when needed
    db2 = SessionLocal()
    u = db2.query(User).filter(User.id == user_id).first()
    db2.close()
    return u


@pytest.fixture(autouse=True)
def setup_default_user_override(default_test_user):
    """Automatically provides the default test user via dependency override
    when no Authorization token is passed, so that legacy tests without auth headers continue passing seamlessly,
    while allowing real JWT tokens to authenticate their actual users.
    """
    def _smart_get_current_user(
        db: Session = Depends(get_db),
        token: Optional[str] = Depends(oauth2_scheme),
    ):
        if token:
            return get_current_user(db=db, token=token)
        return default_test_user

    fastapi_app.dependency_overrides[get_current_user] = _smart_get_current_user
    yield default_test_user
    fastapi_app.dependency_overrides.pop(get_current_user, None)
