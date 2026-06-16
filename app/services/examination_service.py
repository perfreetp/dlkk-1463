from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models import Examination, ImageQuality, BIRADSReport, Hospital, Equipment, Room, Technician, Doctor
from ..schemas import (
    ExaminationCreate,
    ExaminationUpdate,
    ImageQualityCreate,
    BIRADSReportCreate,
    ExaminationBatchCreate,
)
from ..core.exceptions import NotFoundError, ValidationError
from ..core.logger import get_logger
from ..core.utils import (
    normalize_birads,
    normalize_density,
    validate_mammo_views,
    calculate_percentage,
)
from .quality_rule_service import QualityRuleService

logger = get_logger(__name__)


class ExaminationService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_service = QualityRuleService(db)

    def create_examination(self, exam_data: ExaminationCreate) -> Examination:
        existing = self.db.query(Examination).filter(
            Examination.accession_number == exam_data.accession_number,
            Examination.is_deleted == False,
        ).first()
        if existing:
            raise ValidationError(f"检查号已存在: {exam_data.accession_number}")

        exam = Examination(
            **exam_data.model_dump(exclude={"image_quality", "birads_report"})
        )
        exam.status = "received"
        self.db.add(exam)
        self.db.flush()

        if exam_data.image_quality:
            iq_data = exam_data.image_quality.model_dump()
            iq_data["examination_id"] = exam.id
            image_quality = ImageQuality(**iq_data)
            self._auto_evaluate_quality(image_quality, exam)
            self.db.add(image_quality)

        if exam_data.birads_report:
            br_data = exam_data.birads_report.model_dump()
            br_data["examination_id"] = exam.id
            birads_report = BIRADSReport(**br_data)
            self._auto_evaluate_report(birads_report, exam)
            self.db.add(birads_report)

        self.db.commit()
        self.db.refresh(exam)
        logger.info(f"Created examination: {exam.accession_number}")
        return exam

    def batch_create(self, batch_data: ExaminationBatchCreate) -> List[Examination]:
        exams = []
        hospital_id = batch_data.hospital_id

        for exam_data in batch_data.examinations:
            if hospital_id and not exam_data.hospital_id:
                exam_data.hospital_id = hospital_id

            existing = self.db.query(Examination).filter(
                Examination.accession_number == exam_data.accession_number,
                Examination.is_deleted == False,
            ).first()
            if existing:
                logger.warning(f"Skipping duplicate examination: {exam_data.accession_number}")
                continue

            try:
                exam = self.create_examination(exam_data)
                exams.append(exam)
            except Exception as e:
                logger.error(f"Failed to create examination {exam_data.accession_number}: {e}")
                continue

        return exams

    def get_examination(self, exam_id: int) -> Examination:
        exam = self.db.query(Examination).filter(
            Examination.id == exam_id,
            Examination.is_deleted == False,
        ).first()
        if not exam:
            raise NotFoundError(f"检查不存在: {exam_id}")
        return exam

    def get_examination_with_details(self, exam_id: int) -> Examination:
        exam = self.db.query(Examination).filter(
            Examination.id == exam_id,
            Examination.is_deleted == False,
        ).first()
        if not exam:
            raise NotFoundError(f"检查不存在: {exam_id}")

        if exam.hospital_id:
            exam.hospital_name = self.db.query(Hospital.name).filter(Hospital.id == exam.hospital_id).scalar()
        if exam.equipment_id:
            exam.equipment_name = self.db.query(Equipment.name).filter(Equipment.id == exam.equipment_id).scalar()
        if exam.technician_id:
            exam.technician_name = self.db.query(Technician.name).filter(Technician.id == exam.technician_id).scalar()
        if exam.doctor_id:
            exam.doctor_name = self.db.query(Doctor.name).filter(Doctor.id == exam.doctor_id).scalar()

        return exam

    def list_examinations(
        self,
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
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Examination], int]:
        query = self.db.query(Examination).filter(Examination.is_deleted == False)

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)
        if equipment_id:
            query = query.filter(Examination.equipment_id == equipment_id)
        if technician_id:
            query = query.filter(Examination.technician_id == technician_id)
        if doctor_id:
            query = query.filter(Examination.doctor_id == doctor_id)
        if start_date:
            query = query.filter(Examination.examination_date >= start_date)
        if end_date:
            query = query.filter(Examination.examination_date <= end_date)
        if status:
            query = query.filter(Examination.status == status)
        if laterality:
            query = query.filter(Examination.laterality == laterality)
        if birads_classification:
            query = query.join(BIRADSReport).filter(
                BIRADSReport.birads_classification == birads_classification
            )
        if has_anomaly is not None:
            from ..models import AnomalyRecord
            subquery = self.db.query(AnomalyRecord.examination_id).filter(
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
            ).distinct()
            if has_anomaly:
                query = query.filter(Examination.id.in_(subquery))
            else:
                query = query.filter(Examination.id.notin_(subquery))

        total = query.count()
        exams = query.order_by(Examination.examination_date.desc(), Examination.created_at.desc()).offset(skip).limit(limit).all()
        return exams, total

    def update_examination(self, exam_id: int, update_data: ExaminationUpdate) -> Examination:
        exam = self.get_examination(exam_id)
        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(exam, key, value)

        self.db.commit()
        self.db.refresh(exam)
        return exam

    def update_image_quality(self, exam_id: int, iq_data: ImageQualityCreate) -> ImageQuality:
        exam = self.get_examination(exam_id)
        iq = self.db.query(ImageQuality).filter(
            ImageQuality.examination_id == exam_id,
            ImageQuality.is_deleted == False,
        ).first()

        iq_dict = iq_data.model_dump()
        iq_dict["examination_id"] = exam_id

        if iq:
            for key, value in iq_dict.items():
                setattr(iq, key, value)
        else:
            iq = ImageQuality(**iq_dict)
            self.db.add(iq)

        self._auto_evaluate_quality(iq, exam)
        self.db.commit()
        self.db.refresh(iq)
        return iq

    def update_birads_report(self, exam_id: int, br_data: BIRADSReportCreate) -> BIRADSReport:
        exam = self.get_examination(exam_id)
        br = self.db.query(BIRADSReport).filter(
            BIRADSReport.examination_id == exam_id,
            BIRADSReport.is_deleted == False,
        ).first()

        br_dict = br_data.model_dump()
        br_dict["examination_id"] = exam_id

        if br:
            for key, value in br_dict.items():
                setattr(br, key, value)
        else:
            br = BIRADSReport(**br_dict)
            self.db.add(br)

        self._auto_evaluate_report(br, exam)
        self.db.commit()
        self.db.refresh(br)
        return br

    def _auto_evaluate_quality(self, iq: ImageQuality, exam: Examination):
        if exam.views and exam.laterality:
            iq.is_position_complete = validate_mammo_views(exam.views, exam.laterality)
            if not iq.is_position_complete:
                iq.position_completeness = False
                required = ["LCC", "RCC", "LMLO", "RMLO"] if exam.laterality.upper() == "BILATERAL" else ["CC", "MLO"]
                actual = [v.strip().upper() for v in (exam.views or "").split(",")]
                missing = [v for v in required if v not in actual]
                iq.missing_views = ",".join(missing)

        scores = [s for s in [iq.contrast_score, iq.noise_score, iq.sharpness_score, iq.compression_score] if s]
        if scores:
            iq.overall_score = round(sum(scores) / len(scores))

        if iq.overall_score is not None:
            if iq.overall_score >= 80:
                iq.is_quality_acceptable = True
                iq.risk_level = "normal"
            elif iq.overall_score >= 60:
                iq.is_quality_acceptable = True
                iq.risk_level = "low"
            elif iq.overall_score >= 40:
                iq.is_quality_acceptable = False
                iq.risk_level = "medium"
            else:
                iq.is_quality_acceptable = False
                iq.risk_level = "high"

        iq.qa_complete = True
        iq.auto_qa_result = "pass" if (iq.is_position_complete and iq.is_quality_acceptable) else "fail"

    def _auto_evaluate_report(self, br: BIRADSReport, exam: Examination):
        if br.breast_density:
            br.breast_density = normalize_density(br.breast_density)
            from ..core.utils import validate_breast_density
            br.density_check_result = "pass" if validate_breast_density(br.breast_density) else "fail"

        if br.birads_classification:
            br.birads_classification = normalize_birads(br.birads_classification)
            from ..core.utils import validate_birads_classification
            br.birads_check_result = "pass" if validate_birads_classification(br.birads_classification) else "fail"

        required_fields = [
            br.birads_classification,
            br.findings_summary,
            br.impression,
        ]
        br.is_report_complete = all(required_fields)

        if br.findings_summary:
            text = br.findings_summary or ""
            quality_score = 50
            if len(text) >= 50:
                quality_score += 10
            if len(text) >= 100:
                quality_score += 10
            if br.mass_present and br.mass_description:
                quality_score += 10
            if br.calcification_present and br.calcification_description:
                quality_score += 10
            if br.architectural_distortion or br.asymmetry or br.focal_asymmetry:
                if any([br.findings_summary and k in text for k in ["扭曲", "不对称", "致密"]]):
                    quality_score += 10
            br.description_quality_score = min(quality_score, 100)

    def get_daily_statistics(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        query = self.db.query(
            Examination.examination_date,
            func.count(Examination.id).label("total"),
        ).filter(
            Examination.is_deleted == False,
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)
        if start_date:
            query = query.filter(Examination.examination_date >= start_date)
        if end_date:
            query = query.filter(Examination.examination_date <= end_date)

        results = query.group_by(Examination.examination_date).order_by(Examination.examination_date).all()

        daily_stats = []
        for stat_date, total in results:
            position_pass = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
                Examination.examination_date == stat_date,
                Examination.hospital_id == hospital_id if hospital_id else True,
                ImageQuality.is_position_complete == True,
                ImageQuality.is_deleted == False,
            ).scalar() or 0

            quality_pass = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
                Examination.examination_date == stat_date,
                Examination.hospital_id == hospital_id if hospital_id else True,
                ImageQuality.is_quality_acceptable == True,
                ImageQuality.is_deleted == False,
            ).scalar() or 0

            daily_stats.append({
                "stat_date": stat_date,
                "total_examinations": total,
                "position_pass_count": position_pass,
                "position_pass_rate": calculate_percentage(position_pass, total),
                "quality_pass_count": quality_pass,
                "quality_pass_rate": calculate_percentage(quality_pass, total),
            })

        return daily_stats

    def get_birads_distribution(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, int]:
        query = self.db.query(
            BIRADSReport.birads_classification,
            func.count(BIRADSReport.id).label("count"),
        ).join(Examination).filter(
            BIRADSReport.is_deleted == False,
            Examination.is_deleted == False,
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)
        if start_date:
            query = query.filter(Examination.examination_date >= start_date)
        if end_date:
            query = query.filter(Examination.examination_date <= end_date)

        results = query.group_by(BIRADSReport.birads_classification).all()
        return {row[0]: row[1] for row in results if row[0]}

    def get_density_distribution(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, int]:
        query = self.db.query(
            BIRADSReport.breast_density,
            func.count(BIRADSReport.id).label("count"),
        ).join(Examination).filter(
            BIRADSReport.is_deleted == False,
            Examination.is_deleted == False,
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)
        if start_date:
            query = query.filter(Examination.examination_date >= start_date)
        if end_date:
            query = query.filter(Examination.examination_date <= end_date)

        results = query.group_by(BIRADSReport.breast_density).all()
        return {row[0]: row[1] for row in results if row[0]}

    def run_auto_qa(self, exam_ids: Optional[List[int]] = None) -> int:
        query = self.db.query(Examination).filter(
            Examination.is_deleted == False,
            Examination.status == "received",
        )

        if exam_ids:
            query = query.filter(Examination.id.in_(exam_ids))

        exams = query.all()
        processed = 0

        for exam in exams:
            try:
                if exam.image_quality:
                    self._auto_evaluate_quality(exam.image_quality, exam)
                if exam.birads_report:
                    self._auto_evaluate_report(exam.birads_report, exam)
                exam.status = "qa_completed"
                processed += 1
            except Exception as e:
                logger.error(f"Auto QA failed for exam {exam.id}: {e}")

        self.db.commit()
        logger.info(f"Auto QA completed for {processed} examinations")
        return processed
