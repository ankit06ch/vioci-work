"""HTTP request/response models for the web API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SchemaFolderOut(BaseModel):
    id: str
    name: str
    parent_id: str | None = None
    created_at: datetime


class SchemaFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None


class ProjectFolderMove(BaseModel):
    folder_id: str | None = None


class ProjectOut(BaseModel):
    id: str
    name: str
    folder_id: str | None = None
    created_at: datetime
    parse_status: str
    parse_error: str | None = None
    last_provider: str | None = None
    last_domain: str | None = None
    handdrawn: bool = False
    has_diagram: bool = False
    image_enhanced: bool = False
    image_quality_score: float | None = None


class UploadResponse(BaseModel):
    projects: list[ProjectOut]


class ParseRequest(BaseModel):
    """Legacy JSON body accepted but ignored. Parsing uses Google + autodetect."""

    model_config = ConfigDict(extra="ignore")


class ParseQueued(BaseModel):
    status: str = "queued"


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


class SimulateRequest(BaseModel):
    engine: str = "analytic_rc"
    overrides: dict[str, Any] = Field(default_factory=dict)


class SweepRequest(BaseModel):
    engine: str = "analytic_rc"
    axis: dict[str, list[Any]]


class SweepPoint(BaseModel):
    overrides: dict[str, Any]
    result: dict[str, Any]


class SignupRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str


class EnterpriseSignupRequest(BaseModel):
    organization_name: str
    organization_slug: str | None = None
    plan: str = "enterprise"
    email: str
    password: str = Field(min_length=8)
    full_name: str
    job_title: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    job_title: str | None = None
    role: str
    organization_id: str | None = None
    organization_name: str | None = None


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut | None = None


class OrganizationOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
