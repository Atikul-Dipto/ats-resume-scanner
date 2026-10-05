from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]


def _bearer_token(request: Request) -> str | None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def get_optional_user(request: Request, db: DbSession) -> User | None:
    """The signed-in user, or None. A present-but-invalid token is an error,
    not anonymous access, so an expired session is surfaced to the client."""
    token = _bearer_token(request)
    if token is None:
        return None
    user_id = decode_access_token(token)
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(401, "Your session has expired — please sign in again.",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def get_current_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(401, "Sign in to access saved resumes.", headers={"WWW-Authenticate": "Bearer"})
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(403, "Admin access required.")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
