from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case

from ..models import (
    Examination,
    ImageQuality,
    BIRADSReport,
    AnomalyRecord,
    ReviewTask,
    Rectification,
    Hospital,
    Equipment,
    Room,
    Technician,
    Doctor,
    MonthlyReport,
    HighFrequencyDefect,
)
from ..schemas import (
    MonthlyReportCreate,
    StatisticsQuery,
    HospitalComparisonResponse,
    EquipmentComparisonResponse,
    TechnicianComparisonResponse,
    DoctorComparisonResponse,
    MultidimensionalComparisonResponse,
    MonthlyReportResponse,
)
from ..core.exceptions import NotFoundError, BusinessError
from ..core.logger import get_logger
from ..core.utils import calculate_percentage, get_date_range, safe_divide, get_month_range

logger = get_logger(__name__)


class StatisticsService:
    def __init__(self, db: Session):
        self.db = db

    def get_comparison_by_hospital(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[HospitalComparisonResponse]:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        hospitals = self.db.query(Hospital).filter(
            Hospital.is_deleted == False,
            Hospital.is_active == True,
        ).all()

        results = []
        for hospital in hospitals:
            stats = self._get_hospital_statistics(hospital.id, start_date, end_date)
            results.append(HospitalComparisonResponse(
                hospital_id=hospital.id,
                hospital_name=hospital.name,
                hospital_level=hospital.level,
                **stats,
            ))

        return results

    def _get_hospital_statistics(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        query = self.db.query(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.is_deleted == False,
        )

        total_examinations = query.count()

        position_complete = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_position_complete == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        quality_pass = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_quality_acceptable == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        report_standard = self.db.query(func.count(BIRADSReport.id)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.birads_check_result == "pass",
            BIRADSReport.density_check_result == "pass",
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        anomaly_query = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.hospital_id == hospital_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        )
        total_anomalies = anomaly_query.count()
        position_anomalies = anomaly_query.filter(AnomalyRecord.anomaly_type == "position").count()
        quality_anomalies = anomaly_query.filter(AnomalyRecord.anomaly_type == "quality").count()
        report_anomalies = anomaly_query.filter(AnomalyRecord.anomaly_type == "report").count()
        similarity_anomalies = anomaly_query.filter(AnomalyRecord.anomaly_type == "similarity").count()

        high_severity = anomaly_query.filter(AnomalyRecord.severity_level == "high").count()
        critical_severity = anomaly_query.filter(AnomalyRecord.severity_level == "critical").count()

        confirmed_anomalies = anomaly_query.filter(AnomalyRecord.is_confirmed == True).count()
        corrected_anomalies = anomaly_query.filter(AnomalyRecord.correction_status == "corrected").count()

        review_tasks = self.db.query(func.count(ReviewTask.id)).filter(
            ReviewTask.hospital_id == hospital_id,
            ReviewTask.created_at >= start_date,
            ReviewTask.created_at <= end_date,
            ReviewTask.is_deleted == False,
        ).scalar() or 0

        completed_tasks = self.db.query(func.count(ReviewTask.id)).filter(
            ReviewTask.hospital_id == hospital_id,
            ReviewTask.status.in_(["completed", "verified"]),
            ReviewTask.completed_at >= start_date,
            ReviewTask.completed_at <= end_date,
            ReviewTask.is_deleted == False,
        ).scalar() or 0

        rectifications = self.db.query(func.count(Rectification.id)).filter(
            Rectification.hospital_id == hospital_id,
            Rectification.created_at >= start_date,
            Rectification.created_at <= end_date,
            Rectification.is_deleted == False,
        ).scalar() or 0

        rectification_pass = self.db.query(func.count(Rectification.id)).filter(
            Rectification.hospital_id == hospital_id,
            Rectification.status == "verified",
            Rectification.verification_passed == True,
            Rectification.completed_at >= start_date,
            Rectification.completed_at <= end_date,
            Rectification.is_deleted == False,
        ).scalar() or 0

        avg_quality_score = self.db.query(func.avg(ImageQuality.overall_score)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.overall_score.isnot(None),
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        avg_description_score = self.db.query(func.avg(BIRADSReport.description_quality_score)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.description_quality_score.isnot(None),
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        return {
            "total_examinations": total_examinations,
            "position_complete_count": position_complete,
            "position_complete_rate": calculate_percentage(position_complete, total_examinations),
            "quality_pass_count": quality_pass,
            "quality_pass_rate": calculate_percentage(quality_pass, total_examinations),
            "report_standard_count": report_standard,
            "report_standard_rate": calculate_percentage(report_standard, total_examinations),
            "total_anomalies": total_anomalies,
            "position_anomalies": position_anomalies,
            "quality_anomalies": quality_anomalies,
            "report_anomalies": report_anomalies,
            "similarity_anomalies": similarity_anomalies,
            "high_severity_count": high_severity,
            "critical_severity_count": critical_severity,
            "anomaly_rate": calculate_percentage(total_anomalies, total_examinations),
            "confirmed_anomalies": confirmed_anomalies,
            "corrected_anomalies": corrected_anomalies,
            "correction_rate": calculate_percentage(corrected_anomalies, confirmed_anomalies),
            "review_tasks": review_tasks,
            "completed_tasks": completed_tasks,
            "task_completion_rate": calculate_percentage(completed_tasks, review_tasks),
            "rectifications": rectifications,
            "rectification_pass": rectification_pass,
            "rectification_pass_rate": calculate_percentage(rectification_pass, rectifications),
            "average_quality_score": round(avg_quality_score, 2) if avg_quality_score else 0,
            "average_description_score": round(avg_description_score, 2) if avg_description_score else 0,
            "anomaly_density": safe_divide(total_anomalies, total_examinations) * 100 if total_examinations else 0,
        }

    def get_comparison_by_equipment(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[EquipmentComparisonResponse]:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        query = self.db.query(Equipment).filter(
            Equipment.is_deleted == False,
            Equipment.is_active == True,
        )

        if hospital_id:
            query = query.filter(Equipment.hospital_id == hospital_id)

        equipments = query.all()

        results = []
        for equipment in equipments:
            stats = self._get_equipment_statistics(equipment.id, start_date, end_date)
            hospital = self.db.query(Hospital).filter(Hospital.id == equipment.hospital_id).first()

            results.append(EquipmentComparisonResponse(
                equipment_id=equipment.id,
                equipment_name=equipment.name,
                brand=equipment.brand,
                model=equipment.model,
                serial_number=equipment.serial_number,
                hospital_id=equipment.hospital_id,
                hospital_name=hospital.name if hospital else "",
                room_id=equipment.room_id,
                room_name=equipment.room_name,
                installation_date=equipment.installation_date,
                **stats,
            ))

        return results

    def _get_equipment_statistics(
        self,
        equipment_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        query = self.db.query(Examination).filter(
            Examination.equipment_id == equipment_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.is_deleted == False,
        )

        total = query.count()

        position_complete = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.equipment_id == equipment_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_position_complete == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        quality_pass = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.equipment_id == equipment_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_quality_acceptable == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        anomalies = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.equipment_id == equipment_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 0

        avg_score = self.db.query(func.avg(ImageQuality.overall_score)).join(Examination).filter(
            Examination.equipment_id == equipment_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.overall_score.isnot(None),
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        avg_dose = self.db.query(func.avg(Examination.average_glandular_dose)).filter(
            Examination.equipment_id == equipment_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.average_glandular_dose.isnot(None),
            Examination.is_deleted == False,
        ).scalar() or 0

        return {
            "total_examinations": total,
            "position_complete_rate": calculate_percentage(position_complete, total),
            "quality_pass_rate": calculate_percentage(quality_pass, total),
            "anomaly_count": anomalies,
            "anomaly_rate": calculate_percentage(anomalies, total),
            "average_quality_score": round(avg_score, 2) if avg_score else 0,
            "average_dose": round(avg_dose, 3) if avg_dose else 0,
        }

    def get_comparison_by_technician(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[TechnicianComparisonResponse]:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        query = self.db.query(Technician).filter(
            Technician.is_deleted == False,
            Technician.is_active == True,
        )

        if hospital_id:
            query = query.filter(Technician.hospital_id == hospital_id)

        technicians = query.all()

        results = []
        for tech in technicians:
            stats = self._get_technician_statistics(tech.id, start_date, end_date)
            hospital = self.db.query(Hospital).filter(Hospital.id == tech.hospital_id).first()

            results.append(TechnicianComparisonResponse(
                technician_id=tech.id,
                technician_name=tech.name,
                employee_id=tech.employee_id,
                title=tech.title,
                hospital_id=tech.hospital_id,
                hospital_name=hospital.name if hospital else "",
                **stats,
            ))

        return results

    def _get_technician_statistics(
        self,
        technician_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        query = self.db.query(Examination).filter(
            Examination.technician_id == technician_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.is_deleted == False,
        )

        total = query.count()

        position_complete = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.technician_id == technician_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_position_complete == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        quality_pass = self.db.query(func.count(ImageQuality.id)).join(Examination).filter(
            Examination.technician_id == technician_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.is_quality_acceptable == True,
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        anomalies = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.technician_id == technician_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 0

        quality_anomalies = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.technician_id == technician_id,
            AnomalyRecord.anomaly_type.in_(["position", "quality"]),
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 0

        avg_score = self.db.query(func.avg(ImageQuality.overall_score)).join(Examination).filter(
            Examination.technician_id == technician_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.overall_score.isnot(None),
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        return {
            "total_examinations": total,
            "position_complete_rate": calculate_percentage(position_complete, total),
            "quality_pass_rate": calculate_percentage(quality_pass, total),
            "anomaly_count": anomalies,
            "anomaly_rate": calculate_percentage(anomalies, total),
            "quality_anomaly_count": quality_anomalies,
            "quality_anomaly_rate": calculate_percentage(quality_anomalies, total),
            "average_quality_score": round(avg_score, 2) if avg_score else 0,
        }

    def get_comparison_by_doctor(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[DoctorComparisonResponse]:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        query = self.db.query(Doctor).filter(
            Doctor.is_deleted == False,
            Doctor.is_active == True,
        )

        if hospital_id:
            query = query.filter(Doctor.hospital_id == hospital_id)

        doctors = query.all()

        results = []
        for doctor in doctors:
            stats = self._get_doctor_statistics(doctor.id, start_date, end_date)
            hospital = self.db.query(Hospital).filter(Hospital.id == doctor.hospital_id).first()

            results.append(DoctorComparisonResponse(
                doctor_id=doctor.id,
                doctor_name=doctor.name,
                employee_id=doctor.employee_id,
                title=doctor.title,
                department=doctor.department,
                hospital_id=doctor.hospital_id,
                hospital_name=hospital.name if hospital else "",
                **stats,
            ))

        return results

    def _get_doctor_statistics(
        self,
        doctor_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, Any]:
        query = self.db.query(Examination).filter(
            Examination.doctor_id == doctor_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.is_deleted == False,
        )

        total = query.count()

        report_standard = self.db.query(func.count(BIRADSReport.id)).join(Examination).filter(
            Examination.doctor_id == doctor_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.birads_check_result == "pass",
            BIRADSReport.density_check_result == "pass",
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        report_complete = self.db.query(func.count(BIRADSReport.id)).join(Examination).filter(
            Examination.doctor_id == doctor_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.is_report_complete == True,
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        anomalies = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.doctor_id == doctor_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 0

        report_anomalies = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.doctor_id == doctor_id,
            AnomalyRecord.anomaly_type.in_(["report", "similarity"]),
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 0

        avg_description_score = self.db.query(func.avg(BIRADSReport.description_quality_score)).join(Examination).filter(
            Examination.doctor_id == doctor_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.description_quality_score.isnot(None),
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        birads_dist = self.db.query(
            BIRADSReport.birads_classification,
            func.count(BIRADSReport.id),
        ).join(Examination).filter(
            Examination.doctor_id == doctor_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.is_deleted == False,
        ).group_by(BIRADSReport.birads_classification).all()

        birads_distribution = {row[0]: row[1] for row in birads_dist if row[0]}

        return {
            "total_reports": total,
            "report_standard_rate": calculate_percentage(report_standard, total),
            "report_complete_rate": calculate_percentage(report_complete, total),
            "anomaly_count": anomalies,
            "anomaly_rate": calculate_percentage(anomalies, total),
            "report_anomaly_count": report_anomalies,
            "report_anomaly_rate": calculate_percentage(report_anomalies, total),
            "average_description_score": round(avg_description_score, 2) if avg_description_score else 0,
            "birads_distribution": birads_distribution,
        }

    def get_multidimensional_comparison(
        self,
        query_params: StatisticsQuery,
    ) -> MultidimensionalComparisonResponse:
        hospital_stats = self.get_comparison_by_hospital(
            query_params.start_date,
            query_params.end_date,
        )

        equipment_stats = self.get_comparison_by_equipment(
            query_params.hospital_id,
            query_params.start_date,
            query_params.end_date,
        )

        technician_stats = self.get_comparison_by_technician(
            query_params.hospital_id,
            query_params.start_date,
            query_params.end_date,
        )

        doctor_stats = self.get_comparison_by_doctor(
            query_params.hospital_id,
            query_params.start_date,
            query_params.end_date,
        )

        return MultidimensionalComparisonResponse(
            start_date=query_params.start_date,
            end_date=query_params.end_date,
            hospitals=hospital_stats,
            equipments=equipment_stats,
            technicians=technician_stats,
            doctors=doctor_stats,
        )

    def generate_monthly_report(
        self,
        report_data: MonthlyReportCreate,
        creator_id: Optional[int] = None,
    ) -> MonthlyReport:
        existing = self.db.query(MonthlyReport).filter(
            MonthlyReport.hospital_id == report_data.hospital_id,
            MonthlyReport.report_year == report_data.report_year,
            MonthlyReport.report_month == report_data.report_month,
            MonthlyReport.is_deleted == False,
        ).first()

        if existing:
            raise BusinessError("该月报告已存在")

        start_date, end_date = get_month_range(report_data.report_year, report_data.report_month)

        hospital = self.db.query(Hospital).filter(
            Hospital.id == report_data.hospital_id,
            Hospital.is_deleted == False,
        ).first()

        if not hospital:
            raise NotFoundError(f"院区不存在: {report_data.hospital_id}")

        stats = self._get_hospital_statistics(report_data.hospital_id, start_date, end_date)

        report = MonthlyReport(**report_data.model_dump())
        report.hospital_name = hospital.name
        report.report_period = f"{report_data.report_year}年{report_data.report_month}月"
        report.report_type = "screening"
        report.data_start_date = start_date
        report.data_end_date = end_date
        report.generated_by = creator_id
        report.generated_at = datetime.utcnow()
        report.status = "draft"

        report.total_examinations = stats["total_examinations"]
        report.position_complete_rate = stats["position_complete_rate"]
        report.quality_pass_rate = stats["quality_pass_rate"]
        report.report_standard_rate = stats["report_standard_rate"]
        report.anomaly_count = stats["total_anomalies"]
        report.anomaly_rate = stats["anomaly_rate"]
        report.high_severity_count = stats["high_severity_count"]
        report.critical_severity_count = stats["critical_severity_count"]
        report.correction_rate = stats["correction_rate"]
        report.task_completion_rate = stats["task_completion_rate"]
        report.rectification_pass_rate = stats["rectification_pass_rate"]
        report.average_quality_score = stats["average_quality_score"]
        report.average_description_score = stats["average_description_score"]

        defect_stats = self._get_high_frequency_defects(report_data.hospital_id, start_date, end_date)
        report.high_frequency_defects = [d["defect_code"] for d in defect_stats[:10]]
        report.defect_statistics = defect_stats

        report.statistical_data = {
            "by_anomaly_type": {
                "position": stats["position_anomalies"],
                "quality": stats["quality_anomalies"],
                "report": stats["report_anomalies"],
                "similarity": stats["similarity_anomalies"],
            },
            "by_severity": {
                "low": stats["total_anomalies"] - stats["high_severity_count"] - stats["critical_severity_count"],
                "medium": 0,
                "high": stats["high_severity_count"],
                "critical": stats["critical_severity_count"],
            },
            "by_birads": self._get_birads_distribution(report_data.hospital_id, start_date, end_date),
            "by_density": self._get_density_distribution(report_data.hospital_id, start_date, end_date),
        }

        report.summary = self._generate_report_summary(stats, hospital.name)
        report.recommendations = self._generate_recommendations(stats, defect_stats)

        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        logger.info(f"Generated monthly report {report.id} for {hospital.name} {report.report_period}")
        return report

    def _get_high_frequency_defects(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date,
    ) -> List[Dict[str, Any]]:
        results = self.db.query(
            AnomalyRecord.anomaly_type,
            AnomalyRecord.anomaly_category,
            func.count(AnomalyRecord.id).label("count"),
        ).filter(
            AnomalyRecord.hospital_id == hospital_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).group_by(
            AnomalyRecord.anomaly_type,
            AnomalyRecord.anomaly_category,
        ).order_by(func.count(AnomalyRecord.id).desc()).all()

        total = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.hospital_id == hospital_id,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 1

        defect_list = []
        for anomaly_type, category, count in results:
            code = f"{anomaly_type}_{category or 'other'}"
            defect_list.append({
                "defect_code": code,
                "defect_name": self._get_defect_name(anomaly_type, category),
                "count": count,
                "percentage": calculate_percentage(count, total),
                "anomaly_type": anomaly_type,
                "category": category,
            })

        return defect_list

    def _get_defect_name(self, anomaly_type: str, category: Optional[str]) -> str:
        name_map = {
            ("position", "incomplete"): "体位不完整",
            ("quality", "low_quality"): "图像质量不合格",
            ("quality", "dose_issue"): "剂量异常",
            ("report", "non_standard"): "报告不规范",
            ("report", "incomplete"): "报告不完整",
            ("similarity", "description_inconsistency"): "征象描述不一致",
        }
        return name_map.get((anomaly_type, category), f"{anomaly_type}_{category}")

    def _get_birads_distribution(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, int]:
        results = self.db.query(
            BIRADSReport.birads_classification,
            func.count(BIRADSReport.id),
        ).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.is_deleted == False,
        ).group_by(BIRADSReport.birads_classification).all()
        return {row[0]: row[1] for row in results if row[0]}

    def _get_density_distribution(
        self,
        hospital_id: int,
        start_date: date,
        end_date: date,
    ) -> Dict[str, int]:
        results = self.db.query(
            BIRADSReport.breast_density,
            func.count(BIRADSReport.id),
        ).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.is_deleted == False,
        ).group_by(BIRADSReport.breast_density).all()
        return {row[0]: row[1] for row in results if row[0]}

    def _generate_report_summary(self, stats: Dict[str, Any], hospital_name: str) -> str:
        parts = [
            f"本月{hospital_name}共完成乳腺DR检查{stats['total_examinations']}例，",
            f"体位完整率{stats['position_complete_rate']}%，",
            f"图像质量合格率{stats['quality_pass_rate']}%，",
            f"报告规范率{stats['report_standard_rate']}%。",
            f"共检测异常{stats['total_anomalies']}例，异常率{stats['anomaly_rate']}%，",
            f"其中高危{stats['high_severity_count']}例，危重{stats['critical_severity_count']}例。",
            f"复核任务完成率{stats['task_completion_rate']}%，整改通过率{stats['rectification_pass_rate']}%。",
        ]
        return "".join(parts)

    def _generate_recommendations(self, stats: Dict[str, Any], defects: List[Dict[str, Any]]) -> List[str]:
        recommendations = []

        if stats["position_complete_rate"] < 95:
            recommendations.append("建议加强投照技师体位培训，确保体位完整率达到95%以上。")

        if stats["quality_pass_rate"] < 90:
            recommendations.append("建议检查设备状态，优化投照参数，提升图像质量。")

        if stats["report_standard_rate"] < 95:
            recommendations.append("建议加强报告医生BI-RADS分类培训，统一报告标准。")

        if stats["anomaly_rate"] > 20:
            recommendations.append("建议开展专项质控活动，降低异常发生率。")

        if stats["task_completion_rate"] < 85:
            recommendations.append("建议优化复核流程，加强任务督办，提高完成率。")

        if stats["rectification_pass_rate"] < 80:
            recommendations.append("建议加强整改过程指导，提高整改质量。")

        if defects and defects[0]["percentage"] > 30:
            recommendations.append(f"高频缺陷'{defects[0]['defect_name']}'占比{defects[0]['percentage']}%，建议重点关注。")

        return recommendations

    def get_monthly_reports(
        self,
        hospital_id: Optional[int] = None,
        report_year: Optional[int] = None,
        report_month: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[MonthlyReport], int]:
        query = self.db.query(MonthlyReport).filter(MonthlyReport.is_deleted == False)

        if hospital_id:
            query = query.filter(MonthlyReport.hospital_id == hospital_id)
        if report_year:
            query = query.filter(MonthlyReport.report_year == report_year)
        if report_month:
            query = query.filter(MonthlyReport.report_month == report_month)
        if status:
            query = query.filter(MonthlyReport.status == status)

        total = query.count()
        reports = query.order_by(
            MonthlyReport.report_year.desc(),
            MonthlyReport.report_month.desc(),
            MonthlyReport.created_at.desc(),
        ).offset(skip).limit(limit).all()

        return reports, total

    def get_high_frequency_defects(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        query = self.db.query(
            AnomalyRecord.anomaly_type,
            AnomalyRecord.anomaly_category,
            func.count(AnomalyRecord.id).label("count"),
        ).filter(
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        )

        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)

        results = query.group_by(
            AnomalyRecord.anomaly_type,
            AnomalyRecord.anomaly_category,
        ).order_by(func.count(AnomalyRecord.id).desc()).limit(top_n).all()

        total = self.db.query(func.count(AnomalyRecord.id)).filter(
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        ).scalar() or 1

        if hospital_id:
            total = self.db.query(func.count(AnomalyRecord.id)).filter(
                AnomalyRecord.hospital_id == hospital_id,
                AnomalyRecord.detected_at >= start_date,
                AnomalyRecord.detected_at <= end_date,
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
            ).scalar() or 1

        defect_list = []
        for anomaly_type, category, count in results:
            defect_list.append({
                "defect_code": f"{anomaly_type}_{category or 'other'}",
                "defect_name": self._get_defect_name(anomaly_type, category),
                "count": count,
                "percentage": calculate_percentage(count, total),
                "anomaly_type": anomaly_type,
                "category": category,
            })

        return defect_list

    def get_trend_data(
        self,
        hospital_id: Optional[int] = None,
        months: int = 6,
    ) -> List[Dict[str, Any]]:
        trend_data = []
        today = date.today()

        for i in range(months - 1, -1, -1):
            year = today.year - ((today.month - 1 - i) // 12)
            month = (today.month - 1 - i) % 12 + 1
            start_date, end_date = get_month_range(year, month)

            stats = self._get_hospital_statistics(hospital_id, start_date, end_date) if hospital_id else self._get_group_stats(start_date, end_date)

            trend_data.append({
                "year": year,
                "month": month,
                "period": f"{year}年{month}月",
                **stats,
            })

        return trend_data

    def _get_group_stats(self, start_date: date, end_date: date) -> Dict[str, Any]:
        hospitals = self.db.query(Hospital).filter(
            Hospital.is_deleted == False,
            Hospital.is_active == True,
        ).all()

        all_stats = []
        for hospital in hospitals:
            stat = self._get_hospital_statistics(hospital.id, start_date, end_date)
            all_stats.append(stat)

        if not all_stats:
            return {
                "total_examinations": 0,
                "position_complete_rate": 0,
                "quality_pass_rate": 0,
                "report_standard_rate": 0,
                "anomaly_rate": 0,
                "correction_rate": 0,
            }

        total = sum(s["total_examinations"] for s in all_stats)
        return {
            "total_examinations": total,
            "position_complete_rate": safe_divide(sum(s["position_complete_count"] for s in all_stats), total) * 100,
            "quality_pass_rate": safe_divide(sum(s["quality_pass_count"] for s in all_stats), total) * 100,
            "report_standard_rate": safe_divide(sum(s["report_standard_count"] for s in all_stats), total) * 100,
            "anomaly_rate": safe_divide(sum(s["total_anomalies"] for s in all_stats), total) * 100,
            "correction_rate": safe_divide(sum(s["corrected_anomalies"] for s in all_stats), sum(s["confirmed_anomalies"] for s in all_stats)) * 100,
        }

    def export_report_data(self, report_id: int) -> Dict[str, Any]:
        report = self.db.query(MonthlyReport).filter(
            MonthlyReport.id == report_id,
            MonthlyReport.is_deleted == False,
        ).first()

        if not report:
            raise NotFoundError(f"月报不存在: {report_id}")

        export_data = {
            "report_id": report.id,
            "hospital_name": report.hospital_name,
            "report_period": report.report_period,
            "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            "summary": report.summary,
            "key_metrics": {
                "total_examinations": report.total_examinations,
                "position_complete_rate": report.position_complete_rate,
                "quality_pass_rate": report.quality_pass_rate,
                "report_standard_rate": report.report_standard_rate,
                "anomaly_rate": report.anomaly_rate,
                "average_quality_score": report.average_quality_score,
            },
            "statistical_data": report.statistical_data,
            "high_frequency_defects": report.defect_statistics,
            "recommendations": report.recommendations,
        }

        return export_data
