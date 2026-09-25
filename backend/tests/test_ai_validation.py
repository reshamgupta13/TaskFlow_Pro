import pytest
from app.ai.service import AIService
from app.database import Base, SessionLocal, engine
from app.models import AISuggestion, Dependency, Task
from app.seed_data import seed_database


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()
    yield


@pytest.mark.anyio
async def test_untrusted_ai_cycle_rejection():
    """
    Simulate LLM proposing a cycle.
    E.g., task-arch depends on task-deploy (which already depends on task-api -> task-arch).
    AIService MUST filter this out during programmatic validation.
    """
    db = SessionLocal()
    try:
        # Mock LLM provider output with a deliberate cycle and an unknown ID
        from unittest.mock import patch

        mock_llm_output = """
        [
          {"task_id": "task-arch", "prerequisite_id": "task-deploy", "rationale": "Cycles are bad", "confidence": 0.99},
          {"task_id": "task-invented", "prerequisite_id": "task-arch", "rationale": "Hallucinated task", "confidence": 0.8},
          {"task_id": "task-docs", "prerequisite_id": "task-docs", "rationale": "Self loop", "confidence": 0.8}
        ]
        """

        with patch("app.ai.providers.LLMProvider.call_llm", return_value=mock_llm_output):
            suggestions = await AIService.generate_suggestions(db)

            # NONE of the invalid suggestions should survive!
            surviving_task_ids = [s.task_id for s in suggestions]
            assert "task-invented" not in surviving_task_ids
            assert "task-docs" not in surviving_task_ids  # self loop dropped
            assert not any(s.task_id == "task-arch" and s.prerequisite_id == "task-deploy" for s in suggestions)
    finally:
        db.close()
