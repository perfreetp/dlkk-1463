from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date
from sqlalchemy.orm import Session
import operator
import re

from ..models import QualityRule, RuleCategory, Examination, ImageQuality, BIRADSReport, AnomalyRecord
from ..schemas import (
    QualityRuleCreate,
    QualityRuleUpdate,
    RuleCategoryCreate,
    RuleCategoryUpdate,
    QualityRuleTestResult,
)
from ..core.exceptions import NotFoundError, ValidationError, BusinessError
from ..core.logger import get_logger
from ..core.utils import validate_mammo_views, validate_birads_classification, validate_breast_density

logger = get_logger(__name__)


class RuleEngine:
    OPERATORS = {
        "==": operator.eq,
        "!=": operator.ne,
        ">": operator.gt,
        ">=": operator.ge,
        "<": operator.lt,
        "<=": operator.le,
        "contains": lambda a, b: b in str(a) if a else False,
        "in": lambda a, b: a in b if isinstance(b, (list, set, tuple)) else False,
        "not_in": lambda a, b: a not in b if isinstance(b, (list, set, tuple)) else False,
        "regex": lambda a, b: bool(re.search(b, str(a))) if a else False,
        "is_empty": lambda a, b: not bool(a),
        "is_not_empty": lambda a, b: bool(a),
    }

    def __init__(self):
        self.custom_validators = {
            "position_completeness": self._validate_position_completeness,
            "birads_classification": self._validate_birads,
            "breast_density": self._validate_density,
            "view_count": self._validate_view_count,
        }

    def evaluate_rule(self, rule: QualityRule, examination: Examination) -> Tuple[bool, Dict[str, Any]]:
        try:
            if rule.rule_type == "custom" and rule.rule_logic in self.custom_validators:
                return self.custom_validators[rule.rule_logic](rule, examination)

            if rule.condition_expression:
                return self._evaluate_expression(rule, examination)

            if rule.threshold_value and rule.threshold_operator:
                return self._evaluate_threshold(rule, examination)

            return True, {}

        except Exception as e:
            logger.error(f"Rule evaluation error for rule {rule.code}: {e}")
            return False, {"error": str(e)}

    def _validate_position_completeness(
        self, rule: QualityRule, examination: Examination
    ) -> Tuple[bool, Dict[str, Any]]:
        is_complete = validate_mammo_views(examination.views or "", examination.laterality)
        detail = {
            "laterality": examination.laterality,
            "views": examination.views,
            "is_complete": is_complete,
        }
        return is_complete, detail

    def _validate_birads(self, rule: QualityRule, examination: Examination) -> Tuple[bool, Dict[str, Any]]:
        if not examination.birads_report:
            return False, {"error": "No BIRADS report"}
        birads = examination.birads_report.birads_classification
        is_valid = validate_birads_classification(birads)
        return is_valid, {"birads_classification": birads, "is_valid": is_valid}

    def _validate_density(self, rule: QualityRule, examination: Examination) -> Tuple[bool, Dict[str, Any]]:
        if not examination.birads_report:
            return False, {"error": "No BIRADS report"}
        density = examination.birads_report.breast_density
        is_valid = validate_breast_density(density) if density else False
        return is_valid, {"breast_density": density, "is_valid": is_valid}

    def _validate_view_count(self, rule: QualityRule, examination: Examination) -> Tuple[bool, Dict[str, Any]]:
        required = 4 if examination.laterality.upper() == "BILATERAL" else 2
        actual = examination.view_count or 0
        is_ok = actual >= required
        return is_ok, {"required": required, "actual": actual, "is_ok": is_ok}

    def _evaluate_expression(
        self, rule: QualityRule, examination: Examination
    ) -> Tuple[bool, Dict[str, Any]]:
        try:
            context = self._build_context(examination)
            allowed_globals = {
                "abs": abs,
                "len": len,
                "any": any,
                "all": all,
            }
            result = eval(rule.condition_expression, allowed_globals, context)
            return bool(result), {"expression": rule.condition_expression, "result": result}
        except Exception as e:
            return False, {"error": f"Expression evaluation failed: {e}"}

    def _evaluate_threshold(
        self, rule: QualityRule, examination: Examination
    ) -> Tuple[bool, Dict[str, Any]]:
        context = self._build_context(examination)
        field = rule.rule_params.get("field") if rule.rule_params else None
        if not field:
            return False, {"error": "No field specified"}

        actual_value = context.get(field)
        if actual_value is None:
            return False, {"field": field, "value": None, "error": "Field not found"}

        op = self.OPERATORS.get(rule.threshold_operator)
        if not op:
            return False, {"error": f"Unknown operator: {rule.threshold_operator}"}

        try:
            threshold = self._convert_threshold(rule.threshold_value, type(actual_value))
            result = op(actual_value, threshold)
            return bool(result), {
                "field": field,
                "actual": actual_value,
                "operator": rule.threshold_operator,
                "threshold": threshold,
                "result": result,
            }
        except Exception as e:
            return False, {"error": f"Threshold comparison failed: {e}"}

    def _build_context(self, examination: Examination) -> Dict[str, Any]:
        context = {
            "examination": examination,
            "laterality": examination.laterality,
            "views": examination.views,
            "view_count": examination.view_count,
            "compression_pressure": examination.compression_pressure,
            "dose_area_product": examination.dose_area_product,
            "average_glandular_dose": examination.average_glandular_dose,
            "examination_date": examination.examination_date,
        }

        if examination.image_quality:
            iq = examination.image_quality
            context.update({
                "position_completeness": iq.position_completeness,
                "missing_views": iq.missing_views,
                "overall_score": iq.overall_score,
                "contrast_score": iq.contrast_score,
                "noise_score": iq.noise_score,
                "sharpness_score": iq.sharpness_score,
                "is_position_complete": iq.is_position_complete,
                "is_quality_acceptable": iq.is_quality_acceptable,
                "risk_level": iq.risk_level,
            })

        if examination.birads_report:
            br = examination.birads_report
            context.update({
                "breast_density": br.breast_density,
                "birads_classification": br.birads_classification,
                "birads_subcategory": br.birads_subcategory,
                "mass_present": br.mass_present,
                "calcification_present": br.calcification_present,
                "architectural_distortion": br.architectural_distortion,
                "findings_summary": br.findings_summary,
                "impression": br.impression,
                "is_report_complete": br.is_report_complete,
            })

        return context

    def _convert_threshold(self, threshold_str: str, target_type: type):
        if target_type == bool:
            return threshold_str.lower() in ("true", "1", "yes")
        if target_type == int:
            return int(float(threshold_str))
        if target_type == float:
            return float(threshold_str)
        return threshold_str


