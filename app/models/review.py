from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, DateTime, Date
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class ReviewTask(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "review_tasks"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    examination_id = Column(Integer, ForeignKey("examinations.id"), nullable=True, index=True)
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    task_code = Column(String(100), unique=True, nullable=False, index=True)
    task_type = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), default="medium", index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text)
    requirement = Column(Text)

    anomaly_ids = Column(JSON)
    check_items = Column(JSON)

    due_date = Column(Date, index=True)
    reminder_date = Column(Date)

    status = Column(String(20), default="pending", index=True)
    workflow_state = Column(String(50), default="assigned", index=True)

    assigned_at = Column(DateTime, default=datetime.utcnow)
    accepted_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    overdue_at = Column(DateTime)

    is_overdue = Column(Boolean, default=False, index=True)
    is_urgent = Column(Boolean, default=False)

    completion_notes = Column(Text)
    rejection_reason = Column(Text)
    escalation_reason = Column(Text)

    review_count = Column(Integer, default=0)
    max_reviews = Column(Integer, default=1)

    hospital = relationship("Hospital", back_populates="review_tasks")
    examination = relationship("Examination", back_populates="review_tasks")
    creator = relationship("User", back_populates="created_review_tasks", foreign_keys=[creator_id])
    assignee = relationship("User", back_populates="assigned_review_tasks", foreign_keys=[assignee_id])
    anomalies = relationship("AnomalyRecord", back_populates="review_task")
    review_records = relationship("ReviewRecord", back_populates="review_task", cascade="all, delete-orphan")
    rectification = relationship("Rectification", back_populates="review_task", uselist=False, cascade="all, delete-orphan")

    def set_default_due_date(self, days: int = 7):
        self.due_date = (datetime.utcnow() + timedelta(days=days)).date()

    @property
    def is_expired(self) -> bool:
        if not self.due_date:
            return False
        return datetime.utcnow().date() > self.due_date and self.status != "completed"


class ReviewRecord(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "review_records"

    review_task_id = Column(Integer, ForeignKey("review_tasks.id"), nullable=False, index=True)
    anomaly_id = Column(Integer, ForeignKey("anomaly_records.id"), nullable=True, index=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    review_round = Column(Integer, default=1)
    review_action = Column(String(50), nullable=False)
    review_result = Column(String(20), nullable=False, index=True)

    reviewed_at = Column(DateTime, default=datetime.utcnow)
    review_duration = Column(Integer)

    quality_score = Column(Integer)
    risk_assessment = Column(String(20))

    findings = Column(Text)
    comments = Column(Text)
    suggestions = Column(Text)

    corrected_report = Column(JSON)
    correction_fields = Column(JSON)

    attachments = Column(JSON)

    next_action = Column(String(50))
    escalation_required = Column(Boolean, default=False)
    escalation_reason = Column(Text)

    needs_rectification = Column(Boolean, default=False)
    rectification_deadline = Column(Date)

    review_task = relationship("ReviewTask", back_populates="review_records")
    anomaly = relationship("AnomalyRecord", back_populates="review_records")
    reviewer = relationship("User", back_populates="review_records")


class Rectification(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rectifications"

    review_task_id = Column(Integer, ForeignKey("review_tasks.id"), unique=True, nullable=False, index=True)

    rectification_code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    rectification_items = Column(JSON)

    deadline = Column(Date, index=True)
    warning_date = Column(Date)
    actual_completion_date = Column(Date)

    status = Column(String(20), default="pending", index=True)
    priority = Column(String(20), default="high")

    responsible_person = Column(String(100))
    responsible_department = Column(String(200))

    implementation_plan = Column(Text)
    measures = Column(JSON)
    expected_outcome = Column(Text)

    progress = Column(Integer, default=0)
    progress_description = Column(Text)
    update_records = Column(JSON)

    verification_result = Column(String(20), index=True)
    verified_by = Column(Integer)
    verified_at = Column(DateTime)
    verification_notes = Column(Text)

    is_closed = Column(Boolean, default=False, index=True)
    closed_at = Column(DateTime)
    closed_by = Column(Integer)
    closing_notes = Column(Text)

    hospital_id = Column(Integer, index=True)

    review_task = relationship("ReviewTask", back_populates="rectification")
