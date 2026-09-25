from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.service import AIService
from app.database import get_db
from app.routers.board import build_board_state
from app.schemas import AIMetricsResponse, AISuggestionResponse, BoardResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/suggestions", response_model=List[AISuggestionResponse])
async def generate_ai_suggestions(db: Session = Depends(get_db)):
    """Triggers the untrusted AI pipeline with closed-set grounding and DAG engine validation."""
    suggestions = await AIService.generate_suggestions(db)
    task_title_map = {t.id: t.title for t in db.query(from_obj=None).all()} if False else {}
    from app.models import Task
    task_title_map = {t.id: t.title for t in db.query(Task).all()}

    return [
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
        for s in suggestions
    ]


@router.post("/suggestions/{suggestion_id}/accept", response_model=BoardResponse)
def accept_suggestion(suggestion_id: str, db: Session = Depends(get_db)):
    """Accepts an AI suggestion. Passes through DAG engine cycle check before persisting."""
    success, error_msg, dep = AIService.accept_suggestion(db, suggestion_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    return build_board_state(db, changed_task_ids=[dep.task_id])


@router.post("/suggestions/{suggestion_id}/reject", response_model=AIMetricsResponse)
def reject_suggestion(suggestion_id: str, db: Session = Depends(get_db)):
    """Rejects an AI suggestion and logs the decision for acceptance rate calculation."""
    success, error_msg = AIService.reject_suggestion(db, suggestion_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    return AIService.get_metrics(db)


@router.get("/metrics", response_model=AIMetricsResponse)
def get_ai_metrics(db: Session = Depends(get_db)):
    """Returns AI dependency suggestion acceptance rate and metrics."""
    return AIService.get_metrics(db)
