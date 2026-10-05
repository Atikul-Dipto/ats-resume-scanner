from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import rate_limit
from app.core.security import DUMMY_PASSWORD_HASH, create_access_token, hash_password, verify_password
from app.db.models import User
from app.schemas.api import Credentials, TokenOut, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_response(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post(
    "/register",
    response_model=TokenOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("auth"))],
)
def register(body: Credentials, db: DbSession):
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:  # lost a race with a concurrent signup
        db.rollback()
        raise HTTPException(409, "An account with this email already exists.") from exc
    return _token_response(user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(rate_limit("auth"))])
def login(body: Credentials, db: DbSession):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    # Hash even when the user doesn't exist, so timing doesn't leak which emails are registered.
    valid = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if user is None or not valid:
        raise HTTPException(401, "Incorrect email or password.")
    return _token_response(user)


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUser, db: DbSession):
    """Deletes the account and, by cascade, every saved resume and scan."""
    db.delete(user)
    db.commit()
