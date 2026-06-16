from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, Date, Float
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class MonthlyReport(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "monthly_reports"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    report_year = Column(Integer, nullable=False, index=True)
    report_month = Column(Integer, nullable=False, index=True)

    report_code = Column(String(100), unique=True, nullable=False, index=True)
    report_name = Column(String(200), nullable=False)
    report_type = Column(String(50), default="screening", index=True)

    total_examinations = Column(Integer, default=0)
    bilateral_examinations = Column(Integer, default=0)
    position_pass_rate = Column(Float, default=0)
    quality_pass_rate = Column(Float, default=0)
    report_standard_rate = Column(Float, default=0)

    birads_0_count = Column(Integer, default=0)
    birads_1_count = Column(Integer, default=0)
    birads_2_count = Column(Integer, default=0)
    birads_3_count = Column(Integer, default=0)
    birads_4_count = Column(Integer, default=0)
    birads_5_count = Column(Integer, default=0)
    birads_6_count = Column(Integer, default=0)

    density_a_count = Column(Integer, default=0)
    density_b_count = Column(Integer, default=0)
    density_c_count = Column(Integer, default=0)
    density_d_count = Column(Integer, default=0)

    anomaly_count = Column(Integer, default=0)
    anomaly_rate = Column(Float, default=0)
    position_anomaly_count = Column(Integer, default=0)
    quality_anomaly_count = Column(Integer, default=0)
    report_anomaly_count = Column(Integer, default=0)

    review_task_count = Column(Integer, default=0)
    review_completed_count = Column(Integer, default=0)
    review_overdue_count = Column(Integer, default=0)
    review_avg_duration = Column(Float, default=0)

    rectification_count = Column(Integer, default=0)
    rectification_completed_count = Column(Integer, default=0)

    avg_compression_pressure = Column(Float)
    avg_dose = Column(Float)
    avg_ag_dose = Column(Float)

    equipment_stats = Column(JSON)
    technician_stats = Column(JSON)
    doctor_stats = Column(JSON)
    room_stats = Column(JSON)

    high_frequency_defects = Column(JSON)
    best_practices = Column(JSON)

    summary = Column(Text)
    problems = Column(Text)
    recommendations = Column(Text)

    status = Column(String(20), default="draft", index=True)
    generated_by = Column(Integer)
    generated_at = Column(String(20))
    approved_by = Column(Integer)
    approved_at = Column(String(20))
    published = Column(Boolean, default=False)

    hospital = relationship("Hospital")
    high_frequency_defect_records = relationship("HighFrequencyDefect", back_populates="monthly_report")


class HighFrequencyDefect(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "high_frequency_defects"

    monthly_report_id = Column(Integer, ForeignKey("monthly_reports.id"), nullable=True, index=True)
    hospital_id = Column(Integer, nullable=False, index=True)

    defect_code = Column(String(100), nullable=False, index=True)
    defect_name = Column(String(200), nullable=False)
    defect_type = Column(String(50), index=True)
    defect_category = Column(String(50), index=True)

    description = Column(Text)
    occurrence_count = Column(Integer, default=0)
    occurrence_rate = Column(Float, default=0)

    affected_count = Column(Integer, default=0)
    affected_rate = Column(Float, default=0)

    related_rule_id = Column(Integer)
    severity_level = Column(String(20))
    risk_score = Column(Integer)

    trend = Column(String(20))
    trend_change = Column(Float)

    root_cause_analysis = Column(Text)
    improvement_measures = Column(Text)
    responsible_person = Column(String(100))

    related_examinations = Column(JSON)
    related_rooms = Column(JSON)
    related_technicians = Column(JSON)
    related_equipments = Column(JSON)

    is_group_level = Column(Boolean, default=False, index=True)
    status = Column(String(20), default="active", index=True)

    monthly_report = relationship("MonthlyReport", back_populates="high_frequency_defect_records")
