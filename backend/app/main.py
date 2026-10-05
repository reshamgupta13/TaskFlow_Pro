from pathlib import Path
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import Task
from app.routers import ai, board, dependencies, tasks
from app.seed_data import seed_database


@asynccontextmanager
async def lifespan(app: FastAPI):
    source_db = Path(__file__).resolve().parent.parent / "taskflow.db"
    target_db = Path("/tmp/taskflow.db")

    if source_db.exists() and not target_db.exists():
        shutil.copy2(source_db, target_db)

    Base.metadata.create_all(bind=engine)

    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="TaskFlow Pro: Kanban Board with Pure DAG Dependency Engine",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers with /api prefix
app.include_router(board.router, prefix=settings.API_V1_STR)
app.include_router(tasks.router, prefix=settings.API_V1_STR)
app.include_router(dependencies.router, prefix=settings.API_V1_STR)
app.include_router(ai.router, prefix=settings.API_V1_STR)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": settings.PROJECT_NAME}
