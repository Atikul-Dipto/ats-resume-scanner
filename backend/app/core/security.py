"""Password hashing (stdlib scrypt — no native extension to build) and JWTs."""

import base64
import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta

import jwt

from app.core.config import get_settings

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_ALGORITHM = "HS256"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt_b64, digest_b64 = stored.split("$")
        if scheme != "scrypt":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode(), salt=base64.b64decode(salt_b64), n=int(n), r=int(r), p=int(p)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(actual, expected)


# Verified against when the email doesn't exist, so a login attempt costs the
# same either way and response timing doesn't reveal which emails are registered.
DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing")


_generated_keys: dict[str, str] = {}


def _load_or_create_secret(name: str) -> str:
    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError

    from app.db.models import AppSecret
    from app.db.session import get_session_factory

    with get_session_factory()() as db:
        value = db.scalar(select(AppSecret.value).where(AppSecret.name == name))
        if value:
            return value
        db.add(AppSecret(name=name, value=secrets.token_urlsafe(48)))
        try:
            db.commit()
        except IntegrityError:  # another instance created it first — use theirs
            db.rollback()
        return db.scalar(select(AppSecret.value).where(AppSecret.name == name))


def signing_key() -> str:
    """JWT_SECRET when configured; otherwise a random key generated once and
    stored in the database, so a deploy without the env var is still secure
    (never the public dev default)."""
    settings = get_settings()
    if settings.jwt_secret_configured:
        return settings.jwt_secret
    url = settings.sqlalchemy_url
    if url not in _generated_keys:
        _generated_keys[url] = _load_or_create_secret("jwt_signing_key")
    return _generated_keys[url]


def create_access_token(user_id: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, signing_key(), algorithm=_ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Returns the user id, or None for any invalid/expired token."""
    try:
        payload = jwt.decode(token, signing_key(), algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) else None
