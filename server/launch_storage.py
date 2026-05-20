"""Persist launch load overrides and last physics report."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlmodel import Session

from server.models import ProjectLaunchLoads, ProjectLaunchReport


def load_overrides(session: Session, project_id: str) -> dict:
    rec = session.get(ProjectLaunchLoads, project_id)
    if not rec or not rec.json_text:
        return {}
    try:
        return json.loads(rec.json_text)
    except json.JSONDecodeError:
        return {}


def save_overrides(session: Session, project_id: str, data: dict) -> dict:
    text = json.dumps(data)
    rec = session.get(ProjectLaunchLoads, project_id)
    if rec:
        rec.json_text = text
        rec.updated_at = datetime.now(timezone.utc)
    else:
        rec = ProjectLaunchLoads(project_id=project_id, json_text=text)
        session.add(rec)
    session.commit()
    return data


def save_report(session: Session, project_id: str, report: dict) -> None:
    text = json.dumps(report)
    rec = session.get(ProjectLaunchReport, project_id)
    if rec:
        rec.json_text = text
        rec.updated_at = datetime.now(timezone.utc)
    else:
        session.add(ProjectLaunchReport(project_id=project_id, json_text=text))
    session.commit()


def load_report(session: Session, project_id: str) -> dict | None:
    rec = session.get(ProjectLaunchReport, project_id)
    if not rec:
        return None
    try:
        return json.loads(rec.json_text)
    except json.JSONDecodeError:
        return None
