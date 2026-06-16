from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User
from ..schemas import (
    ReviewTaskCreate,
    ReviewTaskUpdate,
    ReviewTaskResponse,
    ReviewRecordCreate,
    ReviewRecordResponse,
    RectificationCreate,
    RectificationUpdate,
    RectificationResponse,
    AssignTaskRequest,
    ReviewTaskFilter,
    ReviewStatsResponse,
    RejectTaskRequest,
    EscalateTaskRequest,
    VerifyRectificationRequest,
    RejectRectificationRequest,
    ApiResponse,
    PaginationParams,
    DateRangeParams,
)
from ..services import ReviewService
from ..core.utils import paginate

router = APIRouter()


@router.get("/tasks", response_model=ApiResponse[dict])
@require_permission("review:read")
async def list_review_tasks(
    hospital_id: Optional[int] = None,
    assignee_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    filter_params = ReviewTaskFilter(
        hospital_id=hospital_id,
        assignee_id=assignee_id,
        status=status,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
    )
    tasks, total = review_service.list_tasks(
        filter_params=filter_params,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [ReviewTaskResponse.model_validate(t) for t in tasks],
        total,
        pagination,
    ), message="复核任务列表查询成功")


@router.get("/tasks/me", response_model=ApiResponse[dict])
@require_permission("review:read")
async def list_my_review_tasks(
    hospital_id: Optional[int] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    filter_params = ReviewTaskFilter(
        hospital_id=hospital_id,
        assignee_id=current_user.id,
        status=status,
        priority=priority,
        start_date=start_date,
        end_date=end_date,
    )
    tasks, total = review_service.list_tasks(
        filter_params=filter_params,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [ReviewTaskResponse.model_validate(t) for t in tasks],
        total,
        pagination,
    ), message="我的复核任务列表查询成功")