class QualityRuleService:
    def __init__(self, db: Session):
        self.db = db
        self.rule_engine = RuleEngine()

    def create_category(self, category_data: RuleCategoryCreate, created_by: Optional[int] = None) -> RuleCategory:
        existing = self.db.query(RuleCategory).filter(
            RuleCategory.code == category_data.code,
            RuleCategory.is_deleted == False,
        ).first()
        if existing:
            raise ValidationError(f"分类编码已存在: {category_data.code}")

        category = RuleCategory(**category_data.model_dump())
        if created_by:
            category.created_by = created_by
        self.db.add(category)
        self.db.commit()
        self.db.refresh(category)
        logger.info(f"Created rule category: {category.code}")
        return category

    def update_category(self, category_id: int, update_data: RuleCategoryUpdate, operator_id: Optional[int] = None) -> RuleCategory:
        category = self.db.query(RuleCategory).filter(
            RuleCategory.id == category_id,
            RuleCategory.is_deleted == False,
        ).first()
        if not category:
            raise NotFoundError(f"分类不存在: {category_id}")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(category, key, value)

        if operator_id:
            category.updated_by = operator_id

        self.db.commit()
        self.db.refresh(category)
        return category

    def list_categories(self, parent_id: Optional[int] = None, is_active: Optional[bool] = None) -> List[RuleCategory]:
        query = self.db.query(RuleCategory).filter(RuleCategory.is_deleted == False)

        if parent_id is not None:
            query = query.filter(RuleCategory.parent_id == parent_id)
        if is_active is not None:
            query = query.filter(RuleCategory.is_active == is_active)

        categories = query.order_by(RuleCategory.sort_order).all()
        return categories

    def get_category(self, category_id: int) -> RuleCategory:
        category = self.db.query(RuleCategory).filter(
            RuleCategory.id == category_id,
            RuleCategory.is_deleted == False,
        ).first()
        if not category:
            raise NotFoundError(f"分类不存在: {category_id}")
        return category

    def get_category_tree(self, hospital_id: Optional[int] = None) -> List[Dict[str, Any]]:
        categories = self.db.query(RuleCategory).filter(
            RuleCategory.is_deleted == False,
            RuleCategory.is_active == True,
        ).order_by(RuleCategory.sort_order).all()
        return self._build_tree(categories)

    def _build_tree(self, categories: List[RuleCategory], parent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        tree = []
        for cat in categories:
            if cat.parent_id == parent_id:
                children = self._build_tree(categories, cat.id)
                tree.append({
                    "id": cat.id,
                    "code": cat.code,
                    "name": cat.name,
                    "description": cat.description,
                    "sort_order": cat.sort_order,
                    "children": children,
                })
        return tree

    def create_rule(self, rule_data: QualityRuleCreate, created_by: Optional[int] = None) -> QualityRule:
        existing = self.db.query(QualityRule).filter(
            QualityRule.code == rule_data.code,
            QualityRule.is_deleted == False,
        ).first()
        if existing:
            raise ValidationError(f"规则编码已存在: {rule_data.code}")

        rule = QualityRule(**rule_data.model_dump())
        if created_by:
            rule.created_by = created_by
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)
        logger.info(f"Created quality rule: {rule.code}")
        return rule

    def update_rule(self, rule_id: int, update_data: QualityRuleUpdate, operator_id: Optional[int] = None) -> QualityRule:
        rule = self.db.query(QualityRule).filter(
            QualityRule.id == rule_id,
            QualityRule.is_deleted == False,
        ).first()
        if not rule:
            raise NotFoundError(f"规则不存在: {rule_id}")

        update_dict = update_data.model_dump(exclude_unset=True)
        for key, value in update_dict.items():
            setattr(rule, key, value)

        if operator_id:
            rule.updated_by = operator_id

        self.db.commit()
        self.db.refresh(rule)
        return rule

    def get_rule(self, rule_id: int) -> QualityRule:
        rule = self.db.query(QualityRule).filter(
            QualityRule.id == rule_id,
            QualityRule.is_deleted == False,
        ).first()
        if not rule:
            raise NotFoundError(f"规则不存在: {rule_id}")
        return rule

    def list_rules(
        self,
        category_id: Optional[int] = None,
        hospital_id: Optional[int] = None,
        rule_type: Optional[str] = None,
        severity: Optional[str] = None,
        is_active: Optional[bool] = None,
        keyword: Optional[str] = None,
        is_standard: Optional[bool] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[QualityRule], int]:
        query = self.db.query(QualityRule).filter(QualityRule.is_deleted == False)

        if category_id:
            query = query.filter(QualityRule.category_id == category_id)
        if rule_type:
            query = query.filter(QualityRule.rule_type == rule_type)
        if severity:
            query = query.filter(QualityRule.severity_level == severity)
        if is_active is not None:
            query = query.filter(QualityRule.is_active == is_active)
        if is_standard is not None:
            query = query.filter(QualityRule.is_standard == is_standard)
        if keyword:
            keyword_pattern = f"%{keyword}%"
            query = query.filter(
                (QualityRule.code.like(keyword_pattern)) | (QualityRule.name.like(keyword_pattern))
            )

        total = query.count()
        rules = query.order_by(QualityRule.created_at.desc()).offset(skip).limit(limit).all()
        return rules, total

    def get_active_rules(
        self,
        rule_type: Optional[str] = None,
        hospital_id: Optional[int] = None,
    ) -> List[QualityRule]:
        query = self.db.query(QualityRule).filter(
            QualityRule.is_deleted == False,
            QualityRule.is_active == True,
        )

        if rule_type:
            query = query.filter(QualityRule.rule_type == rule_type)

        rules = query.all()

        if hospital_id:
            rules = [
                r for r in rules
                if not r.applicable_hospitals or hospital_id in r.applicable_hospitals
            ]

        return rules

    def test_rule(self, rule_id: int, test_data: Dict[str, Any]) -> QualityRuleTestResult:
        rule = self.get_rule(rule_id)

        examination = Examination(
            id=0,
            hospital_id=test_data.get("hospital_id", 0),
            accession_number="TEST001",
            examination_date=date.today(),
            laterality=test_data.get("laterality", "BILATERAL"),
            views=test_data.get("views", ""),
            view_count=test_data.get("view_count", 0),
        )

        if test_data.get("image_quality"):
            examination.image_quality = ImageQuality(**test_data["image_quality"])

        if test_data.get("birads_report"):
            examination.birads_report = BIRADSReport(**test_data["birads_report"])

        import time
        start_time = time.time()
        result, detail = self.rule_engine.evaluate_rule(rule, examination)
        execution_time = (time.time() - start_time) * 1000

        return QualityRuleTestResult(
            rule_id=rule.id,
            rule_name=rule.name,
            test_result=result,
            match_details=str(detail),
            execution_time_ms=execution_time,
        )

    def apply_rule_to_examination(self, rule: QualityRule, examination: Examination) -> Tuple[bool, Dict[str, Any]]:
        return self.rule_engine.evaluate_rule(rule, examination)

    def update_rule_stats(self, rule_id: int, passed: bool):
        rule = self.get_rule(rule_id)
        if passed:
            rule.pass_count += 1
        else:
            rule.failure_count += 1
        self.db.commit()

    def get_group_standard_rules(self) -> List[QualityRule]:
        return self.db.query(QualityRule).filter(
            QualityRule.is_deleted == False,
            QualityRule.is_active == True,
            QualityRule.is_standard == True,
        ).all()

    def toggle_rule_active(self, rule_id: int, is_active: bool, operator_id: Optional[int] = None) -> QualityRule:
        rule = self.get_rule(rule_id)
        rule.is_active = is_active
        if operator_id:
            rule.updated_by = operator_id
        self.db.commit()
        self.db.refresh(rule)
        logger.info(f"Toggled rule {rule.code} active status to {is_active}")
        return rule

    def apply_rules_to_examination(self, exam_id: int, rule_ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        examination = self.db.query(Examination).filter(
            Examination.id == exam_id,
            Examination.is_deleted == False,
        ).first()
        if not examination:
            raise NotFoundError(f"检查记录不存在: {exam_id}")

        if rule_ids:
            rules = self.db.query(QualityRule).filter(
                QualityRule.id.in_(rule_ids),
                QualityRule.is_deleted == False,
                QualityRule.is_active == True,
            ).all()
        else:
            rules = self.get_active_rules()

        results = []
        for rule in rules:
            try:
                passed, details = self.apply_rule_to_examination(rule, examination)
                self.update_rule_stats(rule.id, passed)
            except Exception as e:
                logger.error(f"Error applying rule {rule.code} to exam {exam_id}: {e}")
                passed = False
                details = {"error": str(e)}
            results.append({
                "rule_id": rule.id,
                "rule_name": rule.name,
                "passed": passed,
                "details": details,
            })
        return results

    def get_rule_statistics(
        self,
        rule_id: int,
        hospital_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        rule = self.get_rule(rule_id)

        query = self.db.query(AnomalyRecord).filter(
            AnomalyRecord.rule_id == rule_id,
            AnomalyRecord.is_deleted == False,
        )

        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)
        if start_date:
            query = query.filter(AnomalyRecord.detected_at >= start_date)
        if end_date:
            query = query.filter(AnomalyRecord.detected_at <= end_date)

        anomaly_count = query.count()
        pass_count = rule.pass_count or 0
        failure_count = rule.failure_count or 0
        total_count = pass_count + failure_count
        pass_rate = (pass_count / total_count * 100) if total_count > 0 else 0.0

        return {
            "rule_id": rule_id,
            "rule_name": rule.name,
            "pass_count": pass_count,
            "failure_count": failure_count,
            "total_count": total_count,
            "pass_rate": round(pass_rate, 2),
            "anomaly_triggered_count": anomaly_count,
        }

    def publish_rules(
        self,
        rule_ids: List[int],
        target_hospital_ids: List[int],
        operator_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        rules = self.db.query(QualityRule).filter(
            QualityRule.id.in_(rule_ids),
            QualityRule.is_deleted == False,
        ).all()

        published_count = 0
        for rule in rules:
            rule.applicable_hospitals = target_hospital_ids
            if operator_id:
                rule.updated_by = operator_id
            published_count += 1

        self.db.commit()
        logger.info(f"Published {published_count} rules to hospitals: {target_hospital_ids}")

        return {
            "published_count": published_count,
            "rule_ids": [r.id for r in rules],
            "target_hospitals": target_hospital_ids,
        }

    def get_rule_execution_history(
        self,
        rule_id: Optional[int] = None,
        hospital_id: Optional[int] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[Dict[str, Any]], int]:
        query = self.db.query(AnomalyRecord).filter(AnomalyRecord.is_deleted == False)

        if rule_id:
            query = query.filter(AnomalyRecord.rule_id == rule_id)
        if hospital_id:
            query = query.filter(AnomalyRecord.hospital_id == hospital_id)
        if start_date:
            query = query.filter(AnomalyRecord.detected_at >= start_date)
        if end_date:
            query = query.filter(AnomalyRecord.detected_at <= end_date)

        total = query.count()
        records = query.order_by(AnomalyRecord.detected_at.desc()).offset(skip).limit(limit).all()

        result = []
        for ar in records:
            rule = None
            if ar.rule_id:
                rule = self.db.query(QualityRule).filter(QualityRule.id == ar.rule_id).first()
            result.append({
                "id": ar.id,
                "rule_id": ar.rule_id,
                "rule_name": rule.name if rule else "",
                "examination_id": ar.examination_id,
                "hospital_id": ar.hospital_id,
                "anomaly_type": ar.anomaly_type,
                "severity_level": ar.severity_level,
                "detected_at": ar.detected_at,
                "is_confirmed": ar.is_confirmed,
            })

        return result, total
