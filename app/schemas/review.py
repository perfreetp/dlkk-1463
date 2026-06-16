from typing import Optional, List, Dict, Any
from datetime import date, datetime
from pydantic import BaseModel, Field, ConfigDict


class AssignTaskRequest(BaseModel):
    assignee_id: int = Field(..., description="被分配人ID")
    due_date: Optional[date] = Field(None, description="截止日期")
    remark: Optional[str] = Field(None, description="备注")

    model_config = ConfigDict(from_attributes=True)


class BatchAssignRequest(BaseModel):
    task_ids: List[int] = Field(..., description="任务ID列表")
    assignee_id: int = Field(..., description="被分配人ID")
    due_date: Optional[date] = Field(None, description="截止日期")
    remark: Optional[str] = Field(None, description="备注")

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskFilter(BaseModel):
    hospital_id: Optional[int] = None
    assignee_id: Optional[int] = None
    created_by: Optional[int] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    task_type: Optional[str] = None
    examination_id: Optional[int] = None
    overdue_only: bool = False
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    keyword: Optional[str] = None
    sort_by: str = "created_at"
    sort_order: str = "desc"

    model_config = ConfigDict(from_attributes=True)


class ReviewStatsResponse(BaseModel):
    total_tasks: int = 0
    pending_assignment: int = 0
    assigned: int = 0
    accepted: int = 0
    processing: int = 0
    completed: int = 0
    rejected: int = 0
    verified: int = 0

    total_rectifications: int = 0
    rect_pending: int = 0
    rect_in_progress: int = 0
    rect_submitted: int = 0
    rect_verified: int = 0
    rect_failed: int = 0

    completion_rate: Optional[float] = None
    rectification_rate: Optional[float] = None
    average_review_time_seconds: Optional[float] = None
    average_rectification_time_seconds: Optional[float] = None

    overdue_tasks: int = 0
    overdue_rectifications: int = 0

    by_priority: Optional[Dict[str, int]] = None
    by_type: Optional[Dict[str, int]] = None
    by_verdict: Optional[Dict[str, int]] = None
    by_hospital: Optional[Dict[str, int]] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskBase(BaseModel):
    hospital_id: int = Field(..., description="院区ID")
    examination_id: Optional[int] = Field(None, description="检查ID")
    anomaly_id: Optional[int] = Field(None, description="异常记录ID")
    assignee_id: Optional[int] = Field(None, description="被分配人ID")

    task_code: Optional[str] = Field(None, max_length=100, description="任务编码")
    task_type: str = Field(..., max_length=50, description="任务类型")
    priority: Optional[str] = Field("medium", max_length=20, description="优先级")

    title: str = Field(..., max_length=200, description="任务标题")
    description: Optional[str] = Field(None, description="任务描述")
    requirement: Optional[str] = Field(None, description="复核要求")

    anomaly_ids: Optional[List[int]] = Field(None, description="异常ID列表")
    check_items: Optional[List[Dict[str, Any]]] = Field(None, description="检查项")

    due_date: Optional[date] = Field(None, description="截止日期")
    deadline: Optional[date] = Field(None, description="截止日期(别名)")

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskCreate(ReviewTaskBase):
    pass


class ReviewTaskUpdate(BaseModel):
    assignee_id: Optional[int] = None
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    priority: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, max_length=20)
    due_date: Optional[date] = None
    completion_notes: Optional[str] = None
    rejection_reason: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskResponse(ReviewTaskBase):
    id: int
    creator_id: int
    creator_name: Optional[str] = None
    assignee_name: Optional[str] = None
    hospital_name: Optional[str] = None
    examination_accession: Optional[str] = None

    status: str
    workflow_state: str

    assigned_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    is_overdue: bool
    is_urgent: bool

    review_count: int
    max_reviews: int

    anomaly_count: Optional[int] = 0
    review_record_count: Optional[int] = 0

    has_rectification: Optional[bool] = False
    rectification_status: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewRecordBase(BaseModel):
    review_task_id: int = Field(..., description="复核任务ID")
    anomaly_id: Optional[int] = Field(None, description="异常记录ID")

    review_action: str = Field(..., max_length=50, description="复核动作")
    review_result: str = Field(..., max_length=20, description="复核结果")

    quality_score: Optional[int] = Field(None, description="质量评分")
    risk_assessment: Optional[str] = Field(None, max_length=20, description="风险评估")

    findings: Optional[str] = Field(None, description="复核发现")
    comments: Optional[str] = Field(None, description="复核意见")
    suggestions: Optional[str] = Field(None, description="改进建议")

    corrected_report: Optional[Dict[str, Any]] = Field(None, description="修正后的报告")
    correction_fields: Optional[List[str]] = Field(None, description="修正的字段")

    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="附件")

    next_action: Optional[str] = Field(None, max_length=50, description="下一步动作")
    escalation_required: Optional[bool] = Field(False, description="是否需要升级")
    escalation_reason: Optional[str] = Field(None, description="升级原因")

    needs_rectification: Optional[bool] = Field(False, description="是否需要整改")
    rectification_deadline: Optional[date] = Field(None, description="整改截止日期")

    model_config = ConfigDict(from_attributes=True)


