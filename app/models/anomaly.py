from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, Float, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class AnomalyRecord(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "anomaly_records"

    examination_id = Column(Integer, ForeignKey("examinations.id"), nullable=False, index=True)
    rule_id = Column(Integer, ForeignKey("quality_rules.id"), nullable=True, index=True)
    review_task_id = Column(Integer, ForeignKey("review_tasks.id"), nullable=True, index=True)

    anomaly_type = Column(String(50), nullable=False, index=True)
    anomaly_category = Column(String(50), index=True)
    severity_level = Column(String(20), default="medium", index=True)
    risk_score = Column(Integer, default=5)

    description = Column(Text, nullable=False)
    detail_data = Column(JSON)
    affected_fields = Column(JSON)

    detected_at = Column(DateTime, nullable=False)
    detected_by = Column(String(50), default="system")
    detection_method = Column(String(50))

    status = Column(String(20), default="pending", index=True)
    is_confirmed = Column(Boolean, default=False)
    is_false_positive = Column(Boolean, default=False)

    confirmation_notes = Column(Text)
    confirmed_by = Column(Integer)
    confirmed_at = Column(DateTime)

    correction_suggestion = Column(Text)
    correction_status = Column(String(20), default="pending", index=True)
    corrected_at = Column(DateTime)

    hospital_id = Column(Integer, index=True)
    equipment_id = Column(Integer, index=True)
    technician_id = Column(Integer, index=True)
    doctor_id = Column(Integer, index=True)

    examination = relationship("Examination", back_populates="anomaly_records")
    rule = relationship("QualityRule", back_populates="anomalies")
    review_task = relationship("ReviewTask", back_populates="anomalies")
    review_records = relationship("ReviewRecord", back_populates="anomaly")


class SimilarityCheck(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "similarity_checks"

    examination_id = Column(Integer, ForeignKey("examinations.id"), nullable=False, index=True)
    target_report_id = Column(Integer, ForeignKey("birads_reports.id"), nullable=False, index=True)

    comparison_type = Column(String(50), index=True)
    similarity_score = Column(Float, nullable=False, index=True)
    similarity_threshold = Column(Float, nullable=False)
    is_suspicious = Column(Boolean, default=False, index=True)

    field_similarities = Column(JSON)
    common_findings = Column(JSON)
    differing_findings = Column(JSON)

    description1 = Column(Text)
    description2 = Column(Text)
    processed_text1 = Column(Text)
    processed_text2 = Column(Text)

    keywords1 = Column(JSON)
    keywords2 = Column(JSON)
    common_keywords = Column(JSON)

    check_method = Column(String(50))
    check_result = Column(String(20), index=True)
    notes = Column(Text)

    reviewed_by = Column(Integer)
    reviewed_at = Column(DateTime)
    review_notes = Column(Text)
    review_status = Column(String(20), default="pending", index=True)

    hospital_id = Column(Integer, index=True)
    doctor_id = Column(Integer, index=True)

    examination = relationship("Examination", back_populates="similarity_checks", foreign_keys=[examination_id])
    target_report = relationship("BIRADSReport", back_populates="similarity_checks", foreign_keys=[target_report_id])
