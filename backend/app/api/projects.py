"""Saved projects: create, list, open (also via share link), save, copy, delete."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import optional_workspace, require_workspace
from app.db import ProjectRow, get_db, utcnow
from app.schemas import Project, ProjectCreate, ProjectData, ProjectSummary, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["projects"])

MAX_PROJECT_JSON_BYTES = 2_000_000


def to_project(row: ProjectRow, workspace: str | None) -> Project:
    return Project(
        id=row.id,
        name=row.name,
        is_demo=row.is_demo,
        can_edit=workspace is not None and row.owner_id == workspace,
        created_at=row.created_at,
        updated_at=row.updated_at,
        data=ProjectData.model_validate_json(row.data),
    )


def _serialise(data: ProjectData) -> str:
    payload = data.model_dump_json()
    if len(payload) > MAX_PROJECT_JSON_BYTES:
        raise HTTPException(413, detail={"message": "Project is too large to save."})
    return payload


def _owned(db: Session, project_id: str, workspace: str) -> ProjectRow:
    row = db.get(ProjectRow, project_id)
    if row is None:
        raise HTTPException(404, detail={"message": "Project not found."})
    if row.owner_id != workspace:
        raise HTTPException(403, detail={"message": "This project belongs to someone else. Make a copy to edit it."})
    return row


@router.get("")
def list_projects(workspace: str = Depends(require_workspace), db: Session = Depends(get_db)) -> list[ProjectSummary]:
    rows = db.scalars(select(ProjectRow).where(ProjectRow.owner_id == workspace).order_by(ProjectRow.updated_at.desc()))
    summaries = []
    for row in rows:
        data = ProjectData.model_validate_json(row.data)
        summaries.append(
            ProjectSummary(
                id=row.id,
                name=row.name,
                is_demo=row.is_demo,
                updated_at=row.updated_at,
                view_count=len(data.views),
                cover_image_id=data.views[0].image_id if data.views else None,
            )
        )
    return summaries


@router.post("", status_code=201)
def create_project(body: ProjectCreate, workspace: str = Depends(require_workspace), db: Session = Depends(get_db)) -> Project:
    now = utcnow()
    row = ProjectRow(
        id=uuid.uuid4().hex[:16],
        owner_id=workspace,
        name=body.name.strip(),
        data=_serialise(body.data),
        created_at=now,
        updated_at=now,
    )
    db.add(row)
    db.commit()
    return to_project(row, workspace)


@router.get("/{project_id}")
def get_project(project_id: str, workspace: str | None = Depends(optional_workspace), db: Session = Depends(get_db)) -> Project:
    row = db.get(ProjectRow, project_id)
    if row is None:
        raise HTTPException(404, detail={"message": "Project not found."})
    return to_project(row, workspace)


@router.put("/{project_id}")
def update_project(
    project_id: str, body: ProjectUpdate, workspace: str = Depends(require_workspace), db: Session = Depends(get_db)
) -> Project:
    row = _owned(db, project_id, workspace)
    row.name = body.name.strip()
    row.data = _serialise(body.data)
    row.updated_at = utcnow()
    db.commit()
    return to_project(row, workspace)


@router.post("/{project_id}/copy", status_code=201)
def copy_project(project_id: str, workspace: str = Depends(require_workspace), db: Session = Depends(get_db)) -> Project:
    source = db.get(ProjectRow, project_id)
    if source is None:
        raise HTTPException(404, detail={"message": "Project not found."})
    now = utcnow()
    name = source.name if source.is_demo else f"{source.name} (copy)"
    row = ProjectRow(id=uuid.uuid4().hex[:16], owner_id=workspace, name=name[:120], data=source.data, created_at=now, updated_at=now)
    db.add(row)
    db.commit()
    return to_project(row, workspace)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, workspace: str = Depends(require_workspace), db: Session = Depends(get_db)) -> Response:
    row = _owned(db, project_id, workspace)
    db.delete(row)
    db.commit()
    return Response(status_code=204)
