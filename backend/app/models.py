from datetime import datetime, timezone
from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False, default="Developer")
    avatar = Column(String(255), nullable=False, default="")
    created_at = Column(DateTime, default=utcnow, nullable=False)

    tasks_assigned = relationship("Task", back_populates="assignee", foreign_keys="[Task.assignee_id]")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    icon = Column(String(64), nullable=False, default="git-branch")
    owner_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), ForeignKey("projects.id", ondelete="CASCADE"), default="proj-core", nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="", nullable=False)
    column = Column(String(32), nullable=False, default="backlog")  # backlog, in_progress, review, done
    position = Column(Float, nullable=False, default=0.0)
    duration_days = Column(Integer, nullable=False, default=1)
    planned_start = Column(Date, nullable=False)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)

    # Dynamic fields
    priority = Column(String(16), nullable=False, default="p2")  # p0, p1, p2, p3
    assignee_id = Column(String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assignee_name = Column(String(255), nullable=True)
    assignee_avatar = Column(String(255), nullable=True)
    tags = Column(Text, nullable=False, default="[]")  # JSON string e.g. ["Backend", "Engine"]
    progress = Column(Integer, nullable=False, default=0)  # 0 to 100
    subtasks = Column(Text, nullable=False, default="[]")  # JSON string of subtask items

    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="tasks", foreign_keys=[project_id])
    assignee = relationship("User", back_populates="tasks_assigned", foreign_keys=[assignee_id])
    comments = relationship("TaskComment", back_populates="task", cascade="all, delete-orphan", order_by="TaskComment.created_at.desc()")

    # Dependencies where this task is dependent (prerequisites needed)
    prerequisite_edges = relationship(
        "Dependency",
        foreign_keys="[Dependency.task_id]",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    # Dependencies where this task is a prerequisite to others
    dependent_edges = relationship(
        "Dependency",
        foreign_keys="[Dependency.prerequisite_id]",
        back_populates="prerequisite",
        cascade="all, delete-orphan",
    )


class Dependency(Base):
    __tablename__ = "dependencies"

    task_id = Column(
        String(64),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    prerequisite_id = Column(
        String(64),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    source = Column(String(16), nullable=False, default="manual")  # manual | ai
    created_at = Column(DateTime, default=utcnow, nullable=False)

    task = relationship("Task", foreign_keys=[task_id], back_populates="prerequisite_edges")
    prerequisite = relationship("Task", foreign_keys=[prerequisite_id], back_populates="dependent_edges")

    __table_args__ = (
        UniqueConstraint("task_id", "prerequisite_id", name="uq_task_prerequisite"),
        CheckConstraint("task_id != prerequisite_id", name="check_no_self_dependency"),
        Index("idx_dep_task_id", "task_id"),
        Index("idx_dep_prereq_id", "prerequisite_id"),
    )


class AISuggestion(Base):
    __tablename__ = "ai_suggestions"

    id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    prerequisite_id = Column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    rationale = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.8)
    status = Column(String(32), nullable=False, default="pending")  # pending, accepted, rejected
    created_at = Column(DateTime, default=utcnow, nullable=False)

    task = relationship("Task", foreign_keys=[task_id])
    prerequisite = relationship("Task", foreign_keys=[prerequisite_id])


class TaskComment(Base):
    __tablename__ = "task_comments"

    id = Column(String(64), primary_key=True, index=True)
    task_id = Column(String(64), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_name = Column(String(255), nullable=False)
    user_avatar = Column(String(255), nullable=False, default="")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utcnow, nullable=False)

    task = relationship("Task", back_populates="comments")


class ActivityLog(Base):
    __tablename__ = "activity_logs"

    id = Column(String(64), primary_key=True, index=True)
    project_id = Column(String(64), default="proj-core", nullable=False, index=True)
    user_name = Column(String(255), nullable=False)
    user_avatar = Column(String(255), nullable=False, default="")
    action_type = Column(String(64), nullable=False)  # move, create, update, delete, dependency_add, dependency_remove, ai_accept
    message = Column(Text, nullable=False)
    task_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
