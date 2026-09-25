import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_optional_user
from app.database import get_db
from app.models import ActivityLog, Project, Task, User
from app.schemas import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db)):
    """Lists all active project workspaces with task counts."""
    projects = db.query(Project).all()
    results = []
    for p in projects:
        count = db.query(Task).filter(Task.project_id == p.id).count()
        results.append(
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                icon=p.icon,
                owner_id=p.owner_id,
                created_at=p.created_at,
                task_count=count,
            )
        )
    return results


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Creates a new dynamic project workspace."""
    project_id = f"proj-{uuid.uuid4().hex[:6]}"
    new_proj = Project(
        id=project_id,
        name=payload.name.strip(),
        description=payload.description or "",
        icon=payload.icon or "folder",
        owner_id=current_user.id if current_user else None,
    )
    db.add(new_proj)

    # Log activity
    user_name = current_user.name if current_user else "Team Member"
    user_avatar = current_user.avatar if current_user else ""
    log = ActivityLog(
        id=f"act-{uuid.uuid4().hex[:8]}",
        project_id=project_id,
        user_name=user_name,
        user_avatar=user_avatar,
        action_type="create_project",
        message=f"Created new project workspace: {new_proj.name}",
    )
    db.add(log)
    db.commit()
    db.refresh(new_proj)

    return ProjectResponse(
        id=new_proj.id,
        name=new_proj.name,
        description=new_proj.description,
        icon=new_proj.icon,
        owner_id=new_proj.owner_id,
        created_at=new_proj.created_at,
        task_count=0,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(project_id: str, db: Session = Depends(get_db)):
    """Deletes a custom project workspace (cannot delete default core project)."""
    if project_id == "proj-core":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete the default core benchmark workspace.",
        )

    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found.")

    db.delete(proj)
    db.commit()
    return None
