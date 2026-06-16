from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class BenchmarkDataBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    equipment_id: Optional[int] = Field(None, description="设备ID")
    technician_id: Optional[int] = Field(None, description="技师ID")
    doctor_id: Optional[int] = Field(None, description="医生ID")
    room_id: Optional[int] = Field(None, description="机房ID")

    benchmark_period: str = Field(..., max_length=20, description="对标周期")
    benchmark_date: date = Field(..., description="对标日期")
    benchmark_type: str = Field(..., max_length=50, description="对标类型")

    model_config = ConfigDict(from_attributes=True)


class BenchmarkDataCreate(BenchmarkDataBase):
    pass


class BenchmarkDataResponse(BenchmarkDataBase):
    id: int
    total_examinations: int
    position_pass_count: int
    position_pass_rate: float
    position_rank: Optional[int] = None
    quality_pass_count: int
    quality_pass_rate: float
    quality_rank: Optional[int] = None
    report_standard_count: int
    report_standard_rate: float
    report_rank: Optional[int] = None
    overall_score: float
    overall_rank: Optional[int] = None
    anomaly_count: int
    anomaly_rate: float
    avg_compression_pressure: Optional[float] = None
    avg_dose: Optional[float] = None
    avg_ag_dose: Optional[float] = None
    avg_review_duration: Optional[float] = None
    review_timely_rate: float
    birads_distribution: Optional[Dict[str, Any]] = None
    density_distribution: Optional[Dict[str, Any]] = None
    comparison_group: Optional[str] = None
    group_average: Optional[Dict[str, Any]] = None
    group_rank: Optional[int] = None
    deviation_from_group_avg: Optional[float] = None
    performance_level: str
    strengths: Optional[List[str]] = None
    weaknesses: Optional[List[str]] = None
    improvement_suggestions: Optional[str] = None
    is_best: bool
    is_improvement: bool
    improvement_rate: Optional[float] = None
    hospital_name: Optional[str] = None
    equipment_name: Optional[str] = None
    technician_name: Optional[str] = None
    doctor_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PersistentAnomalyRoomBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    room_id: int = Field(..., description="机房ID")
    room_code: str = Field(..., max_length=50, description="机房编码")
    room_name: str = Field(..., max_length=100, description="机房名称")
    anomaly_type: str = Field(..., max_length=50, description="异常类型")
    first_detected_date: date = Field(..., description="首次发现日期")
    last_detected_date: date = Field(..., description="最近发现日期")
    severity_level: Optional[str] = Field("high", max_length=20, description="严重程度")
    risk_assessment: Optional[str] = Field(None, description="风险评估")
    rectification_deadline: Optional[date] = Field(None, description="整改截止日期")
    assigned_person: Optional[str] = Field(None, max_length=100, description="责任人")
    assigned_department: Optional[str] = Field(None, max_length=200, description="责任部门")

    model_config = ConfigDict(from_attributes=True)


class PersistentAnomalyRoomCreate(PersistentAnomalyRoomBase):
    pass


class PersistentAnomalyRoomUpdate(BaseModel):
    rectification_status: Optional[str] = Field(None, max_length=20)
    rectification_start_date: Optional[date] = None
    progress: Optional[int] = None
    latest_update: Optional[str] = None
    improvement_measures: Optional[List[Dict[str, Any]]] = None
    is_resolved: Optional[bool] = None
    resolution_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PersistentAnomalyRoomResponse(PersistentAnomalyRoomBase):
    id: int
    anomaly_count: int
    consecutive_months: int
    monthly_anomaly_counts: Optional[Dict[str, Any]] = None
    total_examinations_count: int
    anomaly_rate: float
    affected_equipments: Optional[List[int]] = None
    affected_technicians: Optional[List[int]] = None
    affected_doctors: Optional[List[int]] = None
    rectification_status: str
    rectification_start_date: Optional[date] = None
    improvement_measures: Optional[List[Dict[str, Any]]] = None
    progress: int
    is_resolved: bool
    resolved_date: Optional[date] = None
    resolution_notes: Optional[str] = None
    hospital_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BestPracticeBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    practice_code: Optional[str] = Field(None, max_length=100, description="案例编码")
    title: str = Field(..., max_length=200, description="案例标题")
    practice_type: Optional[str] = Field(None, max_length=50, description="案例类型")
    category: Optional[str] = Field(None, max_length=50, description="案例分类")
    description: str = Field(..., description="案例描述")
    background: Optional[str] = Field(None, description="案例背景")
    implementation_steps: Optional[List[Dict[str, Any]]] = None
    key_points: Optional[List[str]] = None
    achieved_results: Optional[Dict[str, Any]] = None
    measurable_indicators: Optional[Dict[str, Any]] = None
    applicable_scenarios: Optional[List[str]] = None
    precautions: Optional[str] = None
    author: Optional[str] = Field(None, max_length=100, description="作者")
    author_title: Optional[str] = Field(None, max_length=100, description="作者职称")
    contact_info: Optional[str] = Field(None, max_length=200, description="联系方式")
    is_group_promoted: Optional[bool] = Field(False, description="是否集团推广")

    model_config = ConfigDict(from_attributes=True)


class BestPracticeCreate(BestPracticeBase):
    pass


class BestPracticeUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)
    is_group_promoted: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class BestPracticeResponse(BestPracticeBase):
    id: int
    related_examinations: Optional[List[int]] = None
    related_doctors: Optional[List[int]] = None
    related_technicians: Optional[List[int]] = None
    likes_count: int
    references_count: int
    attachments: Optional[List[Dict[str, Any]]] = None
    external_url: Optional[str] = None
    hospital_name: Optional[str] = None
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BenchmarkQueryParams(BaseModel):
    hospital_id: Optional[int] = Field(None, description="院区ID")
    hospital_ids: Optional[List[int]] = Field(None, description="院区ID列表")
    benchmark_year: Optional[int] = Field(None, description="年份")
    benchmark_month: Optional[int] = Field(None, description="月份")
    rank_level: Optional[str] = Field(None, description="排名等级")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    benchmark_type: Optional[str] = Field(None, description="对标类型")
    comparison_group: Optional[str] = Field(None, description="对比组")
    sort_by: Optional[str] = Field("overall_score", description="排序字段")

    model_config = ConfigDict(from_attributes=True)


class BenchmarkComparisonResponse(BaseModel):
    benchmark_date: date
    benchmark_year: Optional[int] = None
    benchmark_month: Optional[int] = None
    period: str
    total_hospitals: int
    items: List[BenchmarkDataResponse] = []
    rankings: Optional[List[BenchmarkDataResponse]] = None
    group_averages: Dict[str, Any] = {}
    best_performers: List[Dict[str, Any]] = []
    areas_for_improvement: List[Dict[str, Any]] = []

    model_config = ConfigDict(from_attributes=True)


class RankingResponse(BaseModel):
    ranking_type: str
    period: str
    items: List[Dict[str, Any]] = []
    update_time: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(from_attributes=True)
