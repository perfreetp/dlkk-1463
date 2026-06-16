from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, Date, Float, DateTime
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class BenchmarkData(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "benchmark_datas"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)
    room_id = Column(Integer, nullable=True, index=True)

    benchmark_year = Column(Integer, nullable=False, index=True)
    benchmark_month = Column(Integer, nullable=False, index=True)
    benchmark_period = Column(String(20), nullable=False, index=True)
    benchmark_date = Column(Date, nullable=False, index=True)
    benchmark_type = Column(String(50), nullable=False, index=True)

    data_start_date = Column(Date)
    data_end_date = Column(Date)

    composite_rank = Column(Integer, index=True)
    percentile = Column(Float)
    rank_level = Column(String(20), index=True)

    total_examinations = Column(Integer, default=0)

    position_pass_count = Column(Integer, default=0)
    position_pass_rate = Column(Float, default=0)
    position_rank = Column(Integer)

    quality_pass_count = Column(Integer, default=0)
    quality_pass_rate = Column(Float, default=0)
    quality_rank = Column(Integer)

    report_standard_count = Column(Integer, default=0)
    report_standard_rate = Column(Float, default=0)
    report_rank = Column(Integer)

    overall_score = Column(Float, default=0)
    overall_rank = Column(Integer)

    anomaly_count = Column(Integer, default=0)
    anomaly_rate = Column(Float, default=0)

    avg_compression_pressure = Column(Float)
    avg_dose = Column(Float)
    avg_ag_dose = Column(Float)

    avg_review_duration = Column(Float)
    review_timely_rate = Column(Float, default=0)

    birads_distribution = Column(JSON)
    density_distribution = Column(JSON)

    comparison_group = Column(String(50))
    group_average = Column(JSON)
    group_rank = Column(Integer)
    deviation_from_group_avg = Column(Float)
    performance_level = Column(String(20), default="average", index=True)

    strengths = Column(JSON)
    weaknesses = Column(JSON)
    improvement_suggestions = Column(Text)

    is_best = Column(Boolean, default=False, index=True)
    is_improvement = Column(Boolean, default=False, index=True)
    improvement_rate = Column(Float)

    hospital = relationship("Hospital", back_populates="benchmarks")
    equipment = relationship("Equipment", back_populates="benchmarks")
    technician = relationship("Technician", back_populates="benchmarks")
    doctor = relationship("Doctor", back_populates="benchmarks")


class PersistentAnomalyRoom(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "persistent_anomaly_rooms"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False, index=True)

    room_code = Column(String(50), nullable=False)
    room_name = Column(String(100), nullable=False)

    anomaly_type = Column(String(50), nullable=False, index=True)
    anomaly_count = Column(Integer, default=0)
    consecutive_months = Column(Integer, default=0)

    first_detected_date = Column(Date, nullable=False)
    last_detected_date = Column(Date, nullable=False)

    monthly_anomaly_counts = Column(JSON)

    total_examinations_count = Column(Integer, default=0)
    anomaly_rate = Column(Float, default=0)

    severity_level = Column(String(20), default="high", index=True)
    risk_assessment = Column(Text)

    affected_equipments = Column(JSON)
    affected_technicians = Column(JSON)
    affected_doctors = Column(JSON)

    rectification_status = Column(String(20), default="pending", index=True)
    rectification_start_date = Column(Date)
    rectification_deadline = Column(Date)

    assigned_person = Column(String(100))
    assigned_department = Column(String(200))

    improvement_measures = Column(JSON)
    progress = Column(Integer, default=0)
    latest_update = Column(Text)

    is_resolved = Column(Boolean, default=False, index=True)
    resolved_date = Column(Date)
    resolution_notes = Column(Text)

    hospital = relationship("Hospital", back_populates="persistent_anomaly_rooms")
    room = relationship("Room", back_populates="persistent_anomaly")


class BestPractice(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "best_practices"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)

    practice_code = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(200), nullable=False)
    practice_type = Column(String(50), index=True)
    category = Column(String(50), index=True)

    description = Column(Text, nullable=False)
    background = Column(Text)
    implementation_steps = Column(JSON)
    key_points = Column(JSON)

    achieved_results = Column(JSON)
    measurable_indicators = Column(JSON)

    applicable_scenarios = Column(JSON)
    precautions = Column(Text)

    related_examinations = Column(JSON)
    related_doctors = Column(JSON)
    related_technicians = Column(JSON)

    author = Column(String(100))
    author_title = Column(String(100))
    contact_info = Column(String(200))

    is_group_promoted = Column(Boolean, default=False, index=True)
    promotion_date = Column(Date)
    promoted_by = Column(Integer)

    likes_count = Column(Integer, default=0)
    references_count = Column(Integer, default=0)

    attachments = Column(JSON)
    external_url = Column(String(500))

    status = Column(String(20), default="draft", index=True)
    approved_by = Column(Integer)
    approved_at = Column(DateTime)

    hospital = relationship("Hospital", back_populates="best_practices")