class ReviewRecordCreate(ReviewRecordBase):
    pass


class ReviewRecordUpdate(BaseModel):
    review_result: Optional[str] = Field(None, max_length=20)
    quality_score: Optional[int] = None
    comments: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewRecordResponse(ReviewRecordBase):
    id: int
    reviewer_id: int
    reviewer_name: Optional[str] = None

    review_round: int
    reviewed_at: datetime
    review_duration: Optional[int] = None

    anomaly_description: Optional[str] = None
    anomaly_type: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RectificationBase(BaseModel):
    review_task_id: int = Field(..., description="复核任务ID")
    anomaly_id: Optional[int] = Field(None, description="异常记录ID")
    hospital_id: Optional[int] = Field(None, description="院区ID")

    title: str = Field(..., max_length=200, description="整改标题")
    description: Optional[str] = Field(None, description="整改描述")
    rectification_items: Optional[List[Dict[str, Any]]] = Field(None, description="整改项")

    deadline: date = Field(..., description="整改截止日期")
    warning_date: Optional[date] = Field(None, description="预警日期")

    priority: Optional[str] = Field("high", max_length=20, description="优先级")

    responsible_person: Optional[str] = Field(None, max_length=100, description="责任人")
    responsible_person_id: Optional[int] = Field(None, description="责任人ID")
    responsible_department: Optional[str] = Field(None, max_length=200, description="责任部门")

    implementation_plan: Optional[str] = Field(None, description="实施方案")
    measures: Optional[List[Dict[str, Any]]] = Field(None, description="整改措施")
    expected_outcome: Optional[str] = Field(None, description="预期效果")

    model_config = ConfigDict(from_attributes=True)


class RectificationCreate(RectificationBase):
    pass


class RectificationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, max_length=20)
    progress: Optional[int] = None
    progress_description: Optional[str] = None
    verification_result: Optional[str] = Field(None, max_length=20)
    verification_notes: Optional[str] = None
    is_closed: Optional[bool] = None
    closing_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RectificationResponse(RectificationBase):
    id: int
    rectification_code: str
    hospital_id: int
    hospital_name: Optional[str] = None

    status: str
    progress: int
    progress_description: Optional[str] = None

    actual_completion_date: Optional[date] = None

    verification_result: Optional[str] = None
    verified_by: Optional[int] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None

    is_closed: bool
    closed_at: Optional[datetime] = None
    closed_by: Optional[int] = None
    closing_notes: Optional[str] = None

    update_records: Optional[List[Dict[str, Any]]] = None

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewWorkflowRequest(BaseModel):
    action: str = Field(..., description="工作流动作: accept/start/complete/reject/escalate")
    comments: Optional[str] = Field(None, description="备注")

    model_config = ConfigDict(from_attributes=True)


class RejectTaskRequest(BaseModel):
    reason: str = Field(..., description="拒绝原因")

    model_config = ConfigDict(from_attributes=True)


class EscalateTaskRequest(BaseModel):
    reason: str = Field(..., description="升级原因")

    model_config = ConfigDict(from_attributes=True)


class VerifyRectificationRequest(BaseModel):
    passed: bool = Field(..., description="是否通过")
    comment: Optional[str] = Field(None, description="验收意见")

    model_config = ConfigDict(from_attributes=True)


class RejectRectificationRequest(BaseModel):
    reason: str = Field(..., description="拒绝原因")

    model_config = ConfigDict(from_attributes=True)


class ReviewTaskStatsResponse(BaseModel):
    total_count: int = 0
    pending_count: int = 0
    processing_count: int = 0
    completed_count: int = 0
    rejected_count: int = 0
    overdue_count: int = 0

    my_pending_count: int = 0
    my_processing_count: int = 0
    my_completed_count: int = 0

    avg_completion_days: Optional[float] = None
    completion_rate: Optional[float] = None
    overdue_rate: Optional[float] = None

    by_hospital: Optional[Dict[str, int]] = None
    by_type: Optional[Dict[str, int]] = None
    by_priority: Optional[Dict[str, int]] = None

    trend_data: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(from_attributes=True)
