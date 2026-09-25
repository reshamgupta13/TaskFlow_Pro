from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class TaskColumn(str, Enum):
    BACKLOG = "backlog"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class DependencySource(str, Enum):
    MANUAL = "manual"
    AI = "ai"


class SuggestionStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class TaskNode:
    id: str
    title: str
    column: TaskColumn
    duration_days: int
    planned_start: date
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    description: str = ""
    position: float = 0.0

    # Derived engine fields
    is_blocked: bool = False
    blocking_task_ids: List[str] = field(default_factory=list)
    has_regression_warning: bool = False
    warning_message: Optional[str] = None
    is_critical_path: bool = False


@dataclass
class DependencyEdge:
    task_id: str          # Dependent task (must wait)
    prerequisite_id: str  # Prerequisite task (must be done first)
    source: DependencySource = DependencySource.MANUAL


@dataclass
class CycleCheckResult:
    is_valid: bool
    offending_loop: Optional[List[str]] = None
    message: Optional[str] = None


@dataclass
class GraphScheduleResult:
    updated_tasks: Dict[str, TaskNode]
    critical_path: List[str]
    affected_task_ids: List[str]
