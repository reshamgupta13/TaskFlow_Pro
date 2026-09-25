from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.engine.dag_engine import DAGEngine
from app.engine.types import DependencyEdge, TaskNode
from app.models import Dependency, Task
from app.routers.board import build_board_state
from app.schemas import BoardResponse, DependencyCreate

router = APIRouter(prefix="/dependencies", tags=["dependencies"])


@router.post("", response_model=BoardResponse, status_code=status.HTTP_201_CREATED)
def add_dependency(payload: DependencyCreate, db: Session = Depends(get_db)):
    """
    Adds a dependency edge (task_id depends on prerequisite_id).
    Atomic check-and-write inside one DB transaction:
    Checks for cycles, self-loops, and duplicates before persisting.
    If cycle is detected, returns 400 with the exact offending loop path.
    """
    task = db.query(Task).filter(Task.id == payload.task_id).first()
    prereq = db.query(Task).filter(Task.id == payload.prerequisite_id).first()

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{payload.task_id}' not found.",
        )
    if not prereq:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Prerequisite '{payload.prerequisite_id}' not found.",
        )

    # Load in-memory graph
    tasks_db = db.query(Task).all()
    deps_db = db.query(Dependency).all()

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

    # Cycle and validity check
    check_result = DAGEngine.check_cycle_before_add(
        task_nodes,
        edges,
        new_task_id=payload.task_id,
        new_prerequisite_id=payload.prerequisite_id,
    )

    if not check_result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Cycle or invalid dependency",
                "message": check_result.message,
                "offending_loop": check_result.offending_loop,
            },
        )

    # Persist in same transaction
    dep = Dependency(
        task_id=payload.task_id,
        prerequisite_id=payload.prerequisite_id,
        source=payload.source.value,
    )
    db.add(dep)
    db.commit()

    return build_board_state(db, changed_task_ids=[payload.task_id])


@router.delete("/{task_id}/{prerequisite_id}", response_model=BoardResponse)
def remove_dependency(task_id: str, prerequisite_id: str, db: Session = Depends(get_db)):
    """Deletes a dependency edge and re-evaluates downstream schedule and blocked status."""
    dep = (
        db.query(Dependency)
        .filter(Dependency.task_id == task_id, Dependency.prerequisite_id == prerequisite_id)
        .first()
    )
    if not dep:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dependency not found.")

    db.delete(dep)
    db.commit()

    return build_board_state(db, changed_task_ids=[task_id])
