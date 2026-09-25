from __future__ import annotations
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.ai.providers import LLMProvider
from app.engine.dag_engine import DAGEngine
from app.engine.types import DependencyEdge, DependencySource, SuggestionStatus, TaskNode
from app.models import AISuggestion, Dependency, Task

logger = logging.getLogger(__name__)


class AIService:
    @classmethod
    async def generate_suggestions(cls, db: Session) -> List[AISuggestion]:
        """
        Executes the AI suggestion pipeline:
        1. Closed-set grounding: reads real tasks.
        2. Queries LLM or local provider.
        3. Untrusted AI validation:
           - Drop unknown IDs
           - Drop self-dependencies
           - Drop already existing dependencies
           - Drop already pending suggestions
           - Dry-run through pure DAG engine to reject any cycle
        4. Persists valid suggestions in 'pending' status.
        """
        tasks_db = db.query(Task).all()
        deps_db = db.query(Dependency).all()
        pending_db = db.query(AISuggestion).filter(AISuggestion.status == SuggestionStatus.PENDING.value).all()

        task_dict: Dict[str, TaskNode] = {
            t.id: TaskNode(
                id=t.id,
                title=t.title,
                column=t.column,
                duration_days=t.duration_days,
                planned_start=t.planned_start,
                description=t.description,
            )
            for t in tasks_db
        }
        existing_edges = [
            DependencyEdge(task_id=d.task_id, prerequisite_id=d.prerequisite_id)
            for d in deps_db
        ]
        pending_set = {(p.task_id, p.prerequisite_id) for p in pending_db}

        # Format prompt
        task_list_text = "\n".join([
            f"- ID: {t.id}, Title: {t.title}, Description: {t.description}"
            for t in tasks_db
        ])
        existing_edges_text = "\n".join([
            f"- {d.task_id} depends on {d.prerequisite_id}"
            for d in deps_db
        ]) or "None"

        user_prompt = f"""Active Tasks (CLOSED SET):
{task_list_text}

Existing Dependencies (DO NOT RE-SUGGEST):
{existing_edges_text}

Analyze the tasks and propose missing dependencies. Remember: output strict JSON array."""

        raw_json_str = await LLMProvider.call_llm(user_prompt)

        raw_suggestions: List[Dict[str, Any]] = []
        if raw_json_str:
            try:
                parsed = json.loads(raw_json_str)
                if isinstance(parsed, list):
                    raw_suggestions = parsed
                elif isinstance(parsed, dict) and "suggestions" in parsed:
                    raw_suggestions = parsed["suggestions"]
            except Exception as e:
                logger.warning(f"Failed to parse LLM JSON: {e}")

        # If LLM didn't return suggestions or failed, use local heuristic fallback
        if not raw_suggestions:
            task_summaries = [{"id": t.id, "title": t.title, "description": t.description} for t in tasks_db]
            raw_suggestions = LLMProvider.local_heuristic_suggestions(
                task_summaries,
                [(d.task_id, d.prerequisite_id) for d in deps_db],
            )

        # Programmatic Validation Layer
        surviving_suggestions: List[AISuggestion] = []
        # Keep track of dry-run graph so multiple suggestions don't form a cycle together
        simulated_edges = list(existing_edges)

        for item in raw_suggestions:
            task_id = item.get("task_id")
            prereq_id = item.get("prerequisite_id")
            rationale = item.get("rationale", "Suggested based on task lifecycle ordering.")
            confidence = float(item.get("confidence", 0.8))

            # 1. Closed-set validation: Must exist in task_dict
            if not task_id or not prereq_id:
                continue
            if task_id not in task_dict or prereq_id not in task_dict:
                logger.info(f"AI suggested unknown task ID ({task_id} or {prereq_id}), dropping.")
                continue

            # 2. Drop self loops
            if task_id == prereq_id:
                logger.info(f"AI suggested self-loop on {task_id}, dropping.")
                continue

            # 3. Drop existing dependencies
            if any(e.task_id == task_id and e.prerequisite_id == prereq_id for e in existing_edges):
                continue

            # 4. Drop already pending suggestions
            if (task_id, prereq_id) in pending_set:
                continue

            # 5. DRY-RUN CYCLE CHECK THROUGH DAG ENGINE
            cycle_check = DAGEngine.check_cycle_before_add(
                task_dict,
                simulated_edges,
                new_task_id=task_id,
                new_prerequisite_id=prereq_id,
            )
            if not cycle_check.is_valid:
                logger.info(f"AI suggestion {prereq_id} -> {task_id} would create cycle {cycle_check.offending_loop}, dropping.")
                continue

            # Edge passed all tests! Add to simulated edges for subsequent checks
            simulated_edges.append(DependencyEdge(task_id=task_id, prerequisite_id=prereq_id))

            # Create DB entity
            suggestion = AISuggestion(
                id=f"sugg-{uuid.uuid4().hex[:8]}",
                task_id=task_id,
                prerequisite_id=prereq_id,
                rationale=rationale,
                confidence=confidence,
                status=SuggestionStatus.PENDING.value,
            )
            db.add(suggestion)
            surviving_suggestions.append(suggestion)

        db.commit()
        return surviving_suggestions

    @classmethod
    def accept_suggestion(cls, db: Session, suggestion_id: str) -> Tuple[bool, Optional[str], Optional[Dependency]]:
        """
        Accepts an AI suggestion with full cycle check and transactional integrity.
        """
        suggestion = db.query(AISuggestion).filter(AISuggestion.id == suggestion_id).first()
        if not suggestion:
            return False, "Suggestion not found", None

        if suggestion.status != SuggestionStatus.PENDING.value:
            return False, f"Suggestion is already {suggestion.status}", None

        # Build current graph
        tasks_db = db.query(Task).all()
        deps_db = db.query(Dependency).all()
        task_dict = {
            t.id: TaskNode(
                id=t.id,
                title=t.title,
                column=t.column,
                duration_days=t.duration_days,
                planned_start=t.planned_start,
            )
            for t in tasks_db
        }
        existing_edges = [
            DependencyEdge(task_id=d.task_id, prerequisite_id=d.prerequisite_id)
            for d in deps_db
        ]

        # Verify cycle check one more time before committing
        check = DAGEngine.check_cycle_before_add(
            task_dict,
            existing_edges,
            new_task_id=suggestion.task_id,
            new_prerequisite_id=suggestion.prerequisite_id,
        )
        if not check.is_valid:
            # Mark rejected because graph changed and now forms a cycle
            suggestion.status = SuggestionStatus.REJECTED.value
            db.commit()
            return False, f"Cannot accept: graph changed and adding this edge creates cycle ({check.offending_loop})", None

        # Insert dependency
        dep = Dependency(
            task_id=suggestion.task_id,
            prerequisite_id=suggestion.prerequisite_id,
            source=DependencySource.AI.value,
        )
        db.add(dep)
        suggestion.status = SuggestionStatus.ACCEPTED.value
        db.commit()

        return True, None, dep

    @classmethod
    def reject_suggestion(cls, db: Session, suggestion_id: str) -> Tuple[bool, Optional[str]]:
        """
        Rejects an AI suggestion and logs the decision.
        """
        suggestion = db.query(AISuggestion).filter(AISuggestion.id == suggestion_id).first()
        if not suggestion:
            return False, "Suggestion not found"

        suggestion.status = SuggestionStatus.REJECTED.value
        db.commit()
        return True, None

    @classmethod
    def get_metrics(cls, db: Session) -> Dict[str, Any]:
        """
        Calculates accept rate and suggestion counts for monitoring.
        """
        total = db.query(AISuggestion).count()
        accepted = db.query(AISuggestion).filter(AISuggestion.status == SuggestionStatus.ACCEPTED.value).count()
        rejected = db.query(AISuggestion).filter(AISuggestion.status == SuggestionStatus.REJECTED.value).count()
        pending = db.query(AISuggestion).filter(AISuggestion.status == SuggestionStatus.PENDING.value).count()

        decided = accepted + rejected
        rate = (accepted / decided * 100.0) if decided > 0 else 0.0

        return {
            "total_suggestions": total,
            "accepted": accepted,
            "rejected": rejected,
            "pending": pending,
            "acceptance_rate": round(rate, 1),
        }
