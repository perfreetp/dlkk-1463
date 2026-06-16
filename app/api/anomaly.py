from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User
from ..schemas import (
    AnomalyRecordResponse,
    AnomalyRecordUpdate,
    AnomalyStatsResponse,
    SimilarityCheckResponse,
    BatchAnomalyDetectRequest,
    BatchAnomalyDetectResult,
    ApiResponse,
    PaginationParams,
    DateRangeParams,
)
from ..services import AnomalyDetectionService
from ..core.utils import paginate

router = APIRouter()


@router.get("", response_model=ApiResponse[dict])
@require_permission("anomaly:read")
async def list_anomalies(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    exam_id: Optional[int] = Query(None, description="检查ID"),
    anomaly_type: Optional[str] = Query(None, description="异常类型"),
    severity: Optional[str] = Query(None, description="严重程度"),
    status: Optional[str] = Query(None, description="状态"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import AnomalyRecord
    anomaly_service = AnomalyDetectionService(db)

    if exam_id:
        query = db.query(AnomalyRecord).filter(
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.examination_id == exam_id,
        )
        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)
        if anomaly_type:
            query = query.filter(AnomalyRecord.anomaly_type == anomaly_type)
        if severity:
            query = query.filter(AnomalyRecord.severity_level == severity)
        if status:
            query = query.filter(AnomalyRecord.status == status)
        if start_date:
            query = query.filter(AnomalyRecord.detected_at >= start_date)
        if end_date:
            query = query.filter(AnomalyRecord.detected_at <= end_date)

        total = query.count()
        anomalies = query.order_by(AnomalyRecord.detected_at.desc()).offset(pagination.offset).limit(pagination.limit).all()
    else:
        anomalies, total = anomaly_service.list_anomalies(
            hospital_id=hospital_id,
            anomaly_type=anomaly_type,
            severity_level=severity,
            status=status,
            start_date=start_date,
            end_date=end_date,
            skip=pagination.offset,
            limit=pagination.limit,
        )
    return ApiResponse(data=paginate(
        [AnomalyRecordResponse.model_validate(a) for a in anomalies],
        total,
        pagination,
    ), message="异常记录查询成功")


@router.post("/detect", response_model=ApiResponse[List[AnomalyRecordResponse]])
@require_permission("anomaly:detect")
async def detect_anomalies(
    exam_id: int = Query(..., description="检查ID"),
    auto_create_review: bool = Query(False, description="是否自动创建复核任务"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import Examination
    exam = db.query(Examination).filter(
        Examination.id == exam_id,
        Examination.is_deleted == False,
    ).first()
    if not exam:
        from ..core.exceptions import NotFoundError
        raise NotFoundError(f"检查不存在: {exam_id}")

    anomaly_service = AnomalyDetectionService(db)
    anomalies = anomaly_service.detect_anomalies(exam, auto_create_review=auto_create_review)
    return ApiResponse(
        data=[AnomalyRecordResponse.model_validate(a) for a in anomalies],
        message=f"异常检测完成，共发现 {len(anomalies)} 个异常",
    )


@router.post("/detect-batch", response_model=ApiResponse[BatchAnomalyDetectResult])
@require_permission("anomaly:detect")
async def batch_detect_anomalies(
    request: BatchAnomalyDetectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    result = anomaly_service.batch_detect(request)
    return ApiResponse(data=result, message=f"批量异常检测完成，共处理 {result.total_processed} 条检查")


@router.get("/statistics", response_model=ApiResponse[AnomalyStatsResponse])
async def get_anomaly_statistics(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    stats = anomaly_service.get_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats, message="异常统计查询成功")


@router.get("/statistics/daily", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("anomaly:read")
async def get_daily_anomaly_statistics(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    stats = anomaly_service.get_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats.trend_data or [], message="每日异常统计查询成功")


@router.get("/statistics/by-type", response_model=ApiResponse[Dict[str, Any]])
@require_permission("anomaly:read")
async def get_anomaly_statistics_by_type(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    stats = anomaly_service.get_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats.by_type or {}, message="按类型异常统计查询成功")


@router.get("/statistics/by-hospital", response_model=ApiResponse[Dict[str, Any]])
@require_permission("anomaly:read")
async def get_anomaly_statistics_by_hospital(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    stats = anomaly_service.get_statistics(
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats.by_hospital or {}, message="按医院异常统计查询成功")


@router.get("/statistics/by-rule", response_model=ApiResponse[Dict[str, Any]])
@require_permission("anomaly:read")
async def get_anomaly_statistics_by_rule(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from sqlalchemy import func
    from ..models import AnomalyRecord, QualityRule

    query = db.query(
        QualityRule.name,
        QualityRule.rule_type,
        func.count(AnomalyRecord.id).label("count"),
    ).join(
        AnomalyRecord, AnomalyRecord.rule_id == QualityRule.id,
        isouter=True
    ).filter(
        AnomalyRecord.is_deleted == False,
        AnomalyRecord.is_false_positive == False,
    )

    if hospital_id:
        query = query.filter(AnomalyRecord.hospital_id == hospital_id)
    if start_date:
        query = query.filter(AnomalyRecord.detected_at >= start_date)
    if end_date:
        query = query.filter(AnomalyRecord.detected_at <= end_date)

    results = query.group_by(QualityRule.id).all()

    by_rule = {}
    for name, rule_type, count in results:
        by_rule[name] = {
            "count": count,
            "rule_type": rule_type,
        }

    return ApiResponse(data=by_rule, message="按规则异常统计查询成功")


@router.get("/statistics/trend", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("anomaly:read")
async def get_anomaly_trend(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    stats = anomaly_service.get_statistics(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=stats.trend_data or [], message="异常趋势查询成功")


@router.get("/similarity-check", response_model=ApiResponse[dict])
@require_permission("anomaly:read")
async def list_similarity_checks(
    hospital_id: Optional[int] = Query(None, description="医院ID"),
    exam_id: Optional[int] = Query(None, description="检查ID"),
    is_suspicious: Optional[bool] = Query(None, description="是否可疑"),
    review_status: Optional[str] = Query(None, description="复核状态"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import SimilarityCheck

    query = db.query(SimilarityCheck).filter(SimilarityCheck.is_deleted == False)

    if hospital_id:
        query = query.filter(SimilarityCheck.hospital_id == hospital_id)
    if exam_id:
        query = query.filter(SimilarityCheck.examination_id == exam_id)
    if is_suspicious is not None:
        query = query.filter(SimilarityCheck.is_suspicious == is_suspicious)
    if review_status:
        query = query.filter(SimilarityCheck.review_status == review_status)

    total = query.count()
    checks = query.order_by(SimilarityCheck.created_at.desc()).offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(data=paginate(
        [SimilarityCheckResponse.model_validate(c) for c in checks],
        total,
        pagination,
    ), message="相似度检查列表查询成功")


@router.post("/similarity-check", response_model=ApiResponse[List[SimilarityCheckResponse]])
@require_permission("anomaly:detect")
async def run_similarity_check(
    exam_id: int = Query(..., description="检查ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    checks = anomaly_service.check_similarity(exam_id)
    return ApiResponse(
        data=[SimilarityCheckResponse.model_validate(c) for c in checks],
        message=f"相似度检查完成，共发现 {len(checks)} 条相似报告",
    )


@router.get("/similarity-check/{check_id}", response_model=ApiResponse[SimilarityCheckResponse])
@require_permission("anomaly:read")
async def get_similarity_check(
    check_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import SimilarityCheck
    from ..core.exceptions import NotFoundError

    check = db.query(SimilarityCheck).filter(
        SimilarityCheck.id == check_id,
        SimilarityCheck.is_deleted == False,
    ).first()

    if not check:
        raise NotFoundError(f"相似度检查记录不存在: {check_id}")

    return ApiResponse(data=SimilarityCheckResponse.model_validate(check), message="相似度检查详情查询成功")


@router.get("/similar-reports/{exam_id}", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("anomaly:read")
async def find_similar_reports(
    exam_id: int,
    limit: int = Query(5, ge=1, le=20, description="返回数量限制"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models import Examination
    from ..core.exceptions import NotFoundError

    exam = db.query(Examination).filter(
        Examination.id == exam_id,
        Examination.is_deleted == False,
    ).first()

    if not exam:
        raise NotFoundError(f"检查不存在: {exam_id}")

    anomaly_service = AnomalyDetectionService(db)
    similar_reports = anomaly_service.similarity_checker.find_similar_reports(
        exam,
        hospital_id=exam.hospital_id,
        limit=limit,
    )

    result = []
    for target_exam, similarity, detail in similar_reports:
        result.append({
            "exam_id": target_exam.id,
            "accession_number": target_exam.accession_number,
            "similarity_score": similarity,
            "examination_date": target_exam.examination_date,
            "birads_classification": target_exam.birads_report.birads_classification if target_exam.birads_report else None,
            "field_similarities": detail.get("field_similarities", {}),
            "common_findings": detail.get("common_findings", []),
            "differing_findings": detail.get("differing_findings", []),
        })

    return ApiResponse(data=result, message=f"找到 {len(result)} 份相似报告")


@router.get("/{anomaly_id}", response_model=ApiResponse[AnomalyRecordResponse])
@require_permission("anomaly:read")
async def get_anomaly(
    anomaly_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    anomaly = anomaly_service.get_anomaly(anomaly_id)
    return ApiResponse(data=AnomalyRecordResponse.model_validate(anomaly), message="异常详情查询成功")


@router.patch("/{anomaly_id}/status", response_model=ApiResponse[AnomalyRecordResponse])
@require_permission("anomaly:update")
async def update_anomaly_status(
    anomaly_id: int,
    update_data: AnomalyRecordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    anomaly_service = AnomalyDetectionService(db)
    anomaly = anomaly_service.update_anomaly(anomaly_id, update_data)
    return ApiResponse(data=AnomalyRecordResponse.model_validate(anomaly), message="异常状态更新成功")
