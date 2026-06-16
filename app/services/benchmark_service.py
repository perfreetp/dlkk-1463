from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models import (
    Hospital,
    Room,
    Equipment,
    Examination,
    ImageQuality,
    BIRADSReport,
    AnomalyRecord,
    PersistentAnomalyRoom,
    BenchmarkData,
    BestPractice,
    HighFrequencyDefect,
)
from ..schemas import (
    BenchmarkDataCreate,
    BestPracticeCreate,
    BestPracticeUpdate,
    BenchmarkQueryParams,
    BenchmarkComparisonResponse,
    PersistentAnomalyRoomResponse,
    BestPracticeResponse,
    HighFrequencyDefectResponse,
)
from ..core.exceptions import NotFoundError, BusinessError
from ..core.logger import get_logger
from ..core.utils import calculate_percentage, get_date_range, safe_divide, get_month_range

logger = get_logger(__name__)


class BenchmarkService:
    def __init__(self, db: Session):
        self.db = db

    def generate_benchmark_data(
        self,
        year: int,
        month: int,
        hospital_id: Optional[int] = None,
    ) -> List[BenchmarkData]:
        start_date, end_date = get_month_range(year, month)

        hospitals = self.db.query(Hospital).filter(
            Hospital.is_deleted == False,
            Hospital.is_active == True,
        )

        if hospital_id:
            hospitals = hospitals.filter(Hospital.id == hospital_id)

        hospitals = hospitals.all()

        benchmark_list = []
        for hospital in hospitals:
            existing = self.db.query(BenchmarkData).filter(
                BenchmarkData.hospital_id == hospital.id,
                BenchmarkData.benchmark_year == year,
                BenchmarkData.benchmark_month == month,
                BenchmarkData.is_deleted == False,
            ).first()

            if existing:
                benchmark_list.append(existing)
                continue

            data = self._calculate_benchmark_metrics(hospital.id, start_date, end_date)

            benchmark = BenchmarkData(
                hospital_id=hospital.id,
                hospital_name=hospital.name,
                benchmark_year=year,
                benchmark_month=month,
                benchmark_period=f"{year}年{month}月",
                benchmark_date=date(year, month, 1),
                benchmark_type="hospital",
                data_start_date=start_date,
                data_end_date=end_date,
                **data,
            )

            self.db.add(benchmark)
            benchmark_list.append(benchmark)

        self.db.commit()
        for benchmark in benchmark_list:
            self.db.refresh(benchmark)

        self._update_benchmark_ranks(year, month)

        logger.info(f"Generated benchmark data for {len(benchmark_list)} hospitals, {year}-{month}")
        return benchmark_list

    def _calculate_benchmark_metrics(
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

        total = query.count()

        if total == 0:
            return {
                "total_examinations": 0,
                "position_pass_count": 0,
                "position_pass_rate": 0,
                "quality_pass_count": 0,
                "quality_pass_rate": 0,
                "report_standard_count": 0,
                "report_standard_rate": 0,
                "anomaly_count": 0,
                "anomaly_rate": 0,
                "avg_dose": 0,
                "avg_ag_dose": 0,
                "overall_score": 0,
            }

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
        high_severity = anomaly_query.filter(
            AnomalyRecord.severity_level.in_(["high", "critical"]),
        ).count()
        confirmed = anomaly_query.filter(AnomalyRecord.is_confirmed == True).count()
        corrected = anomaly_query.filter(AnomalyRecord.correction_status == "corrected").count()

        avg_quality = self.db.query(func.avg(ImageQuality.overall_score)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            ImageQuality.overall_score.isnot(None),
            ImageQuality.is_deleted == False,
        ).scalar() or 0

        avg_description = self.db.query(func.avg(BIRADSReport.description_quality_score)).join(Examination).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            BIRADSReport.description_quality_score.isnot(None),
            BIRADSReport.is_deleted == False,
        ).scalar() or 0

        avg_dose = self.db.query(func.avg(Examination.average_glandular_dose)).filter(
            Examination.hospital_id == hospital_id,
            Examination.examination_date >= start_date,
            Examination.examination_date <= end_date,
            Examination.average_glandular_dose.isnot(None),
            Examination.is_deleted == False,
        ).scalar() or 0

        from ..models import ReviewTask, Rectification

        total_tasks = self.db.query(func.count(ReviewTask.id)).filter(
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

        total_rects = self.db.query(func.count(Rectification.id)).filter(
            Rectification.hospital_id == hospital_id,
            Rectification.created_at >= start_date,
            Rectification.created_at <= end_date,
            Rectification.is_deleted == False,
        ).scalar() or 0

        passed_rects = self.db.query(func.count(Rectification.id)).filter(
            Rectification.hospital_id == hospital_id,
            Rectification.status == "verified",
            Rectification.verification_passed == True,
            Rectification.completed_at >= start_date,
            Rectification.completed_at <= end_date,
            Rectification.is_deleted == False,
        ).scalar() or 0

        position_rate = calculate_percentage(position_complete, total)
        quality_rate = calculate_percentage(quality_pass, total)
        report_rate = calculate_percentage(report_standard, total)
        anomaly_rate = calculate_percentage(total_anomalies, total)
        high_sev_rate = calculate_percentage(high_severity, total_anomalies) if total_anomalies else 0
        correction_rate = calculate_percentage(corrected, confirmed) if confirmed else 0
        task_rate = calculate_percentage(completed_tasks, total_tasks) if total_tasks else 100
        rect_rate = calculate_percentage(passed_rects, total_rects) if total_rects else 100

        overall_score = (
            position_rate * 0.25 +
            quality_rate * 0.25 +
            report_rate * 0.20 +
            (100 - anomaly_rate) * 0.15 +
            correction_rate * 0.15
        )

        return {
            "total_examinations": total,
            "position_pass_count": position_complete,
            "position_pass_rate": position_rate,
            "quality_pass_count": quality_pass,
            "quality_pass_rate": quality_rate,
            "report_standard_count": report_standard,
            "report_standard_rate": report_rate,
            "anomaly_count": total_anomalies,
            "anomaly_rate": anomaly_rate,
            "avg_dose": round(avg_dose, 3),
            "avg_ag_dose": round(avg_dose, 3),
            "overall_score": round(overall_score, 2),
        }

    def _update_benchmark_ranks(self, year: int, month: int):
        benchmarks = self.db.query(BenchmarkData).filter(
            BenchmarkData.benchmark_year == year,
            BenchmarkData.benchmark_month == month,
            BenchmarkData.is_deleted == False,
        ).order_by(BenchmarkData.overall_score.desc()).all()

        for idx, benchmark in enumerate(benchmarks, 1):
            benchmark.overall_rank = idx
            benchmark.percentile = round(((len(benchmarks) - idx + 1) / len(benchmarks)) * 100, 2)

            if idx == 1:
                benchmark.performance_level = "excellent"
            elif idx <= len(benchmarks) * 0.25:
                benchmark.performance_level = "good"
            elif idx <= len(benchmarks) * 0.5:
                benchmark.performance_level = "average"
            elif idx <= len(benchmarks) * 0.75:
                benchmark.performance_level = "below_average"
            else:
                benchmark.performance_level = "poor"

        self.db.commit()

    def get_benchmark_comparison(
        self,
        query_params: BenchmarkQueryParams,
    ) -> BenchmarkComparisonResponse:
        query = self.db.query(BenchmarkData).filter(
            BenchmarkData.is_deleted == False,
        )

        if query_params.hospital_id:
            query = query.filter(BenchmarkData.hospital_id == query_params.hospital_id)
        if query_params.benchmark_year:
            query = query.filter(BenchmarkData.benchmark_year == query_params.benchmark_year)
        if query_params.benchmark_month:
            query = query.filter(BenchmarkData.benchmark_month == query_params.benchmark_month)
        if query_params.rank_level:
            query = query.filter(BenchmarkData.performance_level == query_params.rank_level)

        benchmarks = query.order_by(BenchmarkData.overall_rank.asc()).all()

        group_stats = self._calculate_group_stats(benchmarks)

        return BenchmarkComparisonResponse(
            benchmark_year=query_params.benchmark_year,
            benchmark_month=query_params.benchmark_month,
            total_hospitals=len(benchmarks),
            group_averages=group_stats,
            rankings=benchmarks,
        )

    def _calculate_group_stats(self, benchmarks: List[BenchmarkData]) -> Dict[str, Any]:
        if not benchmarks:
            return {}

        fields = [
            "position_pass_rate",
            "quality_pass_rate",
            "report_standard_rate",
            "anomaly_rate",
            "avg_dose",
            "avg_ag_dose",
            "overall_score",
        ]

        stats = {}
        for field in fields:
            values = [getattr(b, field) for b in benchmarks if getattr(b, field) is not None]
            if values:
                stats[f"avg_{field}"] = round(sum(values) / len(values), 2)
                stats[f"max_{field}"] = round(max(values), 2)
                stats[f"min_{field}"] = round(min(values), 2)

        return stats

    def identify_persistent_anomaly_rooms(
        self,
        consecutive_months: int = 3,
        hospital_id: Optional[int] = None,
    ) -> List[PersistentAnomalyRoom]:
        today = date.today()
        end_date = date(today.year, today.month, 1) - timedelta(days=1)
        start_date = end_date - timedelta(days=30 * consecutive_months) + timedelta(days=1)

        query = self.db.query(
            Room.id.label("room_id"),
            Room.code.label("room_code"),
            Room.name.label("room_name"),
            Room.hospital_id,
            Hospital.name.label("hospital_name"),
            AnomalyRecord.anomaly_type,
            func.count(AnomalyRecord.id).label("anomaly_count"),
        ).join(
            Hospital, Hospital.id == Room.hospital_id,
        ).join(
            Examination, Examination.room_id == Room.id,
        ).join(
            AnomalyRecord, AnomalyRecord.examination_id == Examination.id,
        ).filter(
            Room.is_deleted == False,
            Examination.is_deleted == False,
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
            AnomalyRecord.detected_at >= start_date,
            AnomalyRecord.detected_at <= end_date,
        )

        if hospital_id:
            query = query.filter(Room.hospital_id == hospital_id)

        results = query.group_by(
            Room.id,
            Room.code,
            Room.name,
            Room.hospital_id,
            Hospital.name,
            AnomalyRecord.anomaly_type,
        ).having(
            func.count(AnomalyRecord.id) >= 5 * consecutive_months,
        ).all()

        persistent_rooms = []
        for row in results:
            total_exams = self.db.query(func.count(Examination.id)).filter(
                Examination.room_id == row.room_id,
                Examination.examination_date >= start_date,
                Examination.examination_date <= end_date,
                Examination.is_deleted == False,
            ).scalar() or 1

            anomaly_rate = calculate_percentage(row.anomaly_count, total_exams)

            existing = self.db.query(PersistentAnomalyRoom).filter(
                PersistentAnomalyRoom.room_id == row.room_id,
                PersistentAnomalyRoom.anomaly_type == row.anomaly_type,
                PersistentAnomalyRoom.is_resolved == False,
                PersistentAnomalyRoom.is_deleted == False,
            ).first()

            if existing:
                existing.anomaly_count = row.anomaly_count
                existing.anomaly_rate = anomaly_rate
                existing.consecutive_months = consecutive_months
                existing.last_detected_date = end_date
                existing.total_examinations_count = total_exams
                persistent_rooms.append(existing)
            else:
                severity = "high" if anomaly_rate > 30 else "medium"
                persistent = PersistentAnomalyRoom(
                    hospital_id=row.hospital_id,
                    hospital_name=row.hospital_name,
                    room_id=row.room_id,
                    room_code=row.room_code,
                    room_name=row.room_name,
                    anomaly_type=row.anomaly_type,
                    anomaly_count=row.anomaly_count,
                    consecutive_months=consecutive_months,
                    first_detected_date=start_date,
                    last_detected_date=end_date,
                    total_examinations_count=total_exams,
                    anomaly_rate=anomaly_rate,
                    severity_level=severity,
                    rectification_status="pending",
                    is_resolved=False,
                    progress=0,
                )
                self.db.add(persistent)
                persistent_rooms.append(persistent)

        self.db.commit()
        for room in persistent_rooms:
            self.db.refresh(room)

        logger.info(f"Identified {len(persistent_rooms)} persistent anomaly rooms")
        return persistent_rooms

    def get_persistent_anomaly_rooms(
        self,
        hospital_id: Optional[int] = None,
        anomaly_type: Optional[str] = None,
        rectification_status: Optional[str] = None,
        is_resolved: Optional[bool] = False,
        min_consecutive_months: int = 3,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[PersistentAnomalyRoom], int]:
        query = self.db.query(PersistentAnomalyRoom).filter(
            PersistentAnomalyRoom.is_deleted == False,
            PersistentAnomalyRoom.consecutive_months >= min_consecutive_months,
        )

        if hospital_id:
            query = query.filter(PersistentAnomalyRoom.hospital_id == hospital_id)
        if anomaly_type:
            query = query.filter(PersistentAnomalyRoom.anomaly_type == anomaly_type)
        if rectification_status:
            query = query.filter(PersistentAnomalyRoom.rectification_status == rectification_status)
        if is_resolved is not None:
            query = query.filter(PersistentAnomalyRoom.is_resolved == is_resolved)

        total = query.count()
        rooms = query.order_by(
            PersistentAnomalyRoom.consecutive_months.desc(),
            PersistentAnomalyRoom.anomaly_rate.desc(),
        ).offset(skip).limit(limit).all()

        return rooms, total

    def update_persistent_anomaly_room(
        self,
        room_id: int,
        update_data: Dict[str, Any],
    ) -> PersistentAnomalyRoom:
        room = self.db.query(PersistentAnomalyRoom).filter(
            PersistentAnomalyRoom.id == room_id,
            PersistentAnomalyRoom.is_deleted == False,
        ).first()

        if not room:
            raise NotFoundError(f"持续异常机房不存在: {room_id}")

        for key, value in update_data.items():
            setattr(room, key, value)

        if update_data.get("rectification_status") == "resolved":
            room.is_resolved = True
            room.resolved_date = date.today()

        self.db.commit()
        self.db.refresh(room)
        return room

    def create_excellent_case(
        self,
        case_data: BestPracticeCreate,
        creator_id: Optional[int] = None,
    ) -> BestPractice:
        case = BestPractice(**case_data.model_dump())
        hospital = self.db.query(Hospital).filter(Hospital.id == case_data.hospital_id).first()
        if hospital:
            case.hospital_name = hospital.name
        case.status = "draft"

        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)

        logger.info(f"Created best practice {case.id}")
        return case

    def get_excellent_case(self, case_id: int) -> BestPractice:
        case = self.db.query(BestPractice).filter(
            BestPractice.id == case_id,
            BestPractice.is_deleted == False,
        ).first()
        if not case:
            raise NotFoundError(f"优秀案例不存在: {case_id}")
        return case

    def list_excellent_cases(
        self,
        hospital_id: Optional[int] = None,
        case_type: Optional[str] = None,
        category: Optional[str] = None,
        is_approved: Optional[bool] = None,
        keyword: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[BestPractice], int]:
        query = self.db.query(BestPractice).filter(BestPractice.is_deleted == False)

        if hospital_id:
            query = query.filter(BestPractice.hospital_id == hospital_id)
        if case_type:
            query = query.filter(BestPractice.practice_type == case_type)
        if category:
            query = query.filter(BestPractice.category == category)
        if is_approved is not None:
            query = query.filter(BestPractice.status == ("approved" if is_approved else "draft"))
        if keyword:
            keyword = f"%{keyword}%"
            query = query.filter(
                or_(
                    BestPractice.title.ilike(keyword),
                    BestPractice.description.ilike(keyword),
                )
            )

        total = query.count()
        cases = query.order_by(BestPractice.created_at.desc()).offset(skip).limit(limit).all()
        return cases, total

    def update_excellent_case(
        self,
        case_id: int,
        update_data: BestPracticeUpdate,
        operator_id: Optional[int] = None,
    ) -> BestPractice:
        case = self.get_excellent_case(case_id)

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(case, key, value)

        if update_data.status == "approved" and case.status != "approved":
            case.approved_by = operator_id
            case.approved_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(case)
        return case

    def get_high_frequency_defects(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        anomaly_type: Optional[str] = None,
        top_n: int = 20,
    ) -> List[HighFrequencyDefect]:
        if not start_date:
            start_date = date.today() - timedelta(days=90)
        if not end_date:
            end_date = date.today()

        query = self.db.query(HighFrequencyDefect).filter(
            HighFrequencyDefect.is_deleted == False,
            HighFrequencyDefect.period_start >= start_date,
            HighFrequencyDefect.period_end <= end_date,
        )

        if hospital_id:
            query = query.filter(HighFrequencyDefect.hospital_id == hospital_id)
        if anomaly_type:
            query = query.filter(HighFrequencyDefect.anomaly_type == anomaly_type)

        return query.order_by(HighFrequencyDefect.occurrence_count.desc()).limit(top_n).all()

    def analyze_defect_trends(
        self,
        defect_code: str,
        hospital_id: Optional[int] = None,
        months: int = 6,
    ) -> List[Dict[str, Any]]:
        trend_data = []
        today = date.today()

        for i in range(months - 1, -1, -1):
            year = today.year - ((today.month - 1 - i) // 12)
            month = (today.month - 1 - i) % 12 + 1
            start_date, end_date = get_month_range(year, month)

            count = self.db.query(func.count(AnomalyRecord.id)).filter(
                AnomalyRecord.detected_at >= start_date,
                AnomalyRecord.detected_at <= end_date,
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
            )

            if hospital_id:
                count = count.filter(AnomalyRecord.hospital_id == hospital_id)

            parts = defect_code.split("_", 1)
            if len(parts) == 2:
                anomaly_type, category = parts
                count = count.filter(
                    AnomalyRecord.anomaly_type == anomaly_type,
                    AnomalyRecord.anomaly_category == category,
                )
            else:
                count = count.filter(AnomalyRecord.anomaly_type == defect_code)

            count = count.scalar() or 0

            total = self.db.query(func.count(AnomalyRecord.id)).filter(
                AnomalyRecord.detected_at >= start_date,
                AnomalyRecord.detected_at <= end_date,
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
            )

            if hospital_id:
                total = total.filter(AnomalyRecord.hospital_id == hospital_id)

            total = total.scalar() or 1

            trend_data.append({
                "year": year,
                "month": month,
                "period": f"{year}年{month}月",
                "defect_code": defect_code,
                "count": count,
                "percentage": calculate_percentage(count, total),
            })

        return trend_data

    def get_group_best_practices(
        self,
        category: Optional[str] = None,
        top_n: int = 10,
    ) -> List[Dict[str, Any]]:
        practices = []

        benchmarks = self.db.query(BenchmarkData).filter(
            BenchmarkData.is_deleted == False,
        ).order_by(
            BenchmarkData.created_at.desc(),
        ).limit(50).all()

        if not benchmarks:
            return practices

        best_position = max(benchmarks, key=lambda b: b.position_pass_rate)
        best_quality = max(benchmarks, key=lambda b: b.quality_pass_rate)
        best_report = max(benchmarks, key=lambda b: b.report_standard_rate)
        best_low_anomaly = min(benchmarks, key=lambda b: b.anomaly_rate)

        practice_map = {
            "position_complete": {
                "category": "position",
                "title": "体位完整性最佳实践",
                "hospital_name": best_position.hospital_name,
                "metric_name": "体位完整率",
                "metric_value": best_position.position_pass_rate,
                "description": f"{best_position.hospital_name}体位完整率达到{best_position.position_pass_rate}%，建议学习其投照技师培训方法和检查核对流程。",
            },
            "image_quality": {
                "category": "quality",
                "title": "图像质量最佳实践",
                "hospital_name": best_quality.hospital_name,
                "metric_name": "图像质量合格率",
                "metric_value": best_quality.quality_pass_rate,
                "description": f"{best_quality.hospital_name}图像质量合格率达到{best_quality.quality_pass_rate}%，建议学习其设备维护和参数优化经验。",
            },
            "report_standard": {
                "category": "report",
                "title": "报告规范化最佳实践",
                "hospital_name": best_report.hospital_name,
                "metric_name": "报告规范率",
                "metric_value": best_report.report_standard_rate,
                "description": f"{best_report.hospital_name}报告规范率达到{best_report.report_standard_rate}%，建议学习其BI-RADS分类培训和报告模板。",
            },
            "low_anomaly": {
                "category": "process",
                "title": "低异常率最佳实践",
                "hospital_name": best_low_anomaly.hospital_name,
                "metric_name": "异常率",
                "metric_value": best_low_anomaly.anomaly_rate,
                "description": f"{best_low_anomaly.hospital_name}异常率仅{best_low_anomaly.anomaly_rate}%，建议学习其全过程质控管理方法。",
            },
        }

        for key, practice in practice_map.items():
            if not category or practice["category"] == category:
                practices.append(practice)

        return practices[:top_n]
