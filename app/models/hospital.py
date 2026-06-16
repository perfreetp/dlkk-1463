from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, Date
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class Hospital(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "hospitals"

    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    short_name = Column(String(100))
    address = Column(String(500))
    level = Column(String(50))
    contact_person = Column(String(100))
    contact_phone = Column(String(20))
    is_active = Column(Boolean, default=True, nullable=False)
    description = Column(Text)

    departments = relationship("Department", back_populates="hospital")
    equipments = relationship("Equipment", back_populates="hospital")
    rooms = relationship("Room", back_populates="hospital")
    technicians = relationship("Technician", back_populates="hospital")
    doctors = relationship("Doctor", back_populates="hospital")
    examinations = relationship("Examination", back_populates="hospital")
    users = relationship("User", back_populates="hospital")
    benchmarks = relationship("BenchmarkData", back_populates="hospital")
    persistent_anomaly_rooms = relationship("PersistentAnomalyRoom", back_populates="hospital")
    best_practices = relationship("BestPractice", back_populates="hospital")
    review_tasks = relationship("ReviewTask", back_populates="hospital")


class Department(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "departments"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    hospital = relationship("Hospital", back_populates="departments")
    users = relationship("User", back_populates="department")
    doctors = relationship("Doctor", back_populates="department")

    __table_args__ = (
        {"sqlite_autoincrement": True},
    )


class Equipment(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "equipments"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    brand = Column(String(100), index=True, nullable=False)
    model = Column(String(100))
    serial_number = Column(String(100))
    install_date = Column(Date)
    last_maintenance_date = Column(Date)
    next_maintenance_date = Column(Date)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    hospital = relationship("Hospital", back_populates="equipments")
    room = relationship("Room", back_populates="equipments")
    examinations = relationship("Examination", back_populates="equipment")
    benchmarks = relationship("BenchmarkData", back_populates="equipment")


class Room(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rooms"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    floor = Column(String(20))
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    hospital = relationship("Hospital", back_populates="rooms")
    equipments = relationship("Equipment", back_populates="room")
    examinations = relationship("Examination", back_populates="room")
    persistent_anomaly = relationship("PersistentAnomalyRoom", back_populates="room", uselist=False)


class Technician(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "technicians"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10))
    title = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    hire_date = Column(Date)
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    hospital = relationship("Hospital", back_populates="technicians")
    examinations = relationship("Examination", back_populates="technician")
    benchmarks = relationship("BenchmarkData", back_populates="technician")


class Doctor(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "doctors"

    hospital_id = Column(Integer, ForeignKey("hospitals.id"), nullable=False, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    gender = Column(String(10))
    title = Column(String(50))
    phone = Column(String(20))
    email = Column(String(100))
    specialty = Column(String(100))
    description = Column(Text)
    is_active = Column(Boolean, default=True, nullable=False)

    hospital = relationship("Hospital", back_populates="doctors")
    department = relationship("Department", back_populates="doctors")
    examinations = relationship("Examination", back_populates="doctor")
    benchmarks = relationship("BenchmarkData", back_populates="doctor")