@router.post("/tasks", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:create")
async def create_review_task(
    task_data: ReviewTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.create_task(task_data, creator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务创建成功")


@router.get("/tasks/{task_id}", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:read")
async def get_review_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.get_task(task_id, operator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务详情查询成功")


@router.put("/tasks/{task_id}", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:update")
async def update_review_task(
    task_id: int,
    update_data: ReviewTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.update_task(task_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务更新成功")


@router.post("/tasks/{task_id}/assign", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:assign")
async def assign_review_task(
    task_id: int,
    assign_data: AssignTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.assign_task(task_id, assign_data, operator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务分配成功")


@router.post("/tasks/{task_id}/accept", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:operate")
async def accept_review_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.accept_task(task_id, operator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务已接受")


@router.post("/tasks/{task_id}/reject", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:operate")
async def reject_review_task(
    task_id: int,
    reject_data: RejectTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.reject_task(task_id, operator_id=current_user.id, reason=reject_data.reason)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务已拒绝")


@router.post("/tasks/{task_id}/submit", response_model=ApiResponse[ReviewRecordResponse])
@require_permission("review:operate")
async def submit_review_result(
    task_id: int,
    record_data: ReviewRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    record = review_service.submit_review(task_id, record_data, operator_id=current_user.id)
    return ApiResponse(data=ReviewRecordResponse.model_validate(record), message="复核结果提交成功")


@router.post("/tasks/{task_id}/escalate", response_model=ApiResponse[ReviewTaskResponse])
@require_permission("review:operate")
async def escalate_review_task(
    task_id: int,
    escalate_data: EscalateTaskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    task = review_service.escalate_task(task_id, reason=escalate_data.reason, operator_id=current_user.id)
    return ApiResponse(data=ReviewTaskResponse.model_validate(task), message="复核任务已升级")


@router.get("/tasks/{task_id}/records", response_model=ApiResponse[List[ReviewRecordResponse]])
@require_permission("review:read")
async def get_review_records(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    records = review_service.get_review_records(task_id=task_id)
    return ApiResponse(
        data=[ReviewRecordResponse.model_validate(r) for r in records],
        message="复核记录列表查询成功"
    )


@router.post("/tasks/{task_id}/records", response_model=ApiResponse[ReviewRecordResponse])
@require_permission("review:operate")
async def add_review_record(
    task_id: int,
    record_data: ReviewRecordCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    record = review_service.add_review_record(task_id, record_data, operator_id=current_user.id)
    return ApiResponse(data=ReviewRecordResponse.model_validate(record), message="复核记录添加成功")


@router.get("/records/{record_id}", response_model=ApiResponse[ReviewRecordResponse])
@require_permission("review:read")
async def get_review_record_detail(
    record_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    record = review_service.get_review_record(record_id)
    return ApiResponse(data=ReviewRecordResponse.model_validate(record), message="复核记录详情查询成功")


@router.get("/rectifications", response_model=ApiResponse[dict])
@require_permission("review:read")
async def list_rectifications(
    hospital_id: Optional[int] = None,
    status: Optional[str] = None,
    responsible_person_id: Optional[int] = None,
    overdue_only: bool = False,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectifications, total = review_service.list_rectifications(
        hospital_id=hospital_id,
        status=status,
        responsible_person_id=responsible_person_id,
        overdue_only=overdue_only,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [RectificationResponse.model_validate(r) for r in rectifications],
        total,
        pagination,
    ), message="整改列表查询成功")


@router.post("/rectifications", response_model=ApiResponse[RectificationResponse])
@require_permission("review:create")
async def create_rectification(
    rect_data: RectificationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.create_rectification(rect_data, creator_id=current_user.id)
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改创建成功")


@router.get("/rectifications/{rect_id}", response_model=ApiResponse[RectificationResponse])
@require_permission("review:read")
async def get_rectification_detail(
    rect_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.get_rectification(rect_id)
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改详情查询成功")


@router.put("/rectifications/{rect_id}", response_model=ApiResponse[RectificationResponse])
@require_permission("review:update")
async def update_rectification(
    rect_id: int,
    update_data: RectificationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.update_rectification(rect_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改更新成功")


@router.post("/rectifications/{rect_id}/submit", response_model=ApiResponse[RectificationResponse])
@require_permission("review:operate")
async def submit_rectification(
    rect_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.submit_rectification(rect_id, operator_id=current_user.id)
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改已提交")


@router.post("/rectifications/{rect_id}/verify", response_model=ApiResponse[RectificationResponse])
@require_permission("review:verify")
async def verify_rectification(
    rect_id: int,
    verify_data: VerifyRectificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.verify_rectification(
        rect_id,
        passed=verify_data.passed,
        comment=verify_data.comment,
        operator_id=current_user.id,
    )
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改验收完成")


@router.post("/rectifications/{rect_id}/reject", response_model=ApiResponse[RectificationResponse])
@require_permission("review:verify")
async def reject_rectification(
    rect_id: int,
    reject_data: RejectRectificationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    rectification = review_service.reject_rectification(
        rect_id,
        reason=reject_data.reason,
        operator_id=current_user.id,
    )
    return ApiResponse(data=RectificationResponse.model_validate(rectification), message="整改已拒绝")


@router.get("/statistics", response_model=ApiResponse[ReviewStatsResponse])
@require_permission("review:statistics")
async def get_review_statistics(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    stats = review_service.get_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats, message="复核统计查询成功")


@router.get("/statistics/workload", response_model=ApiResponse[Dict[str, Any]])
@require_permission("review:statistics")
async def get_reviewer_workload(
    user_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    target_user_id = user_id if user_id else current_user.id
    workload = review_service.get_user_workload(target_user_id)
    return ApiResponse(data=workload, message="复核人员工作量查询成功")


@router.get("/statistics/efficiency", response_model=ApiResponse[Dict[str, Any]])
@require_permission("review:statistics")
async def get_review_efficiency(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    efficiency = review_service.get_efficiency_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=efficiency, message="复核效率统计查询成功")


@router.get("/statistics/rectification", response_model=ApiResponse[Dict[str, Any]])
@require_permission("review:statistics")
async def get_rectification_statistics(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    stats = review_service.get_rectification_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats, message="整改统计查询成功")


@router.get("/statistics/by-hospital", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("review:statistics")
async def get_review_statistics_by_hospital(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    review_service = ReviewService(db)
    stats = review_service.get_statistics_by_hospital(
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats, message="各医院复核统计查询成功")
