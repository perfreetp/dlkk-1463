from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class ExaminationBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    equipment_id: Optional[int] = Field(None, description="设备ID")
    room_id: Optional[int] = Field(None, description="机房ID")
    technician_id: Optional[int] = Field(None, description="技师ID")
    doctor_id: Optional[int] = Field(None, description="医生ID")

    accession_number: str = Field(..., max_length=100, description="检查号")
    study_instance_uid: Optional[str] = Field(None, max_length=200, description="实例UID")
    patient_id: Optional[str] = Field(None, max_length=100, description="患者ID")
    patient_name: Optional[str] = Field(None, max_length=100, description="患者姓名")
    patient_gender: Optional[str] = Field(None, max_length=10, description="患者性别")
    patient_age: Optional[int] = Field(None, description="患者年龄")

    examination_date: date = Field(..., description="检查日期")
    examination_time: Optional[datetime] = Field(None, description="检查时间")

    laterality: str = Field(..., max_length=10, description="检查侧别")
    views: Optional[str] = Field(None, max_length=200, description="投照体位")
    view_count: Optional[int] = Field(0, description="体位数量")

    compression_pressure: Optional[float] = Field(None, description="压迫压力")
    dose_area_product: Optional[float] = Field(None, description="剂量面积乘积")
    average_glandular_dose: Optional[float] = Field(None, description="平均腺体剂量")

    status: Optional[str] = Field("pending", max_length=50, description="状态")
    source_system: Optional[str] = Field(None, max_length=100, description="来源系统")

    model_config = ConfigDict(from_attributes=True)


class ExaminationCreate(ExaminationBase):
    image_quality: Optional["ImageQualityCreate"] = None
    birads_report: Optional["BIRADSReportCreate"] = None


class ExaminationUpdate(BaseModel):
    equipment_id: Optional[int] = None
    room_id: Optional[int] = None
    technician_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(from_attributes=True)


class ExaminationResponse(ExaminationBase):
    id: int
    hospital_name: Optional[str] = None
    equipment_name: Optional[str] = None
    room_name: Optional[str] = None
    technician_name: Optional[str] = None
    doctor_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImageQualityBase(BaseModel):
    examination_id: Optional[int] = Field(None, description="检查ID")

    position_completeness: Optional[bool] = Field(True, description="体位完整性")
    missing_views: Optional[str] = Field(None, max_length=500, description="缺失体位")

    breast_position: Optional[str] = Field(None, max_length=50, description="乳腺位置")
    nipple_position: Optional[str] = Field(None, max_length=50, description="乳头位置")
    pectoral_muscle: Optional[str] = Field(None, max_length=50, description="胸大肌显示")
    retromammary_space: Optional[str] = Field(None, max_length=50, description="乳腺后间隙")
    skin_fold: Optional[str] = Field(None, max_length=50, description="皮肤皱褶")
    artifacts: Optional[str] = Field(None, max_length=50, description="伪影")

    exposure_quality: Optional[str] = Field(None, max_length=50, description="曝光质量")
    contrast_score: Optional[int] = Field(None, description="对比度评分")
    noise_score: Optional[int] = Field(None, description="噪声评分")
    sharpness_score: Optional[int] = Field(None, description="锐利度评分")

    compression_score: Optional[int] = Field(None, description="压迫评分")
    overall_score: Optional[int] = Field(None, description="总体评分")

    quality_notes: Optional[str] = Field(None, description="质量备注")

    model_config = ConfigDict(from_attributes=True)


class ImageQualityCreate(ImageQualityBase):
    pass


