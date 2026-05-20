from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from server.auth import (
    create_access_token,
    get_current_user,
    get_user_by_email,
    hash_password,
    verify_password,
)
from server.models import User as UserModel
from server.deps import SessionDep
from server.models import Organization, User
from server.schemas import (
    AuthTokenResponse,
    EnterpriseSignupRequest,
    LoginRequest,
    SignupRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:48] or "org"


def _user_out(session: SessionDep, user: User) -> UserOut:
    org_name = None
    if user.organization_id:
        org = session.get(Organization, user.organization_id)
        org_name = org.name if org else None
    return UserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        job_title=user.job_title,
        role=user.role,
        organization_id=user.organization_id,
        organization_name=org_name,
    )


@router.post("/signup", response_model=AuthTokenResponse)
def signup(body: SignupRequest, session: SessionDep):
    email = body.email.lower().strip()
    if get_user_by_email(session, email):
        raise HTTPException(400, "Email already registered")
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        role="member",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthTokenResponse(
        access_token=create_access_token(user.id),
        user=_user_out(session, user),
    )


@router.post("/signup/enterprise", response_model=AuthTokenResponse)
def signup_enterprise(body: EnterpriseSignupRequest, session: SessionDep):
    email = body.email.lower().strip()
    if get_user_by_email(session, email):
        raise HTTPException(400, "Email already registered")

    slug = (body.organization_slug or _slugify(body.organization_name)).lower().strip()
    existing = session.exec(select(Organization).where(Organization.slug == slug)).first()
    if existing:
        raise HTTPException(400, f"Organization slug '{slug}' is already taken")

    org = Organization(
        id=str(uuid.uuid4()),
        name=body.organization_name.strip(),
        slug=slug,
        plan=body.plan if body.plan in ("starter", "enterprise") else "enterprise",
    )
    session.add(org)
    session.flush()

    user = User(
        id=str(uuid.uuid4()),
        email=email,
        password_hash=hash_password(body.password),
        full_name=body.full_name.strip(),
        job_title=body.job_title,
        role="owner",
        organization_id=org.id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthTokenResponse(
        access_token=create_access_token(user.id),
        user=_user_out(session, user),
    )


@router.post("/login", response_model=AuthTokenResponse)
def login(body: LoginRequest, session: SessionDep):
    email = body.email.lower().strip()
    user = get_user_by_email(session, email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return AuthTokenResponse(
        access_token=create_access_token(user.id),
        user=_user_out(session, user),
    )


@router.get("/me", response_model=UserOut)
def me(session: SessionDep, user: UserModel = Depends(get_current_user)):
    return _user_out(session, user)
