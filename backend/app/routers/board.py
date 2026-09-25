import json
from collections import defaultdict
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.engine.dag_engine import DAGEngine
from app.engine.types import DependencyEdge, SuggestionStatus, TaskNode
from app.models import ActivityLog, AISuggestion, Dependency, Project, Task
from app.schemas import (
    ActivityLogResponse,
    AISuggestionResponse,
    BoardResponse,
    BoardStats,
    DependencyResponse,
    ProjectResponse,
    TaskResponse,
)
from app.seed_data import seed_database

router = APIRouter(tags=["board"])


def build_board_state(
    db: Session,
    project_id: str = "proj-core",
    changed_task_ids: Optional[List[str]] = None,
) -> BoardResponse:
    """
    Core graph synchronization pipeline for a specific project workspace:
    1. Reads DB state for project
    2. Runs pure DAG engine schedule & blocked computation
    3. Persists computed schedule dates to DB
    4. Gathers projects and recent activities
    5. Serializes board response with derived fields
    """
    tasks_db = db.query(Task).filter(Task.project_id == project_id).all()
    task_id_set = {t.id for t in tasks_db}

    # Fetch dependencies relevant to this project
    all_deps = db.query(Dependency).all()
    deps_db = [d for d in all_deps if d.task_id in task_id_set and d.prerequisite_id in task_id_set]

    pending_suggestions_db = (
        db.query(AISuggestion)
        .filter(
            AISuggestion.status == SuggestionStatus.PENDING.value,
            AISuggestion.task_id.in_(task_id_set) if task_id_set else False,
        )
        .all()
        if task_id_set
        else []
    )

    # Convert to engine structures
    task_nodes = {
        t.id: TaskNode(
            id=t.id,
            title=t.title,
            column=t.column,
            position=t.position,
            duration_days=t.duration_days,
            planned_start=t.planned_start,
            start_date=t.start_date,
            end_date=t.end_date,
            description=t.description,
        )
        for t in tasks_db
    }

    edges = [
        DependencyEdge(task_id=d.task_id, prerequisite_id=d.prerequisite_id, source=d.source)
        for d in deps_db
    ]

    # Recompute schedule & blocked status
    schedule_res = DAGEngine.recompute_schedule(
        task_nodes,
        edges,
        changed_task_ids=changed_task_ids,
    )

    # Persist updated dates back to DB
    for t_db in tasks_db:
        if t_db.id in schedule_res.updated_tasks:
            node = schedule_res.updated_tasks[t_db.id]
            t_db.start_date = node.start_date
            t_db.end_date = node.end_date
    db.commit()

    # Build adjacency for client serialization
    prereq_map = defaultdict(list)
    depend_map = defaultdict(list)
    for edge in edges:
        prereq_map[edge.task_id].append(edge.prerequisite_id)
        depend_map[edge.prerequisite_id].append(edge.task_id)

    task_responses: List[TaskResponse] = []
    ready_count = 0
    blocked_count = 0
    done_count = 0
    in_progress_count = 0

    for t_db in tasks_db:
        node = schedule_res.updated_tasks.get(t_db.id)
        if not node:
            continue

        if node.is_blocked:
            blocked_count += 1
        else:
            ready_count += 1

        if node.column == "done":
            done_count += 1
        elif node.column == "in_progress":
            in_progress_count += 1

        # Parse tags
        tags_list = []
        try:
            if t_db.tags:
                tags_list = json.loads(t_db.tags) if isinstance(t_db.tags, str) else t_db.tags
        except Exception:
            tags_list = []

        # Parse subtasks
        subtasks_list = []
        try:
            if t_db.subtasks:
                subtasks_list = json.loads(t_db.subtasks) if isinstance(t_db.subtasks, str) else t_db.subtasks
        except Exception:
            subtasks_list = []

        comments_count = len(t_db.comments) if hasattr(t_db, "comments") and t_db.comments else 0

        task_responses.append(
            TaskResponse(
                id=node.id,
                project_id=t_db.project_id or project_id,
                title=node.title,
                description=node.description,
                column=node.column,
                position=node.position,
                duration_days=node.duration_days,
                planned_start=node.planned_start,
                start_date=node.start_date,
                end_date=node.end_date,
                priority=t_db.priority or "p2",
                assignee_id=t_db.assignee_id,
                assignee_name=t_db.assignee_name,
                assignee_avatar=t_db.assignee_avatar,
                tags=tags_list,
                progress=t_db.progress or 0,
                subtasks=subtasks_list,
                comments_count=comments_count,
                created_at=t_db.created_at,
                updated_at=t_db.updated_at,
                is_blocked=node.is_blocked,
                blocking_task_ids=node.blocking_task_ids,
                has_regression_warning=node.has_regression_warning,
                warning_message=node.warning_message,
                is_critical_path=node.is_critical_path,
                prerequisites=prereq_map[node.id],
                dependents=depend_map[node.id],
            )
        )

    # Compute total project duration
    if task_responses:
        min_start = min(t.start_date or t.planned_start for t in task_responses)
        max_end = max(t.end_date or t.planned_start for t in task_responses)
        total_duration = max(1, (max_end - min_start).days)
    else:
        total_duration = 0

    # Build AI suggestion responses with task titles
    task_title_map = {t.id: t.title for t in tasks_db}
    suggestion_responses = [
        AISuggestionResponse(
            id=s.id,
            task_id=s.task_id,
            prerequisite_id=s.prerequisite_id,
            rationale=s.rationale,
            confidence=s.confidence,
            status=s.status,
            created_at=s.created_at,
            task_title=task_title_map.get(s.task_id, s.task_id),
            prerequisite_title=task_title_map.get(s.prerequisite_id, s.prerequisite_id),
        )
        for s in pending_suggestions_db
    ]

    # Fetch projects list
    all_projects = db.query(Project).all()
    project_responses = []
    for p in all_projects:
        cnt = db.query(Task).filter(Task.project_id == p.id).count()
        project_responses.append(
            ProjectResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                icon=p.icon,
                owner_id=p.owner_id,
                created_at=p.created_at,
                task_count=cnt,
            )
        )

    # Fetch recent activities for project
    activities_db = (
        db.query(ActivityLog)
        .filter(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(25)
        .all()
    )
    activity_responses = [ActivityLogResponse.model_validate(a) for a in activities_db]

    return BoardResponse(
        tasks=task_responses,
        dependencies=[DependencyResponse.model_validate(d) for d in deps_db],
        critical_path=schedule_res.critical_path,
        pending_suggestions=suggestion_responses,
        stats=BoardStats(
            total_tasks=len(task_responses),
            ready_tasks=ready_count,
            blocked_tasks=blocked_count,
            done_tasks=done_count,
            in_progress_tasks=in_progress_count,
            total_duration_days=total_duration,
            critical_path_length=len(schedule_res.critical_path),
        ),
        current_project_id=project_id,
        projects=project_responses,
        activities=activity_responses,
    )


@router.get("/board", response_model=BoardResponse)
def get_board(
    project_id: str = Query(default="proj-core"),
    db: Session = Depends(get_db),
):
    """Fetches board state with calculated schedule, blocked states, and critical path."""
    if db.query(Task).count() == 0:
        seed_database(db)

    # Ensure project exists
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        project_id = "proj-core"

    return build_board_state(db, project_id=project_id)


@router.post("/board/reset-seed", response_model=BoardResponse)
def reset_seed(
    project_id: str = Query(default="proj-core"),
    db: Session = Depends(get_db),
):
    """Resets board to the benchmark canonical tasks and seed dependencies."""
    seed_database(db)
    return build_board_state(db, project_id=project_id)
