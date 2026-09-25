from datetime import date
from typing import List, Tuple
from sqlalchemy.orm import Session

from app.models import Dependency, Task
from app.engine.types import DependencySource, TaskColumn


SEEDED_TASKS = [
    {
        "id": "task-arch",
        "title": "System Architecture & Data Modeling",
        "description": "Define high-level DAG architecture, schema constraints, and API contracts.",
        "column": TaskColumn.DONE.value,
        "position": 1.0,
        "duration_days": 3,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-auth",
        "title": "Authentication & Session Security",
        "description": "Implement token validation, CORS restrictions, and route guards.",
        "column": TaskColumn.DONE.value,
        "position": 2.0,
        "duration_days": 2,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-db",
        "title": "Core Database Schema & Migrations",
        "description": "Create SQLite/Postgres tables with foreign keys and cascade delete rules.",
        "column": TaskColumn.DONE.value,
        "position": 3.0,
        "duration_days": 2,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-api",
        "title": "Backend REST API & DAG Engine",
        "description": "Implement pure DAG engine, topological sort, cycle prevention, and endpoints.",
        "column": TaskColumn.IN_PROGRESS.value,
        "position": 1.0,
        "duration_days": 4,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-ui",
        "title": "Frontend Shell & Design System",
        "description": "Build modern responsive Kanban UI with dark mode, glowing accents, and badges.",
        "column": TaskColumn.IN_PROGRESS.value,
        "position": 2.0,
        "duration_days": 3,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-docs",
        "title": "Developer Documentation & API Spec",
        "description": "Write architecture documentation, Mermaid graphs, and setup guide. Independent task.",
        "column": TaskColumn.BACKLOG.value,
        "position": 1.0,
        "duration_days": 2,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-integ",
        "title": "Integration Testing & Contract Validation",
        "description": "Validate end-to-end task moves, schedule propagation, and API payloads.",
        "column": TaskColumn.BACKLOG.value,
        "position": 2.0,
        "duration_days": 3,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-ai",
        "title": "AI Dependency Suggestion Engine",
        "description": "Provider-agnostic LLM pipeline with closed-set grounding and engine validation.",
        "column": TaskColumn.BACKLOG.value,
        "position": 3.0,
        "duration_days": 3,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-perf",
        "title": "Stress & 500-Task Benchmark Testing",
        "description": "Run O(V+E) benchmarks ensuring <10ms cycle check and <50ms schedule recalc.",
        "column": TaskColumn.BACKLOG.value,
        "position": 4.0,
        "duration_days": 2,
        "planned_start": date(2026, 3, 1),
    },
    {
        "id": "task-deploy",
        "title": "Production Deployment & Monitoring",
        "description": "Configure Docker containerization, health checks, and production readiness.",
        "column": TaskColumn.BACKLOG.value,
        "position": 5.0,
        "duration_days": 2,
        "planned_start": date(2026, 3, 1),
    },
]

# (task_id, prerequisite_id) -> task_id depends on prerequisite_id
SEEDED_DEPENDENCIES: List[Tuple[str, str]] = [
    # task-auth depends on task-arch
    ("task-auth", "task-arch"),
    # task-db depends on task-arch
    ("task-db", "task-arch"),
    # Diamond convergence: task-api depends on BOTH task-auth and task-db
    ("task-api", "task-auth"),
    ("task-api", "task-db"),
    # task-ui depends on task-arch
    ("task-ui", "task-arch"),
    # task-integ depends on task-api and task-ui
    ("task-integ", "task-api"),
    ("task-integ", "task-ui"),
    # task-ai depends on task-api
    ("task-ai", "task-api"),
    # task-perf depends on task-integ
    ("task-perf", "task-integ"),
    # task-deploy depends on task-perf and task-ai
    ("task-deploy", "task-perf"),
    ("task-deploy", "task-ai"),
]


def seed_database(db: Session) -> None:
    """Populates or resets the database to the 10 canonical seeded tasks."""
    # Clear existing dependencies and tasks
    db.query(Dependency).delete()
    db.query(Task).delete()
    db.commit()

    # Insert tasks
    for item in SEEDED_TASKS:
        t = Task(
            id=item["id"],
            title=item["title"],
            description=item["description"],
            column=item["column"],
            position=item["position"],
            duration_days=item["duration_days"],
            planned_start=item["planned_start"],
        )
        db.add(t)
    db.commit()

    # Insert dependencies
    for task_id, prereq_id in SEEDED_DEPENDENCIES:
        dep = Dependency(
            task_id=task_id,
            prerequisite_id=prereq_id,
            source=DependencySource.MANUAL.value,
        )
        db.add(dep)
    db.commit()
