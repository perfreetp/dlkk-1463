from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..core.deps import get_current_user, require_permission
from ..models import User
from ..schemas import (
    ExaminationCreate,
    ExaminationUpdate,
    ExaminationResponse,
    ImageQualityCreate,
    ImageQualityResponse,
    BIRADSReportCreate,
    BIRADSReportResponse,
    ExaminationBatchCreate,
    ApiResponse,
    PaginationParams,
    DateRangeParams,
)
from ..services import ExaminationService
from ..core.utils import paginate

router = APIRouter()


@router.post("", response_model=ApiResponse[ExaminationResponse])
@require_permission("examination:create")
async def create_examination(
    exam_data: ExaminationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    exam = exam_service.create_examination(exam_data)
    return ApiResponse(data=ExaminationResponse.model_validate(exam), message="检查数据创建成功")


@router.post("/batch", response_model=ApiResponse[List[ExaminationResponse]])
@require_permission("examination:create")
async def batch_create_examinations(
    batch_data: ExaminationBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    exams = exam_service.batch_create(batch_data)
    return ApiResponse(
        data=[ExaminationResponse.model_validate(e) for e in exams],
        message=f"成功导入 {len(exams)} 条检查数据",
    )


@router.get("", response_model=ApiResponse[dict])
@require_permission("examination:read")
async def list_examinations(
    hospital_id: Optional[int] = None,
    equipment_id: Optional[int] = None,
    technician_id: Optional[int] = None,
    doctor_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    status: Optional[str] = None,
    laterality: Optional[str] = None,
    birads_classification: Optional[str] = None,
    has_anomaly: Optional[bool] = None,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    exams, total = exam_service.list_examinations(
        hospital_id=hospital_id,
        equipment_id=equipment_id,
        technician_id=technician_id,
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date,
        status=status,
        laterality=laterality,
        birads_classification=birads_classification,
        has_anomaly=has_anomaly,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return ApiResponse(data=paginate(
        [ExaminationResponse.model_validate(e) for e in exams],
        total,
        pagination,
    ))


@router.get("/statistics/daily", response_model=ApiResponse[List[dict]])
@require_permission("examination:read")
async def get_daily_statistics(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    stats = exam_service.get_daily_statistics(hospital_id, start_date, end_date)
    return ApiResponse(data=stats)


@router.get("/statistics/birads-distribution", response_model=ApiResponse[dict])
@require_permission("examination:read")
async def get_birads_distribution(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    distribution = exam_service.get_birads_distribution(hospital_id, start_date, end_date)
    return ApiResponse(data=distribution)


@router.get("/statistics/density-distribution", response_model=ApiResponse[dict])
@require_permission("examination:read")
async def get_density_distribution(
    hospital_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    distribution = exam_service.get_density_distribution(hospital_id, start_date, end_date)
    return ApiResponse(data=distribution)


@router.post("/run-auto-qa", response_model=ApiResponse[dict])
@require_permission("examination:manage")
async def run_auto_qa(
    exam_ids: Optional[List[int]] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    processed = exam_service.run_auto_qa(exam_ids)
    return ApiResponse(data={"processed_count": processed}, message=f"完成 {processed} 条检查的自动质控")


@router.get("/{exam_id}", response_model=ApiResponse[ExaminationResponse])
@require_permission("examination:read")
async def get_examination(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    exam = exam_service.get_examination_with_details(exam_id)
    return ApiResponse(data=ExaminationResponse.model_validate(exam))


@router.put("/{exam_id}", response_model=ApiResponse[ExaminationResponse])
@require_permission("examination:update")
async def update_examination(
    exam_id: int,
    update_data: ExaminationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    exam = exam_service.update_examination(exam_id, update_data)
    return ApiResponse(data=ExaminationResponse.model_validate(exam), message="检查信息更新成功")


@router.post("/{exam_id}/image-quality", response_model=ApiResponse[ImageQualityResponse])
@require_permission("examination:update")
async def update_image_quality(
    exam_id: int,
    iq_data: ImageQualityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    iq = exam_service.update_image_quality(exam_id, iq_data)
    return ApiResponse(data=ImageQualityResponse.model_validate(iq), message="图像质量信息更新成功")


@router.post("/{exam_id}/birads-report", response_model=ApiResponse[BIRADSReportResponse])
@require_permission("examination:update")
async def update_birads_report(
    exam_id: int,
    br_data: BIRADSReportCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    exam_service = ExaminationService(db)
    br = exam_service.update_birads_report(exam_id, br_data)
    return ApiResponse(data=BIRADSReportResponse.model_validate(br), message="BI-RADS报告信息更新成功")
