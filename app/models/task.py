from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class ScheduledTask(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "scheduled_tasks"

    name = Column(String(200), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text)
    task_type = Column(String(50), index=True, nullable=False)

    cron_expression = Column(String(100))
    interval_seconds = Column(Integer)
    run_date = Column(DateTime)

    task_params = Column(JSON)
    target_function = Column(String(200), nullable=False)

    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    is_running = Column(Boolean, default=False, nullable=False)

    last_run_at = Column(DateTime)
    last_run_status = Column(String(20))
    last_run_error = Column(Text)
    next_run_at = Column(DateTime)

    success_count = Column(Integer, default=0)
    failure_count = Column(Integer, default=0)
    total_runs = Column(Integer, default=0)

    created_by = Column(Integer)
    max_retries = Column(Integer, default=3)
    timeout_seconds = Column(Integer, default=3600)

    executions = relationship("TaskExecution", back_populates="task", cascade="all, delete-orphan")


class TaskExecution(BaseModel, TimestampMixin):
    __tablename__ = "task_executions"

    task_id = Column(Integer, ForeignKey("scheduled_tasks.id"), nullable=False, index=True)

    execution_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(20), default="pending", index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    duration_seconds = Column(Integer)

    result_data = Column(JSON)
    error_message = Column(Text)
    error_traceback = Column(Text)

    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    is_success = Column(Boolean, default=False, index=True)

    triggered_by = Column(String(50), default="scheduler")
    triggered_at = Column(DateTime, default=datetime.utcnow)

    task = relationship("ScheduledTask", back_populates="executions")
