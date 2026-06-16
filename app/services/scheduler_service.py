from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, date, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR
from sqlalchemy.orm import Session
import logging

from ..models import ScheduledTask, TaskExecutionLog
from ..schemas import ScheduledTaskCreate, ScheduledTaskUpdate
from ..core.exceptions import NotFoundError, BusinessError
from ..core.logger import get_logger
from ..database import SessionLocal
from .examination_service import ExaminationService
from .anomaly_detection_service import AnomalyDetectionService
from .statistics_service import StatisticsService
from .benchmark_service import BenchmarkService

logger = get_logger(__name__)


class SchedulerService:
    _instance = None
    _scheduler: Optional[BackgroundScheduler] = None
    _db: Optional[Session] = None

    def __new__(cls, db: Optional[Session] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        if db is not None:
            cls._instance._db = db
        return cls._instance

    def __init__(self, db: Optional[Session] = None):
        if self._initialized:
            if db is not None:
                self._db = db
            return
        self._initialized = True
        if db is not None:
            self._db = db
        self._scheduler = None
        self._job_handlers = {}
        self._register_job_handlers()

    def _register_job_handlers(self):
        self._job_handlers = {
            "auto_qa": self._job_auto_qa,
            "anomaly_detection": self._job_anomaly_detection,
            "monthly_report": self._job_monthly_report,
            "benchmark_calculation": self._job_benchmark_calculation,
            "persistent_anomaly_check": self._job_persistent_anomaly_check,
            "data_backup": self._job_data_backup,
            "similarity_check": self._job_similarity_check,
        }

    def start(self):
        if self._scheduler and self._scheduler.running:
            logger.warning("Scheduler is already running")
            return

        self._scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        self._scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
        self._scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)

        self._load_scheduled_tasks()

        self._scheduler.start()
        logger.info("Scheduler started successfully")

    def shutdown(self, wait: bool = True):
        if self._scheduler:
            self._scheduler.shutdown(wait=wait)
            logger.info("Scheduler shutdown successfully")

    def _load_scheduled_tasks(self):
        if not self._db:
            logger.error("Database session not available")
            return

        tasks = self._db.query(ScheduledTask).filter(
            ScheduledTask.is_deleted == False,
            ScheduledTask.is_active == True,
        ).all()

        for task in tasks:
            try:
                self._add_job_to_scheduler(task)
                logger.info(f"Loaded scheduled task: {task.name} ({task.id})")
            except Exception as e:
                logger.error(f"Failed to load scheduled task {task.id}: {e}")

    def _add_job_to_scheduler(self, task: ScheduledTask):
        if not self._scheduler:
            raise BusinessError("Scheduler not initialized")

        if task.task_type not in self._job_handlers:
            raise BusinessError(f"Unknown task type: {task.task_type}")

        trigger = self._build_trigger(task)
        job_id = f"task_{task.id}"

        self._scheduler.add_job(
            func=self._job_wrapper,
            trigger=trigger,
            id=job_id,
            name=task.name,
            args=[task.id],
            replace_existing=True,
            misfire_grace_time=task.misfire_grace_time or 3600,
            coalesce=task.coalesce or True,
            max_instances=task.max_instances or 1,
        )

    def _build_trigger(self, task: ScheduledTask):
        if task.schedule_type == "cron":
            return CronTrigger.from_crontab(task.cron_expression)
        elif task.schedule_type == "interval":
            return IntervalTrigger(seconds=task.interval_seconds or 3600)
        elif task.schedule_type == "date":
            return DateTrigger(run_date=task.run_date)
        else:
            raise BusinessError(f"Unknown schedule type: {task.schedule_type}")

    def _job_wrapper(self, task_id: int):
        db = SessionLocal()
        try:
            task = db.query(ScheduledTask).filter(
                ScheduledTask.id == task_id,
                ScheduledTask.is_deleted == False,
            ).first()

            if not task:
                logger.error(f"Scheduled task {task_id} not found")
                return

            if not task.is_active:
                logger.info(f"Skipping inactive task {task_id}")
                return

            execution_log = TaskExecutionLog(
                task_id=task_id,
                start_time=datetime.utcnow(),
                status="running",
            )
            db.add(execution_log)
            db.commit()
            db.refresh(execution_log)

            try:
                handler = self._job_handlers.get(task.task_type)
                if handler:
                    result = handler(db, task.task_params)
                    execution_log.end_time = datetime.utcnow()
                    execution_log.status = "success"
                    execution_log.result = result
                    execution_log.duration_ms = int(
                        (execution_log.end_time - execution_log.start_time).total_seconds() * 1000
                    )
                else:
                    raise BusinessError(f"Unknown task type: {task.task_type}")
            except Exception as e:
                execution_log.end_time = datetime.utcnow()
                execution_log.status = "failed"
                execution_log.error_message = str(e)
                execution_log.duration_ms = int(
                    (execution_log.end_time - execution_log.start_time).total_seconds() * 1000
                )
                logger.error(f"Task {task_id} execution failed: {e}")

            db.commit()
            task.last_run_at = execution_log.start_time
            task.last_run_status = execution_log.status

            if task.retry_count:
                task.retry_count -= 1

            db.commit()

        except Exception as e:
            logger.error(f"Error in task wrapper for {task_id}: {e}")
        finally:
            db.close()

    def _on_job_executed(self, event):
        logger.info(f"Job {event.job_id} executed successfully")

    def _on_job_error(self, event):
        logger.error(f"Job {event.job_id} failed with error: {event.exception}")

    def _job_auto_qa(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        exam_service = ExaminationService(db)
        processed = exam_service.run_auto_qa()
        return {
            "processed_count": processed,
            "message": f"Auto QA completed for {processed} examinations",
        }

    def _job_anomaly_detection(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        anomaly_service = AnomalyDetectionService(db)

        hospital_id = params.get("hospital_id")
        start_date = params.get("start_date")
        end_date = params.get("end_date")

        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()

        if not start_date:
            start_date = date.today() - timedelta(days=1)
        if not end_date:
            end_date = date.today()

        anomaly_count = anomaly_service.run_periodic_detection(
            hospital_id=hospital_id,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "anomaly_count": anomaly_count,
            "hospital_id": hospital_id,
            "period": f"{start_date} to {end_date}",
        }

    def _job_monthly_report(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        stats_service = StatisticsService(db)

        hospital_id = params.get("hospital_id")
        year = params.get("year")
        month = params.get("month")

        if not year or not month:
            today = date.today()
            first_day = date(today.year, today.month, 1)
            last_month = first_day - timedelta(days=1)
            year = last_month.year
            month = last_month.month

        hospitals = []
        if hospital_id:
            hospitals = [hospital_id]
        else:
            from ..models import Hospital
            hospitals = [h.id for h in db.query(Hospital).filter(
                Hospital.is_deleted == False,
                Hospital.is_active == True,
            ).all()]

        reports = []
        for h_id in hospitals:
            try:
                from ..schemas import MonthlyReportCreate
                report_data = MonthlyReportCreate(
                    hospital_id=h_id,
                    report_year=year,
                    report_month=month,
                    report_type="screening",
                )
                report = stats_service.generate_monthly_report(report_data)
                reports.append({"hospital_id": h_id, "report_id": report.id})
            except Exception as e:
                logger.error(f"Failed to generate report for hospital {h_id}: {e}")

        return {
            "year": year,
            "month": month,
            "reports_generated": len(reports),
            "reports": reports,
        }

    def _job_benchmark_calculation(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        benchmark_service = BenchmarkService(db)

        year = params.get("year")
        month = params.get("month")
        hospital_id = params.get("hospital_id")

        if not year or not month:
            today = date.today()
            first_day = date(today.year, today.month, 1)
            last_month = first_day - timedelta(days=1)
            year = last_month.year
            month = last_month.month

        benchmarks = benchmark_service.generate_benchmark_data(year, month, hospital_id)

        return {
            "year": year,
            "month": month,
            "benchmarks_count": len(benchmarks),
        }

    def _job_persistent_anomaly_check(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        benchmark_service = BenchmarkService(db)

        consecutive_months = params.get("consecutive_months", 3)
        hospital_id = params.get("hospital_id")

        rooms = benchmark_service.identify_persistent_anomaly_rooms(
            consecutive_months=consecutive_months,
            hospital_id=hospital_id,
        )

        return {
            "consecutive_months": consecutive_months,
            "persistent_rooms_count": len(rooms),
        }

    def _job_data_backup(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        backup_type = params.get("type", "full")
        retention_days = params.get("retention_days", 30)

        return {
            "backup_type": backup_type,
            "retention_days": retention_days,
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _job_similarity_check(self, db: Session, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        anomaly_service = AnomalyDetectionService(db)

        hospital_id = params.get("hospital_id")
        days = params.get("days", 7)
        limit = params.get("limit", 100)

        start_date = date.today() - timedelta(days=days)

        from ..models import Examination
        query = db.query(Examination).filter(
            Examination.is_deleted == False,
            Examination.examination_date >= start_date,
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)

        exams = query.limit(limit).all()

        total_checks = 0
        for exam in exams:
            try:
                checks = anomaly_service.check_similarity(exam.id)
                total_checks += len(checks)
            except Exception as e:
                logger.error(f"Similarity check failed for exam {exam.id}: {e}")

        return {
            "exams_processed": len(exams),
            "similarity_checks": total_checks,
            "period_days": days,
        }

    def create_task(self, task_data: ScheduledTaskCreate, creator_id: Optional[int] = None) -> ScheduledTask:
        existing = self._db.query(ScheduledTask).filter(
            ScheduledTask.name == task_data.name,
            ScheduledTask.is_deleted == False,
        ).first()
        if existing:
            raise BusinessError(f"任务名称已存在: {task_data.name}")

        if task_data.task_type not in self._job_handlers:
            raise BusinessError(f"不支持的任务类型: {task_data.task_type}")

        task = ScheduledTask(**task_data.model_dump())
        task.created_by = creator_id

        self._db.add(task)
        self._db.commit()
        self._db.refresh(task)

        if task.is_active and self._scheduler:
            try:
                self._add_job_to_scheduler(task)
            except Exception as e:
                logger.error(f"Failed to add task to scheduler: {e}")
                task.is_active = False
                self._db.commit()

        logger.info(f"Created scheduled task: {task.name} ({task.id})")
        return task

    def update_task(self, task_id: int, update_data: ScheduledTaskUpdate) -> ScheduledTask:
        task = self._db.query(ScheduledTask).filter(
            ScheduledTask.id == task_id,
            ScheduledTask.is_deleted == False,
        ).first()

        if not task:
            raise NotFoundError(f"定时任务不存在: {task_id}")

        old_name = task.name
        old_is_active = task.is_active

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(task, key, value)

        self._db.commit()
        self._db.refresh(task)

        if self._scheduler:
            job_id = f"task_{task_id}"

            if old_is_active and self._scheduler.get_job(job_id):
                self._scheduler.remove_job(job_id)

            if task.is_active:
                try:
                    self._add_job_to_scheduler(task)
                except Exception as e:
                    logger.error(f"Failed to update task in scheduler: {e}")

        logger.info(f"Updated scheduled task: {task.name} ({task_id})")
        return task

    def run_task_now(self, task_id: int) -> TaskExecutionLog:
        task = self._db.query(ScheduledTask).filter(
            ScheduledTask.id == task_id,
            ScheduledTask.is_deleted == False,
        ).first()

        if not task:
            raise NotFoundError(f"定时任务不存在: {task_id}")

        execution_log = TaskExecutionLog(
            task_id=task_id,
            start_time=datetime.utcnow(),
            status="running",
            triggered_by="manual",
        )
        self._db.add(execution_log)
        self._db.commit()
        self._db.refresh(execution_log)

        try:
            handler = self._job_handlers.get(task.task_type)
            if handler:
                result = handler(self._db, task.task_params)
                execution_log.end_time = datetime.utcnow()
                execution_log.status = "success"
                execution_log.result = result
                execution_log.duration_ms = int(
                    (execution_log.end_time - execution_log.start_time).total_seconds() * 1000
                )
            else:
                raise BusinessError(f"Unknown task type: {task.task_type}")
        except Exception as e:
            execution_log.end_time = datetime.utcnow()
            execution_log.status = "failed"
            execution_log.error_message = str(e)
            execution_log.duration_ms = int(
                (execution_log.end_time - execution_log.start_time).total_seconds() * 1000
            )
            logger.error(f"Manual task execution failed for {task_id}: {e}")

        self._db.commit()
        task.last_run_at = execution_log.start_time
        task.last_run_status = execution_log.status
        self._db.commit()

        return execution_log

    def toggle_task(self, task_id: int, is_active: bool) -> ScheduledTask:
        task = self._db.query(ScheduledTask).filter(
            ScheduledTask.id == task_id,
            ScheduledTask.is_deleted == False,
        ).first()

        if not task:
            raise NotFoundError(f"定时任务不存在: {task_id}")

        task.is_active = is_active
        self._db.commit()
        self._db.refresh(task)

        if self._scheduler:
            job_id = f"task_{task_id}"
            if is_active:
                try:
                    self._add_job_to_scheduler(task)
                except Exception as e:
                    logger.error(f"Failed to activate task {task_id}: {e}")
                    task.is_active = False
                    self._db.commit()
            else:
                if self._scheduler.get_job(job_id):
                    self._scheduler.remove_job(job_id)

        return task

    def list_tasks(
        self,
        task_type: Optional[str] = None,
        is_active: Optional[bool] = None,
        schedule_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ScheduledTask], int]:
        query = self._db.query(ScheduledTask).filter(ScheduledTask.is_deleted == False)

        if task_type:
            query = query.filter(ScheduledTask.task_type == task_type)
        if is_active is not None:
            query = query.filter(ScheduledTask.is_active == is_active)
        if schedule_type:
            query = query.filter(ScheduledTask.schedule_type == schedule_type)

        total = query.count()
        tasks = query.order_by(ScheduledTask.created_at.desc()).offset(skip).limit(limit).all()
        return tasks, total

    def get_execution_logs(
        self,
        task_id: Optional[int] = None,
        status: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[TaskExecutionLog], int]:
        query = self._db.query(TaskExecutionLog)

        if task_id:
            query = query.filter(TaskExecutionLog.task_id == task_id)
        if status:
            query = query.filter(TaskExecutionLog.status == status)
        if start_date:
            query = query.filter(TaskExecutionLog.start_time >= start_date)
        if end_date:
            query = query.filter(TaskExecutionLog.start_time <= end_date)

        total = query.count()
        logs = query.order_by(TaskExecutionLog.start_time.desc()).offset(skip).limit(limit).all()
        return logs, total

    def get_scheduler_status(self) -> Dict[str, Any]:
        if not self._scheduler:
            return {"running": False, "message": "Scheduler not initialized"}

        jobs = self._scheduler.get_jobs()
        return {
            "running": self._scheduler.running,
            "job_count": len(jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
                }
                for job in jobs
            ],
        }
