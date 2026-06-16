from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from ..models import (
    ReviewTask,
    ReviewRecord,
    Rectification,
    Examination,
    User,
    Hospital,
    AnomalyRecord,
)
from ..schemas import (
    ReviewTaskCreate,
    ReviewTaskUpdate,
    ReviewRecordCreate,
    RectificationCreate,
    RectificationUpdate,
    ReviewStatsResponse,
    AssignTaskRequest,
    BatchAssignRequest,
    ReviewTaskFilter,
)
from ..core.exceptions import NotFoundError, BusinessError, ForbiddenError
from ..core.logger import get_logger
from ..core.utils import calculate_percentage, get_date_range, safe_divide

logger = get_logger(__name__)


class ReviewService:
    def __init__(self, db: Session):
        self.db = db

    def create_task(self, task_data: ReviewTaskCreate, creator_id: Optional[int] = None) -> ReviewTask:
        exam = self.db.query(Examination).filter(
            Examination.id == task_data.examination_id,
            Examination.is_deleted == False,
        ).first()
        if not exam:
            raise NotFoundError(f"检查不存在: {task_data.examination_id}")

        assignee = None
        if task_data.assignee_id:
            assignee = self.db.query(User).filter(
                User.id == task_data.assignee_id,
                User.is_deleted == False,
                User.is_active == True,
            ).first()
            if not assignee:
                raise NotFoundError(f"复核人不存在: {task_data.assignee_id}")

        task_dict = task_data.model_dump(exclude={"anomaly_ids"})
        task = ReviewTask(**task_dict)
        task.status = "assigned" if task_data.assignee_id else "pending"
        task.created_by = creator_id
        task.assigned_at = datetime.utcnow() if task_data.assignee_id else None

        if task_data.anomaly_ids:
            anomalies = self.db.query(AnomalyRecord).filter(
                AnomalyRecord.id.in_(task_data.anomaly_ids),
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.examination_id == task_data.examination_id,
            ).all()
            task.anomalies = anomalies

        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        exam.status = "under_review"
        self.db.commit()

        logger.info(f"Created review task {task.id} for exam {task.examination_id}")
        return task

    def assign_task(self, task_id: int, assign_data: AssignTaskRequest, operator_id: Optional[int] = None) -> ReviewTask:
        task = self._get_task(task_id)

        if task.status not in ["pending", "rejected"]:
            raise BusinessError(f"任务状态不允许分配: {task.status}")

        assignee = self.db.query(User).filter(
            User.id == assign_data.assignee_id,
            User.is_deleted == False,
            User.is_active == True,
        ).first()
        if not assignee:
            raise NotFoundError(f"复核人不存在: {assign_data.assignee_id}")

        task.assignee_id = assign_data.assignee_id
        task.status = "assigned"
        task.assigned_at = datetime.utcnow()
        task.assigned_by = operator_id
        task.assignment_remark = assign_data.remark
        task.due_date = assign_data.due_date

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Assigned task {task_id} to user {assign_data.assignee_id}")
        return task

    def batch_assign(self, batch_data: BatchAssignRequest, operator_id: Optional[int] = None) -> int:
        assigned = 0
        for task_id in batch_data.task_ids:
            try:
                assign_data = AssignTaskRequest(
                    assignee_id=batch_data.assignee_id,
                    due_date=batch_data.due_date,
                    remark=batch_data.remark,
                )
                self.assign_task(task_id, assign_data, operator_id)
                assigned += 1
            except Exception as e:
                logger.error(f"Failed to assign task {task_id}: {e}")
                continue

        return assigned

    def accept_task(self, task_id: int, operator_id: int) -> ReviewTask:
        task = self._get_task(task_id)

        if task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限接受此任务")

        if task.status != "assigned":
            raise BusinessError(f"任务状态不允许接受: {task.status}")

        task.status = "accepted"
        task.accepted_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} accepted by user {operator_id}")
        return task

    def reject_task(self, task_id: int, operator_id: int, reason: str) -> ReviewTask:
        task = self._get_task(task_id)

        if task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限拒绝此任务")

        if task.status != "assigned":
            raise BusinessError(f"任务状态不允许拒绝: {task.status}")

        task.status = "rejected"
        task.rejected_at = datetime.utcnow()
        task.rejection_reason = reason

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} rejected by user {operator_id}: {reason}")
        return task

    def submit_review(self, task_id: int, record_data: ReviewRecordCreate, operator_id: int) -> ReviewRecord:
        task = self._get_task(task_id)

        if task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限操作此任务")

        if task.status != "accepted":
            raise BusinessError(f"任务状态不允许提交: {task.status}")

        review_record = ReviewRecord(**record_data.model_dump())
        review_record.review_task_id = task_id
        review_record.reviewer_id = operator_id
        review_record.reviewed_at = datetime.utcnow()

        self.db.add(review_record)

        task.status = "completed" if record_data.verdict != "needs_follow_up" else "processing"
        task.completed_at = datetime.utcnow() if record_data.verdict != "needs_follow_up" else None

        if record_data.verdict != "needs_follow_up" and task.anomalies:
            for anomaly in task.anomalies:
                anomaly.status = "confirmed" if record_data.verdict == "confirmed" else "rejected"
                anomaly.is_confirmed = record_data.verdict == "confirmed"
                anomaly.is_false_positive = record_data.verdict == "false_positive"
                anomaly.confirmed_at = datetime.utcnow()
                anomaly.review_comment = record_data.comments

        self.db.commit()
        self.db.refresh(review_record)

        if task.examination_id:
            exam = self.db.query(Examination).filter(Examination.id == task.examination_id).first()
            if exam:
                exam.review_status = "reviewed"

        logger.info(f"Review submitted for task {task_id}: {record_data.verdict}")
        return review_record

    def create_rectification(self, rect_data: RectificationCreate, creator_id: Optional[int] = None) -> Rectification:
        anomaly = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.id == rect_data.anomaly_id,
            AnomalyRecord.is_deleted == False,
        ).first()
        if not anomaly:
            raise NotFoundError(f"异常记录不存在: {rect_data.anomaly_id}")

        if anomaly.correction_status not in ["pending", "failed"]:
            raise BusinessError(f"异常状态不允许创建整改: {anomaly.correction_status}")

        rectification = Rectification(**rect_data.model_dump())
        rectification.created_by = creator_id
        rectification.status = "pending"
        rectification.anomaly_type = anomaly.anomaly_type
        rectification.severity_level = anomaly.severity_level

        if rect_data.hospital_id:
            rectification.hospital_id = rect_data.hospital_id
        elif anomaly.hospital_id:
            rectification.hospital_id = anomaly.hospital_id

        if rect_data.responsible_person_id:
            rectification.responsible_person_id = rect_data.responsible_person_id
        elif anomaly.technician_id:
            rectification.responsible_person_id = anomaly.technician_id

        self.db.add(rectification)

        anomaly.correction_status = "pending_correction"
        anomaly.rectification_id = rectification.id

        self.db.commit()
        self.db.refresh(rectification)

        logger.info(f"Created rectification {rectification.id} for anomaly {rect_data.anomaly_id}")
        return rectification

    def update_rectification(self, rect_id: int, update_data: RectificationUpdate, operator_id: int) -> Rectification:
        rectification = self.db.query(Rectification).filter(
            Rectification.id == rect_id,
            Rectification.is_deleted == False,
        ).first()
        if not rectification:
            raise NotFoundError(f"整改记录不存在: {rect_id}")

        if rectification.responsible_person_id != operator_id and rectification.created_by != operator_id:
            raise ForbiddenError("您没有权限修改此整改记录")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(rectification, key, value)

        if update_data.status == "in_progress":
            rectification.started_at = datetime.utcnow()

        if update_data.status == "submitted":
            rectification.submitted_at = datetime.utcnow()

        if update_data.status == "verified":
            rectification.verified_at = datetime.utcnow()
            rectification.verified_by = operator_id
            rectification.completed_at = datetime.utcnow()

            if rectification.anomaly_id:
                anomaly = self.db.query(AnomalyRecord).filter(AnomalyRecord.id == rectification.anomaly_id).first()
                if anomaly:
                    anomaly.correction_status = "corrected"
                    anomaly.corrected_at = datetime.utcnow()

        if update_data.status == "failed":
            rectification.failed_at = datetime.utcnow()
            rectification.failed_reason = update_data.failure_reason

            if rectification.anomaly_id:
                anomaly = self.db.query(AnomalyRecord).filter(AnomalyRecord.id == rectification.anomaly_id).first()
                if anomaly:
                    anomaly.correction_status = "failed"

        self.db.commit()
        self.db.refresh(rectification)
        return rectification

    def verify_rectification(self, rect_id: int, passed: bool, comment: Optional[str], operator_id: int) -> Rectification:
        rectification = self.db.query(Rectification).filter(
            Rectification.id == rect_id,
            Rectification.is_deleted == False,
        ).first()
        if not rectification:
            raise NotFoundError(f"整改记录不存在: {rect_id}")

        if rectification.status != "submitted":
            raise BusinessError(f"整改状态不允许验收: {rectification.status}")

        rectification.verification_passed = passed
        rectification.verification_comment = comment
        rectification.verified_at = datetime.utcnow()
        rectification.verified_by = operator_id

        if passed:
            rectification.status = "verified"
            rectification.completed_at = datetime.utcnow()
            if rectification.anomaly_id:
                anomaly = self.db.query(AnomalyRecord).filter(AnomalyRecord.id == rectification.anomaly_id).first()
                if anomaly:
                    anomaly.correction_status = "corrected"
                    anomaly.corrected_at = datetime.utcnow()
        else:
            rectification.status = "failed"
            rectification.failed_at = datetime.utcnow()
            if rectification.anomaly_id:
                anomaly = self.db.query(AnomalyRecord).filter(AnomalyRecord.id == rectification.anomaly_id).first()
                if anomaly:
                    anomaly.correction_status = "failed"

        self.db.commit()
        self.db.refresh(rectification)
        return rectification

    def _get_task(self, task_id: int) -> ReviewTask:
        task = self.db.query(ReviewTask).filter(
            ReviewTask.id == task_id,
            ReviewTask.is_deleted == False,
        ).first()
        if not task:
            raise NotFoundError(f"复核任务不存在: {task_id}")
        return task

    def get_task(self, task_id: int, operator_id: Optional[int] = None) -> ReviewTask:
        task = self._get_task(task_id)
        if operator_id and task.assignee_id != operator_id and task.created_by != operator_id:
            # 允许查看但标记是否可操作
            task.can_operate = False
        else:
            task.can_operate = True
        return task

    def list_tasks(
        self,
        filter_params: ReviewTaskFilter,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[ReviewTask], int]:
        query = self.db.query(ReviewTask).filter(ReviewTask.is_deleted == False)

        if filter_params.hospital_id:
            query = query.filter(ReviewTask.hospital_id == filter_params.hospital_id)
        if filter_params.assignee_id:
            query = query.filter(ReviewTask.assignee_id == filter_params.assignee_id)
        if filter_params.created_by:
            query = query.filter(ReviewTask.created_by == filter_params.created_by)
        if filter_params.status:
            query = query.filter(ReviewTask.status == filter_params.status)
        if filter_params.priority:
            query = query.filter(ReviewTask.priority == filter_params.priority)
        if filter_params.task_type:
            query = query.filter(ReviewTask.task_type == filter_params.task_type)
        if filter_params.examination_id:
            query = query.filter(ReviewTask.examination_id == filter_params.examination_id)
        if filter_params.overdue_only:
            query = query.filter(
                ReviewTask.due_date < datetime.utcnow(),
                ReviewTask.status.notin_(["completed", "rejected", "verified"]),
            )
        if filter_params.start_date:
            query = query.filter(ReviewTask.created_at >= filter_params.start_date)
        if filter_params.end_date:
            query = query.filter(ReviewTask.created_at <= filter_params.end_date)

        if filter_params.keyword:
            keyword = f"%{filter_params.keyword}%"
            query = query.filter(
                or_(
                    ReviewTask.title.ilike(keyword),
                    ReviewTask.description.ilike(keyword),
                )
            )

        total = query.count()
        order_column = getattr(ReviewTask, filter_params.sort_by, ReviewTask.created_at)
        order_func = order_column.desc() if filter_params.sort_order == "desc" else order_column.asc()
        tasks = query.order_by(order_func).offset(skip).limit(limit).all()
        return tasks, total

    def list_rectifications(
        self,
        hospital_id: Optional[int] = None,
        status: Optional[str] = None,
        anomaly_id: Optional[int] = None,
        responsible_person_id: Optional[int] = None,
        overdue_only: bool = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Rectification], int]:
        query = self.db.query(Rectification).filter(Rectification.is_deleted == False)

        if hospital_id:
            query = query.filter(Rectification.hospital_id == hospital_id)
        if status:
            query = query.filter(Rectification.status == status)
        if anomaly_id:
            query = query.filter(Rectification.anomaly_id == anomaly_id)
        if responsible_person_id:
            query = query.filter(Rectification.responsible_person_id == responsible_person_id)
        if overdue_only:
            query = query.filter(
                Rectification.due_date < datetime.utcnow(),
                Rectification.status.notin_(["verified", "failed"]),
            )

        total = query.count()
        rectifications = query.order_by(Rectification.created_at.desc()).offset(skip).limit(limit).all()
        return rectifications, total

    def get_review_records(self, task_id: Optional[int] = None, reviewer_id: Optional[int] = None) -> List[ReviewRecord]:
        query = self.db.query(ReviewRecord).filter(ReviewRecord.is_deleted == False)

        if task_id:
            query = query.filter(ReviewRecord.review_task_id == task_id)
        if reviewer_id:
            query = query.filter(ReviewRecord.reviewer_id == reviewer_id)

        return query.order_by(ReviewRecord.reviewed_at.desc()).all()

    def find_available_reviewer(self, hospital_id: int) -> Optional[User]:
        from ..models import user_roles
        subquery = self.db.query(user_roles.c.user_id).join(User).filter(
            User.hospital_id == hospital_id,
            User.is_active == True,
            User.is_deleted == False,
        )
        reviewers = self.db.query(User).filter(
            User.id.in_(subquery),
            User.hospital_id == hospital_id,
            User.is_active == True,
            User.is_deleted == False,
        ).all()

        if not reviewers:
            return None

        reviewer_load = {}
        for reviewer in reviewers:
            load = self.db.query(func.count(ReviewTask.id)).filter(
                ReviewTask.assignee_id == reviewer.id,
                ReviewTask.status.in_(["assigned", "accepted", "processing"]),
                ReviewTask.is_deleted == False,
            ).scalar() or 0
            reviewer_load[reviewer.id] = load

        min_load = min(reviewer_load.values())
        for reviewer in reviewers:
            if reviewer_load[reviewer.id] == min_load:
                return reviewer

        return reviewers[0]

    def get_statistics(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> ReviewStatsResponse:
        task_query = self.db.query(ReviewTask).filter(ReviewTask.is_deleted == False)
        rect_query = self.db.query(Rectification).filter(Rectification.is_deleted == False)

        if hospital_id:
            task_query = task_query.filter(ReviewTask.hospital_id == hospital_id)
            rect_query = rect_query.filter(Rectification.hospital_id == hospital_id)
        if start_date:
            task_query = task_query.filter(ReviewTask.created_at >= start_date)
            rect_query = rect_query.filter(Rectification.created_at >= start_date)
        if end_date:
            task_query = task_query.filter(ReviewTask.created_at <= end_date)
            rect_query = rect_query.filter(Rectification.created_at <= end_date)

        total_tasks = task_query.count()
        pending_assign = task_query.filter(ReviewTask.status == "pending").count()
        assigned = task_query.filter(ReviewTask.status == "assigned").count()
        accepted = task_query.filter(ReviewTask.status == "accepted").count()
        processing = task_query.filter(ReviewTask.status == "processing").count()
        completed = task_query.filter(ReviewTask.status == "completed").count()
        rejected = task_query.filter(ReviewTask.status == "rejected").count()
        verified = task_query.filter(ReviewTask.status == "verified").count()

        total_rectifications = rect_query.count()
        rect_pending = rect_query.filter(Rectification.status == "pending").count()
        rect_in_progress = rect_query.filter(Rectification.status == "in_progress").count()
        rect_submitted = rect_query.filter(Rectification.status == "submitted").count()
        rect_verified = rect_query.filter(Rectification.status == "verified").count()
        rect_failed = rect_query.filter(Rectification.status == "failed").count()

        avg_review_time = None
        completed_tasks_with_time = task_query.filter(
            ReviewTask.status == "completed",
            ReviewTask.accepted_at.isnot(None),
            ReviewTask.completed_at.isnot(None),
        ).all()

        if completed_tasks_with_time:
            total_time = sum(
                (task.completed_at - task.accepted_at).total_seconds()
                for task in completed_tasks_with_time
            )
            avg_review_time = total_time / len(completed_tasks_with_time)

        avg_rect_time = None
        completed_rects_with_time = rect_query.filter(
            Rectification.status == "verified",
            Rectification.started_at.isnot(None),
            Rectification.completed_at.isnot(None),
        ).all()

        if completed_rects_with_time:
            total_time = sum(
                (rect.completed_at - rect.started_at).total_seconds()
                for rect in completed_rects_with_time
            )
            avg_rect_time = total_time / len(completed_rects_with_time)

        now = datetime.utcnow()
        overdue_tasks = task_query.filter(
            ReviewTask.due_date < now,
            ReviewTask.status.notin_(["completed", "rejected", "verified"]),
        ).count()

        overdue_rectifications = rect_query.filter(
            Rectification.due_date < now,
            Rectification.status.notin_(["verified", "failed"]),
        ).count()

        by_priority = {
            "low": task_query.filter(ReviewTask.priority == "low").count(),
            "medium": task_query.filter(ReviewTask.priority == "medium").count(),
            "high": task_query.filter(ReviewTask.priority == "high").count(),
            "urgent": task_query.filter(ReviewTask.priority == "urgent").count(),
        }

        by_type = {
            "manual": task_query.filter(ReviewTask.task_type == "manual").count(),
            "auto_review": task_query.filter(ReviewTask.task_type == "auto_review").count(),
            "spot_check": task_query.filter(ReviewTask.task_type == "spot_check").count(),
            "complaint": task_query.filter(ReviewTask.task_type == "complaint").count(),
        }

        by_verdict = {}
        records = self.db.query(ReviewRecord.verdict, func.count(ReviewRecord.id)).group_by(ReviewRecord.verdict).all()
        for verdict, count in records:
            if verdict:
                by_verdict[verdict] = count

        by_hospital = {}
        if not hospital_id:
            hospital_stats = task_query.with_entities(
                ReviewTask.hospital_id,
                func.count(ReviewTask.id),
            ).group_by(ReviewTask.hospital_id).all()

            for h_id, count in hospital_stats:
                hospital = self.db.query(Hospital).filter(Hospital.id == h_id).first()
                name = hospital.name if hospital else f"Hospital {h_id}"
                by_hospital[name] = count

        return ReviewStatsResponse(
            total_tasks=total_tasks,
            pending_assignment=pending_assign,
            assigned=assigned,
            accepted=accepted,
            processing=processing,
            completed=completed,
            rejected=rejected,
            verified=verified,
            total_rectifications=total_rectifications,
            rect_pending=rect_pending,
            rect_in_progress=rect_in_progress,
            rect_submitted=rect_submitted,
            rect_verified=rect_verified,
            rect_failed=rect_failed,
            completion_rate=calculate_percentage(completed + verified, total_tasks),
            rectification_rate=calculate_percentage(rect_verified, total_rectifications),
            average_review_time_seconds=avg_review_time,
            average_rectification_time_seconds=avg_rect_time,
            overdue_tasks=overdue_tasks,
            overdue_rectifications=overdue_rectifications,
            by_priority=by_priority,
            by_type=by_type,
            by_verdict=by_verdict,
            by_hospital=by_hospital,
        )

    def get_user_workload(self, user_id: int) -> Dict[str, Any]:
        pending_tasks = self.db.query(func.count(ReviewTask.id)).filter(
            ReviewTask.assignee_id == user_id,
            ReviewTask.status.in_(["assigned", "accepted", "processing"]),
            ReviewTask.is_deleted == False,
        ).scalar() or 0

        pending_rects = self.db.query(func.count(Rectification.id)).filter(
            Rectification.responsible_person_id == user_id,
            Rectification.status.in_(["pending", "in_progress", "submitted"]),
            Rectification.is_deleted == False,
        ).scalar() or 0

        completed_tasks_7d = self.db.query(func.count(ReviewTask.id)).filter(
            ReviewTask.assignee_id == user_id,
            ReviewTask.status.in_(["completed", "verified"]),
            ReviewTask.completed_at >= datetime.utcnow() - timedelta(days=7),
            ReviewTask.is_deleted == False,
        ).scalar() or 0

        completed_rects_7d = self.db.query(func.count(Rectification.id)).filter(
            Rectification.responsible_person_id == user_id,
            Rectification.status == "verified",
            Rectification.completed_at >= datetime.utcnow() - timedelta(days=7),
            Rectification.is_deleted == False,
        ).scalar() or 0

        return {
            "user_id": user_id,
            "pending_tasks": pending_tasks,
            "pending_rectifications": pending_rects,
            "completed_tasks_7d": completed_tasks_7d,
            "completed_rectifications_7d": completed_rects_7d,
        }

    def update_task(self, task_id: int, update_data: ReviewTaskUpdate, operator_id: int) -> ReviewTask:
        task = self._get_task(task_id)

        if task.created_by != operator_id and task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限修改此任务")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(task, key, value)

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} updated by user {operator_id}")
        return task

    def escalate_task(self, task_id: int, reason: str, operator_id: int) -> ReviewTask:
        task = self._get_task(task_id)

        if task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限升级此任务")

        if task.status not in ["assigned", "accepted", "processing"]:
            raise BusinessError(f"任务状态不允许升级: {task.status}")

        task.status = "escalated"
        task.escalation_reason = reason
        task.escalated_at = datetime.utcnow()
        task.escalated_by = operator_id

        self.db.commit()
        self.db.refresh(task)

        logger.info(f"Task {task_id} escalated by user {operator_id}: {reason}")
        return task

    def add_review_record(self, task_id: int, record_data: ReviewRecordCreate, operator_id: int) -> ReviewRecord:
        task = self._get_task(task_id)

        if task.assignee_id != operator_id:
            raise ForbiddenError("您没有权限添加复核记录")

        if task.status not in ["accepted", "processing"]:
            raise BusinessError(f"任务状态不允许添加记录: {task.status}")

        review_record = ReviewRecord(**record_data.model_dump())
        review_record.review_task_id = task_id
        review_record.reviewer_id = operator_id
        review_record.reviewed_at = datetime.utcnow()
        review_record.review_round = task.review_count + 1

        self.db.add(review_record)
        task.review_count += 1

        self.db.commit()
        self.db.refresh(review_record)

        logger.info(f"Review record added for task {task_id} by user {operator_id}")
        return review_record

    def get_review_record(self, record_id: int) -> ReviewRecord:
        record = self.db.query(ReviewRecord).filter(
            ReviewRecord.id == record_id,
            ReviewRecord.is_deleted == False,
        ).first()
        if not record:
            raise NotFoundError(f"复核记录不存在: {record_id}")
        return record

    def get_rectification(self, rect_id: int) -> Rectification:
        rectification = self.db.query(Rectification).filter(
            Rectification.id == rect_id,
            Rectification.is_deleted == False,
        ).first()
        if not rectification:
            raise NotFoundError(f"整改记录不存在: {rect_id}")
        return rectification

    def submit_rectification(self, rect_id: int, operator_id: int) -> Rectification:
        rectification = self.get_rectification(rect_id)

        if rectification.responsible_person_id != operator_id:
            raise ForbiddenError("您没有权限提交此整改")

        if rectification.status != "in_progress":
            raise BusinessError(f"整改状态不允许提交: {rectification.status}")

        rectification.status = "submitted"
        rectification.submitted_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(rectification)

        logger.info(f"Rectification {rect_id} submitted by user {operator_id}")
        return rectification

    def reject_rectification(self, rect_id: int, reason: str, operator_id: int) -> Rectification:
        rectification = self.get_rectification(rect_id)

        if rectification.status != "submitted":
            raise BusinessError(f"整改状态不允许拒绝: {rectification.status}")

        rectification.status = "rejected"
        rectification.rejected_at = datetime.utcnow()
        rectification.rejected_by = operator_id
        rectification.rejection_reason = reason

        self.db.commit()
        self.db.refresh(rectification)

        logger.info(f"Rectification {rect_id} rejected by user {operator_id}: {reason}")
        return rectification

    def get_efficiency_statistics(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        task_query = self.db.query(ReviewTask).filter(
            ReviewTask.is_deleted == False,
            ReviewTask.status.in_(["completed", "verified"]),
        )

        if hospital_id:
            task_query = task_query.filter(ReviewTask.hospital_id == hospital_id)
        if start_date:
            task_query = task_query.filter(ReviewTask.completed_at >= start_date)
        if end_date:
            task_query = task_query.filter(ReviewTask.completed_at <= end_date)

        completed_tasks = task_query.all()

        if not completed_tasks:
            return {
                "total_completed": 0,
                "avg_review_time_hours": 0,
                "avg_review_time_days": 0,
                "reviewer_efficiency": [],
                "daily_completion": [],
            }

        total_time = 0
        valid_tasks = 0
        reviewer_times: Dict[int, List[float]] = {}
        daily_completion: Dict[str, int] = {}

        for task in completed_tasks:
            if task.accepted_at and task.completed_at:
                time_diff = (task.completed_at - task.accepted_at).total_seconds()
                total_time += time_diff
                valid_tasks += 1

                if task.assignee_id not in reviewer_times:
                    reviewer_times[task.assignee_id] = []
                reviewer_times[task.assignee_id].append(time_diff)

                day_key = task.completed_at.strftime("%Y-%m-%d")
                daily_completion[day_key] = daily_completion.get(day_key, 0) + 1

        avg_time_seconds = total_time / valid_tasks if valid_tasks > 0 else 0

        reviewer_efficiency = []
        for reviewer_id, times in reviewer_times.items():
            user = self.db.query(User).filter(User.id == reviewer_id).first()
            reviewer_name = user.name if user else f"User {reviewer_id}"
            avg_time = sum(times) / len(times) if times else 0
            reviewer_efficiency.append({
                "reviewer_id": reviewer_id,
                "reviewer_name": reviewer_name,
                "completed_count": len(times),
                "avg_review_time_hours": round(avg_time / 3600, 2),
                "avg_review_time_days": round(avg_time / 86400, 2),
            })

        daily_list = [
            {"date": date_str, "count": count}
            for date_str, count in sorted(daily_completion.items())
        ]

        return {
            "total_completed": valid_tasks,
            "avg_review_time_hours": round(avg_time_seconds / 3600, 2),
            "avg_review_time_days": round(avg_time_seconds / 86400, 2),
            "reviewer_efficiency": reviewer_efficiency,
            "daily_completion": daily_list,
        }

    def get_rectification_statistics(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        rect_query = self.db.query(Rectification).filter(Rectification.is_deleted == False)

        if hospital_id:
            rect_query = rect_query.filter(Rectification.hospital_id == hospital_id)
        if start_date:
            rect_query = rect_query.filter(Rectification.created_at >= start_date)
        if end_date:
            rect_query = rect_query.filter(Rectification.created_at <= end_date)

        total = rect_query.count()
        pending = rect_query.filter(Rectification.status == "pending").count()
        in_progress = rect_query.filter(Rectification.status == "in_progress").count()
        submitted = rect_query.filter(Rectification.status == "submitted").count()
        verified = rect_query.filter(Rectification.status == "verified").count()
        rejected = rect_query.filter(Rectification.status == "rejected").count()
        failed = rect_query.filter(Rectification.status == "failed").count()

        now = datetime.utcnow()
        overdue = rect_query.filter(
            Rectification.deadline < now,
            Rectification.status.notin_(["verified", "failed"]),
        ).count()

        completed_rects = rect_query.filter(
            Rectification.status == "verified",
            Rectification.started_at.isnot(None),
            Rectification.completed_at.isnot(None),
        ).all()

        avg_completion_days = None
        if completed_rects:
            total_days = sum(
                (rect.completed_at - rect.started_at).total_seconds() / 86400
                for rect in completed_rects
            )
            avg_completion_days = round(total_days / len(completed_rects), 2)

        by_priority = {
            "low": rect_query.filter(Rectification.priority == "low").count(),
            "medium": rect_query.filter(Rectification.priority == "medium").count(),
            "high": rect_query.filter(Rectification.priority == "high").count(),
            "urgent": rect_query.filter(Rectification.priority == "urgent").count(),
        }

        return {
            "total": total,
            "pending": pending,
            "in_progress": in_progress,
            "submitted": submitted,
            "verified": verified,
            "rejected": rejected,
            "failed": failed,
            "overdue": overdue,
            "completion_rate": calculate_percentage(verified, total),
            "avg_completion_days": avg_completion_days,
            "by_priority": by_priority,
        }

    def get_statistics_by_hospital(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        hospitals = self.db.query(Hospital).filter(Hospital.is_deleted == False).all()

        result = []
        for hospital in hospitals:
            stats = self.get_statistics(
                hospital_id=hospital.id,
                start_date=start_date,
                end_date=end_date,
            )
            result.append({
                "hospital_id": hospital.id,
                "hospital_name": hospital.name,
                **stats.model_dump(),
            })

        return result
