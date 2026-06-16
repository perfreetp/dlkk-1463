from typing import Optional, List, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel, Field, ConfigDict


class ScheduledTaskBase(BaseModel):
    name: str = Field(..., max_length=200, description="任务名称")
    code: str = Field(..., max_length=100, description="任务编码")
    description: Optional[str] = Field(None, description="任务描述")
    task_type: str = Field(..., max_length=50, description="任务类型")
    cron_expression: Optional[str] = Field(None, max_length=100, description="Cron表达式")
    interval_seconds: Optional[int] = Field(None, description="间隔秒数")
    run_date: Optional[datetime] = Field(None, description="运行时间")
    task_params: Optional[Dict[str, Any]] = Field(None, description="任务参数")
    target_function: str = Field(..., max_length=200, description="目标函数")
    is_enabled: Optional[bool] = Field(True, description="是否启用")
    max_retries: Optional[int] = Field(3, description="最大重试次数")
    timeout_seconds: Optional[int] = Field(3600, description="超时时间")

    model_config = ConfigDict(from_attributes=True)


class ScheduledTaskCreate(ScheduledTaskBase):
    pass


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    cron_expression: Optional[str] = Field(None, max_length=100)
    interval_seconds: Optional[int] = None
    task_params: Optional[Dict[str, Any]] = None
    is_enabled: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class ScheduledTaskResponse(ScheduledTaskBase):
    id: int
    is_running: bool
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[str] = None
    last_run_error: Optional[str] = None
    next_run_at: Optional[datetime] = None
    success_count: int
    failure_count: int
    total_runs: int
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TaskExecutionBase(BaseModel):
    task_id: int = Field(..., description="任务ID")
    execution_id: str = Field(..., max_length=100, description="执行ID")
    status: Optional[str] = Field("pending", max_length=20, description="状态")
    triggered_by: Optional[str] = Field("scheduler", max_length=50, description="触发方式")

    model_config = ConfigDict(from_attributes=True)


class TaskExecutionResponse(TaskExecutionBase):
    id: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_traceback: Optional[str] = None
    retry_count: int
    is_success: bool
    task_name: Optional[str] = None
    task_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TaskTriggerRequest(BaseModel):
    task_id: int = Field(..., description="任务ID")
    task_params: Optional[Dict[str, Any]] = Field(None, description="任务参数")

    model_config = ConfigDict(from_attributes=True)


class TaskStatusResponse(BaseModel):
    task_id: int
    task_name: str
    is_running: bool
    current_execution: Optional[TaskExecutionResponse] = None
    last_execution: Optional[TaskExecutionResponse] = None
    next_run_at: Optional[datetime] = None
    queue_size: int = 0

    model_config = ConfigDict(from_attributes=True)
