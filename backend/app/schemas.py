from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.engine.types import DependencySource, SuggestionStatus, TaskColumn


# --- Authentication Schemas ---
class UserRegister(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    role: Optional[str] = "Developer"
    avatar: Optional[str] = ""


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    avatar: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- Project Schemas ---
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = ""
    icon: Optional[str] = "git-branch"


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    owner_id: Optional[str] = None
    created_at: datetime
    task_count: int = 0

    model_config = ConfigDict(from_attributes=True)


# --- Task & Dependency Schemas ---
class SubtaskItem(BaseModel):
    id: str
    title: str
    done: bool = False


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    duration_days: int = Field(default=1, ge=1, le=365)
    planned_start: date


class TaskCreate(TaskBase):
    id: Optional[str] = None
    project_id: Optional[str] = "proj-core"
    column: TaskColumn = TaskColumn.BACKLOG
    position: Optional[float] = None
    priority: Optional[str] = "p2"  # p0, p1, p2, p3
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    assignee_avatar: Optional[str] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    progress: Optional[int] = Field(default=0, ge=0, le=100)
    subtasks: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    prerequisite_ids: Optional[List[str]] = Field(default_factory=list)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    planned_start: Optional[date] = None
    priority: Optional[str] = None
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    assignee_avatar: Optional[str] = None
    tags: Optional[List[str]] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    subtasks: Optional[List[Dict[str, Any]]] = None


class TaskMove(BaseModel):
    column: TaskColumn
    position: Optional[float] = None


class DependencyCreate(BaseModel):
    task_id: str
    prerequisite_id: str
    source: DependencySource = DependencySource.MANUAL


class DependencyResponse(BaseModel):
    task_id: str
    prerequisite_id: str
    source: DependencySource
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AISuggestionResponse(BaseModel):
    id: str
    task_id: str
    prerequisite_id: str
    rationale: str
    confidence: float
    status: SuggestionStatus
    created_at: datetime

    task_title: Optional[str] = None
    prerequisite_title: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class AIMetricsResponse(BaseModel):
    total_suggestions: int
    accepted: int
    rejected: int
    pending: int
    acceptance_rate: float


class TaskCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    user_name: Optional[str] = "Anonymous"
    user_avatar: Optional[str] = ""


class TaskCommentResponse(BaseModel):
    id: str
    task_id: str
    user_name: str
    user_avatar: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityLogResponse(BaseModel):
    id: str
    project_id: str
    user_name: str
    user_avatar: str
    action_type: str
    message: str
    task_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskResponse(BaseModel):
    id: str
    project_id: str = "proj-core"
    title: str
    description: str
    column: TaskColumn
    position: float
    duration_days: int
    planned_start: date
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    priority: str = "p2"
    assignee_id: Optional[str] = None
    assignee_name: Optional[str] = None
    assignee_avatar: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    progress: int = 0
    subtasks: List[Dict[str, Any]] = Field(default_factory=list)
    comments_count: int = 0
    created_at: datetime
    updated_at: datetime

    # Pure DAG engine derived values
    is_blocked: bool = False
    blocking_task_ids: List[str] = Field(default_factory=list)
    has_regression_warning: bool = False
    warning_message: Optional[str] = None
    is_critical_path: bool = False

    # Graph edge IDs for fast client rendering
    prerequisites: List[str] = Field(default_factory=list)
    dependents: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class BoardStats(BaseModel):
    total_tasks: int
    ready_tasks: int
    blocked_tasks: int
    done_tasks: int
    in_progress_tasks: int
    total_duration_days: int
    critical_path_length: int


class BoardResponse(BaseModel):
    tasks: List[TaskResponse]
    dependencies: List[DependencyResponse]
    critical_path: List[str]
    pending_suggestions: List[AISuggestionResponse]
    stats: BoardStats
    current_project_id: str = "proj-core"
    projects: List[ProjectResponse] = Field(default_factory=list)
    activities: List[ActivityLogResponse] = Field(default_factory=list)
