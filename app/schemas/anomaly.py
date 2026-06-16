from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class AnomalyRecordBase(BaseModel):
    examination_id: int = Field(..., description="检查ID")
    rule_id: Optional[int] = Field(None, description="规则ID")

    anomaly_type: str = Field(..., max_length=50, description="异常类型")
    anomaly_category: Optional[str] = Field(None, max_length=50, description="异常分类")
    severity_level: Optional[str] = Field("medium", max_length=20, description="严重程度")
    risk_score: Optional[int] = Field(5, description="风险分值")

    description: str = Field(..., description="异常描述")
    detail_data: Optional[Dict[str, Any]] = Field(None, description="详细数据")
    affected_fields: Optional[List[str]] = Field(None, description="受影响字段")

    correction_suggestion: Optional[str] = Field(None, description="整改建议")

    model_config = ConfigDict(from_attributes=True)


class AnomalyRecordCreate(AnomalyRecordBase):
    pass


class AnomalyRecordUpdate(BaseModel):
    status: Optional[str] = Field(None, max_length=20)
    is_confirmed: Optional[bool] = None
    is_false_positive: Optional[bool] = None
    confirmation_notes: Optional[str] = None
    correction_suggestion: Optional[str] = None
    correction_status: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(from_attributes=True)


class AnomalyRecordResponse(AnomalyRecordBase):
    id: int
    hospital_id: Optional[int] = None
    equipment_id: Optional[int] = None
    technician_id: Optional[int] = None
    doctor_id: Optional[int] = None

    detected_at: datetime
    detected_by: Optional[str] = None
    detection_method: Optional[str] = None

    status: str
    is_confirmed: bool
    is_false_positive: bool
    correction_status: Optional[str] = None

    hospital_name: Optional[str] = None
    examination_accession: Optional[str] = None
    rule_name: Optional[str] = None

    review_task_id: Optional[int] = None
    review_task_status: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SimilarityCheckBase(BaseModel):
    examination_id: int = Field(..., description="检查ID")
    target_report_id: int = Field(..., description="对比报告ID")
    comparison_type: Optional[str] = Field(None, max_length=50, description="对比类型")
    check_method: Optional[str] = Field(None, max_length=50, description="检查方法")
    notes: Optional[str] = Field(None, description="备注")

    model_config = ConfigDict(from_attributes=True)


class SimilarityCheckCreate(SimilarityCheckBase):
    pass


class SimilarityCheckResponse(SimilarityCheckBase):
    id: int
    similarity_score: float
    similarity_threshold: float
    is_suspicious: bool
    check_result: Optional[str] = None
    review_status: Optional[str] = None

    field_similarities: Optional[Dict[str, Any]] = None
    common_findings: Optional[List[str]] = None
    differing_findings: Optional[List[str]] = None
    common_keywords: Optional[List[str]] = None

    hospital_id: Optional[int] = None
    doctor_id: Optional[int] = None

    examination_accession: Optional[str] = None
    target_examination_accession: Optional[str] = None

    reviewed_by: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnomalyStatsResponse(BaseModel):
    total_count: int = 0
    pending_count: int = 0
    confirmed_count: int = 0
    false_positive_count: int = 0

    position_anomaly_count: int = 0
    quality_anomaly_count: int = 0
    report_anomaly_count: int = 0
    similarity_anomaly_count: int = 0

    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    by_hospital: Optional[Dict[str, int]] = None
    by_type: Optional[Dict[str, int]] = None
    by_severity: Optional[Dict[str, int]] = None

    trend_data: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)


class BatchAnomalyDetectRequest(BaseModel):
    examination_ids: List[int] = Field(..., description="检查ID列表")
    rule_types: Optional[List[str]] = Field(None, description="规则类型")
    auto_create_review_task: Optional[bool] = Field(False, description="是否自动创建复核任务")

    model_config = ConfigDict(from_attributes=True)


class BatchAnomalyDetectResult(BaseModel):
    total_processed: int
    anomaly_count: int
    anomaly_records: List[AnomalyRecordResponse] = []
    review_task_ids: List[int] = []
    execution_time_ms: float

    model_config = ConfigDict(from_attributes=True)