class ImageQualityUpdate(BaseModel):
    position_completeness: Optional[bool] = None
    missing_views: Optional[str] = Field(None, max_length=500)
    breast_position: Optional[str] = Field(None, max_length=50)
    nipple_position: Optional[str] = Field(None, max_length=50)
    pectoral_muscle: Optional[str] = Field(None, max_length=50)
    retromammary_space: Optional[str] = Field(None, max_length=50)
    skin_fold: Optional[str] = Field(None, max_length=50)
    artifacts: Optional[str] = Field(None, max_length=50)
    exposure_quality: Optional[str] = Field(None, max_length=50)
    contrast_score: Optional[int] = None
    noise_score: Optional[int] = None
    sharpness_score: Optional[int] = None
    compression_score: Optional[int] = None
    overall_score: Optional[int] = None
    quality_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ImageQualityResponse(ImageQualityBase):
    id: int
    is_position_complete: Optional[bool] = None
    is_quality_acceptable: Optional[bool] = None
    risk_level: Optional[str] = None
    auto_qa_result: Optional[str] = None
    qa_complete: Optional[bool] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BIRADSReportBase(BaseModel):
    examination_id: Optional[int] = Field(None, description="检查ID")

    breast_density: Optional[str] = Field(None, max_length=20, description="乳腺密度")
    density_standard: Optional[str] = Field(None, max_length=50, description="密度标准")

    birads_classification: str = Field(..., max_length=10, description="BI-RADS分类")
    birads_subcategory: Optional[str] = Field(None, max_length=20, description="BI-RADS亚分类")

    mass_present: Optional[bool] = Field(False, description="有无肿块")
    mass_description: Optional[str] = Field(None, description="肿块描述")
    mass_shape: Optional[str] = Field(None, max_length=50, description="肿块形状")
    mass_margin: Optional[str] = Field(None, max_length=50, description="肿块边缘")
    mass_density: Optional[str] = Field(None, max_length=50, description="肿块密度")
    mass_size: Optional[float] = Field(None, description="肿块大小")

    calcification_present: Optional[bool] = Field(False, description="有无钙化")
    calcification_description: Optional[str] = Field(None, description="钙化描述")
    calcification_type: Optional[str] = Field(None, max_length=50, description="钙化类型")
    calcification_distribution: Optional[str] = Field(None, max_length=50, description="钙化分布")

    architectural_distortion: Optional[bool] = Field(False, description="结构扭曲")
    asymmetry: Optional[bool] = Field(False, description="不对称")
    focal_asymmetry: Optional[bool] = Field(False, description="局灶性不对称")
    skin_changes: Optional[bool] = Field(False, description="皮肤改变")
    nipple_retraction: Optional[bool] = Field(False, description="乳头回缩")
    axillary_adenopathy: Optional[bool] = Field(False, description="腋窝淋巴结肿大")

    findings_summary: Optional[str] = Field(None, description="征象总结")
    impression: Optional[str] = Field(None, description="诊断印象")
    recommendations: Optional[str] = Field(None, description="建议")

    report_date: Optional[date] = Field(None, description="报告日期")
    reporting_doctor: Optional[str] = Field(None, max_length=100, description="报告医生")
    review_doctor: Optional[str] = Field(None, max_length=100, description="审核医生")

    model_config = ConfigDict(from_attributes=True)


class BIRADSReportCreate(BIRADSReportBase):
    pass


class BIRADSReportUpdate(BaseModel):
    breast_density: Optional[str] = Field(None, max_length=20)
    birads_classification: Optional[str] = Field(None, max_length=10)
    birads_subcategory: Optional[str] = Field(None, max_length=20)
    findings_summary: Optional[str] = None
    impression: Optional[str] = None
    recommendations: Optional[str] = None
    report_date: Optional[date] = None

    model_config = ConfigDict(from_attributes=True)


class BIRADSReportResponse(BIRADSReportBase):
    id: int
    is_report_complete: Optional[bool] = None
    density_check_result: Optional[str] = None
    birads_check_result: Optional[str] = None
    description_quality_score: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExaminationWithDetailResponse(ExaminationResponse):
    image_quality: Optional[ImageQualityResponse] = None
    birads_report: Optional[BIRADSReportResponse] = None
    anomaly_count: Optional[int] = 0
    review_task_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)


class ExaminationBatchCreate(BaseModel):
    examinations: List[ExaminationCreate]
    hospital_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


ExaminationCreate.model_rebuild()
ExaminationResponse.model_rebuild()
