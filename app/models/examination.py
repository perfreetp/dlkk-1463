from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, Date, DateTime, Float, SmallInteger
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class Examination(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "examinations"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    equipment_id = Column(Integer, ForeignKey("equipments.id"), nullable=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True, index=True)
    technician_id = Column(Integer, ForeignKey("technicians.id"), nullable=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True, index=True)

    accession_number = Column(String(100), unique=True, index=True, nullable=False)
    study_instance_uid = Column(String(200), unique=True, index=True)
    patient_id = Column(String(100), index=True)
    patient_name = Column(String(100))
    patient_gender = Column(String(10))
    patient_age = Column(SmallInteger)
    examination_date = Column(Date, index=True, nullable=False)
    examination_time = Column(DateTime)

    laterality = Column(String(10), nullable=False)
    views = Column(String(200))
    view_count = Column(SmallInteger, default=0)

    compression_pressure = Column(Float)
    dose_area_product = Column(Float)
    average_glandular_dose = Column(Float)

    status = Column(String(50), default="pending", index=True)
    source_system = Column(String(100))

    hospital = relationship("Hospital", back_populates="examinations")
    equipment = relationship("Equipment", back_populates="examinations")
    room = relationship("Room", back_populates="examinations")
    technician = relationship("Technician", back_populates="examinations")
    doctor = relationship("Doctor", back_populates="examinations")
    image_quality = relationship("ImageQuality", back_populates="examination", uselist=False, cascade="all, delete-orphan")
    birads_report = relationship("BIRADSReport", back_populates="examination", uselist=False, cascade="all, delete-orphan")
    anomaly_records = relationship("AnomalyRecord", back_populates="examination")
    similarity_checks = relationship("SimilarityCheck", foreign_keys="SimilarityCheck.examination_id", back_populates="examination")
    review_tasks = relationship("ReviewTask", back_populates="examination")


class ImageQuality(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "image_qualities"

    examination_id = Column(Integer, ForeignKey("examinations.id"), unique=True, nullable=False, index=True)

    position_completeness = Column(Boolean, default=True)
    missing_views = Column(String(500))

    breast_position = Column(String(50))
    nipple_position = Column(String(50))
    pectoral_muscle = Column(String(50))
    retromammary_space = Column(String(50))
    skin_fold = Column(String(50))
    artifacts = Column(String(50))

    exposure_quality = Column(String(50))
    contrast_score = Column(SmallInteger)
    noise_score = Column(SmallInteger)
    sharpness_score = Column(SmallInteger)

    compression_score = Column(SmallInteger)
    overall_score = Column(SmallInteger, index=True)

    is_position_complete = Column(Boolean, default=True, index=True)
    is_quality_acceptable = Column(Boolean, default=True, index=True)
    risk_level = Column(String(20), default="normal", index=True)

    quality_notes = Column(Text)
    auto_qa_result = Column(String(50))
    qa_complete = Column(Boolean, default=False)

    examination = relationship("Examination", back_populates="image_quality")


class BIRADSReport(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "birads_reports"

    examination_id = Column(Integer, ForeignKey("examinations.id"), unique=True, nullable=False, index=True)

    breast_density = Column(String(20), index=True)
    density_standard = Column(String(50))

    birads_classification = Column(String(10), index=True, nullable=False)
    birads_subcategory = Column(String(20))

    mass_present = Column(Boolean, default=False)
    mass_description = Column(Text)
    mass_shape = Column(String(50))
    mass_margin = Column(String(50))
    mass_density = Column(String(50))
    mass_size = Column(Float)

    calcification_present = Column(Boolean, default=False)
    calcification_description = Column(Text)
    calcification_type = Column(String(50))
    calcification_distribution = Column(String(50))

    architectural_distortion = Column(Boolean, default=False)
    asymmetry = Column(Boolean, default=False)
    focal_asymmetry = Column(Boolean, default=False)
    skin_changes = Column(Boolean, default=False)
    nipple_retraction = Column(Boolean, default=False)
    axillary_adenopathy = Column(Boolean, default=False)

    findings_summary = Column(Text)
    impression = Column(Text)
    recommendations = Column(Text)

    report_date = Column(Date)
    reporting_doctor = Column(String(100))
    review_doctor = Column(String(100))

    is_report_complete = Column(Boolean, default=False)
    density_check_result = Column(String(50))
    birads_check_result = Column(String(50))
    description_quality_score = Column(SmallInteger)

    examination = relationship("Examination", back_populates="birads_report")
    similarity_checks = relationship("SimilarityCheck", foreign_keys="SimilarityCheck.target_report_id", back_populates="target_report")
