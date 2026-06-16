from typing import List, Optional, Dict, Any
from datetime import date, datetime
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User, BenchmarkData, PersistentAnomalyRoom, BestPractice, HighFrequencyDefect
from ..schemas import (
    BenchmarkDataResponse,
    PersistentAnomalyRoomResponse,
    PersistentAnomalyRoomUpdate,
    BestPracticeCreate,
    BestPracticeUpdate,
    BestPracticeResponse,
    BenchmarkComparisonResponse,
    RankingResponse,
    ApiResponse,
    PaginationParams,
)
from ..services import BenchmarkService
from ..core.utils import paginate

router = APIRouter()


@router.get("/data", response_model=ApiResponse[dict])
@require_permission("benchmark:read")
async def list_benchmark_data(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    category: Optional[str] = Query(None, description="分类"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    query = db.query(BenchmarkData).filter(BenchmarkData.is_deleted == False)

    if year:
        query = query.filter(BenchmarkData.benchmark_date >= date(year, 1, 1))
        query = query.filter(BenchmarkData.benchmark_date <= date(year, 12, 31))
    if month and year:
        from ..core.utils import get_date_range
        start_date, end_date = get_date_range("month", date(year, month, 1))
        query = query.filter(BenchmarkData.benchmark_date >= start_date)
        query = query.filter(BenchmarkData.benchmark_date <= end_date)
    if hospital_id:
        query = query.filter(BenchmarkData.hospital_id == hospital_id)
    if category:
        query = query.filter(BenchmarkData.benchmark_type == category)

    total = query.count()
    data_list = query.order_by(BenchmarkData.benchmark_date.desc(), BenchmarkData.overall_score.desc()) \
        .offset(pagination.offset).limit(pagination.limit).all()

    return ApiResponse(data=paginate(
        [BenchmarkDataResponse.model_validate(d) for d in data_list],
        total,
        pagination,
    ), message="基准数据列表查询成功")


@router.post("/data", response_model=ApiResponse[List[BenchmarkDataResponse]])
@require_permission("benchmark:manage")
async def generate_benchmark_data(
    year: int = Query(..., description="年份"),
    month: int = Query(..., description="月份"),
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    data_list = benchmark_service.generate_benchmark_data(
        year=year,
        month=month,
        hospital_id=hospital_id,
    )
    return ApiResponse(
        data=[BenchmarkDataResponse.model_validate(d) for d in data_list],
        message=f"{year}年{month}月基准数据生成成功"
    )


@router.get("/data/{data_id}", response_model=ApiResponse[BenchmarkDataResponse])
@require_permission("benchmark:read")
async def get_benchmark_detail(
    data_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    data = db.query(BenchmarkData).filter(
        BenchmarkData.id == data_id,
        BenchmarkData.is_deleted == False,
    ).first()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="基准数据不存在",
        )
    return ApiResponse(data=BenchmarkDataResponse.model_validate(data), message="基准数据详情查询成功")


@router.get("/persistent-anomaly-rooms", response_model=ApiResponse[dict])
@require_permission("benchmark:read")
async def list_persistent_anomaly_rooms(
    consecutive_months: int = Query(3, ge=1, description="连续异常月数"),
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    rooms, total = benchmark_service.get_persistent_anomaly_rooms(
        hospital_id=hospital_id,
        min_consecutive_months=consecutive_months,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [PersistentAnomalyRoomResponse.model_validate(r) for r in rooms],
        total,
        pagination,
    ), message="持续异常机房列表查询成功")


@router.post("/persistent-anomaly-rooms/identify", response_model=ApiResponse[List[PersistentAnomalyRoomResponse]])
@require_permission("benchmark:manage")
async def identify_persistent_anomaly_rooms(
    consecutive_months: int = Query(3, ge=1, description="连续异常月数"),
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    rooms = benchmark_service.identify_persistent_anomaly_rooms(
        consecutive_months=consecutive_months,
        hospital_id=hospital_id,
    )
    return ApiResponse(
        data=[PersistentAnomalyRoomResponse.model_validate(r) for r in rooms],
        message="持续异常机房识别完成"
    )


@router.get("/persistent-anomaly-rooms/{room_id}", response_model=ApiResponse[PersistentAnomalyRoomResponse])
@require_permission("benchmark:read")
async def get_persistent_anomaly_room_detail(
    room_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    room = db.query(PersistentAnomalyRoom).filter(
        PersistentAnomalyRoom.id == room_id,
        PersistentAnomalyRoom.is_deleted == False,
    ).first()
    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="持续异常机房不存在",
        )
    return ApiResponse(data=PersistentAnomalyRoomResponse.model_validate(room), message="持续异常机房详情查询成功")


@router.patch("/persistent-anomaly-rooms/{room_id}/status", response_model=ApiResponse[PersistentAnomalyRoomResponse])
@require_permission("benchmark:manage")
async def update_persistent_anomaly_room_status(
    room_id: int,
    update_data: PersistentAnomalyRoomUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    room = benchmark_service.update_persistent_anomaly_room(
        room_id=room_id,
        update_data=update_data.model_dump(exclude_unset=True),
    )
    return ApiResponse(data=PersistentAnomalyRoomResponse.model_validate(room), message="持续异常机房状态更新成功")


@router.get("/excellent-cases", response_model=ApiResponse[dict])
@require_permission("benchmark:read")
async def list_excellent_cases(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    category: Optional[str] = Query(None, description="分类"),
    is_active: Optional[bool] = Query(None, description="是否激活"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    cases, total = benchmark_service.list_excellent_cases(
        hospital_id=hospital_id,
        category=category,
        is_approved=is_active,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [BestPracticeResponse.model_validate(c) for c in cases],
        total,
        pagination,
    ), message="优秀案例列表查询成功")


@router.post("/excellent-cases", response_model=ApiResponse[BestPracticeResponse])
@require_permission("benchmark:manage")
async def create_excellent_case(
    case_data: BestPracticeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    case = benchmark_service.create_excellent_case(
        case_data=case_data,
        creator_id=current_user.id,
    )
    return ApiResponse(data=BestPracticeResponse.model_validate(case), message="优秀案例创建成功")


@router.get("/excellent-cases/{case_id}", response_model=ApiResponse[BestPracticeResponse])
@require_permission("benchmark:read")
async def get_excellent_case_detail(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    case = benchmark_service.get_excellent_case(case_id)
    return ApiResponse(data=BestPracticeResponse.model_validate(case), message="优秀案例详情查询成功")


@router.put("/excellent-cases/{case_id}", response_model=ApiResponse[BestPracticeResponse])
@require_permission("benchmark:manage")
async def update_excellent_case(
    case_id: int,
    update_data: BestPracticeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    case = benchmark_service.update_excellent_case(
        case_id=case_id,
        update_data=update_data,
        operator_id=current_user.id,
    )
    return ApiResponse(data=BestPracticeResponse.model_validate(case), message="优秀案例更新成功")


@router.patch("/excellent-cases/{case_id}/toggle-active", response_model=ApiResponse[BestPracticeResponse])
@require_permission("benchmark:manage")
async def toggle_excellent_case_active(
    case_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    case = benchmark_service.get_excellent_case(case_id)
    is_approved = case.status == "approved"
    case.status = "draft" if is_approved else "approved"
    if not is_approved:
        case.approved_by = current_user.id
        case.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(case)
    status_text = "激活" if case.status == "approved" else "停用"
    return ApiResponse(data=BestPracticeResponse.model_validate(case), message=f"优秀案例{status_text}成功")


@router.get("/best-practices", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("benchmark:read")
async def get_group_best_practices(
    category: Optional[str] = Query(None, description="分类"),
    top_n: int = Query(10, ge=1, le=50, description="返回前N个最佳实践"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    practices = benchmark_service.get_group_best_practices(
        category=category,
        top_n=top_n,
    )
    return ApiResponse(data=practices, message="集团最佳实践查询成功")


@router.get("/high-frequency-defects", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("benchmark:read")
async def get_high_frequency_defects(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    top_n: int = Query(20, ge=1, le=100, description="返回前N个高频缺陷"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    defects = benchmark_service.get_high_frequency_defects(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
    )
    return ApiResponse(
        data=[{
            "id": d.id,
            "hospital_id": d.hospital_id,
            "defect_type": d.defect_type,
            "defect_category": d.defect_category,
            "defect_code": d.defect_code,
            "defect_name": d.defect_name,
            "occurrence_count": d.occurrence_count,
            "occurrence_rate": d.occurrence_rate,
            "severity_level": d.severity_level,
            "description": d.description,
        } for d in defects],
        message="高频缺陷查询成功"
    )


@router.get("/ranking", response_model=ApiResponse[RankingResponse])
@require_permission("benchmark:read")
async def get_hospital_ranking(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    category: Optional[str] = Query(None, description="分类"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BenchmarkData).filter(BenchmarkData.is_deleted == False)

    if year:
        query = query.filter(BenchmarkData.benchmark_date >= date(year, 1, 1))
        query = query.filter(BenchmarkData.benchmark_date <= date(year, 12, 31))
    if month and year:
        from ..core.utils import get_date_range
        start_date, end_date = get_date_range("month", date(year, month, 1))
        query = query.filter(BenchmarkData.benchmark_date >= start_date)
        query = query.filter(BenchmarkData.benchmark_date <= end_date)
    if category:
        query = query.filter(BenchmarkData.benchmark_type == category)

    benchmarks = query.order_by(BenchmarkData.overall_rank.asc()).all()

    ranking_items = []
    for idx, bm in enumerate(benchmarks, 1):
        ranking_items.append({
            "rank": idx,
            "hospital_id": bm.hospital_id,
            "hospital_name": bm.hospital_name,
            "overall_score": bm.overall_score,
            "position_pass_rate": bm.position_pass_rate,
            "quality_pass_rate": bm.quality_pass_rate,
            "report_standard_rate": bm.report_standard_rate,
            "anomaly_rate": bm.anomaly_rate,
            "composite_rank": bm.overall_rank,
            "performance_level": bm.performance_level,
        })

    period = f"{year}年{month}月" if year and month else (f"{year}年" if year else "全部")
    ranking_type = category if category else "综合排名"

    return ApiResponse(
        data=RankingResponse(
            ranking_type=ranking_type,
            period=period,
            items=ranking_items,
        ),
        message="医院排名查询成功"
    )


@router.get("/comparison", response_model=ApiResponse[BenchmarkComparisonResponse])
@require_permission("benchmark:read")
async def get_hospital_comparison(
    hospital_ids: Optional[List[int]] = Query(None, description="院区ID列表"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    benchmark_service = BenchmarkService(db)
    query = db.query(BenchmarkData).filter(BenchmarkData.is_deleted == False)

    if hospital_ids:
        query = query.filter(BenchmarkData.hospital_id.in_(hospital_ids))
    if year:
        query = query.filter(BenchmarkData.benchmark_date >= date(year, 1, 1))
        query = query.filter(BenchmarkData.benchmark_date <= date(year, 12, 31))
    if month and year:
        from ..core.utils import get_date_range
        start_date, end_date = get_date_range("month", date(year, month, 1))
        query = query.filter(BenchmarkData.benchmark_date >= start_date)
        query = query.filter(BenchmarkData.benchmark_date <= end_date)

    benchmarks = query.order_by(BenchmarkData.overall_rank.asc()).all()
    group_stats = benchmark_service._calculate_group_stats(benchmarks)

    best_performers = []
    areas_for_improvement = []
    if benchmarks:
        best = benchmarks[0]
        best_performers.append({
            "hospital_id": best.hospital_id,
            "hospital_name": best.hospital_name,
            "overall_score": best.overall_score,
            "strengths": best.strengths,
        })
        worst = benchmarks[-1]
        areas_for_improvement.append({
            "hospital_id": worst.hospital_id,
            "hospital_name": worst.hospital_name,
            "overall_score": worst.overall_score,
            "weaknesses": worst.weaknesses,
        })

    period = f"{year}年{month}月" if year and month else (f"{year}年" if year else "全部")
    benchmark_date = date(year, month, 1) if year and month else (date(year, 1, 1) if year else date.today())

    return ApiResponse(
        data=BenchmarkComparisonResponse(
            benchmark_date=benchmark_date,
            period=period,
            total_hospitals=len(benchmarks),
            items=[BenchmarkDataResponse.model_validate(b) for b in benchmarks],
            group_averages=group_stats,
            best_performers=best_performers,
            areas_for_improvement=areas_for_improvement,
        ),
        message="医院对比查询成功"
    )


@router.get("/export")
@require_permission("benchmark:export")
async def export_benchmark_data(
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    export_type: Optional[str] = Query("excel", description="导出格式"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(BenchmarkData).filter(BenchmarkData.is_deleted == False)

    if year:
        query = query.filter(BenchmarkData.benchmark_date >= date(year, 1, 1))
        query = query.filter(BenchmarkData.benchmark_date <= date(year, 12, 31))
    if month and year:
        from ..core.utils import get_date_range
        start_date, end_date = get_date_range("month", date(year, month, 1))
        query = query.filter(BenchmarkData.benchmark_date >= start_date)
        query = query.filter(BenchmarkData.benchmark_date <= end_date)
    if hospital_id:
        query = query.filter(BenchmarkData.hospital_id == hospital_id)

    benchmarks = query.order_by(BenchmarkData.benchmark_date.desc(), BenchmarkData.overall_rank.asc()).all()

    export_data = {
        "export_type": export_type,
        "year": year,
        "month": month,
        "hospital_id": hospital_id,
        "exported_at": datetime.utcnow().isoformat(),
        "exported_by": current_user.username,
        "total_records": len(benchmarks),
        "data": [{
            "hospital_id": b.hospital_id,
            "hospital_name": b.hospital_name,
            "benchmark_period": b.benchmark_period,
            "benchmark_date": b.benchmark_date.isoformat(),
            "benchmark_type": b.benchmark_type,
            "total_examinations": b.total_examinations,
            "position_pass_rate": b.position_pass_rate,
            "position_rank": b.position_rank,
            "quality_pass_rate": b.quality_pass_rate,
            "quality_rank": b.quality_rank,
            "report_standard_rate": b.report_standard_rate,
            "report_rank": b.report_rank,
            "overall_score": b.overall_score,
            "overall_rank": b.overall_rank,
            "anomaly_rate": b.anomaly_rate,
            "performance_level": b.performance_level,
            "strengths": b.strengths,
            "weaknesses": b.weaknesses,
            "improvement_suggestions": b.improvement_suggestions,
        } for b in benchmarks],
    }

    import json
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    buffer = io.BytesIO(json_str.encode("utf-8"))
    buffer.seek(0)

    period_part = f"_{year}{month:02d}" if year and month else (f"_{year}" if year else "")
    hospital_part = f"_hospital{hospital_id}" if hospital_id else ""
    filename = f"benchmark_export{period_part}{hospital_part}.json"

    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
