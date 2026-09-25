import json
import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_optional_user
from app.database import get_db
from app.engine.dag_engine import DAGEngine
from app.engine.types import DependencyEdge, TaskColumn, TaskNode
from app.models import ActivityLog, Dependency, Task, TaskComment, User
from app.routers.board import build_board_state
from app.schemas import (
    BoardResponse,
    TaskCommentCreate,
    TaskCommentResponse,
    TaskCreate,
    TaskMove,
    TaskUpdate,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Creates a new task and recomputes the schedule."""
    task_id = payload.id or f"task-{uuid.uuid4().hex[:8]}"
    project_id = payload.project_id or "proj-core"

    if db.query(Task).filter(Task.id == task_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Task with ID '{task_id}' already exists.",
        )

    # Compute default position in column
    max_pos = db.query(Task).filter(
        Task.project_id == project_id,
        Task.column == payload.column.value,
    ).count()
    pos = payload.position if payload.position is not None else float(max_pos + 1)

    # Resolve assignee info
    assignee_name = payload.assignee_name
    assignee_avatar = payload.assignee_avatar
    if payload.assignee_id:
        u = db.query(User).filter(User.id == payload.assignee_id).first()
        if u:
            assignee_name = u.name
            assignee_avatar = u.avatar

    tags_json = json.dumps(payload.tags) if payload.tags else "[]"
    subtasks_json = json.dumps(payload.subtasks) if payload.subtasks else "[]"

    new_task = Task(
        id=task_id,
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        column=payload.column.value,
        position=pos,
        duration_days=payload.duration_days,
        planned_start=payload.planned_start,
        priority=payload.priority or "p2",
        assignee_id=payload.assignee_id,
        assignee_name=assignee_name,
        assignee_avatar=assignee_avatar,
        tags=tags_json,
        progress=payload.progress or 0,
        subtasks=subtasks_json,
    )
    db.add(new_task)
    db.commit()

    # Log activity
    actor = current_user.name if current_user else "Team Member"
    actor_avatar = current_user.avatar if current_user else ""
    db.add(
        ActivityLog(
            id=f"act-{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            user_name=actor,
            user_avatar=actor_avatar,
            action_type="create",
            message=f"Created task {new_task.title} ({task_id})",
            task_id=task_id,
        )
    )
    db.commit()

    # If initial prerequisites provided, validate and add them
    if payload.prerequisite_ids:
        for p_id in payload.prerequisite_ids:
            if not db.query(Task).filter(Task.id == p_id).first():
                continue
            dep = Dependency(task_id=task_id, prerequisite_id=p_id, source="manual")
            db.add(dep)
        db.commit()

    return build_board_state(db, project_id=project_id, changed_task_ids=[task_id])


@router.patch("/{task_id}", response_model=BoardResponse)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Updates task fields and propagates schedule downstream."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    date_or_duration_changed = False

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.duration_days is not None and payload.duration_days != task.duration_days:
        task.duration_days = payload.duration_days
        date_or_duration_changed = True
    if payload.planned_start is not None and payload.planned_start != task.planned_start:
        task.planned_start = payload.planned_start
        date_or_duration_changed = True
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.progress is not None:
        task.progress = payload.progress
    if payload.tags is not None:
        task.tags = json.dumps(payload.tags)
    if payload.subtasks is not None:
        task.subtasks = json.dumps(payload.subtasks)
    if payload.assignee_id is not None:
        task.assignee_id = payload.assignee_id
        if payload.assignee_id:
            u = db.query(User).filter(User.id == payload.assignee_id).first()
            if u:
                task.assignee_name = u.name
                task.assignee_avatar = u.avatar
        else:
            task.assignee_name = None
            task.assignee_avatar = None
    elif payload.assignee_name is not None:
        task.assignee_name = payload.assignee_name
        task.assignee_avatar = payload.assignee_avatar

    # Log update activity
    actor = current_user.name if current_user else "Team Member"
    actor_avatar = current_user.avatar if current_user else ""
    db.add(
        ActivityLog(
            id=f"act-{uuid.uuid4().hex[:8]}",
            project_id=task.project_id,
            user_name=actor,
            user_avatar=actor_avatar,
            action_type="update",
            message=f"Updated details for {task.title}",
            task_id=task.id,
        )
    )

    db.commit()

    changed_ids = [task_id] if date_or_duration_changed else None
    return build_board_state(db, project_id=task.project_id, changed_task_ids=changed_ids)


@router.patch("/{task_id}/move", response_model=BoardResponse)
def move_task(
    task_id: str,
    payload: TaskMove,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """
    Moves a task to a target column/position.
    Enforces rule: Blocked tasks CANNOT be moved to In Progress, Review, or Done.
    Triggers rollback re-evaluation of downstream tasks if moved backwards from Done.
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    target_column = payload.column
    project_id = task.project_id

    # Fetch current graph for this project to determine blocked status
    tasks_db = db.query(Task).filter(Task.project_id == project_id).all()
    all_deps = db.query(Dependency).all()
    task_ids = {t.id for t in tasks_db}
    deps_db = [d for d in all_deps if d.task_id in task_ids and d.prerequisite_id in task_ids]

    task_nodes = {
        t.id: TaskNode(
            id=t.id,
            title=t.title,
            column=t.column,
            duration_days=t.duration_days,
            planned_start=t.planned_start,
        )
        for t in tasks_db
    }
    edges = [DependencyEdge(task_id=d.task_id, prerequisite_id=d.prerequisite_id) for d in deps_db]
    prereqs, _ = DAGEngine.build_adjacency(task_nodes, edges)
    DAGEngine.compute_blocked_status(task_nodes, prereqs)

    current_node = task_nodes[task_id]

    # Validate move
    is_valid, error_msg = DAGEngine.validate_move(current_node, target_column)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Apply move
    was_done = (task.column == TaskColumn.DONE.value)
    task.column = target_column.value
    if payload.position is not None:
        task.position = payload.position

    # Log activity
    actor = current_user.name if current_user else "Team Member"
    actor_avatar = current_user.avatar if current_user else ""
    col_label = target_column.value.replace("_", " ").title()
    db.add(
        ActivityLog(
            id=f"act-{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            user_name=actor,
            user_avatar=actor_avatar,
            action_type="move",
            message=f"Moved '{task.title}' to {col_label}",
            task_id=task.id,
        )
    )

    db.commit()

    # If regression (Done -> Backlog/In Progress/Review), recompute downstream
    is_regression = was_done and (target_column != TaskColumn.DONE)
    changed_ids = [task_id] if is_regression else None

    return build_board_state(db, project_id=project_id, changed_task_ids=changed_ids)


@router.delete("/{task_id}", response_model=BoardResponse)
def delete_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Deletes task and cascaded dependencies, recomputing affected downstream graph."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    project_id = task.project_id
    task_title = task.title

    actor = current_user.name if current_user else "Team Member"
    actor_avatar = current_user.avatar if current_user else ""
    db.add(
        ActivityLog(
            id=f"act-{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            user_name=actor,
            user_avatar=actor_avatar,
            action_type="delete",
            message=f"Deleted task '{task_title}' ({task_id})",
            task_id=task_id,
        )
    )

    db.delete(task)
    db.commit()

    return build_board_state(db, project_id=project_id)


# --- Task Comments ---
@router.get("/{task_id}/comments", response_model=List[TaskCommentResponse])
def get_task_comments(task_id: str, db: Session = Depends(get_db)):
    """Returns comments for a given task."""
    comments = (
        db.query(TaskComment)
        .filter(TaskComment.task_id == task_id)
        .order_by(TaskComment.created_at.asc())
        .all()
    )
    return [TaskCommentResponse.model_validate(c) for c in comments]


@router.post("/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
def add_task_comment(
    task_id: str,
    payload: TaskCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_optional_user),
):
    """Adds a dynamic comment to a task."""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    user_name = current_user.name if current_user else (payload.user_name or "Anonymous")
    user_avatar = current_user.avatar if current_user else (payload.user_avatar or "")

    comment = TaskComment(
        id=f"comment-{uuid.uuid4().hex[:8]}",
        task_id=task_id,
        user_name=user_name,
        user_avatar=user_avatar,
        content=payload.content.strip(),
    )
    db.add(comment)

    # Activity log
    db.add(
        ActivityLog(
            id=f"act-{uuid.uuid4().hex[:8]}",
            project_id=task.project_id,
            user_name=user_name,
            user_avatar=user_avatar,
            action_type="comment",
            message=f"Commented on '{task.title}': {payload.content[:50]}...",
            task_id=task_id,
        )
    )
    db.commit()
    db.refresh(comment)

    return TaskCommentResponse.model_validate(comment)
