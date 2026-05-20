"""SQLModel tables — users, orgs, projects, and blob storage."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class Organization(SQLModel, table=True):
    __tablename__ = "organization"

    id: str = Field(primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    plan: str = Field(default="starter")  # starter | enterprise
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: str = Field(primary_key=True)
    email: str = Field(index=True, unique=True)
    password_hash: str
    full_name: str
    job_title: str | None = None
    role: str = Field(default="member")  # member | admin | owner
    organization_id: str | None = Field(default=None, foreign_key="organization.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SchemaFolder(SQLModel, table=True):
    __tablename__ = "schema_folder"

    id: str = Field(primary_key=True)
    name: str
    parent_id: str | None = Field(default=None, foreign_key="schema_folder.id", index=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    organization_id: str | None = Field(default=None, foreign_key="organization.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectRecord(SQLModel, table=True):
    __tablename__ = "project"

    id: str = Field(primary_key=True)
    name: str
    folder_id: str | None = Field(default=None, foreign_key="schema_folder.id", index=True)
    owner_id: str = Field(foreign_key="user.id", index=True)
    organization_id: str | None = Field(default=None, foreign_key="organization.id", index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    parse_status: str = Field(default="idle")
    parse_error: str | None = None
    last_provider: str | None = None
    last_domain: str | None = None
    handdrawn: bool = Field(default=False)


class ProjectImage(SQLModel, table=True):
    __tablename__ = "project_image"

    project_id: str = Field(primary_key=True, foreign_key="project.id")
    data: bytes
    mime_type: str = Field(default="image/png")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProjectDiagram(SQLModel, table=True):
    __tablename__ = "project_diagram"

    project_id: str = Field(primary_key=True, foreign_key="project.id")
    json_text: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
