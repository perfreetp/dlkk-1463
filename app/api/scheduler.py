from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query, Path
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User, ScheduledTask, TaskExecution
from ..schemas import (
    ScheduledTaskCreate,
    ScheduledTaskUpdate,
    ScheduledTaskResponse,
    TaskExecutionResponse,
    ApiResponse,
    PaginationParams,
    DateRangeParams,
)
from ..services import SchedulerService
from ..core.utils import paginate
from ..core.exceptions import NotFoundError, BusinessError

router = APIRouter()


@router.get("/status", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:read")
async def get_scheduler_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    status = scheduler_service.get_scheduler_status()
    return ApiResponse(data=status, message="调度器状态查询成功")


@router.post("/start", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def start_scheduler(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    try:
        scheduler_service.start()
        status = scheduler_service.get_scheduler_status()
        return ApiResponse(data=status, message="调度器启动成功")
    except Exception as e:
        raise BusinessError(f"调度器启动失败: {str(e)}")


@router.post("/shutdown", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def shutdown_scheduler(
    wait: bool = Query(True, description="是否等待任务完成"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    try:
        scheduler_service.shutdown(wait=wait)
        return ApiResponse(data={"running": False}, message="调度器已关闭")
    except Exception as e:
        raise BusinessError(f"调度器关闭失败: {str(e)}")


@router.post("/pause", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def pause_scheduler(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    if not scheduler_service._scheduler or not scheduler_service._scheduler.running:
        raise BusinessError("调度器未运行")
    scheduler_service._scheduler.pause()
    status = scheduler_service.get_scheduler_status()
    return ApiResponse(data=status, message="调度器已暂停")


@router.post("/resume", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def resume_scheduler(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    if not scheduler_service._scheduler:
        raise BusinessError("调度器未初始化")
    scheduler_service._scheduler.resume()
    status = scheduler_service.get_scheduler_status()
    return ApiResponse(data=status, message="调度器已恢复")


@router.get("/tasks", response_model=ApiResponse[dict])
@require_permission("scheduler:read")
async def list_scheduled_tasks(
    task_type: Optional[str] = Query(None, description="任务类型"),
    is_active: Optional[bool] = Query(None, description="是否启用"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    tasks, total = scheduler_service.list_tasks(
        task_type=task_type,
        is_active=is_active,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [ScheduledTaskResponse.model_validate(t) for t in tasks],
        total,
        pagination,
    ), message="定时任务列表查询成功")


@router.post("/tasks", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:create")
async def create_scheduled_task(
    task_data: ScheduledTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = scheduler_service.create_task(task_data, creator_id=current_user.id)
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message="定时任务创建成功")


@router.get("/tasks/{task_id}", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:read")
async def get_scheduled_task(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = db.query(ScheduledTask).filter(
        ScheduledTask.id == task_id,
        ScheduledTask.is_deleted == False,
    ).first()
    if not task:
        raise NotFoundError(f"定时任务不存在: {task_id}")
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message="定时任务详情查询成功")


@router.put("/tasks/{task_id}", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:update")
async def update_scheduled_task(
    task_id: int = Path(..., description="任务ID"),
    update_data: ScheduledTaskUpdate = ...,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = scheduler_service.update_task(task_id, update_data)
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message="定时任务更新成功")


@router.patch("/tasks/{task_id}/toggle-active", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:operate")
async def toggle_task_active(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = db.query(ScheduledTask).filter(
        ScheduledTask.id == task_id,
        ScheduledTask.is_deleted == False,
    ).first()
    if not task:
        raise NotFoundError(f"定时任务不存在: {task_id}")
    new_is_active = not task.is_active
    task = scheduler_service.toggle_task(task_id, new_is_active)
    message = "定时任务已启用" if new_is_active else "定时任务已禁用"
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message=message)


@router.delete("/tasks/{task_id}", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:delete")
async def delete_scheduled_task(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = db.query(ScheduledTask).filter(
        ScheduledTask.id == task_id,
        ScheduledTask.is_deleted == False,
    ).first()
    if not task:
        raise NotFoundError(f"定时任务不存在: {task_id}")
    
    if scheduler_service._scheduler:
        job_id = f"task_{task_id}"
        if scheduler_service._scheduler.get_job(job_id):
            scheduler_service._scheduler.remove_job(job_id)
    
    task.is_deleted = True
    db.commit()
    return ApiResponse(data={"id": task_id}, message="定时任务删除成功")


@router.post("/tasks/{task_id}/run", response_model=ApiResponse[TaskExecutionResponse])
@require_permission("scheduler:operate")
async def run_task_now(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    execution_log = scheduler_service.run_task_now(task_id)
    return ApiResponse(data=TaskExecutionResponse.model_validate(execution_log), message="任务已立即执行")


@router.post("/tasks/{task_id}/pause", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:operate")
async def pause_task(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = scheduler_service.toggle_task(task_id, False)
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message="定时任务已暂停")


@router.post("/tasks/{task_id}/resume", response_model=ApiResponse[ScheduledTaskResponse])
@require_permission("scheduler:operate")
async def resume_task(
    task_id: int = Path(..., description="任务ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    task = scheduler_service.toggle_task(task_id, True)
    return ApiResponse(data=ScheduledTaskResponse.model_validate(task), message="定时任务已恢复")


@router.get("/tasks/{task_id}/logs", response_model=ApiResponse[dict])
@require_permission("scheduler:read")
async def get_task_execution_logs(
    task_id: int = Path(..., description="任务ID"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    logs, total = scheduler_service.get_execution_logs(
        task_id=task_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [TaskExecutionResponse.model_validate(log) for log in logs],
        total,
        pagination,
    ), message="任务执行日志查询成功")


@router.get("/logs", response_model=ApiResponse[dict])
@require_permission("scheduler:read")
async def list_execution_logs(
    task_id: Optional[int] = Query(None, description="任务ID"),
    status: Optional[str] = Query(None, description="执行状态"),
    date_range: DateRangeParams = Depends(),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    logs, total = scheduler_service.get_execution_logs(
        task_id=task_id,
        status=status,
        start_date=date_range.start_date,
        end_date=date_range.end_date,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [TaskExecutionResponse.model_validate(log) for log in logs],
        total,
        pagination,
    ), message="执行日志列表查询成功")


@router.get("/logs/{log_id}", response_model=ApiResponse[TaskExecutionResponse])
@require_permission("scheduler:read")
async def get_execution_log_detail(
    log_id: int = Path(..., description="日志ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    log = db.query(TaskExecution).filter(TaskExecution.id == log_id).first()
    if not log:
        raise NotFoundError(f"执行日志不存在: {log_id}")
    return ApiResponse(data=TaskExecutionResponse.model_validate(log), message="执行日志详情查询成功")


@router.get("/jobs", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("scheduler:read")
async def list_running_jobs(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    if not scheduler_service._scheduler:
        return ApiResponse(data=[], message="调度器未初始化")
    
    jobs = scheduler_service._scheduler.get_jobs()
    job_list = [
        {
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        }
        for job in jobs
    ]
    return ApiResponse(data=job_list, message="运行中作业列表查询成功")


@router.post("/built-in-tasks/auto-qa", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def trigger_auto_qa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    result = scheduler_service._job_auto_qa(db)
    return ApiResponse(data=result, message="自动QA任务触发成功")


@router.post("/built-in-tasks/anomaly-detection", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def trigger_anomaly_detection(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    params = {
        "hospital_id": hospital_id,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
    }
    result = scheduler_service._job_anomaly_detection(db, params)
    return ApiResponse(data=result, message="异常检测任务触发成功")


@router.post("/built-in-tasks/monthly-report", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def trigger_monthly_report(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    params = {
        "hospital_id": hospital_id,
        "year": year,
        "month": month,
    }
    result = scheduler_service._job_monthly_report(db, params)
    return ApiResponse(data=result, message="月度报告任务触发成功")


@router.post("/built-in-tasks/benchmark", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def trigger_benchmark(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    params = {
        "year": year,
        "month": month,
        "hospital_id": hospital_id,
    }
    result = scheduler_service._job_benchmark_calculation(db, params)
    return ApiResponse(data=result, message="基准数据计算任务触发成功")


@router.post("/built-in-tasks/persistent-anomaly", response_model=ApiResponse[Dict[str, Any]])
@require_permission("scheduler:operate")
async def trigger_persistent_anomaly(
    consecutive_months: int = Query(3, description="连续月数"),
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scheduler_service = SchedulerService(db)
    params = {
        "consecutive_months": consecutive_months,
        "hospital_id": hospital_id,
    }
    result = scheduler_service._job_persistent_anomaly_check(db, params)
    return ApiResponse(data=result, message="持续性异常检测任务触发成功")
