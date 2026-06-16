from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import random

from ..models import (
    AnomalyRecord,
    SimilarityCheck,
    Examination,
    ImageQuality,
    BIRADSReport,
    QualityRule,
    Hospital,
)
from ..schemas import (
    AnomalyRecordCreate,
    AnomalyRecordUpdate,
    AnomalyStatsResponse,
    SimilarityCheckCreate,
    BatchAnomalyDetectRequest,
    BatchAnomalyDetectResult,
)
from ..core.exceptions import NotFoundError, BusinessError
from ..core.logger import get_logger
from ..core.utils import (
    calculate_text_similarity,
    extract_keywords,
    clean_text,
    calculate_percentage,
    get_date_range,
    safe_divide,
)
from ..config import settings
from .quality_rule_service import QualityRuleService
from .examination_service import ExaminationService

logger = get_logger(__name__)


class QualityChecker:
    def __init__(self, rule_service: QualityRuleService):
        self.rule_service = rule_service

    def check_position_integrity(self, exam: Examination) -> Optional[Dict[str, Any]]:
        if not exam.views or not exam.laterality:
            return None

        required = 4 if exam.laterality.upper() == "BILATERAL" else 2
        actual = exam.view_count or 0
        views_list = [v.strip().upper() for v in (exam.views or "").split(",")]

        if exam.laterality.upper() == "BILATERAL":
            required_views = ["LCC", "RCC", "LMLO", "RMLO"]
        else:
            side = exam.laterality.upper()[0]
            required_views = [f"{side}CC", f"{side}MLO"]

        missing = [v for v in required_views if v not in views_list]

        if missing or actual < required:
            return {
                "anomaly_type": "position",
                "anomaly_category": "incomplete",
                "description": f"体位不完整，缺失体位: {', '.join(missing)}",
                "severity_level": "high" if missing else "medium",
                "risk_score": 8 if missing else 5,
                "detail_data": {
                    "required": required_views,
                    "actual": views_list,
                    "missing": missing,
                    "required_count": required,
                    "actual_count": actual,
                },
                "affected_fields": ["views", "view_count"],
                "correction_suggestion": "请补充缺失的投照体位",
            }
        return None

    def check_image_quality(self, exam: Examination) -> Optional[Dict[str, Any]]:
        if not exam.image_quality:
            return None

        iq = exam.image_quality
        issues = []
        affected_fields = []

        if iq.overall_score is not None and iq.overall_score < 60:
            issues.append(f"总体图像质量评分偏低: {iq.overall_score}/100")
            affected_fields.append("overall_score")

        if iq.contrast_score is not None and iq.contrast_score < 50:
            issues.append(f"对比度评分偏低: {iq.contrast_score}")
            affected_fields.append("contrast_score")

        if iq.noise_score is not None and iq.noise_score < 50:
            issues.append(f"噪声评分偏低: {iq.noise_score}")
            affected_fields.append("noise_score")

        if iq.sharpness_score is not None and iq.sharpness_score < 50:
            issues.append(f"锐利度评分偏低: {iq.sharpness_score}")
            affected_fields.append("sharpness_score")

        if iq.artifacts and iq.artifacts.lower() in ["严重", "较多", "明显"]:
            issues.append(f"存在明显伪影: {iq.artifacts}")
            affected_fields.append("artifacts")

        if not iq.is_quality_acceptable:
            issues.append("图像质量不符合标准要求")
            affected_fields.append("is_quality_acceptable")

        if issues:
            severity = "high" if iq.overall_score and iq.overall_score < 40 else "medium"
            risk_score = 7 if severity == "high" else 5
            return {
                "anomaly_type": "quality",
                "anomaly_category": "low_quality",
                "description": "; ".join(issues),
                "severity_level": severity,
                "risk_score": risk_score,
                "detail_data": {
                    "overall_score": iq.overall_score,
                    "contrast_score": iq.contrast_score,
                    "noise_score": iq.noise_score,
                    "sharpness_score": iq.sharpness_score,
                    "issues": issues,
                },
                "affected_fields": affected_fields,
                "correction_suggestion": "建议重新拍摄，调整曝光参数",
            }
        return None

    def check_dose(self, exam: Examination) -> Optional[Dict[str, Any]]:
        issues = []
        if exam.average_glandular_dose is not None:
            if exam.average_glandular_dose > 3.0:
                issues.append(f"平均腺体剂量偏高: {exam.average_glandular_dose} mGy")
            elif exam.average_glandular_dose < 0.5:
                issues.append(f"平均腺体剂量偏低: {exam.average_glandular_dose} mGy")

        if exam.compression_pressure is not None:
            if exam.compression_pressure > 200:
                issues.append(f"压迫压力过高: {exam.compression_pressure} N")
            elif exam.compression_pressure < 80:
                issues.append(f"压迫压力不足: {exam.compression_pressure} N")

        if issues:
            return {
                "anomaly_type": "quality",
                "anomaly_category": "dose_issue",
                "description": "; ".join(issues),
                "severity_level": "medium",
                "risk_score": 4,
                "detail_data": {
                    "average_glandular_dose": exam.average_glandular_dose,
                    "compression_pressure": exam.compression_pressure,
                    "dose_area_product": exam.dose_area_product,
                },
                "affected_fields": ["average_glandular_dose", "compression_pressure"],
                "correction_suggestion": "请优化投照参数，确保剂量在合理范围内",
            }
        return None

    def check_report_standard(self, exam: Examination) -> Optional[Dict[str, Any]]:
        if not exam.birads_report:
            return None

        br = exam.birads_report
        issues = []
        affected_fields = []

        if br.density_check_result == "fail":
            issues.append(f"乳腺密度填写不规范: {br.breast_density}")
            affected_fields.append("breast_density")

        if br.birads_check_result == "fail":
            issues.append(f"BI-RADS分类填写不规范: {br.birads_classification}")
            affected_fields.append("birads_classification")

        if not br.is_report_complete:
            missing_fields = []
            if not br.birads_classification:
                missing_fields.append("BI-RADS分类")
            if not br.findings_summary:
                missing_fields.append("征象描述")
            if not br.impression:
                missing_fields.append("诊断印象")
            issues.append(f"报告不完整，缺失: {', '.join(missing_fields)}")
            affected_fields.extend(missing_fields)

        if br.description_quality_score is not None and br.description_quality_score < 60:
            issues.append(f"征象描述质量评分偏低: {br.description_quality_score}/100")
            affected_fields.append("findings_summary")

        if br.mass_present and not br.mass_description:
            issues.append("报告提示有肿块但缺乏详细描述")
            affected_fields.append("mass_description")

        if br.calcification_present and not br.calcification_description:
            issues.append("报告提示有钙化但缺乏详细描述")
            affected_fields.append("calcification_description")

        if br.findings_summary:
            findings = br.findings_summary.strip()
            if len(findings) < 5:
                issues.append("征象描述内容过短，描述不充分")
                affected_fields.append("findings_summary")
            keywords = extract_keywords(findings, top_k=10)
            if len(keywords) < 2:
                issues.append("征象描述缺乏有效医学关键词")
                if "findings_summary" not in affected_fields:
                    affected_fields.append("findings_summary")

        if br.impression:
            impression = br.impression.strip()
            if len(impression) < 3:
                issues.append("诊断印象内容过短")
                affected_fields.append("impression")

        if br.birads_classification and br.findings_summary:
            birads_upper = br.birads_classification.upper()
            findings_lower = br.findings_summary.lower()
            if birads_upper in ["1", "2"]:
                positive_keywords = ["肿块", "钙化", "结节", "异常", "占位", "病变", "扭曲", "不对称"]
                found_positive = [kw for kw in positive_keywords if kw in br.findings_summary]
                if found_positive:
                    issues.append(f"BI-RADS {br.birads_classification}（阴性）报告中包含阳性描述词: {', '.join(found_positive)}")
                    affected_fields.extend(["birads_classification", "findings_summary"])
            elif birads_upper in ["4", "4A", "4B", "4C", "5", "6"]:
                negative_patterns = ["未见明显异常", "未见异常", "未见明确异常", "未见明显占位", "未见明显病变"]
                found_negative = [p for p in negative_patterns if p in br.findings_summary]
                if found_negative:
                    issues.append(f"BI-RADS {br.birads_classification}（阳性）报告中包含阴性描述: {', '.join(found_negative)}")
                    affected_fields.extend(["birads_classification", "findings_summary"])

        if issues:
            severity = "high" if len(issues) >= 3 else "medium"
            risk_score = 8 if severity == "high" else 5
            return {
                "anomaly_type": "report",
                "anomaly_category": "non_standard",
                "description": "; ".join(issues),
                "severity_level": severity,
                "risk_score": risk_score,
                "detail_data": {
                    "breast_density": br.breast_density,
                    "birads_classification": br.birads_classification,
                    "density_check_result": br.density_check_result,
                    "birads_check_result": br.birads_check_result,
                    "is_report_complete": br.is_report_complete,
                    "description_quality_score": br.description_quality_score,
                    "issues": issues,
                },
                "affected_fields": list(set(affected_fields)),
                "correction_suggestion": "请按照集团标准规范填写报告",
            }
        return None


