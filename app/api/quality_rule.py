from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User
from ..schemas import (
    QualityRuleCreate,
    QualityRuleUpdate,
    QualityRuleResponse,
    RuleCategoryCreate,
    RuleCategoryUpdate,
    RuleCategoryResponse,
    QualityRuleTestRequest,
    QualityRuleTestResult,
    QualityRuleApplyRequest,
    ApiResponse,
    PaginationParams,
)
from ..services import QualityRuleService
from ..core.utils import paginate

router = APIRouter()


@router.get("/categories", response_model=ApiResponse[List[RuleCategoryResponse]])
@require_permission("rule:read")
async def list_categories(
    parent_id: Optional[int] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    categories = rule_service.list_categories(parent_id=parent_id, is_active=is_active)
    return ApiResponse(data=[RuleCategoryResponse.model_validate(c) for c in categories])


@router.get("/categories/tree", response_model=ApiResponse[List[dict]])
@require_permission("rule:read")
async def get_category_tree(
    hospital_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    tree = rule_service.get_category_tree(hospital_id=hospital_id)
    return ApiResponse(data=tree)


@router.post("/categories", response_model=ApiResponse[RuleCategoryResponse])
@require_permission("rule:create")
async def create_category(
    category_data: RuleCategoryCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    category = rule_service.create_category(category_data, created_by=current_user.id)
    return ApiResponse(data=RuleCategoryResponse.model_validate(category), message="规则分类创建成功")


@router.get("/categories/{category_id}", response_model=ApiResponse[RuleCategoryResponse])
@require_permission("rule:read")
async def get_category(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    category = rule_service.get_category(category_id)
    return ApiResponse(data=RuleCategoryResponse.model_validate(category))


@router.put("/categories/{category_id}", response_model=ApiResponse[RuleCategoryResponse])
@require_permission("rule:update")
async def update_category(
    category_id: int,
    update_data: RuleCategoryUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    category = rule_service.update_category(category_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=RuleCategoryResponse.model_validate(category), message="规则分类更新成功")


@router.get("/active", response_model=ApiResponse[List[QualityRuleResponse]])
@require_permission("rule:read")
async def get_active_rules(
    rule_type: Optional[str] = None,
    hospital_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rules = rule_service.get_active_rules(rule_type=rule_type, hospital_id=hospital_id)
    return ApiResponse(data=[QualityRuleResponse.model_validate(r) for r in rules])


@router.post("/apply", response_model=ApiResponse[List[dict]])
@require_permission("rule:manage")
async def apply_rules(
    apply_data: QualityRuleApplyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    results = rule_service.apply_rules_to_examination(
        exam_id=apply_data.exam_id,
        rule_ids=apply_data.rule_ids,
    )
    return ApiResponse(data=results)


@router.post("/publish", response_model=ApiResponse[dict])
@require_permission("rule:manage")
async def publish_rules(
    rule_ids: List[int] = Query(..., description="规则ID列表"),
    target_hospital_ids: List[int] = Query(..., description="目标医院ID列表"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    result = rule_service.publish_rules(
        rule_ids=rule_ids,
        target_hospital_ids=target_hospital_ids,
        operator_id=current_user.id,
    )
    return ApiResponse(data=result, message="规则下发成功")


@router.get("/execution-history", response_model=ApiResponse[dict])
@require_permission("rule:read")
async def get_rule_execution_history(
    rule_id: Optional[int] = None,
    hospital_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    history, total = rule_service.get_rule_execution_history(
        rule_id=rule_id,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(history, total, pagination))


@router.get("", response_model=ApiResponse[dict])
@require_permission("rule:read")
async def list_rules(
    category_id: Optional[int] = None,
    hospital_id: Optional[int] = None,
    rule_type: Optional[str] = None,
    severity: Optional[str] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rules, total = rule_service.list_rules(
        category_id=category_id,
        hospital_id=hospital_id,
        rule_type=rule_type,
        severity=severity,
        is_active=is_active,
        keyword=keyword,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [QualityRuleResponse.model_validate(r) for r in rules],
        total,
        pagination,
    ))


@router.post("", response_model=ApiResponse[QualityRuleResponse])
@require_permission("rule:create")
async def create_rule(
    rule_data: QualityRuleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rule = rule_service.create_rule(rule_data, created_by=current_user.id)
    return ApiResponse(data=QualityRuleResponse.model_validate(rule), message="质控规则创建成功")


@router.get("/{rule_id}", response_model=ApiResponse[QualityRuleResponse])
@require_permission("rule:read")
async def get_rule(
    rule_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rule = rule_service.get_rule(rule_id)
    return ApiResponse(data=QualityRuleResponse.model_validate(rule))


@router.put("/{rule_id}", response_model=ApiResponse[QualityRuleResponse])
@require_permission("rule:update")
async def update_rule(
    rule_id: int,
    update_data: QualityRuleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rule = rule_service.update_rule(rule_id, update_data, operator_id=current_user.id)
    return ApiResponse(data=QualityRuleResponse.model_validate(rule), message="质控规则更新成功")


@router.patch("/{rule_id}/toggle-active", response_model=ApiResponse[QualityRuleResponse])
@require_permission("rule:manage")
async def toggle_rule_active(
    rule_id: int,
    is_active: bool = Query(..., description="是否激活"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    rule = rule_service.toggle_rule_active(rule_id, is_active, operator_id=current_user.id)
    return ApiResponse(data=QualityRuleResponse.model_validate(rule), message="规则状态更新成功")


@router.post("/{rule_id}/test", response_model=ApiResponse[QualityRuleTestResult])
@require_permission("rule:manage")
async def test_rule(
    rule_id: int,
    test_data: QualityRuleTestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    result = rule_service.test_rule(rule_id, test_data.test_data)
    return ApiResponse(data=result)


@router.get("/{rule_id}/statistics", response_model=ApiResponse[dict])
@require_permission("rule:read")
async def get_rule_statistics(
    rule_id: int,
    hospital_id: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    rule_service = QualityRuleService(db)
    stats = rule_service.get_rule_statistics(
        rule_id=rule_id,
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats)
