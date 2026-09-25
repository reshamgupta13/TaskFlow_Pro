import pytest
from fastapi.testclient import TestClient

from app.database import Base, engine, SessionLocal
from app.main import app
from app.seed_data import seed_database
from app.models import Task, Dependency


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_get_board_initial_state(client):
    response = client.get("/api/board")
    assert response.status_code == 200
    data = response.json()

    assert len(data["tasks"]) == 10
    assert len(data["dependencies"]) > 0
    assert len(data["critical_path"]) > 0
    assert data["stats"]["total_tasks"] == 10

    # task-docs has no prerequisites, should be Ready
    docs_task = next(t for t in data["tasks"] if t["id"] == "task-docs")
    assert not docs_task["is_blocked"]

    # task-integ depends on task-api (which is in progress), should be Blocked
    integ_task = next(t for t in data["tasks"] if t["id"] == "task-integ")
    assert integ_task["is_blocked"]
    assert "task-api" in integ_task["blocking_task_ids"]


def test_blocked_task_cannot_move_forward(client):
    # task-integ is blocked, attempt to move to 'in_progress'
    response = client.patch(
        "/api/tasks/task-integ/move",
        json={"column": "in_progress"},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Cannot move Blocked task" in detail


def test_cycle_detection_on_add_dependency(client):
    # Existing: task-auth depends on task-arch.
    # Attempting to make task-arch depend on task-auth would create cycle: task-arch -> task-auth -> task-arch
    response = client.post(
        "/api/dependencies",
        json={
            "task_id": "task-arch",
            "prerequisite_id": "task-auth",
        },
    )
    assert response.status_code == 400
    data = response.json()
    detail = data["detail"]
    assert "offending_loop" in detail
    assert detail["offending_loop"] == ["task-arch", "task-auth", "task-arch"]


def test_self_dependency_rejected(client):
    response = client.post(
        "/api/dependencies",
        json={
            "task_id": "task-docs",
            "prerequisite_id": "task-docs",
        },
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["offending_loop"] == ["task-docs", "task-docs"]


def test_rollback_triggers_downstream_warning(client):
    """
    task-api is in_progress and depends on task-arch (Done) and task-db (Done).
    If we move task-db back to backlog, task-api should stay in_progress but have has_regression_warning == True.
    """
    # Move task-db from Done to Backlog
    response = client.patch(
        "/api/tasks/task-db/move",
        json={"column": "backlog"},
    )
    assert response.status_code == 200
    board = response.json()

    api_task = next(t for t in board["tasks"] if t["id"] == "task-api")
    assert api_task["column"] == "in_progress"
    assert api_task["is_blocked"] is True
    assert api_task["has_regression_warning"] is True
    assert "task-db" in api_task["blocking_task_ids"]


def test_ai_suggestion_and_metrics_pipeline(client):
    # 1. Trigger AI suggestions
    res = client.post("/api/ai/suggestions")
    assert res.status_code == 200
    suggestions = res.json()
    assert isinstance(suggestions, list)

    # 2. Check metrics endpoint
    res_m = client.get("/api/ai/metrics")
    assert res_m.status_code == 200
    metrics = res_m.json()
    assert "acceptance_rate" in metrics

    if suggestions:
        s_id = suggestions[0]["id"]
        # Accept suggestion
        res_accept = client.post(f"/api/ai/suggestions/{s_id}/accept")
        assert res_accept.status_code == 200