class SimilarityChecker:
    HIGH_DISCREPANCY_THRESHOLD = 0.3
    DISCREPANCY_THRESHOLD = 0.5

    def __init__(self, db: Session):
        self.db = db
        self.threshold = settings.QC_SIMILARITY_THRESHOLD

    def find_similar_reports(
        self,
        exam: Examination,
        hospital_id: Optional[int] = None,
        limit: int = 5,
    ) -> List[Tuple[Examination, float, Dict[str, Any]]]:
        if not exam.birads_report or not exam.birads_report.findings_summary:
            return []

        source_findings = clean_text(exam.birads_report.findings_summary or "")
        source_impression = clean_text(exam.birads_report.impression or "")
        source_birads = exam.birads_report.birads_classification

        if not source_birads:
            return []

        query = self.db.query(Examination).join(BIRADSReport).filter(
            Examination.id != exam.id,
            Examination.is_deleted == False,
            BIRADSReport.is_deleted == False,
            BIRADSReport.birads_classification == source_birads,
            or_(
                BIRADSReport.findings_summary.isnot(None),
                BIRADSReport.impression.isnot(None),
            ),
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)

        if exam.examination_date:
            date_from = exam.examination_date - timedelta(days=180)
            date_to = exam.examination_date + timedelta(days=180)
            query = query.filter(
                Examination.examination_date >= date_from,
                Examination.examination_date <= date_to,
            )

        candidate_reports = []
        for target_exam in query.limit(limit * 10).all():
            if not target_exam.birads_report:
                continue

            target_findings = clean_text(target_exam.birads_report.findings_summary or "")
            target_impression = clean_text(target_exam.birads_report.impression or "")

            if not target_findings and not target_impression:
                continue

            findings_sim = 0.0
            impression_sim = 0.0
            sim_count = 0

            if source_findings and target_findings:
                findings_sim = calculate_text_similarity(source_findings, target_findings, method="cosine")
                sim_count += 1

            if source_impression and target_impression:
                impression_sim = calculate_text_similarity(source_impression, target_impression, method="cosine")
                sim_count += 1

            if sim_count == 0:
                continue

            overall_similarity = (findings_sim + impression_sim) / sim_count if sim_count > 0 else 0.0

            field_sims = self._calculate_field_similarities(exam.birads_report, target_exam.birads_report)

            source_combined = f"{source_findings} {source_impression}".strip()
            target_combined = f"{target_findings} {target_impression}".strip()

            common_findings = self._find_common_findings(source_combined, target_combined)
            differing_findings = self._find_differing_findings(source_combined, target_combined)

            differing_fields = []
            if findings_sim < self.DISCREPANCY_THRESHOLD:
                differing_fields.append("findings_summary")
            if impression_sim < self.DISCREPANCY_THRESHOLD:
                differing_fields.append("impression")
            for field_name, sim_val in field_sims.items():
                if sim_val < self.DISCREPANCY_THRESHOLD:
                    differing_fields.append(field_name)

            detail = {
                "field_similarities": field_sims,
                "findings_similarity": findings_sim,
                "impression_similarity": impression_sim,
                "common_findings": common_findings,
                "differing_findings": differing_findings,
                "differing_fields": differing_fields,
                "description1": exam.birads_report.findings_summary or "",
                "description2": target_exam.birads_report.findings_summary or "",
                "processed_text1": source_findings,
                "processed_text2": target_findings,
                "keywords1": extract_keywords(source_combined, top_k=30),
                "keywords2": extract_keywords(target_combined, top_k=30),
                "common_keywords": common_findings,
            }

            candidate_reports.append((target_exam, overall_similarity, detail))

        candidate_reports.sort(key=lambda x: x[1])
        return candidate_reports[:limit]

    def _calculate_field_similarities(self, source: BIRADSReport, target: BIRADSReport) -> Dict[str, float]:
        sims = {}

        if source.breast_density and target.breast_density:
            sims["density"] = 1.0 if source.breast_density == target.breast_density else 0.0

        sims["mass_present"] = 1.0 if source.mass_present == target.mass_present else 0.0
        sims["calcification_present"] = 1.0 if source.calcification_present == target.calcification_present else 0.0
        sims["architectural_distortion"] = 1.0 if source.architectural_distortion == target.architectural_distortion else 0.0
        sims["asymmetry"] = 1.0 if source.asymmetry == target.asymmetry else 0.0

        if source.findings_summary and target.findings_summary:
            sims["findings"] = calculate_text_similarity(source.findings_summary, target.findings_summary)

        if source.impression and target.impression:
            sims["impression"] = calculate_text_similarity(source.impression, target.impression)

        return sims

    def _find_common_findings(self, text1: str, text2: str) -> List[str]:
        keywords1 = set(extract_keywords(text1, top_k=30))
        keywords2 = set(extract_keywords(text2, top_k=30))
        common = keywords1 & keywords2
        return list(common)[:10]

    def _find_differing_findings(self, text1: str, text2: str) -> List[str]:
        keywords1 = set(extract_keywords(text1, top_k=30))
        keywords2 = set(extract_keywords(text2, top_k=30))
        differing = (keywords1 - keywords2) | (keywords2 - keywords1)
        return list(differing)[:10]

    def check_description_consistency(
        self,
        exam: Examination,
        target_exam: Examination,
    ) -> SimilarityCheck:
        if not exam.birads_report or not target_exam.birads_report:
            return SimilarityCheck(
                examination_id=exam.id,
                target_report_id=target_exam.birads_report.id if target_exam.birads_report else 0,
                comparison_type="description_consistency",
                similarity_score=0.0,
                similarity_threshold=self.DISCREPANCY_THRESHOLD,
                is_suspicious=False,
                check_method="text_similarity",
                check_result="normal",
                hospital_id=exam.hospital_id,
                doctor_id=exam.doctor_id,
                notes="缺少报告数据，无法进行一致性检查",
            )

        source_findings = clean_text(exam.birads_report.findings_summary or "")
        source_impression = clean_text(exam.birads_report.impression or "")
        target_findings = clean_text(target_exam.birads_report.findings_summary or "")
        target_impression = clean_text(target_exam.birads_report.impression or "")

        findings_sim = 0.0
        impression_sim = 0.0
        sim_count = 0

        if source_findings and target_findings:
            findings_sim = calculate_text_similarity(source_findings, target_findings, method="cosine")
            sim_count += 1

        if source_impression and target_impression:
            impression_sim = calculate_text_similarity(source_impression, target_impression, method="cosine")
            sim_count += 1

        field_sims = self._calculate_field_similarities(exam.birads_report, target_exam.birads_report)
        overall_score = (findings_sim + impression_sim) / sim_count if sim_count > 0 else (
            sum(field_sims.values()) / len(field_sims) if field_sims else 0.0
        )

        is_suspicious = overall_score < self.DISCREPANCY_THRESHOLD

        source_combined = f"{source_findings} {source_impression}".strip()
        target_combined = f"{target_findings} {target_impression}".strip()

        common_findings = self._find_common_findings(source_combined, target_combined)
        differing_findings = self._find_differing_findings(source_combined, target_combined)

        check_result = "suspicious" if is_suspicious else "normal"
        notes = ""
        if is_suspicious:
            notes = f"同 BI-RADS {exam.birads_report.birads_classification} 分类报告描述差异过大"

        check = SimilarityCheck(
            examination_id=exam.id,
            target_report_id=target_exam.birads_report.id,
            comparison_type="description_consistency",
            similarity_score=overall_score,
            similarity_threshold=self.DISCREPANCY_THRESHOLD,
            is_suspicious=is_suspicious,
            field_similarities=field_sims,
            common_findings=common_findings,
            differing_findings=differing_findings,
            description1=exam.birads_report.findings_summary or "",
            description2=target_exam.birads_report.findings_summary or "",
            processed_text1=source_findings,
            processed_text2=target_findings,
            keywords1=extract_keywords(source_combined, top_k=30),
            keywords2=extract_keywords(target_combined, top_k=30),
            common_keywords=common_findings,
            check_method="text_similarity",
            check_result=check_result,
            notes=notes,
            hospital_id=exam.hospital_id,
            doctor_id=exam.doctor_id,
        )
        return check


