from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class MonthlyReportBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    report_year: int = Field(..., description="报告年份")
    report_month: int = Field(..., description="报告月份")
    report_type: Optional[str] = Field("screening", max_length=50, description="报告类型")

    summary: Optional[str] = Field(None, description="总结")
    problems: Optional[str] = Field(None, description="存在问题")
    recommendations: Optional[str] = Field(None, description="改进建议")

    model_config = ConfigDict(from_attributes=True)


class MonthlyReportCreate(MonthlyReportBase):
    pass


class MonthlyReportUpdate(BaseModel):
    summary: Optional[str] = None
    problems: Optional[str] = None
    recommendations: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)
    published: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class MonthlyReportResponse(MonthlyReportBase):
    id: int
    report_code: str
    report_name: str

    total_examinations: int
    bilateral_examinations: int
    position_pass_rate: float
    quality_pass_rate: float
    report_standard_rate: float

    birads_0_count: int
    birads_1_count: int
    birads_2_count: int
    birads_3_count: int
    birads_4_count: int
    birads_5_count: int
    birads_6_count: int

    density_a_count: int
    density_b_count: int
    density_c_count: int
    density_d_count: int

    anomaly_count: int
    anomaly_rate: float
    position_anomaly_count: int
    quality_anomaly_count: int
    report_anomaly_count: int

    review_task_count: int
    review_completed_count: int
    review_overdue_count: int
    review_avg_duration: float

    rectification_count: int
    rectification_completed_count: int

    avg_compression_pressure: Optional[float] = None
    avg_dose: Optional[float] = None
    avg_ag_dose: Optional[float] = None

    equipment_stats: Optional[List[Dict[str, Any]]] = None
    technician_stats: Optional[List[Dict[str, Any]]] = None
    doctor_stats: Optional[List[Dict[str, Any]]] = None
    room_stats: Optional[List[Dict[str, Any]]] = None

    high_frequency_defects: Optional[List[Dict[str, Any]]] = None
    best_practices: Optional[List[Dict[str, Any]]] = None

    hospital_name: Optional[str] = None

    status: str
    generated_by: Optional[int] = None
    generated_at: Optional[str] = None
    approved_by: Optional[int] = None
    approved_at: Optional[str] = None
    published: bool

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HighFrequencyDefectBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    monthly_report_id: Optional[int] = Field(None, description="月报ID")

    defect_code: str = Field(..., max_length=100, description="缺陷编码")
    defect_name: str = Field(..., max_length=200, description="缺陷名称")
    defect_type: Optional[str] = Field(None, max_length=50, description="缺陷类型")
    defect_category: Optional[str] = Field(None, max_length=50, description="缺陷分类")

    description: Optional[str] = Field(None, description="缺陷描述")
    occurrence_count: Optional[int] = Field(0, description="发生次数")
    occurrence_rate: Optional[float] = Field(0.0, description="发生率")

    affected_count: Optional[int] = Field(0, description="受影响数量")
    affected_rate: Optional[float] = Field(0.0, description="受影响率")

    related_rule_id: Optional[int] = Field(None, description="关联规则ID")
    severity_level: Optional[str] = Field(None, max_length=20, description="严重程度")
    risk_score: Optional[int] = Field(None, description="风险分值")

    trend: Optional[str] = Field(None, max_length=20, description="趋势")
    trend_change: Optional[float] = Field(None, description="趋势变化")

    root_cause_analysis: Optional[str] = Field(None, description="根因分析")
    improvement_measures: Optional[str] = Field(None, description="改进措施")
    responsible_person: Optional[str] = Field(None, max_length=100, description="责任人")

    is_group_level: Optional[bool] = Field(False, description="是否集团级")
    status: Optional[str] = Field("active", max_length=20, description="状态")

    model_config = ConfigDict(from_attributes=True)


class HighFrequencyDefectCreate(HighFrequencyDefectBase):
    pass


class HighFrequencyDefectUpdate(BaseModel):
    defect_name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    root_cause_analysis: Optional[str] = None
    improvement_measures: Optional[str] = None
    responsible_person: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, max_length=20)

    model_config = ConfigDict(from_attributes=True)


class HighFrequencyDefectResponse(HighFrequencyDefectBase):
    id: int
    hospital_name: Optional[str] = None
    monthly_report_period: Optional[str] = None

    related_examinations: Optional[List[int]] = None
    related_rooms: Optional[List[int]] = None
    related_technicians: Optional[List[int]] = None
    related_equipments: Optional[List[int]] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StatsQueryParams(BaseModel):
    hospital_id: Optional[int] = Field(None, description="院区ID")
    equipment_id: Optional[int] = Field(None, description="设备ID")
    technician_id: Optional[int] = Field(None, description="技师ID")
    doctor_id: Optional[int] = Field(None, description="医生ID")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    period: Optional[str] = Field("month", description="统计周期: day/week/month/quarter/year")
    group_by: Optional[str] = Field("hospital", description="分组维度: hospital/equipment/technician/doctor/room")

    model_config = ConfigDict(from_attributes=True)


class DailyStatsResponse(BaseModel):
    stat_date: date
    total_examinations: int
    position_pass_count: int
    position_pass_rate: float
    quality_pass_count: int
    quality_pass_rate: float
    report_standard_count: int
    report_standard_rate: float
    anomaly_count: int
    anomaly_rate: float

    model_config = ConfigDict(from_attributes=True)


class QualityTrendResponse(BaseModel):
    period: str
    period_start: date
    period_end: date
    total_examinations: int
    position_pass_rate: float
    quality_pass_rate: float
    report_standard_rate: float
    anomaly_rate: float
    avg_overall_score: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class ReportExportRequest(BaseModel):
    report_type: str = Field(..., description="报表类型: monthly/quarterly/annual")
    hospital_ids: Optional[List[int]] = Field(None, description="院区ID列表")
    start_date: Optional[date] = Field(None, description="开始日期")
    end_date: Optional[date] = Field(None, description="结束日期")
    export_format: Optional[str] = Field("excel", description="导出格式: excel/pdf")
    include_charts: Optional[bool] = Field(True, description="是否包含图表")

    model_config = ConfigDict(from_attributes=True)
