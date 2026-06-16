from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User, MonthlyReport
from ..schemas import (
    MonthlyReportCreate,
    MonthlyReportResponse,
    ApiResponse,
    PaginationParams,
    DateRangeParams,
    ReportExportRequest,
)
from ..services import StatisticsService
from ..core.utils import paginate

router = APIRouter()


@router.get("/comparison/hospital", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_comparison_by_hospital(
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_comparison_by_hospital(
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=results, message="院区对比统计查询成功")


@router.get("/comparison/equipment", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_comparison_by_equipment(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_comparison_by_equipment(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=results, message="设备对比统计查询成功")


@router.get("/comparison/technician", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_comparison_by_technician(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_comparison_by_technician(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=results, message="技师对比统计查询成功")


@router.get("/comparison/doctor", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_comparison_by_doctor(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_comparison_by_doctor(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=results, message="医生对比统计查询成功")


@router.get("/trend", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_trend_data(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    period: Optional[str] = Query("month", description="统计周期: day/week/month/quarter/year"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    months: Optional[int] = Query(6, description="统计月数"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_trend_data(
        hospital_id=hospital_id,
        months=months,
    )
    return ApiResponse(data=results, message="趋势数据查询成功")


@router.get("/monthly-reports", response_model=ApiResponse[Dict[str, Any]])
@require_permission("statistics:read")
async def list_monthly_reports(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    year: Optional[int] = Query(None, description="年份"),
    month: Optional[int] = Query(None, description="月份"),
    status: Optional[str] = Query(None, description="状态"),
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    reports, total = stats_service.get_monthly_reports(
        hospital_id=hospital_id,
        report_year=year,
        report_month=month,
        status=status,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [MonthlyReportResponse.model_validate(r) for r in reports],
        total,
        pagination,
    ), message="月度报告列表查询成功")


@router.post("/monthly-reports", response_model=ApiResponse[MonthlyReportResponse])
@require_permission("statistics:manage")
async def generate_monthly_report(
    report_data: MonthlyReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    report = stats_service.generate_monthly_report(
        report_data=report_data,
        creator_id=current_user.id,
    )
    return ApiResponse(data=MonthlyReportResponse.model_validate(report), message="月度报告生成成功")


@router.get("/monthly-reports/{report_id}", response_model=ApiResponse[MonthlyReportResponse])
@require_permission("statistics:read")
async def get_monthly_report_detail(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    report = stats_service.db.query(MonthlyReport).filter(
        MonthlyReport.id == report_id,
        MonthlyReport.is_deleted == False,
    ).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="月度报告不存在",
        )
    return ApiResponse(data=MonthlyReportResponse.model_validate(report), message="月度报告详情查询成功")


@router.get("/monthly-reports/{report_id}/download")
@require_permission("statistics:read")
async def download_monthly_report(
    report_id: int,
    format: Optional[str] = Query("excel", description="导出格式: excel/pdf"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    export_data = stats_service.export_report_data(report_id)
    
    import json
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    buffer = io.BytesIO(json_str.encode("utf-8"))
    buffer.seek(0)
    
    filename = f"monthly_report_{report_id}.json"
    
    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/high-frequency-defects", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_high_frequency_defects(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    top_n: int = Query(20, description="返回前N个高频缺陷"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_high_frequency_defects(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
        top_n=top_n,
    )
    return ApiResponse(data=results, message="高频缺陷统计查询成功")


@router.get("/overview", response_model=ApiResponse[Dict[str, Any]])
@require_permission("statistics:read")
async def get_statistics_overview(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    if hospital_id:
        if not start_date:
            start_date = date.today()
        if not end_date:
            end_date = date.today()
        stats = stats_service._get_hospital_statistics(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        )
    else:
        if not start_date:
            from datetime import timedelta
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        stats = stats_service._get_group_stats(
            start_date=start_date,
            end_date=end_date,
        )
    return ApiResponse(data=stats, message="统计概览查询成功")


@router.get("/qa-summary", response_model=ApiResponse[Dict[str, Any]])
@require_permission("statistics:read")
async def get_qa_summary(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    if hospital_id:
        if not start_date:
            from datetime import timedelta
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        hospital_stats = stats_service._get_hospital_statistics(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        )
        qa_summary = {
            "total_examinations": hospital_stats.get("total_examinations", 0),
            "position_pass_rate": hospital_stats.get("position_complete_rate", 0),
            "quality_pass_rate": hospital_stats.get("quality_pass_rate", 0),
            "report_standard_rate": hospital_stats.get("report_standard_rate", 0),
            "anomaly_rate": hospital_stats.get("anomaly_rate", 0),
            "average_quality_score": hospital_stats.get("average_quality_score", 0),
            "average_description_score": hospital_stats.get("average_description_score", 0),
            "review_task_count": hospital_stats.get("review_tasks", 0),
            "task_completion_rate": hospital_stats.get("task_completion_rate", 0),
            "rectification_count": hospital_stats.get("rectifications", 0),
            "rectification_pass_rate": hospital_stats.get("rectification_pass_rate", 0),
        }
    else:
        if not start_date:
            from datetime import timedelta
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()
        group_stats = stats_service._get_group_stats(
            start_date=start_date,
            end_date=end_date,
        )
        qa_summary = {
            "total_examinations": group_stats.get("total_examinations", 0),
            "position_pass_rate": group_stats.get("position_complete_rate", 0),
            "quality_pass_rate": group_stats.get("quality_pass_rate", 0),
            "report_standard_rate": group_stats.get("report_standard_rate", 0),
            "anomaly_rate": group_stats.get("anomaly_rate", 0),
            "correction_rate": group_stats.get("correction_rate", 0),
        }
    return ApiResponse(data=qa_summary, message="质控汇总查询成功")


@router.get("/birads-summary", response_model=ApiResponse[Dict[str, Any]])
@require_permission("statistics:read")
async def get_birads_summary(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    if not start_date:
        from datetime import timedelta
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    birads_dist = stats_service._get_birads_distribution(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    density_dist = stats_service._get_density_distribution(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    
    summary = {
        "birads_distribution": birads_dist,
        "density_distribution": density_dist,
        "start_date": start_date,
        "end_date": end_date,
    }
    return ApiResponse(data=summary, message="BI-RADS汇总查询成功")


@router.get("/equipment-performance", response_model=ApiResponse[List[Dict[str, Any]]])
@require_permission("statistics:read")
async def get_equipment_performance(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    results = stats_service.get_comparison_by_equipment(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    return ApiResponse(data=results, message="设备性能统计查询成功")


@router.get("/personnel-performance", response_model=ApiResponse[Dict[str, Any]])
@require_permission("statistics:read")
async def get_personnel_performance(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    technician_stats = stats_service.get_comparison_by_technician(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    doctor_stats = stats_service.get_comparison_by_doctor(
        hospital_id=hospital_id,
        start_date=start_date,
        end_date=end_date,
    )
    performance_data = {
        "technicians": technician_stats,
        "doctors": doctor_stats,
    }
    return ApiResponse(data=performance_data, message="人员绩效统计查询成功")


@router.get("/export")
@require_permission("statistics:export")
async def export_statistics_data(
    hospital_id: Optional[int] = Query(None, description="院区ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    export_type: Optional[str] = Query("excel", description="导出格式"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stats_service = StatisticsService(db)
    if not start_date:
        from datetime import timedelta
        start_date = date.today() - timedelta(days=30)
    if not end_date:
        end_date = date.today()
    
    export_data = {
        "export_type": export_type,
        "hospital_id": hospital_id,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "exported_at": date.today().isoformat(),
        "exported_by": current_user.username,
        "hospital_comparison": stats_service.get_comparison_by_hospital(
            start_date=start_date,
            end_date=end_date,
        ),
        "equipment_comparison": stats_service.get_comparison_by_equipment(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "technician_comparison": stats_service.get_comparison_by_technician(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "doctor_comparison": stats_service.get_comparison_by_doctor(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "high_frequency_defects": stats_service.get_high_frequency_defects(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        ),
        "trend_data": stats_service.get_trend_data(
            hospital_id=hospital_id,
            months=6,
        ),
    }
    
    import json
    json_str = json.dumps(export_data, ensure_ascii=False, indent=2)
    buffer = io.BytesIO(json_str.encode("utf-8"))
    buffer.seek(0)
    
    filename = f"statistics_export_{date.today().isoformat()}.json"
    
    return StreamingResponse(
        buffer,
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