class AnomalyDetectionService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_service = QualityRuleService(db)
        self.quality_checker = QualityChecker(self.rule_service)
        self.similarity_checker = SimilarityChecker(db)
        self.exam_service = ExaminationService(db)

    def detect_anomalies(self, exam: Examination, auto_create_review: bool = False) -> List[AnomalyRecord]:
        anomalies = []
        similarity_checks_to_add = []

        position_anomaly = self.quality_checker.check_position_integrity(exam)
        if position_anomaly:
            anomaly = self._create_anomaly_record(exam, position_anomaly)
            anomalies.append(anomaly)

        quality_anomaly = self.quality_checker.check_image_quality(exam)
        if quality_anomaly:
            anomaly = self._create_anomaly_record(exam, quality_anomaly)
            anomalies.append(anomaly)

        dose_anomaly = self.quality_checker.check_dose(exam)
        if dose_anomaly:
            anomaly = self._create_anomaly_record(exam, dose_anomaly)
            anomalies.append(anomaly)

        report_anomaly = self.quality_checker.check_report_standard(exam)
        if report_anomaly:
            anomaly = self._create_anomaly_record(exam, report_anomaly)
            anomalies.append(anomaly)

        if exam.birads_report and exam.birads_report.birads_classification:
            discrepant_reports = self.similarity_checker.find_similar_reports(exam, exam.hospital_id, limit=3)
            for target, score, detail in discrepant_reports:
                check = self.similarity_checker.check_description_consistency(exam, target)
                similarity_checks_to_add.append(check)

                if check.is_suspicious:
                    severity_level = "high" if score < SimilarityChecker.HIGH_DISCREPANCY_THRESHOLD else "medium"
                    risk_score = 8 if severity_level == "high" else 6
                    anomaly_type = "report_consistency" if score < SimilarityChecker.HIGH_DISCREPANCY_THRESHOLD else "description_discrepancy"

                    consistency_anomaly_data = {
                        "anomaly_type": anomaly_type,
                        "anomaly_category": "description_inconsistency",
                        "description": f"同 BI-RADS {exam.birads_report.birads_classification} 分类报告描述差异过大，与检查 {target.accession_number} 相似度为 {score:.2f}",
                        "severity_level": severity_level,
                        "risk_score": risk_score,
                        "detail_data": {
                            "similarity_score": score,
                            "target_exam_id": target.id,
                            "target_accession": target.accession_number,
                            "target_birads_classification": target.birads_report.birads_classification if target.birads_report else None,
                            "field_similarities": detail.get("field_similarities", {}),
                            "differing_fields": detail.get("differing_fields", []),
                            "common_findings": detail.get("common_findings", []),
                            "differing_findings": detail.get("differing_findings", []),
                        },
                        "affected_fields": detail.get("differing_fields", ["findings_summary", "impression"]),
                        "correction_suggestion": "请核实报告描述的准确性和一致性，相同BI-RADS分类的报告描述不应有显著差异",
                    }
                    anomaly = self._create_anomaly_record(exam, consistency_anomaly_data)
                    anomalies.append(anomaly)

        rules = self.rule_service.get_active_rules(hospital_id=exam.hospital_id)
        for rule in rules:
            passed, detail = self.rule_service.apply_rule_to_examination(rule, exam)
            self.rule_service.update_rule_stats(rule.id, passed)
            if not passed:
                anomaly_data = {
                    "anomaly_type": rule.rule_type,
                    "anomaly_category": rule.category.code if rule.category else None,
                    "description": f"违反规则: {rule.name}",
                    "severity_level": rule.severity_level,
                    "risk_score": rule.risk_score,
                    "detail_data": detail,
                    "affected_fields": [rule.rule_params.get("field")] if rule.rule_params else [],
                    "correction_suggestion": rule.description,
                }
                anomaly = self._create_anomaly_record(exam, anomaly_data, rule_id=rule.id)
                anomalies.append(anomaly)

        self.db.add_all(anomalies)
        if similarity_checks_to_add:
            self.db.add_all(similarity_checks_to_add)
        self.db.commit()

        for anomaly in anomalies:
            self.db.refresh(anomaly)

        if auto_create_review and anomalies:
            self._auto_create_review_task(exam, anomalies)

        exam.status = "anomaly_checked"
        self.db.commit()

        logger.info(f"Detected {len(anomalies)} anomalies for exam {exam.accession_number}")
        return anomalies

    def _create_anomaly_record(
        self,
        exam: Examination,
        anomaly_data: Dict[str, Any],
        rule_id: Optional[int] = None,
    ) -> AnomalyRecord:
        anomaly = AnomalyRecord(
            examination_id=exam.id,
            rule_id=rule_id,
            anomaly_type=anomaly_data["anomaly_type"],
            anomaly_category=anomaly_data.get("anomaly_category"),
            severity_level=anomaly_data.get("severity_level", "medium"),
            risk_score=anomaly_data.get("risk_score", 5),
            description=anomaly_data["description"],
            detail_data=anomaly_data.get("detail_data"),
            affected_fields=anomaly_data.get("affected_fields"),
            correction_suggestion=anomaly_data.get("correction_suggestion"),
            detected_at=datetime.utcnow(),
            detected_by="system",
            detection_method="auto",
            status="pending",
            is_confirmed=False,
            is_false_positive=False,
            correction_status="pending",
            hospital_id=exam.hospital_id,
            equipment_id=exam.equipment_id,
            technician_id=exam.technician_id,
            doctor_id=exam.doctor_id,
        )
        return anomaly

    def _auto_create_review_task(self, exam: Examination, anomalies: List[AnomalyRecord]):
        try:
            from .review_service import ReviewService
            review_service = ReviewService(self.db)

            has_high_severity = any(a.severity_level == "high" for a in anomalies)
            should_auto_review = has_high_severity or random.random() < settings.QC_AUTO_REVIEW_RATIO

            if should_auto_review and exam.hospital_id:
                assignee = review_service.find_available_reviewer(exam.hospital_id)
                if assignee:
                    anomaly_ids = [a.id for a in anomalies]
                    task_data = {
                        "hospital_id": exam.hospital_id,
                        "examination_id": exam.id,
                        "assignee_id": assignee.id,
                        "task_type": "auto_review",
                        "priority": "high" if has_high_severity else "medium",
                        "title": f"自动复核: {exam.accession_number}",
                        "description": f"系统检测到{len(anomalies)}个异常，请复核",
                        "requirement": "请检查异常记录，确认问题并给出整改建议",
                        "anomaly_ids": anomaly_ids,
                    }
                    from ..schemas import ReviewTaskCreate
                    review_service.create_task(ReviewTaskCreate(**task_data), creator_id=None)
                    logger.info(f"Auto-created review task for exam {exam.accession_number}")
        except Exception as e:
            logger.error(f"Failed to auto-create review task: {e}")

    def batch_detect(self, request: BatchAnomalyDetectRequest) -> BatchAnomalyDetectResult:
        import time
        start_time = time.time()

        exams = self.db.query(Examination).filter(
            Examination.id.in_(request.examination_ids),
            Examination.is_deleted == False,
        ).all()

        all_anomalies: List[AnomalyRecord] = []
        review_task_ids: List[int] = []

        for exam in exams:
            try:
                anomalies = self.detect_anomalies(exam, auto_create_review=request.auto_create_review_task)
                all_anomalies.extend(anomalies)
            except Exception as e:
                logger.error(f"Anomaly detection failed for exam {exam.id}: {e}")

        execution_time = (time.time() - start_time) * 1000

        return BatchAnomalyDetectResult(
            total_processed=len(exams),
            anomaly_count=len(all_anomalies),
            anomaly_records=all_anomalies,
            review_task_ids=review_task_ids,
            execution_time_ms=execution_time,
        )

    def run_periodic_detection(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> int:
        query = self.db.query(Examination).filter(
            Examination.is_deleted == False,
            Examination.status.in_(["qa_completed", "received"]),
        )

        if hospital_id:
            query = query.filter(Examination.hospital_id == hospital_id)
        if start_date:
            query = query.filter(Examination.examination_date >= start_date)
        if end_date:
            query = query.filter(Examination.examination_date <= end_date)

        exams = query.all()
        total_anomalies = 0

        for exam in exams:
            try:
                anomalies = self.detect_anomalies(exam)
                total_anomalies += len(anomalies)
            except Exception as e:
                logger.error(f"Periodic detection failed for exam {exam.id}: {e}")

        logger.info(f"Periodic detection completed: {len(exams)} exams, {total_anomalies} anomalies")
        return total_anomalies

    def check_similarity(self, exam_id: int) -> List[SimilarityCheck]:
        exam = self.db.query(Examination).filter(
            Examination.id == exam_id,
            Examination.is_deleted == False,
        ).first()
        if not exam:
            raise NotFoundError(f"检查不存在: {exam_id}")

        discrepant_reports = self.similarity_checker.find_similar_reports(exam, exam.hospital_id)
        checks = []

        for target, score, detail in discrepant_reports:
            check = self.similarity_checker.check_description_consistency(exam, target)
            self.db.add(check)
            checks.append(check)

            if check.is_suspicious:
                severity_level = "high" if score < SimilarityChecker.HIGH_DISCREPANCY_THRESHOLD else "medium"
                risk_score = 8 if severity_level == "high" else 6
                anomaly_type = "report_consistency" if score < SimilarityChecker.HIGH_DISCREPANCY_THRESHOLD else "description_discrepancy"

                anomaly_data = {
                    "anomaly_type": anomaly_type,
                    "anomaly_category": "description_inconsistency",
                    "description": f"同 BI-RADS {exam.birads_report.birads_classification if exam.birads_report else 'N/A'} 分类报告描述差异过大，与检查 {target.accession_number} 相似度为 {score:.2f}",
                    "severity_level": severity_level,
                    "risk_score": risk_score,
                    "detail_data": {
                        "similarity_score": score,
                        "target_exam_id": target.id,
                        "target_accession": target.accession_number,
                        "target_birads_classification": target.birads_report.birads_classification if target.birads_report else None,
                        "field_similarities": detail.get("field_similarities", {}),
                        "differing_fields": detail.get("differing_fields", []),
                        "common_findings": detail.get("common_findings", []),
                        "differing_findings": detail.get("differing_findings", []),
                        "findings_similarity": detail.get("findings_similarity"),
                        "impression_similarity": detail.get("impression_similarity"),
                    },
                    "affected_fields": detail.get("differing_fields", ["findings_summary", "impression"]),
                    "correction_suggestion": "请核实报告描述的准确性和一致性，相同BI-RADS分类的报告描述不应有显著差异",
                }
                anomaly = self._create_anomaly_record(exam, anomaly_data)
                self.db.add(anomaly)

        self.db.commit()
        return checks

    def get_anomaly(
        self,
        anomaly_id: int,
    ) -> AnomalyRecord:
        anomaly = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.id == anomaly_id,
            AnomalyRecord.is_deleted == False,
        ).first()
        if not anomaly:
            raise NotFoundError(f"异常记录不存在: {anomaly_id}")
        return anomaly

    def list_anomalies(
        self,
        hospital_id: Optional[int] = None,
        equipment_id: Optional[int] = None,
        technician_id: Optional[int] = None,
        doctor_id: Optional[int] = None,
        anomaly_type: Optional[str] = None,
        severity_level: Optional[str] = None,
        status: Optional[str] = None,
        is_confirmed: Optional[bool] = None,
        is_false_positive: Optional[bool] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[AnomalyRecord], int]:
        query = self.db.query(AnomalyRecord).filter(AnomalyRecord.is_deleted == False)

        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)
        if equipment_id:
            query = query.filter(AnomalyRecord.equipment_id == equipment_id)
        if technician_id:
            query = query.filter(AnomalyRecord.technician_id == technician_id)
        if doctor_id:
            query = query.filter(AnomalyRecord.doctor_id == doctor_id)
        if anomaly_type:
            query = query.filter(AnomalyRecord.anomaly_type == anomaly_type)
        if severity_level:
            query = query.filter(AnomalyRecord.severity_level == severity_level)
        if status:
            query = query.filter(AnomalyRecord.status == status)
        if is_confirmed is not None:
            query = query.filter(AnomalyRecord.is_confirmed == is_confirmed)
        if is_false_positive is not None:
            query = query.filter(AnomalyRecord.is_false_positive == is_false_positive)
        if start_date:
            query = query.filter(AnomalyRecord.detected_at >= start_date)
        if end_date:
            query = query.filter(AnomalyRecord.detected_at <= end_date)

        total = query.count()
        anomalies = query.order_by(AnomalyRecord.detected_at.desc()).offset(skip).limit(limit).all()
        return anomalies, total

    def update_anomaly(self, anomaly_id: int, update_data: AnomalyRecordUpdate) -> AnomalyRecord:
        anomaly = self.get_anomaly(anomaly_id)
        update_dict = update_data.model_dump(exclude_unset=True)

        for key, value in update_dict.items():
            setattr(anomaly, key, value)

        if update_data.is_confirmed:
            anomaly.confirmed_at = datetime.utcnow()

        if update_data.status == "corrected":
            anomaly.corrected_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(anomaly)
        return anomaly

    def get_statistics(
        self,
        hospital_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> AnomalyStatsResponse:
        query = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == False,
        )

        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)
        if start_date:
            query = query.filter(AnomalyRecord.detected_at >= start_date)
        if end_date:
            query = query.filter(AnomalyRecord.detected_at <= end_date)

        total = query.count()
        pending = query.filter(AnomalyRecord.status == "pending").count()
        confirmed = query.filter(AnomalyRecord.is_confirmed == True).count()
        false_positive = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.is_deleted == False,
            AnomalyRecord.is_false_positive == True,
        ).count()

        position_count = query.filter(AnomalyRecord.anomaly_type == "position").count()
        quality_count = query.filter(AnomalyRecord.anomaly_type == "quality").count()
        report_count = query.filter(AnomalyRecord.anomaly_type == "report").count()
        similarity_count = query.filter(AnomalyRecord.anomaly_type == "similarity").count()
        report_consistency_count = query.filter(AnomalyRecord.anomaly_type == "report_consistency").count()
        description_discrepancy_count = query.filter(AnomalyRecord.anomaly_type == "description_discrepancy").count()

        critical = query.filter(AnomalyRecord.severity_level == "critical").count()
        high = query.filter(AnomalyRecord.severity_level == "high").count()
        medium = query.filter(AnomalyRecord.severity_level == "medium").count()
        low = query.filter(AnomalyRecord.severity_level == "low").count()

        by_hospital = {}
        by_type = {
            "position": position_count,
            "quality": quality_count,
            "report": report_count,
            "similarity": similarity_count,
            "report_consistency": report_consistency_count,
            "description_discrepancy": description_discrepancy_count,
        }
        by_severity = {
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
        }

        if not hospital_id:
            hospital_stats = self.db.query(
                AnomalyRecord.hospital_id,
                func.count(AnomalyRecord.id),
            ).filter(
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
            ).group_by(AnomalyRecord.hospital_id).all()

            for h_id, count in hospital_stats:
                hospital = self.db.query(Hospital).filter(Hospital.id == h_id).first()
                name = hospital.name if hospital else f"Hospital {h_id}"
                by_hospital[name] = count

        trend_data = self._get_trend_data(hospital_id, start_date, end_date)

        return AnomalyStatsResponse(
            total_count=total,
            pending_count=pending,
            confirmed_count=confirmed,
            false_positive_count=false_positive,
            position_anomaly_count=position_count,
            quality_anomaly_count=quality_count,
            report_anomaly_count=report_count,
            similarity_anomaly_count=similarity_count,
            report_consistency_anomaly_count=report_consistency_count,
            description_discrepancy_anomaly_count=description_discrepancy_count,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            by_hospital=by_hospital,
            by_type=by_type,
            by_severity=by_severity,
            trend_data=trend_data,
        )

    def _get_trend_data(
        self,
        hospital_id: Optional[int],
        start_date: Optional[date],
        end_date: Optional[date],
    ) -> List[Dict[str, Any]]:
        if not start_date:
            start_date = date.today() - timedelta(days=30)
        if not end_date:
            end_date = date.today()

        trend_data = []
        current_date = start_date
        while current_date <= end_date:
            day_start = datetime.combine(current_date, datetime.min.time())
            day_end = datetime.combine(current_date, datetime.max.time())

            count = self.db.query(func.count(AnomalyRecord.id)).filter(
                AnomalyRecord.is_deleted == False,
                AnomalyRecord.is_false_positive == False,
                AnomalyRecord.detected_at >= day_start,
                AnomalyRecord.detected_at <= day_end,
            ).scalar() or 0

            if hospital_id:
                count = self.db.query(func.count(AnomalyRecord.id)).filter(
                    AnomalyRecord.hospital_id == hospital_id,
                    AnomalyRecord.is_deleted == False,
                    AnomalyRecord.is_false_positive == False,
                    AnomalyRecord.detected_at >= day_start,
                    AnomalyRecord.detected_at <= day_end,
                ).scalar() or 0

            trend_data.append({
                "date": current_date.isoformat(),
                "count": count,
            })
            current_date += timedelta(days=1)

        return trend_data

    def get_persistent_anomaly_rooms(
        self,
        hospital_id: Optional[int] = None,
        consecutive_months: int = 3,
    ) -> List[Dict[str, Any]]:
        from ..models import PersistentAnomalyRoom

        query = self.db.query(PersistentAnomalyRoom).filter(
            PersistentAnomalyRoom.is_deleted == False,
            PersistentAnomalyRoom.is_resolved == False,
            PersistentAnomalyRoom.consecutive_months >= consecutive_months,
        )

        if hospital_id:
            query = query.filter(PersistentAnomalyRoom.hospital_id == hospital_id)

        rooms = query.order_by(PersistentAnomalyRoom.consecutive_months.desc()).all()
        return [
            {
                "id": r.id,
                "hospital_id": r.hospital_id,
                "room_id": r.room_id,
                "room_name": r.room_name,
                "anomaly_type": r.anomaly_type,
                "anomaly_count": r.anomaly_count,
                "consecutive_months": r.consecutive_months,
                "anomaly_rate": r.anomaly_rate,
                "severity_level": r.severity_level,
                "rectification_status": r.rectification_status,
                "progress": r.progress,
            }
            for r in rooms
        ]
