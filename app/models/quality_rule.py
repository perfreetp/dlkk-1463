from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, SmallInteger
from sqlalchemy.orm import relationship

from .base import BaseModel, TimestampMixin, SoftDeleteMixin


class RuleCategory(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "rule_categories"

    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    parent_id = Column(Integer, ForeignKey("rule_categories.id"), nullable=True)
    description = Column(Text)
    sort_order = Column(SmallInteger, default=0)
    is_active = Column(Boolean, default=True, nullable=False)

    rules = relationship("QualityRule", back_populates="category")
    parent = relationship("RuleCategory", remote_side="RuleCategory.id", back_populates="children")
    children = relationship("RuleCategory", back_populates="parent")


class QualityRule(BaseModel, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "quality_rules"

    category_id = Column(Integer, ForeignKey("rule_categories.id"), nullable=False, index=True)

    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    rule_type = Column(String(50), index=True)

    description = Column(Text)
    rule_logic = Column(Text)
    rule_params = Column(JSON)

    severity_level = Column(String(20), default="medium", index=True)
    risk_score = Column(SmallInteger, default=5)

    condition_expression = Column(Text)
    threshold_value = Column(String(100))
    threshold_operator = Column(String(20))

    applicable_hospitals = Column(JSON)
    effective_date = Column(String(20))
    expiry_date = Column(String(20))

    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True, nullable=False)
    is_standard = Column(Boolean, default=False)

    failure_count = Column(Integer, default=0)
    pass_count = Column(Integer, default=0)

    created_by = Column(Integer)
    approved_by = Column(Integer)
    approved_at = Column(String(20))

    category = relationship("RuleCategory", back_populates="rules")
    anomalies = relationship("AnomalyRecord", back_populates="rule")
