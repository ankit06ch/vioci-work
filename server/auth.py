"""Password hashing and JWT session tokens."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlmodel import Session, select

import os

from server.config import auth_disabled, JWT_ALGORITHM, JWT_EXPIRE_HOURS, JWT_SECRET
from server.models import User
from server.state import get_engine

_bearer = HTTPBearer(auto_error=False)


def _bcrypt_rounds() -> int:
    try:
        return max(4, min(15, int(os.environ.get("VIOCI_BCRYPT_ROUNDS", "12"))))
    except ValueError:
        return 12


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=_bcrypt_rounds()),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    payload = {"sub": user_id, "exp": expire, "jti": str(uuid.uuid4())}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        sub = payload.get("sub")
        return str(sub) if sub else None
    except JWTError:
        return None


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.exec(select(User).where(User.email == email.lower().strip())).first()


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if auth_disabled():
        with Session(get_engine()) as session:
            user = session.exec(select(User)).first()
            if user:
                return user
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "AUTH_DISABLED but no users — create one via /api/auth/signup",
        )

    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    with Session(get_engine()) as session:
        user = get_user_by_id(session, user_id)
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        return user


CurrentUser = Depends(get_current_user)
